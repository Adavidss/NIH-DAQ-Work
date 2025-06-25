import os
import json
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from Nested_Programs.ToolTip import ToolTip  # Ensure correct import path for ToolTip

# Define presets directory path
PRESETS_DIR = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods\Presets"

# ==== PRESET MANAGER CLASS ==============================
class PresetManager:
    """Manages presets including CRUD operations and UI components"""
    def __init__(self, parent, param_section):
        self.parent = parent  # Parent SABREGUI instance
        self.param_section = param_section  # ParameterSection instance
        self.preset_var = None
        self.preset_combobox = None
        
    def create_presets_management(self, parent):
        """Create comprehensive presets management section"""
        presets_frame = ttk.LabelFrame(parent, text="Presets Management", padding=10)
        presets_frame.pack(fill="x", padx=5, pady=5)
        
        # Preset selection row
        selection_frame = tk.Frame(presets_frame)
        selection_frame.pack(fill="x", pady=2)
        
        tk.Label(selection_frame, text="Select Preset:", width=15, anchor="w").pack(side="left")
        
        self.preset_var = tk.StringVar(value="Select a preset...")
        self.preset_combobox = ttk.Combobox(
            selection_frame,
            textvariable=self.preset_var,
            width=25,
            state="readonly"
        )
        self.preset_combobox.pack(side="left", padx=5, fill="x", expand=True)
        self.preset_combobox.bind("<<ComboboxSelected>>", self.on_preset_selected)
        
        # Refresh presets list
        self.refresh_presets_list()
        
        # Preset management buttons - First row
        buttons_frame1 = tk.Frame(presets_frame)
        buttons_frame1.pack(fill="x", pady=2)
        
        ttk.Button(buttons_frame1, text="Save Current as Preset", command=self.save_current_as_preset).pack(side="left", padx=2)
        ttk.Button(buttons_frame1, text="Edit Preset", command=self.edit_preset).pack(side="left", padx=2)
        
        # Preset management buttons - Second row
        buttons_frame2 = tk.Frame(presets_frame)
        buttons_frame2.pack(fill="x", pady=2)
        
        ttk.Button(buttons_frame2, text="Delete Preset", command=self.delete_preset).pack(side="left", padx=2)
        ttk.Button(buttons_frame2, text="Refresh List", command=self.refresh_presets_list).pack(side="left", padx=2)
        ttk.Button(buttons_frame2, text="Download Config Files", 
                  command=self.parent.download_config_files).pack(side="left", padx=2)
        
        # Add tooltips
        preset_tooltip = "Manage experimental parameter presets. Load from external files, create new ones, or edit existing presets."
        ToolTip(self.preset_combobox, preset_tooltip, parent=self.parent)
        
    def refresh_presets_list(self):
        """Refresh the list of available presets from the presets directory"""
        try:
            preset_files = []
            if os.path.exists(PRESETS_DIR):
                for file in os.listdir(PRESETS_DIR):
                    if file.endswith('.json'):
                        preset_files.append(file[:-5])  # Remove .json extension
            
            preset_options = ["Select a preset..."] + sorted(preset_files)
            self.preset_combobox['values'] = preset_options
            
            # Reset selection if current selection no longer exists
            if self.preset_var.get() not in preset_options:
                self.preset_var.set("Select a preset...")
                
        except Exception as e:
            print(f"Error refreshing presets list: {e}")
            self.preset_combobox['values'] = ["Select a preset..."]

    def load_preset_from_file(self, preset_name):
        """Load preset data from file"""
        try:
            preset_file = os.path.join(PRESETS_DIR, f"{preset_name}.json")
            if os.path.exists(preset_file):
                with open(preset_file, 'r') as f:
                    preset_data = json.load(f)
                    # Debug output to verify structure
                    print(f"Loaded preset structure: {list(preset_data.keys())}")
                    return preset_data
            return None
        except Exception as e:
            print(f"Error loading preset {preset_name}: {e}")
            return None

    def save_preset_to_file(self, preset_name, preset_data):
        """Save preset data to file"""
        try:
            preset_file = os.path.join(PRESETS_DIR, f"{preset_name}.json")
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving preset {preset_name}: {e}")
            return False

    def get_current_parameters(self):
        """Get all current parameter values as a preset dictionary"""
        parameters = self.param_section.get_current_parameters()
        
        # Add polarization method to the parameters
        preset_data = {
            "general": parameters["general"],
            "advanced": parameters["advanced"],
            "polarization_method": self.parent.polarization_method_file
        }
        
        return preset_data

    def apply_preset_data(self, preset_data):
        """Apply preset data to current parameters"""
        try:
            # Apply general parameters
            for param, data in preset_data.get("general", {}).items():
                if param in self.param_section.entries:
                    self.param_section.entries[param].delete(0, tk.END)
                    self.param_section.entries[param].insert(0, data["value"])
                    self.param_section.units[param].set(data["unit"])
                    print(f"Applied general parameter: {param} = {data['value']} {data['unit']}")
            
            # Apply advanced parameters
            advanced_entries = {
                "Valve Control Timing": (self.parent.valve_time_entry, self.parent.valve_time_entry_unit),
                "Activation Time": (self.parent.activation_time_entry, self.parent.activation_time_entry_unit),
                "Degassing Time": (self.parent.degassing_time_entry, self.parent.degassing_time_entry_unit),
                "Injection Time": (self.parent.injection_time_entry, self.parent.injection_time_entry_unit),
                "Transfer Time": (self.parent.transfer_time_entry, self.parent.transfer_time_entry_unit),
                "Recycle Time": (self.parent.recycle_time_entry, self.parent.recycle_time_entry_unit)
            }
            
            for param, data in preset_data.get("advanced", {}).items():
                if param in advanced_entries:
                    entry, unit_var = advanced_entries[param]
                    entry.delete(0, tk.END)
                    entry.insert(0, data["value"])
                    unit_var.set(data["unit"])
                    print(f"Applied advanced parameter: {param} = {data['value']} {data['unit']}")
            
            # Apply polarization method
            if "polarization_method" in preset_data and preset_data["polarization_method"]:
                self.parent.polarization_method_file = preset_data["polarization_method"]
                
                # Update method combobox selection
                method_filename = os.path.basename(preset_data["polarization_method"])
                if method_filename in self.parent.method_combobox['values']:
                    self.parent.selected_method_var.set(method_filename)
                else:
                    # Try to refresh the method list first
                    self.parent.refresh_method_list()
                    if method_filename in self.parent.method_combobox['values']:
                        self.parent.selected_method_var.set(method_filename)
                    else:
                        # If still not found, reset to default
                        self.parent._reset_selected_method_label()
                        
                print(f"Applied polarization method: {os.path.basename(preset_data['polarization_method'])}")
            
            # Force UI update
            self.parent.update_idletasks()
            return True
        except Exception as e:
            print(f"Error applying preset data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_current_as_preset(self):
        """Save current parameters as a new preset"""
        # Get preset name from user
        preset_name = simpledialog.askstring(
            "Save Preset", 
            "Enter name for new preset:",
            parent=self.parent
        )
        
        if not preset_name:
            return
        
        # Remove invalid characters for filename
        preset_name = "".join(c for c in preset_name if c.isalnum() or c in (' ', '-', '_')).strip()
        
        if not preset_name:
            messagebox.showerror("Error", "Invalid preset name.")
            return
        
        # Check if preset already exists
        preset_file = os.path.join(PRESETS_DIR, f"{preset_name}.json")
        if os.path.exists(preset_file):
            if not messagebox.askyesno("Overwrite", f"Preset '{preset_name}' already exists. Overwrite?"):
                return
        
        # Get current parameters and save
        preset_data = self.get_current_parameters()
        if self.save_preset_to_file(preset_name, preset_data):
            self.refresh_presets_list()
            self.preset_var.set(preset_name)
            messagebox.showinfo("Success", f"Saved preset: {preset_name}")
        else:
            messagebox.showerror("Error", f"Failed to save preset: {preset_name}")

    def edit_preset(self):
        """Edit an existing preset using a non-modal dialog"""
        selected = self.preset_var.get()
        if selected == "Select a preset...":
            messagebox.showwarning("No Selection", "Please select a preset to edit.")
            return
        
        # Load current preset data
        preset_data = self.load_preset_from_file(selected)
        if not preset_data:
            messagebox.showerror("Error", f"Could not load preset: {selected}")
            return
        
        # Apply preset data to current fields for editing
        if self.apply_preset_data(preset_data):
            # Create a non-modal dialog
            edit_window = tk.Toplevel(self.parent)
            edit_window.title(f"Edit Preset: {selected}")
            edit_window.geometry("400x150")
            edit_window.transient(self.parent)  # Set as transient to main window but not modal
            
            message_label = tk.Label(
                edit_window, 
                text=f"Preset '{selected}' has been loaded into the current fields.\n\n"
                     "Modify the parameters as needed, then click 'Save Changes'\n"
                     "or 'Cancel' when finished.",
                justify=tk.LEFT,
                padx=20,
                pady=10
            )
            message_label.pack(fill="x", expand=True)
            
            button_frame = tk.Frame(edit_window)
            button_frame.pack(fill="x", padx=20, pady=10)
            
            def save_changes():
                updated_data = self.get_current_parameters()
                if self.save_preset_to_file(selected, updated_data):
                    messagebox.showinfo("Success", f"Updated preset: {selected}")
                    edit_window.destroy()
                else:
                    messagebox.showerror("Error", f"Failed to update preset: {selected}")
            
            save_button = ttk.Button(button_frame, text="Save Changes", command=save_changes)
            save_button.pack(side="left", padx=10)
            
            cancel_button = ttk.Button(button_frame, text="Cancel", command=edit_window.destroy)
            cancel_button.pack(side="left", padx=10)
            
            # Center the window on screen
            edit_window.update_idletasks()
            width = edit_window.winfo_width()
            height = edit_window.winfo_height()
            x = (edit_window.winfo_screenwidth() // 2) - (width // 2)
            y = (edit_window.winfo_screenheight() // 2) - (height // 2)
            edit_window.geometry(f"{width}x{height}+{x}+{y}")

    def delete_preset(self):
        """Delete an existing preset"""
        selected = self.preset_var.get()
        if selected == "Select a preset...":
            messagebox.showwarning("No Selection", "Please select a preset to delete.")
            return
        
        if messagebox.askyesno("Delete Preset", f"Are you sure you want to delete preset '{selected}'?"):
            try:
                preset_file = os.path.join(PRESETS_DIR, f"{selected}.json")
                if os.path.exists(preset_file):
                    os.remove(preset_file)
                    self.refresh_presets_list()
                    messagebox.showinfo("Success", f"Deleted preset: {selected}")
                else:
                    messagebox.showerror("Error", f"Preset file not found: {selected}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete preset: {e}")

    def on_preset_selected(self, event=None):
        """Handle preset selection and automatically apply the selected preset"""
        selected = self.preset_var.get()
        if selected != "Select a preset...":
            # Automatically load and apply the selected preset
            preset_data = self.load_preset_from_file(selected)
            if preset_data:
                if self.apply_preset_data(preset_data):
                    print(f"Successfully applied preset: {selected}")
                else:
                    messagebox.showerror("Error", f"Failed to apply preset: {selected}")
            else:
                messagebox.showerror("Error", f"Could not load preset: {selected}")
