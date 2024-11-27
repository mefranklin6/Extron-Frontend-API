"""Early version of replacing the Extron Control Script Backend"""

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
from gui_elements.popups import all_modals, all_popups
from gui_elements.sliders import all_sliders
from hardware.hardware import all_processors, all_touch_panels
from hardware.relays import all_relays
from hardware.serial import all_serial_interfaces
from utils import log, set_ntp

with open("config.json", "r") as f:
    config = json.load(f)


def make_str_obj_map(element_list):
    """Creates a dictionary using objects as values and their string names as keys"""
    # GUI objects have name properties
    # Touch Panels and Processors have DeviceAlias properties
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
TOUCH_PANELS_MAP = make_str_obj_map(all_touch_panels)
BUTTONS_MAP = make_str_obj_map(all_buttons)
KNOBS_MAP = make_str_obj_map(all_knobs)
LEVELS_MAP = make_str_obj_map(all_levels)
SLIDERS_MAP = make_str_obj_map(all_sliders)
LABELS_MAP = make_str_obj_map(all_labels)
RELAYS_MAP = make_str_obj_map(all_relays)
SERIAL_INTERFACE_MAP = make_str_obj_map(all_serial_interfaces)

# Popup/modal pages are already called using their string names,
# so a simple list is sufficient
POPUPS = all_popups + all_modals

DOMAINS_MAP = {
    "processor": PROCESSORS_MAP,
    "touch_panel": TOUCH_PANELS_MAP,
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


def set_enabled(obj, enabled):
    obj.SetEnabled(string_to_bool(enabled))


def show_popup(touch_panel, popup, duration=None):
    if duration is None:
        touch_panel.ShowPopup(popup)  # Default indefinite popup
        return
    touch_panel.ShowPopup(popup, int(duration))


def hide_all_popups(touch_panel):
    touch_panel.HideAllPopups()


def show_page(touch_panel, page):
    touch_panel.ShowPage(page)


def set_level(obj, level):
    obj.SetLevel(int(level))


def set_range(obj, min, max, step=1):
    obj.SetRange(int(min), int(max), int(step))


def pulse(obj, duration):
    obj.Pulse(float(duration))


def toggle(obj):
    obj.Toggle()


def send_and_wait(obj, data, timeout):
    return obj.SendAndWait(data, float(timeout))


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


# TODO: The rest of the extronlib ui functions, or at least the most common ones

#### Macro Functions ####


def get_all_elements():
    """Called through RPC by sending {"type": "get_all_elements"}"""
    data = {
        "all_processors": list(PROCESSORS_MAP.keys()),
        "all_touch_panels": list(TOUCH_PANELS_MAP.keys()),
        "all_buttons": list(BUTTONS_MAP.keys()),
        "all_knobs": list(KNOBS_MAP.keys()),
        "all_labels": list(LABELS_MAP.keys()),
        "all_levels": list(LEVELS_MAP.keys()),
        "all_sliders": list(SLIDERS_MAP.keys()),
        "all_modals": all_modals,
        "all_popups": all_popups,
    }
    return data


# TODO: Timer / Level functions

FUNCTIONS_MAP = {
    "SetState": set_state,
    "SetFill": set_fill,
    "SetText": set_text,
    "SetVisible": set_visible,
    "SetBlinking": set_blinking,
    "SetEnabled": set_enabled,
    "ShowPopup": show_popup,
    "HideAllPopups": hide_all_popups,
    "ShowPage": show_page,
    "SetLevel": set_level,
    "SetRange": set_range,
    "Pulse": pulse,
    "Toggle": toggle,
    "GetProperty": get_property,
    "SendAndWait": send_and_wait,
}

#### User interaction events ####


@event(all_buttons, "Pressed")
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

        # TODO: Get states / Get all states

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
