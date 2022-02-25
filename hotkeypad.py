#!/usr/bin/python -u
import select
import time
import sys
import signal

from evdev import InputDevice, categorize, ecodes
from requests import post

DEBUG = True
DEBUG_PRINT_UNKNOWN_EVENTS = True
DEBUG_PRINT_KNOWN_KEYS = False
DEBUG_PRINT_UNKNOWN_KEYS =True
DROP_EVENT_OLDER_SEC = 1.0

# Mediana m-kn-np674 numpad
KEYBOARDS = (
    # Regular numpad keys + tab
    '/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd',
    # Home, mail and calc buttons. No hold events
    '/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-if01')

mapping = {
    #row1
    "KEY_HOMEPAGE": None,
    "KEY_TAB": None,
    "KEY_MAIL": None,
    "KEY_CALC": None,  
    #row2
    "KEY_NUMLOCK": None,
    "KEY_KPSLASH": None,
    "KEY_KPASTERISK": None,
    "KEY_BACKSPACE": None,
    #row3
    "KEY_KP7": None,
    "KEY_KP8": None,
    "KEY_KP9": None,
    "KEY_KPMINUS": None,
    #row4
    "KEY_KP4": None,
    "KEY_KP5": None,
    "KEY_KP6": None,
    "KEY_KPPLUS": None,
    #row5
    "KEY_KP1": None,
    "KEY_KP2": None,
    "KEY_KP3": None,
    "KEY_KPENTER": "_PAUSERESUME",
    #row6
    "KEY_KP0": None,
    "KEY_KPSPACE": None,
    "KEY_KPDOT": None,
}

devices = {}

def send_gcode(cmd):
    #Request blocks thread. Fix?
    post('http://127.0.0.1/printer/gcode/script', data={'script': cmd})

def grab_keyboards():
    for fd, kbd in devices.items():
        kbd.grab()
        if DEBUG:
            print("grabbed {}".format(kbd.name))
    
def ungrab_keyboards():
    for fd, kbd in devices.items():
        kbd.ungrab()
        if DEBUG:
            print("ungrabbed {}".format(kbd.name))

def process_key_event(event):
    known = event.keycode in mapping
    if known and DEBUG_PRINT_KNOWN_KEYS or not known and DEBUG_PRINT_UNKNOWN_KEYS:
            print("keycode: {}, scancode: {}, state:{}".format(event.keycode, event.scancode , ("up", "down", "hold")[event.keystate]))   
    if event.keystate == event.key_down:
        cmd = mapping.get(event.keycode)
        if cmd is not None:
            send_gcode(cmd)
    elif event.keystate == event.key_up:
        pass
    elif event.keystate == event.key_hold:
        pass


def terminate(signalNumber, frame):
    sys.exit()

if __name__ == "__main__":
    run = True
    signal.signal(signal.SIGTERM, terminate)
    #signal.signal(signal.SIGINT, terminate)
    devices = {dev.fd: dev for dev in map(InputDevice, KEYBOARDS)}
    if DEBUG:
        for dev in devices.values(): print(dev)
    grab_keyboards()
    try:        
        while True:
            r, w, x = select.select(devices, [], [])
            for fd in r:
                for event in devices[fd].read():
                    if time.time() - event.timestamp() > DROP_EVENT_OLDER_SEC:
                        continue
                    if event.type == ecodes.EV_KEY:
                        process_key_event(categorize(event))
                    elif event.type == ecodes.EV_SYN:	
                        pass #spam between events, ignore
                    elif event.type == ecodes.EV_MSC:	
                        pass #scancodes, ignore
                    else:
                        if DEBUG_PRINT_UNKNOWN_EVENTS:
                            print("WOW! New event type!:")
                            print(categorize(event))
    except (KeyboardInterrupt,SystemExit):
        pass
    finally:
        ungrab_keyboards()
        for dev in devices.values(): dev.close()