# klipper-hotkeypad
A python script to control klipper wuth usb numpad

## Installation (raspbian)
1. copy klipper-hotkeypad folder to /home/pi
2. install python3
3. install requests and evdev pascages
4. edit config (see below)
5. run start.bat

## Runing as service (raspbian)
1. edit hotkeypad.rules: replace product and vendor ids with ones from your numpad
2. copy hotkeypad.rules to /etc/udev/rules.d/
3. copy hotkeypad.service to /etc/systemd/system/
4. reboot

## Commandline argguments
- -c , --config: Path to config file. Defaults to config.cfg
- -v, --verbose: more logging
- -k, --keys: Print key events to output (use this to get keycodes)

## Config file
```
[moonraker]
#hostname of machine with moonraker
host: 127.0.0.1

#List of input devices. Some numpad has more then one
[keyboards]
path_1: /dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd
path_2: /dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-if01

#Key configs. Only key down event  for now
[key KEYCODE]
gcode: G28 # send gcode via moonraker
dev: devicename # toggle moonraker device
exec: echo 123 # system call
```
## Notes
* Script grab all keyboards in config! Do not use with your primary keybord! 
* System call not tested at all
* It's should possible to execute multiple actions ordered by postfix: gcode_1,gcode_2... Not tested yet.
* Calls and requests for api are block script until completed for now
* Use at you own risk

