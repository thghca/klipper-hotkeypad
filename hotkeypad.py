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
        logging.error(f'Template error:\n{self._undefined_message}')
        return ''

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
        __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
        __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
        __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = __int__ = \
        __float__ = __complex__ = __pow__ = __rpow__ = \
        _fail_with_undefined_error

KEYSTATES = ("up", "down", "hold")
DROP_EVENT_OLDER_SEC = 1.0
DEFAULT_CONFIG_NAME = 'config.cfg'

config_path = os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_NAME)
KEY_DEFAULT = 'KEY_DEFAULT'
mapping = {}
variables = {}
devices = {}
HOST = '127.0.0.1'
PRINT_KEY_EVENTS = False
env = jinja2.Environment(undefined=LoggerUndefined)

def indent(s, spaces):
    ind=''.ljust(spaces)
    return ind + ('\n' + ind).join(s.splitlines())

def send_gcode(cmd):
    #Request blocks thread. Fix?
    logging.info(f'\n    gcode:\n{indent(cmd,8)}')
    requests.post(f'http://{HOST}/printer/gcode/script',
                  data={'script': cmd})

def send_device_toggle(device):
    #Request blocks thread. Fix?
    logging.info(f'\n    send_device_toggle: {device}')
    requests.post(f'http://{HOST}/machine/device_power/device',
                  data={'device': device, 'action': 'toggle'})

def system_call(cmd):
    #Call blocks thread. Fix?
    logging.info(f'\n    gcode:\n{indent(cmd,8)}')
    os.system(cmd)

env.globals = {
            'action_gcode': send_gcode,
            'action_dev': send_device_toggle,
            'action_exec': system_call,
            'action_print': print,
            'vars' : variables
        }

def grab_keyboards():
    for _, kbd in devices.items():
        kbd.grab()
        logging.info(f"grabbed {kbd.name}")

def ungrab_keyboards():
    for _, kbd in devices.items():
        try:
            kbd.ungrab()
            logging.info(f"ungrabbed {kbd.name}")
        except OSError as e:
            if e.args[0] == 19:
                logging.warning(f"ungrab {kbd.name} fail, device disconnected?")
            else:
                raise


def process_key_event(event):
    keycode = event.keycode
    keystate = KEYSTATES[event.keystate]
    if PRINT_KEY_EVENTS:
        print(f"keycode: {keycode}, scancode: {event.scancode}, state:{keystate}")

    actions = mapping.get(keycode) or mapping.get(KEY_DEFAULT)
    if actions is not None:
        action = actions.get(keystate)
        if action is not None:
            try:
                context = {'event_keycode': keycode,
                           'event_timestamp': event.event.timestamp}
                action.render(context)
            except jinja2.TemplateError:
                msg = f"Template error for {keycode}: {keystate}"
                logging.exception(msg)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda signalNumber, frame: sys.exit())

    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--config', default=config_path,
                        help=f'Path to config file. Defaults to {DEFAULT_CONFIG_NAME}')
    parser.add_argument('-v','--verbose', default=config_path,action='store_true',
                        help='Verbose logging')
    parser.add_argument('-k','--keys', default=config_path,action='store_true',
                        help='Print key events')
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARN)
    if args.keys:
        PRINT_KEY_EVENTS = True
    kbd_paths = []

    config = configparser.ConfigParser(interpolation=None)
    config.read(os.path.join(os.path.dirname(__file__), args.config))
    logging.info('config')
    for section_name in config.sections():
        logging.info(f'  [{section_name}]')
        section = config[section_name]
        if section_name == 'moonraker':
            host = section.get('host','127.0.0.1').strip()
            if host is not None:
                HOST = host
                logging.info(f'    host:{host}')
        elif section_name == 'keyboards':
            paths = config.items(section_name)
            for key, path in paths:
                kbd_paths.append(path.strip())
                logging.info(f'    path:{path}')
        elif section_name.startswith('key'):
            keycode = section_name.split()[1]
            actions = {}
            for keystate in KEYSTATES:
                action = section.get(keystate)
                if action is not None:
                    logging.info(f'\n    {keycode} {keystate}:\n{indent(action,6)}')
                    try:
                        actions[keystate] = env.from_string(action)
                    except jinja2.TemplateSyntaxError:
                        logging.exception('Template syntax error')
            mapping[keycode] = actions
        elif section_name == 'variables':
            for key, value in config.items(section_name):
                logging.info(f'    variable:{key}({value})')
                if key.startswith('flist_'):
                    try:
                        variables[key] = [float(x) for x in value.split(',')]
                    except ValueError:
                        logging.exception(f'Error in parsing variable {key}')
                elif key.startswith('int_'):
                    try:
                        variables[key] = int(value)
                    except ValueError:
                        logging.exception(f'Error in parsing variable {key}')
                else:
                    variables[key] = value


    devices = {dev.fd: dev for dev in map(InputDevice, kbd_paths)}
    for dev in devices.values():
        logging.debug(dev)
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
                        logging.warning(f"Unknown event type: {categorize(event)}")
    except (KeyboardInterrupt,SystemExit):
        pass
    finally:
        ungrab_keyboards()
        for dev in devices.values():
            dev.close()
