import json
import urllib.error
import urllib.request

from extronlib import event
from extronlib.interface import EthernetServerInterfaceEx
from extronlib.system import File as open
from extronlib.system import Timer, Wait

from gui_elements.buttons import all_buttons
from gui_elements.knobs import all_knobs
from gui_elements.labels import all_labels
from gui_elements.levels import all_levels
from gui_elements.sliders import all_sliders
from hardware.hardware import all_processors, all_ui_devices
from hardware.relays import all_relays
from hardware.serial import all_serial_interfaces
from utils import log, set_ntp

with open("config.json", "r") as f:
    config = json.load(f)

BUTTON_EVENTS = ["Pressed", "Released", "Held", "Repeated", "Tapped"]


def make_str_obj_map(element_list):
    """Creates a dictionary using objects as values and their string names as keys"""
    # GUI objects have name properties
    # UI Devices (touch panels) and Processors have DeviceAlias properties
    # Hardware interfaces have Port properties
    attributes_to_try = ["Name", "DeviceAlias", "Port"]

    for attr in attributes_to_try:
        try:
            return {str(getattr(element, attr)): element for element in element_list}
        except AttributeError:
            continue
        except Exception as e:
            log(str(e), "error")
            return None

    log(
        "None of the attributes {} found in elements".format(attributes_to_try), "error"
    )
    return None


# Domain maps.  Key: string name, Value: object
PROCESSORS_MAP = make_str_obj_map(all_processors)
UI_DEVICE_MAP = make_str_obj_map(all_ui_devices)
BUTTONS_MAP = make_str_obj_map(all_buttons)
KNOBS_MAP = make_str_obj_map(all_knobs)
LEVELS_MAP = make_str_obj_map(all_levels)
SLIDERS_MAP = make_str_obj_map(all_sliders)
LABELS_MAP = make_str_obj_map(all_labels)
RELAYS_MAP = make_str_obj_map(all_relays)
SERIAL_INTERFACE_MAP = make_str_obj_map(all_serial_interfaces)


DOMAINS_MAP = {
    "processor_device": PROCESSORS_MAP,
    "ui_device": UI_DEVICE_MAP,
    "button": BUTTONS_MAP,
    "knob": KNOBS_MAP,
    "label": LABELS_MAP,
    "level": LEVELS_MAP,
    "slider": SLIDERS_MAP,
    "relay": RELAYS_MAP,
    "serial_interface": SERIAL_INTERFACE_MAP,
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


class PageStateMachine:
    """
    Extron libs do not have the ability to query
    all possible pages and popups, nor do they have properties
    that contain current visible pages and popups.
    We track state here and store all unique pages and popups called
    """

    def __init__(self, ui_device):
        self.ui_device = ui_device
        self.current_page = None
        self.current_popup = None  # includes modals

        # Collect all pages and popups that have been called,
        # to try and track all possibilities
        self.all_pages_called = []
        self.all_popups_called = []  # includes modals

    def _add_to_all(self, element, element_type_list):
        if element not in element_type_list:
            element_type_list.append(element)

    def hide_all_popups(self):
        self.current_modal = None
        self.current_popup = None

    def set_page(self, page):
        self.current_page = page
        self._add_to_all(page, self.all_pages_called)

    def show_popup(self, popup, duration=None):
        if duration is None:
            self.current_popup = popup
        else:
            pass
            # TODO: Set timer to clear self.current_popup after duration
        self._add_to_all(popup, self.all_popups_called)


PageState1 = PageStateMachine(all_ui_devices[0])
if len(all_ui_devices) > 1:
    PageState2 = PageStateMachine(all_ui_devices[1])
if len(all_ui_devices) > 2:
    PageState3 = PageStateMachine(all_ui_devices[2])
if len(all_ui_devices) > 3:
    PageState4 = PageStateMachine(all_ui_devices[3])

#### Externally callable functions ####


## Standard Extron Package Functions ##
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
    if duration is None:
        ui_device.ShowPopup(popup)  # Default indefinite popup
    else:
        ui_device.ShowPopup(popup, int(duration))
    if ui_device == all_ui_devices[0]:
        PageState1.show_popup(popup, duration)
    elif ui_device == all_ui_devices[1]:
        PageState2.show_popup(popup, duration)
    elif ui_device == all_ui_devices[2]:
        PageState3.show_popup(popup, duration)
    elif ui_device == all_ui_devices[3]:
        PageState4.show_popup(popup, duration)


def hide_all_popups(ui_device):
    ui_device.HideAllPopups()
    if ui_device == all_ui_devices[0]:
        PageState1.hide_all_popups()
    elif ui_device == all_ui_devices[1]:
        PageState2.hide_all_popups()
    elif ui_device == all_ui_devices[2]:
        PageState3.hide_all_popups()
    elif ui_device == all_ui_devices[3]:
        PageState4.hide_all_popups()


def show_page(ui_device, page):
    ui_device.ShowPage(page)
    if ui_device == all_ui_devices[0]:
        PageState1.set_page(page)
    elif ui_device == all_ui_devices[1]:
        PageState2.set_page(page)
    elif ui_device == all_ui_devices[2]:
        PageState3.set_page(page)
    elif ui_device == all_ui_devices[3]:
        PageState4.set_page(page)


def set_level(obj, level):
    obj.SetLevel(int(level))


def set_range(obj, min, max, step=1):
    obj.SetRange(int(min), int(max), int(step))


def pulse(obj, duration):
    obj.Pulse(float(duration))


def toggle(obj):
    obj.Toggle()


def send(obj, data):
    obj.Send(data)


def send_and_wait(obj, data, timeout):
    return obj.SendAndWait(data, float(timeout))


def reboot(obj):
    obj.Reboot()


def set_executive_mode(obj, mode):
    obj.SetExecutiveMode(string_to_int(mode))


def get_property(obj, property):
    try:
        attribute = getattr(obj, property)
        return attribute
    except AttributeError as e:
        log(str(e), "error")
        return e
    except Exception as e:
        log(str(e), "error")
        return e


# TODO: Add more functions as needed

#### Macro Functions ####


def get_all_elements():
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
        "current_page_ui_device1": PageState1.current_page,
        "current_popup_ui_device_1": PageState1.current_popup,
        "all_pages_called_ui_device_1": PageState1.all_pages_called,
        "all_popups_called_ui_device_1": PageState1.all_popups_called,
    }
    return data


# TODO: Timer / Level functions

FUNCTIONS_MAP = {
    "SetState": set_state,
    "SetFill": set_fill,
    "SetText": set_text,
    "SetVisible": set_visible,
    "SetBlinking": set_blinking,
    "SetEnable": set_enable,
    "ShowPopup": show_popup,
    "HideAllPopups": hide_all_popups,
    "ShowPage": show_page,
    "SetLevel": set_level,
    "SetRange": set_range,
    "Pulse": pulse,
    "Toggle": toggle,
    "GetProperty": get_property,
    "Send": send,
    "SendAndWait": send_and_wait,
    "SetExecutiveMode": set_executive_mode,
    "Reboot": reboot,
}

#### User interaction events ####


@event(all_buttons, BUTTON_EVENTS)
def any_button_pressed(button, action):
    button_data = ("button", str(button.Name), action, str(button.State))
    send_user_interaction(button_data)


@event(all_sliders, "Released")
def any_slider_released(slider, action, value):
    slider_data = ("slider", str(slider.Name), action, str(value))
    send_user_interaction(slider_data)


# TODO: Knob events
# TODO: Property Handlers (ex: Changed, Connected)


#### Internal Functions ####


def get_object(string_key, object_map):
    """
    Pass in string representing an object and the dictionary map of the object domain,
    returns the object
    """
    try:
        return object_map[string_key]
    except KeyError:
        log("{} not in {}".format(string_key, object_map), "error")
        log("Valid options for map are: {}".format(object_map.keys()), "info")
        return None
    except Exception as e:
        log(str(e), "error")
        log("Valid options for map are: {}".format(object_map.keys()), "info")
        return None


def function_call_handler(data):
    try:
        # Required
        type_str = data["type"]
        object_str = data["object"]
        function_str = data["function"]

        # Optional
        arg1 = data.get("arg1", None)
        arg2 = data.get("arg2", None)
        arg3 = data.get("arg3", None)

        object_type_map = DOMAINS_MAP[type_str]
        obj = get_object(object_str, object_type_map)
        func = FUNCTIONS_MAP[function_str]
        args = [arg for arg in [arg1, arg2, arg3] if arg not in ["", None]]
        result = func(obj, *args)
        if result == None:
            return "OK"
        return str(result)
    except Exception as e:
        error = "Function Error: {} | with data {}".format(str(e), str(data))
        log(str(error), "error")
        return str(error)


def process_rx_data_and_send_reply(json_data, client):
    # Client is only present when function is called from RPC server
    # Function does not send replies when invoked as a REST API reply processor
    try:
        data_dict = json.loads(json_data)
        command_type = data_dict["type"]

        if command_type in DOMAINS_MAP.keys():
            result = function_call_handler(data_dict)
            if client:
                client.Send(result)
            return

        elif command_type == "get_all_elements":
            if not client:
                return
            else:
                data = get_all_elements()
                data = json.dumps(data).encode()
                client.Send(data)
                return

        else:
            log("Unknown action: {}".format(command_type), "error")
            if client:
                client.Send(b"Unknown action\n")

    except (json.JSONDecodeError, KeyError) as e:
        log("Error processing JSON data: {}".format(str(e)), "error")
        if client:
            client.Send(b"Error processing JSON data\n")
    except Exception as e:
        log(str(e), "error")
        if client:
            client.Send(b"Error processing data : {}".format(str(e)))


def send_user_interaction(gui_element_data):
    domain = gui_element_data[0]
    data = {
        "name": gui_element_data[1],
        "action": gui_element_data[2],
        "value": gui_element_data[3],
    }

    data = json.dumps(data).encode()

    log("Sending data: {}".format(str(data)), "info")

    headers = {"Content-Type": "application/json"}
    url = "{}/api/v1/{}".format(config["backend_server_ip"], domain)
    log("URL: {}".format(url), "info")

    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(
            req, timeout=int(config["backend_server_timeout"])
        ) as response:
            response_data = response.read().decode()
            log(str(response_data), "info")
            process_rx_data_and_send_reply(response_data, None)

    except Exception as e:
        log(str(e), "error")
        print(e)


#### RPC Server ####

# TODO: IP allow list filteirng

rpc_serv = EthernetServerInterfaceEx(
    IPPort=int(config["rpc_server_port"]),
    Protocol="TCP",
    Interface=config["rpc_server_interface"],
)

if rpc_serv.StartListen() != "Listening":
    raise ResourceWarning("Port unavailable")  # this is not likely to recover


@event(rpc_serv, "ReceiveData")
def handle_unsolicited_rpc_rx(client, data):
    log("Rx: {}".format(data), "info")
    try:
        data_str = data.decode()

        # Extract the body from the HTTP request
        body = data_str.split("\r\n\r\n", 1)[1]

        if body:
            log(str(body), "info")
            process_rx_data_and_send_reply(body, client)
        else:
            log("No data received", "error")
    except json.JSONDecodeError as e:
        log(str(e), "error")
    except Exception as e:
        log(str(e), "error")


@event(rpc_serv, "Connected")
def handle_rpc_client_connect(client, state):
    log("Client connected ({}).".format(client.IPAddress), "info")
    # client.Send(b"Connected\n")
    # Log the state to see if any data is sent on connection
    log("Connection state: {}".format(state), "info")
    # TODO: Debug mode


@event(rpc_serv, "Disconnected")
def handle_rpc_client_disconnect(client, state):
    log("Server/Client {} disconnected.".format(client.IPAddress), "info")


def Initialize():
    # set_ntp(config["ntp_primary"], config["ntp_secondary"])
    log("Initialized", "info")


Initialize()
