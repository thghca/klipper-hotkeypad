#!/usr/bin/python -u

import configparser
import logging
import os
import select
import time
import sys
import signal
import argparse

import jinja2
import requests
from evdev import InputDevice, categorize, ecodes

class LoggerUndefined(jinja2.Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        logging.error('Template error:\n{}'.format(self._undefined_message))
        return ''

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
        __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
        __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
        __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = __int__ = \
        __float__ = __complex__ = __pow__ = __rpow__ = \
        _fail_with_undefined_error     

DROP_EVENT_OLDER_SEC = 1.0
DEFAULT_CONFIG_NAME = 'config.cfg'

config_path = os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_NAME)
KEY_DEFAULT = 'KEY_DEFAULT'
mapping = {}
devices = {}
host = '127.0.0.1'
print_key_events = False
env = jinja2.Environment(undefined=LoggerUndefined)
 

def send_gcode(cmd):
    #Request blocks thread. Fix?
    logging.info('\n    gcode: {}'.format('\n        '.join(['']+cmd.splitlines())))
    requests.post('http://{}/printer/gcode/script'.format(host), data={'script': cmd})

def send_device_toggle(device):
    #Request blocks thread. Fix?
    logging.info('\n    send_device_toggle: {}'.format(device))
    requests.post('http://{}/machine/device_power/device'.format(host), data={'device': device, 'action': 'toggle'})

def system_call(cmd):
    #Call blocks thread. Fix?
    logging.info('\n    system_call: {}'.format('\n        '.join(['']+cmd.splitlines())))
    os.system(cmd)
    
env.globals = {
            'action_gcode': send_gcode,
            'action_dev': send_device_toggle,
            'action_exec': system_call,
            'action_print': print,
        }

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

KEYSTATES = ("up", "down", "hold")
def process_key_event(event):
    keycode = event.keycode
    keystate = KEYSTATES[event.keystate]
    if print_key_events:
        print("keycode: {}, scancode: {}, state:{}".format(keycode, event.scancode , keystate))
        
    actions = mapping.get(keycode) or mapping.get(KEY_DEFAULT)
    if actions is not None:
        t = actions.get(keystate)
        try:
            t.render({'context_keycode': keycode}) if t is not None else None
        except Exception as e:
            msg = "Template error for {}: {}".format(keycode, keystate)
            logging.exception(msg)

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
            actions = {}
            for keystate in KEYSTATES:
                action = section.get(keystate)
                if action is not None:
                    logging.info('\n    {} {}: {}'.format(keycode,keystate, '\n        '.join(['']+action.splitlines())))
                    actions[keystate] = env.from_string(action)       
            mapping[keycode] = actions
            
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