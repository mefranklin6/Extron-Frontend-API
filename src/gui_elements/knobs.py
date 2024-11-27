from extronlib.ui import Knob

from hardware import all_touch_panels

tlp1 = all_touch_panels[0]

all_knobs = [
    Knob(tlp1, 'Example'),
]