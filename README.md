# Extron-Frontend-API

Externally control the frontend and hardware of a system running Extron Control Script

Not affiliated with Extron

## Use Cases

This project can be used to entirely replace the 'backend' (logic, device handling, external connections) on a control system running Extron Control Script (ECS).  This project only uses the standard libraries that come with 'Pro' (non-xi) control processors so it is backwards compatible with anything that can run ECS, including old IPCP and IPL Pro processors.  Coming Soon: an example of the 'backend server' that one can build.

Physical ports such as relays and serial ports on control processors are also supported.

Additionally, this project allows full external control of the GUI which may be helpful for development or could allow broadcasting messages to touch panels or other uses.

## Reason

Use modern Python, Go, Rust, C#, Java, Javascript, NodeRed or basically any modern language as a backend and extend the useful life and capibility of your hardware.

Additionally, the process of deploying a system using ControlScript® Deployment Utility (CSDU) is cumbersome.  It is a manual process that can only deploy to one room at a time and breaks any hope of a CI/CD pipeline, continuous improvement, and makes minor bugfixes painful if you have a shared codebase.  By using this project, you only have to use CSDU once, or whenever your GUI file changes.

## Compatible Devices

Anything that can run Extron ControlScript®.  You'll need someone who holds the Extron Authorized Programmer cert to initially push the files.

## Use

Deployment is mostly unchanged from the normal process, but please pay attention to how devices and elements need to be instantiated.

1. As normal, place your `.gdl` file in `layout` then setup your room configuration JSON file, but make note of the `Device Alias`'s you assign to processors and UI Devices (touch panels).

2. Write the `config.json` file from this project to the root of your processor.  This file contains the address for your backend server and NTP server coniguration.

3. Instantiate your hardware into the existing lists using the Device Aliases from step 1 into the `src/hardware/hardware.py` file.

Example

```Python
# src/hardware.py
from extronlib.device import ProcessorDevice, UIDevice, eBUSDevice

all_ui_devices = [
    UIDevice("TouchPanel_1"),
    UIDevice("TouchPanel_2"),
]

all_processors = [
    ProcessorDevice("Processor_1"),
]
 ```

4. Instantiate your GUI elements into the existing lists in their respective files in the `gui_elements` folder.  Use the names that are assigned to these elements in your GUI Designer file.  Do the same for any hardware ports you need in `hardware`.

Example

```python
# src/gui_elements/buttons.py

from extronlib.ui import Button
from hardware import all_ui_devices

tlp1 = all_ui_devices[0]
tlp2 = all_ui_devices[1]

all_buttons = [
    Button(tlp1, "Btn_Con_Projector"),
    Button(tlp1, "Btn_Proj_Power"),
    Button(tlp2, "Btn_Diagnostic"),
]
```

5. Deploy as normal using CSDU.  Re-deploy if you update your GUI Designer File or if you change hardware.

## Architecture

There are two major systems that allow fast responsiveness and extensive control over the GUI.

1. A custom built Remote Procedure Call (RPC) API listening on a port of your choosing. This API will accept unsolicited commands. Currently you can send GUI action commands such as page flips, set text on labels, and all of the common tasks one would use for making a responsive GUI. This API can be controlled from a server or you can even send commands through `curl`.  Additionally, you can use this API to get the properties of your processors, touch panels, GUI elements or even send reboot commands.

2. User actions, such as button presses, are sent to an external server using REST POST commands for external procesisng.  For extra responsiveness, the replies to these POST's can include commands for immidate execution.  A great example is if a user presses a power toggle button, the reply can tell the touch panel to update the state of that button immidately, even before any commands are sent to external devices.

### RPC Structure

The RPC API is structured as such:

- Domain (type)
- Object
- Function
- Function Params (up to 3, sometimes optional)

For simplicity sake **all JSON values are strings**.  The API will type convert appropriately.

Due to limitations in the built-in server library, the RPC api runs `HTTP 0.9`

The API has been made to mirror existing methods as close as possible.  The paramaters in the form of `arg1`, `arg2`, `arg3` are simply paramaters that need to be passed to the control script function.   The `ControlScript® Documentation` document provided by Extron will prove helpful in determing how to use the RPC API.

#### Domains (or types) are derived from their Extron classes

- `processor_device`
- `ui_device`
- `button`
- `knob`
- `label`
- `level`
- `slider`
- `relay`
- `serial_interface`

#### Objects are objects that fall in any of the above classes

For processors and touch panels, pass in their `Device Alias` as setup in your standard room configuration JSON file.

All other objects are referenced by their names that are set in GUI designer.

#### Most functions are derived from Extron Class attributes

For example, the `label` class has an attribute called `SetText`.  You would call `SetText` as the function in the API.

#### Additional functions which have been added

- `GetProperty` with the property name as `arg1` will return the property of an object.  Available properties of an object are found in Extron ControlScript® documentation.

- `GetProperty` can return values from the internal page/popup state machine

    State Machine Objects: 

     - `PageState1` for ui_device 1, `PageState2` for ui_device 2, up to 4 total ui_devices.

    PageState Attributes:
    - `ui_device`: returns the ui_device object attached to the state machine
    - `current_page`
    - `current_popup`
    - `all_pages_called` , all pages called since boot
    - `all_popups_called`, all popups and modals called since boot

    Example to return the current page of the first UI Device:
    ```JSON
    {
        "type": "page_state",
        "object": "PageState1",
        "function": "GetProperty",
        "arg1": "current_page"
    }
    ```

`GetAllElements` with no additional arguments will return names of all objects in the system, including processors, UI devices, buttons, sliders, popups, etc.


### RPC API Examples

To set a button called `Btn_Power` to a state of `1`, you would use the following command structure:

```JSON
{
    "type": "button",
    "object": "Btn_Power",
    "function": "SetState",
    "arg1": "1"
}
```

To get the state of that same button:

```JSON
{
    "type": "button",
    "object": "Btn_Power",
    "function": "GetProperty",
    "arg1": "State"
}
```

To show a popup called `Popup1` for 5 seconds. (Alternatively not including `arg1` will default to the popup staying indefinetly, as documented)

```JSON
{
    "type": "ui_device",
    "object": "TouchPanel_1",
    "function": "ShowPopup",
    "arg1": "Popup1",
    "arg2": "5"
}
```

To set a button called `Btn_1` to a medium blink from state 1 to state 2.
In this case `arg1` coresponds to the methods `rate` paramater and `arg2` is the `state_list`

```JSON
{
    "type": "button",
    "object": "Btn_1",
    "function": "SetBlinking",
    "arg1": "Medium",
    "arg2": "[1,2]"
}
```

### REST API Structure

The processor will send user interaction events with the following structure:

- Name (of the object)
- Action
- Value

For example, when a button called `Btn_1` is pressed, the processor will send:

```JSON
{
    "name": "Btn_1",
    "action": "pressed",
    "value": "1"
}
```

Where `value` is the current button visual state.

This data will be sent to domain endpoints on the backend server.
`http://<yourServer>:<yourPort>/api/v1/<domain>`

Example:
`http://192.168.1.1:8080/api/v1/button`

The processor will then wait for an immidate reply, which could be instructions to set that same button to a state of `0` so the user has immidate feedback.  This is especially important for sliders so they don't 'bounce' back to their old state upon release.

## Current State

Currently the majority of GUI functions are supported for all GUI types, relay control, and basic serial port control passthrough.  Multiple touch panels and multiple processors are supported.  This should be enough to get most projects converted but more functionality is coming.


Future:

- MLC Support (this will be a GCP file in a different repo)
- Knob support, eBUS® and other less common hardware, tested.  (Dev enviroment was a IPCP Pro 550 and TLP 725T)
- Tests and performance improvements.  Also tests will determine if continuous level fills would be better handled internally as opposed to a series of RPC calls.

I ask that if you use this project and find a way to make it better, please consider sending pull requests to make this project better for everyone.

## FAQ

Q: Wouldn't the GUI update slower vs writing the logic on the local processor since it has to contact an external server over the network then wait for a reply?

A: Unless your network is awfuly slow, the user will not notice.  You have to remember that when it comes to languages you can't get much slower than Python.  Even though you add in network latency, the processing can be exponentially faster if using a modern language like Go.  If you're using a new Q xi procesor running Python 3.11, and a backend server running the same version of Python, there should be no noticeable difference to the user as the typical network latency on a LAN will be sub 10ms, which is much faster than your typical webpage.  Additinally, the processor is greatly unburdened and on some systems decoupling the backend will result in significant performance improvements and faster GUI responsiveness since the processor is only handling the GUI and the API's.

Q: What if the backend server goes down or the processor loses connectivity to it?

A: Well then the system breaks and the touch panel will appear 'frozen'.  The good news is that it's not too hard to implement high availability and server failover.  That functionality will be coming to this project soon.  Until then, you can still setup email alerts.

Q: Will Extron support this?

A: Probably not.  Please do not contact their support for help, I'm hoping this system will reduce support calls for them.  When it comes to building a backend server, absloute freedom comes with the responsibility for fixing things yourself.

Q: Will you post an example of a backend server?

A: Yes.  As of now I only have a basic proof of concept written in Go.  Unlike this project that will work for most everyone, the backend server will be custom to your logic and your GUI.  Check back soon as i'll be posting the server example in a different repo and link it here.

Q: What about device drivers and modules?

A: The backend server i'm writing intends to use Go Microservices from <https://github.com/Dartmouth-OpenAV> for device handling.  If your equipment is not yet supported, please consider writing a microservice and contributing it to the group.

### Disclaimer

Not affilated with Extron. All registered trademarks noted are property of Extron, and I may have missed some but those would also be property of Extron.