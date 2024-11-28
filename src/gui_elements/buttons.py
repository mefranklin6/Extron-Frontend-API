from extronlib.ui import Button

from hardware.hardware import all_ui_devices

tlp1 = all_ui_devices[0]

all_buttons = [
    Button(tlp1, 'Example'),
]