import json
import tkinter as tk
from tkinter import messagebox, ttk

"""
Helper tool to generate JSON for port instantiation (Serial, Relay, Ethernet)

Run this on a workstation, not on the processor
"""


class PortInstantiationApp:
    def __init__(self, root):

        self.host_classes = ["ProcessorDevice", "eBUSDevice"]
        self.host_options = self.find_existing_hosts()

        self.root = root
        self.root.title("Port Instantiation Helper")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, expand=True)

        self.serial_frame = ttk.Frame(self.notebook, width=400, height=280)
        self.ethernet_frame = ttk.Frame(self.notebook, width=400, height=280)
        self.relay_frame = ttk.Frame(self.notebook, width=400, height=280)

        self.serial_frame.pack(fill="both", expand=True)
        self.ethernet_frame.pack(fill="both", expand=True)
        self.relay_frame.pack(fill="both", expand=True)

        self.notebook.add(self.serial_frame, text="Serial Interface")
        self.notebook.add(self.ethernet_frame, text="Ethernet Client Interface")
        self.notebook.add(self.relay_frame, text="Relay Interface")

        self.create_serial_interface()
        self.create_ethernet_interface()
        self.create_relay_interface()

    def find_existing_hosts(self):
        """Scans the room config JSON to try and pre-fill 'Host' fields"""
        existing_hosts = []
        try:
            with open("src/hardware/hardware.py", "r") as hardware_file:
                lines = hardware_file.readlines()
        except Exception as e:
            print(e)
            return []

        for line in lines:
            line = line.strip()
            if "import" in line or line.startswith("#"):
                continue
            for host_class in self.host_classes:
                if host_class in line and "(" in line and ")" in line:
                    host_name = line.split("(")[1].split(")")[0].strip('"').strip("'")
                    existing_hosts.append(host_name)
        return existing_hosts

    def create_serial_interface(self):
        struct = {
            "Host": "",
            "Port": "",
            "Baud": 9600,
            "Data": 8,
            "Stop": 1,
            "CharDelay": 0,
        }
        hosts_option_len = len(self.host_options)
        if hosts_option_len == 1:
            struct["Host"] = self.host_options[0]
        elif hosts_option_len > 1:
            button_frame = ttk.Frame(self.serial_frame)
            button_frame.pack(pady=10)
            for host in self.host_options:
                button = ttk.Button(
                    button_frame,
                    text=host,
                    command=lambda h=host: self.serial_entries["Host"].delete(0, tk.END)
                    or self.serial_entries["Host"].insert(0, h),
                )
                button.pack(side="left")

        self.serial_entries = {}
        for field, default in struct.items():
            label = ttk.Label(self.serial_frame, text=field)
            label.pack()
            entry = ttk.Entry(self.serial_frame)
            entry.insert(0, default)
            entry.pack()
            self.serial_entries[field] = entry

        # Parity
        parity_label = ttk.Label(self.serial_frame, text="Parity")
        parity_label.pack()
        self.parity_var = tk.StringVar(value="None")
        parity_frame = ttk.Frame(self.serial_frame)
        parity_frame.pack()
        for parity in ["None", "Odd", "Even"]:
            radio = ttk.Radiobutton(
                parity_frame, text=parity, variable=self.parity_var, value=parity
            )
            radio.pack(side="left")

        # FlowControl
        flowcontrol_label = ttk.Label(self.serial_frame, text="FlowControl")
        flowcontrol_label.pack()
        self.flowcontrol_var = tk.StringVar(value="Off")
        flowcontrol_frame = ttk.Frame(self.serial_frame)
        flowcontrol_frame.pack()
        for flowcontrol in ["Off", "HW", "SW"]:
            radio = ttk.Radiobutton(
                flowcontrol_frame,
                text=flowcontrol,
                variable=self.flowcontrol_var,
                value=flowcontrol,
            )
            radio.pack(side="left")

        # Mode
        mode_label = ttk.Label(self.serial_frame, text="Mode")
        mode_label.pack()
        self.mode_var = tk.StringVar(value="RS232")
        mode_frame = ttk.Frame(self.serial_frame)
        mode_frame.pack()
        for mode in ["RS232", "RS422", "RS485"]:
            radio = ttk.Radiobutton(
                mode_frame, text=mode, variable=self.mode_var, value=mode
            )
            radio.pack(side="left")

        generate_button = ttk.Button(
            self.serial_frame, text="Generate JSON", command=self.generate_serial_json
        )
        generate_button.pack(pady=10)

    def generate_serial_json(self):
        data = {field: entry.get() for field, entry in self.serial_entries.items()}
        data["Parity"] = self.parity_var.get()
        data["FlowControl"] = self.flowcontrol_var.get()
        data["Mode"] = self.mode_var.get()
        json_data = json.dumps(data, indent=4)
        self.show_json(json_data)

    def create_ethernet_interface(self):
        struct = {
            "Hostname": "",
            "IPPort": "",
            "Protocol": "TCP",
            "Username": "",
            "Password": "",
            "ServicePort": 0,
            "bufferSize": 4096,
        }
        self.ethernet_entries = {}
        self.protocol_var = tk.StringVar(value="TCP")

        for field, default in struct.items():
            if field == "Protocol":
                label = ttk.Label(self.ethernet_frame, text=field)
                label.pack()
                frame = ttk.Frame(self.ethernet_frame)
                frame.pack()
                for protocol in ["TCP", "UDP", "SSH"]:
                    radio = ttk.Radiobutton(
                        frame,
                        text=protocol,
                        variable=self.protocol_var,
                        value=protocol,
                        command=self.update_ethernet_fields,
                    )
                    radio.pack(side="left")
            else:
                label = ttk.Label(self.ethernet_frame, text=field)
                label.pack()
                entry = ttk.Entry(self.ethernet_frame)
                entry.insert(0, default)
                entry.pack()
                self.ethernet_entries[field] = entry

        generate_button = ttk.Button(
            self.ethernet_frame,
            text="Generate JSON",
            command=self.generate_ethernet_json,
        )
        generate_button.pack(pady=10)

        self.update_ethernet_fields()

    def update_ethernet_fields(self):
        protocol = self.protocol_var.get()
        if protocol == "TCP":
            self.ethernet_entries["IPPort"].delete(0, tk.END)
            self.ethernet_entries["IPPort"].insert(0, "23")
            self.ethernet_entries["ServicePort"].config(state="disabled")
            self.ethernet_entries["Username"].config(state="disabled")
            self.ethernet_entries["Password"].config(state="disabled")
            self.ethernet_entries["bufferSize"].config(state="disabled")
        elif protocol == "UDP":
            self.ethernet_entries["IPPort"].delete(0, tk.END)
            self.ethernet_entries["ServicePort"].config(state="normal")
            self.ethernet_entries["Username"].config(state="disabled")
            self.ethernet_entries["Password"].config(state="disabled")
            self.ethernet_entries["bufferSize"].config(state="normal")
        elif protocol == "SSH":
            self.ethernet_entries["IPPort"].delete(0, tk.END)
            self.ethernet_entries["IPPort"].insert(0, "22023")
            self.ethernet_entries["ServicePort"].config(state="disabled")
            self.ethernet_entries["Username"].config(state="normal")
            self.ethernet_entries["Password"].config(state="normal")
            self.ethernet_entries["bufferSize"].config(state="disabled")

    def create_relay_interface(self):
        struct = {"Host": "", "Port": ""}
        hosts_option_len = len(self.host_options)
        if hosts_option_len == 1:
            struct["Host"] = self.host_options[0]
        elif hosts_option_len > 1:
            button_frame = ttk.Frame(self.relay_frame)
            button_frame.pack(pady=10)
            for host in self.host_options:
                button = ttk.Button(
                    button_frame,
                    text=host,
                    command=lambda h=host: self.relay_entries["Host"].delete(0, tk.END)
                    or self.relay_entries["Host"].insert(0, h),
                )
                button.pack(side="left")

        self.relay_entries = {}
        for field, default in struct.items():
            label = ttk.Label(self.relay_frame, text=field)
            label.pack()
            entry = ttk.Entry(self.relay_frame)
            entry.insert(0, default)
            entry.pack()
            self.relay_entries[field] = entry

        generate_button = ttk.Button(
            self.relay_frame, text="Generate JSON", command=self.generate_relay_json
        )
        generate_button.pack(pady=10)

    def generate_serial_json(self):
        data = {field: entry.get() for field, entry in self.serial_entries.items()}
        json_data = json.dumps(data, indent=4)
        self.show_json(json_data)

    def generate_ethernet_json(self):
        data = {field: entry.get() for field, entry in self.ethernet_entries.items()}
        protocol = self.protocol_var.get()
        data["Protocol"] = protocol

        tcp_pop = ["Username", "Password", "ServicePort", "bufferSize"]
        udp_pop = ["Username", "Password"]
        ssh_pop = ["ServicePort", "bufferSize"]

        if protocol == "TCP":
            pop_list = tcp_pop
        elif protocol == "UDP":
            pop_list = udp_pop
        elif protocol == "SSH":
            pop_list = ssh_pop

        for pop_item in pop_list:
            data.pop(pop_item)

        json_data = json.dumps(data, indent=4)
        self.show_json(json_data)

    def generate_relay_json(self):
        data = {field: entry.get() for field, entry in self.relay_entries.items()}
        json_data = json.dumps(data, indent=4)
        self.show_json(json_data)

    def show_json(self, json_data):
        json_window = tk.Toplevel(self.root)
        json_window.title("Generated JSON")
        text = tk.Text(json_window, wrap="word")
        text.insert("1.0", json_data)
        text.pack(expand=True, fill="both")
        text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = PortInstantiationApp(root)
    root.mainloop()
