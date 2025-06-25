import tkinter as tk
from tkinter import messagebox
import json
import os

# Import constants
from Constants_Paths import PRESETS_DIR


class PresetController:
    """Handles all preset-related functionality"""
    
    def __init__(self, parent):
        self.parent = parent
        self.current_preset_data = {}
        
    def on_preset_selected_auto_fill(self, event=None):
        """Auto-fill all parameters when a preset is selected"""
        try:
            selected_preset = self.parent.selected_preset_var.get()
            if not selected_preset or selected_preset == "Select a method preset...":
                return
                
            # Load preset data from file
            preset_file = os.path.join(PRESETS_DIR, f"{selected_preset}.json")
            if os.path.exists(preset_file):
                with open(preset_file, 'r') as f:
                    preset_data = json.load(f)
                    
                # Store the preset data
                self.current_preset_data = preset_data
                
                # Auto-fill parameters in both Main and Advanced tabs
                self._auto_fill_parameters(preset_data)
                
                print(f"Loaded and applied preset: {selected_preset}")
            else:
                messagebox.showerror("Error", f"Preset file not found: {selected_preset}")                
        except Exception as e:
            print(f"Error loading preset: {e}")
            messagebox.showerror("Error", f"Failed to load preset: {e}")
            
    def _auto_fill_parameters(self, preset_data):
        """Auto-fill parameters in both Main and Advanced tabs based on preset data"""
        try:
            # Fill Main tab parameters (if they exist)
            if hasattr(self.parent, 'entries') and self.parent.entries:
                for param_name, param_data in preset_data.get('general', {}).items():
                    if param_name in self.parent.entries:
                        entry = self.parent.entries[param_name]
                        if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                            entry.delete(0, tk.END)
                            # Extract just the value, not the full dict
                            value = param_data.get('value', param_data) if isinstance(param_data, dict) else param_data
                            entry.insert(0, str(value))
                        
                        # Set unit if available and units dict exists
                        if hasattr(self.parent, 'units') and param_name in self.parent.units and isinstance(param_data, dict) and 'unit' in param_data:
                            unit_var = self.parent.units[param_name]
                            unit_var.set(param_data['unit'])
            
            # Fill Advanced tab parameters via parameter section
            if hasattr(self.parent, 'parameter_section') and self.parent.parameter_section:
                # Fill general parameters
                for param_name, param_data in preset_data.get('general', {}).items():
                    if hasattr(self.parent.parameter_section, 'entries') and param_name in self.parent.parameter_section.entries:
                        entry = self.parent.parameter_section.entries[param_name]
                        if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                            entry.delete(0, tk.END)
                            entry.insert(0, str(param_data.get('value', param_data)))
                        
                        # Set unit if available
                        if hasattr(self.parent.parameter_section, 'units') and param_name in self.parent.parameter_section.units and 'unit' in param_data:
                            unit_var = self.parent.parameter_section.units[param_name]
                            unit_var.set(param_data['unit'])
                
                # Fill advanced parameters
                for param_name, param_data in preset_data.get('advanced', {}).items():
                    # Map advanced parameter names to entry attributes
                    entry_mapping = {
                        'Injection Time': 'injection_time_entry', 
                        'Valve Control Timing': 'valve_time_entry',
                        'Degassing Time': 'degassing_time_entry',
                        'Transfer Time': 'transfer_time_entry',
                        'Recycle Time': 'recycle_time_entry'
                    }
                    
                    if param_name in entry_mapping:
                        entry_attr = entry_mapping[param_name]
                        if hasattr(self.parent, entry_attr):
                            entry = getattr(self.parent, entry_attr)
                            if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                                entry.delete(0, tk.END)
                                entry.insert(0, str(param_data.get('value', param_data)))            
            # Update polarization method if specified
            if 'polarization_method' in preset_data:
                method_file = preset_data['polarization_method']
                if method_file:
                    # Extract just the filename from the path
                    method_name = os.path.basename(method_file)
                    
                    # Update both the file path and dropdown selection
                    self.parent.polarization_method_file = method_file
                      # Update dropdown to show the selected method
                    if hasattr(self.parent, 'polarization_method_var'):
                        self.parent.polarization_method_var.set(method_name)
                    elif hasattr(self.parent, 'selected_method_var'):
                        self.parent.selected_method_var.set(method_name)
                    
                    print(f"Set polarization method to: {method_name}")
                    
                    # Update the live waveform plot with the new method
                    if hasattr(self.parent, 'waveform_controller'):
                        self.parent.waveform_controller.refresh_live_waveform()
            
            print(f"Successfully auto-filled parameters from preset")
                
        except Exception as e:
            print(f"Error auto-filling parameters: {e}")
            messagebox.showwarning("Auto-Fill Warning", 
                                 f"Some parameters could not be auto-filled: {e}") 