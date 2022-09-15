# Copyright 2020 Mischief Gadgets LLC

import os
import sys
import glob
import platform

VERSION="FIRMWARE FLASHER VERSION NUMBER [ 040120 @ 203515 CST ] .[d]."
UPDATES="FOR UPDATES VISIT: [ https://github.com/O-MG/O.MG_Cable-Firmware ]\n"

MOTD="""\
               ./ohds. -syhddddhys: .oddo/.
                `: oMM+ dMMMMMMMMm`/MMs :`
             `/hMh`:MMm .:-....-:- hMM+`hMh/
           `oNMm:`sMMN:`:+osssso+:`-NMMy.:dMNo`
          +NMMs +NMMh`:mMMMMMMMMMMN/`yMMNo +MMN+
        .dMMMy sMMMh oMNhs+////+shNMs yMMMy sMMMd.
       -NMMM+  NMMMd`-.  `.::::.`  .:`hMMMM` +MMMN-
      -NMMN-   hMMMMMdhhmMMMMMMMMmhhdNMMMMd   -NMMN.
      mMMM- `m:`hMMMMMMMMMmhyyhmMMMMMMMMMd.-d` -MMMm
     +MMMs  dMMs -sMMMMm+`      `+mMMMMs: oMMh  sMMM+
     dMMM` :MMMy  oMMMy            yMMMo  hMMM: `MMMd
     MMMm  sMMM:  NMMN              NMMN  :MMMs  mMMM
    `MMMd  yMMM- `MMMd              dMMM` :MMMs  dMMM`
     NMMN  +MMMo  dMMM:            :MMMN. +MMM+  NMMN
     yMMM/ `NMMN` .NMMN+          +MMMMMMh.+MN` /MMMy
     .MMMm` /MMMd` .hMMMNy+:--:+yNMMMdsNMMN.+/ `mMMM.
      +MMMh  +MMMN/  :hMMMMMMMMMMMMh:  yMMM/   hMMM+
       sMMMh` -mMMMd/` `:oshhhhy+:` `/dMMMh  `hMMMs
        oMMMN/  +mMMMMho:.      .:ohMMMMm/  :NMMMo
         -mMMMd:  :yNMMMMMMNNNNMMMMMMNy:  :dMMMm-
           +NMMMmo   -+shmNMMMMNmhs+-  .omMMMN+
            `/dNo.:/              `-+ymMMMMd/
                /mM-.:/+ossyyhhdmNMMMMMMdo.
              -mMMMMMMMMMMMMMMMMMMNdy+-
             /MMMMMMmyso+//::--.`
            :MMMMNNNNs-
           `Ndo:`    `.`
           :-\
"""



def omg_tos():
    message = """
Agreement
O.MG Cable, O.MG Adapter, and O.MG Plug are trademarks of Mischief Gadgets, LLC. Mischief 
Gadgets, LLC requires that all users read and accept the provisions of the Terms of Use 
Policy and the Privacy Policy prior to granting users any authorization to use pentesting 
hardware created by Mischief Gadgets, LLC and/or its affiliates. The Terms of Use Policy 
and the Privacy Policy can be found at https://o.mg.lol, and must be affirmatively 
consented to by users prior to using any pentesting hardware created by Mischief Gadgets, 
LLC and/or its affiliates (hereinafter referred to as “O.MG Devices”). Reading and 
Accepting the Terms of Use and the Privacy Policy are REQUIRED CONSIDERTIONS for Mischief 
Gadgets, LLC and/or its affiliates granting users the right to use any O.MG Device. 
All persons are DENIED permission to use any O.MG Device, unless they read and affirmatively
accept the Terms of Use Policy and the Privacy Policy located at https://o.mg.lol.

Privacy Policy
All persons under the age of 18 are denied access to the website located at https://o.mg.lol,
as well as denied authorization to use any O.MG Device. If you are under the age of 18, it 
is unlawful for you to visit, communicate, or interact with Mischief Gadgets, LLC and/or 
its affiliates in any manner. Mischief Gadgets, LLC and/or its affiliates specifically 
denies access to any individual that is covered by the Child Online Privacy Act (COPA) of 1998.

Mischief Gadgets, LLC and/or its affiliates reserve the right to deny access to any person
or viewer for any reason. Under the provisions of this Privacy Policy, Mischief Gadgets, 
LLC and/or its affiliates are allowed to collect and store data and information for the 
purpose of exclusion, and for any other uses seen fit.

Mischief Gadgets, LLC and/or its affiliates have established safeguards to help prevent 
unauthorized access to or misuse of your information but cannot guarantee that your 
information will never be disclosed in a manner inconsistent with this Privacy Policy 
(for example, as a result of any unauthorized act by third parties that violate applicable 
law or our affiliates’ policies). To protect your privacy and security, we may use passwords
or other technologies to register or authenticate you and enable you to take advantage of 
our services, and before granting access or making corrections to your information.

Mischief Gadgets, LLC and/or its affiliates do not rent or sell your personally identifiable
information (such as name, address, telephone number, and credit card information) to 
third parties for their marketing purposes.

This Privacy Policy may change from time to time. Users have an affirmative duty, as part
of the consideration for permission to use O.MG Devices, to keep themselves informed of 
changes to this Privacy Policy. All changes to this Privacy Policy will be posted
at https://o.mg.lol.


Terms of Use
Pentesting hardware designed by Mischief Gadgets, LLC and/or its affiliates (hereinafter 
referred to as “O.MG Devices”) are network administration and pentesting tools used for 
authorized auditing and security analysis purposes only where permitted, subject to local
and international laws where applicable. Users are solely responsible for compliance with
all laws of their locality. Mischief Gadgets, LLC and/or its affiliates claim no 
responsibility for unauthorized or unlawful use.

O.MG Devices are packaged with a limited warranty, the acceptance of which is a condition 
of sale. See https://o.mg.lol for additional warranty details and limitations. 
Availability and performance of certain features, services, and applications are device 
and network dependent and may not be available in all areas; additional terms, conditions
and/or charges may apply.

You agree not to access or use any O.MG Device or the website located at https://o.mg.lol 
in any unlawful way or for any unlawful or illegitimate purpose or in any manner that 
contravenes this Agreement. You shall not use any O.MG Device to post, use, store, or
transmit any information that is unlawful, libelous, defamatory, obscene, fraudulent, 
predatory of minors, harassing, threatening or hateful towards any individual, this
includes any information that infringes or violates any of the intellectual property 
rights of others or the privacy rights of others. You shall not use any O.MG Device 
to attempt to disturb the peace by any method, including through use of viruses, 
Trojan horses, worms, time bombs, denial of service attacks, flooding or spamming. 
You shall not use any O.MG Device in any manner that could damage, disable or impair 
Mischief Gadgets, LLC and/or its affiliates, or any third-party. You shall not use any
O.MG Device to attempt to gain unauthorized access to any user account, computer systems,
or networks through hacking, password mining or any other means. You shall not use any 
O.MG Device alongside any robot, data scraper, miner or virtual computer to gain unlawful
access to protected computer systems.

All features, functionality and other product specifications are subject to change without
notice or obligation. Mischief Gadgets, LLC and/or its affiliates reserve the right to
make changes to the product description in this document without notice. Mischief Gadgets,
LLC and/or its affiliates do not assume any liability that may occur due to the use or 
application of the product(s) described herein.

These terms and conditions shall be governed by and construed in accordance with the laws 
of the state of New York, United States of America, and you agree to submit to the personal
jurisdiction of the courts of the state of New York. In the event that any portion of these
terms and conditions is deemed by a court to be invalid, the remaining provisions shall
remain in full force and effect. You agree that regardless of any statute or law to the
contrary, any claim or cause of action arising out of or related to this Web site, or the
use of this Website, must be filed within one year after such claim or cause of action 
arose and must be filed in a court in New York, New York, U.S.A.

As required by Section 512(c)(2) of Title 17 of the United States Code, if you believe 
that any material on the website located at https://o.mg.lol infringes your copyright, 
you must send a notice of claimed infringement to Mischief Gadget, LLC’s General Counsel 
at the following address:

    c/o Mischief Gadgets, LLC - General Counsel

    Tor Ekeland Law, PLLC

    30 Wall St., 8th Floor

    New York, NY 10005

    [info@torekeland.com]

If you do not agree to be bound by this Agreement, do not access or use any O.MG Device, 
or the website located at https://o.mg.lol. We reserve the right, with or without notice,
to make changes to this Agreement at our discretion. Continued use of any O.MG Device or
the website located at https://o.mg.lol constitutes your acceptance of these Terms, 
as they may appear at the time of your access.

By continuing, by availing yourself of any O.MG Device or the website located at 
https://o.mg.lol, or by accessing, visiting, browsing, using or attempting to interact
with or use any O.MG Device or the website located at https://o.mg.lol, you agree that
you have read, understand, and agree to be bound by this Agreement as well as our 
Privacy Policy, which is a part of this Agreement and which can be viewed here: 
https://o.mg.lol.
"""
    print("\n\nTo use this flashing tool and O.MG Devices you must agree to the following\n\n")
    try:
        from scripts import pager as pager
        from io import StringIO
        f = StringIO(message)
        pager.page(f)
    except KeyError:
        print(message)
    print("\n\nTo use this flashing tool and O.MG Devices you must agree to the following\n\n")
    INPUT_CORRECT = False
    USER_AGREED = False
    while not INPUT_CORRECT:
        print("\n\nDo you agree? You must type yes or no\n\n")
        user_response = str(input("Select Option: ")).replace(" ","").lower().strip()
        if "yes" in user_response:
            INPUT_CORRECT = True
            USER_AGREED = True
        if "no" in user_response:
            INPUT_CORRECT = True
            USER_AGREED = False    
    if USER_AGREED:
        return True
    else:
        print("<<< DID NOT AGREE TO TERMS OF SERVICE. CANNOT CONTINUE >>>")
        sys.exit(1)

class omg_results():
    def __init__(self):
        self.OS_DETECTED = ""
        self.PORT_FOUND = False
        self.PORT_PATH = ""
        self.WIFI_DEFAULTS = False
        self.WIFI_SSID = "O.MG-Cable"
        self.WIFI_PASS = "12345678"
        self.WIFI_MODE = "1"
        self.WIFI_TYPE = "STATION"
        self.FILE_PAGE = "page.mpfs"
        self.FILE_INIT = "esp_init_data_default_v08.bin"
        self.FILE_ELF0 = "image.elf-0x00000.bin"
        self.FILE_ELF1 = "image.elf-0x10000.bin"


def complete(statuscode,message="Press Enter to continue..."):
    input(message)
    sys.exit(statuscode)

def omg_locate():

    PAGE_LOCATED = False
    INIT_LOCATED = False
    ELF0_LOCATED = False
    ELF1_LOCATED = False

    if os.path.isfile(results.FILE_PAGE):
        PAGE_LOCATED = True
    else:
        if os.path.isfile("firmware/" + results.FILE_PAGE):
            results.FILE_PAGE = "firmware/" + results.FILE_PAGE
            PAGE_LOCATED = True

    if os.path.isfile(results.FILE_INIT):
        INIT_LOCATED = True
    else:
        if os.path.isfile("firmware/" + results.FILE_INIT):
            results.FILE_INIT = "firmware/" + results.FILE_INIT
            INIT_LOCATED = True

    if os.path.isfile(results.FILE_ELF0):
        ELF0_LOCATED = True
    else:
        if os.path.isfile("firmware/" + results.FILE_ELF0):
            results.FILE_ELF0 = "firmware/" + results.FILE_ELF0
            ELF0_LOCATED = True

    if os.path.isfile(results.FILE_ELF1):
        ELF1_LOCATED = True
    else:
        if os.path.isfile("firmware/" + results.FILE_ELF1):
            results.FILE_ELF1 = "firmware/" + results.FILE_ELF1
            ELF1_LOCATED = True

    if PAGE_LOCATED and INIT_LOCATED and ELF0_LOCATED and ELF1_LOCATED:
        print("\n<<< ALL FIRMWARE FILES LOCATED >>>\n")
    else:
        print("<<< SOME FIRMWARE FILES ARE MISSING, PLACE THEM IN THIS FILE'S DIRECTORY >>>")
        if not PAGE_LOCATED: print("\n\tMISSING FILE: {PAGE}".format(PAGE=results.FILE_PAGE))
        if not INIT_LOCATED: print("\tMISSING FILE: {INIT}".format(INIT=results.FILE_INIT))
        if not ELF0_LOCATED: print("\tMISSING FILE: {ELF0}".format(ELF0=results.FILE_ELF0))
        if not ELF1_LOCATED: print("\tMISSING FILE: {ELF1}".format(ELF1=results.FILE_ELF1))
        print('')
        complete(1)

def omg_probe():

    devices = ""
    results.PORT_FOUND = False

    if results.OS_DETECTED == "WINDOWS":
        print("<<< PROBING WINDOWS COMPORTS FOR O.MG-CABLE-PROGRAMMER >>>\n")
        for i in range(1, 256):
            try:
                comport = "COM{PORT}".format(PORT=i)
                command = [ '--baud', '115200', '--port', comport, '--no-stub', 'chip_id' ]
                esptool.main(command)
                results.PORT_FOUND = True
                results.PORT_PATH = comport
                break
            except:
                pass

        if results.PORT_FOUND:
            print("\n<<< O.MG-CABLE-PROGRAMMER WAS FOUND ON {PORT} >>>".format(PORT=results.PORT_PATH))
        else:
            print("<<< O.MG-CABLE-PROGRAMMER WAS NOT FOUND ON THESE COMPORTS >>>\n")
            complete(1)

    elif results.OS_DETECTED == "DARWIN":
        print("<<< PROBING OSX DEVICES FOR O.MG-CABLE-PROGRAMMER >>>\n")
        devices = glob.glob("/dev/cu.*SLAB*UART*")
        devices += glob.glob("/dev/cu.usbserial*")
    elif results.OS_DETECTED == "LINUX":
        print("<<< PROBING LINUX DEVICES FOR O.MG-CABLE-PROGRAMMER >>>\n")
        devices = glob.glob("/dev/ttyUSB*")

    if results.OS_DETECTED == "DARWIN" or results.OS_DETECTED == "LINUX":
        for i in range(len(devices)):
            try:
                devport = "{PORT}".format(PORT=devices[i])
                command = [ '--baud', '115200', '--port', devport, '--no-stub', 'chip_id' ]
                esptool.main(command)
                results.PORT_FOUND = True
                results.PORT_PATH = devices[i]
                break
            except:
                pass

        if results.PORT_FOUND:
            from pprint import pprint
            pprint(results)
            print("\n<<< O.MG-CABLE-PROGRAMMER WAS FOUND AT %s >>>"%(str(results.PORT_PATH)))
        else:
            if results.OS_DETECTED == "DARWIN":
                print("<<< O.MG-CABLE-PROGRAMMER WAS NOT FOUND IN DEVICES, YOU MAY NEED TO INSTALL THE DRIVERS FOR CP210X USB BRIDGE >>>\n")
                print("VISIT: [ https://www.silabs.com/products/development-tools/software/usb-to-uart-bridge-vcp-drivers ]\n")
            else:
                print("<<< O.MG-CABLE-PROGRAMMER WAS NOT FOUND IN DEVICES >>>\n")
            complete(1)

def omg_patch(_ssid, _pass, _mode):

    FILE_PAGE = results.FILE_PAGE

    try:
        BYTES = []
        with open(FILE_PAGE, "rb") as f:
            byte = f.read(1)
            BYTES.append(byte)
            while byte != b"":
                byte = f.read(1)
                BYTES.append(byte)

            offset = 0

            for i, byte in enumerate(BYTES):
                if chr(int(hex(int.from_bytes(BYTES[i+0],"big"))[2:].upper(),16)) == 'a':
                    if chr(int(hex(int.from_bytes(BYTES[i+1],"big"))[2:].upper(),16)) == 'c':
                        if chr(int(hex(int.from_bytes(BYTES[i+2],"big"))[2:].upper(),16)) == 'c':
                            if chr(int(hex(int.from_bytes(BYTES[i+3],"big"))[2:].upper(),16)) == 'e':
                                if chr(int(hex(int.from_bytes(BYTES[i+4],"big"))[2:].upper(),16)) == 's':
                                    if chr(int(hex(int.from_bytes(BYTES[i+5],"big"))[2:].upper(),16)) == 's':
                                        if chr(int(hex(int.from_bytes(BYTES[i+6],"big"))[2:].upper(),16)) == '.':
                                            if chr(int(hex(int.from_bytes(BYTES[i+7],"big"))[2:].upper(),16)) == 'l':
                                                if chr(int(hex(int.from_bytes(BYTES[i+8],"big"))[2:].upper(),16)) == 'o':
                                                    if chr(int(hex(int.from_bytes(BYTES[i+9],"big"))[2:].upper(),16)) == 'g':
                                                        offset = i
                                                        break
        offset+=24
        d=hex(int.from_bytes(BYTES[offset+0],"big"))[2:].zfill(2)
        c=hex(int.from_bytes(BYTES[offset+1],"big"))[2:].zfill(2)
        b=hex(int.from_bytes(BYTES[offset+2],"big"))[2:].zfill(2)
        a=hex(int.from_bytes(BYTES[offset+3],"big"))[2:].zfill(2)
        offset=int(a+b+c+d,16)
        length=len("SSID {SSID} PASS {PASS} MODE {MODE}".format(SSID=_ssid,PASS=_pass,MODE=_mode))
        aligned=114
        _bytes=bytearray("SSID {SSID}\0PASS {PASS}\0MODE {MODE}{NULL}".format(SSID=_ssid,PASS=_pass,MODE=_mode,NULL="\0"*(aligned-length)).encode("utf8"))
        for i in range(offset+0,offset+aligned):
            BYTES[i]=_bytes[i-offset]
        try:
            os.remove(FILE_PAGE)
        except:
            pass
        with open(FILE_PAGE, 'bw+') as f:
            for byte in BYTES:
                if type(byte)==int:
                    f.write(bytes([byte]))
                else:
                    f.write(byte)
        print("\n<<< PATCH SUCCESS, FLASHING FIRMWARE >>>\n")
    except:
        print("\n<<< PATCH FAILURE, ABORTING >>>")
        complete(1)

def omg_input():
    print("INPUT PREPARED ")
    WIFI_MODE = ''
    SANITIZED_SELECTION = False

    while not SANITIZED_SELECTION:

        try:
            WIFI_MODE = input("\nSELECT WIFI MODE: 1) STATION or 2) ACCESS POINT or ENTER) DEFAULTS: ")
            if WIFI_MODE == '' or WIFI_MODE == '1' or WIFI_MODE == '2':
                SANITIZED_SELECTION = True
        except:
            pass

    if len(WIFI_MODE) == 1:
        results.WIFI_DEFAULTS = False
        results.WIFI_MODE = WIFI_MODE
        if WIFI_MODE == '1':
            results.WIFI_TYPE = 'STATION'
        else:
            results.WIFI_TYPE = 'ACCESS POINT'
    else:
        results.WIFI_DEFAULTS = True

    if not results.WIFI_DEFAULTS:

        WIFI_SSID = ''
        SANITIZED_SELECTION = False

        while not SANITIZED_SELECTION:
            try:
                WIFI_SSID = input("\nENTER WIFI SSID (limit 1-32chars): ")
                if len(WIFI_SSID) > 1 and len(WIFI_SSID) < 33:
                    SANITIZED_SELECTION = True
            except:
                pass

        results.WIFI_SSID = WIFI_SSID

        WIFI_PASS = ''
        SANITIZED_SELECTION = False

        while not SANITIZED_SELECTION:
            try:
                WIFI_PASS = input("\nENTER WIFI PASS (limit 8-64chars): ")
                if len(WIFI_PASS) > 7 and len(WIFI_PASS) < 65:
                    SANITIZED_SELECTION = True
            except:
                pass

        results.WIFI_PASS = WIFI_PASS

def omg_flash():
    try:
        FILE_PAGE = results.FILE_PAGE
        FILE_INIT = results.FILE_INIT
        FILE_ELF0 = results.FILE_ELF0
        FILE_ELF1 = results.FILE_ELF1

        command = ['--baud', '115200', '--port', results.PORT_PATH, 'write_flash', '-fs', '1MB', '-fm',
                   'dout', '0xfc000', FILE_INIT, '0x00000', FILE_ELF0, '0x10000', FILE_ELF1, '0x80000', FILE_PAGE]
        esptool.main(command)

    except:
        print("\n<<< SOMETHING FAILED WHILE FLASHING >>>")
        complete(1)

def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

if __name__=='__main__':
    print("\n" + VERSION)
    print("\n" + UPDATES)
    print("\n" + MOTD + "\n")

    results = omg_results()

    thedirectory=get_script_path()
    os.chdir(thedirectory)

    omg_tos()
    
    try:
        import serial
    except:
        print("<<< PYSERIAL MODULE MISSING >>> ")
    try:
        import serial
    except:
        print("\n<<< PYSERIAL MODULE MISSING, MANUALLY INSTALL TO CONTINUE >>>")
        complete(1)

    try:
        import esptool
    except:
        try:
            from scripts import esptool as esptool
        except:
            print("<<< ESPTOOL.PY MISSING, PLACE IT IN THIS FILE'S DIRECTORY >>>")
            complete(1)

    results.OS_DETECTED = platform.system().upper()

    omg_locate()

    omg_probe()

    omg_input()

    omg_patch( results.WIFI_SSID, results.WIFI_PASS, results.WIFI_MODE )

    omg_flash()

    print("\n[ WIFI SETTINGS ]")
    print("\n\tWIFI_SSID: {SSID}\n\tWIFI_PASS: {PASS}\n\tWIFI_MODE: {MODE}\n\tWIFI_TYPE: {TYPE}".format(SSID=results.WIFI_SSID, PASS=results.WIFI_PASS, MODE=results.WIFI_MODE, TYPE=results.WIFI_TYPE))

    print("\n[ FIRMWARE USED ]")
    print("\n\tINIT: {INIT}\n\tELF0: {ELF0}\n\tELF1: {ELF1}\n\tPAGE: {PAGE}".format(INIT=results.FILE_INIT, ELF0=results.FILE_ELF0, ELF1=results.FILE_ELF1, PAGE=results.FILE_PAGE))

    print("\n<<< PROCESS FINISHED, REMOVE PROGRAMMER >>>\n")
    complete(0)
   







