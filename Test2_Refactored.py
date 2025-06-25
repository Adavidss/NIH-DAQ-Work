import csv
import json
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import winsound
from functools import partial

import matplotlib.pyplot as plt
import nidaqmx
from nidaqmx.constants import AcquisitionType
from nidaqmx.stream_writers import AnalogSingleChannelWriter
import numpy as np

# Set up path for nested programs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Nested_Programs"))

# Import of controller classes
from Nested_Programs.WindowManager import WindowManager
from Nested_Programs.PresetController import PresetController
from Nested_Programs.WaveformController import WaveformController
from Nested_Programs.CountdownController import CountdownController
from Nested_Programs.WidgetSynchronizer import WidgetSynchronizer
from Nested_Programs.TooltipManager import TooltipManager
from Nested_Programs.ThemeManager import ThemeManager
from Nested_Programs.DAQController import DAQController
from Nested_Programs.StateManager import StateManager
from Nested_Programs.PlotController import PlotController
from Nested_Programs.UIManager import UIManager
from Nested_Programs.MethodManager import MethodManager
from Nested_Programs.TimerWidget import TimerWidget

# Import utility modules
from Nested_Programs.Utility_Functions import (
    build_composite_waveform,
    ensure_default_state_files,
    get_value as convert_value
)

from Nested_Programs.Constants_Paths import (
    BASE_DIR,
    CONFIG_DIR,
    DAQ_DEVICE,
    DIO_CHANNELS,
    STATE_MAPPING
)
from Nested_Programs.TestPanels_AI_AO import AnalogInputPanel, AnalogOutputPanel
from Nested_Programs.Virtual_Testing_Panel import VirtualTestingPanel
from Nested_Programs.FullFlowSystem import FullFlowSystem
from Nested_Programs.SLIC_Control import SLICSequenceControl
from Nested_Programs.ScramController import ScramController
from Nested_Programs.Polarization_Calc import PolarizationApp

# Import custom classes
from Nested_Programs.ToolTip import ToolTip
from Nested_Programs.ParameterSection import ParameterSection
from Nested_Programs.PresetManager import PresetManager
from Nested_Programs.VisualAspects import VisualAspects

# Import presets directory path from constants
from Nested_Programs.Constants_Paths import PRESETS_DIR

try:
    # Initialize state files
    ensure_default_state_files()
    # Ensure presets directory exists
    if not os.path.exists(PRESETS_DIR):
        os.makedirs(PRESETS_DIR)
except Exception as e:
    print(f"Error creating config directory and files: {e}")
    sys.exit(1)


class TabManager:
    """Manages tab creation and organization"""
    def __init__(self, parent):
        self.parent = parent
        self.tabs = {}
        
    def build_dashboard_tabs(self):
        """Build the main dashboard with multiple tabs"""
        print("Building dashboard tabs...")
        
        # Create Main tab
        print("Creating Main tab...")
        main_frame = ttk.Frame(self.parent.notebook)
        self.parent.notebook.add(main_frame, text="Main")
        self.tabs["Main"] = main_frame
        self.create_main_tab(main_frame)
        print("Main tab created successfully")
        
        # Create Advanced Parameters tab
        print("Creating Advanced Parameters tab...")
        advanced_frame = ttk.Frame(self.parent.notebook)
        self.parent.notebook.add(advanced_frame, text="Advanced Parameters")
        self.tabs["Advanced Parameters"] = advanced_frame
        self.create_advanced_tab(advanced_frame)
        print("Advanced Parameters tab created successfully")
        
        # Create Testing tab
        print("Creating Testing tab...")
        testing_frame = ttk.Frame(self.parent.notebook)
        self.parent.notebook.add(testing_frame, text="Testing")
        self.tabs["Testing"] = testing_frame
        self.create_testing_tab(testing_frame)
        print("Testing tab created successfully")
        
        # Create SLIC Control tab
        print("Creating SLIC Control tab...")
        slic_frame = ttk.Frame(self.parent.notebook)
        self.parent.notebook.add(slic_frame, text="SLIC Control")
        self.tabs["SLIC Control"] = slic_frame
        self.create_slic_tab(slic_frame)
        print("SLIC Control tab created successfully")
        
        # Create Polarization Calculator tab
        print("Creating Polarization Calculator tab...")
        pol_frame = ttk.Frame(self.parent.notebook)
        self.parent.notebook.add(pol_frame, text="% Polarization Calc")
        self.tabs["% Polarization Calc"] = pol_frame
        self.create_polarization_tab(pol_frame)
        print("Polarization Calculator tab created successfully")
        print("All tabs created successfully!")
        
        # Initialize tooltips for all tabs after creation
        self.parent.after(100, self._initialize_all_tooltips)
        
    def _initialize_all_tooltips(self):
        """Initialize tooltips for all embedded panels after they're fully created"""
        try:
            # Add tooltips to Virtual Testing panel
            if hasattr(self.parent, 'embedded_virtual_panel') and self.parent.embedded_virtual_panel:
                self.parent._add_virtual_testing_tooltips(self.parent.embedded_virtual_panel)
                
            # Add tooltips to Full Flow System panel
            if hasattr(self.parent, 'embedded_full_flow') and self.parent.embedded_full_flow:
                self.parent._add_full_flow_tooltips(self.parent.embedded_full_flow)
                
            # Add tooltips to SLIC Control panel
            if hasattr(self.parent, 'embedded_slic_panel') and self.parent.embedded_slic_panel:
                self.parent._add_slic_control_tooltips(self.parent.embedded_slic_panel)
                        
            # Add tooltips to Polarization Calculator panel  
            if hasattr(self.parent, 'embedded_polarization_panel') and self.parent.embedded_polarization_panel:
                self.parent._add_polarization_calc_tooltips(self.parent.embedded_polarization_panel)
                        
            # Add tooltips to Analog Input/Output panels
            if hasattr(self.parent, 'embedded_ai_panel') and self.parent.embedded_ai_panel:
                self.parent._add_analog_input_tooltips(self.parent.embedded_ai_panel)
                
            if hasattr(self.parent, 'embedded_ao_panel') and self.parent.embedded_ao_panel:
                self.parent._add_analog_output_tooltips(self.parent.embedded_ao_panel)
                        
        except Exception as e:
            print(f"Error initializing tooltips: {e}")
        
    def create_main_tab(self, parent, detached=False):
        """Create the main control tab with key controls and previews"""
        # Configure grid with different row weights to make boxes more compact
        parent.columnconfigure((0, 1), weight=1, uniform="col")
        parent.rowconfigure(0, weight=0)  # Top row shrinks to fit content
        parent.rowconfigure(1, weight=1)  # Bottom row takes remaining space
        
        # General Configuration section (top-left) - compact
        gen_cfg = ttk.LabelFrame(parent, text="General Configuration", padding="5")
        gen_cfg.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.create_general_params_preview(gen_cfg)
        
        # Waveform Live View (bottom-left)
        waveform_frame = ttk.LabelFrame(parent, text="Waveform Live View")
        waveform_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.create_waveform_live_view_main(waveform_frame)

        # Method Selection and Experiment Controls section (top-right) - compact
        method_control_frame = ttk.LabelFrame(parent, text="Experimental Controls", padding="5")
        method_control_frame.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.create_method_and_control_section(method_control_frame)
        
        # Magnetic Field Live View (bottom-right)
        magnetic_frame = ttk.LabelFrame(parent, text="Magnetic Field Live View")
        magnetic_frame.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        self.create_magnetic_field_live_view_main(magnetic_frame)
    
    def create_advanced_tab(self, parent, detached=False):
        """Create the advanced parameters tab"""
        # Create scrollable frame for advanced parameters
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add Polarization Method controls
        self.create_polarization_method_section(scrollable_frame)
        
        # Initialize parameter section in advanced tab
        self.parent.parameter_section = ParameterSection(self.parent, scrollable_frame)
        
        # Create valve timing section
        self.parent.parameter_section.create_valve_timing_section(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def create_testing_tab(self, parent):
        """Create the testing tab with fully embedded testing panels"""
        # Create notebook for different testing panels
        testing_notebook = ttk.Notebook(parent)
        testing_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Add tooltip to the testing notebook itself
        try:
            from Nested_Programs.ToolTip import ToolTip
            ToolTip(testing_notebook, 
                   "TESTING ENVIRONMENT: Multiple testing interfaces for the SABRE system.\n"
                   "• Virtual Testing: Visual valve control and system monitoring\n"
                   "• Full Flow System: Complete flow path visualization\n"
                   "• Analog Input: Real-time sensor data monitoring\n"
                   "• Analog Output: Manual control of analog outputs", 
                   parent=self.parent)
        except Exception as e:
            print(f"Error adding testing notebook tooltip: {e}")
        
        # Virtual Testing panel - Fully embedded
        vt_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(vt_frame, text="Virtual Testing Environment")
        
        # Embed the full VirtualTestingPanel directly
        try:
            self.parent.embedded_virtual_panel = VirtualTestingPanel(self.parent, embedded=True, container=vt_frame)
            self.parent.embedded_virtual_panel.pack(fill="both", expand=True)
            
        except Exception as e:
            error_label = tk.Label(vt_frame, text=f"Virtual Testing Panel Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
        
        # Full Flow System panel - Fully embedded
        ff_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ff_frame, text="Full Flow System")
        
        try:
            self.parent.embedded_full_flow = FullFlowSystem(self.parent, embedded=True)
            self.parent.embedded_full_flow.pack(fill="both", expand=True, in_=ff_frame)
            
        except Exception as e:
            error_label = tk.Label(ff_frame, text=f"Full Flow System Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
        
        # Analog I/O panels
        ai_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ai_frame, text="Analog Input")
        ai_panel = AnalogInputPanel(ai_frame, embedded=True)
        ai_panel.pack(fill="both", expand=True)
        
        # Store reference for tooltip initialization
        self.parent.embedded_ai_panel = ai_panel
        
        ao_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ao_frame, text="Analog Output")
        ao_panel = AnalogOutputPanel(ao_frame, embedded=True)
        ao_panel.pack(fill="both", expand=True)
        
        # Store reference for tooltip initialization
        self.parent.embedded_ao_panel = ao_panel
        
    def create_slic_tab(self, parent):
        """Create the SLIC control tab"""
        try:
            slic_panel = SLICSequenceControl(parent, embedded=True)
            slic_panel.pack(fill="both", expand=True)
            
            # Store reference for tooltip initialization
            self.parent.embedded_slic_panel = slic_panel
            
        except Exception as e:
            error_label = tk.Label(parent, text=f"SLIC Control Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
            
    def create_polarization_tab(self, parent):
        """Create the polarization calculator tab"""
        try:
            pol_panel = PolarizationApp(parent, embedded=True)
            pol_panel.pack(fill="both", expand=True)
            
            # Store reference for tooltip initialization
            self.parent.embedded_polarization_panel = pol_panel
            
        except Exception as e:
            error_label = tk.Label(parent, text=f"Polarization Calculator Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
            
    def create_waveform_live_view_main(self, parent):
        """Create the waveform live view for the Main tab"""
        # Create a frame for the waveform section
        waveform_container = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
        waveform_container.pack(fill="both", expand=True, padx=2, pady=2)

        # Create header frame for title and toggle button
        header_frame = tk.Frame(waveform_container, bg=self.parent.theme_manager.color("frame_bg"))
        header_frame.pack(fill="x", pady=(0, 2))

        # Add title and refresh button side by side
        tk.Label(header_frame, text="Live Waveform", font=("Arial", 10, "bold"), 
                bg=self.parent.theme_manager.color("label_bg"), 
                fg=self.parent.theme_manager.color("label_fg")).pack(side="left")
        refresh_btn = ttk.Button(header_frame, text="Refresh", command=self.parent._refresh_live_waveform)
        refresh_btn.pack(side="right", padx=1)

        # Create the plot container frame
        plot_container = tk.Frame(waveform_container, bg=self.parent.theme_manager.color("frame_bg"), height=120)
        plot_container.pack(fill="both", expand=True)
        plot_container.pack_propagate(False)

        # Create simple matplotlib figure for main tab
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Create smaller figure for main tab
            fig, ax = plt.subplots(figsize=(4, 2))
            fig.patch.set_facecolor(self.parent.theme_manager.color("plot_bg"))
            ax.set_facecolor(self.parent.theme_manager.color("plot_bg"))
            ax.tick_params(colors=self.parent.theme_manager.color("fg"), labelsize=8)
            ax.set_xlabel("Time (s)", color=self.parent.theme_manager.color("fg"), fontsize=8)
            ax.set_ylabel("Voltage (V)", color=self.parent.theme_manager.color("fg"), fontsize=8)
            ax.set_title("Live Waveform", color=self.parent.theme_manager.color("fg"), fontsize=9)
            ax.grid(True, color=self.parent.theme_manager.color("grid_color"), alpha=0.3)
            # Set spine colors
            for spine in ax.spines.values():
                spine.set_color(self.parent.theme_manager.color("fg"))
            
            # Store figure reference for main tab
            self.parent.main_fig = fig
            self.parent.main_ax = ax
            
            # Embed in Tkinter
            canvas = FigureCanvasTkAgg(fig, master=plot_container)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)
            
            # Store canvas reference
            self.parent.main_canvas = canvas
            # Update plot controller references
            self.parent.plot_controller.main_fig = fig
            self.parent.plot_controller.main_ax = ax  
            self.parent.plot_controller.main_canvas = canvas
            
            # Add tooltip to waveform plot
            self._add_plot_tooltip(canvas_widget, "waveform")
            
            # Plot initial waveform if method is already selected
            self.parent.after(100, self.parent._refresh_live_waveform)
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(plot_container, 
                                    text="Waveform Display\n(Matplotlib required)", 
                                    fg=self.parent.theme_manager.color("label_fg"), 
                                    bg=self.parent.theme_manager.color("label_bg"), 
                                    font=("Arial", 9))
            fallback_label.pack(expand=True)

    def create_magnetic_field_live_view_main(self, parent):
        """Create the magnetic field live view for the Main tab"""
        # Create a frame for the magnetic field section
        field_container = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
        field_container.pack(fill="both", expand=True, padx=2, pady=2)

        # Create header frame
        header_frame = tk.Frame(field_container, bg=self.parent.theme_manager.color("frame_bg"))
        header_frame.pack(fill="x", pady=(0, 2))

        # Add title
        tk.Label(header_frame, text="Live Field", font=("Arial", 10, "bold"), 
                bg=self.parent.theme_manager.color("label_bg"),
                fg=self.parent.theme_manager.color("label_fg")).pack(side="left")
        
        # Current reading display
        self.parent.field_value_label = tk.Label(header_frame, text="0.0 mT", 
                                         font=("Arial", 9, "bold"), fg="blue", 
                                         bg=self.parent.theme_manager.color("label_bg"))
        self.parent.field_value_label.pack(side="right")

        # Create the display container
        display_container = tk.Frame(field_container, bg=self.parent.theme_manager.color("frame_bg"), height=120)
        display_container.pack(fill="both", expand=True)
        display_container.pack_propagate(False)

        # Create simple field monitor display
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Create smaller figure for field monitoring
            fig, ax = plt.subplots(figsize=(4, 2))
            fig.patch.set_facecolor(self.parent.theme_manager.color("plot_bg"))
            ax.set_facecolor(self.parent.theme_manager.color("plot_bg"))
            ax.tick_params(colors=self.parent.theme_manager.color("fg"), labelsize=8)
            ax.set_xlabel("Time (s)", color=self.parent.theme_manager.color("fg"), fontsize=8)
            ax.set_ylabel("Magnetic Field (mT)", color=self.parent.theme_manager.color("fg"), fontsize=8)
            ax.set_title("Live Magnetic Field", color=self.parent.theme_manager.color("fg"), fontsize=9)
            ax.grid(True, color=self.parent.theme_manager.color("grid_color"), alpha=0.3)
            # Set spine colors
            for spine in ax.spines.values():
                spine.set_color(self.parent.theme_manager.color("fg"))
            
            # Store figure reference for field monitoring
            self.parent.field_fig = fig
            self.parent.field_ax = ax
            # Update plot controller references
            self.parent.plot_controller.field_fig = fig
            self.parent.plot_controller.field_ax = ax
            
            # Embed in Tkinter
            canvas = FigureCanvasTkAgg(fig, master=display_container)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)
            
            # Store canvas reference
            self.parent.field_canvas = canvas
            self.parent.plot_controller.field_canvas = canvas
            
            # Add tooltip to field plot
            self._add_plot_tooltip(canvas_widget, "field")
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(display_container, 
                                    text="Magnetic Field Monitor\n(Matplotlib required)", 
                                    fg=self.parent.theme_manager.color("label_fg"), 
                                    bg=self.parent.theme_manager.color("label_bg"), 
                                    font=("Arial", 9))
            fallback_label.pack(expand=True)
            
    def create_method_and_control_section(self, parent):
        """Create merged method selection and experiment controls section - compact layout"""
        # Preset combobox at very top of Experimental Controls frame
        preset_combobox = ttk.Combobox(parent, 
                                      textvariable=self.parent.selected_preset_var,
                                      state="readonly", width=25)
        preset_combobox.bind("<<ComboboxSelected>>", self.parent.on_preset_selected_auto_fill)
        preset_combobox.pack(fill="x", padx=5, pady=(0, 2))
        self.parent.preset_combobox = preset_combobox
        
        # Three small buttons immediately under the combobox - more compact
        presets_controls = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
        presets_controls.pack(fill="x", padx=5, pady=(0, 2))
        
        save_btn = ttk.Button(presets_controls, text="Save Preset", 
                  command=self.parent.save_current_as_preset)
        save_btn.pack(side="left", padx=(0, 1))
        
        delete_btn = ttk.Button(presets_controls, text="Delete", 
                  command=self.parent.delete_selected_preset)
        delete_btn.pack(side="left", padx=1)
        
        refresh_btn = ttk.Button(presets_controls, text="Refresh", 
                  command=self.parent.refresh_preset_list)
        refresh_btn.pack(side="left", padx=1)
        
        # Add tooltips to preset controls
        self._add_preset_control_tooltips(preset_combobox, save_btn, delete_btn, refresh_btn)
        
        # Add state and timer section - improved layout with timer on right
        controls_status_frame = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
        controls_status_frame.pack(fill="x", padx=5, pady=(0, 2))
        
        # State label on the left - now shows current experiment state
        self.parent.state_display_label = ttk.Label(controls_status_frame, 
                                                   text="State: Idle", 
                                                   font=("Arial", 12, "bold"), foreground="blue")
        self.parent.state_display_label.pack(side="left", padx=(0, 5))
        
        # Add countdown timer on the right (fixed position)
        self.parent.countdown_label = tk.Label(controls_status_frame, text="00:00.000", 
                                             font=("Arial", 12, "bold"), foreground="#003366", 
                                             bg=self.parent.theme_manager.color("label_bg"))
        self.parent.countdown_label.pack(side="right", padx=(5, 0))
        
        # Create buttons frame for 2x2 grid layout - more compact
        buttons_frame = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
        buttons_frame.pack(fill="x", padx=5, pady=(0, 2))
        
        # Configure grid for quadrant layout in buttons frame
        buttons_frame.columnconfigure((0, 1), weight=1, uniform="col")
        buttons_frame.rowconfigure((0, 1), weight=1, uniform="row")

        # Create buttons in quadrant layout - larger buttons with bigger text
        activate_btn = tk.Button(buttons_frame, text="Activate", 
                                command=self.parent.activate_experiment,
                                font=('Arial', 10, 'bold'), relief="raised", bd=2,
                                width=14, height=1, bg="#2E7D32", fg="white", 
                                activebackground="#2E7D32")
        activate_btn.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        
        start_btn = tk.Button(buttons_frame, text="Start", 
                             command=self.parent.start_experiment,
                             font=('Arial', 10, 'bold'), relief="raised", bd=2,
                             width=14, height=1, bg="#1565C0", fg="white", 
                             activebackground="#1565C0")
        start_btn.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        
        test_btn = tk.Button(buttons_frame, text="Test Field", 
                            command=self.parent.test_field,
                            font=('Arial', 10, 'bold'), relief="raised", bd=2,
                            width=14, height=1, bg="#EF6C00", fg="white", 
                            activebackground="#EF6C00")
        test_btn.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        
        scram_btn = tk.Button(buttons_frame, text="SCRAM", 
                             command=self.parent.scram_experiment,
                             font=('Arial', 10, 'bold'), relief="raised", bd=2,
                             width=14, height=1, bg="#B71C1C", fg="white", 
                             activebackground="#B71C1C")
        scram_btn.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        
        # Add tooltips to control buttons
        self._add_control_button_tooltips(activate_btn, start_btn, test_btn, scram_btn)
        
        # Refresh the method list and preset list for the new comboboxes
        self.parent.refresh_method_list()
        self.parent.refresh_preset_list()
        
    def _add_control_button_tooltips(self, activate_btn, start_btn, test_btn, scram_btn):
        """Add comprehensive tooltips to control buttons"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            # Control button tooltips with detailed explanations
            ToolTip(activate_btn, 
                   "ACTIVATE: Starts the sample activation sequence.\n"
                   "• Opens valves for injection and activation\n"
                   "• Runs degassing phase to remove oxygen\n"
                   "• Activates the catalyst with parahydrogen\n"
                   "• Returns to initial state when complete", 
                   parent=self.parent)
                   
            ToolTip(start_btn, 
                   "START: Begins the main polarization experiment.\n"
                   "• Starts bubbling sequence with parahydrogen\n"
                   "• Applies selected polarization method\n"
                   "• Transfers hyperpolarized sample to NMR\n"
                   "• Includes automatic timing from method file", 
                   parent=self.parent)
                   
            ToolTip(test_btn, 
                   "TEST FIELD: Tests the polarization method only.\n"
                   "• Applies the selected polarization waveform\n"
                   "• Does not change valve positions\n"
                   "• Useful for testing magnetic field sequences\n"
                   "• Shows waveform preview in real-time", 
                   parent=self.parent)
                   
            ToolTip(scram_btn, 
                   "SCRAM: Emergency stop for all operations.\n"
                   "• Immediately stops all running sequences\n"
                   "• Sets all analog outputs to 0V\n"
                   "• Returns system to Initial_State configuration\n"
                   "• Use in case of emergency or malfunction", 
                   parent=self.parent)
                   
        except Exception as e:
            print(f"Error adding control button tooltips: {e}")
            
    def _add_plot_tooltip(self, canvas_widget, plot_type):
        """Add tooltips to plot canvases"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            if plot_type == "waveform":
                tooltip_text = ("WAVEFORM PLOT: Shows the polarization method waveform.\n"
                               "• Displays voltage vs time for the selected method\n"
                               "• Updates automatically when method is changed\n"
                               "• Shows live data during 'Test Field' operation\n"
                               "• Grey out bubbling time when method is selected")
            elif plot_type == "field":
                tooltip_text = ("MAGNETIC FIELD PLOT: Live monitoring of field strength.\n"
                               "• Real-time magnetic field measurements\n"
                               "• Current reading shown in top-right corner\n"
                               "• Tracks field changes during experiments\n"
                               "• Useful for monitoring field stability")
            else:
                tooltip_text = f"{plot_type.upper()} PLOT: Interactive data visualization"
            
            ToolTip(canvas_widget, tooltip_text, parent=self.parent)
            
        except Exception as e:
            print(f"Error adding plot tooltip: {e}")
        
    def create_general_params_preview(self, parent):
        """Create a preview of general parameters in the main tab matching advanced parameters style"""
        
        # Add a few key parameters as a preview
        params = [
            ("Activation Time", "", ["s", "min", "h"]),
            ("Bubbling Time", "", ["s", "min", "h"]),
            ("Magnetic Field", "", ["mT", "T", "G"]),
            ("Temperature", "", ["K", "°C", "°F"]),
            ("Flow Rate", "", ["sccm", "slm", "ccm"]),
            ("Pressure", "", ["atm", "bar", "psi", "Pa"])
        ]
        
        for i, (label, default_val, unit_options) in enumerate(params):
            row = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
            row.pack(fill="x", padx=5, pady=2)
            
            # Match advanced parameters styling: wider label, better spacing
            label_widget = tk.Label(row, text=label, width=20, anchor="w", 
                    bg=self.parent.theme_manager.color("label_bg"),
                    fg=self.parent.theme_manager.color("label_fg"))
            label_widget.pack(side="left")
            entry = tk.Entry(row, width=10, 
                           bg=self.parent.theme_manager.color("entry_bg"),
                           fg=self.parent.theme_manager.color("entry_fg"))
            entry.insert(0, default_val)
            entry.pack(side="left")
            
            # Store the entry in self.parent.entries for access by other methods
            self.parent.entries[label] = entry
            
            # Create StringVar for unit and store it
            unit_var = tk.StringVar(value=unit_options[0])
            self.parent.units[label] = unit_var
            
            # Create wider unit dropdown to match advanced parameters
            unit_combo = ttk.Combobox(row, textvariable=unit_var, 
                                     values=unit_options, width=12, state="normal")
            unit_combo.pack(side="left")
            
            # Add tooltips to main tab parameters
            self._add_parameter_tooltips(label_widget, entry, unit_combo, label, unit_options)
        
        # Add link to advanced parameters
        link_frame = tk.Frame(parent, bg=self.parent.theme_manager.color("frame_bg"))
        link_frame.pack(fill="x", pady=(5, 0))
        advanced_btn = ttk.Button(link_frame, text="Go to Advanced Parameters", 
                  command=lambda: self.parent.notebook.select(1))
        advanced_btn.pack()
        
        # Add tooltip to advanced parameters button
        try:
            from Nested_Programs.ToolTip import ToolTip
            ToolTip(advanced_btn, 
                   "ADVANCED PARAMETERS: Access detailed experimental settings.\n"
                   "• Configure valve timing and sequences\n"
                   "• Set polarization method parameters\n"
                   "• Manage experimental presets\n"
                   "• Advanced interface options and theming", 
                   parent=self.parent)
        except Exception as e:
            print(f"Error adding advanced button tooltip: {e}")
            
    def _add_parameter_tooltips(self, label_widget, entry, unit_combo, param_name, unit_options):
        """Add tooltips to parameter UI elements"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            # Parameter-specific tooltip texts
            tooltip_texts = {
                "Activation Time": "Duration for sample activation sequence.\nTime spent in the activation state to prepare the sample for polarization.",
                "Bubbling Time": "Duration for bubbling parahydrogen through the sample.\nNote: This will be disabled when a polarization method is selected,\nas the method file will control the timing automatically.",
                "Magnetic Field": "Magnetic field strength during the polarization process.\nUsed to control spin dynamics and polarization efficiency.",
                "Temperature": "Sample temperature during the experiment.\nAffects reaction kinetics and polarization decay rates.",
                "Flow Rate": "Gas flow rate in standard cubic centimeters per minute.\nControls the rate of parahydrogen delivery to the sample.",
                "Pressure": "System pressure during the experiment.\nAffects gas solubility and reaction conditions."
            }
            
            base_tooltip = tooltip_texts.get(param_name, f"Parameter: {param_name}")
            
            # Add tooltips to each widget
            ToolTip(label_widget, base_tooltip, parent=self.parent)
            ToolTip(entry, base_tooltip + "\n\nEnter numerical value for this parameter.", parent=self.parent)
            ToolTip(unit_combo, f"Select or type the unit for {param_name}.\nSupported units: {', '.join(unit_options)}", parent=self.parent)
            
        except Exception as e:
            print(f"Error adding parameter tooltips for {param_name}: {e}")
            
    def _add_preset_control_tooltips(self, preset_combobox, save_btn, delete_btn, refresh_btn):
        """Add comprehensive tooltips to preset control elements"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            # Preset control tooltips
            ToolTip(preset_combobox, 
                   "PRESET SELECTOR: Choose from saved parameter combinations.\n"
                   "• Select a preset to auto-fill all parameters\n"
                   "• Includes general parameters and advanced settings\n"
                   "• Automatically loads associated polarization methods\n"
                   "• Create custom presets for different experiments", 
                   parent=self.parent)
                   
            ToolTip(save_btn, 
                   "SAVE PRESET: Save current parameters as a new preset.\n"
                   "• Captures all current parameter values\n"
                   "• Includes both main and advanced tab settings\n"
                   "• Stores selected polarization method\n"
                   "• Creates reusable experimental configurations", 
                   parent=self.parent)
                   
            ToolTip(delete_btn, 
                   "DELETE PRESET: Remove the selected preset permanently.\n"
                   "• Deletes the selected preset file\n"
                   "• Cannot be undone - use with caution\n"
                   "• Will ask for confirmation before deletion\n"
                   "• Built-in presets cannot be deleted", 
                   parent=self.parent)
                   
            ToolTip(refresh_btn, 
                   "REFRESH PRESETS: Update the preset list.\n"
                   "• Scans for new preset files\n"
                   "• Updates dropdown with latest presets\n"
                   "• Use after adding presets manually\n"
                   "• Automatically sorts presets alphabetically", 
                   parent=self.parent)
                   
        except Exception as e:
            print(f"Error adding preset control tooltips: {e}")
                  
    def create_polarization_method_section(self, parent):
        """Create the polarization method configuration section with dropdown selector"""
        # Polarization Method Selection Section
        polarization_frame = ttk.LabelFrame(parent, text="Polarization Method", padding="5")
        polarization_frame.pack(fill="x", padx=5, pady=3)
        
        # Method Selection Dropdown
        method_frame = ttk.Frame(polarization_frame)
        method_frame.pack(fill="x", pady=(0, 3))
        
        ttk.Label(method_frame, text="Method:").pack(side="left")
        
        # Polarization method dropdown reading from directory
        self.parent.polarization_method_combobox = ttk.Combobox(method_frame, 
                                                        textvariable=self.parent.polarization_method_var,
                                                        state="readonly", width=25)
        
        # Load available polarization methods from directory
        polarization_methods = self.parent.method_manager.load_polarization_methods_from_directory()
        
        self.parent.polarization_method_combobox['values'] = polarization_methods
        self.parent.polarization_method_combobox.bind("<<ComboboxSelected>>", self.on_polarization_method_changed)
        self.parent.polarization_method_combobox.pack(side="left", padx=(3, 0), fill="x", expand=True)
        
        # Add refresh button next to the combobox
        refresh_button = ttk.Button(method_frame, text="Refresh", 
                                   command=self.parent.refresh_method_list)
        refresh_button.pack(side="left", padx=(3, 0))
        
        # Add check directory button
        check_dir_button = ttk.Button(method_frame, text="Check Directory", 
                                     command=self.parent._open_polarization_methods_directory)
        check_dir_button.pack(side="left", padx=(3, 0))
        
        # Toggles Section (Audio and Tooltips as requested)
        toggles_frame = ttk.LabelFrame(parent, text="Interface Settings", padding="5")
        toggles_frame.pack(fill="x", padx=5, pady=3)
        
        # Audio toggle
        audio_frame = tk.Frame(toggles_frame, bg=self.parent.theme_manager.color("frame_bg"))
        audio_frame.pack(fill="x", pady=2)
        
        self.parent.audio_enabled_checkbox = ttk.Checkbutton(audio_frame, text="Enable Audio Feedback",
                                                     variable=self.parent.audio_enabled,
                                                     command=self.on_audio_toggle)
        self.parent.audio_enabled_checkbox.pack(side="left")
        
        # Tooltip toggle
        tooltip_frame = tk.Frame(toggles_frame, bg=self.parent.theme_manager.color("frame_bg"))
        tooltip_frame.pack(fill="x", pady=2)
        
        self.parent.tooltips_enabled_checkbox = ttk.Checkbutton(tooltip_frame, text="Enable Tooltips",
                                                        variable=self.parent.tooltips_enabled)
        self.parent.tooltips_enabled_checkbox.pack(side="left")
        # Set the command after packing to avoid initial trigger
        self.parent.tooltips_enabled_checkbox.config(command=self.on_tooltip_toggle)
        
        # Theme control
        theme_frame = tk.Frame(toggles_frame, bg=self.parent.theme_manager.color("frame_bg"))
        theme_frame.pack(fill="x", pady=2)
        
        tk.Label(theme_frame, text="Theme:", 
                bg=self.parent.theme_manager.color("label_bg"),
                fg=self.parent.theme_manager.color("label_fg")).pack(side="left")
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.parent.theme_var,
                                  values=["Light", "Dark", "High-Contrast", "Normal"], 
                                  state="readonly", width=15)
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_changed)
        theme_combo.pack(side="left", padx=(5, 0))
        
    def on_polarization_method_changed(self, event=None):
        """Handle polarization method selection changes - Ultra Simple Solution"""
        try:
            selected_method = self.parent.polarization_method_var.get()
            
            if selected_method and selected_method != "Select method...":
                # Store the full path to the selected method file
                methods_dir = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
                self.parent.polarization_method_file = os.path.join(methods_dir, selected_method)
                
                # ULTRA SIMPLE SOLUTION: Just plot directly
                self._plot_method_directly(self.parent.polarization_method_file, selected_method)
                
                # Grey out bubbling time parameter when method is selected
                self._update_bubbling_time_state(disabled=True)
                
            else:
                self.parent.polarization_method_file = None
                # Re-enable bubbling time parameter when no method is selected
                self._update_bubbling_time_state(disabled=False)
                
            print(f"Polarization method changed to: {selected_method}")
            
        except Exception as e:
            print(f"Error handling polarization method change: {e}")
            
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
    
    def _plot_method_directly(self, method_file, method_name):
        """Ultra simple direct plotting - no fancy refresh logic"""
        try:
            # Load the method data
            with open(method_file, 'r') as f:
                cfg = json.load(f)
            
            # Generate waveform
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                initial_voltage = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"], initial_voltage)
            
            print(f"Generated waveform: {len(buf)} samples at {sr} Hz")
            
            # Get direct access to the plot
            main_ax = self.parent.plot_controller.main_ax
            main_canvas = self.parent.plot_controller.main_canvas
            
            # Clear and plot with consistent styling
            main_ax.clear()
            time_axis = [i / sr for i in range(len(buf))]
            main_ax.plot(time_axis, buf, 'b-', linewidth=1)
            main_ax.set_xlabel('Time (s)', color=self.parent.theme_manager.color("fg"), fontsize=8)
            main_ax.set_ylabel('Voltage (V)', color=self.parent.theme_manager.color("fg"), fontsize=8)
            main_ax.set_title(f'Polarization Method: {method_name}', color=self.parent.theme_manager.color("fg"), fontsize=9)
            main_ax.grid(True, color=self.parent.theme_manager.color("grid_color"), alpha=0.3)
            main_ax.tick_params(colors=self.parent.theme_manager.color("fg"), labelsize=8)
            # Set spine colors
            for spine in main_ax.spines.values():
                spine.set_color(self.parent.theme_manager.color("fg"))
            # Set background color
            main_ax.set_facecolor(self.parent.theme_manager.color("plot_bg"))
            
            # Force canvas update
            main_canvas.draw()
            main_canvas.flush_events()
            
            print(f"Plotted waveform directly: {method_name}")
            
        except Exception as e:
            print(f"Error in direct plotting: {e}")
    
    def on_audio_toggle(self):
        """Handle audio enable/disable toggle"""
        enabled = self.parent.audio_enabled.get()
        if enabled:
            print("Audio feedback enabled")
            # You can add audio initialization here
        else:
            print("Audio feedback disabled")
    
    def on_tooltip_toggle(self):
        """Handle tooltip enable/disable toggle"""
        enabled = self.parent.tooltips_enabled.get()
        if enabled:
            print("Tooltips enabled")
        else:
            print("Tooltips disabled")
    
    def on_theme_changed(self, event=None):
        """Handle theme selection changes"""
        selected_theme = self.parent.theme_var.get()
        print(f"Theme changed to: {selected_theme}")
        
        # Apply theme using the theme manager
        if hasattr(self.parent, 'theme_manager'):
            self.parent.theme_manager.apply_theme(selected_theme)
        else:
            print("Theme manager not available")

class ExperimentController:
    """Handles experiment sequences and state management"""
    def __init__(self, sabre_gui):
        self.gui = sabre_gui
        self.running = False
        self.stop_polarization = False
        self.scram_active = False  # Add SCRAM flag to prevent state changes after SCRAM
        # Add DAQ task management
        self.test_task = None
        self.dio_task = None
        self.task_lock = threading.Lock()
        
    def activate_experiment(self):
        """Activate the experiment sequence with proper DAQ interactions"""
        missing_params = []
        required_fields = [
            ("Activation Time", self.gui.entries.get("Activation Time")),
            ("Temperature", self.gui.entries.get("Temperature")),
            ("Flow Rate", self.gui.entries.get("Flow Rate")),
            ("Pressure", self.gui.entries.get("Pressure")),
            ("Injection Time", getattr(self.gui, 'injection_time_entry', None)),
            ("Valve Control Timing", getattr(self.gui, 'valve_time_entry', None)),
            ("Degassing Time", getattr(self.gui, 'degassing_time_entry', None)),
            ("Transfer Time", getattr(self.gui, 'transfer_time_entry', None)),
            ("Recycle Time", getattr(self.gui, 'recycle_time_entry', None)),
        ]
        for param, entry in required_fields:
            if entry is None or not entry.get():
                missing_params.append(param)
    
        if missing_params:
            self.gui.show_error_popup(missing_params)
            return
            
        # Don't automatically initialize virtual panel - only use if already exists
        
        # Set up and start the activation sequence directly in the main app
        self.running = True  # Add running flag to main app
        
        # Start the activation sequence in a separate thread
        threading.Thread(target=self.run_activation_sequence, daemon=True).start()

    def run_activation_sequence(self):
        """Run the activation sequence directly in the main app, independent of virtual panel"""
        try:
            # Load initial state with direct DAQ interaction
            config_loaded = self.load_config("Initial_State")
            if not config_loaded:
                messagebox.showerror("Error", "Failed to load initial state configuration")
                return
                
            # Update GUI state
            self.gui.set_controls_state("Activating")
            
            # Update virtual panel if it exists
            if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                self.gui.virtual_panel.load_config_visual("Initial_State")
            
            valve_duration = self.gui.get_value('valve_time_entry')
            injection_duration = self.gui.get_value('injection_time_entry')
            degassing_duration = self.gui.get_value('degassing_time_entry')
            activation_duration = self.gui.get_value('Activation Time') or 0.0

            state_sequence = [
                ("Initial_State", valve_duration),
                ("Injection_State_Start", injection_duration),
                ("Degassing", degassing_duration),
                ("Activation_State_Initial", activation_duration),
                ("Activation_State_Final", valve_duration),
                ("Initial_State", None)
            ]

            total_time = sum(duration for _, duration in state_sequence if duration)
            self.gui.start_timer(total_time)

            for state, duration in state_sequence:
                if not hasattr(self, 'running') or not self.running:
                    break
                
                # Load config and send DAQ signals
                if self.load_config(state):
                    # Update virtual panel if it exists
                    if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                        self.gui.virtual_panel.load_config_visual(state)
                    
                    # Wait for duration - hold the current state for the specified time
                    if duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and hasattr(self, 'running') and self.running:
                            time.sleep(0.1)

        except Exception as error:
            print(f"Error in activation sequence: {error}")
        finally:
            self.running = False
            # Only load Initial_State if SCRAM is not active (SCRAM handles state loading)
            if not getattr(self, 'scram_active', False):
                self.load_config("Initial_State")  # Always return to initial state
                self.gui.set_controls_state("Idle")
                # Update virtual panel if it exists
                if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                    self.gui.virtual_panel.load_config_visual("Initial_State")
            else:
                print("Activation sequence cleanup skipped - SCRAM active")

    def start_experiment(self):
        """Start the bubbling sequence with integrated method timing"""
        # always begin from a clean baseline
        self._reset_run_state()

        if not hasattr(self.gui, 'polarization_method_file') or not self.gui.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        # Ensure entries exist to prevent KeyError
        self.gui._ensure_entries_exist()

        missing_params = []
        required_fields = [
            ("Valve Control Timing", getattr(self.gui, 'valve_time_entry', None)),
            ("Transfer Time", getattr(self.gui, 'transfer_time_entry', None)),
            ("Recycle Time", getattr(self.gui, 'recycle_time_entry', None)),
        ]
        for param, entry in required_fields:
            if entry is None or not entry.get():
                missing_params.append(param)
    
        if missing_params:
            self.gui.show_error_popup(missing_params)
            return
        
        # Reset stop flag at start of experiment
        self.stop_polarization = False
        self.running = True  # Set running flag

        # Load and plot the waveform before starting the experiment
        try:
            with open(self.gui.polarization_method_file) as f:
                cfg = json.load(f)

            # Check if this is a SLIC sequence file and get buffer
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                initial_voltage = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"],
                                                 dc_offset=initial_voltage)
            
            # Plot the waveform that will be used in the experiment
            self.gui._plot_waveform_buffer(buf, sr)
            
        except Exception as e:
            print(f"Error loading waveform for plotting: {e}")
            messagebox.showerror("Error", f"Failed to load polarization method for plotting: {e}")
            return

        # Don't automatically initialize virtual panel - only use if already exists

        # Start the bubbling sequence in a separate thread
        threading.Thread(target=self.run_bubbling_sequence, daemon=True).start()

    def run_bubbling_sequence(self):
        """Run the bubbling sequence directly in the main app, independent of virtual panel"""
        try:
            # Calculate method duration first
            method_dur = self.gui._compute_polarization_duration()
            
            # Get timing parameters
            valve = self.gui.get_value("valve_time_entry") or 0.0
            transfer = self.gui.get_value("transfer_time_entry") or 0.0
            recycle = self.gui.get_value("recycle_time_entry") or 0.0
            bubbling_time = method_dur if method_dur > 0 else self.gui.get_value('bubbling_time_entry')

            # Total experiment time: method duration + valve transitions + transfer + recycle
            total_time = method_dur + (valve * 3) + transfer + recycle
            
            # Start the timer with total duration
            self.gui.start_timer(total_time)
            
            # Start plotting without resetting the existing plot
            if hasattr(self.gui, 'plotting'):
                self.gui.plotting = True
            
            # Load bubbling state with direct DAQ interaction
            config_loaded = self.load_config("Bubbling_State_Initial")
            if not config_loaded:
                messagebox.showerror("Error", "Failed to load bubbling state configuration")
                self.gui.stop_timer()
                return
                
            self.gui.set_controls_state("Bubbling the Sample")
            
            # Update virtual panel if it exists
            if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                self.gui.virtual_panel.load_config_visual("Bubbling_State_Initial")
            
            # Run polarization method after a delay
            def delayed_method():
                try:
                    print(f"Waiting {valve * 2} seconds for bubbling valves to stabilize")
                    time.sleep(valve * 2)  # Wait for bubbling valves to stabilize
                    
                    if hasattr(self, 'running') and self.running and not self.stop_polarization:
                        print("Starting polarization method execution")
                        self.run_polarization_method()
                except Exception as e:
                    print(f"Error in delayed method execution: {e}")

            threading.Thread(target=delayed_method, daemon=True).start()
            
            # Wait for bubbling time
            if bubbling_time > 0:
                start_time = time.time()
                while time.time() - start_time < bubbling_time and hasattr(self, 'running') and self.running and not self.stop_polarization:
                    time.sleep(0.1)
            
            # Continue with the rest of the sequence if still running
            if hasattr(self, 'running') and self.running and not self.stop_polarization:
                # Execute the remaining states in sequence
                remaining_states = [
                    ("Bubbling_State_Final", valve),
                    ("Transfer_Initial", valve),
                    ("Transfer_Final", valve),
                    ("Recycle", recycle),
                    ("Initial_State", None)
                ]
                
                for state, duration in remaining_states:
                    if not hasattr(self, 'running') or not self.running or self.stop_polarization:
                        break
                    
                    if self.load_config(state):
                        # Update virtual panel if it exists
                        if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                            self.gui.virtual_panel.load_config_visual(state)
                        
                        # Wait for duration - hold the current state for the specified time
                        if duration:
                            start_time = time.time()
                            while time.time() - start_time < duration and hasattr(self, 'running') and self.running and not self.stop_polarization:
                                time.sleep(0.1)
            
        except Exception as error:
            print(f"Error in bubbling sequence: {error}")
        finally:
            self.running = False
            # Only load Initial_State if SCRAM is not active and not already stopped
            if not self.stop_polarization and not getattr(self, 'scram_active', False):
                self.load_config("Initial_State")  # Return to initial state
                # Update virtual panel if it exists
                if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                    self.gui.virtual_panel.load_config_visual("Initial_State")
            else:
                if getattr(self, 'scram_active', False):
                    print("Bubbling sequence cleanup skipped - SCRAM active")
                else:
                    print("Bubbling sequence cleanup skipped - already stopped by SCRAM")

    def run_polarization_method(self):
        """Execute the selected polarization method during experiment sequence"""
        if not hasattr(self.gui, 'polarization_method_file') or not self.gui.polarization_method_file or self.stop_polarization:
            print("Polarization method execution canceled - no file or stop flag set")
            return

        print(f"Running polarization method: {self.gui.polarization_method_file}")
        
        with self.task_lock:  # Ensure exclusive access to task resources
            try:
                # Clean up any existing tasks first
                self.cleanup_tasks()
                
                # Ensure any existing task is closed
                if self.test_task:
                    try:
                        self.test_task.close()
                    except Exception as e:
                        print(f"Error closing existing test task: {e}")
                    self.test_task = None
                
                # Add a delay to ensure resources are released
                time.sleep(0.2)
                
                if self.stop_polarization:  # Check if stopped before starting
                    return
                
                # Load and validate polarization method file
                if not os.path.exists(self.gui.polarization_method_file):
                    raise FileNotFoundError(f"Polarization method file not found: {self.gui.polarization_method_file}")
                    
                with open(self.gui.polarization_method_file) as f:
                    cfg = json.load(f)

                # Check if this is a SLIC sequence file and get buffer
                if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                    buf, sr = build_composite_waveform(cfg)
                    daq_channel = "Dev1/ao1"
                    voltage_range = {"min": -10.0, "max": 10.0}
                else:
                    daq_channel = cfg.get("daq_channel", "Dev1/ao1")
                    voltage_range = cfg.get("voltage_range", {"min": -10.0, "max": 10.0})
                    initial_voltage = cfg.get("initial_voltage", 0.0)
                    buf, sr = build_composite_waveform(cfg["ramp_sequences"],
                                                     dc_offset=initial_voltage)

                # Update the state label
                self.gui.set_controls_state("Polarizing Sample")
                print(f"Polarization method loaded: buffer length={len(buf)}, sample rate={sr}")

                # Configure and run DAQ task for the experiment
                self.test_task = nidaqmx.Task()
                task_started = False
                
                try:
                    self.test_task.ao_channels.add_ao_voltage_chan(
                            daq_channel,
                            min_val=voltage_range["min"],
                            max_val=voltage_range["max"])

                    self.test_task.timing.cfg_samp_clk_timing(
                            sr,
                            sample_mode=AcquisitionType.FINITE,
                            samps_per_chan=len(buf))

                    writer = AnalogSingleChannelWriter(self.test_task.out_stream)
                    writer.write_many_sample(buf)
                    self.test_task.start()
                    task_started = True
                    print("Polarization method task started successfully")

                    # Wait for method to complete with timeout
                    method_duration = len(buf) / sr
                    print(f"Waiting for method to complete: {method_duration} seconds")
                    self.test_task.wait_until_done(timeout=method_duration + 2.0)
                    print("Polarization method completed")
                    
                    # When method completes, proceed to transfer state
                    if not self.stop_polarization:
                        print("Transitioning to transfer state")
                        self.load_config("Transfer_Initial")
                        if hasattr(self.gui, 'state_label'):
                            self.gui.state_label.config(text="State: Transferring the Sample")
                        
                        # Allow time for transfer
                        transfer_time = self.gui.get_value("transfer_time_entry") or 0.0
                        print(f"Waiting for transfer: {transfer_time} seconds")
                        time.sleep(transfer_time)
                        
                        # After transfer, proceed to recycle state
                        if not self.stop_polarization:
                            print("Transitioning to recycle state")
                            self.load_config("Recycle")
                            if hasattr(self.gui, 'state_label'):
                                self.gui.state_label.config(text="State: Recycling Solution")

                finally:
                    if self.test_task:
                        try:
                            # Only try to write 0V if the task was started successfully
                            if task_started and self.test_task.is_task_done():
                                self.test_task.write(0.0)  # Set to 0V before closing
                                print("Task completed and voltage set to 0V")
                            self.test_task.close()
                            print("Test task closed")
                        except Exception as e:
                            print(f"Error cleaning up test task: {e}")
                    self.test_task = None

            except Exception as e:
                print(f"Error in run_polarization_method: {e}")
                if not self.stop_polarization:
                    messagebox.showerror("Error",
                        f"Failed to execute polarization method:\n{e}")
            finally:
                # Always try to set voltage to zero after method completes
                try:
                    self.set_voltage_to_zero()
                    print("Final voltage reset to zero")
                except Exception as e:
                    print(f"Error zeroing voltage after polarization: {e}")

    def _write_analog_waveform(self, data, rate, continuous=False):
        """
        Write a numpy 1-D array to an AO channel with hardware timing.
        If continuous=True the buffer regenerates until you stop the task.
        """
        if not self.test_task:
            print("Error: No test task available for waveform writing")
            return False
            
        try:
            import nidaqmx.constants as C
            from nidaqmx.stream_writers import AnalogSingleChannelWriter

            mode = (C.AcquisitionType.CONTINUOUS
                    if continuous else C.AcquisitionType.FINITE)
            self.test_task.timing.cfg_samp_clk_timing(
                rate,
                sample_mode=mode,
                samps_per_chan=len(data)
            )
            writer = AnalogSingleChannelWriter(self.test_task.out_stream)
            writer.write_many_sample(data)
            self.test_task.start()
            return True
        except Exception as e:
            print(f"Error writing analog waveform: {e}")
            if self.test_task:
                try:
                    self.test_task.close()
                except:
                    pass
                self.test_task = None
            return False

    def test_field(self):
        """Load the polarization method and send it to ao1 with proper DAQ interaction"""
        if not hasattr(self.gui, 'polarization_method_file') or not self.gui.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        print(f"Test Field activated - Loading method from: {self.gui.polarization_method_file}")
        
        # Load and plot the waveform on the main thread first
        try:
            with open(self.gui.polarization_method_file) as f:
                cfg = json.load(f)

            # Check if this is a SLIC sequence file and get buffer
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                initial_voltage = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"],
                                                 dc_offset=initial_voltage)
            
            # Calculate method duration and start timer on main thread
            method_duration = len(buf) / sr
            self.gui.start_timer(method_duration)
            
            # Plot the waveform on the main thread
            self.gui._plot_waveform_buffer(buf, sr)
            
        except Exception as e:
            print(f"Error loading waveform for plotting: {e}")
            messagebox.showerror("Error", f"Failed to load polarization method for plotting: {e}")
            return  # Just return, don't try to stop timer that may not exist
        
        def run_test_field():
            # ensure clean state before launching the task (but don't clear plot)
            self._reset_run_state(clear_plot=False)

            task_started = False
            with self.task_lock:  # Ensure exclusive access to task resources
                try:
                    # Clean up any existing tasks first
                    self.cleanup_tasks()
                    
                    # Ensure any existing task is closed
                    if self.test_task:
                        try:
                            self.test_task.close()
                        except Exception as e:
                            print(f"Error closing existing test task: {e}")
                        self.test_task = None
                    
                    # Add a delay to ensure resources are released
                    time.sleep(0.2)
                    
                    if self.stop_polarization:  # Check if stopped before starting
                        return
                        
                    # Reload the config (we already validated it exists above)
                    with open(self.gui.polarization_method_file) as f:
                        cfg = json.load(f)

                    # Check if this is a SLIC sequence file and get buffer
                    if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                        buf, sr = build_composite_waveform(cfg)
                        daq_channel = "Dev1/ao1"
                        voltage_range = {"min": -10.0, "max": 10.0}
                    else:
                        daq_channel = cfg.get("daq_channel", "Dev1/ao1")
                        voltage_range = cfg.get("voltage_range", {"min": -10.0, "max": 10.0})
                        initial_voltage = cfg.get("initial_voltage", 0.0)
                        buf, sr = build_composite_waveform(cfg["ramp_sequences"],
                                                         dc_offset=initial_voltage)

                    # Configure and run DAQ task
                    self.test_task = nidaqmx.Task()
                    try:
                        self.test_task.ao_channels.add_ao_voltage_chan(
                                daq_channel,
                                min_val=voltage_range["min"],
                                max_val=voltage_range["max"])

                        self.test_task.timing.cfg_samp_clk_timing(
                                sr,
                                sample_mode=AcquisitionType.FINITE,
                                samps_per_chan=len(buf))

                        writer = AnalogSingleChannelWriter(self.test_task.out_stream)
                        writer.write_many_sample(buf)
                        self.test_task.start()
                        task_started = True

                        method_duration = len(buf) / sr
                        self.test_task.wait_until_done(timeout=method_duration + 2.0)

                    finally:
                        if self.test_task:
                            try:
                                # Only try to write 0V if the task was started successfully
                                if task_started and self.test_task.is_task_done():
                                    self.test_task.write(0.0)  # Set to 0V before closing
                                self.test_task.close()
                            except Exception as e:
                                print(f"Error cleaning up test task: {e}")
                        self.test_task = None

                except Exception as e:
                    if not self.stop_polarization:
                        messagebox.showerror("Error",
                            f"Failed to send polarization method to ao1:\n{e}")
                finally:
                    # Always try to set voltage to zero after test is complete
                    try:
                        self.set_voltage_to_zero()
                    except Exception as e:
                        print(f"Error zeroing voltage after test: {e}")
        
        # Run the test field in a separate thread
        threading.Thread(target=run_test_field, daemon=True).start()

    def scram_experiment(self):
        """Instant emergency stop with proper DAQ interaction."""
        print("EMERGENCY STOP ACTIVATED")
        # Stop timer
        self.gui.stop_timer()
        self.gui.reset_timer()
        
        # Stop polarization and running flag
        self.stop_polarization = True
        if hasattr(self, 'running'):
            self.running = False  # Added flag to stop sequences
        
        # Use comprehensive cleanup to handle emergency stop
        self.cleanup_tasks()
        
        # Reset state label
        if hasattr(self.gui, 'state_label'):
            self.gui.state_label.config(text="State: EMERGENCY STOP")
        
        # Don't load any state during SCRAM - cleanup_tasks() already handles voltage zeroing
        # Loading a state would send unwanted DIO signals during emergency stop
        print("SCRAM complete - all tasks cleaned up, voltage set to 0V")
        
        # Alert user
        if hasattr(self.gui, 'audio_enabled') and self.gui.audio_enabled.get():
            try:
                winsound.Beep(2000, 100)
                winsound.Beep(1500, 100)
                winsound.Beep(1000, 100)
            except Exception as e:
                print(f"Audio alert error: {e}")

    def _reset_run_state(self, clear_plot: bool = True):
        """Fully reset timers, DAQ tasks, buffers, and button states."""
        # 1) stop timers
        if hasattr(self.gui, 'timer_thread') and self.gui.timer_thread:
            self.gui.timer_thread.cancel()
            self.gui.timer_thread = None
        
        # Only reset end_time if we're doing a full reset (clear_plot=True)
        if clear_plot and hasattr(self.gui, 'end_time'):
            self.gui.end_time = None

        # 2) cancel any Tk `after` job
        if hasattr(self.gui, 'after_job_id') and self.gui.after_job_id:
            self.gui.after_cancel(self.gui.after_job_id)
            self.gui.after_job_id = None

        # 3) shut down DAQ tasks
        try:
            self.cleanup_tasks()          # zeroes AO + closes tasks
        except Exception:
            pass
        for tsk in ("test_task", "dio_task"):
            obj = getattr(self, tsk, None)
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, tsk, None)

        # 4) reset flags
        self.stop_polarization = False
        if hasattr(self.gui, 'plotting'):
            self.gui.plotting = False
        if hasattr(self.gui, 'start_time'):
            self.gui.start_time = None

        # 5) clear / recreate plot
        if clear_plot:
            self.gui.reset_waveform_plot()

        # 6) return GUI to idle
        if hasattr(self.gui, 'state_label'):
            self.gui.state_label.config(text="State: Idle")

    def set_voltage_to_zero(self):
        """Set analog output voltage to zero using a temporary task"""
        try:
            with nidaqmx.Task() as zero_task:
                zero_task.ao_channels.add_ao_voltage_chan("Dev1/ao1", min_val=-10.0, max_val=10.0)
                zero_task.write(0.0)
                print("Voltage set to 0V")
        except Exception as e:
            print(f"Error setting voltage to zero: {e}")

    def cleanup_tasks(self):
        """Clean up all DAQ tasks and set voltage to zero"""
        try:
            # Set voltage to zero first
            self.set_voltage_to_zero()
        except Exception as e:
            print(f"Error zeroing voltage during cleanup: {e}")
        
        # Close all tasks
        for task_attr in ['test_task', 'dio_task']:
            task = getattr(self, task_attr, None)
            if task:
                try:
                    task.close()
                    print(f"Closed {task_attr}")
                except Exception as e:
                    print(f"Error closing {task_attr}: {e}")
                setattr(self, task_attr, None)
                
    def clear_scram_flag(self):
        """Clear the SCRAM flag to allow normal operation"""
        self.scram_active = False
        print("SCRAM flag cleared - normal operation can resume")

    def load_config(self, state):
        """Load and apply configuration from file with enhanced DAQ control."""
        state_mapping = {
            "Activation_State_Final": "Activating the Sample",
            "Activation_State_Initial": "Activating the Sample",
            "Bubbling_State_Final": "Bubbling the Sample",
            "Bubbling_State_Initial": "Bubbling the Sample",
            "Degassing": "Degassing Solution",
            "Recycle": "Recycling Solution",
            "Injection_State_Start": "Injecting the Sample",
            "Transfer_Final": "Transferring the Sample",
            "Transfer_Initial": "Transferring the Sample",
            "Initial_State": "Idle",
        }

        try:
            config_file = os.path.join(CONFIG_DIR, f"{state}.json")
            if not os.path.exists(config_file):
                print(f"Configuration file not found: {config_file}")
                return False

            with open(config_file, "r") as file:
                config_data = json.load(file)

            human_readable_state = state_mapping.get(state, "Unknown State")
            # Use the set_controls_state method for consistent state display
            self.gui.set_controls_state(human_readable_state.replace("State: ", ""))

            # Map valve numbers to DIO channels (Valve 1 = DIO0, etc)
            dio_states = {}
            for i in range(8):
                dio_states[f"DIO{i}"] = config_data.get(f"DIO{i}", "LOW").upper() == "HIGH"

            # Send signals to DAQ
            self.send_daq_signals(dio_states)

            return True

        except Exception as error:
            print(f"Error loading state {state}: {error}")
            return False

    def send_daq_signals(self, dio_states):
        """Send digital signals to DAQ as a single packet and close task"""
        try:
            # Clean up any existing DIO task first
            if self.dio_task:
                try:
                    self.dio_task.close()
                except:
                    pass
                self.dio_task = None
            
            # Create temporary task to set states
            with nidaqmx.Task() as temp_dio_task:
                # Configure all DIO channels
                temp_dio_task.do_channels.add_do_chan(','.join(DIO_CHANNELS))
                
                # Convert states to 1 for HIGH and 0 for LOW
                signals = [1 if dio_states[f"DIO{i}"] else 0 for i in range(8)]
                
                # Convert the list of signals to a single unsigned 32-bit integer
                signal_value = sum(val << idx for idx, val in enumerate(signals))
                
                # Write the signal once - DAQ hardware will hold the states
                temp_dio_task.write(signal_value)
                
            # Task automatically closes when exiting context manager
            # DIO lines will maintain their states until explicitly changed
                    
        except Exception as e:
            print(f"Error sending DAQ signals: {e}")
            if hasattr(self.gui, 'show_error_popup'):
                self.gui.show_error_popup(["DAQ communication error. Check hardware connection."])

    def send_analog_signal(self, channel, value):
        """Send analog signal to specified channel"""
        try:
            with nidaqmx.Task() as temp_ao_task:
                temp_ao_task.ao_channels.add_ao_voltage_chan(f"Dev1/{channel}", min_val=-10.0, max_val=10.0)
                temp_ao_task.write(value)
                print(f"Sent {value}V to {channel}")
        except Exception as e:
            print(f"Error sending analog signal to {channel}: {e}")

# --- Main SABRE GUI Class ---
class SABREGUI(tk.Frame):
    """Main SABRE GUI application - now modular and organized with focused responsibilities"""
    
    def __init__(self, master=None):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        
        # Initialize core controllers and managers
        self.daq_controller = DAQController()
        self.state_manager = StateManager(CONFIG_DIR)
        self.plot_controller = PlotController(self)
        self.ui_manager = UIManager(self)
        self.method_manager = MethodManager(self)
        self.tab_manager = TabManager(self)
        self.theme_manager = ThemeManager(self)
        
        # Initialize new focused controllers
        self.window_manager = WindowManager(self)
        self.preset_controller = PresetController(self)
        self.waveform_controller = WaveformController(self)
        self.countdown_controller = CountdownController(self)
        self.widget_synchronizer = WidgetSynchronizer(self)
        self.tooltip_manager = TooltipManager(self)
        
        # Initialize specialized components
        self.scram = ScramController(self)
        self.experiment_controller = ExperimentController(self)
        
        # Initialize panels (will be created on demand)
        self.full_flow_panel = None
        self.virtual_panel = None
        
        # Setup variables and UI
        self.setup_variables()
        self.setup_ui_structure()
        self.setup_ui_components()
        
        # Apply initial theme based on user selection
        self.theme_manager.apply_theme(self.theme_var.get())
        
        # Initialize countdown display (if countdown_label exists)
        
    def setup_variables(self):
        """Initialize all instance variables"""
        # Control variables
        self.controls_state_var = tk.StringVar(value="State: Idle")
        
        # Timer variables (SLIC_Control.py implementation)
        self.countdown_running = False
        self.countdown_end_time = None
        self.after_id = None
        self.countdown_label = None  # Will be initialized when UI is created
        
        # Timer functionality removed
        
        # Preset management
        self.selected_preset_var = tk.StringVar(value="Select a method preset...")
        self.current_preset_data = {}
        
        # Live waveform plotting variables
        self.voltage_data = []
        self.time_data = []
        self.plotting = False
        self.current_method_duration = 0.0
        self.start_time = None   # Track when plotting starts
        
        # DAQ and experiment control
        self.stop_polarization = False
        self.task_lock = threading.Lock()
        self.test_task = None
        self.dio_task = None
        self.running = False
        
        # UI state
        self.virtual_panel = None
        self.entries = {}
        self.units = {}
        
        # Initialize toggle variables
        self.audio_enabled = tk.BooleanVar(value=True)
        self.tooltips_enabled = tk.BooleanVar(value=False)
        self.theme_var = tk.StringVar(value="Normal")
        
        # Preset and method variables
        self.preset_combobox = None  # Initialize preset combobox reference
        self.polarization_method_var = tk.StringVar(value="Select method...")
        self.selected_method_var = tk.StringVar(value="Select method...")
        self.polarization_method_file = None
        
        # Main tab entries
        self.main_entries = {}
        self.main_units = {}
        
        # Ensure entries exist to prevent KeyError
        self._ensure_entries_exist()
        
    def setup_ui_structure(self):
        """Setup the main UI structure"""
        # Notebook and Tabs Setup
        self.notebook_container = tk.Frame(self)
        self.notebook_container.pack(fill="both", expand=True)
        self.notebook = ttk.Notebook(self.notebook_container, style="DarkTab.TNotebook")
        self.notebook.pack(side="left", fill="both", expand=True)
        self.more_btn = ttk.Menubutton(self.notebook_container, text="⋯", width=2)
        self.more_btn.pack(side="right", anchor="ne", padx=2)
        self.overflow_menu = tk.Menu(self.more_btn, tearoff=0)
        self.more_btn["menu"] = self.overflow_menu
        
        # Configure tab styles
        self.setup_tab_styles()
        
        # Status Bar at the Top (Timer removed)
        self.status_timer_bar = tk.Frame(self, relief="groove", bd=2)
        self.status_timer_bar.pack(fill="x", side="top", padx=0, pady=(0, 2))
        self.status_var = tk.StringVar(value="System Ready")
        self.status_label = tk.Label(self.status_timer_bar, textvariable=self.status_var, 
                                   font=("Arial", 11, "bold"), fg="darkgreen")
        self.status_label.pack(side="left", padx=(10, 20), pady=2)
        
        # Create basic widgets
        self.create_initial_widgets()
        
        # Build dashboard tabs
        self.tab_manager.build_dashboard_tabs()
        
        # Timer functionality removed
        
        # Bind events
        self.bind("<Configure>", lambda e: self._update_tab_overflow())
        self.notebook.bind("<Button-3>", self._maybe_clone_tab, add="+")
        
    def setup_tab_styles(self):
        """Setup tab styling"""
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("DarkTab.TNotebook.Tab", padding=(12, 4))
        style.map("DarkTab.TNotebook.Tab",
                  background=[("selected", "#333333")],
                  foreground=[("selected", "white")])
                  
    def setup_ui_components(self):
        """Setup UI components using the modular classes"""
        # Initialize plotting components
        self.plot_controller.initialize_plots()
        
        # Set up method variables from method manager
        self.polarization_method_file = self.method_manager.polarization_method_file
        self.polarization_methods_dir = self.method_manager.polarization_methods_dir
        self.selected_method_var = self.method_manager.selected_method_var
        self.polarization_method_var = self.method_manager.polarization_method_var
        
        # Set up plot references for backward compatibility
        self.ax = self.plot_controller.main_ax
        self.canvas = self.plot_controller.main_canvas
        
        # Initialize parameter section and preset manager
        self.parameter_section = ParameterSection(self, self)
        self.preset_manager = PresetManager(self, self.parameter_section)

    def create_initial_widgets(self):
        """Create basic widgets needed before building dashboard tabs"""
        # Initialize stop event
        self.stop_event = threading.Event()
        
        # Create basic UI elements that other methods depend on
        self.state_label = tk.Label(self, text="State: Initial", font=('Arial', 12))
        
    # Delegate methods to respective controllers/managers
    def _create_control_button(self, parent, text, color, command):
        """Delegate to UI manager"""
        return self.ui_manager.create_control_button(parent, text, color, command)
        
    def show_error_popup(self, missing_params):
        """Delegate to UI manager"""
        return self.ui_manager.show_error_popup(missing_params)
        
    def select_polarization_method(self):
        """Delegate to method manager"""
        return self.method_manager.select_polarization_method()
        
    def _create_quadrant_button(self, parent, text, color, command, row, col):
        """Delegate to UI manager"""
        return self.ui_manager.create_quadrant_button(parent, text, color, command, row, col)

    # Tab creation methods (these would be implemented with the UI structure)
    def _create_main_tab(self, parent, detached=False):
        """Create the main control tab with key controls and previews"""
        # Implementation would go here
        placeholder = tk.Label(parent, text="Main Tab Content\n(Implementation in progress)", 
                             font=("Arial", 14), justify="center")
        placeholder.pack(expand=True)
        
    def _create_advanced_tab(self, parent, detached=False):
        """Create the advanced parameters tab"""
        # Implementation would go here
        placeholder = tk.Label(parent, text="Advanced Parameters Tab\n(Implementation in progress)", 
                             font=("Arial", 14), justify="center")
        placeholder.pack(expand=True)
        
    def _create_testing_tab(self, parent):
        """Create the testing tab with fully embedded testing panels"""
        # Implementation would go here
        placeholder = tk.Label(parent, text="Testing Tab\n(Implementation in progress)", 
                             font=("Arial", 14), justify="center")
        placeholder.pack(expand=True)
        
    def _create_slic_tab(self, parent):
        """Create the SLIC control tab"""
        try:
            slic_panel = SLICSequenceControl(parent, embedded=True)
            slic_panel.pack(fill="both", expand=True)
            
            # Add comprehensive tooltips to SLIC Control components
            self._add_slic_control_tooltips(slic_panel)
            
        except Exception as e:
            error_label = tk.Label(parent, text=f"SLIC Control Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
            
    def _create_polarization_tab(self, parent):
        """Create the polarization calculator tab"""
        try:
            pol_panel = PolarizationApp(parent, embedded=True)
            pol_panel.pack(fill="both", expand=True)
        except Exception as e:
            error_label = tk.Label(parent, text=f"Polarization Calculator Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)

    # Additional methods for tab overflow and cloning functionality
    def _update_tab_overflow(self):
        """Handle tab overflow in the notebook"""
        try:
            # Safety check for widgets that might be destroyed
            if not hasattr(self, 'notebook') or not self.notebook.winfo_exists():
                return
                
            self.update_idletasks()
            
            # Another safety check after update_idletasks
            if not hasattr(self, 'notebook_container') or not self.notebook_container.winfo_exists():
                return
                
            if not hasattr(self, 'more_btn') or not self.more_btn.winfo_exists():
                return
                
            # Use a safe default if sizes are not yet available
            try:
                avail = self.notebook_container.winfo_width() - self.more_btn.winfo_width() - 15
                if avail <= 0:
                    avail = 600  # Default reasonable width
            except:
                avail = 600  # Default reasonable width
            
            # Estimate tab width instead of trying to get it from tkinter (which doesn't support it)
            tab_count = len(self.notebook.tabs())
            if tab_count == 0:
                return
                
            # Estimate each tab width as approximately 120 pixels
            estimated_tab_width = 120
            used = tab_count * estimated_tab_width
            
            # if everything fits, make all tabs visible
            if used < avail:
                for i in range(tab_count):
                    try:
                        self.notebook.tab(i, state="normal")
                    except:
                        pass  # Skip if tab issues
                self.overflow_menu.delete(0, "end")
                return
                
            # otherwise, hide tabs from rightmost until fits
            excess = []
            for i in reversed(range(tab_count)):
                used -= estimated_tab_width
                excess.append(i)
                if used < avail:
                    break
                    
            # hide excess
            for idx in excess:
                try:
                    self.notebook.tab(idx, state="hidden")
                except:
                    pass  # Skip if tab issues
                
            # repopulate menu
            self.overflow_menu.delete(0, "end")
            for idx in excess[::-1]:
                try:
                    text = self.notebook.tab(idx, "text")
                    self.overflow_menu.add_command(label=text,
                        command=lambda i=idx: self.safe_select_tab(i))
                except:
                    pass  # Skip if tab issues
        except Exception as e:
            # Log errors but don't crash
            print(f"Tab overflow error: {e}")
            
    def safe_select_tab(self, idx):
        """Safely select a tab by index, with error handling"""
        try:
            self.notebook.select(idx)
        except Exception as e:
            print(f"Error selecting tab {idx}: {e}")
            
    def _maybe_clone_tab(self, event):
        """Handle right-click on tab for detaching all tabs"""
        elem = self.notebook.identify(event.x, event.y)
        if elem != "label":
            return
        
        index = self.notebook.index("@%d,%d" % (event.x, event.y))
        tab_text = self.notebook.tab(index, "text")
        
        # Allow detaching all tabs
        available_tabs = ["Main", "Advanced Parameters", "Testing", "SLIC Control", "% Polarization Calc"]
        if tab_text not in available_tabs:
            return
            
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="Detach Tab", command=lambda: self._clone_tab(tab_text))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _clone_tab(self, tab_text):
        """Create a detached window for any tab."""
        available_tabs = ["Main", "Advanced Parameters", "Testing", "SLIC Control", "% Polarization Calc"]
        if tab_text not in available_tabs:
            return
        
        # Check if already detached
        detached_attr = f"_detached_{tab_text.replace(' ', '_').replace('%', 'percent').lower()}"
        if hasattr(self, detached_attr) and getattr(self, detached_attr) and getattr(self, detached_attr).winfo_exists():
            getattr(self, detached_attr).lift()  # Bring to front
            return
        
        try:
            win = tk.Toplevel(self)
            win.title(f"{tab_text} (Detached)")
            
            # Set the application icon for detached window
            self._set_sabre_icon(win)
            
            # Set appropriate window size based on tab type
            if tab_text in ["Main", "Advanced Parameters"]:
                win.geometry("900x700")
            elif tab_text == "Testing":
                win.geometry("1000x800")
            elif tab_text == "SLIC Control":
                win.geometry("800x600")
            elif tab_text == "% Polarization Calc":
                win.geometry("700x500")
                
            win.protocol("WM_DELETE_WINDOW", lambda: self._on_detached_close(tab_text, win))
            
            # Store reference to detached window
            setattr(self, detached_attr, win)
            
            container = ttk.Frame(win)
            container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create content based on tab type
            if tab_text == "Main":
                self.tab_manager.create_main_tab(container, detached=True)
                # Find original tab and sync
                for i in range(self.notebook.index("end")):
                    if self.notebook.tab(i, "text") == "Main":
                        original_tab = self.notebook.nametowidget(self.notebook.tabs()[i])
                        self.sync_widget_values(original_tab, container)
                        break
                        
            elif tab_text == "Advanced Parameters":
                self.tab_manager.create_advanced_tab(container, detached=True)
                # Find original tab and sync
                for i in range(self.notebook.index("end")):
                    if self.notebook.tab(i, "text") == "Advanced Parameters":
                        original_tab = self.notebook.nametowidget(self.notebook.tabs()[i])
                        self.sync_widget_values(original_tab, container)
                        break
                        
            elif tab_text == "Testing":
                self.tab_manager.create_testing_tab(container)
                
            elif tab_text == "SLIC Control":
                self.tab_manager.create_slic_tab(container)
                
            elif tab_text == "% Polarization Calc":
                self.tab_manager.create_polarization_tab(container)
            
            # Auto-skin the detached window
            self.theme_manager._apply_theme_recursive(win, self.theme_manager.get_theme_colors())
            
        except Exception as e:
            print(f"Error creating detached tab '{tab_text}': {e}")
            messagebox.showerror("Error", f"Could not detach tab '{tab_text}': {e}")
    
    def _on_detached_close(self, tab_text, window):
        """Handle closing of detached window"""
        detached_attr = f"_detached_{tab_text.replace(' ', '_').replace('%', 'percent').lower()}"
        if hasattr(self, detached_attr):
            delattr(self, detached_attr)
        window.destroy()

    # Panel opening methods - delegate to window manager
    def open_ai_panel(self):
        """Launch the miniature AI test panel."""
        self.window_manager.open_panel("ai")

    def open_ao_panel(self):
        """Launch the miniature AO test panel."""
        self.window_manager.open_panel("ao")

    def open_slic_control(self):
        """Open SLIC control window"""
        self.window_manager.open_panel("slic")
    
    def open_polarization_calculator(self):
        """Open polarization calculator window"""
        self.window_manager.open_panel("polarization")
            
    def open_full_flow_system(self):
        """Open the Full Flow System window"""
        self.window_manager.open_panel("full_flow")

    def toggle_virtual_panel(self):
        """Toggle the Virtual Testing Environment window"""
        self.window_manager.open_panel("virtual")

    def _set_sabre_icon(self, window):
        """Set the SABRE application icon on any window"""
        try:
            from PIL import Image, ImageTk
            icon_path = r"C:\Users\walsworthlab\Desktop\SABRE Program\SABREAppICON.png"
            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path)
                # Resize icon to appropriate size for window icon (32x32 is standard)
                icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS)
                icon_photo = ImageTk.PhotoImage(icon_image)
                window.iconphoto(True, icon_photo)
                return True
            else:
                print(f"Icon file not found: {icon_path}")
                return False
        except ImportError:
            print("PIL/Pillow not available - icon not set")
            return False
        except Exception as e:
            print(f"Error setting window icon: {e}")
            return False

    def get_value(self, entry_attr, conversion_type="time"):
        """Get parameter value with unit conversion"""
        # First check if this is a main tab entry (stored in self.entries)
        if hasattr(self, 'entries') and entry_attr in self.entries:
            entry = self.entries[entry_attr]
            unit_var = self.units.get(entry_attr, tk.StringVar(value="s"))
            
            # Import conversion function
            from Nested_Programs.Utility_Functions import get_value as convert_value
            return convert_value(entry, unit_var, conversion_type)
            
        # Then check parameter section for advanced parameters
        if self.parameter_section is not None and hasattr(self.parameter_section, 'get_value'):
            return self.parameter_section.get_value(entry_attr, conversion_type)
            
        return 0.0

    # Experiment control methods (delegate to experiment controller)
    def activate_experiment(self):
        """Delegate to experiment controller"""
        self.experiment_controller.activate_experiment()
        
    def start_experiment(self):
        """Delegate to experiment controller"""
        self.experiment_controller.start_experiment()
        
    def test_field(self):
        """Delegate to experiment controller"""
        self.experiment_controller.test_field()
        
    def scram_experiment(self):
        """Instant emergency stop with proper DAQ interaction."""
        print("EMERGENCY STOP ACTIVATED")
        
        # Set SCRAM flag to prevent other sequences from loading states
        if hasattr(self, 'experiment_controller'):
            self.experiment_controller.scram_active = True
        
        # Stop countdown timer
        self.stop_countdown()
        
        # Stop polarization and running flag
        self.stop_polarization = True
        if hasattr(self, 'running'):
            self.running = False  # Added flag to stop sequences
        
        # Use ScramController to handle emergency stop
        self.scram()
    
        # After SCRAM hardware cleanup, explicitly load Initial_State to ensure proper valve positions
        try:
            if hasattr(self, 'experiment_controller'):
                success = self.experiment_controller.load_config("Initial_State")
                if success:
                    print("SCRAM: Initial_State loaded and maintained")
                    if hasattr(self, 'state_label'):
                        self.state_label.config(text="State: Initial (Post-SCRAM)")
                    
                    # Update virtual panel if it exists
                    if hasattr(self, 'virtual_panel') and self.virtual_panel and self.virtual_panel.winfo_exists():
                        self.virtual_panel.load_config_visual("Initial_State")
                else:
                    print("SCRAM: Failed to load Initial_State")
                    if hasattr(self, 'state_label'):
                        self.state_label.config(text="State: EMERGENCY STOP")
        except Exception as e:
            print(f"SCRAM: Error loading Initial_State after emergency stop: {e}")
        if hasattr(self, 'state_label'):
            self.state_label.config(text="State: EMERGENCY STOP")
        
        # Alert user
        if self.audio_enabled.get():
            try:
                winsound.Beep(2000, 100)
                winsound.Beep(1500, 100)
                winsound.Beep(1000, 100)
            except Exception as e:
                print(f"Audio alert error: {e}")
        
    def send_daq_signals(self, dio_states):
        """Send DAQ signals - delegate to experiment controller"""
        if hasattr(self, 'experiment_controller'):
            self.experiment_controller.send_daq_signals(dio_states)
        
    def set_controls_state(self, state_name):
        """Set the controls state display"""
        if hasattr(self, 'state_display_label'):
            self.state_display_label.config(text=f"State: {state_name}")
        # Keep the old variable for backward compatibility
        if hasattr(self, 'controls_state_var'):
            self.controls_state_var.set(f"State: {state_name}")
            
    def _ensure_entries_exist(self):
        """Ensure all required entries exist in the entries dictionary to prevent KeyError"""
        required_keys = ["Activation Time", "Temperature", "Flow Rate", "Pressure", "Bubbling Time", "Magnetic Field"]
        
        # Create dummy entries if they don't exist
        for key in required_keys:
            if key not in self.entries:
                # Create a temporary entry widget to avoid KeyError
                dummy_frame = tk.Frame(self)
                self.entries[key] = tk.Entry(dummy_frame)
                self.entries[key].insert(0, "0.0")  # Default value
                # Don't pack the dummy_frame - it's just to prevent errors
        
        # Also ensure required entry widgets exist as attributes
        required_attrs = [
            'activation_time_entry', 'injection_time_entry', 'valve_time_entry',
            'degassing_time_entry', 'transfer_time_entry', 'recycle_time_entry'
        ]
        
        dummy_frame = tk.Frame(self)
        for attr in required_attrs:
            if not hasattr(self, attr) or not getattr(self, attr).winfo_exists():
                entry = tk.Entry(dummy_frame)
                entry.insert(0, "0.0")  # Default value
                setattr(self, attr, entry)
        # Don't pack dummy_frame

    def on_preset_selected_auto_fill(self, event=None):
        """Auto-fill all parameters when a preset is selected - delegate to preset controller"""
        self.preset_controller.on_preset_selected_auto_fill(event)

    def _auto_fill_parameters(self, preset_data):
        """Auto-fill parameters in both Main and Advanced tabs based on preset data"""
        try:
            # Fill Main tab parameters (if they exist)
            if hasattr(self, 'entries') and self.entries:
                for param_name, param_data in preset_data.get('general', {}).items():
                    if param_name in self.entries:
                        entry = self.entries[param_name]
                        if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                            entry.delete(0, tk.END)
                            # Extract just the value, not the full dict
                            value = param_data.get('value', param_data) if isinstance(param_data, dict) else param_data
                            entry.insert(0, str(value))
                        
                        # Set unit if available and units dict exists
                        if hasattr(self, 'units') and param_name in self.units and isinstance(param_data, dict) and 'unit' in param_data:
                            unit_var = self.units[param_name]
                            unit_var.set(param_data['unit'])
            
            # Fill Advanced tab parameters via parameter section
            if hasattr(self, 'parameter_section') and self.parameter_section:
                # Fill general parameters
                for param_name, param_data in preset_data.get('general', {}).items():
                    if hasattr(self.parameter_section, 'entries') and param_name in self.parameter_section.entries:
                        entry = self.parameter_section.entries[param_name]
                        if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                            entry.delete(0, tk.END)
                            entry.insert(0, str(param_data.get('value', param_data)))
                        
                        # Set unit if available
                        if hasattr(self.parameter_section, 'units') and param_name in self.parameter_section.units and 'unit' in param_data:
                            unit_var = self.parameter_section.units[param_name]
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
                        if hasattr(self, entry_attr):
                            entry = getattr(self, entry_attr)
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
                    self.polarization_method_file = method_file
                      # Update dropdown to show the selected method
                    if hasattr(self, 'polarization_method_var'):
                        self.polarization_method_var.set(method_name)
                    elif hasattr(self, 'selected_method_var'):
                        self.selected_method_var.set(method_name)
                    
                    print(f"Set polarization method to: {method_name}")
                    
                    # Update the live waveform plot with the new method
                    self._refresh_live_waveform()
            
            print(f"Successfully auto-filled parameters from preset")
                
        except Exception as e:
            print(f"Error auto-filling parameters: {e}")
            messagebox.showwarning("Auto-Fill Warning", 
                                 f"Some parameters could not be auto-filled: {e}")

    def save_current_as_preset(self):
        """Save current parameters as a new preset"""
        try:
            if (hasattr(self, 'preset_manager') and self.preset_manager is not None and 
                hasattr(self.preset_manager, 'preset_var') and self.preset_manager.preset_var is not None):
                self.preset_manager.save_current_as_preset()
            else:
                # Simple fallback implementation
                preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
                if preset_name:
                    messagebox.showinfo("Info", f"Preset '{preset_name}' would be saved.\nFull preset management available in Advanced Parameters tab.")
                    self.notebook.select(1)  # Switch to Advanced Parameters tab
        except Exception as e:
            print(f"Error saving preset: {e}")
            messagebox.showerror("Error", f"Failed to save preset: {e}")

    def delete_selected_preset(self):
        """Delete the currently selected preset"""
        try:
            if (hasattr(self, 'preset_manager') and self.preset_manager is not None and 
                hasattr(self.preset_manager, 'preset_var') and self.preset_manager.preset_var is not None):
                self.preset_manager.delete_preset()
            else:
                # Simple fallback implementation
                selected_preset = self.selected_preset_var.get()
                if selected_preset and selected_preset != "Select a method preset...":
                    preset_file = os.path.join(PRESETS_DIR, f"{selected_preset}.json")
                    if os.path.exists(preset_file):
                        if messagebox.askyesno("Delete Preset", f"Delete preset '{selected_preset}'?"):
                            os.remove(preset_file)
                            self.refresh_preset_list()
                            messagebox.showinfo("Success", f"Preset '{selected_preset}' deleted.")
                    else:
                        messagebox.showerror("Error", f"Preset file not found: {selected_preset}")
                else:
                    messagebox.showinfo("Info", "No preset selected for deletion.")
        except Exception as e:
            print(f"Error deleting preset: {e}")
            messagebox.showerror("Error", f"Failed to delete preset: {e}")

    def refresh_preset_list(self):
        """Refresh the list of available presets in all comboboxes"""
        try:
            if not os.path.exists(PRESETS_DIR):
                os.makedirs(PRESETS_DIR)
                
            # Get all JSON files in presets directory
            preset_files = [f[:-5] for f in os.listdir(PRESETS_DIR) if f.endswith('.json')]
            preset_options = ["Select a method preset..."] + sorted(preset_files)
            
            # Update main tab preset combobox if it exists
            if hasattr(self, 'preset_combobox') and self.preset_combobox is not None:
                try:
                    self.preset_combobox['values'] = preset_options
                except Exception as e:
                    print(f"Error updating main preset combobox: {e}")
            
            # Update any preset combobox in Advanced tab
            if hasattr(self, 'preset_manager') and self.preset_manager is not None:
                try:
                    # Check if preset_combobox exists before trying to refresh
                    if hasattr(self.preset_manager, 'preset_combobox') and self.preset_manager.preset_combobox is not None:
                        self.preset_manager.refresh_presets_list()
                    else:
                        print("Advanced preset manager combobox not initialized yet")
                except Exception as e:
                    print(f"Error updating advanced preset manager: {e}")
                
        except Exception as e:
            print(f"Error refreshing preset list: {e}")

    def refresh_method_list(self):
        """Refresh the polarization method list in all comboboxes"""
        try:
            # Get updated method list from directory
            polarization_methods = self.method_manager.load_polarization_methods_from_directory()
            
            # Update the Advanced Parameters tab combobox
            if hasattr(self, 'polarization_method_combobox') and self.polarization_method_combobox is not None:
                try:
                    current_selection = self.polarization_method_var.get()
                    self.polarization_method_combobox['values'] = polarization_methods
                    
                    # Restore selection if it still exists
                    if current_selection in polarization_methods:
                        self.polarization_method_var.set(current_selection)
                    else:
                        self.polarization_method_var.set("Select method...")
                        self.polarization_method_file = None
                        
                    print(f"Refreshed polarization method list: {len(polarization_methods)} methods found")
                except Exception as e:
                    print(f"Error updating polarization method combobox: {e}")
            
            # Update any other method comboboxes if they exist
            if hasattr(self, 'method_manager') and hasattr(self.method_manager, 'method_combobox'):
                try:
                    if self.method_manager.method_combobox is not None:
                        self.method_manager.method_combobox['values'] = polarization_methods
                except Exception as e:
                    print(f"Error updating method manager combobox: {e}")
                    
        except Exception as e:
            print(f"Error refreshing method list: {e}")

    def _open_polarization_methods_directory(self):
        """Open the polarization methods directory in file explorer"""
        import subprocess
        import platform
        
        directory = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
        
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{directory}"')
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", directory])
            else:  # Linux
                subprocess.Popen(["xdg-open", directory])
            
            print(f"Opened directory: {directory}")
        except Exception as e:
            print(f"Error opening directory: {e}")
            messagebox.showerror("Error", f"Could not open directory:\n{directory}\n\nError: {e}")

    # Delegate waveform methods to WaveformController
    def toggle_waveform_plot(self):
        """Toggle waveform plot visibility"""
        self.waveform_controller.toggle_waveform_plot()

    def _plot_waveform_buffer(self, buf, sr):
        """Plot waveform buffer for preview"""
        self.waveform_controller.plot_waveform_buffer(buf, sr)

    def _compute_polarization_duration(self):
        """Compute polarization duration"""
        return self.method_manager.compute_polarization_duration()

    def reset_waveform_plot(self):
        """Reset waveform plot"""
        self.waveform_controller.reset_waveform_plot()

    def _refresh_live_waveform(self):
        """Refresh the live waveform plot - delegate to waveform controller"""
        self.waveform_controller.refresh_live_waveform()

    def _force_waveform_update(self):
        """Force an immediate waveform plot update - delegate to waveform controller"""
        self.waveform_controller.force_waveform_update()
        
    # Delegate countdown methods to CountdownController  
    def start_countdown(self, duration_s):
        """Start countdown timer - delegate to countdown controller"""
        self.countdown_controller.start_countdown(duration_s)

    def update_countdown(self):
        """Update countdown display - delegate to countdown controller"""
        self.countdown_controller.update_countdown()

    def stop_countdown(self):
        """Stop countdown timer - delegate to countdown controller"""
        self.countdown_controller.stop_countdown()
        
    # Legacy method compatibility - redirect to countdown controller
    def start_timer(self, total_seconds):
        """Legacy method - redirect to countdown"""
        self.countdown_controller.start_countdown(total_seconds)
        
    def stop_timer(self):
        """Legacy method - redirect to countdown"""
        self.countdown_controller.stop_countdown()
        
    def reset_timer(self):
        """Legacy method - redirect to countdown"""
        self.countdown_controller.stop_countdown()
        
    def start_countdown_timer(self, duration_seconds):
        """Legacy method - redirect to countdown"""
        self.countdown_controller.start_countdown(duration_seconds)
        
    def stop_countdown_timer(self):
        """Legacy method - redirect to countdown"""
        self.countdown_controller.stop_countdown()

    def apply_theme(self, theme_name):
        """Apply a theme to the application"""
        if hasattr(self, 'theme_manager'):
            self.theme_manager.apply_theme(theme_name)
            self.theme_var.set(theme_name)  # Update the theme variable
            
            # Also apply theme to any detached windows
            self._apply_theme_to_detached_windows(theme_name)
        else:
            print("Theme manager not available")
            
    def _apply_theme_to_detached_windows(self, theme_name):
        """Apply theme to any detached windows"""
        try:
            colors = self.theme_manager.get_theme_colors(theme_name)
            
            # List of possible detached window attributes
            detached_attrs = [
                '_detached_main', '_detached_advanced_parameters', 
                '_detached_testing', '_detached_slic_control', 
                '_detached_percent_polarization_calc'
            ]
            
            for attr in detached_attrs:
                if hasattr(self, attr):
                    window = getattr(self, attr)
                    if window and window.winfo_exists():
                        # Apply theme to the detached window
                        window.configure(bg=colors["bg"])
                        self.theme_manager._apply_theme_recursive(window, colors)
                        
        except Exception as e:
            print(f"Error applying theme to detached windows: {e}")
            
    def sync_widget_values(self, src_frame, clone_frame):
        """Delegate to widget synchronizer"""
        self.widget_synchronizer.sync_widget_values(src_frame, clone_frame)
            
    def _add_virtual_testing_tooltips(self, virtual_panel):
        """Delegate to tooltip manager"""
        self.tooltip_manager.add_virtual_testing_tooltips(virtual_panel)
            
    def _add_full_flow_tooltips(self, full_flow_panel):
        """Delegate to tooltip manager"""
        self.tooltip_manager.add_full_flow_tooltips(full_flow_panel)
            
    def _add_analog_input_tooltips(self, ai_panel):
        """Delegate to tooltip manager"""
        self.tooltip_manager.add_analog_input_tooltips(ai_panel)
            
    def _add_analog_output_tooltips(self, ao_panel):
        """Delegate to tooltip manager"""
        self.tooltip_manager.add_analog_output_tooltips(ao_panel)
            
    def _add_slic_control_tooltips(self, slic_panel):
        """Add comprehensive tooltips to SLIC Control components using the provided definitions"""
        try:
            # Add tooltips to SLIC parameter controls only (no main panel tooltip)
            self._add_slic_parameter_tooltips(slic_panel)
            
        except Exception as e:
            print(f"Error adding SLIC control tooltips: {e}")
            
    def _add_slic_parameter_tooltips(self, slic_panel):
        """Add tooltips to SLIC parameter controls with scientific definitions"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            # Recursively search for parameter widgets and add appropriate tooltips
            for child in slic_panel.winfo_children():
                self._add_slic_tooltips_recursive(child)
                
        except Exception as e:
            print(f"Error adding SLIC parameter tooltips: {e}")
            
    def _add_slic_tooltips_recursive(self, widget):
        """Recursively add tooltips to SLIC widgets based on their labels or names"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            # Check if this widget has text that matches SLIC parameters
            widget_text = ""
            try:
                if hasattr(widget, 'cget'):
                    widget_text = widget.cget('text')
            except:
                pass
                    
            # For Entry widgets, find the specific associated label using grid position
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                tooltip_text = self._find_associated_label_tooltip_slic(widget)
                if tooltip_text:
                    ToolTip(widget, tooltip_text + "\n\nEnter numerical value for this parameter.", parent=self)
            
            # Handle labels and buttons with text
            elif widget_text:
                tooltip_text = self._get_slic_tooltip_for_parameter(widget_text)
                if tooltip_text:
                    ToolTip(widget, tooltip_text, parent=self)
                    
                # Add tooltips for common button types
                elif isinstance(widget, (tk.Button, ttk.Button)):
                    button_text = widget_text.lower()
                    if "generate" in button_text:
                        ToolTip(widget, 
                               "GENERATE SEQUENCE: Create SLIC waveform from parameters.\n"
                               "• Builds the complete magnetic field sequence\n"
                               "• Combines all pulses and timing elements\n"
                               "• Validates parameters before generation\n"
                               "• Creates optimized waveform for DAQ output", 
                               parent=self)
                    elif "send" in button_text or "start" in button_text:
                        ToolTip(widget, 
                               "SEND SEQUENCE: Output the generated waveform to hardware.\n"
                               "• Sends waveform to the specified AO channel\n"
                               "• Applies the magnetic field sequence to sample\n"
                               "• Monitor field output during execution\n"
                               "• Use for actual polarization experiments", 
                               parent=self)
                    elif "stop" in button_text:
                        ToolTip(widget, 
                               "STOP SEQUENCE: Halt waveform output immediately.\n"
                               "• Emergency stop for magnetic field output\n"
                               "• Sets output voltage to 0V safely\n"
                               "• Use if sequence needs to be interrupted\n"
                               "• Preserves DAQ hardware from damage", 
                               parent=self)
                    elif "plot" in button_text or "view" in button_text or "look" in button_text:
                        ToolTip(widget, 
                               "PLOT WAVEFORM: Visualize the generated sequence.\n"
                               "• Shows voltage vs time for the complete sequence\n"
                               "• Verify waveform before sending to hardware\n"
                               "• Check for timing and amplitude accuracy\n"
                               "• Useful for sequence optimization", 
                               parent=self)
                    
            # Recursively process child widgets
            for child in widget.winfo_children():
                self._add_slic_tooltips_recursive(child)
                
        except Exception as e:
            print(f"Error in SLIC recursive tooltips: {e}")
    
    def _get_slic_tooltip_for_parameter(self, text):
        """Get tooltip text for SLIC parameters based on text content"""
        text_lower = text.lower()
        
        if "coilcalibration" in text_lower or "coil calibration" in text_lower:
            return "coilcalibration (µT/V): Conversion factor from DAQ output voltage to the B₁ field produced by the drive coil."
        elif "b1_slic" in text_lower or "b1 slic" in text_lower:
            return "B1_SLIC (µT): Target B₁ amplitude used during the SLIC spin-lock period."
        elif "f_slic" in text_lower or "frequency" in text_lower:
            return "f_SLIC (Hz): Spin-lock (SLIC) carrier frequency applied to match the heteronuclear J-coupling or desired offset."
        elif "timeslic" in text_lower or "slic duration" in text_lower:
            return "TimeSLIC_approx (s): Approximate duration of the SLIC spin-lock block delivered each scan."
        elif "df" in text_lower or "detuning" in text_lower:
            return "df (Hz): Frequency detuning or sweep width applied around fₛₗᵢc to achieve adiabatic passage."
        elif "length90pulse" in text_lower or "90 pulse" in text_lower:
            return "Length90Pulse (s): Duration of the 90° excitation pulse preceding the SLIC block."
        elif "b1_pulse" in text_lower or "pulse amplitude" in text_lower:
            return "B1_Pulse (µT): B₁ amplitude for that 90° pulse."
        elif "sample_rate" in text_lower or "sampling rate" in text_lower:
            return "sample_rate (Sa/s): Digital sampling rate used when synthesising the analogue waveform."
        elif "ao_channel" in text_lower or "output channel" in text_lower:
            return "ao_channel: Designated NI-DAQ analogue-output channel (e.g., \"ao1\") that delivers the generated waveform."
        
        return None
    
    def _find_associated_label_tooltip_slic(self, entry_widget):
        """Find the specific label associated with an Entry widget in SLIC Control using grid position"""
        try:
            if not hasattr(entry_widget, 'master') or not entry_widget.master:
                return None
                
            # Get the grid info for the entry widget
            entry_grid_info = entry_widget.grid_info()
            if not entry_grid_info:
                return None
                
            entry_row = entry_grid_info.get('row')
            entry_col = entry_grid_info.get('column')
            
            # In SLIC Control, labels are in column 0, entries in column 1
            if entry_col == 1:  # This is an entry widget
                # Look for a label in the same row, column 0
                for sibling in entry_widget.master.winfo_children():
                    if isinstance(sibling, (tk.Label, ttk.Label)):
                        sibling_grid_info = sibling.grid_info()
                        if (sibling_grid_info and 
                            sibling_grid_info.get('row') == entry_row and 
                            sibling_grid_info.get('column') == 0):
                            try:
                                label_text = sibling.cget('text')
                                return self._get_slic_tooltip_for_parameter(label_text)
                            except:
                                continue
            
        except Exception as e:
            print(f"Error finding SLIC label tooltip: {e}")
        
        return None
            
    def _add_polarization_calc_tooltips(self, pol_panel):
        """Add comprehensive tooltips to Polarization Calculator components"""
        try:
            # Add tooltips to polarization calculator parameters only (no main panel tooltip)
            self._add_polarization_parameter_tooltips(pol_panel)
            
        except Exception as e:
            print(f"Error adding polarization calculator tooltips: {e}")
            
    def _add_polarization_parameter_tooltips(self, pol_panel):
        """Add tooltips to polarization calculator parameters using provided definitions"""
        try:
            from Nested_Programs.ToolTip import ToolTip
            
            # Recursively search for parameter widgets
            for child in pol_panel.winfo_children():
                self._add_polarization_tooltips_recursive(child)
                
        except Exception as e:
            print(f"Error adding polarization parameter tooltips: {e}")
            
    def _add_polarization_tooltips_recursive(self, widget):
        """Recursively add tooltips to polarization calculator widgets"""
        # Temporarily commented out due to syntax issues
        pass
        # try:
        #     from Nested_Programs.ToolTip import ToolTip
        #     
        #     # Get widget text for identification
        #     widget_text = ""
        #     try:
        #         if hasattr(widget, 'cget'):
        #             widget_text = widget.cget('text')
        #     except:
        #         pass
        #         
        #     # For Entry widgets, find the specific associated label using grid position
        #     if isinstance(widget, (tk.Entry, ttk.Entry)):
        #         tooltip_text = self._find_associated_label_tooltip_polarization(widget)
        #         if tooltip_text:
        #             ToolTip(widget, tooltip_text + "\n\nEnter numerical value for this parameter.", parent=self)
        #     
        #     # Handle labels and buttons with text
        #     elif widget_text:
        #         tooltip_text = self._get_polarization_tooltip_for_parameter(widget_text)
        #         if tooltip_text:
        #             ToolTip(widget, tooltip_text, parent=self)
        #         
        #         # Add tooltips for buttons and controls
        #         elif isinstance(widget, (tk.Button, ttk.Button)):
        #             button_text = widget_text.lower()
        #             if "calculate" in button_text or "compute" in button_text:
        #                 ToolTip(widget, 
        #                        "CALCULATE: Compute polarization from input data.", 
        #                        parent=self)
        #         
        #     # Recursively process child widgets
        #     for child in widget.winfo_children():
        #         self._add_polarization_tooltips_recursive(child)
        #         
        # except Exception as e:
        #     print(f"Error in polarization recursive tooltips: {e}")
    
    def _get_polarization_tooltip_for_parameter(self, text):
        """Get tooltip text for polarization calculator parameters based on text content"""
        text_lower = text.lower()
        
        # Support both Unicode and ASCII representations
        if "ħ" in text or "hbar" in text_lower or "planck" in text_lower or "ℏ" in text:
            return "ħ (J·s): Planck's reduced constant, the fundamental quantum of angular momentum used in all magnetic-resonance calculations."
        elif "γ" in text or "gamma" in text_lower or "gyromagnetic" in text_lower:
            return "γ (rad s⁻¹ T⁻¹): Gyromagnetic ratio of the observed nucleus, linking magnetic-field strength to its Larmor precession rate."
        elif "b₀" in text_lower or "b0" in text_lower or "static field" in text_lower:
            return "B₀ (T): Static magnetic-field magnitude at which the sample is polarized and detected."
        elif "kᴮ" in text or "k_b" in text_lower or "kb" in text_lower or "boltzmann" in text_lower:
            return "kᴮ (J K⁻¹): Boltzmann's constant, relating thermal energy to temperature for population-difference estimates."
        elif "sa ratio" in text_lower or "signal ratio" in text_lower:
            return "SA ratio: Ratio of the integrated NMR signal areas (or amplitudes) used to normalise bound vs reference signals."
        elif "temperature" in text_lower or "t (k)" in text_lower:
            return "T (K): Absolute temperature of the sample during acquisition or calculation."
        elif "conc_ref" in text_lower or "reference concentration" in text_lower:
            return "Conc_ref: Molar concentration of the reference species whose signal calibrates the measurement."
        elif "conc_free" in text_lower or "free concentration" in text_lower:
            return "Conc_free: Concentration of the analyte in its free (unbound) state."
        elif "conc_bound" in text_lower or "bound concentration" in text_lower:
            return "Conc_bound: Concentration of the analyte bound to its binding partner or catalyst."
        elif "signal_ref" in text_lower or "reference signal" in text_lower:
            return "Signal_ref: Measured NMR signal intensity (or area) for the reference compound."
        elif "signal_free" in text_lower or "free signal" in text_lower:
            return "Signal_free: Integrated NMR signal (peak area or amplitude) arising from the analyte molecules that remain freely dissolved in solution after SABRE, quantifying their hyper-polarization level independent of catalyst binding."
        elif "signal_bound" in text_lower or "bound signal" in text_lower:
            return "Signal_bound: Integrated NMR signal originating from analyte molecules transiently bound to the SABRE catalyst complex, reflecting the polarization achieved in the bound state and used to gauge catalyst-mediated transfer efficiency."
        elif "x-axis" in text_lower or "axis label" in text_lower:
            return "X-axis label: User-defined text that will appear on the plot's horizontal axis."
        
        return None
    
    def _find_associated_label_tooltip_polarization(self, entry_widget):
        """Find the specific label associated with an Entry widget in Polarization Calculator using grid position"""
        try:
            if not hasattr(entry_widget, 'master') or not entry_widget.master:
                return None
                
            # Get the grid info for the entry widget
            entry_grid_info = entry_widget.grid_info()
            if not entry_grid_info:
                return None
                
            entry_row = entry_grid_info.get('row')
            entry_col = entry_grid_info.get('column')
            
            # In Polarization Calculator, labels are in even columns, entries in odd columns
            if entry_col is not None and entry_col % 2 == 1:  # This is an entry widget (odd column)
                # Look for a label in the same row, previous column (even column)
                label_col = entry_col - 1
                for sibling in entry_widget.master.winfo_children():
                    if isinstance(sibling, (tk.Label, ttk.Label)):
                        sibling_grid_info = sibling.grid_info()
                        if (sibling_grid_info and 
                            sibling_grid_info.get('row') == entry_row and 
                            sibling_grid_info.get('column') == label_col):
                            try:
                                label_text = sibling.cget('text')
                                return self._get_polarization_tooltip_for_parameter(label_text)
                            except:
                                continue
                    
        except Exception as e:
            print(f"Error finding polarization label tooltip: {e}")
        
        return None
            
# ------------- Main Application Entry Point -------------
if __name__ == "__main__":
    print("Starting SABRE GUI application (Refactored)...")
    root = tk.Tk()
    root.title("SABRE Control System - Modular Architecture")
    root.geometry("1200x800")
    
    # Set the application icon
    try:
        from PIL import Image, ImageTk
        icon_path = r"C:\Users\walsworthlab\Desktop\SABRE Program\SABREAppICON.png"
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path)
            # Resize icon to appropriate size for window icon (32x32 is standard)
            icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon_image)
            root.iconphoto(True, icon_photo)
            print(f"Application icon set successfully: {icon_path}")
        else:
            print(f"Icon file not found: {icon_path}")
    except ImportError:
        print("PIL/Pillow not available - icon not set")
    except Exception as e:
        print(f"Error setting application icon: {e}")
    
    print("Root window created...")
    style = ttk.Style()
    
    # Configure style for dark tab
    style.configure("DarkTab.TNotebook.Tab", padding=[10, 2],
                   background="#333333", foreground="white")
    style.configure("DarkTab.TNotebook", background="#f0f0f0")
    style.map("DarkTab.TNotebook.Tab",
             background=[("selected", "#555555"), ("active", "#444444")],
             foreground=[("selected", "white"), ("active", "white")])
    
    print("Creating SABREGUI instance...")
    try:
        app = SABREGUI(master=root)
        print("SABREGUI created successfully, starting mainloop...")
        app.mainloop()
    except Exception as e:
        print(f"Error creating SABREGUI: {e}")
        import traceback
        traceback.print_exc()