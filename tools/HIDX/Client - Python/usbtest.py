#   tcpsrvr  Quick & dirty tcp client tester

import sys
import ctypes as ct
import usb.core as uc
import usb.util as uu
from time import sleep, time, localtime, strftime

def send_msg(if2, msg):
    try:
        if2.endpoints()[1].write(msg)
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** SendMsg ERROR ***: {}, {}********************************".format(err_type, value))
        raise


def test1(dev, if2, n_or_str):
    epout = if2.endpoints()[1]
    try:
        if type(n_or_str) == int:
            for i in range(n_or_str):
                try:
                    epout.write("Test {:03d}".format(i), timeout=1000)
                except:
                    err_type, value, traceback = sys.exc_info()
                    print("***** USB Write exception: {}, {} ****************".format(err_type, value))
                    raise Exception("Error in test OUT")
                    # print("Aborting at iteration {}".format(i))
                    # raise TypeError("error")
            # epout.write("********")
        else:
            epout.write(n_or_str)
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** ERROR ***: {}, {}********************************".format(err_type, value))


def testin(dev, if2, buffer_limit):
    epin = if2.endpoints()[0]
    rawdata = ""
    counter = t_bytes = 0
    try:
        remainder = buffer_limit
        while remainder > 8:
            sz = 8
            remainder -= sz
            rawdata = dev.read(epin.bEndpointAddress, sz, 1000)      # 200ms = 25 USB Frames
            counter += 1
            t_bytes += len(rawdata)
            # print("{} ({})".format(last_data, len(data)))
        print("----- IN Buffer is buff -----")
        print()
    except uc.USBTimeoutError:
        pass
        # print("- IN Time-out")
    except uc.USBError as err:
        err_type, value, traceback = sys.exc_info()
        print("***** IN Error: {}, {}".format(err_type, value))
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** IN Error: {}, {}".format(err_type, value))
        raise Exception("Error in test IN")
    try:
        if counter:
            data_str = ""
            for c in rawdata:
                data_str += chr(c)
            # print("   <<< Count: {:3},  Last: \"{}\" ({})".format(counter, data_str, len(data_str)))
        else:
            # print("    <<< No data")
            pass
    except:
        print("----- print error -----")
    return t_bytes, counter


##################################
#  Stress Test Controls
# TEST_SIZE = 100
TEST_SIZE = 200
TEST_TIME_GAP_S = 0
##################################

def stress():
    dev = uc.find(idVendor=0x1209, idProduct=0x6667)
    reattach = False
    if dev.is_kernel_driver_active(2):
        reattach = True
        dev.detach_kernel_driver(2)
    cfg = dev.get_active_configuration()
    if2 = cfg.interfaces()[2]
    print("{} ====== RawHID Stress Test ======   Burst-size: {},  Burst-wait: {} sec".format(
        strftime("%H:%M:%S> ", localtime()), TEST_SIZE, TEST_TIME_GAP_S))
    tup_bytes = 0
    ttime = 0
    tup_time = 0
    tup_count = 0
    tdown_bytes = 0
    tdown_time = 0
    tdown_count = 0
    iter = 1;
    usb_dead_counter = 0;
    try:
        while True:
            upstart = time()
            test1(dev, if2, TEST_SIZE)                          # Send 100 HID reports
            up_time = time() - upstart
            tup_time += up_time
            up_bytes = 8 * TEST_SIZE
            tup_count += TEST_SIZE
            tup_bytes += up_bytes
            downstart = time()
            down_bytes, down_count = testin(dev, if2, 10000)   # Receive all pending HID reports
            down_time = time() - downstart
            tdown_time += down_time
            tdown_bytes += down_bytes
            tdown_count += down_count
            bdiff_str = ""
            tbdiff_str = ""
            if up_bytes != down_bytes:
                bdiff_str = "  {:8d}".format(up_bytes - down_bytes)
            if tup_bytes != tdown_bytes:
                tbdiff_str = "  {:8d} bytes".format(tup_bytes - tdown_bytes)
            print("{:8s}> #{:5}    ---UP---  --DOWN--  --diff--".format(
                strftime("%H:%M:%S", localtime()), "{}".format(iter)))
            print("             Bytes  {:8d}  {:8d}{}".format(up_bytes, down_bytes, bdiff_str))
            print("           Seconds  {:8.0f}  {:8.0f}".format(up_time, down_time))
            print("   -TOTALS-     KB  {:8.1f}  {:8.1f}{}".format(tup_bytes/1000, tdown_bytes/1000, tbdiff_str))
            print("           Minutes  {:8.0f}  {:8.0f}".format(tup_time/60, tdown_time/60))
            print("   -SPEED-     BPS  {:8.1f}  {:8.1f}".format(tup_bytes/tup_time, tdown_bytes/tdown_time))
            print()
            iter += 1
            if down_bytes == 0:
                usb_dead_counter += 1
            else:
                usb_dead_counter = 0
            if usb_dead_counter > 4:
                print("***** USB IN is dead *****")
                break
            sleep(TEST_TIME_GAP_S)
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** Main Error: {}, {}".format(err_type, value))
        print(traceback)
    uu.dispose_resources(dev)
    if reattach:
        try:
            dev.attach_kernel_driver(2)
        except:
            pass

def get_dev():
    dev = uc.find(idVendor=0x1209, idProduct=0x6667)
    reattach = False
    if dev.is_kernel_driver_active(2):
        reattach = True
        dev.detach_kernel_driver(2)
    cfg = dev.get_active_configuration()
    if2 = cfg.interfaces()[2]
    return dev, if2, reattach

def free_dev(dev, reattach):
    uu.dispose_resources(dev)
    if reattach:
        try:
            dev.attach_kernel_driver(2)
        except:
            pass

def send(size, count):
    flood_msg = 'a0123456b0123456c0123456d0123456e0123456f0123456g0123456h0123456i0123456j012345-'
    dev, if2, reattach = get_dev()
    print("{} ====== Send() ======   Size: {},  Repeat: {}".format(
        strftime("%H:%M:%S> ", localtime()), size, count))
    tup_bytes = 0
    tdown_bytes = 0
    ttime = 0
    tup_time = 0
    tdown_time = 0
    tup_count = 0
    tdown_count = 0
    iter = 1;
    usb_dead_counter = 0;
    # Generate msg
    msg = ''
    size80 = int((size + 1) / 80)
    for i in range(size80):
        msg += flood_msg
    remaining = size % 80
    msg += flood_msg[:remaining]
    print("Gen. msg({}): {}".format(len(msg), msg))
    #==========================================================
    upstart = time()
    for i in range(count):
        send_msg(if2, msg)
        tup_count += 1
        tup_bytes += len(msg)
    up_time = time() - upstart
    tup_time += up_time
    up_bytes = 8 * TEST_SIZE
    tup_count += TEST_SIZE
    tup_bytes += up_bytes
    try:
        while True:
            downstart = time()
            down_bytes, down_count = testin(dev, if2, 10000)   # Receive all pending HID reports
            down_time = time() - downstart
            tdown_time += down_time
            tdown_bytes += down_bytes
            tdown_count += down_count
            bdiff_str = ""
            tbdiff_str = ""
            if up_bytes != down_bytes:
                bdiff_str = "  {:8d}".format(up_bytes - down_bytes)
            if tup_bytes != tdown_bytes:
                tbdiff_str = "  {:8d} bytes".format(tup_bytes - tdown_bytes)
            print("{:8s}> #{:5}    --DOWN--".format(
                strftime("%H:%M:%S", localtime()), "{}".format(iter)))
            print("             Bytes  {:8d}".format(down_bytes))
            print("           Seconds  {:8.0f}".format(down_time))
            print("   -TOTALS-     KB  {:8.1f}".format(tdown_bytes/1000))
            print("           Minutes  {:8.0f}".format(tdown_time/60))
            print("   -SPEED-     BPS  {:8.1f}".format(tdown_bytes/tdown_time))
            print()
            iter += 1
            if down_bytes == 0:
                usb_dead_counter += 1
            else:
                usb_dead_counter = 0
            if usb_dead_counter > 4:
                print("***** USB IN is dead *****")
                break
            sleep(TEST_TIME_GAP_S)
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** Main Error: {}, {}".format(err_type, value))
        print(traceback)
    free_dev(dev, reattach)

def _send(dev, if2, prefix, size, count):
    timeout = False
    onerpt = prefix + ':345678'
    tup_bytes = 0
    tup_time = 0
    tup_count = 0
    msg = ''
    size8 = int((size + 1) / 8)
    for i in range(size8):
        msg += onerpt
    remaining = size % 8
    # adj8 = int((remaining + 7) / 8) * 8
    msg += onerpt[:remaining]
    print("Gen. msg({}): {}".format(len(msg), msg))
    upstart = time()
    try:
        for i in range(count):
            send_msg(if2, msg)
            tup_count += 1
            tup_bytes += len(msg)
    except uc.USBTimeoutError:
        timeout = True
    except:
        raise
    tup_time = time() - upstart
    return tup_count, tup_bytes, tup_time, timeout

def test4(size, count):
    dev, if2, reattach = get_dev()
    print("Test #4: size: {},  repeat: {}".format(size, count))
    msgs, bytes, time, timeout = _send(dev, if2, '4', size, count)
    free_dev(dev, reattach)
    print("{:8s}>           ---UP---".format(strftime("%H:%M:%S", localtime())))
    print("   -TOTALS-  Bytes  {:8.0f}    Count: {}".format(bytes, msgs))
    print("           Seconds  {:8.1f}".format(time))
    print("   -SPEED-     BPS  {:8.1f}".format(bytes / time))

def test5(size, count):
    dev, if2, reattach = get_dev()
    tup_count, tup_bytes, tup_time, timeout = _send(dev, if2, '5', size, count)
    tdown_bytes = 0
    tdown_time = 0
    tdown_count = 0
    usb_dead_counter = 0;
    try:
        while True:
            downstart = time()
            down_bytes, down_count = testin(dev, if2, 10000)   # Receive all pending HID reports
            down_time = time() - downstart
            tdown_time += down_time
            tdown_bytes += down_bytes
            tdown_count += down_count
            print("{:8s}>           ---UP---  --DOWN--".format(
                strftime("%H:%M:%S", localtime())))
            print("             Bytes  {:8d}  {:8d}".format(tup_bytes, down_bytes))
            print("           Seconds  {:8.0f}  {:8.0f}".format(tup_time, down_time))
            print("   -TOTALS-     KB  {:8.1f}  {:8.1f}".format(tup_bytes/1000, tdown_bytes/1000))
            print("           Minutes  {:8.0f}  {:8.0f}".format(tup_time/60, tdown_time/60))
            print("   -SPEED-     BPS  {:8.1f}  {:8.1f}".format(tup_bytes/tup_time, tdown_bytes/tdown_time))
            print()
            if down_bytes == 0:
                usb_dead_counter += 1
            else:
                usb_dead_counter = 0
            if usb_dead_counter > 4:
                print("***** USB IN is dead *****")
                break
            sleep(TEST_TIME_GAP_S)
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** Main Error: {}, {}".format(err_type, value))
        print(traceback)
    finally:
        free_dev(dev, reattach)

def reset():
    dev, if2, reattach = get_dev()
    send_msg(if2, "*reset")
    free_dev(dev, reattach)

def read():
    dev, if2, reattach = get_dev()
    epin = if2.endpoints()[0]
    try:
        counter = t_bytes = 0
        while True:
            rawdata = dev.read(epin.bEndpointAddress, 8, 1000)
            counter += 1
            t_bytes += len(rawdata)
            data_str = ""
            for c in rawdata:
                data_str += chr(c)
            print("{} ({})".format(data_str, len(data_str)))
    except uc.USBTimeoutError:
        pass
    except uc.USBError as err:
        err_type, value, traceback = sys.exc_info()
        print("***** IN Error: {}, {}".format(err_type, value))
    except:
        err_type, value, traceback = sys.exc_info()
        print("***** IN Error: {}, {}".format(err_type, value))
        raise Exception("Error in test IN")
    finally:
        free_dev(dev, reattach)
        print(" Total  msgs: {},   bytes: {}".format(counter, t_bytes))

