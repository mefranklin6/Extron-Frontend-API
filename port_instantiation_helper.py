import json
import tkinter as tk
from tkinter import messagebox, ttk

"""
Helper tool to generate JSON for port instantiation (Serial, Relay, Ethernet)

Place this file in the root of your projects directory

Run this on a workstation, not on the processor
"""

__version__ = "1.1.0"


class PortInstantiationApp:
    def __init__(self, root):
        self.export_path = "/ports.json"  # Default: "/ports.json"

        self.SFTP_PORT = 22022
        self.HOST_CLASSES = ["ProcessorDevice", "eBUSDevice"]

        self.json_cache = []

        self.processor_address = ""
        self.processor_password = ""
        self.sftp_available = False

        self.host_options = self.find_existing_hosts()
        try:
            import paramiko

            self.paramiko = paramiko
            self.sftp_available = True
        except ImportError as e:
            print(e)

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
            for host_class in self.HOST_CLASSES:
                if host_class in line and "(" in line and ")" in line:
                    host_name = line.split("(")[1].split(")")[0].strip('"').strip("'")
                    existing_hosts.append(host_name)
        return existing_hosts

    def add_footer_buttons(self, frame):
        if self.sftp_available:
            load_button = ttk.Button(
                frame, text="Load from SFTP", command=self.load_file
            )
            load_button.pack(pady=10)

        preview_button = ttk.Button(
            frame, text="Preview Export", command=self.show_preview
        )
        preview_button.pack(pady=10)

        export_button = ttk.Button(
            frame, text="Export over SFTP", command=self.export_prompt
        )
        export_button.pack(pady=10)

    def create_serial_interface(self):
        struct = {
            "Alias": "",
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
            self.serial_frame,
            text="Generate and Add",
            command=self.generate_serial_json,
        )
        generate_button.pack(pady=10)
        self.add_footer_buttons(self.serial_frame)

    def create_ethernet_interface(self):
        struct = {
            "Alias": "",
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

        self.update_ethernet_fields()

        generate_button = ttk.Button(
            self.ethernet_frame,
            text="Generate and Add",
            command=self.generate_ethernet_json,
        )
        generate_button.pack(pady=10)
        self.add_footer_buttons(self.ethernet_frame)

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
        struct = {"Alias": "", "Host": "", "Port": ""}
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
            self.relay_frame,
            text="Generate and Add",
            command=self.generate_relay_json,
        )
        generate_button.pack(pady=10)
        self.add_footer_buttons(self.relay_frame)

    def update_preview_window(self):
        if (
            hasattr(self, "preview_window")
            and self.preview_window
            and self.preview_window.winfo_exists()
        ):
            self.refresh_preview()

    def generate_serial_json(self):
        data = {field: entry.get() for field, entry in self.serial_entries.items()}
        if not data["Port"].startswith("COM"):
            messagebox.showerror(
                "Error", "Malformed Serial Port: must start with 'COM'."
            )
            return
        data["Class"] = "SerialInterfaceEx"
        data["Parity"] = self.parity_var.get()
        data["FlowControl"] = self.flowcontrol_var.get()
        data["Mode"] = self.mode_var.get()
        self.json_cache.append(data)
        self.update_preview_window()
        self.serial_entries["Port"].delete(0, tk.END)
        self.serial_entries["Alias"].delete(0, tk.END)

    def generate_ethernet_json(self):
        data = {field: entry.get() for field, entry in self.ethernet_entries.items()}

        if data["Hostname"] == "":
            messagebox.showerror("Error", "Hostname cannot be empty.")
            return

        data["Class"] = "EthernetClientInterfaceEx"
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
            if data["Username"] == "" or data["Password"] == "":
                messagebox.showerror("Error", "Missing Credentials for SSH")
                return

        for pop_item in pop_list:
            data.pop(pop_item)

        self.json_cache.append(data)
        self.update_preview_window()

        self.ethernet_entries["Hostname"].delete(0, tk.END)
        self.ethernet_entries["Alias"].delete(0, tk.END)

    def generate_relay_json(self):
        data = {field: entry.get() for field, entry in self.relay_entries.items()}
        if not data["Port"].startswith("RLY"):
            messagebox.showerror(
                "Error", "Malformed Relay Port: must start with 'RLY'."
            )
            return
        data["Class"] = "RelayInterfaceEx"
        self.json_cache.append(data)
        self.update_preview_window()
        self.relay_entries["Port"].delete(0, tk.END)
        self.relay_entries["Alias"].delete(0, tk.END)

    def load_file(self):
        if self.json_cache != []:
            user_continue = messagebox.askyesno(
                "Continue?",
                "Loading a file will undo any previous un-exported work.  Continue?",
            )
            if not user_continue:
                return
            else:
                self.json_cache = {}
                self.update_preview_window()

        # Prompt for processor address and admin password
        loader_window = tk.Toplevel(self.root)
        loader_window.title("Load Remote JSON from Processor")

        info_label = ttk.Label(
            loader_window,
            text=f"Loading: {self.export_path}",
        )
        info_label.pack(pady=(10, 0))

        address_label = ttk.Label(loader_window, text="Processor Address:")
        address_label.pack(pady=10)
        address_entry = ttk.Entry(loader_window)
        address_entry.insert(0, self.processor_address)
        address_entry.pack(pady=0)

        password_label = ttk.Label(loader_window, text="Admin Password:")
        password_label.pack(pady=10)
        password_entry = ttk.Entry(loader_window, show="*")
        password_entry.insert(0, self.processor_password)
        password_entry.pack(pady=0)

        def on_load_submit():
            self.processor_address = address_entry.get().strip()
            self.processor_password = password_entry.get()
            loader_window.destroy()

            hostname = self.processor_address
            port = self.SFTP_PORT
            username = "admin"
            password = self.processor_password
            remote_file_path = self.export_path

            transport = None
            try:
                transport = self.paramiko.Transport((hostname, port))
                transport.connect(username=username, password=password)
                sftp = self.paramiko.SFTPClient.from_transport(transport)

                # Open and read remote JSON file
                with sftp.file(remote_file_path, "r") as remote_file:
                    content = remote_file.read()
                    if isinstance(content, bytes):
                        content = content.decode("utf-8", errors="replace")
                data = json.loads(content)

                # Normalize into list for json_cache
                if isinstance(data, list):
                    self.json_cache = data
                elif isinstance(data, dict):
                    self.json_cache = [data]
                else:
                    raise ValueError("Unsupported JSON format (expected list or dict)")

                self.show_preview()
            except FileNotFoundError:
                messagebox.showerror(
                    "Not Found",
                    f"The file '{remote_file_path}' was not found on the processor.",
                )
            except Exception as e:
                messagebox.showerror("Load Failed", f"Failed to load: {e}")
            finally:
                try:
                    if transport:
                        transport.close()
                except Exception:
                    pass

        submit_button = ttk.Button(loader_window, text="Load", command=on_load_submit)
        loader_window.bind("<Return>", lambda event: on_load_submit())
        submit_button.pack(pady=12)

    def show_preview(self):
        # Reuse existing preview window if open
        if (
            hasattr(self, "preview_window")
            and self.preview_window
            and self.preview_window.winfo_exists()
        ):
            self.preview_window.deiconify()
            self.preview_window.lift()
            self.refresh_preview()
            return

        # Create a new preview window
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("JSON Cache Preview")
        self.preview_text = tk.Text(self.preview_window, wrap="word")
        self.preview_text.pack(expand=True, fill="both")
        self.preview_text.config(state="disabled")

        # Clear the reference when the window is closed
        def on_close():
            self.preview_text = None
            self.preview_window.destroy()
            self.preview_window = None

        self.preview_window.protocol("WM_DELETE_WINDOW", on_close)
        self.refresh_preview()

    def refresh_preview(self):
        # Update the preview text if the window is open
        if (
            hasattr(self, "preview_window")
            and self.preview_window
            and self.preview_window.winfo_exists()
            and hasattr(self, "preview_text")
            and self.preview_text
        ):
            self.preview_text.config(state="normal")
            self.preview_text.delete("1.0", tk.END)
            json_data = json.dumps(self.json_cache, indent=4)
            self.preview_text.insert("1.0", json_data)
            self.preview_text.config(state="disabled")

    def export(self):
        json_data = json.dumps(self.json_cache, indent=4)

        hostname = self.processor_address
        port = self.SFTP_PORT
        username = "admin"
        password = self.processor_password
        remote_file_path = self.export_path

        try:
            transport = self.paramiko.Transport((hostname, port))
            transport.connect(username=username, password=password)
            sftp = self.paramiko.SFTPClient.from_transport(transport)

            # Check if the file already exists
            try:
                sftp.stat(remote_file_path)
                file_exists = True
            except FileNotFoundError:
                file_exists = False

            if not file_exists:
                with sftp.file(remote_file_path, "w") as remote_file:
                    remote_file.write(json_data)

            if file_exists:
                action = messagebox.askyesnocancel(
                    "File Exists",
                    f"The file {remote_file_path} already exists. Do you want to overwrite it? (Yes to overwrite, No to append, Cancel to abort)",
                )
                if action is None:
                    transport.close()
                    return
                elif action:
                    # Overwrite the file
                    with sftp.file(remote_file_path, "w") as remote_file:
                        remote_file.write(json_data)
                else:
                    # Append to the file
                    with sftp.file(remote_file_path, "r") as remote_file:
                        existing_data = json.load(remote_file)

                    # Merge the existing data with the new data
                    if isinstance(existing_data, list):
                        existing_data.extend(self.json_cache)
                    elif isinstance(existing_data, dict):
                        existing_data.update(self.json_cache)
                    else:
                        raise ValueError("Unsupported JSON format for appending")

                    with sftp.file(remote_file_path, "w") as remote_file:
                        remote_file.write(json.dumps(existing_data, indent=4))

            print("Export successful")
            transport.close()
            exit(0)
        except Exception as e:
            print("Export failed!")
            messagebox.showerror(
                "Error",
                f"""Export failed: {e}

You can still copy-paste your data from the "Show Preview" button
""",
            )
        finally:
            transport.close()

    def export_prompt(self):
        if not self.sftp_available:
            messagebox.showerror(
                "No SFTP Client",
                """Missing required library "paramiko".
SFTP Export is diabled for this session.

Please copy and paste manually from the "Preview Export" button

To fix this error, please `pip install paramiko`
""",
            )
            return

        if self.json_cache == []:
            messagebox.showerror("Error", "No data to export.")
            return

        processor_info_window = tk.Toplevel(self.root)
        processor_info_window.title("Enter Processor Information")

        address_label = ttk.Label(processor_info_window, text="Processor Address:")
        address_label.pack(pady=10)
        address_entry = ttk.Entry(processor_info_window)
        address_entry.pack(pady=10)

        password_label = ttk.Label(processor_info_window, text="Admin Password:")
        password_label.pack(pady=10)
        password_entry = ttk.Entry(processor_info_window, show="*")
        password_entry.pack(pady=10)

        def on_submit():
            self.processor_address = address_entry.get()
            self.processor_password = password_entry.get()
            processor_info_window.destroy()
            self.export()

        submit_button = ttk.Button(
            processor_info_window, text="Submit", command=on_submit
        )
        submit_button.pack(pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = PortInstantiationApp(root)
    root.mainloop()
