import os
import json
import tkinter as tk
from tkinter import filedialog

# Import from the utility functions - using try/except for graceful handling
try:
    from Nested_Programs.Utility_Functions import build_composite_waveform
except ImportError:
    # Fallback if utility functions aren't available
    def build_composite_waveform(*args, **kwargs):
        return [], 44100  # Empty buffer, sample rate


class MethodManager:
    """Handles polarization method selection and management"""
    def __init__(self, parent):
        self.parent = parent
        self.polarization_method_file = None
        self.polarization_methods_dir = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
        self.selected_method_var = tk.StringVar(value="Select method...")
        self.polarization_method_var = tk.StringVar(value="Select method...")
        
    def load_polarization_methods_from_directory(self):
        """Load all JSON polarization method files from the specified directory"""
        try:
            # Create directory if it doesn't exist
            if not os.path.exists(self.polarization_methods_dir):
                os.makedirs(self.polarization_methods_dir)
                return ["Select method..."]
            
            # Get all JSON files in the directory
            json_files = []
            for file in os.listdir(self.polarization_methods_dir):
                if file.endswith('.json'):
                    json_files.append(file)
            
            # Sort alphabetically and add default option
            json_files.sort()
            methods = ["Select method..."] + json_files
            
            print(f"Found {len(json_files)} polarization method files in {self.polarization_methods_dir}")
            return methods
            
        except Exception as e:
            print(f"Error loading polarization methods from directory: {e}")
            return ["Select method..."]
            
    def on_method_selected(self, event=None):
        """Handle method selection from combobox"""
        try:
            selected_method = self.selected_method_var.get()
            if selected_method and selected_method != "Select method...":
                self.polarization_method_file = os.path.join(self.polarization_methods_dir, selected_method)
                print(f"Selected polarization method: {self.polarization_method_file}")
                
                # Update the live waveform plot in the main tab
                self.parent._refresh_live_waveform()
                
                # Grey out bubbling time parameter when method is selected
                self._update_bubbling_time_state(disabled=True)
            else:
                # Re-enable bubbling time parameter when no method is selected
                self._update_bubbling_time_state(disabled=False)
        except Exception as e:
            print(f"Error handling method selection: {e}")
            
    def _update_bubbling_time_state(self, disabled=True):
        """Update the state (enabled/disabled) of bubbling time entries"""
        try:
            state = "disabled" if disabled else "normal"
            
            # Update Main tab bubbling time entry
            if hasattr(self.parent, 'entries') and "Bubbling Time" in self.parent.entries:
                entry = self.parent.entries["Bubbling Time"]
                if hasattr(entry, 'config'):
                    entry.config(state=state)
                    if disabled:
                        entry.config(bg="#f0f0f0")  # Grey background when disabled
                    else:
                        entry.config(bg=self.parent.theme_manager.color("entry_bg"))
            
            # Update Advanced tab bubbling time entry  
            if (hasattr(self.parent, 'parameter_section') and 
                self.parent.parameter_section and 
                hasattr(self.parent.parameter_section, 'entries') and 
                "Bubbling Time" in self.parent.parameter_section.entries):
                
                entry = self.parent.parameter_section.entries["Bubbling Time"]
                if hasattr(entry, 'config'):
                    entry.config(state=state)
                    if disabled:
                        entry.config(bg="#f0f0f0")  # Grey background when disabled
                    else:
                        entry.config(bg=self.parent.theme_manager.color("entry_bg"))
            
            action = "disabled" if disabled else "enabled"
            print(f"Bubbling time parameter {action} - polarization method timing will be used")
            
        except Exception as e:
            print(f"Error updating bubbling time state: {e}")
            
    def select_polarization_method(self):
        """Open file dialog to select polarization method"""
        file_path = filedialog.askopenfilename(
            initialdir=self.polarization_methods_dir,
            title="Select Polarization Method",
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            self.polarization_method_file = file_path
            filename = os.path.basename(file_path)
            self.selected_method_var.set(filename)
            print(f"Selected polarization method: {file_path}")
            
            # Update the live waveform plot in the main tab
            self.parent._refresh_live_waveform()
            
    def compute_polarization_duration(self):
        """Return the duration (s) of the waveform described by the currently selected polarization-method JSON file"""
        if not self.parent.polarization_method_file:
            return 0.0
        try:
            with open(self.parent.polarization_method_file, "r") as f:
                cfg = json.load(f)

            # Build the identical buffer the DAQ routine will output
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                dc_offset = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"], dc_offset=dc_offset)
            return len(buf) / sr
        except Exception as e:
            print(f"[Timer] duration-calc error: {e}")
            return 0.0 