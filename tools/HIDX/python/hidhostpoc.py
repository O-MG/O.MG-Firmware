import os,sys,time
from textwrap import wrap

# set these
 
hidx_device = None
transmission_delay = 1 # in seconds, 0 disables
max_message_size = 48 # bytes

# don't do things past here


def do_cmd(cmd):
    c = os.popen(cmd)
    r = c.read()
    return r

# trick found by 01phor1e
def get_linux_dev():
    cmd = "dmesg|grep hidraw|grep hiddev|grep input2|tail -n1|awk -F ',' '{print $2}'|awk -F ':' '{print $1}'"
    try:
        r = str(do_cmd(cmd)).strip()
        return r
    except:
        return None

# trick found by 01phor1e
def debug_linux_dev():
    cmd = "dmesg|grep hidraw|grep hiddev|grep input2"
    try:
        r = str(do_cmd(cmd)).strip()
        return r
    except:
        return "No DMESG output identified"

def debug_linux(fd):
    print("===== Debug: DMESG =====")
    debug_linux_dev()
    print("Found Device at Location: %s"%get_linux_dev())
    print("===== Debug: FD INFO =====")
    if fd is None:
        print("FD Error, no FD")
    else:
        print(os.stat(fd))
        print(os.fstat(fd))
        print(os.lstat(fd))
    print("===== End Debug =====")

def chunk_cmd(result):
    def chunk(o):
        r = str(result)
        s = sys.getsizeof(o)
        if s>max_message_size:
            queued_cmds.extend(wrap(r,max_message_size-1))
        else:
            queued_cmds.append(r)
    if isinstance(result, list) or isinstance(result, tuple):
        for line in result:
            chunk(line)
    else:
        chunk(result)

raw_dev = get_linux_dev()
if raw_dev is not None:
    hidx_device = "/dev/"+raw_dev
else:
    if len(sys.argv) < 2:
        print("error provide hid device")
        sys.exit(1)
    else:
        hidx_device = sys.argv[1]

queued_cmds = []
hs = os.open(hidx_device, os.O_RDWR)

run = True
cmd = ""
tries = 16
while tries>1:
    print("Ready")
    try:
        print("In Listener")
        while run:
            print("Running...")
            try:
                debug_linux(hs)
            except:
                print("HID FD is unreadable")
            debug_linux(hidx_device)
            if hs is None:
                print("Opening Socket...")
                hs = os.open(hidx_device, os.O_RDWR)
            else:
                print("Reusing Socket...")
            r = os.read(hs,int(max_message_size))
            if "\n" in cmd:
                # have a command
                print("Attempting to run cmd: '%s'"%cmd)
                print("Result from cmd is %d"%len(queued_cmds))
                chunk_cmd(do_cmd(cmd))
                cmd = ""
                if len(queued_cmds)>0:
                    for queued_cmd in queued_cmds:
                        queued_cmd = queued_cmd+"\n"
                        os.write(hs,bytearray(queued_cmd.encode("utf-8")))
                        if transmission_delay>0:
                            time.sleep(transmission_delay)
                queued_cmds = []
            else:
                cmd += r.decode("utf-8")
    except OSError as e:
        print("Error with socket, you have %d tries remaining"%tries)
        time.sleep(5)
        try:
            if hs is not None:
                os.close(hs)
                try:
                    debug_linux(hs)
                except:
                    print("HID FD is unreadable")
                debug_linux(hidx_device)
        except:
            print("Socket already closed")
        print(e)
        tries-=1
