This is for all versions of the O.MG Cable, O.MG Adapter, and O.MG Plug



# [Setup Instructions & Latest Firmware](https://github.com/O-MG/O.MG-Firmware/wiki)



<img src="https://o.mg.lol/OMGCable-pkg.jpg" >

## Automated flashing

`flash.py` can select the only connected CP210x programmer, flash the current
firmware, configure Wi-Fi, and request the firmware's default OFAT layout:

```sh
python3 ./flash.py --auto \
  --wifimode station \
  --wifissid LabNet \
  --wifipasswd CatbugLovesYou
```

This still displays the required terms prompt. For a genuinely unattended
invocation, after reading and accepting those terms, add `--accept-tos`:

```sh
python3 ./flash.py --auto --accept-tos \
  --wifimode station \
  --wifissid LabNet \
  --wifipasswd CatbugLovesYou
```

If more than one CP210x programmer is connected, select one with `--port`.
Accepted Wi-Fi modes are `station` and `ap`. All three Wi-Fi flags must be
provided together. Quote credentials containing shell metacharacters. Auto
mode connects to the ESP ROM at 115200 and then flashes at 460800 baud. Wi-Fi
passwords must be 8-63 UTF-8 bytes or a 64-digit hexadecimal PSK.

The packaged `firmware/firmware-update.json` is required. The flasher verifies
the boot, application, WebUI, `blank.bin`, `blank-settings.bin`, and PHY-init
files against it, uses its hexadecimal flash targets, and reads the
protected data-reset geometry from its `programmer` section. The two
blank templates are verified before Python generates the first-boot Wi-Fi and
OFAT images. Programmer-only records are explicitly excluded from OTA. Unsafe
or overlapping targets are rejected before the serial flash operation starts.
