from extronlib.ui import Slider
from hardware.hardware import all_touch_panels

tlp1 = all_touch_panels[0]

all_sliders = [
    Slider(tlp1, 'Example'),
]