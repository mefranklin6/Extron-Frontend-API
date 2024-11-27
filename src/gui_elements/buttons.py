from extronlib.ui import Button

from hardware.hardware import all_touch_panels

tlp1 = all_touch_panels[0]

all_buttons = [
    Button(tlp1, 'Example'),
]