#!/usr/bin/python -u
import configparser
import logging
import os
import select
import time
import sys
import signal
import argparse

import requests
from evdev import InputDevice, categorize, ecodes

DROP_EVENT_OLDER_SEC = 1.0
DEFAULT_CONFIG_NAME = 'config.cfg'

config_path = os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_NAME)
mapping = {}
devices = {}
host = '127.0.0.1'
print_key_events = False

def send_gcode(cmd):
    #Request blocks thread. Fix?
    requests.post('http://{}/printer/gcode/script'.format(host), data={'script': cmd})

def send_device_toggle(device):
    #Request blocks thread. Fix?
    requests.post('http://{}/machine/device_power/device'.format(host), data={'device': device, 'action': 'toggle'})

def system_call(cmd):
    os.system(cmd)

def grab_keyboards():
    for fd, kbd in devices.items():
        kbd.grab()
        logging.info("grabbed {}".format(kbd.name))
    
def ungrab_keyboards():
    for fd, kbd in devices.items():
        try:
            kbd.ungrab()
            logging.info("ungrabbed {}".format(kbd.name))
        except OSError as ex:
            if ex.args[0] == 19:
                logging.warning("ungrab {} fail, device disconnected?".format(kbd.name))
            else:
                raise

def run_actions(actions):
    for (action, arg) in actions:
        if action == 'gcode':
            send_gcode(arg)
        elif action == 'dev':
            send_device_toggle(arg)
        elif action == 'exec':
            system_call(arg)

def process_key_event(event):
    if print_key_events:
        print("keycode: {}, scancode: {}, state:{}".format(event.keycode, event.scancode , ("up", "down", "hold")[event.keystate]))   
    if event.keystate == event.key_down:
        actions = mapping.get(event.keycode)
        if actions is not None:
            run_actions(actions)   
    elif event.keystate == event.key_up:
        pass
    elif event.keystate == event.key_hold:
        pass


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda signalNumber, frame: sys.exit())
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--config', default=config_path, help='Path to config file. Defaults to {}'.format(DEFAULT_CONFIG_NAME))
    parser.add_argument('-v','--verbose', default=config_path,action='store_true', help='Verbose logging')
    parser.add_argument('-k','--keys', default=config_path,action='store_true', help='Print key events')
    args = parser.parse_args()
    if(args.verbose):
        logging.basicConfig(level=logging.INFO)
    else:
         logging.basicConfig(level=logging.WARN)
    if(args.keys):
        print_key_events = True   
    kbd_paths = []
    
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__), args.config))
    for section_name in config.sections():
        section = config[section_name] 
        if section_name == 'moonraker':
            host = section.get('host','127.0.0.1').strip()
        elif section_name == 'keyboards':
            paths = config.items(section_name)
            for key, path in paths:
                kbd_paths.append(path.strip())
        elif section_name.startswith('key'):
            keycode = section_name.split()[1]
            alist=[]
            for key in section:
                (action, sep, posfix) = key.partition("_")
                arg = section.get(key)
                alist.append((posfix, action, arg))
            alist.sort(key=lambda x:x[0])
            mapping[keycode] = [(action, arg) for (posfix, action, arg) in alist]
            
    devices = {dev.fd: dev for dev in map(InputDevice, kbd_paths)}
    for dev in devices.values(): logging.debug(dev)
    try: 
        grab_keyboards()       
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
                        logging.warning("Unknown event type: {}".format(categorize(event)))
    except (KeyboardInterrupt,SystemExit):
        pass
    finally:
        ungrab_keyboards()
        for dev in devices.values(): dev.close()