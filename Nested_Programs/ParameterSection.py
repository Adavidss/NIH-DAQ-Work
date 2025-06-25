import tkinter as tk
from tkinter import ttk
from Nested_Programs.ToolTip import ToolTip          # Ensure correct import path
from Nested_Programs.Utility_Functions import get_value  # Ensure correct import path


# ==== PARAMETER SECTION CLASS ==============================
class ParameterSection:
    """Manages all parameter input fields, tooltips, and value conversion."""

    def __init__(self, parent, master_frame):
        self.parent = parent              # Parent SABREGUI instance
        self.master_frame = master_frame  # Frame where parameters are placed
        self.entries = {}                 # {label : tk.Entry}
        self.units = {}                   # {label : tk.StringVar}

        # Create the General‐parameter inputs immediately        self._create_general_parameters()

    # ---------- UI BUILDERS -------------------------------------------------
    def _create_general_parameters(self):
        """Create the General-Parameters section."""
        general_frame = ttk.LabelFrame(self.master_frame,
                                       text="General Parameters",
                                       padding=10)
        general_frame.pack(fill="x", padx=5, pady=5)

        self._create_advanced_input(general_frame, "Bubbling Time",
                                    "bubbling_time_entry")
        self._create_advanced_input(general_frame, "Magnetic Field",
                                    "magnetic_field_entry",
                                    units=["T", "mT", "µT"])
        self._create_advanced_input(general_frame, "Temperature",
                                    "temperature_entry",
                                    units=["K", "C", "F"])
        self._create_advanced_input(general_frame, "Flow Rate",
                                    "flow_rate_entry",
                                    units=["sccm"])
        self._create_advanced_input(general_frame, "Pressure",
                                    "pressure_entry",                                    units=["psi", "bar", "atm"])

    def _create_advanced_input(self, parent, label_text,
                               entry_attr, units=None):
        """Build a label + entry + unit-dropdown row with fully editable units."""
        frame = tk.Frame(parent, bg="#d9d9d9")
        frame.pack(fill="x", padx=5, pady=2)

        label = tk.Label(frame, text=label_text, width=25,
                 anchor="w", bg="#d9d9d9")
        label.pack(side="left")

        entry = tk.Entry(frame, width=10, bg="#d9d9d9")
        entry.pack(side="left")

        if units is None:                                   # default time units
            units = ["sec", "min", "ms"]
        unit_var = tk.StringVar(value=units[0])
        
        # Make units combobox fully editable (not readonly)
        unit_combo = ttk.Combobox(frame, textvariable=unit_var,
                     values=units, width=12,
                     state="normal")  # Changed from "readonly" to "normal"
        unit_combo.pack(side="left")

        # Tooltips on label, entry, and unit combobox
        tooltip = self._get_tooltip_text(label_text)
        ToolTip(label, tooltip, parent=self.parent)
        ToolTip(entry, tooltip + "\n\nEnter numerical value for this parameter.", parent=self.parent)
        ToolTip(unit_combo, f"Select or type the unit for {label_text}.\nSupported units: {', '.join(units)}", parent=self.parent)

        # Store references
        setattr(self.parent, entry_attr, entry)
        setattr(self.parent, f"{entry_attr}_unit", unit_var)
        self.entries[label_text] = entry
        self.units[label_text] = unit_var
        # For backward compatibility
        if not hasattr(self.parent, 'entries'):
            self.parent.entries = {}
        if not hasattr(self.parent, 'units'):
            self.parent.units = {}
        self.parent.entries[label_text] = entry
        self.parent.units[label_text] = unit_var
        
        # Bind change events for syncing with main tab
        entry.bind('<KeyRelease>', lambda e, lbl=label_text: self._sync_to_main(lbl))
        unit_combo.bind('<<ComboboxSelected>>', lambda e, lbl=label_text: self._sync_to_main(lbl))
        unit_combo.bind('<KeyRelease>', lambda e, lbl=label_text: self._sync_to_main(lbl))  # For manual typing

    def _sync_to_main(self, parameter_name):
        """Sync parameter values from advanced tab to main tab"""
        try:
            if hasattr(self.parent, '_sync_from_advanced'):
                self.parent._sync_from_advanced(parameter_name)
        except Exception as e:
            print(f"Error syncing to main {parameter_name}: {e}")

    def create_valve_timing_section(self, parent):
        """Create Valve-Timing configuration section."""
        valve_frame = ttk.LabelFrame(parent, text="Valve Timing Configuration",
                                     padding=10)
        valve_frame.pack(fill="x", padx=5, pady=5)

        self._create_advanced_input(valve_frame, "Valve Control Timing",
                                    "valve_time_entry")
        self._create_advanced_input(valve_frame, "Degassing Time",
                                    "degassing_time_entry")
        self._create_advanced_input(valve_frame, "Injection Time",
                                    "injection_time_entry")
        self._create_advanced_input(valve_frame, "Transfer Time",
                                    "transfer_time_entry")
        self._create_advanced_input(valve_frame, "Recycle Time",
                                    "recycle_time_entry")

    # ---------- HELPERS -----------------------------------------------------
    @staticmethod
    def _get_tooltip_text(label_text):
        """Return tooltip text for each input field."""
        tooltips = {
            "Bubbling Time": "Duration for bubbling with parahydrogen gas.",
            "Magnetic Field": "Magnetic-field strength during transfer.",
            "Temperature": "Sample temperature during the experiment.",
            "Flow Rate": "Gas flow in standard cm³/min (sccm).",
            "Pressure": "System pressure (psi/bar/atm).",
            "Valve Control Timing": "Time allowed for valve transitions.",
            "Degassing Time": "Time to remove dissolved gases (e.g., O₂).",
            "Injection Time": "Time for sample injection.",
            "Transfer Time": "Time to move hyperpolarized sample to NMR.",
            "Recycle Time": "System reset/cleaning interval."
        }
        return tooltips.get(label_text, f"Enter value for {label_text}")

    # ---------- VALUE ACCESSORS --------------------------------------------
    def get_value(self, entry_attr, conversion_type="time"):
        """Return value from entry with unit conversion."""
        entry = getattr(self.parent, entry_attr)
        unit_var = getattr(self.parent, f"{entry_attr}_unit")
        return get_value(entry, unit_var, conversion_type)

    def get_current_parameters(self):
        """Return all current parameter values in a nested dictionary."""
        parameters = {"general": {}, "advanced": {}}

        # General parameters
        for param, entry in self.entries.items():
            parameters["general"][param] = {
                "value": entry.get(),
                "unit": self.units[param].get()
            }

        # Advanced (valve-timing) parameters – only if attributes exist
        advanced_map = {
            "Valve Control Timing": ("valve_time_entry",
                                     "valve_time_entry_unit"),
            "Degassing Time": ("degassing_time_entry",
                               "degassing_time_entry_unit"),
            "Injection Time": ("injection_time_entry",
                               "injection_time_entry_unit"),
            "Transfer Time": ("transfer_time_entry",
                              "transfer_time_entry_unit"),
            "Recycle Time": ("recycle_time_entry",
                             "recycle_time_entry_unit"),
        }

        for label, (attr_entry, attr_unit) in advanced_map.items():
            if hasattr(self.parent, attr_entry):  # created only after valve section
                entry = getattr(self.parent, attr_entry)
                unit_var = getattr(self.parent, attr_unit)
                parameters["advanced"][label] = {
                    "value": entry.get(),
                    "unit": unit_var.get()
                }

        return parameters