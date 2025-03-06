import json
import urllib.error
import urllib.request

from extronlib import event
from extronlib.interface import EthernetServerInterfaceEx
from extronlib.system import File as open
from extronlib.system import SaveProgramLog, Timer, Wait

import variables as v
from extronlib_extensions import (
    EthernetClientInterfaceEx,
    RelayInterfaceEx,
    SerialInterfaceEx,
)
from gui_elements.buttons import all_buttons
from gui_elements.knobs import all_knobs
from gui_elements.labels import all_labels
from gui_elements.levels import all_levels
from gui_elements.sliders import all_sliders
from hardware.hardware import all_processors, all_ui_devices
from utils import backend_server_ok, log, set_ntp

BUTTON_EVENTS = ["Pressed", "Held", "Repeated", "Tapped"]


def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return None


config = load_json("config.json")


class PortInstantiation:
    """
    Instantiates all ports defined in ports.json

    Use port_instantiation_helper.py make the JSON file
    """

    def __init__(self):
        self.port_definitions = load_json("ports.json")
        self.all_relays = []
        self.all_serial_interfaces = []
        self.all_ethernet_interfaces = []
        self.instantiate_ports()

    def instantiate_ports(self):
        if not self.port_definitions:
            return
        for port_definition in self.port_definitions:
            port_class = port_definition["Class"]
            if port_class == "RelayInterfaceEx":
                self.instantiate_relays(port_definition)
            elif port_class == "SerialInterfaceEx":
                self.instantiate_serial_interface(port_definition)
            elif port_class == "EthernetClientInterfaceEx":
                self.instantiate_ethernet_client_interface(port_definition)
            else:
                log("Unknown Port Definition Class: {}".format(port_class), "error")

    def instantiate_relays(self, port_definition):
        host = PROCESSORS_MAP.get(port_definition["Host"], None)
        if not host:
            log(
                "Host Processor for relay port not found: {}".format(
                    port_definition["Host"]
                ),
                "error",
            )
            return
        port = port_definition["Port"]
        alias = port_definition["Alias"]
        self.all_relays.append(RelayInterfaceEx(host, port, alias=alias))

    def instantiate_serial_interface(self, port_definition):
        host = PROCESSORS_MAP.get(port_definition["Host"], None)
        if not host:
            log(
                "Host Processor for relay port not found: {}".format(
                    port_definition["Host"]
                ),
                "error",
            )
            return
        port = port_definition["Port"]
        baud = int(port_definition["Baud"])
        data = int(port_definition["Data"])
        stop = int(port_definition["Stop"])
        char_delay = int(port_definition["CharDelay"])
        parity = port_definition["Parity"]
        flow_control = port_definition["FlowControl"]
        mode = port_definition["Mode"]
        alias = port_definition["Alias"]
        self.all_serial_interfaces.append(
            SerialInterfaceEx(
                host,
                port,
                Baud=baud,
                Data=data,
                Parity=parity,
                Stop=stop,
                FlowControl=flow_control,
                CharDelay=char_delay,
                Mode=mode,
                alias=alias,
            )
        )

    def instantiate_ethernet_client_interface(self, port_definition):
        host = port_definition["Hostname"]
        ip_port = int(port_definition["IPPort"])
        protocol = port_definition["Protocol"]
        alias = port_definition["Alias"]

        if protocol == "TCP":
            self.all_ethernet_interfaces.append(
                EthernetClientInterfaceEx(host, ip_port, Protocol=protocol, alias=alias)
            )
        elif protocol == "UDP":
            service_port = port_definition["ServicePort"]
            buffer_size = port_definition["bufferSize"]
            self.all_ethernet_interfaces.append(
                EthernetClientInterfaceEx(
                    host,
                    ip_port,
                    Protocol=protocol,
                    ServicePort=int(service_port),
                    bufferSize=int(buffer_size),
                    alias=alias,
                )
            )
        elif protocol == "SSH":
            username = port_definition["Username"]
            password = port_definition["Password"]
            credentials = (username, password)
            self.all_ethernet_interfaces.append(
                EthernetClientInterfaceEx(
                    host,
                    ip_port,
                    Protocol=protocol,
                    Credentials=credentials,
                    alias=alias,
                )
            )


def make_str_obj_map(element_list):
    """Creates a dictionary using objects as values and their string names as keys"""
    # GUI Object: Name = "Name"
    # UI Devices (touch panels) and Processors: Name = DeviceAlias
    # Ports and Devices: Name = "alias"
    # PopupPageValidator: Name = "ui_device_name"
    attributes_to_try = [
        "Name",
        "DeviceAlias",
        "alias",
        "ui_device_name",
    ]

    for attr in attributes_to_try:
        try:
            return {str(getattr(element, attr)): element for element in element_list}
        except AttributeError:
            continue
        except Exception as e:
            log("Error creating string:object dict: {}".format(str(e)), "error")
            return {}

    log(
        "None of the attributes {} found in {}".format(attributes_to_try, attr), "error"
    )
    return {}


class PopupPageValidator:
    """
    Ensures popup and page names are valid for a given UI device

    Needed because ShowPopup and ShowPage methods do not return errors
    """

    def __init__(self, ui_device):
        self.ui_device = ui_device
        self.ui_device_name = ui_device.DeviceAlias
        self.valid_popups = getattr(self.ui_device, "_popups")
        self.valid_pages = getattr(self.ui_device, "_pages")

    def _is_valid_popup_integer(self, popup):
        try:
            popup_int = int(popup)
        except ValueError as e:
            # Not an integer
            return False
        if popup_int == 65535:
            raise ValueError("Invalid popup: 'Offline Page' can not be called")
        if popup_int in self.valid_popups.keys():
            return True
        raise ValueError("Invalid popup integer: {}".format(popup))

    def _is_valid_popup_string(self, popup_str):
        if popup_str == "Offline Page":
            raise ValueError("Invalid popup: 'Offline Page' can not be called")
        for value in self.valid_popups.values():
            for sub_key in value:
                if sub_key == "name" and value[sub_key] == popup_str:
                    return True
        raise ValueError("Invalid popup string: {}".format(popup_str))

    def _is_valid_page_integer(self, page):
        try:
            page_int = int(page)
        except ValueError as e:
            # Not an integer
            return False
        if page_int in self.valid_pages.keys():
            return True
        raise ValueError("Invalid page integer: {}".format(page))

    def _is_valid_page_string(self, page_str):
        if page_str in self.valid_pages.values():
            return True
        return False

    def validated_popup_call(self, popup):
        """
        Returns the proper way to call the popup
        if the popup is valid, otherwise returns None
        """
        if self._is_valid_popup_integer(popup):
            return int(popup)
        elif self._is_valid_popup_string(popup):
            return popup
        else:
            return None

    def validated_page_call(self, page):
        """
        Returns the proper way to call the page
        if the page is valid, otherwise returns None
        """
        if self._is_valid_page_integer(page):
            return int(page)
        elif self._is_valid_page_string(page):
            return page
        else:
            return None


class PopupPageValidatorFactory:
    @staticmethod
    def create(ui_devices):
        validators = []
        for ui_device in ui_devices:
            validators.append(PopupPageValidator(ui_device))
        return validators


all_popup_page_validators = PopupPageValidatorFactory.create(all_ui_devices)


# Key: string name, Value: object
## Standard Extron Classes ##
PROCESSORS_MAP = make_str_obj_map(all_processors)
UI_DEVICE_MAP = make_str_obj_map(all_ui_devices)
BUTTONS_MAP = make_str_obj_map(all_buttons)
KNOBS_MAP = make_str_obj_map(all_knobs)
LEVELS_MAP = make_str_obj_map(all_levels)
SLIDERS_MAP = make_str_obj_map(all_sliders)
LABELS_MAP = make_str_obj_map(all_labels)

## Ports ##
ports = PortInstantiation()
RELAYS_MAP = make_str_obj_map(ports.all_relays)
SERIAL_INTERFACE_MAP = make_str_obj_map(ports.all_serial_interfaces)
ETHERNET_INTERFACE_MAP = make_str_obj_map(ports.all_ethernet_interfaces)

## Custom Classes ##
ALL_POPUP_PAGE_VALIDATORS = make_str_obj_map(all_popup_page_validators)

####

DOMAIN_CLASS_MAP = {
    ## Standard Extron Classes ##
    "ProcessorDevice": PROCESSORS_MAP,
    "UIDevice": UI_DEVICE_MAP,
    "Button": BUTTONS_MAP,
    "Knob": KNOBS_MAP,
    "Label": LABELS_MAP,
    "Level": LEVELS_MAP,
    "Slider": SLIDERS_MAP,
    "RelayInterface": RELAYS_MAP,
    "SerialInterface": SERIAL_INTERFACE_MAP,
    "EthernetClientInterface": ETHERNET_INTERFACE_MAP,
}


def string_to_bool(string):
    """Interperts RPC string values received as boolean"""
    if string.lower() in ["true", "1", "t", "y", "yes"]:
        return True
    elif string.lower() in ["false", "0", "f", "n", "no"]:
        return False
    else:
        log("Invalid boolean value: {}".format(string), "error")
        return None


def string_to_int(string):
    """
    Interperts RPC string values received as integers.
    Supports hardware interface string syntax.
    """
    if string in ["0", "1", "2"]:
        return int(string)
    else:
        string = string.lower()
        if string in ["close", "on"]:
            return 1
        elif string in ["open", "off"]:
            return 0


#### Externally callable functions ####


## Standard Extron Methods ##
def set_state(obj, state):
    obj.SetState(string_to_int(state))


def set_fill(obj, fill):
    obj.SetFill(int(fill))


def set_text(obj, text):
    obj.SetText(text)


def set_visible(obj, visible):
    obj.SetVisible(string_to_bool(visible))


def set_blinking(obj, rate, state_list):
    state_list = state_list.replace("[", "").replace("]", "").split(",")
    state_list = [int(state) for state in state_list]
    obj.SetBlinking(rate, state_list)


def set_enable(obj, enabled):
    obj.SetEnable(string_to_bool(enabled))


def show_popup(ui_device, popup, duration=None):
    validator, err = get_object(ui_device.DeviceAlias, ALL_POPUP_PAGE_VALIDATORS)
    if err is not None:
        raise Exception(err)

    popup_call = validator.validated_popup_call(popup)
    if popup_call is None:
        raise ValueError("Invalid popup: {}".format(popup))

    if duration is None:
        ui_device.ShowPopup(popup_call)  # Default indefinite popup
    else:
        ui_device.ShowPopup(popup_call, int(duration))


def hide_all_popups(ui_device):
    ui_device.HideAllPopups()


def show_page(ui_device, page):
    validator, err = get_object(ui_device.DeviceAlias, ALL_POPUP_PAGE_VALIDATORS)
    if err is not None:
        raise Exception(err)
    page_call = validator.validated_page_call(page)
    if page_call is None:
        raise ValueError("Invalid page: {}".format(page))
    ui_device.ShowPage(page_call)


def get_volume(obj, name):
    return obj.GetVolume(name)


def play_sound(obj, filename):
    obj.PlaySound(filename)


def set_led_blinking(obj, ledid, rate, state_list):
    state_list = state_list.replace("[", "").replace("]", "").split(",")
    state_list = [state.strip() for state in state_list]
    obj.SetLEDBlinking(int(ledid), rate, state_list)


def set_led_state(obj, ledid, state):
    obj.SetLEDState(int(ledid), state)


def set_level(obj, level):
    obj.SetLevel(int(level))


def set_range(obj, min, max, step=1):
    obj.SetRange(int(min), int(max), int(step))


def inc(obj):
    obj.Inc()


def dec(obj):
    obj.Dec()


def pulse(obj, duration):
    obj.Pulse(float(duration))


def toggle(obj):
    obj.Toggle()


def send(obj, data):
    obj.Send(data)


def send_and_wait(obj, data, timeout):
    return obj.SendAndWait(data, float(timeout))


def reboot(obj):
    log("Rebooting {}".format(str(obj)), "warning")
    obj.Reboot()


def set_executive_mode(obj, mode):
    obj.SetExecutiveMode(string_to_int(mode))


def connect(obj, timeout=None):
    if timeout is None:
        return obj.Connect()
    else:
        return obj.Connect(float(timeout))


def disconnect(obj):
    obj.Disconnect()


def start_keepalive(obj, interval, data):
    obj.StartKeepAlive(float(interval), data)


def stop_keepalive(obj):
    obj.StopKeepAlive()


def save_program_log(obj, filepath):
    # Saving is always done to the primary processor storage,
    # so therefore object is not used, but kept for convention.
    with open(filepath, "w") as f:
        SaveProgramLog(f)


## Custom Methods ##


def get_property_(obj, property):
    try:
        attribute = getattr(obj, property)
        return attribute
    except AttributeError as e:
        log("GetProperty Attribute Error: {}".format(str(e)), "error")
        return e
    except Exception as e:
        log("GetProperty bare exception: {}".format(str(e)), "error")
        return e


# TODO: Add more methods as needed

#### Macros ####


def get_all_elements_():
    """Called through RPC by sending {"type": "get_all_elements"}"""
    data = {
        "all_processors": list(PROCESSORS_MAP.keys()),
        "all_ui_devices": list(UI_DEVICE_MAP.keys()),
        "all_buttons": list(BUTTONS_MAP.keys()),
        "all_knobs": list(KNOBS_MAP.keys()),
        "all_labels": list(LABELS_MAP.keys()),
        "all_levels": list(LEVELS_MAP.keys()),
        "all_sliders": list(SLIDERS_MAP.keys()),
        "all_relays": list(RELAYS_MAP.keys()),
        "all_serial_interfaces": list(SERIAL_INTERFACE_MAP.keys()),
        "all_ethernet_interfaces": str(ETHERNET_INTERFACE_MAP),
        "backend_server_available": v.backend_server_available,
        "backend_server_role": v.backend_server_role,
        "backend_server_ip": v.backend_server_ip,
    }
    return data


def set_backend_server_(ip=None):
    """
    Call example: {"type": "set_backend_server", "ip": "http://10.0.0.1:8080"}

    If no IP is provided, the function will try servers in the config.json file.
    """

    def _set_server(role, ip, message, log_level):
        v.backend_server_available = True
        v.backend_server_role = role
        v.backend_server_ip = ip
        log(message, log_level)

    def _no_server(message):
        v.backend_server_available = False
        v.backend_server_role = "none"
        v.backend_server_ip = None
        log(message, "error")

    if ip:  # Custom IP specified
        if backend_server_ok(ip):
            _set_server(
                "custom", ip, "Using custom backend server: {}".format(ip), "warning"
            )
            return "200 OK | Custom IP"
        else:
            err = "Custom backend server {} is not available".format(ip)
            _no_server(err)
            return "502 Bad Gateway | {}".format(err)

    # Try primary from the config
    if backend_server_ok(config["primary_backend_server_ip"]):
        _set_server(
            "primary",
            config["primary_backend_server_ip"],
            "Using primary backend server",
            "info",
        )
        return "200 OK | Primary Server Selected"
    # Try secondary from the config
    elif backend_server_ok(config["secondary_backend_server_ip"]):
        _set_server(
            "secondary",
            config["secondary_backend_server_ip"],
            "Using secondary backend server",
            "warning",
        )
        return "200 OK | Secondary Server Selected"
    else:
        _no_server("No backend servers available")
        return "502 Bad Gateway | No backend servers available"


METHODS_MAP = {
    # All 'methods' take "type", "object", "function" as required arguments
    # and "arg1", "arg2", "arg3" as optional arguments.
    # This is different from 'macros' which can have custom call formats
    "SetState": set_state,
    "SetFill": set_fill,
    "SetText": set_text,
    "SetVisible": set_visible,
    "SetBlinking": set_blinking,
    "SetEnable": set_enable,
    "ShowPopup": show_popup,
    "HideAllPopups": hide_all_popups,
    "ShowPage": show_page,
    "GetVolume": get_volume,
    "PlaySound": play_sound,
    "SetLEDBlinking": set_led_blinking,
    "SetLEDState": set_led_state,
    "SetLevel": set_level,
    "SetRange": set_range,
    "Inc": inc,
    "Dec": dec,
    "Pulse": pulse,
    "Toggle": toggle,
    "Send": send,
    "SendAndWait": send_and_wait,
    "SetExecutiveMode": set_executive_mode,
    "Reboot": reboot,
    "Connect": connect,
    "Disconnect": disconnect,
    "StartKeepAlive": start_keepalive,
    "StopKeepAlive": stop_keepalive,
    "SaveProgramLog": save_program_log,
    "get_property": get_property_,
}

MACROS_MAP = {
    "get_all_elements": get_all_elements_,
    "set_backend_server": set_backend_server_,
}

#### User interaction events ####


@event(all_buttons, BUTTON_EVENTS)
def any_button_event(button, action):
    button_data = ("button", str(button.Name), action, str(button.State))
    send_user_interaction(button_data)


@event(all_sliders, "Changed")
def any_slider_changed(slider, action, value):
    slider_data = ("slider", str(slider.Name), action, str(value))
    send_user_interaction(slider_data)


# TODO: Knob events


#### Internal Functions ####


def send_client_error(client, code, description):
    if code == "400":
        prefix = "400 Bad Request"
    else:
        prefix = ""

    formatted = "{} | {}".format(prefix, description)
    log(formatted, "error")
    if client:
        client.Send(formatted.encode("utf-8"))
        client.Disconnect()


def get_object(string_key, object_map):
    """
    Pass in string representing an object and the dictionary map of the object domain,
    returns a tuple golang style (object, error).
    """
    try:
        return (object_map[string_key], None)
    except KeyError:
        err = "400 Bad Request | Object not found: {}".format(string_key)
        log(err, "error")
        return None, err
    except Exception as e:
        err = "400 Bad Request | GetObject bare exception: {}".format(str(e))
        log(err, "error")
        return None, err


def method_call_handler(data):
    """
    Executes functions (different from "Macros"),
    returns tuple golang style (data, error)
    """
    try:
        # Required
        type_str = data["type"]
        object_str = data["object"]
        function_str = data["function"]

        # Optional
        arg1 = data.get("arg1", None)
        arg2 = data.get("arg2", None)
        arg3 = data.get("arg3", None)

        object_type_map = DOMAIN_CLASS_MAP[type_str]
        obj, err = get_object(object_str, object_type_map)
        if err != None:
            return (None, err)

        func = METHODS_MAP[function_str]
        args = [arg for arg in [arg1, arg2, arg3] if arg not in ["", None]]
        result = func(obj, *args)
        if result is None:
            return ("200 OK", None)
        return ("200 OK | {}".format(str(result)), None)
    except KeyError as e:
        err = "400 Bad Request | Key Error: {}".format(str(e))
        log(str(err), "error")
        return None, err
    except ValueError as e:
        err = "400 Bad Request | Value Error: {}".format(str(e))
        log(str(err), "error")
        return None, err
    except Exception as e:
        err = "400 Bad Request | Function Error: {}".format(str(e))
        log(str(err), "error")
        return None, err


def macro_call_handler(command_type, data_dict=None):
    """
    Executes Macros (different from "Functions"),
    returns tuple golang style (data, error)
    """
    if command_type == "get_all_elements":
        try:
            data = get_all_elements_()
            data = json.dumps(data).encode()
            return (data, None)
        except Exception as e:
            return (None, e)

    elif command_type == "set_backend_server":
        try:
            ip = data_dict.get("ip", None)
            result = set_backend_server_(ip)
            return (result, None)
        except Exception as e:
            return (None, e)
    else:
        return (None, "Macro: {} Not Found".format(command_type))


class RxDataReplyProcessor:

    def __init__(self, json_data, client):
        self.json_data = json_data
        # client is only present when function is called from RPC server
        # No replies sent when invoked as a REST API reply processor
        self.client = client
        self.valid_json = self._validate_json()

        self.successes = 0
        self.errors = 0
        self.ordered_reply = []

    def _validate_json(self):
        try:
            data = json.loads(self.json_data)
        except (json.JSONDecodeError, KeyError) as e:
            send_client_error(
                self.client, "400", "Error decoding JSON: {}".format(str(e))
            )
            return None

        # Make compatible with list processing
        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            send_client_error(
                self.client,
                "400",
                "Data type must be interpreted as list or dict. Found {}".format(
                    type(data)
                ),
            )
            return None
        return data

    def _cache_result(self, success: bool, result):
        if success:
            self.successes += 1
        else:
            self.errors += 1
        self.ordered_reply.append(result)

    def process_and_send(self):
        if not self.valid_json:
            raise json.JSONDecodeError

        for command in self.valid_json:
            command_type = command["type"]
            if command_type in DOMAIN_CLASS_MAP.keys():
                result, err = method_call_handler(command)
                if err is not None:
                    self._cache_result(False, err)
                else:
                    self._cache_result(True, result)
                continue

            elif command_type in MACROS_MAP.keys():
                if not self.client:
                    raise Exception("Macro command called without client")
                result, err = macro_call_handler(command_type, command)
                success = False if err is not None else True
                self._cache_result(success, result)
                continue

            else:
                self.ordered_reply.append(
                    "400 Bad Request | Unknown Action: {}".format(str(command_type))
                )
        response = json.dumps(self.ordered_reply).encode("utf-8")
        self.client.Send(response)


def handle_backend_server_timeout():
    v.backend_server_timeout_count += 1
    log(
        "Backend Server Timed Out Count: {}".format(v.backend_server_timeout_count),
        "error",
    )


def format_user_interaction_data(gui_element_data):
    if v.backend_server_available != True:
        return None

    domain = gui_element_data[0]
    data = {
        "name": gui_element_data[1],
        "action": gui_element_data[2],
        "value": gui_element_data[3],
    }

    data = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    url = "{}/api/v1/{}".format(v.backend_server_ip, domain)
    user_data_req = urllib.request.Request(
        url, data=data, headers=headers, method="PUT"
    )
    return user_data_req


def send_to_backend_server(user_data_req):
    if not user_data_req:
        log("No backend server set. Cannot send data", "error")
        return

    @Wait(0)
    def _send_to_backend_server():
        try:
            with urllib.request.urlopen(
                user_data_req, timeout=int(config["backend_server_timeout"])
            ) as response:
                response_data = response.read().decode()
                reply_processor = RxDataReplyProcessor(response_data, None)
                reply_processor.process_and_send()

        # Timeout
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower():
                handle_backend_server_timeout()
            else:
                log("URLError: {}".format(str(e)), "error")
                return

        except Exception as e:
            log("Bare Exception for send_to_backend_server: {}".format(str(e)), "error")
            return

        v.backend_server_timeout_count = 0


def send_user_interaction(gui_element_data):
    user_data_req = format_user_interaction_data(gui_element_data)
    send_to_backend_server(user_data_req)


#### RPC Server ####

rpc_serv = EthernetServerInterfaceEx(
    IPPort=int(config["rpc_server_port"]),
    Protocol="TCP",
    Interface=config["rpc_server_interface"],
)

if rpc_serv.StartListen() != "Listening":
    raise ResourceWarning("Port unavailable")  # this is not likely to recover


@event(rpc_serv, "ReceiveData")
def handle_unsolicited_rpc_rx(client, data):
    try:
        data_str = data.decode()

        # Extract the body from the HTTP request
        parts = data_str.split("\r\n\r\n", 1)
        if len(parts) > 1:
            body = parts[1]
        else:
            body = ""
    except json.JSONDecodeError as e:
        err = "400 Bad Request | JSON Decode Error on RPC Rx: {}".format(str(e))
        log(err, "error")
    except Exception as e:
        err = "Bare Exception in RPC Rx: {}".format(str(e))
        log(err, "error")
    finally:
        if body:
            reply_processor = RxDataReplyProcessor(body, client)
            reply_processor.process_and_send()
        else:
            if err:
                send_client_error(client, "400", err)
        client.Disconnect()


@event(rpc_serv, "Connected")
def handle_rpc_client_connect(client, state):
    # you can use 'client.IPAddress' to implement IP filtering
    # to only allow authorized clients or subnets to connect
    pass


class Initialize:
    @Wait(0)
    def _set_ntp():
        set_ntp(config["ntp_primary"], config["ntp_secondary"])
        log("NTP Complete (success or failure)", "info")

    @Wait(0)
    def _set_backend_server():
        set_backend_server_()  # Using addresses from config.json
        log("Backend Server Connection Complete (success or timeout)", "info")


Initialize()
