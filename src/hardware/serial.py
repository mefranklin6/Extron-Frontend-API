from extronlib.interface import SerialInterface

from hardware.hardware import all_processors

processor1 = all_processors[0]

all_serial_interfaces = [
    SerialInterface(processor1, "COM1")
]