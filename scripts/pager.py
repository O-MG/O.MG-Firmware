#!/usr/bin/env python
"""
Page output and find dimensions of console.

This module deals with paging on Linux terminals and Windows consoles in
a cross-platform way. The major difference for paging here is line ends.
Not line end characters, but the console behavior when the last character
on a line is printed.  To get technical details, run this module without
parameters::

  python pager.py

Author:  anatoly techtonik <techtonik@gmail.com>
License: Public Domain (use MIT if the former doesn't work for you)
"""

__version__ = '3.3'

import os,sys

WINDOWS = os.name == 'nt'
PY3K = sys.version_info >= (3,)

# Windows constants
# http://msdn.microsoft.com/en-us/library/ms683231%28v=VS.85%29.aspx

STD_INPUT_HANDLE  = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE  = -12


# --- console/window operations ---

if WINDOWS:
    # get console handle
    from ctypes import windll, Structure, byref
    try:
        from ctypes.wintypes import SHORT, WORD, DWORD
    # workaround for missing types in Python 2.5
    except ImportError:
        from ctypes import (
            c_short as SHORT, c_ushort as WORD, c_ulong as DWORD)
    console_handle = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

    # CONSOLE_SCREEN_BUFFER_INFO Structure
    class COORD(Structure):
        _fields_ = [("X", SHORT), ("Y", SHORT)]

    class SMALL_RECT(Structure):
        _fields_ = [("Left", SHORT), ("Top", SHORT),
                    ("Right", SHORT), ("Bottom", SHORT)]

    class CONSOLE_SCREEN_BUFFER_INFO(Structure):
        _fields_ = [("dwSize", COORD),
                    ("dwCursorPosition", COORD),
                    ("wAttributes", WORD),
                    ("srWindow", SMALL_RECT),
                    ("dwMaximumWindowSize", DWORD)]


def _windows_get_window_size():
    """Return (width, height) of available window area on Windows.
       (0, 0) if no console is allocated.
    """
    sbi = CONSOLE_SCREEN_BUFFER_INFO()
    ret = windll.kernel32.GetConsoleScreenBufferInfo(console_handle, byref(sbi))
    if ret == 0:
        return (0, 0)
    return (sbi.srWindow.Right - sbi.srWindow.Left + 1,
            sbi.srWindow.Bottom - sbi.srWindow.Top + 1)

def _posix_get_window_size():
    """Return (width, height) of console terminal on POSIX system.
       (0, 0) on IOError, i.e. when no console is allocated.
    """
    # see README.txt for reference information
    # http://www.kernel.org/doc/man-pages/online/pages/man4/tty_ioctl.4.html

    from fcntl import ioctl
    from termios import TIOCGWINSZ
    from array import array
    
    winsize = array("H", [0] * 4)
    try:
        ioctl(sys.stdout.fileno(), TIOCGWINSZ, winsize)
    except IOError:
        # for example IOError: [Errno 25] Inappropriate ioctl for device
        # when output is redirected
        # [ ] TODO: check fd with os.isatty
        pass
    return (winsize[1], winsize[0])

def getwidth():
    width = None
    if WINDOWS:
        return _windows_get_window_size()[0]
    elif os.name == 'posix':
        return _posix_get_window_size()[0]
    else:
        # 'mac', 'os2', 'ce', 'java', 'riscos' need implementations
        pass

    return width or 80

def getheight():
    height = None
    if WINDOWS:
        return _windows_get_window_size()[1]
    elif os.name == 'posix':
        return _posix_get_window_size()[1]
    else:
        # 'mac', 'os2', 'ce', 'java', 'riscos' need implementations
        pass

    return height or 25

if WINDOWS:
    ENTER_ = '\x0d'
    CTRL_C_ = '\x03'
else:
    ENTER_ = '\n'
    # [ ] check CTRL_C_ on Linux
    CTRL_C_ = None
ESC_ = '\x1b'

# other constants with getchars()
if WINDOWS:
    LEFT =  ['\xe0', 'K']
    UP =    ['\xe0', 'H']
    RIGHT = ['\xe0', 'M']
    DOWN =  ['\xe0', 'P']
else:
    LEFT =  ['\x1b', '[', 'D']
    UP =    ['\x1b', '[', 'A']
    RIGHT = ['\x1b', '[', 'C']
    DOWN =  ['\x1b', '[', 'B']
ENTER = [ENTER_]
ESC  = [ESC_]

def dumpkey(key):
    def hex3fy(key):
        """Helper to convert string into hex string (Python 3 compatible)"""
        from binascii import hexlify
        # Python 3 strings are no longer binary, encode them for hexlify()
        if PY3K:
           key = key.encode('utf-8')
        keyhex = hexlify(key).upper()
        if PY3K:
           keyhex = keyhex.decode('utf-8')
        return keyhex
    if type(key) == str:
        return hex3fy(key)
    else:
        return ' '.join( [hex3fy(s) for s in key] )


if WINDOWS:
    if PY3K:
        from msvcrt import kbhit, getwch as __getchw
    else:
        from msvcrt import kbhit, getch as __getchw

def _getch_windows(_getall=False):
    chars = [__getchw()]  # wait for the keypress
    if _getall:           # read everything, return list
        while kbhit():
            chars.append(__getchw())
        return chars
    else:
        return chars[0]


# [ ] _getch_linux() or _getch_posix()? (test on FreeBSD and MacOS)
def _getch_unix(_getall=False):
    import sys, termios

    fd = sys.stdin.fileno()
    # save old terminal settings
    old_settings = termios.tcgetattr(fd)

    chars = []
    try:
        newattr = list(old_settings)
        newattr[3] &= ~termios.ICANON
        newattr[3] &= ~termios.ECHO
        newattr[6][termios.VMIN] = 1   # block until one char received
        newattr[6][termios.VTIME] = 0
        # TCSANOW below means apply settings immediately
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        # [ ] this fails when stdin is redirected, like
        #       ls -la | pager.py
        #   [ ] also check on Windows
        ch = sys.stdin.read(1)
        chars = [ch]

        if _getall:
            newattr = termios.tcgetattr(fd)
            newattr[6][termios.VMIN] = 0      # CC structure
            newattr[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, newattr)

            while True:
                ch = sys.stdin.read(1)
                if ch != '':
                    chars.append(ch)
                else:
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if _getall:
        return chars
    else:
        return chars[0]


# choose correct getch function at module import time
if WINDOWS:
    getch = _getch_windows
else:
    getch = _getch_unix

getch.__doc__ = \
    """
    Wait for keypress, return first char generated as a result.

    Arrows and special keys generate sequence of chars. Use `getchars`
    function to receive all chars generated or present in buffer.
    """

    # check that Ctrl-C and Ctrl-Break break this function
    #
    # Ctrl-C       [n] Windows  [y] Linux  [ ] OSX
    # Ctrl-Break   [y] Windows  [n] Linux  [ ] OSX


# [ ] check if getchars returns chars already present in buffer
#     before the call to this function
def getchars():
    return getch(_getall=True)
    

def echo(msg):
    #https://groups.google.com/forum/#!topic/python-ideas/8vLtBO4rzBU
    sys.stdout.write(msg)
    sys.stdout.flush()

def prompt(pagenum):
    prompt = "Page -%s-. Press any key to continue . . . " % pagenum
    echo(prompt)
    if getch() in [ESC_, CTRL_C_, 'q', 'Q']:
        return False
    echo('\r' + ' '*(len(prompt)-1) + '\r')

def page(content, pagecallback=prompt):
    width = getwidth()
    height = getheight()
    pagenum = 1

    try:
        try:
            line = content.next().rstrip("\r\n")
        except AttributeError:
            # Python 3 compatibility
            line = content.__next__().rstrip("\r\n")
    except StopIteration:
        pagecallback(pagenum)
        return

    while True:     # page cycle
        linesleft = height-1 # leave the last line for the prompt callback
        while linesleft:
            linelist = [line[i:i+width] for i in range(0, len(line), width)]
            if not linelist:
                linelist = ['']
            lines2print = min(len(linelist), linesleft)
            for i in range(lines2print):
                if WINDOWS and len(line) == width:
                    # avoid extra blank line by skipping linefeed print
                    echo(linelist[i])
                else:
                    print(linelist[i])
            linesleft -= lines2print
            linelist = linelist[lines2print:]

            if linelist: # prepare symbols left on the line for the next iteration
                line = ''.join(linelist)
                continue
            else:
                try:
                    try:
                        line = content.next().rstrip("\r\n")
                    except AttributeError:
                        # Python 3 compatibility
                        line = content.__next__().rstrip("\r\n")
                except StopIteration:
                    pagecallback(pagenum)
                    return
        if pagecallback(pagenum) == False:
            return
        pagenum += 1





