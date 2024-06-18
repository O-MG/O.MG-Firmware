# Copyright 2023 Mischief Gadgets LLC

import os
import sys
import json
import glob
import serial
import base64
import platform
import argparse
import platform
import mimetypes
import http.client
import urllib.parse
from sys import exit
from time import time
from math import floor
from signal import signal, SIGINT
from serial.tools import hexlify_codec
from serial.tools.list_ports import comports

from pprint import pprint

try:
    raw_input
except NameError:
    # pylint: disable=redefined-builtin,invalid-name
    raw_input = input   # in python3 it's "raw"
    unichr = chr

if 'idlelib.run' in sys.modules:
    print("!!!! PLEASE DO NOT RUN THIS IN IDLE EDITOR !!!!")
    print("Unexpected outcomes or errors may occur when running in IDLE")
    print("Please launch this by opening your command line or terminal and typing 'python3 flash.py'")
    print("If you have any questions please see the wiki https://github.com/O-MG/O.MG-Firmware/wiki")
    sys.exit(1)

VERSION = "FIRMWARE FLASHER VERSION NUMBER [ 230907 @ 153241 UTC ]"
FLASHER_VERSION = 1 # presume we have an old style flasher = 1
FLASHER_VERSION_DETECT = True

BRANCH = "stable"
FIRMWARE_DIR="./firmware"
FIRMWARE_URL = "https://raw.githubusercontent.com/O-MG/O.MG-Firmware/%BRANCH%"
MEMMAP_URL = "https://raw.githubusercontent.com/O-MG/WebFlasher/main/assets/memmap.json"

UPDATES = "FOR UPDATES VISIT: [ https://github.com/O-MG/O.MG-Firmware ]\n"

MOTD = """\
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
O.MG Cable, O.MG Adapter, and O.MG Plug are trademarks of Mischief Gadgets, 
LLC. Mischief Gadgets, LLC requires that all users read and accept the 
provisions  of the Terms of Use Policy and the Privacy Policy prior to 
granting users any  authorization to use pentesting hardware created by 
Mischief Gadgets, LLC  and/or its affiliates. The Terms of Use Policy and
the Privacy Policy can be  found at  https://o.mg.lol, and must be 
affirmatively consented to by users prior to using any pentesting hardware
created by Mischief Gadgets, LLC and/or its  affiliates (hereinafter referred
to as “O.MG Devices”). Reading and  Accepting the Terms of Use and the Privacy
Policy are REQUIRED CONSIDERTIONS for Mischief Gadgets, LLC and/or its 
affiliates granting users the right to use any  O.MG Device. All persons are 
DENIED permission to use any O.MG Device,  unless they read and affirmatively
accept the Terms of Use Policy and the Privacy Policy located at
https://o.mg.lol.

Privacy Policy
All persons under the age of 18 are denied access to the website located at 
https://o.mg.lol, as well as denied authorization to use any O.MG Device. 
If you are under the age of 18, it is unlawful for you to visit, communicate, 
or interact with Mischief Gadgets, LLC and/or its affiliates in any manner. 
Mischief Gadgets, LLC and/or its affiliates specifically denies access to any
individual that is covered by the Child Online Privacy Act (COPA) of 1998.

Mischief Gadgets, LLC and/or its affiliates reserve the right to deny access 
to any person or viewer for any reason. Under the provisions of this Privacy 
Policy, Mischief Gadgets, LLC and/or its affiliates are allowed to collect and
store data and information for the purpose of exclusion, and for any other 
uses seen fit.

Mischief Gadgets, LLC and/or its affiliates have established safeguards to 
help prevent unauthorized access to or misuse of your information but cannot
guarantee that your information will never be disclosed in a manner 
inconsistent with this Privacy Policy (for example, as a result of any 
unauthorized act by third parties that violate applicable law or our
affiliates’ policies). To protect your privacy and security, we may use 
passwords or other technologies to register or authenticate you and enable
you to take advantage  of our services, and before granting access or making
corrections to your  information.

Mischief Gadgets, LLC and/or its affiliates do not rent or sell your personally
identifiable information (such as name, address, telephone number, and credit 
card information) to third parties for their marketing purposes.

This Privacy Policy may change from time to time. Users have an affirmative 
duty, as part of the consideration for permission to use O.MG Devices, to keep 
themselves informed of changes to this Privacy Policy. All changes to this 
Privacy Policy will be posted at https://o.mg.lol.

Terms of Use
Pentesting hardware designed by Mischief Gadgets, LLC and/or its affiliates 
(hereinafter referred to as “O.MG Devices”) are network administration and 
pentesting tools used for authorized auditing and security analysis purposes
only where permitted, subject to local and international laws where applicable.
Users are solely responsible for compliance with all laws of their locality. 
Mischief Gadgets, LLC and/or its affiliates claim no responsibility for 
unauthorized or unlawful use.

O.MG Devices are packaged with a limited warranty, the acceptance of which is
a condition of sale. See https://o.mg.lol for additional warranty details and
limitations. Availability and performance of certain features, services, and
applications are device and network dependent and may not be available in all
areas; additional terms, conditions and/or charges may apply.

You agree not to access or use any O.MG Device or the website located at 
https://o.mg.lol in any unlawful way or for any unlawful or illegitimate 
purpose or in any manner that contravenes this Agreement. You shall not 
use any O.MG 

Device to post, use, store, or transmit any information that is unlawful, 
libelous, defamatory, obscene, fraudulent, predatory of minors, harassing, 
threatening or hateful towards any individual, this includes any information 
that infringes or violates any of the intellectual property rights of others
or the privacy rights of others. You shall not use any O.MG Device to attempt
to disturb the peace by any method, including through use of viruses, Trojan 
horses, worms, time bombs, denial of service attacks, flooding or spamming. 
You shall not use any O.MG Device in any manner that could damage, disable or
impair Mischief Gadgets, LLC and/or its affiliates, or any third-party. You 
shall not use any O.MG Device to attempt to gain unauthorized access to any 
user account, computer systems, or networks through hacking, password mining 
or any other means. You shall not use any O.MG Device alongside any robot, data
scraper, miner or virtual computer to gain unlawful access to protected 
computer systems.

All features, functionality and other product specifications are subject to 
change without notice or obligation. Mischief Gadgets, LLC and/or its 
affiliates reserve the right to make changes to the product description in 
this document  without notice. Mischief Gadgets, LLC and/or its affiliates 
do not assume any liability that may occur due to the use or application of 
the product(s) described herein.

These terms and conditions shall be governed by and construed in accordance 
with the laws of the state of New York, United States of America, and you 
agree to  submit to the personal jurisdiction of the courts of the state of 
New York. In the event that any portion of these terms and conditions is deemed
by a court to be invalid, the remaining provisions shall remain in full force
and effect.  You agree that regardless of any statute or law to the contrary,
any claim or cause of action arising out of or related to this Web site, or the
use of this Website, must be filed within one year after such claim or cause of 
action arose and must be filed in a court in New York, New York, U.S.A.

As required by Section 512(c)(2) of Title 17 of the United States Code, if you
believe that any material on the website located at https://o.mg.lol infringes
your copyright, you must send a notice of claimed infringement to Mischief 
Gadget, LLC’s General Counsel  at the following address:
    c/o Mischief Gadgets, LLC - General Counsel
    Tor Ekeland Law, PLLC
    30 Wall St., 8th Floor
    New York, NY 10005
    [info@torekeland.com]
If you do not agree to be bound by this Agreement, do not access or use any 
O.MG Device,  or the website located at https://o.mg.lol. We reserve the right, 
with or without notice, to make changes to this Agreement at our discretion. 
Continued use of any O.MG Device or the website located at https://o.mg.lol 
constitutes your acceptance of these Terms,  as they may appear at the time 
of your access.

By continuing, by availing yourself of any O.MG Device or the website located 
at  https://o.mg.lol, or by accessing, visiting, browsing, using or attempting
to interact with or use any O.MG Device or the website located at 
https://o.mg.lol, you agree that you have read, understand, and agree to be 
bound by this Agreement as well as our  Privacy Policy, which is a part of this
Agreement and which can be viewed here: https://o.mg.lol.
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

def omg_dependency_imports():
    # load pyserial
    try:
        global serial
        import serial
    except:
        print("\n<<< PYSERIAL MODULE MISSING, MANUALLY INSTALL TO CONTINUE >>>")
        print("<<< YOU CAN TRY: npm install serial or pip install pyserial >>>")
        complete(1)

    try:
        from scripts import flashapi as flashtest
    except:
        if not os.path.exists('./scripts/'):
            os.mkdir("./scripts/")
        dependencies = ['flashapi.py', 'miniterm.py']
        for dependency in dependencies:
            file_path = "scripts/"+dependency
            file_url = FIRMWARE_URL.replace("%BRANCH%",BRANCH) + "/scripts/" + dependency
            try:
                res = get_resource_file(file_url)
                if res['status'] == 200:
                    with open(file_path,"wb") as f:
                            f.write(res['data'])
                    print("succesfully fetched missing dependency %s from %s"%(dependency,file_url))
            except:
                print("failed to get missing dependency %s from %s"%(dependency,file_url))
    try:
        global flashapi
        from scripts import flashapi as flashapi 
    except:
        print("<<< flashapi.PY MISSING FROM scripts/flashapi.py >>>")
        print("<<< PLEASE MANUALLY DOWNLOAD FROM https://github.com/O-MG/O.MG-Firmware >>>")
        complete(1)

def handler(signal_received, frame):
    # Handle any cleanup here
    print('SIGINT or CTRL-C detected. Exiting gracefully')
    exit(0)

class omg_results():
    def __init__(self):
        self.OS_DETECTED = ""
        self.PROG_FOUND = False
        self.PORT_PATH = ""
        self.WIFI_DEFAULTS = False
        self.WIFI_SSID = "O.MG"
        self.WIFI_PASS = "12345678"
        self.WIFI_MODE = "2"
        self.WIFI_TYPE = "STATION"
        self.FILE_PAGE = "page.mpfs"
        self.FILE_INIT = "esp_init_data_default_v08.bin"
        self.FILE_ELF0 = "image.elf-0x00000.bin"
        self.FILE_ELF1 = "image.elf-0x10000.bin"
        self.FILE_BLANK = "blank.bin"
        self.FILE_OFAT_INIT = "blank-settings.bin"
        self.FLASH_SLOTS = 4
        self.FLASH_PAYLOAD_SIZE = 60
        self.NUMBER_SLOTS = 50

def get_dev_info(dev):
    esp = flashapi.ESP8266ROM(dev, baudrate, None)
    esp.connect(None)
    mac = esp.read_mac()

    esp.flash_spi_attach(0)
    flash_id = esp.flash_id()
    size_id = flash_id >> 16
    flash_size = {0x14: 0x100000, 0x15: 0x200000, 0x16: 0x400000}[size_id]
    return mac, flash_size

def ask_for_flasherhwver():
    """
        Ask for the flasher version, either 1 or 2 right now...
    """
    FLASHER_VERSION = 1
    flash_version = FLASHER_VERSION
    if FLASHER_VERSION is None:
        while True:
            try:
                flash_version = int(raw_input("--- Enter version of programmer hardware [Available Versions: Programmer V1 or Programmer V2]: ".format(FLASHVER=flash_version)))
            except:
                pass
            if flash_version == 1 or flash_version == 2:
                break
        print("<<< USER REPORTED HARDWARE FLASHER REVISION AS VERSION", flash_version, ">>>")
    return flash_version    
    
def ask_for_port():
    """\
    Show a list of ports and ask the user for a choice. To make selection
    easier on systems with long device names, also allow the input of an
    index.
    """
    global FLASHER_VERSION
    i = 0
    sys.stderr.write('\n--- Available ports:\n')
    port = None
    ports = []
    ports_info = {}
    skippedports = []

    for n, (port, desc, hwid) in enumerate(sorted(comports()), 1):
        includedport = "CP210"
        if includedport in desc:
            i+=1
            sys.stderr.write('--- {:2}: {:20} {!r}\n'.format(i, port, desc))
            ports.append(port)
            ports_info[port]={'port': port,'desc': desc,'hwid': hwid}
        else: 
            skippedports.append(port)
    while True:
        num_ports = len(ports)
        #if num_ports == 1:
        #    return ports[0]
        #else:
        port = raw_input('--- Enter port index or full name: ')
        try:
            index = int(port) - 1
            if not 0 <= index < len(ports):
                sys.stderr.write('--- Invalid index!\n')
                continue
        except ValueError:
            all_ports = skippedports + list(ports_info.keys())
            cleaned_value = str(port).strip().strip(" ")
            in_valid_list = (cleaned_value in ports_info.keys())
            if cleaned_value in all_ports:
                # we found a port
                if not in_valid_list:
                    print(f"!! Warning: Manually selecting port {port}, but unable to verify it is a CP210x device")
                break
            else:
                if len(ports)==1:
                    print("<<< ONLY ONE PROGRAMMER FOUND, SELECTING PROGRAMMER 1 >>>")
                    port = ports[0]
                    break
                else:
                    print("Invalid option. You must enter an index or full path to the device")
                    pass
        else:
            port = ports[index]
            break
    FLASHER_VERSION = 1 # update back to 1
    if FLASHER_VERSION_DETECT:       
        try:      
            sercheck = serial.Serial(port=port,dsrdtr=True)
            sercheck.dtr=0
            # we do 3 checks
            final_check = True
            if sercheck.dsr == sercheck.dtr and sercheck.dsr == 0:
                # we will set it to true
                for check in [True,False,True]:
                    sercheck.dtr=int(check)
                    curr_check = False
                    if sercheck.dtr == int(check) and sercheck.dsr == sercheck.dtr:
                        curr_check = True
                    final_check = final_check & curr_check
            sercheck.close()
            if final_check:
                print("Found programmer version: 2")
                print("This programmer will not require reconnection, please utilize the visual indicators on the programmer to ensure omg device is properly connected.")
                FLASHER_VERSION = 2
            else:
                print("Found programmer version: 1")
                #print("You will need to reconnect this when doing operations.")
        except KeyError:
            print("Defaulting to programmer version: 1")
    # finish
    return port

def omg_flash(command,tries=2):
    global FLASHER_VERSION
    ver = FLASHER_VERSION
    if int(ver) == 2 and FLASHER_VERSION_DETECT:
        try:
            flashapi.main(command)
            return True
        except (flashapi.FatalError, serial.SerialException, serial.serialutil.SerialException) as e:
            print("Error", str(e))
            return False
    else:
        ret = False
        while tries>0:
            try:
                ret = flashapi.main(command)
                print("<<< OPERATION SUCCESSFUL. PLEASE UNPLUG AND REPLUG DEVICE BEFORE CONTINUING >>>")
                input("")
                ret = True
                break
            except (flashapi.FatalError, serial.SerialException, serial.serialutil.SerialException) as e:
                tries-=1
                print("Unsuccessful communication,", tries, "trie(s) remain")
        if not ret:
            print("<<< ERROR DURING OPERATION PREVENTED SUCCESSFUL FLASH. TRY TO RECONNECT DEVICE OR REBOOT >>>")
            complete(1)
        else:
            return ret

def complete(statuscode, message="Press Enter to continue..."):
    input(message)
    sys.exit(statuscode)

def make_request(url):
    urlparse = urllib.parse.urlparse(url)
    url_parts = None
    if ":" in str(urlparse.netloc):
        url_parts = str(urlparse.netloc).split(":")
    else:
        port = 443
        if urlparse.scheme != "https":
            port = 80
        url_parts = (urlparse.netloc, port)
    if urlparse.scheme == "https":
        conn = http.client.HTTPSConnection(host=url_parts[0], port=url_parts[1])
    else:
        conn = http.client.HTTPConnection(host=url_parts[0], port=url_parts[1])
    return conn

def get_resource_file(url,params=None,data_type='text'):
    dta = "text/plain"
    if data_type == "json":
        dta = "application/json"
    pyver = sys.version_info
    uas = "httplib ({0}) python/{1}.{2}.{3}-{4}".format(sys.platform,pyver.major,pyver.minor,pyver.micro,pyver.serial)
    headers = {
        "Content-type": "application/x-www-form-urlencoded",
        "Accept": dta,
        "User-Agent": uas
    }
    status = None
    try:
        conn = make_request(url)
        conn.request("GET", url, params, headers)
        response = conn.getresponse()
        status = int(response.status)
        data = response.read()
    except ConnectionError:
        data = None
        status = 500
    return {'data': data, 'status': status}

def get_release_data():
    global BRANCH
    release_url = "https://api.github.com/repos/O-MG/O.MG-Firmware/releases?per_page=100"
    release_data = get_resource_file(url=release_url,data_type='json')
    if release_data['status'] == 200:
        raw_releases = json.loads(release_data['data'])
        releases = {}
        release_list = []
        for element in raw_releases:
            if "target_commitish" in element and element["target_commitish"] not in releases:
                # add
                if not element["draft"] :
                    releases[element["target_commitish"]] = element
                    releases[element["target_commitish"]]["version"] = element["tag_name"]
                    releases[element["target_commitish"]]["author"] = element["author"]["login"]
                    #del element["target_commitish"]["author"]
                    release_list.append(releases[element["target_commitish"]])
        if BRANCH in releases:
            return releases[BRANCH]["tag_name"]
        else:
            return None
        
def omg_fetch_latest_firmware(create_dst_dir=False,dst_dir="./firmware"):
    curr_branch = BRANCH
    try:
      curr_branch = get_release_data()
    except OSError:
      pass
    mem_map = get_resource_file(MEMMAP_URL)
    data = None
    if mem_map is not None and 'status' in mem_map and mem_map['status'] == 200:
        # attempt to create dir
        if not dst_dir=="./" or create_dst_dir:
            if os.path.exists(dst_dir):
                for f in os.listdir(dst_dir):
                    os.remove(dst_dir + "/" + f)
                os.rmdir(dst_dir)
            os.mkdir(dst_dir)
        json_map = json.loads(mem_map['data'])
        data = json_map
        pymap = {}
        dl_files = []
        for flash_size,files in json_map.items():
            mem_size = int(int(flash_size)/1024)
            file_map = []
            for resource in files:
                file_map.append(resource['offset'])
                file_map.append(resource['name'])
                if resource['name'] not in dl_files:
                    dl_files.append(resource['name'])
            pymap[mem_size]=file_map
        #pprint(pymap)
        #pprint(dl_files)
        print(f"\n\n<<<< WARNING: Firmware was not found in {dst_dir}! Resetting and attempting to download {curr_branch} firmware from the internet. >>>> \n\n")
        for dl_file in dl_files:
            dl_url = ("%s/firmware/%s"%(FIRMWARE_URL,dl_file)).replace("%BRANCH%",curr_branch)
            n = get_resource_file(dl_url)    
            if n is not None and 'data' in n and n['status']==200:
                dl_file_path = "%s/%s"%(dst_dir,dl_file)
                with open(dl_file_path,'wb') as f:
                    print("writing %d bytes of data to file %s from %s"%(len(n['data']),dl_file_path,dl_url))
                    f.write(n['data'])
    return data

def omg_locate():
    def omg_check(fw_path):
        PAGE_LOCATED = False
        INIT_LOCATED = False
        ELF0_LOCATED = False
        ELF1_LOCATED = False
        ELF2_LOCATED = False

        if os.path.isfile(results.FILE_PAGE):
            PAGE_LOCATED = True
        else:
            if os.path.isfile(fw_path + results.FILE_PAGE):
                results.FILE_PAGE = fw_path + results.FILE_PAGE
                PAGE_LOCATED = True

        if os.path.isfile(results.FILE_INIT):
            INIT_LOCATED = True
        else:
            if os.path.isfile(fw_path + results.FILE_INIT):
                results.FILE_INIT = fw_path + results.FILE_INIT
                INIT_LOCATED = True

        if os.path.isfile(results.FILE_ELF0):
            ELF0_LOCATED = True
        else:
            if os.path.isfile(fw_path + results.FILE_ELF0):
                results.FILE_ELF0 = fw_path + results.FILE_ELF0
                ELF0_LOCATED = True

        if os.path.isfile(results.FILE_ELF1):
            ELF1_LOCATED = True
        else:
            if os.path.isfile(fw_path + results.FILE_ELF1):
                results.FILE_ELF1 = fw_path + results.FILE_ELF1
                ELF1_LOCATED = True

        if os.path.isfile(results.FILE_BLANK):
            ELF2_LOCATED = True
        else:
            if os.path.isfile(fw_path + results.FILE_BLANK):
                results.FILE_BLANK = fw_path + results.FILE_BLANK
                ELF2_LOCATED = True
                
        if os.path.isfile(fw_path + results.FILE_OFAT_INIT):
            try:
                os.unlink(fw_path + results.FILE_OFAT_INIT)
            except:
                pass
        results.FILE_OFAT_INIT = fw_path + results.FILE_OFAT_INIT
        # return data
        return (PAGE_LOCATED,INIT_LOCATED,ELF0_LOCATED,ELF1_LOCATED,ELF2_LOCATED)

    # do lookups
    fw_path = FIRMWARE_DIR + "/"
    if not os.path.exists(fw_path):
        omg_fetch_latest_firmware(True,fw_path)
    # try one
    PAGE_LOCATED,INIT_LOCATED,ELF0_LOCATED,ELF1_LOCATED,ELF2_LOCATED = omg_check(fw_path)
    
    if not (PAGE_LOCATED and INIT_LOCATED and ELF0_LOCATED and ELF1_LOCATED and ELF2_LOCATED):
        omg_fetch_latest_firmware(False,fw_path)
        PAGE_LOCATED,INIT_LOCATED,ELF0_LOCATED,ELF1_LOCATED,ELF2_LOCATED = omg_check(fw_path)
    
    # now see if things worked
    if PAGE_LOCATED and INIT_LOCATED and ELF0_LOCATED and ELF1_LOCATED and ELF2_LOCATED:
        print("\n<<< ALL FIRMWARE FILES LOCATED >>>\n")
    else:
        print("<<< SOME FIRMWARE FILES ARE MISSING, PLACE THEM IN THIS FILE'S DIRECTORY >>>")
        if not PAGE_LOCATED: print("\n\tMISSING FILE: {PAGE}".format(PAGE=results.FILE_PAGE))
        if not INIT_LOCATED: print("\tMISSING FILE: {INIT}".format(INIT=results.FILE_INIT))
        if not ELF0_LOCATED: print("\tMISSING FILE: {ELF0}".format(ELF0=results.FILE_ELF0))
        if not ELF1_LOCATED: print("\tMISSING FILE: {ELF1}".format(ELF1=results.FILE_ELF1))
        if not ELF2_LOCATED: print("\tMISSING FILE: {ELF2}".format(ELF2=results.FILE_BLANK))
        print('')
        complete(1)



def omg_probe():
    devices = ""
    results.PROG_FOUND = False

    detected_ports = ask_for_port()
    devices = detected_ports
    
    results.PORT_PATH = devices
    if len(devices) > 1:
        results.PROG_FOUND = True
    
    if results.PROG_FOUND:
        print("\n<<< O.MG-PROGRAMMER WAS FOUND ON {PORT} >>>".format(PORT=results.PORT_PATH))
    else:
        if results.OS_DETECTED == "DARWIN":
            print("<<< O.MG-DEVICE-PROGRAMMER WAS NOT FOUND IN DEVICES, YOU MAY NEED TO INSTALL THE DRIVERS FOR CP210X USB BRIDGE >>>\n")
            print("VISIT: [ https://www.silabs.com/products/development-tools/software/usb-to-uart-bridge-vcp-drivers ]\n")
        else:
            print("<<< O.MG-PROGRAMMER WAS NOT FOUND IN DEVICES >>>\n")
        complete(1)

def omg_reset_settings():
    FILE_INIT = results.FILE_OFAT_INIT
    try:
        with open(FILE_INIT,'wb') as f:
            fill = (4*1024)
            init_cmd = "\00"*abs(fill)
            f.write(bytes(init_cmd.encode("utf-8")))  
    except:
        print("Warning: Unable to reset " + FILE_INIT)


def omg_patch(_ssid, _pass, _mode, slotsize=4, percent=60):
    FILE_INIT = results.FILE_OFAT_INIT

    init_cmd = "INIT;"
    settings = {
        "wifimode": _mode,
        "wifissid": _ssid,
        "wifikey": _pass
    }
    for config,value in settings.items():
        init_cmd+="S:{KEY}{SEP}{VALUE};".format(SEP="=", KEY=config,VALUE=value)
    #  once booted we know more, this is a sane default for now
    # if we set this to %f we can actually erase and allocate at once
    if slotsize>0:
        init_cmd += "F:keylog=0;F:payload1=0;F:payload2=0;F:payload3=0;F:payload4=0;F:payload5=0;F:payload6=0;F:payload7=0;F:bootscript=4;F:hidxfile=16;"
        ns = floor(((360*4)*(percent*.01))/(slotsize*4))
        print(f"[If Applicable] Number of Slots: {ns} with size {slotsize*4}k each based on {percent}% for payload slots")
        results.NUMBER_SLOTS = ns
        for i in range(1,ns+1):
            init_cmd+="f{SEP}payload{COUNT}={SLOT};".format(SEP=":", COUNT=i, SLOT=int(slotsize))
        init_cmd += "f{SEP}keylog=100%F;".format(SEP=":")   
    init_cmd += "\0"
    try:
        with open(FILE_INIT,'wb') as f:
            length = len(init_cmd)
            fill = (4*1024)-length
            init_cmd += "\00"*abs(fill)
            f.write(bytes(init_cmd.encode("utf-8")))  
    except:
        print("\n<<< PATCH FAILURE, ABORTING >>>")
        complete(1)


def omg_input():
    WIFI_MODE = ''
    SANITIZED_SELECTION = False

    while not SANITIZED_SELECTION:

        try:
            notemsg = "Hitting enter without an option will default to AP Mode with SSID: %s Pass: %s"%(results.WIFI_SSID,results.WIFI_PASS)
            WIFI_MODE = input("\nSELECT WIFI MODE\n1: STATION - (Connect to existing network. 2.4GHz)\n2: ACCESS POINT - (Create SSID. IP: 192.168.4.1)\n[%s]\nWifi Configuration [Hit Enter to use Defaults]: "%notemsg)
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
                WIFI_SSID = input("\nENTER WIFI SSID (1-32 Characters): ")
                if len(WIFI_SSID) > 1 and len(WIFI_SSID) < 33:
                    SANITIZED_SELECTION = True
            except:
                pass

        results.WIFI_SSID = WIFI_SSID

        WIFI_PASS = ''
        SANITIZED_SELECTION = False

        while not SANITIZED_SELECTION:
            try:
                WIFI_PASS = input("\nENTER WIFI PASS (8-64 Characters): ")
                if len(WIFI_PASS) > 7 and len(WIFI_PASS) < 65:
                    SANITIZED_SELECTION = True
            except:
                pass

        results.WIFI_PASS = WIFI_PASS
        
    # enable to let user customize on plus an elite devices
    # beta feature
    PROMPT_FLASH_CUSTOMIZE = False 
    FLASH_CUSTOMIZE = 0
    FLASH_SIZE = 4
    FLASH_PAYLOAD_PERCENT = 60
    SANITIZED_SELECTION = False
    if PROMPT_FLASH_CUSTOMIZE:
        while not SANITIZED_SELECTION:
            try:
                CUST_INPUT = str(input("\nCUSTOMIZE PAYLOAD AND KEYLOG ALLOCATIONS?\n(Note: Only compatible with Plus and Elite O.MG Devices)\nBegin Customization? (Yes or No) [Default: No] ")).lower()
                if "yes" in CUST_INPUT or "no" in CUST_INPUT or '' in CUST_INPUT:
                    print("Using default")
                    SANITIZED_SELECTION = True
                if "yes" in CUST_INPUT:
                    FLASH_CUSTOMIZE=1
            except:
                pass

    if FLASH_CUSTOMIZE:
        SANITIZED_SELECTION = False
        while not SANITIZED_SELECTION:
            try:
                CUST_INPUT = int(input("\nPERCENTAGE OF FLASH ALLOCATED TO PAYLOAD: [Usually 40%] ").lower().replace("%",""))
                if CUST_INPUT>0 and CUST_INPUT<101:
                    SANITIZED_SELECTION=True
                    FLASH_PAYLOAD_PERCENT = CUST_INPUT
                elif '' in CUST_INPUT:
                    SANITIZED_SELECTION=True
                    print("Using default")
            except:
                pass
    
        SANITIZED_SELECTION=False
        while not SANITIZED_SELECTION:
            try:
                CUST_INPUT = int(str(input("\nENTER PAYLOAD SLOT SIZE [Divisible By 4 between  4K and Max 32K]: ")).lower().replace("%","").replace("k",""))
                if (CUST_INPUT%4)==0:
                    FLASH_SIZE=(CUST_INPUT)/4
                    SANITIZED_SELECTION=True
                    if(CUST_INPUT>(360*4)):
                       print(f"{CUST_INPUT} is greater then the max size available.")
                    break
                else:
                    print(f"\n{CUST_INPUT} is not divisible by 4, try again. Note: Default is 4k")
            except:
                pass
        results.FLASH_SLOTS = FLASH_SIZE
        results.FLASH_PAYLOAD_SIZE = FLASH_PAYLOAD_PERCENT
        

def omg_flashfw(mac=None,flash_size=None):
    if not mac and not flash_size:
        mac, flash_size = get_dev_info(results.PORT_PATH)
    # attempt to continue
    try:
        FILE_PAGE = results.FILE_PAGE
        FILE_INIT = results.FILE_INIT
        FILE_ELF0 = results.FILE_ELF0
        FILE_ELF1 = results.FILE_ELF1
        FILE_OFAT_INIT = results.FILE_OFAT_INIT

        if flash_size < 0x200000:
            command = ['--baud', baudrate, '--port', results.PORT_PATH, 'write_flash', '-fs', '1MB', '-fm', 'dout', '0xfc000', FILE_INIT, '0x00000', FILE_ELF0, '0x10000', FILE_ELF1, '0x80000', FILE_PAGE, '0x7f000', FILE_OFAT_INIT]
        else:
            command = ['--baud', baudrate, '--port', results.PORT_PATH, 'write_flash', '-fs', '2MB', '-fm', 'dout', '0x1fc000', FILE_INIT, '0x00000', FILE_ELF0, '0x10000', FILE_ELF1, '0x80000', FILE_PAGE, '0x7f000', FILE_OFAT_INIT]
        print("\n\n")
        omg_flash(command)

    except:
        print("\n<<< SOMETHING FAILED WHILE FLASHING >>>")
        complete(1)

def omg_runflash(pre_erase=False,skip_flash=False,skip_input=False,skip_reset=False):
    # get info
    mac, flash_size = get_dev_info(results.PORT_PATH)
    if (pre_erase and skip_flash) or FLASHER_VERSION>=2:
        if skip_flash:
            print("Attempting to factory reset (erase) device...")
        else:
            print("Attempting to clear device before flashing...")
        if flash_size < 0x200000:
            command = ['--baud', baudrate, '--port', results.PORT_PATH, 'erase_region', '0x70000', '0x8A000']
        else:
            command = ['--baud', baudrate, '--port', results.PORT_PATH, 'erase_region', '0x70000', '0x18A000']
        omg_flash(command)
    if not skip_flash:
        if not skip_input:
            omg_input()
        omg_patch(results.WIFI_SSID, results.WIFI_PASS, results.WIFI_MODE, results.FLASH_SLOTS, results.FLASH_PAYLOAD_SIZE)
        omg_flashfw(mac,flash_size)
        print("\n[ WIFI SETTINGS ]")
        print("\n    WIFI_SSID: {SSID}\n    WIFI_PASS: {PASS}\n    WIFI_MODE: {MODE}\n    WIFI_TYPE: {TYPE}".format(SSID=results.WIFI_SSID, PASS=results.WIFI_PASS, MODE=results.WIFI_MODE, TYPE=results.WIFI_TYPE))
        print("\n[ FIRMWARE USED ]")
        print("\n    INIT: {INIT}\n    ELF0: {ELF0}\n    ELF1: {ELF1}\n    PAGE: {PAGE}".format(INIT=results.FILE_INIT, ELF0=results.FILE_ELF0, ELF1=results.FILE_ELF1, PAGE=results.FILE_PAGE))
        if results.FLASH_SLOTS > 0:
            print("\n[ CUSTOM PAYLOAD CONFIGURATION ]")
            pp=results.FLASH_PAYLOAD_SIZE
            kp=abs(100-results.FLASH_PAYLOAD_SIZE)
            ns=int(results.FLASH_SLOTS*4)
            np=results.NUMBER_SLOTS
            print(f"\n    PERCENT FLASH PAYLOAD SPACE: {pp}\n    PERCENT FLASH KEYLOG SPACE: {kp} (Where Applicable)\n    NUMBER OF PAYLOADS: {np}\n    SIZE OF PAYLOAD SLOTS: {ns}k\n    ")
    # attempt to always erase settings
    if not skip_reset:
        omg_reset_settings()
    
def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))


if __name__ == '__main__':
    signal(SIGINT, handler)
    print("\n" + VERSION)
    print("\n" + UPDATES)
    print("\n" + MOTD + "\n")

    results = omg_results()
    baudrate = '115200'

    thedirectory = get_script_path()
    os.chdir(thedirectory)

    omg_tos()

    omg_dependency_imports()

    results.OS_DETECTED = platform.system().upper()

    omg_locate()
    
    omg_reset_settings()

    omg_probe()
    
    if FLASHER_VERSION_DETECT:
        FLASHER_VERSION = ask_for_flasherhwver()
    MENU_MODE = ''
    SANITIZED_SELECTION = False

    while not SANITIZED_SELECTION:
        try:
            menu_options = [
                'FLASH NEW FIRMWARE',
                'FACTORY RESET',
                'FIRMWARE UPGRADE - BATCH MODE',
                'FACTORY RESET - BATCH MODE',
                'BACKUP DEVICE',
                'DOWNLOAD FIRMWARE UPDATES',
                'EXIT FLASHER',
            ]
            print("Available Options \n")
            i = 1
            for menu_option in menu_options:
                 print(i," ",menu_option,end="")
                 if i == 1:
                     print(" (DEFAULT)")
                 else:
                     print("")
                 i+=1    
            menu_options = [''] 
            MENU_MODE = str(input("Select Option: ")).replace(" ","")
            if MENU_MODE == '1' or MENU_MODE == '2' or MENU_MODE == '3' or MENU_MODE == '4' or MENU_MODE == '5' or MENU_MODE == '6' or  MENU_MODE == '7' or  MENU_MODE == '8':
                SANITIZED_SELECTION = True
        except:
            pass
    # handle python serial exceptions here        
    try:
        if MENU_MODE == '1':
            print("\nFIRMWARE UPGRADE")
            omg_runflash()
            print("\n<<< FIRMWARE PROCESS FINISHED, REMOVE DEVICE >>>\n")
        elif MENU_MODE == '2':
            print("\nFACTORY RESET")
            omg_runflash(True,True)
        elif MENU_MODE == '3':
            baudrate = '460800'
            
            print("\nFIRMWARE UPGRADE - BATCH MODE")
            omg_input()
            repeating = ''
            while repeating != 'e':
                omg_runflash(True,skip_input=True,skip_reset=True)
                repeating = input("\n\n<<< PRESS ENTER TO UPGRADE NEXT DEVICE, OR 'E' TO EXIT >>>\n")
            omg_reset_settings()
            complete(0)
        elif MENU_MODE == '4':
            baudrate = '460800'
            print("\nFACTORY RESET - BATCH MODE")
            omg_input()
            repeating = ''
            while repeating != 'e':
                omg_runflash(True,True,skip_input=True,skip_reset=True)
                repeating = input("\n\n<<< PRESS ENTER TO RESTORE NEXT DEVICE, OR 'E' TO EXIT >>>\n")
        elif MENU_MODE == '5':
            print("\nBACKUP DEVICE")
            mac, flash_size = get_dev_info(results.PORT_PATH)
            filename = "backup-{MACLOW}-{TIMESTAMP}.img".format(MACLOW="".join([hex(m).lstrip("0x") for m in mac]).lower(),TIMESTAMP=int(time()))
            if flash_size < 0x200000:
                command = ['--baud', baudrate, '--port', results.PORT_PATH, 'read_flash', '0x00000', '0x100000', filename]
            else:
                command = ['--baud', baudrate, '--port', results.PORT_PATH, 'read_flash', '0x00000', '0x200000', filename]
            omg_flash(command)
            print('Backup written to ', filename)
        elif MENU_MODE == '6':
            print("Attempting to update flash data...")
            d = omg_fetch_latest_firmware(True,FIRMWARE_DIR)
            if d is not None and len(d) > 1:
                print("\n<<< LOAD SUCCESS. RELOADING DATA >>>\n\n")
            else:
                print("\n<<< LOAD FAILED. PLEASE MANUALLY DOWNLOAD FIRMWARE AND PLACE IN '%s' >>>\n\n"%FIRMWARE_DIR)
                complete(0)
        elif MENU_MODE == '7':
            print("<<< GOODBYE. FLASHER EXITING >>> ")
            sys.exit(0)
        else:
            print("<<< NO VALID INPUT WAS DETECTED. >>>")
    except (flashapi.FatalError, serial.SerialException, serial.serialutil.SerialException) as e:
        print("<<< FATAL ERROR: %s. PLEASE DISCONNECT AND RECONNECT DEVICE AND START TASK AGAIN >>>"%str(e))
        sys.exit(1) # special case
    complete(0)
