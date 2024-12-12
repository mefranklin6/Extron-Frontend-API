from extronlib.interface import EthernetClientInterface

"""
Devices should only be added here if they are on the processors AVLAN or
a segmented network that only the processor can access.

Regular networked devce control should be handled through your backend server.
"""

all_ethernet_interfaces = [
    # EthernetClientInterface('192.168.254.131', 22023, Protocol='SSH', Credentials=('admin', 'your_password')),
]