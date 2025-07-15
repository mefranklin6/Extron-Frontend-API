import json
import urllib.error
import urllib.request
from time import sleep  # Only for intentionally blocking the main thread

from extronlib import event
from extronlib.interface import EthernetServerInterfaceEx
from extronlib.system import File as open
from extronlib.system import SaveProgramLog, Timer, Wait

import variables
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
from utils import (
    ProgramLogSaver,
    backend_server_ok,
    backend_server_ready_to_pair,
    log,
    set_ntp,
)

# "Released" is ommitted by default to increase performance,
# but it can be added to the list if needed.
BUTTON_EVENTS = ["Pressed", "Held", "Repeated", "Tapped"]


def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return None


config = load_json("config.json")
if not config:
    log("Config file not found", "error")
    raise FileNotFoundError("Config file not found")

log_to_disk = config.get("log_to_disk", False)
if log_to_disk:
    ProgramLogSaver.EnableProgramLogSaver()
    variables.program_log_saver = "Enabled"
    log("Enabling Program Log Saver", "info")

variables.backend_server_timeout = config.get("backend_server_timeout", 2)


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
        result = obj.Connect()
    else:
        result = obj.Connect(float(timeout))
    if "Connected" in result or "ConnectedAlready" in result:
        return result
    elif "Failed to connect" in result:
        raise ConnectionError(result)
    elif "Invalid credentials" in result:
        raise PermissionError(result)
    else:
        raise Exception(result)


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
        "backend_server_available": variables.backend_server_available,
        "backend_server_role": variables.backend_server_role,
        "backend_server_address": variables.backend_server_address,
    }
    return data


def set_backend_server_(address=None):
    """
    Call example: {"type": "set_backend_server", "address": "http://10.0.0.1:8080"}

    If no address is provided, the function will try servers in the config.json file.
    """

    def _set_server(role, address, message, log_level):
        if backend_server_ready_to_pair(address):
            backend_server_available_setter(True)
            variables.backend_server_role = role
            variables.backend_server_address = address
            log(message, log_level)
        else:
            log("Unhandled Pairing Exception with server {}".format(address), "error")

    def _no_server(message):
        backend_server_available_setter(False)
        variables.backend_server_role = "none"
        variables.backend_server_address = None
        log(message, "error")

    if address is not None and address != "":  # Custom address specified
        if backend_server_ok(address):
            _set_server(
                role="custom",
                address=address,
                message="Using custom backend server: {}".format(address),
                log_level="warning",
            )
            return "200 OK | Custom address"
        else:
            err = "Custom backend server {} is not available".format(address)
            _no_server(err)
            return "502 Bad Gateway | {}".format(err)

    # No custom address provided, check config.json
    server_list = config.get("backend_server_addresses", None)
    if not server_list:
        err = "No backend server addresses configured in config.json"
        _no_server(err)
        return "502 Bad Gateway | {}".format(err)

    log("Checking backend server addresses: {}".format(server_list), "info")
    available_servers = []
    variables.checked_servers = 0
    for address in server_list:

        # Spawn an asynchronous task to check each server
        # This avoids long waits if the server list is large and many are not available
        @Wait(0)
        def async_check_all_servers(addr=address):
            log("Checking backend server: {}".format(addr), "info")
            if backend_server_ok(addr):
                available_servers.append(addr)
            variables.checked_servers += 1

    while variables.checked_servers < len(server_list):
        sleep(0.1)  # Block main thread until all servers are checked

    log("Available backend servers: {}".format(available_servers), "info")
    if config["backend_server_addresses"][0] in available_servers:
        # Give priority to the first server in the config list
        _set_server(
            role="primary",
            address=config["backend_server_addresses"][0],
            message="Using primary backend server: {}".format(
                config["backend_server_addresses"][0]
            ),
            log_level="info",
        )
        return "200 OK | Primary Server Selected"
    elif len(available_servers) > 0:
        # First server in config is not available but other(s) are
        # Use the first available server
        _set_server(
            role="secondary",
            address=available_servers[0],
            message="First backend server not available, using: {}".format(
                available_servers[0]
            ),
            log_level="warning",
        )
        return "200 OK | Secondary Server Selected"

    _no_server("No backend servers available")
    return "502 Bad Gateway | No backend servers available"


def program_log_saver_enable_disable(enabled: bool):
    if string_to_bool(enabled):
        if variables.program_log_saver == "Enabled":
            return "200 OK | Program Log Saver is already enabled"
        ProgramLogSaver.EnableProgramLogSaver()
        variables.program_log_saver = "Enabled"
        return "200 OK | Program Log will be continually saved to disk"
    else:
        if variables.program_log_saver == "Disabled":
            return "200 OK | Program Log Saver is already disabled"
        ProgramLogSaver.DisableProgramLogSaver()
        variables.program_log_saver = "Disabled"
        return "200 OK | Program Log will no longer save to disk"


def unpair_backend_server():
    """
    Call example: {"type": "unpair"}

    The processor will begin to search for a new server.

    Note: make sure before calling this, your server stops responsing to the test endpoint,
    or else the processor might pair to the same server again.
    """
    log("Backend Server called 'unpair', searching for new server", "warning")
    backend_server_available_setter(False)
    return "200 OK", None


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
    "program_log_saver": program_log_saver_enable_disable,
    "unpair": unpair_backend_server,
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


def backend_server_available_setter(status):
    if status == True:
        if variables.backend_server_available == False:
            variables.backend_server_available = True
            server_check_loop("start")
            log("Backend Server Available", "info")
            offline_popup = config.get("backend_server_offline_gui_popup", None)
            if offline_popup:
                for ui_device in list(UI_DEVICE_MAP.values()):
                    ui_device.HidePopup(offline_popup)
    else:  # Status: False
        if variables.backend_server_available == True:
            variables.backend_server_available = False
            server_check_loop("stop")
            log("Backend Server Unavailable", "error")
            set_backend_server_loop()
            offline_popup = config.get("backend_server_offline_gui_popup", None)
            if offline_popup:
                for ui_device in list(UI_DEVICE_MAP.values()):
                    ui_device.ShowPopup(offline_popup)


def server_check_loop(start_or_stop):
    if start_or_stop == "start":
        if not variables.server_check_timer:
            variables.server_check_timer = Timer(
                config.get("check_backend_server_interval", 5), server_check_callback
            )
        else:
            variables.server_check_timer.Restart()
    else:
        variables.server_check_timer.Stop()


def server_check_callback(_, __):
    if backend_server_ok(variables.backend_server_address):
        return
    else:
        handle_backend_server_timeout()


def set_backend_server_loop():
    """
    Will try all servers listed in config.json continually,
    until one is available
    """
    if variables.backend_server_available:
        return

    def _timer_callback(timer, _):
        if variables.backend_server_available:
            timer.Stop()
            return
        else:
            set_backend_server_()
            timer.Restart()

    timer = Timer(config.get("server_search_interval", 2), _timer_callback)


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
    except ConnectionError as e:
        err = "503 Service Unavailable | Connection Error: {}".format(str(e))
        log(str(err), "error")
        return None, err
    except PermissionError as e:
        err = "403 Forbidden | Permission Error: {}".format(str(e))
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
    # Dictionary of handler functions for each command type
    handlers = {
        "get_all_elements": lambda: (MACROS_MAP["get_all_elements"](), None),
        "set_backend_server": lambda: (
            MACROS_MAP["set_backend_server"](data_dict.get("address", None)),
            None,
        ),
        "program_log_saver": lambda: (
            MACROS_MAP["program_log_saver"](data_dict["enabled"]),
            None,
        ),
        "unpair": lambda: (MACROS_MAP["unpair"](), None),
    }

    if command_type not in handlers:
        return (None, "Macro: {} Not Found".format(command_type))

    try:
        return handlers[command_type]()
    except Exception as e:
        return (None, e)


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
            command_type = command.get("type", None)
            if not command_type:
                self._cache_result(
                    False, "400 Bad Request | Missing required key 'type'"
                )
                continue
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
        if response is not None and self.client is not None:
            self.client.Send(response)


def handle_backend_server_timeout():
    if not variables.backend_server_available:
        return

    if variables.backend_server_timeout_count == 2:
        log(
            "Backend Server Timed Out 3 times, begining search for new server",
            "error",
        )
        backend_server_available_setter(False)
        return

    variables.backend_server_timeout_count += 1
    log(
        "Backend Server Timed Out Count: {}".format(
            variables.backend_server_timeout_count
        ),
        "error",
    )


def format_user_interaction_data(gui_element_data):
    if variables.backend_server_available != True:
        return None

    domain = gui_element_data[0]
    data = {
        "name": gui_element_data[1],
        "action": gui_element_data[2],
        "value": gui_element_data[3],
    }

    data = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    url = "{}/api/v1/{}".format(variables.backend_server_address, domain)
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
                user_data_req, timeout=int(config.get("backend_server_timeout", 2))
            ) as response:
                response_data = response.read().decode()
                # No commands received, just an acknowledgment
                if response_data == "ACK":
                    variables.backend_server_timeout_count = 0
                    return
                # Server has commands in its response
                reply_processor = RxDataReplyProcessor(response_data, None)
                reply_processor.process_and_send()
                variables.backend_server_timeout_count = 0
                return

        # Timeout
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower():
                handle_backend_server_timeout()
            else:
                log("URLError: {}".format(str(e)), "error")

        except Exception as e:
            log("Bare Exception for send_to_backend_server: {}".format(str(e)), "error")


def send_user_interaction(gui_element_data):
    user_data_req = format_user_interaction_data(gui_element_data)
    send_to_backend_server(user_data_req)


#### RPC Server (Listening) ####

rpc_serv = EthernetServerInterfaceEx(
    IPPort=int(config["rpc_server_port"]),
    Protocol="TCP",
    Interface=config["rpc_server_interface"],
)

if rpc_serv.StartListen() != "Listening":
    raise ResourceWarning("Port unavailable")  # this will not recover


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


def initialize():
    @Wait(0)
    def _set_ntp_async():
        set_ntp(
            config.get("ntp_primary", "pool.ntp.org"),
            config.get("ntp_secondary", None),
        )
        log("NTP Complete (success or failure)", "info")

    set_backend_server_loop()


initialize()
