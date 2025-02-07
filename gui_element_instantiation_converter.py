import os
import tkinter as tk
from tkinter import filedialog

info = """
This is a utility script for converting your existing GUI element instantiations
into a format compatible with Extron-Frontend-API (mefranklin6)

Run this on a workstation, not on a control processor

For now, this script is only useful if you instantiated your GUI elements by:
variable_name = Object(gui_object, ID)

Example:
# old file
Button1 = Button(TLP1, 101)
Button2 = Button(TLP1, 102)

This script will convert it into a compatible list and place it in the correct folder

# src/gui_elements/buttons.py
all_buttons = [
    Button(TLP1, 101),
    Button(TLP1, 102),
]


This should be safe to run against your entire old repository,
and will find all instances of GUI element instantiations and process them
in a single run, recursively.

"""


class InstantionConverter:

    def __init__(self, user_selected_directory):
        self.ignore_lines_with_words = ("import", "extronlib")
        self.required_chars = ("=", "(", ")", ",")
        self.dest_button_file = "src/gui_elements/buttons.py"
        self.dest_knob_file = "src/gui_elements/knobs.py"
        self.dest_label_file = "src/gui_elements/labels.py"
        self.dest_level_file = "src/gui_elements/levels.py"
        self.dest_slider_file = "src/gui_elements/sliders.py"

        self.gui_elements = {
            "Button": [],
            "Knob": [],
            "Label": [],
            "Level": [],
            "Slider": [],
        }

        self.search_terms = self._make_search_terms()

        self.selected_directory = user_selected_directory

    def _make_search_terms(self):
        result = []
        raw_gui_elements = self.gui_elements.keys()
        for raw_element in raw_gui_elements:
            search_str = f"{raw_element}("
            result.append(search_str)
        return result

    def _file_to_lines(self, file_path):
        with open(file_path, "r") as file:
            lines = file.readlines()
        return lines

    def _process_file(self, file_path):
        lines = self._file_to_lines(file_path)
        print(f"Processing file: {file_path}")

        for line in lines:
            # Ignore lines with certain words
            if any(word in line for word in self.ignore_lines_with_words):
                continue

            if ":" in line or "[" in line or "{" in line:
                continue

            # Ignore commented out lines
            line_strip = line.strip()
            if line_strip.startswith("#"):
                continue

            # Ignore lines that don't contain required characters
            if not all(char in line for char in self.required_chars):
                continue

            else:
                try:
                    splits = line.split("=")
                    assignment_side = "=".join(splits[1:])  # grab optional args
                    for search_str in self.search_terms:
                        if search_str in assignment_side:
                            obj_type = search_str[:-1]
                            collection_list = self.gui_elements[obj_type]
                            collection_list.append(assignment_side)
                except:
                    print(f"------------ Error processing line: {line}")

    def _process_directory(self):
        if selected_directory:
            try:
                for root, dirs, files in os.walk(selected_directory):
                    for file in files:
                        if (
                            file.endswith(".py")
                            and "gui_element_instantiation_converter" not in file
                        ):
                            self._process_file(os.path.join(root, file))

            except FileNotFoundError:
                print(f"The directory '{selected_directory}' does not exist.")
        else:
            print("No directory selected to process")

    def _write_to_file(self, dest_file, collection, list_name):
        with open(dest_file, "a") as file:
            file.write("\n")
            file.write(f"{list_name} = [\n")
            for element in collection:
                file.write(f"    {element},")
            file.write("\n]\n")
            print(f"{list_name} written to {dest_file}")

    def bundle_and_save(self):
        self._process_directory()
        self._write_to_file(
            self.dest_button_file, self.gui_elements["Button"], "all_buttons"
        )
        self._write_to_file(self.dest_knob_file, self.gui_elements["Knob"], "all_knobs")
        self._write_to_file(
            self.dest_label_file, self.gui_elements["Label"], "all_labels"
        )
        self._write_to_file(
            self.dest_level_file, self.gui_elements["Level"], "all_levels"
        )
        self._write_to_file(
            self.dest_slider_file, self.gui_elements["Slider"], "all_sliders"
        )


def select_directory():
    global selected_directory
    selected_directory = filedialog.askdirectory(title="Select Directory")
    if selected_directory:
        print(f"Selected directory: {selected_directory}")
    else:
        print("No directory selected")


def start_conversion():
    converter = InstantionConverter(selected_directory)
    converter.bundle_and_save()
    print("Conversion complete")
    exit()


root = tk.Tk()
root.title("GUI Instantiation Converter")

label = tk.Label(root, text=info, anchor="w", justify="left")
label.pack(pady=10, fill="both")

button_select = tk.Button(root, text="Select Directory", command=select_directory)
button_select.pack(pady=5)

button_start = tk.Button(root, text="Start", command=start_conversion)
button_start.pack(pady=5)

root.mainloop()
