from extronlib.interface import EthernetClientInterface, SerialInterface, RelayInterface

"""
These classes extend the built-in extronlib classes

Additions:
- alias: a friendly name for the port or device

"""


class EthernetClientInterfaceEx(EthernetClientInterface):
    def __init__(
        self,
        Hostname,
        IPPort,
        Protocol="TCP",
        ServicePort=0,
        Credentials=None,
        bufferSize=4096,
        alias=None,
    ):
        super().__init__(
            Hostname, IPPort, Protocol, ServicePort, Credentials, bufferSize
        )
        self.alias = alias


class SerialInterfaceEx(SerialInterface):
    def __init__(
        self,
        Host,
        Port,
        Baud=9600,
        Data=8,
        Parity="None",
        Stop=1,
        FlowControl="Off",
        CharDelay=0,
        Mode="RS232",
        alias=None,
    ):
        super().__init__(
            Host, Port, Baud, Data, Parity, Stop, FlowControl, CharDelay, Mode
        )
        self.alias = alias


class RelayInterfaceEx(RelayInterface):
    def __init__(self, host, port, alias=None):
        super().__init__(host, port)
        self.alias = alias
