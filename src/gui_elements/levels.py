from extronlib.ui import Level

from hardware.hardware import all_touch_panels

tlp1 = all_touch_panels[0]

all_levels = [
    Level(tlp1, 'Example'),
]