
# klipper-hotkeypad

A python script to control klipper wuth usb numpad

## Installation (raspbian)

1. copy klipper-hotkeypad folder to /home/pi
2. install python3
3. install requests, evdev and jinja packages
4. edit config (see below)
5. run start.sh

## Runing as service (raspbian)

1. edit hotkeypad.rules: replace product and vendor ids with ones from your numpad
2. copy hotkeypad.rules to /etc/udev/rules.d/
3. copy hotkeypad.service to /etc/systemd/system/
4. reboot

## Commandline argguments

- -c , --config: Path to config file. Defaults to config.cfg
- -v, --verbose: more logging output
- -k, --keys: Print key events to output (use this to get keycodes)

## Config file

```
[moonraker]
# Hostname of machine with moonraker
host: 127.0.0.1

# List of input devices. Some numpad has more then one
[keyboards]
path_1: /dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd
path_2: /dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-if01

# Variables for storing data between events 
[variables]
variable: value
flist_floats: 1, 10, 100
int_integer: 0
# "flist_" prefix for comma-separated list of floats
# "int_" prefix for integer
# others threated as strings

# Key configs
[key KEYCODE]
#up:
#down:
#hold:
#   jinja2 templates for key events

```
[Look keycodes here.](https://github.com/torvalds/linux/blob/2293be58d6a18cab800e25e42081bacb75c05752/include/uapi/linux/input-event-codes.h#L75)  
KEY_DEFAULT may be used for all keys not defined in config file.

### Templates:

#### Actions:

* Send gcode via moonraker:  
  `{{ action_gcode("G28") }}`

* Toggle moonraker device:  
  `{{ action_dev("device") }}`

* System call:  
  `{{ action_exec("command") }}`

* Print in terminal:  
  `{{ action_print("print") }}`

#### Context:

* Keycode of event:  
`event_keycode`
* Get timestamp as float:  
`event_timestamp()`

#### Variables from [variables] section:

* getting value:  
  `{% set x = vars['x'] %}`
* setting value:  
  `{% set t = vars.__setitem__('x', 123) %}`

## Notes

* Script grab all keyboards in config! Do not use with your primary keybord! 
* System call not tested at all
* It's should be possible to execute multiple actions. Not tested yet.
* Calls and requests for api are block script until completed for now
* Use at you own risk

## changelog

* 0.2.1 add variables
* 0.2.0 move to jinja2
* 0.1.0 "it works"
