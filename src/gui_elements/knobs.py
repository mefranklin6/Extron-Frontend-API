from extronlib.ui import Knob

from hardware.hardware import all_ui_devices

tlp1 = all_ui_devices[0]

all_knobs = [
    Knob(tlp1, 'Example'),
]