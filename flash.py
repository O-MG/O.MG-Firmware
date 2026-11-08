# Copyright 2023 Mischief Gadgets LLC

import os
import sys
import glob
import base64
import hashlib
import json
import platform
import argparse
import mimetypes
import string
import re
import zlib
from sys import exit
from time import time
from math import floor
from signal import signal, SIGINT

serial = None
comports = None

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

VERSION = "FIRMWARE FLASHER VERSION [ 2.0.0 ]"
FLASHER_VERSION = 1 # presume we have an old style flasher = 1
FLASHER_VERSION_DETECT = True
AUTO_MODE = False
CLI_WIFI_CONFIGURED = False

SECTOR_SIZE = 4 * 1024
APPLICATION_CAPACITY = 0x64000
WEBUI_CAPACITY = 0x40000
FLASHLOG_ADDRESS = 0x74000
DATA_RESET_END_1MB = 0xFA000
DATA_RESET_END_2MB = 0x1FA000
FIRMWARE_MANIFEST_FORMAT = "omg-websocket-update-v2"
WIFI_REFLASH_MAGIC = b"WIFI"  # WIFI_REFLASH_CODE (0x49464957), little-endian on flash
WIFI_MODE_NAMES = {
    "1": ("1", "STATION"),
    "station": ("1", "STATION"),
    "sta": ("1", "STATION"),
    "2": ("2", "ACCESS POINT"),
    "ap": ("2", "ACCESS POINT"),
    "accesspoint": ("2", "ACCESS POINT"),
    "access-point": ("2", "ACCESS POINT"),
    "softap": ("2", "ACCESS POINT"),
}

FIRMWARE_DIR="./firmware"
UPDATES = "LOCAL-ONLY FLASHER. MANUALLY DOWNLOAD UPDATES FROM: [ https://github.com/O-MG/O.MG-Firmware ]\n"

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
        global serial, comports
        import serial
        from serial.tools.list_ports import comports
    except:
        print("\n<<< PYSERIAL MODULE MISSING, MANUALLY INSTALL TO CONTINUE >>>")
        print("<<< YOU CAN TRY: npm install serial or pip install pyserial >>>")
        complete(1)

    try:
        from scripts import flashapi as flashtest
    except:
        print("\n<<< REQUIRED LOCAL DEPENDENCIES ARE MISSING FROM ./scripts >>>")
        print("<<< RESTORE scripts/flashapi.py AND scripts/miniterm.py FROM A LOCAL COPY OF THE FIRMWARE PACKAGE >>>")
    try:
        global flashapi
        from scripts import flashapi as flashapi
    except:
        print("<<< flashapi.PY MISSING FROM scripts/flashapi.py >>>")
        print("<<< RESTORE IT FROM A LOCAL COPY OF THE O.MG FIRMWARE PACKAGE >>>")
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
        self.WIFI_TYPE = "ACCESS POINT"
        self.FILE_PAGE = "page.mpfs"
        self.FILE_INIT = "esp_init_data_default_v08.bin"
        self.FILE_ELF0 = "image.elf-0x00000.bin"
        self.FILE_ELF1 = "image.elf-0x10000.bin"
        self.FILE_MANIFEST = "firmware-update.json"
        self.FILE_BLANK = "blank.bin"
        self.FILE_OFAT_TEMPLATE = "blank-settings.bin"
        self.FILE_OFAT_INIT = "ofat-settings.bin"
        self.FILE_WIFI_INIT = "wifi-settings.bin"
        # Zero means use the firmware's capability-aware default OFAT layout.
        self.FLASH_SLOTS = 0
        self.FLASH_PAYLOAD_SIZE = 60
        self.NUMBER_SLOTS = 0
        self.FIRMWARE_MANIFEST = None


def normalize_wifi_mode(value):
    """Return the firmware numeric mode and a display label."""
    normalized = str(value).strip().lower().replace("_", "-").replace(" ", "")
    try:
        return WIFI_MODE_NAMES[normalized]
    except KeyError:
        raise ValueError("Wi-Fi mode must be station or ap")


def validate_wifi_credentials(ssid, password):
    """Validate the byte limits used by the firmware's 33/65-byte buffers."""
    if "\x00" in ssid or "\x00" in password:
        raise ValueError("Wi-Fi credentials cannot contain NUL bytes")
    ssid_len = len(ssid.encode("utf-8"))
    password_len = len(password.encode("utf-8"))
    if ssid_len < 1 or ssid_len > 32:
        raise ValueError("Wi-Fi SSID must be 1-32 UTF-8 bytes")
    is_64_hex_psk = password_len == 64 and all(char in string.hexdigits for char in password)
    if not (8 <= password_len <= 63 or is_64_hex_psk):
        raise ValueError("Wi-Fi password must be 8-63 UTF-8 bytes or a 64-digit hexadecimal PSK")


def validate_programmer_image(path, label, capacity, record=None):
    """Verify a package image against its manifest record and partition."""
    size = os.path.getsize(path)
    if size <= 0:
        raise ValueError("%s image is empty" % label)
    if size > capacity:
        raise ValueError(
            "%s image is %d bytes; its flash partition allows %d bytes"
            % (label, size, capacity)
        )
    if record is None:
        return
    if os.path.basename(path) != record.get("file"):
        raise ValueError("%s image filename does not match firmware-update.json" % label)
    if size != record.get("size"):
        raise ValueError("%s image size does not match firmware-update.json" % label)
    with open(path, "rb") as image_file:
        data = image_file.read()
    if hashlib.md5(data).hexdigest() != record.get("md5"):
        raise ValueError("%s image MD5 does not match firmware-update.json" % label)
    if hashlib.sha256(data).hexdigest() != record.get("sha256"):
        raise ValueError("%s image SHA-256 does not match firmware-update.json" % label)
    if "%08x" % (zlib.crc32(data) & 0xffffffff) != record.get("crc32"):
        raise ValueError("%s image CRC32 does not match firmware-update.json" % label)


def manifest_address(value, field):
    """Parse a legacy integer or a hexadecimal address from the manifest."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        if not isinstance(value, str) or not re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
            raise ValueError("firmware-update.json has invalid %s" % field)
        return int(value[2:], 16)
    return value


def format_flash_address(value, field):
    """Return a canonical hexadecimal address for esptool command arguments."""
    return "0x%05x" % manifest_address(value, field)


def manifest_record_needed(record, consumer, legacy_default):
    """Return whether a manifest record applies to a flashing consumer."""
    consumers = record.get("consumers")
    if consumers is None:
        return legacy_default
    if not isinstance(consumers, list) or any(
            not isinstance(item, str) or not item for item in consumers):
        raise ValueError("firmware-update.json has invalid consumers metadata")
    return consumer in consumers


def manifest_file_path(root, record, label):
    filename = record.get("file")
    if not isinstance(filename, str) or not filename or os.path.basename(filename) != filename:
        raise ValueError("firmware-update.json has an unsafe %s filename" % label)
    path = os.path.join(root, filename)
    if not os.path.isfile(path):
        raise ValueError("firmware-update.json requires missing file %s" % filename)
    return path


def load_firmware_manifest(path, image_paths=None, programmer_paths=None):
    """Load, integrity-check, and safety-check the Programmer flash layout."""
    with open(path, "r") as manifest_file:
        manifest = json.load(manifest_file)
    if manifest.get("format") != FIRMWARE_MANIFEST_FORMAT:
        raise ValueError("unsupported firmware-update.json format")
    if manifest.get("sector_size") != SECTOR_SIZE:
        raise ValueError("firmware-update.json has an unsupported sector size")

    images = manifest.get("images")
    programmer = manifest.get("programmer")
    if not isinstance(images, dict) or not isinstance(programmer, dict):
        raise ValueError("firmware-update.json is missing layout metadata")
    reset = programmer.get("data_reset")
    auxiliary = programmer.get("images")
    if not isinstance(reset, dict) or not isinstance(auxiliary, dict):
        raise ValueError("firmware-update.json is missing Programmer geometry")
    manifest_root = os.path.dirname(os.path.abspath(path))

    reset_start = manifest_address(reset.get("start"), "programmer.data_reset.start")
    reset_ends = reset.get("end_by_flash_mb")
    if not isinstance(reset_ends, dict) or reset_start != FLASHLOG_ADDRESS or {
        size: manifest_address(reset_ends.get(size), "programmer.data_reset.end_by_flash_mb.%s" % size)
        for size in ("1", "2")
    } != {"1": DATA_RESET_END_1MB, "2": DATA_RESET_END_2MB}:
        raise ValueError("firmware-update.json has an unsupported data-reset layout")

    safety_limits = {"boot": 0x10000, "application": APPLICATION_CAPACITY, "webui": WEBUI_CAPACITY}
    ranges = []
    if image_paths is None:
        image_paths = {}
    for role in ("boot", "application", "webui"):
        record = images.get(role)
        if not isinstance(record, dict):
            raise ValueError("firmware-update.json is missing %s" % role)
        if not manifest_record_needed(record, "python", True):
            raise ValueError("firmware-update.json does not provide %s for the Python flasher" % role)
        if role not in image_paths:
            image_paths[role] = manifest_file_path(manifest_root, record, role)
        target = manifest_address(record.get("target"), "images.%s.target" % role)
        manifest_address(record.get("stage"), "images.%s.stage" % role)
        capacity = record.get("capacity")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
            raise ValueError("firmware-update.json has invalid images.%s.capacity" % role)
        if target % SECTOR_SIZE or capacity <= 0 or capacity % SECTOR_SIZE:
            raise ValueError("firmware-update.json has unaligned %s geometry" % role)
        if capacity > safety_limits[role]:
            raise ValueError("firmware-update.json exceeds the safe %s capacity" % role)
        validate_programmer_image(image_paths[role], role, capacity, record)
        ranges.append((target, target + capacity, role))

    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if previous[1] > current[0]:
            raise ValueError("firmware-update.json image partitions overlap")
    boot_range = next(item for item in ranges if item[2] == "boot")
    app_range = next(item for item in ranges if item[2] == "application")
    web_range = next(item for item in ranges if item[2] == "webui")
    if boot_range[0] != 0 or app_range[0] < 0x10000 or app_range[1] > reset_start:
        raise ValueError("firmware-update.json has unsafe boot/application targets")
    if web_range[0] < 0x80000 or web_range[1] > 0xF0000:
        raise ValueError("firmware-update.json has an unsafe WebUI target")

    required_aux = {"phy_init", "wifi_reflash", "ofat_init"}
    if not required_aux.issubset(auxiliary) or any(
            not isinstance(auxiliary[role], dict) for role in required_aux):
        raise ValueError("firmware-update.json is missing Programmer image targets")
    phy_targets = auxiliary["phy_init"].get("target_by_flash_mb")
    if not isinstance(phy_targets, dict) or {
        size: manifest_address(phy_targets.get(size), "programmer.images.phy_init.target_by_flash_mb.%s" % size)
        for size in ("1", "2")
    } != {"1": 0xFC000, "2": 0x1FC000}:
        raise ValueError("firmware-update.json has unsafe PHY-init targets")
    if programmer_paths is None:
        programmer_paths = {}
    for role in ("phy_init", "wifi_reflash", "ofat_init"):
        record = auxiliary[role]
        capacity = record.get("capacity")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
            raise ValueError("firmware-update.json has invalid programmer.images.%s.capacity" % role)
        if capacity != SECTOR_SIZE:
            raise ValueError("firmware-update.json has an unsafe %s capacity" % role)
        if manifest_record_needed(record, "python", False):
            if role not in programmer_paths:
                programmer_paths[role] = manifest_file_path(manifest_root, record, role)
            validate_programmer_image(programmer_paths[role], role, capacity, record)
    for role in ("wifi_reflash", "ofat_init"):
        target = manifest_address(auxiliary[role].get("target"), "programmer.images.%s.target" % role)
        if target < reset_start or target + SECTOR_SIZE > web_range[0]:
            raise ValueError("firmware-update.json has an unsafe %s target" % role)
    return manifest


def data_reset_region(flash_size, manifest):
    """Return the manifest-declared data erase range within the protected boundaries."""
    flash_mb = "2" if flash_size >= 0x200000 else "1"
    reset = manifest["programmer"]["data_reset"]
    start = manifest_address(reset["start"], "programmer.data_reset.start")
    end = manifest_address(
        reset["end_by_flash_mb"][flash_mb],
        "programmer.data_reset.end_by_flash_mb.%s" % flash_mb,
    )
    return start, end - start


def build_wifi_config(mode, ssid, password):
    """Build JSON accepted by wificonfig.c's current parser."""
    numeric_mode, _ = normalize_wifi_mode(mode)
    validate_wifi_credentials(ssid, password)
    config = {"hostname": ssid}
    if numeric_mode == "1":
        config["station"] = {"ap_list": [{"ssid": ssid, "key": password}]}
    else:
        config["soft_ap"] = {"ssid": ssid, "key": password}
    return config


def build_wifi_reflash_image(mode, ssid, password):
    """Build the 4 KiB WIFI_REFLASH_SECTOR image consumed on first boot."""
    config = build_wifi_config(mode, ssid, password)
    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    image = WIFI_REFLASH_MAGIC + payload + b"\0"
    if len(image) > SECTOR_SIZE:
        raise ValueError("Wi-Fi configuration does not fit in the reflash sector")
    return image + (b"\xff" * (SECTOR_SIZE - len(image)))


def build_default_ofat_image():
    """Request the firmware's default_filelist layout without overrides."""
    script = b"INIT;\0"
    return script + (b"\0" * (SECTOR_SIZE - len(script)))


def build_argument_parser():
    parser = argparse.ArgumentParser(description="Flash O.MG firmware")
    parser.add_argument(
        "--auto", action="store_true",
        help="flash firmware immediately, selecting the only connected CP210x programmer",
    )
    parser.add_argument("--port", help="serial programmer path (required in auto mode when multiple are connected)")
    parser.add_argument("--wifimode", "--wifi-mode", dest="wifi_mode", help="station or ap")
    parser.add_argument("--wifissid", "--wifi-ssid", dest="wifi_ssid", help="1-32 byte Wi-Fi SSID")
    parser.add_argument("--wifipasswd", "--wifi-password", dest="wifi_password", help="Wi-Fi password")
    parser.add_argument(
        "--accept-tos", action="store_true",
        help="confirm that you have read and accept the displayed O.MG terms (required for unattended use)",
    )
    return parser


def parse_cli_args(argv=None):
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    supplied = [args.wifi_mode is not None, args.wifi_ssid is not None, args.wifi_password is not None]
    if any(supplied) and not all(supplied):
        parser.error("--wifimode, --wifissid, and --wifipasswd must be supplied together")
    if all(supplied):
        try:
            args.wifi_mode, args.wifi_type = normalize_wifi_mode(args.wifi_mode)
            validate_wifi_credentials(args.wifi_ssid, args.wifi_password)
        except ValueError as error:
            parser.error(str(error))
    else:
        args.wifi_type = None
    return args


def select_baudrate(auto):
    return '460800' if auto else '115200'


def mdns_webui_url(hostname):
    if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", hostname):
        return "http://%s.local/" % hostname
    return None


def get_dev_info(dev):
    # The ROM always starts at 115200. flashapi.main() connects there first and
    # then switches to the requested flashing baud after uploading its stub.
    esp = flashapi.ESP8266ROM(dev, min(int(baudrate), 115200), None)
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
    global FLASHER_VERSION
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

def ask_for_port(auto=False, requested_port=None):
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

    all_ports = []
    for n, (detected_port, desc, hwid) in enumerate(sorted(comports()), 1):
        all_ports.append(detected_port)
        includedport = "CP210"
        if includedport in desc:
            i+=1
            sys.stderr.write('--- {:2}: {:20} {!r}\n'.format(i, detected_port, desc))
            ports.append(detected_port)
            ports_info[detected_port]={'port': detected_port,'desc': desc,'hwid': hwid}
        else:
            skippedports.append(detected_port)

    if requested_port:
        if requested_port not in all_ports:
            print("<<< REQUESTED PROGRAMMER PORT WAS NOT FOUND: %s >>>" % requested_port)
            complete(1)
        if requested_port not in ports:
            print("!! Warning: unable to verify that %s is a CP210x programmer" % requested_port)
        port = requested_port
    elif auto:
        if len(ports) == 1:
            port = ports[0]
            print("<<< AUTO-SELECTED PROGRAMMER: %s >>>" % port)
        elif len(ports) == 0:
            print("<<< AUTO MODE FOUND NO CP210x PROGRAMMER >>>")
            complete(1)
        else:
            print("<<< AUTO MODE FOUND MULTIPLE CP210x PROGRAMMERS; USE --port >>>")
            complete(1)

    while not port:
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
            final_check = False
            if sercheck.dsr == sercheck.dtr and sercheck.dsr == 0:
                final_check = True
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
                if not AUTO_MODE:
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
    if not AUTO_MODE:
        input(message)
    sys.exit(statuscode)

def omg_locate():
    fw_path = os.path.abspath(FIRMWARE_DIR)
    manifest_path = os.path.join(fw_path, results.FILE_MANIFEST)
    try:
        results.FIRMWARE_MANIFEST = load_firmware_manifest(manifest_path)
        images = results.FIRMWARE_MANIFEST["images"]
        programmer_images = results.FIRMWARE_MANIFEST["programmer"]["images"]
        results.FILE_MANIFEST = manifest_path
        results.FILE_ELF0 = manifest_file_path(fw_path, images["boot"], "boot")
        results.FILE_ELF1 = manifest_file_path(fw_path, images["application"], "application")
        results.FILE_PAGE = manifest_file_path(fw_path, images["webui"], "webui")
        results.FILE_INIT = manifest_file_path(fw_path, programmer_images["phy_init"], "phy_init")

        # New manifests explicitly identify the two packaged templates needed by
        # Python/WebFlasher. Legacy manifests described generated filenames, so
        # retain their canonical package filenames as a compatibility fallback.
        if manifest_record_needed(programmer_images["wifi_reflash"], "python", False):
            results.FILE_BLANK = manifest_file_path(
                fw_path, programmer_images["wifi_reflash"], "wifi_reflash")
        else:
            results.FILE_BLANK = os.path.join(fw_path, "blank.bin")
        if manifest_record_needed(programmer_images["ofat_init"], "python", False):
            results.FILE_OFAT_TEMPLATE = manifest_file_path(
                fw_path, programmer_images["ofat_init"], "ofat_init")
        else:
            results.FILE_OFAT_TEMPLATE = os.path.join(fw_path, "blank-settings.bin")
        if not os.path.isfile(results.FILE_BLANK) or not os.path.isfile(results.FILE_OFAT_TEMPLATE):
            raise ValueError("firmware package is missing Python flasher templates")

        results.FILE_OFAT_INIT = os.path.join(fw_path, "ofat-settings.bin")
        results.FILE_WIFI_INIT = os.path.join(fw_path, "wifi-settings.bin")
    except (OSError, ValueError) as error:
        print("<<< FIRMWARE MANIFEST VALIDATION FAILED: %s >>>" % error)
        complete(1)
    print("\n<<< ALL PYTHON FLASHER FILES AND MANIFEST RECORDS VALIDATED >>>\n")



def omg_probe(auto=False, requested_port=None):
    devices = ""
    results.PROG_FOUND = False

    detected_ports = ask_for_port(auto=auto, requested_port=requested_port)
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
    for generated_file in (results.FILE_OFAT_INIT, results.FILE_WIFI_INIT):
        try:
            with open(generated_file, 'wb') as output:
                output.write(b"\0" * SECTOR_SIZE)
        except OSError:
            print("Warning: Unable to reset " + generated_file)


def omg_patch(slotsize=0, percent=60):
    FILE_INIT = results.FILE_OFAT_INIT

    if slotsize <= 0:
        try:
            with open(FILE_INIT, 'wb') as output:
                output.write(build_default_ofat_image())
            return
        except OSError:
            print("\n<<< PATCH FAILURE, ABORTING >>>")
            complete(1)

    init_cmd = "INIT;"
    # A zero slot size intentionally leaves the capability-aware defaults from
    # firmware/user/fs/ofatdefaults.h unchanged.
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
            encoded = init_cmd.encode("utf-8")
            if len(encoded) > SECTOR_SIZE:
                raise ValueError("OFAT init script exceeds one flash sector")
            f.write(encoded + (b"\0" * (SECTOR_SIZE - len(encoded))))
    except (OSError, ValueError):
        print("\n<<< PATCH FAILURE, ABORTING >>>")
        complete(1)


def omg_patch_wifi(ssid, password, mode):
    try:
        image = build_wifi_reflash_image(mode, ssid, password)
        with open(results.FILE_WIFI_INIT, "wb") as output:
            output.write(image)
    except (OSError, ValueError) as error:
        print("\n<<< WIFI PATCH FAILURE: %s >>>" % error)
        complete(1)


def omg_input():
    if CLI_WIFI_CONFIGURED:
        return
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
                WIFI_SSID = input("\nENTER WIFI SSID (1-32 UTF-8 Bytes): ")
                if 1 <= len(WIFI_SSID.encode("utf-8")) <= 32:
                    SANITIZED_SELECTION = True
            except:
                pass

        results.WIFI_SSID = WIFI_SSID

        WIFI_PASS = ''
        SANITIZED_SELECTION = False

        while not SANITIZED_SELECTION:
            try:
                WIFI_PASS = input("\nENTER WIFI PASS (8-63 UTF-8 Bytes or 64 Hex Digits): ")
                try:
                    validate_wifi_credentials(WIFI_SSID, WIFI_PASS)
                    SANITIZED_SELECTION = True
                except ValueError:
                    pass
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
        FILE_WIFI_INIT = results.FILE_WIFI_INIT
        manifest = results.FIRMWARE_MANIFEST
        if not isinstance(manifest, dict):
            raise ValueError("firmware-update.json has not been loaded")
        images = manifest["images"]
        programmer_images = manifest["programmer"]["images"]
        flash_mb = "2" if flash_size >= 0x200000 else "1"

        validate_programmer_image(FILE_ELF0, "boot", images["boot"]["capacity"], images["boot"])
        validate_programmer_image(FILE_ELF1, "application", images["application"]["capacity"], images["application"])
        validate_programmer_image(FILE_PAGE, "WebUI", images["webui"]["capacity"], images["webui"])
        validate_programmer_image(
            FILE_INIT, "PHY init", programmer_images["phy_init"]["capacity"],
            programmer_images["phy_init"] if manifest_record_needed(
                programmer_images["phy_init"], "python", False) else None,
        )
        # These two images are generated from the packaged blank templates after
        # their release checksums have been verified. Their runtime contents are
        # intentionally different from the immutable manifest records.
        validate_programmer_image(FILE_WIFI_INIT, "WiFi reflash", programmer_images["wifi_reflash"]["capacity"])
        validate_programmer_image(FILE_OFAT_INIT, "OFAT init", programmer_images["ofat_init"]["capacity"])

        command = [
            '--baud', baudrate, '--port', results.PORT_PATH, 'write_flash',
            '-fs', flash_mb + 'MB', '-fm', 'dout',
            format_flash_address(
                programmer_images["phy_init"]["target_by_flash_mb"][flash_mb],
                "programmer.images.phy_init.target_by_flash_mb.%s" % flash_mb,
            ), FILE_INIT,
            format_flash_address(images["boot"]["target"], "images.boot.target"), FILE_ELF0,
            format_flash_address(images["application"]["target"], "images.application.target"), FILE_ELF1,
            format_flash_address(
                programmer_images["wifi_reflash"]["target"],
                "programmer.images.wifi_reflash.target",
            ), FILE_WIFI_INIT,
            format_flash_address(
                programmer_images["ofat_init"]["target"],
                "programmer.images.ofat_init.target",
            ), FILE_OFAT_INIT,
            format_flash_address(images["webui"]["target"], "images.webui.target"), FILE_PAGE,
        ]
        print("\n\n")
        omg_flash(command)

    except Exception as error:
        print("\n<<< SOMETHING FAILED WHILE FLASHING: %s >>>" % error)
        complete(1)

def omg_runflash(pre_erase=False,skip_flash=False,skip_input=False,skip_reset=False):
    # get info
    mac, flash_size = get_dev_info(results.PORT_PATH)
    if (pre_erase and skip_flash) or FLASHER_VERSION>=2:
        if skip_flash:
            print("Attempting to factory reset (erase) device...")
        else:
            print("Attempting to clear device before flashing...")
        if not isinstance(results.FIRMWARE_MANIFEST, dict):
            raise ValueError("firmware-update.json has not been loaded")
        reset_address, reset_size = data_reset_region(flash_size, results.FIRMWARE_MANIFEST)
        command = [
            '--baud', baudrate, '--port', results.PORT_PATH, 'erase_region',
            '0x%x' % reset_address, '0x%x' % reset_size,
        ]
        omg_flash(command)
    if not skip_flash:
        if not skip_input:
            omg_input()
        try:
            omg_patch(results.FLASH_SLOTS, results.FLASH_PAYLOAD_SIZE)
            omg_patch_wifi(results.WIFI_SSID, results.WIFI_PASS, results.WIFI_MODE)
            omg_flashfw(mac,flash_size)
        finally:
            # Generated sectors contain credentials; clear them even if the
            # serial flash operation fails or is interrupted.
            if not skip_reset:
                omg_reset_settings()
        print("\n[ WIFI SETTINGS ]")
        print("\n    WIFI_SSID: {SSID}\n    WIFI_PASS: <configured>\n    WIFI_MODE: {MODE}\n    WIFI_TYPE: {TYPE}".format(SSID=results.WIFI_SSID, MODE=results.WIFI_MODE, TYPE=results.WIFI_TYPE))
        mdns_url = mdns_webui_url(results.WIFI_SSID)
        if mdns_url:
            print("\n    WEBUI: %s" % mdns_url)
        print("    The station IP is assigned by DHCP; confirm the lease instead of assuming a subnet.")
        print("\n[ FIRMWARE USED ]")
        print("\n    INIT: {INIT}\n    ELF0: {ELF0}\n    ELF1: {ELF1}\n    PAGE: {PAGE}".format(INIT=results.FILE_INIT, ELF0=results.FILE_ELF0, ELF1=results.FILE_ELF1, PAGE=results.FILE_PAGE))
        if results.FLASH_SLOTS > 0:
            print("\n[ CUSTOM PAYLOAD CONFIGURATION ]")
            pp=results.FLASH_PAYLOAD_SIZE
            kp=abs(100-results.FLASH_PAYLOAD_SIZE)
            ns=int(results.FLASH_SLOTS*4)
            np=results.NUMBER_SLOTS
            print(f"\n    PERCENT FLASH PAYLOAD SPACE: {pp}\n    PERCENT FLASH KEYLOG SPACE: {kp} (Where Applicable)\n    NUMBER OF PAYLOADS: {np}\n    SIZE OF PAYLOAD SLOTS: {ns}k\n    ")
        else:
            print("\n[ OFAT LAYOUT ]\n\n    FIRMWARE DEFAULT (capability-aware)\n")
        if AUTO_MODE:
            print("\n[ NEXT STEP ]")
            print("\n    Disconnect the O.MG Cable from the programmer and connect it directly")
            print("    to a normal USB port before waiting for DHCP or opening the WebUI.\n")
    # attempt to always erase settings
    if skip_flash and not skip_reset:
        omg_reset_settings()

def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))


if __name__ == '__main__':
    cli_args = parse_cli_args()
    AUTO_MODE = cli_args.auto
    CLI_WIFI_CONFIGURED = cli_args.wifi_mode is not None

    signal(SIGINT, handler)
    print("\n" + VERSION)
    print("\n" + UPDATES)
    print("\n" + MOTD + "\n")

    results = omg_results()
    if CLI_WIFI_CONFIGURED:
        results.WIFI_MODE = cli_args.wifi_mode
        results.WIFI_TYPE = cli_args.wifi_type
        results.WIFI_SSID = cli_args.wifi_ssid
        results.WIFI_PASS = cli_args.wifi_password
    baudrate = select_baudrate(cli_args.auto)

    thedirectory = get_script_path()
    os.chdir(thedirectory)

    if cli_args.accept_tos:
        print("<<< TERMS ACCEPTED BY --accept-tos >>>")
    else:
        omg_tos()

    omg_dependency_imports()

    results.OS_DETECTED = platform.system().upper()

    omg_locate()

    omg_reset_settings()

    omg_probe(auto=cli_args.auto, requested_port=cli_args.port)

    if FLASHER_VERSION_DETECT:
        FLASHER_VERSION = ask_for_flasherhwver()
    MENU_MODE = '1' if cli_args.auto else ''
    SANITIZED_SELECTION = cli_args.auto

    while not SANITIZED_SELECTION:
        try:
            menu_options = [
                'FLASH NEW FIRMWARE',
                'FACTORY RESET',
                'FIRMWARE UPGRADE - BATCH MODE',
                'FACTORY RESET - BATCH MODE',
                'BACKUP DEVICE',
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
            if MENU_MODE == '1' or MENU_MODE == '2' or MENU_MODE == '3' or MENU_MODE == '4' or MENU_MODE == '5' or MENU_MODE == '6':
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
            print("<<< GOODBYE. FLASHER EXITING >>> ")
            sys.exit(0)
        else:
            print("<<< NO VALID INPUT WAS DETECTED. >>>")
    except (flashapi.FatalError, serial.SerialException, serial.serialutil.SerialException) as e:
        print("<<< FATAL ERROR: %s. PLEASE DISCONNECT AND RECONNECT DEVICE AND START TASK AGAIN >>>"%str(e))
        sys.exit(1) # special case
    complete(0)
