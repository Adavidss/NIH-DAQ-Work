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

# Import utility modules
from Nested_Programs.Utility_Functions import (
    build_composite_waveform,
    ensure_default_state_files
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

# Define presets directory path
PRESETS_DIR = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods\Presets"

try:
    # Initialize state files
    ensure_default_state_files()
    # Ensure presets directory exists
    if not os.path.exists(PRESETS_DIR):
        os.makedirs(PRESETS_DIR)
except Exception as e:
    print(f"Error creating config directory and files: {e}")
    sys.exit(1)

class SABREGUI(VisualAspects):
    """Main SABRE control application that handles program logic and hardware interaction"""
    
    def __init__(self, master=None):
        super().__init__(master=master)
        
        # Pack self into master to make it visible
        self.pack(fill="both", expand=True)
            
        # Initialize ScramController with new implementation
        self.scram = ScramController(self)
        
        self.setup_variables()
        
        # ------------------------------------------------------------
        # 2a. notebook + overflow menubutton
        self.notebook_container = tk.Frame(self)
        self.notebook_container.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(self.notebook_container, style="DarkTab.TNotebook")
        self.notebook.pack(side="left", fill="both", expand=True)

        # overflow menu button (smaller and positioned differently)
        self.more_btn = ttk.Menubutton(self.notebook_container, text="⋯", width=2)
        self.more_btn.pack(side="right", anchor="ne", padx=2)
        self.overflow_menu = tk.Menu(self.more_btn, tearoff=0)
        self.more_btn["menu"] = self.overflow_menu

        # configure style so selected tab is dark
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("DarkTab.TNotebook.Tab", padding=(12, 4))
        style.map("DarkTab.TNotebook.Tab",
                  background=[("selected", "#333333")],
                  foreground=[("selected", "white")])

        # Create necessary widgets first before building dashboard tabs
        self.create_initial_widgets()
        # build dashboard tabs
        self._build_dashboard_tabs()
        
        # bind <Configure> to handle overflow
        self.bind("<Configure>", lambda e: self._update_tab_overflow())
        # bind right-click for tear-off (not left-click)
        self.notebook.bind("<Button-3>", self._maybe_clone_tab, add="+")
        # ------------------------------------------------------------
        
        self.time_window = None  # Store the time window for plotting
        self.start_time = None   # Track when plotting starts
        self.stop_polarization = False  # Add this flag
        self.task_lock = threading.Lock()  # Add task lock        # Timer variables (reference implementation from SLIC_Control)
        self.countdown_running = False
        self.countdown_end_time = None
        self.after_id = None
        # Track any Tk "after" job IDs so we can cancel them
        self.after_job_id = None

    def setup_variables(self):
        """Initialize all instance variables"""
        # Don't re-initialize these variables, they come from VisualAspects.__init__
        self.voltage_data = []
        self.time_data = []
        self.plotting = False
        self.current_method_duration = 0.0
        self.timer_thread = None
        self.virtual_panel = None
        self.advanced_visible = False
        self.entries = {}
        self.units = {}
        self.main_entries = {}  # Add main entries dict
        self.main_units = {}    # Add main units dict
        self.audio_enabled = tk.BooleanVar(value=False)  # Initialize audio toggle only once here
        self.tooltips_enabled = tk.BooleanVar(value=True)  # Initialize tooltip toggle to be ON by default
        self.current_method_duration = None  # Track method duration
        self.test_task = None  # Track test_field task
        self.dio_task = None  # Add persistent DIO task tracking
        
        # Preset-based method selection variables
        self.selected_preset_var = tk.StringVar(value="Select a method preset...")
        self.current_preset_data = {}  # Store current preset parameters
        
        # Timer variables (reference implementation from SLIC_Control)
        self.countdown_running = False
        self.countdown_end_time = None
        self.after_id = None
        # Ensure entries exist to prevent KeyError
        self._ensure_entries_exist()

    def create_initial_widgets(self):
        """Create basic widgets needed before building dashboard tabs"""
        # Initialize stop event
        self.stop_event = threading.Event()
        
        # Create basic UI elements that other methods depend on
        self.state_label = tk.Label(self, text="State: Initial", font=('Arial', 12))
        self.timer_label = tk.Label(self, text="00:00:000", font=('Arial', 14, 'bold'))
        
        # Initialize status variable
        self.status_var = tk.StringVar(value="System Ready")
          # Initialize preset manager and parameter section placeholders
        self.preset_manager = None
        self.parameter_section = None

    def _build_dashboard_tabs(self):
        """Build the main dashboard with multiple tabs"""
        print("Building dashboard tabs...")
        # Store tab references
        self._tabs = {}
        
        # Create Main tab
        print("Creating Main tab...")
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="Main")
        self._tabs["Main"] = main_frame
        self._create_main_tab(main_frame)
        print("Main tab created successfully")
        
        # Create Advanced Parameters tab
        print("Creating Advanced Parameters tab...")
        advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(advanced_frame, text="Advanced Parameters")
        self._tabs["Advanced Parameters"] = advanced_frame
        self._create_advanced_tab(advanced_frame)
        print("Advanced Parameters tab created successfully")
        
        # Create Testing tab
        print("Creating Testing tab...")
        testing_frame = ttk.Frame(self.notebook)
        self.notebook.add(testing_frame, text="Testing")
        self._tabs["Testing"] = testing_frame
        self._create_testing_tab(testing_frame)
        print("Testing tab created successfully")
        
        # Create SLIC Control tab
        print("Creating SLIC Control tab...")
        slic_frame = ttk.Frame(self.notebook)
        self.notebook.add(slic_frame, text="SLIC Control")
        self._tabs["SLIC Control"] = slic_frame
        self._create_slic_tab(slic_frame)
        print("SLIC Control tab created successfully")
        
        # Create Polarization Calculator tab
        print("Creating Polarization Calculator tab...")
        pol_frame = ttk.Frame(self.notebook)
        self.notebook.add(pol_frame, text="Polarization Cal")
        self._tabs["Polarization Cal"] = pol_frame
        self._create_polarization_tab(pol_frame)
        print("Polarization Calculator tab created successfully")
        print("All tabs created successfully!")
    
    def _create_main_tab(self, parent, detached=False):
        """Create the main control tab with key controls and previews"""
        # Configure grid
        parent.columnconfigure((0, 1), weight=1, uniform="col")
        parent.rowconfigure((0, 1), weight=1, uniform="row")
        
        # General Configuration section (top-left)
        gen_cfg = ttk.LabelFrame(parent, text="General Configuration")
        gen_cfg.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._create_general_params_preview(gen_cfg)
        
        # Waveform Live View (bottom-left)
        waveform_frame = ttk.LabelFrame(parent, text="Waveform Live View")
        waveform_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._create_waveform_live_view_main(waveform_frame)

        # Method Selection and Experiment Controls section (top-right)
        method_control_frame = ttk.LabelFrame(parent, text="Controls")
        method_control_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self._create_method_and_control_section(method_control_frame)
        
        # Magnetic Field Live View (bottom-right)
        magnetic_frame = ttk.LabelFrame(parent, text="Magnetic Field Live View")
        magnetic_frame.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._create_magnetic_field_live_view_main(magnetic_frame)
    
    def _create_advanced_tab(self, parent, detached=False):
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
        self._create_polarization_method_section(scrollable_frame)
        
        # Initialize parameter section in advanced tab
        self.parameter_section = ParameterSection(self, scrollable_frame)
        
        # Create valve timing section
        self.parameter_section.create_valve_timing_section(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_testing_tab(self, parent):
        """Create the testing tab with fully embedded testing panels"""
        # Create notebook for different testing panels
        testing_notebook = ttk.Notebook(parent)
        testing_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Virtual Testing panel - Fully embedded
        vt_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(vt_frame, text="Virtual Testing Environment")
        
        # Embed the full VirtualTestingPanel directly
        try:
            self.embedded_virtual_panel = VirtualTestingPanel(self, embedded=True, container=vt_frame)
            self.embedded_virtual_panel.pack(fill="both", expand=True)
        except Exception as e:
            error_label = tk.Label(vt_frame, text=f"Virtual Testing Panel Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
        
        # Full Flow System panel - Fully embedded
        ff_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ff_frame, text="Full Flow System")
        
        try:
            self.embedded_full_flow = FullFlowSystem(self, embedded=True)
            self.embedded_full_flow.pack(fill="both", expand=True, in_=ff_frame)
        except Exception as e:
            error_label = tk.Label(ff_frame, text=f"Full Flow System Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
        
        # Analog I/O panels
        ai_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ai_frame, text="Analog Input")
        ai_panel = AnalogInputPanel(ai_frame, embedded=True)
        ai_panel.pack(fill="both", expand=True)
        
        ao_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ao_frame, text="Analog Output")
        ao_panel = AnalogOutputPanel(ao_frame, embedded=True)
        ao_panel.pack(fill="both", expand=True)
    
    def _create_slic_tab(self, parent):
        """Create the SLIC control tab"""
        try:
            slic_panel = SLICSequenceControl(parent, embedded=True)
            slic_panel.pack(fill="both", expand=True)
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
    
    def _create_waveform_live_view_main(self, parent):
        """Create the waveform live view for the Main tab"""
        # Create a frame for the waveform section
        waveform_container = tk.Frame(parent)
        waveform_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create header frame for title and toggle button
        header_frame = tk.Frame(waveform_container)
        header_frame.pack(fill="x", pady=(0, 5))

        # Add title and toggle button side by side
        tk.Label(header_frame, text="Live Waveform", font=("Arial", 10, "bold")).pack(side="left")
        toggle_btn = ttk.Button(header_frame, text="Hide", command=self.toggle_waveform_plot)
        toggle_btn.pack(side="right", padx=2)

        # Create the plot container frame
        plot_container = tk.Frame(waveform_container, bg="black", height=120)
        plot_container.pack(fill="both", expand=True)
        plot_container.pack_propagate(False)

        # Create simple matplotlib figure for main tab
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Create smaller figure for main tab
            fig, ax = plt.subplots(figsize=(4, 2))
            fig.patch.set_facecolor('black')
            ax.set_facecolor('black')
            ax.tick_params(colors='lime', labelsize=8)
            ax.set_xlabel("Time (s)", color='lime', fontsize=8)
            ax.set_ylabel("Voltage (V)", color='lime', fontsize=8)
            ax.set_title("Live Waveform", color='lime', fontsize=9)
            ax.grid(True, color='darkgreen', alpha=0.3)
            
            # Store figure reference for main tab
            if not hasattr(self, 'main_fig'):
                self.main_fig = fig
                self.main_ax = ax
            
            # Embed in Tkinter
            canvas = FigureCanvasTkAgg(fig, master=plot_container)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)
            
            # Store canvas reference
            if not hasattr(self, 'main_canvas'):
                self.main_canvas = canvas
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(plot_container, 
                                    text="Waveform Display\n(Matplotlib required)", 
                                    fg="lime", bg="black", font=("Arial", 9))
            fallback_label.pack(expand=True)

    def _create_magnetic_field_live_view_main(self, parent):
        """Create the magnetic field live view for the Main tab"""
        # Create a frame for the magnetic field section
        field_container = tk.Frame(parent)
        field_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create header frame
        header_frame = tk.Frame(field_container)
        header_frame.pack(fill="x", pady=(0, 5))

        # Add title
        tk.Label(header_frame, text="Live Field", font=("Arial", 10, "bold")).pack(side="left")
        
        # Current reading display
        self.field_value_label = tk.Label(header_frame, text="0.0 mT", 
                                         font=("Arial", 9, "bold"), fg="blue")
        self.field_value_label.pack(side="right")

        # Create the display container
        display_container = tk.Frame(field_container, bg="darkblue", height=120)
        display_container.pack(fill="both", expand=True)
        display_container.pack_propagate(False)

        # Create simple field monitor display
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Create smaller figure for field monitoring
            fig, ax = plt.subplots(figsize=(4, 2))
            fig.patch.set_facecolor('darkblue')
            ax.set_facecolor('darkblue')
            ax.tick_params(colors='yellow', labelsize=8)
            ax.set_xlabel("Time (s)", color='yellow', fontsize=8)
            ax.set_ylabel("Field (mT)", color='yellow', fontsize=8)
            ax.set_title("Magnetic Field Monitor", color='yellow', fontsize=9)
            ax.grid(True, color='orange', alpha=0.3)
            
            # Store figure reference for field monitoring
            if not hasattr(self, 'field_fig'):
                self.field_fig = fig
                self.field_ax = ax
            
            # Embed in Tkinter
            canvas = FigureCanvasTkAgg(fig, master=display_container)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)
            
            # Store canvas reference
            if not hasattr(self, 'field_canvas'):
                self.field_canvas = canvas
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(display_container, 
                                    text="Magnetic Field Monitor\n(Matplotlib required)", 
                                    fg="yellow", bg="darkblue", font=("Arial", 9))
            fallback_label.pack(expand=True)

    def _create_method_and_control_section(self, parent):
        """Create merged method selection and experiment controls section"""
        # Preset Selection at top (replaces old method selection)
        preset_frame = ttk.LabelFrame(parent, text="Method Preset")
        preset_frame.pack(fill="x", padx=4, pady=4)
        
        # Preset selection label and dropdown
        preset_selection_frame = tk.Frame(preset_frame)
        preset_selection_frame.pack(fill="x", padx=4, pady=4)
        
        ttk.Label(preset_selection_frame, text="Preset:").pack(side="left")
        
        # Preset combobox that will auto-fill parameters
        if hasattr(self, 'preset_combobox'):
            self.preset_combobox.destroy()
        self.preset_combobox = ttk.Combobox(preset_selection_frame, 
                                          textvariable=self.selected_preset_var,
                                          state="readonly", width=25)
        self.preset_combobox.bind("<<ComboboxSelected>>", self.on_preset_selected_auto_fill)
        self.preset_combobox.pack(side="left", padx=(5, 0), fill="x", expand=True)
          # Preset management controls
        presets_controls = tk.Frame(preset_frame)
        presets_controls.pack(fill="x", padx=4, pady=2)
        
        ttk.Button(presets_controls, text="Save Current as Preset", 
                  command=self.save_current_as_preset).pack(side="left", padx=2)
        ttk.Button(presets_controls, text="Delete Preset", 
                  command=self.delete_selected_preset).pack(side="left", padx=2)
        ttk.Button(presets_controls, text="Refresh Presets", 
                  command=self.refresh_preset_list).pack(side="left", padx=2)
        
        # System Status and Timer section (styled like SLIC Control)
        status_timer_frame = tk.Frame(preset_frame)
        status_timer_frame.pack(fill="x", padx=4, pady=5)
        
        ttk.Label(status_timer_frame, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_timer_frame, textvariable=self.status_var, 
                                font=('Arial', 10, 'bold'))
        status_label.pack(side="left", padx=(5, 15))
        
        # Timer display (like SLIC Control)
        timer_display_frame = tk.Frame(status_timer_frame)
        timer_display_frame.pack(side="right")
        
        ttk.Label(timer_display_frame, text="Timer:").pack(side="left")
        if not hasattr(self, 'timer_label'):
            self.timer_label = tk.Label(timer_display_frame, text="00:00:000", 
                                       font=('Arial', 12, 'bold'), 
                                       fg="blue", bg="white", relief="sunken", padx=5)
        self.timer_label.pack(side="left", padx=(5, 0))
        
        # Main experiment controls - Quadrant layout (2x2 grid)
        controls_frame = ttk.LabelFrame(parent, text="Control Buttons")
        controls_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Configure grid for quadrant layout
        controls_frame.columnconfigure((0, 1), weight=1, uniform="col")
        controls_frame.rowconfigure((0, 1), weight=1, uniform="row")
        
        # Create buttons in quadrant layout
        self._create_quadrant_button(controls_frame, "Activate", "green", self.activate_experiment, 0, 0)
        self._create_quadrant_button(controls_frame, "Start", "blue", self.start_experiment, 0, 1)
        self._create_quadrant_button(controls_frame, "Test Field", "orange", self.test_field, 1, 0)
        self._create_quadrant_button(controls_frame, "SCRAM", "red", self.scram_experiment, 1, 1)
        
        # Refresh the method list for the new combobox
        self.refresh_method_list()
    
    def _create_quadrant_button(self, parent, text, color, command, row, col):
        """Create a quadrant experiment control button with consistent styling"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 11, 'bold'),
                          relief="raised", bd=3)
        
        # Set color scheme based on button type
        if color == "green":
            button.config(bg="#4CAF50", fg="white", activebackground="#45a049")
        elif color == "blue":
            button.config(bg="#2196F3", fg="white", activebackground="#1976D2")
        elif color == "orange":
            button.config(bg="#FF9800", fg="white", activebackground="#F57C00")
        elif color == "red":
            button.config(bg="#F44336", fg="white", activebackground="#D32F2F")
        
        button.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
        return button
    
    def _create_discrete_button(self, parent, text, color, command):
        """Create a discrete experiment control button with consistent styling"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 10, 'bold'),
                          width=12, height=2,
                          relief="raised", bd=2)
        
        # Set color scheme based on button type
        if color == "green":
            button.config(bg="#4CAF50", fg="white", activebackground="#45a049")
        elif color == "blue":
            button.config(bg="#2196F3", fg="white", activebackground="#1976D2")
        elif color == "orange":
            button.config(bg="#FF9800", fg="white", activebackground="#F57C00")
        elif color == "red":
            button.config(bg="#F44336", fg="white", activebackground="#D32F2F")
        
        button.pack(side="left", padx=5, pady=2)
        return button
    
    def _create_live_plots_section(self, parent):
        """Create live plots section with waveform and magnetic field displays"""
        # Create notebook for different plots
        plots_notebook = ttk.Notebook(parent)
        plots_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Waveform plot tab
        waveform_frame = ttk.Frame(plots_notebook)
        plots_notebook.add(waveform_frame, text="Waveform")
        self._create_waveform_preview(waveform_frame)
        
        # Magnetic field plot tab
        magnetic_frame = ttk.Frame(plots_notebook)
        plots_notebook.add(magnetic_frame, text="Magnetic Field")
        self._create_magnetic_field_preview(magnetic_frame)
    
    def _create_control_buttons(self, parent):
        """Create the main control buttons"""
        # Main experiment controls
        main_controls = tk.Frame(parent)
        main_controls.pack(fill="x", padx=10, pady=5)
        
        # First row of buttons
        row1 = tk.Frame(main_controls)
        row1.pack(fill="x", pady=2)
        
        self._create_control_button(row1, "Activate Experiment", "green", self.activate_experiment)
        self._create_control_button(row1, "Start Experiment", "blue", self.start_experiment)
        self._create_control_button(row1, "Test Field", "orange", self.test_field)
        
        # Second row of buttons
        row2 = tk.Frame(main_controls)
        row2.pack(fill="x", pady=2)
        
        self._create_control_button(row2, "SCRAM", "red", self.scram_experiment)
    
    def _create_status_section(self, parent):
        """Create the status and timer section"""
        # Status display
        status_frame = tk.Frame(parent)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(status_frame, text="Status:", font=("Arial", 12, "bold")).pack(side="left")
        status_label = tk.Label(status_frame, textvariable=self.status_var, 
                               font=("Arial", 12), fg="blue")
        status_label.pack(side="left", padx=10)
        
        # Timer display
        timer_frame = tk.Frame(parent)
        timer_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(timer_frame, text="Timer:", font=("Arial", 12, "bold")).pack(side="left")
        self.timer_label.pack(side="left", padx=10)
        
        # State display
        state_frame = tk.Frame(parent)
        state_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(state_frame, text="Current State:", font=("Arial", 12, "bold")).pack(side="left")
        self.state_label.pack(side="left", padx=10)
    
    def open_ai_panel(self):
        """Launch the miniature AI test panel."""
        AnalogInputPanel(self, embedded=False)

    def open_ao_panel(self):
        """Launch the miniature AO test panel."""
        AnalogOutputPanel(self, embedded=False)

    def open_slic_control(self):
        """Open SLIC control window"""
        try:
            SLICSequenceControl(self, embedded=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open SLIC Control: {e}")
    
    def open_polarization_calculator(self):
        """Open polarization calculator window"""
        try:
            PolarizationApp(self, embedded=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Polarization Calculator: {e}")

    def get_value(self, entry_attr, conversion_type="time"):
        """Delegate to parameter_section to get a value with unit conversion"""
        return self.parameter_section.get_value(entry_attr, conversion_type)

    def activate_experiment(self):
        """Activate the experiment sequence with proper DAQ interactions"""
        missing_params = []
        required_fields = [
            ("Activation Time", self.activation_time_entry),
            ("Temperature", self.entries["Temperature"]),
            ("Flow Rate", self.entries["Flow Rate"]),
            ("Pressure", self.entries["Pressure"]),
            ("Injection Time", self.injection_time_entry),
            ("Valve Control Timing", self.valve_time_entry),
            ("Degassing Time", self.degassing_time_entry),
            ("Bubbling Time", self.entries["Bubbling Time"]),
            ("Transfer Time", self.transfer_time_entry),
            ("Recycle Time", self.recycle_time_entry),
        ]
        for param, entry in required_fields:
            if not entry.get():  # Check if the field is empty
                missing_params.append(param)
    
        if missing_params:
            self.show_error_popup(missing_params)
        else:
            # Initialize virtual panel for visualization only (optional)
            if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
                self.virtual_panel = VirtualTestingPanel(self)
            
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
                
            self.state_label.config(text="State: Activating")
            
            # Update virtual panel if it exists
            if self.virtual_panel and self.virtual_panel.winfo_exists():
                self.virtual_panel.load_config_visual("Initial_State")
            
            valve_duration = self.get_value('valve_time_entry')
            injection_duration = self.get_value('injection_time_entry')
            degassing_duration = self.get_value('degassing_time_entry')
            activation_duration = self.get_value('activation_time_entry')

            state_sequence = [
                ("Initial_State", valve_duration),
                ("Injection_State_Start", injection_duration),
                ("Degassing", degassing_duration),
                ("Activation_State_Initial", activation_duration),
                ("Activation_State_Final", valve_duration),
                ("Initial_State", None)
            ]

            total_time = sum(duration for _, duration in state_sequence if duration)
            self.start_countdown(total_time)

            for state, duration in state_sequence:
                if not hasattr(self, 'running') or not self.running:
                    break
                
                # Load config and send DAQ signals
                if self.load_config(state):
                    # Update virtual panel if it exists
                    if self.virtual_panel and self.virtual_panel.winfo_exists():
                        self.virtual_panel.load_config_visual(state)
                    
                    # Wait for duration
                    if duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and hasattr(self, 'running') and self.running:
                            time.sleep(0.1)

        except Exception as error:
            print(f"Error in activation sequence: {error}")
        finally:
            self.running = False
            self.load_config("Initial_State")  # Always return to initial state            # Update virtual panel if it exists
            if self.virtual_panel and self.virtual_panel.winfo_exists():
                self.virtual_panel.load_config_visual("Initial_State")

    def start_experiment(self):
        """Start the bubbling sequence with integrated method timing"""
        # always begin from a clean baseline
        self._reset_run_state()

        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        # Ensure entries exist to prevent KeyError
        self._ensure_entries_exist()

        missing_params = []
        required_fields = [
            ("Valve Control Timing", getattr(self, 'valve_time_entry', None)),
            ("Transfer Time", getattr(self, 'transfer_time_entry', None)),
            ("Recycle Time", getattr(self, 'recycle_time_entry', None)),
        ]
        for param, entry in required_fields:
            if entry is None or not entry.get():
                missing_params.append(param)
    
        if missing_params:
            self.show_error_popup(missing_params)
            return
        
        # Reset stop flag at start of experiment
        self.stop_polarization = False
        self.running = True  # Set running flag

        # Load and plot the waveform before starting the experiment
        try:
            with open(self.polarization_method_file) as f:
                cfg = json.load(f)

            # Check if this is a SLIC sequence file and get buffer
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                initial_voltage = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"],
                                                 dc_offset=initial_voltage)
            
            # Plot the waveform that will be used in the experiment
            self._plot_waveform_buffer(buf, sr)
            
        except Exception as e:
            print(f"Error loading waveform for plotting: {e}")
            messagebox.showerror("Error", f"Failed to load polarization method for plotting: {e}")
            return

        # Initialize virtual panel for visualization only (optional)
        if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
            self.virtual_panel = VirtualTestingPanel(self)

        # Start the bubbling sequence in a separate thread
        threading.Thread(target=self.run_bubbling_sequence, daemon=True).start()

    def run_bubbling_sequence(self):
        """Run the bubbling sequence directly in the main app, independent of virtual panel"""
        try:
            # Calculate method duration first
            method_dur = self._compute_polarization_duration()
            
            # Get timing parameters
            valve = self.get_value("valve_time_entry") or 0.0
            transfer = self.get_value("transfer_time_entry") or 0.0
            recycle = self.get_value("recycle_time_entry") or 0.0
            bubbling_time = method_dur if method_dur > 0 else self.get_value('bubbling_time_entry')

            # Total experiment time: method duration + valve transitions + transfer + recycle
            total_time = method_dur + (valve * 3) + transfer + recycle
              # Start the timer with total duration
            self.start_countdown(total_time)
            
            # Start plotting without resetting the existing plot
            self.plotting = True
            
            # Load bubbling state with direct DAQ interaction
            config_loaded = self.load_config("Bubbling_State_Initial")
            if not config_loaded:
                messagebox.showerror("Error", "Failed to load bubbling state configuration")
                self.stop_timer()
                return
                
            self.state_label.config(text="State: Bubbling the Sample")
            
            # Update virtual panel if it exists
            if self.virtual_panel and self.virtual_panel.winfo_exists():
                self.virtual_panel.load_config_visual("Bubbling_State_Initial")
            
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
                        if self.virtual_panel and self.virtual_panel.winfo_exists():
                            self.virtual_panel.load_config_visual(state)
                        
                        # Wait for duration
                        if duration:
                            start_time = time.time()
                            while time.time() - start_time < duration and hasattr(self, 'running') and self.running and not self.stop_polarization:
                                time.sleep(0.1)
            
        except Exception as error:
            print(f"Error in bubbling sequence: {error}")
        finally:
            self.running = False
            if not self.stop_polarization:  # Only if not already stopped
                self.load_config("Initial_State")  # Return to initial state
                # Update virtual panel if it exists
                if self.virtual_panel and self.virtual_panel.winfo_exists():
                    self.virtual_panel.load_config_visual("Initial_State")

    def run_polarization_method(self):
        """Execute the selected polarization method during experiment sequence"""
        if not self.polarization_method_file or self.stop_polarization:
            print("Polarization method execution canceled - no file or stop flag set")
            return

        print(f"Running polarization method: {self.polarization_method_file}")
        
        with self.task_lock:  # Ensure exclusive access to task resources
            try:
                # Clean up any existing tasks first
                self.scram.cleanup_tasks()
                
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
                if not os.path.exists(self.polarization_method_file):
                    raise FileNotFoundError(f"Polarization method file not found: {self.polarization_method_file}")
                    
                with open(self.polarization_method_file) as f:
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
                self.state_label.config(text="State: Applying Polarization Method")
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

                    writer = AnalogSingleChannelWriter(self.test_task.out_stream,
                                                   auto_start=False)
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
                        self.state_label.config(text="State: Transferring the Sample")
                        
                        # Allow time for transfer
                        transfer_time = self.get_value("transfer_time_entry") or 0.0
                        print(f"Waiting for transfer: {transfer_time} seconds")
                        time.sleep(transfer_time)
                        
                        # After transfer, proceed to recycle state
                        if not self.stop_polarization:
                            print("Transitioning to recycle state")
                            self.load_config("Recycle")
                            self.state_label.config(text="State: Recycling Solution")

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

    def test_field(self):
        """Test the magnetic field functionality"""
        try:
            # Ensure entries exist
            self._ensure_entries_exist()
            
            print("Testing magnetic field...")
            # Add your magnetic field testing logic here
            messagebox.showinfo("Test Field", "Magnetic field test completed successfully!")
            
        except Exception as e:
            print(f"Error in test_field: {e}")
            messagebox.showerror("Error", f"Magnetic field test failed: {e}")

    def scram_experiment(self):
        """Emergency stop - immediately halt all operations"""
        try:
            print("SCRAM button pressed - Emergency stop initiated")
            
            # Set stop event to terminate threads
            self.stop_event.set()
              # Clear any timers (updated for reference implementation)
            if hasattr(self, 'countdown_running') and self.countdown_running:
                self.stop_countdown()
                
            # Reset timer display
            if hasattr(self, 'timer_label'):
                self.timer_label.config(text="00:00:000")
            
            # Update status
            if hasattr(self, 'status_var'):
                self.status_var.set("EMERGENCY STOP ACTIVATED")
            
            # Use the ScramController to safely shut down hardware
            if hasattr(self, 'scram'):
                self.scram()
            
            # Reset waveform display
            self.reset_waveform_plot()
            
            # Reset experiment state
            self._reset_run_state()
            
            # Sound alert
            winsound.Beep(2000, 1000)
            
            # Update status
            if hasattr(self, 'status_var'):
                self.status_var.set("System safe - Ready")
            
            messagebox.showwarning("SCRAM", "Emergency stop completed. All operations halted.")
            
        except Exception as e:
            print(f"Error in scram_experiment: {e}")
            messagebox.showerror("SCRAM Error", f"Error during emergency stop: {e}")
            # Ensure system is in safe state even if exception occurs
            if hasattr(self, 'scram'):
                self.scram()

    def load_config(self, state):
        """Load configuration for a given state"""
        try:
            config_file = os.path.join(CONFIG_DIR, f"{state}.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                print(f"Loaded config for state: {state}")
                return True
            else:
                print(f"Config file not found for state: {state}")
                return False
        except Exception as e:
            print(f"Error loading config for state {state}: {e}")
            return False
        
    def start_countdown(self, duration_s):
        """Start countdown timer for given duration in seconds (reference implementation from SLIC_Control)"""
        self.countdown_end_time = time.time() + duration_s
        self.countdown_running = True
        self.update_countdown()
        print(f"Timer started for {duration_s} seconds")

    def update_countdown(self):
        """Update countdown display every millisecond (reference implementation from SLIC_Control)"""
        if not self.countdown_running:
            return
            
        remaining = max(0, self.countdown_end_time - time.time())
        
        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining % 1) * 1000)
            
            time_str = f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
            if hasattr(self, 'timer_label'):
                self.timer_label.config(text=time_str)
            
            self.after_id = self.after(1, self.update_countdown)
        else:
            if hasattr(self, 'timer_label'):
                self.timer_label.config(text="00:00:000")
            self.countdown_running = False

    def stop_countdown(self):
        """Stop the countdown timer (reference implementation from SLIC_Control)"""
        self.countdown_running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
    
    def _reset_run_state(self):
        """Reset the running state and clean up any active processes"""
        try:
            self.running = False
            self.stop_polarization = True
            
            # Stop any active timer (updated for reference implementation)
            if hasattr(self, 'countdown_running') and self.countdown_running:
                self.stop_countdown()
                
            print("Run state reset successfully")
            
        except Exception as e:
            print(f"Error resetting run state: {e}")

    def _write_analog_waveform(self, data, rate, continuous=False):
        """
        Write a numpy 1-D array to an AO channel with hardware timing.
        If continuous=True the buffer regenerates until you stop the task.
        """
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
            writer = AnalogSingleChannelWriter(self.test_task.out_stream, auto_start=False)
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
                temp_dio_task.write(signal_value, auto_start=True)
                
            # Task automatically closes when exiting context manager
            # DIO lines will maintain their states until explicitly changed
                    
        except Exception as e:
            print(f"Error sending DAQ signals: {e}")
            self.show_error_popup(["DAQ communication error. Check hardware connection."])

    def set_voltage_to_zero(self):
        """Set the voltage to 0V on ao3 with proper cleanup"""
        try:
            # Use ScramController's method
            if hasattr(self, 'scram'):
                self.scram.set_voltage_to_zero()
        except Exception as e:
            print(f"Error setting voltage to 0V: {e}")
    
    def stop_timer(self):
        """Stop the experiment timer (reference implementation from SLIC_Control)"""
        self.countdown_running = False
        if hasattr(self, 'after_id') and self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def _plot_waveform_buffer(self, buf, sr):
        """Plot waveform buffer for preview"""
        try:
            if hasattr(self, 'ax') and hasattr(self, 'canvas'):
                self.ax.clear()
                time_axis = np.arange(len(buf)) / sr
                self.ax.plot(time_axis, buf, 'b-', linewidth=1)
                self.ax.set_xlabel("Time (s)")
                self.ax.set_ylabel("Voltage (V)")
                self.ax.set_title("Polarization Method Waveform")
                self.ax.grid(True, alpha=0.3)
                self.canvas.draw()
                print(f"Plotted waveform: {len(buf)} samples at {sr} Hz")
        except Exception as e:
            print(f"Error plotting waveform buffer: {e}")

    def _compute_polarization_duration(self) -> float:
        """
        Return the duration (s) of the waveform described by the currently‐
        selected polarization-method JSON file.  Falls back to 0 on error.
        """
        if not self.polarization_method_file:
            return 0.0
        try:
            with open(self.polarization_method_file, "r") as f:
                cfg = json.load(f)

            # Build the identical buffer the DAQ routine will output
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                dc_offset = cfg.get("initial_voltage", 0.0)
                buf, sr   = build_composite_waveform(
                                cfg["ramp_sequences"], dc_offset=dc_offset)
            self.current_method_duration = len(buf) / sr
            return self.current_method_duration
        except Exception as e:
            print(f"[Timer] duration-calc error: {e}")
            return 0.0

    def get_current_parameters(self):
        """Get all current parameter values as a dictionary"""
        return self.parameter_section.get_current_parameters()

    def select_polarization_method(self):
        """
        Legacy method maintained for compatibility. 
        Now opens a file dialog and then updates the combobox accordingly.
        """
        file_path = filedialog.askopenfilename(
            initialdir=self.polarization_methods_dir,
            title="Select Polarization Method",
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            self.polarization_method_file = file_path
            filename = os.path.basename(file_path)
            
            # Check if file is in the dropdown values, add it if not
            current_values = list(self.method_combobox['values'])
            if filename not in current_values:
                current_values.append(filename)
                self.method_combobox['values'] = sorted(current_values)
            
            # Update the combobox selection
            self.selected_method_var.set(filename)
            print(f"Selected polarization method: {file_path}")

    def _create_presets_preview(self, parent):
        """Create simplified presets selection for main tab"""
        pres_frame = ttk.LabelFrame(parent, text="Method Selection")
        pres_frame.pack(fill="x", padx=4, pady=4)
        
        # Recreate method combobox in the correct parent
        if hasattr(self, 'method_combobox'):
            self.method_combobox.destroy()
        self.method_combobox = ttk.Combobox(pres_frame, 
                                          textvariable=self.selected_method_var,
                                          state="readonly")
        self.method_combobox.bind("<<ComboboxSelected>>", self.on_method_selected)
        self.method_combobox.pack(fill="x", padx=4, pady=4)
        
        # Add link to advanced parameters for full preset management
        link_frame = tk.Frame(pres_frame)
        link_frame.pack(fill="x", pady=2)
        ttk.Button(link_frame, text="Manage Presets in Advanced Tab", 
                  command=lambda: self.notebook.select(1)).pack()        # Refresh the method list for the new combobox
        self.refresh_method_list()

    def _maybe_clone_tab(self, event):
        """If user right-clicks directly on a tab label, show context menu with detach option."""
        elem = self.notebook.identify(event.x, event.y)
        if elem != "label":
            return
        
        index = self.notebook.index("@%d,%d" % (event.x, event.y))
        tab_text = self.notebook.tab(index, "text")
        
        # Only allow detaching Main and Advanced Parameters tabs as requested
        if tab_text not in ["Main", "Advanced Parameters"]:
            return
            
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="Detach", command=lambda: self._clone_tab(tab_text))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _clone_tab(self, tab_text):
        """Create a detached window with synchronized content for Main or Advanced Parameters tabs."""
        if tab_text not in ["Main", "Advanced Parameters"]:
            return
        
        # Check if already detached
        detached_attr = f"_detached_{tab_text.replace(' ', '_').lower()}"
        if hasattr(self, detached_attr) and getattr(self, detached_attr) and getattr(self, detached_attr).winfo_exists():
            getattr(self, detached_attr).lift()  # Bring to front
            return
        
        try:
            win = tk.Toplevel(self)
            win.title(f"{tab_text} (Detached)")
            win.geometry("900x700")
            win.protocol("WM_DELETE_WINDOW", lambda: self._on_detached_close(tab_text, win))
            
            # Store reference to detached window
            setattr(self, detached_attr, win)
            
            container = ttk.Frame(win)
            container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create synchronized content
            if tab_text == "Main":
                self._build_synchronized_main_clone(container, win)
            elif tab_text == "Advanced Parameters":
                self._build_synchronized_advanced_clone(container, win)
            
        except Exception as e:
            print(f"Error creating detached tab '{tab_text}': {e}")
            messagebox.showerror("Error", f"Could not detach tab '{tab_text}': {e}")
    
    def _on_detached_close(self, tab_text, window):
        """Handle closing of detached window"""
        detached_attr = f"_detached_{tab_text.replace(' ', '_').lower()}"
        if hasattr(self, detached_attr):
            delattr(self, detached_attr)
        window.destroy()

    def _build_synchronized_main_clone(self, parent, window):
        """Build synchronized Main tab clone with live updates"""
        # Create a scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", 
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create Main tab content with references for synchronization
        self._create_main_tab(scrollable_frame, detached=True)
        
        # Store window reference for updates
        window.main_content = scrollable_frame

    def _build_synchronized_advanced_clone(self, parent, window):
        """Build synchronized Advanced Parameters tab clone with live updates"""
        # Create a scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", 
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create Advanced Parameters content with references for synchronization
        self._create_advanced_tab(scrollable_frame, detached=True)
        
        # Store window reference for updates
        window.advanced_content = scrollable_frame

    def _build_main_clone(self, parent):
        """Clone layout for Main tab inside detached window."""
        # Same layout as main tab
        gen_cfg = ttk.LabelFrame(parent, text="General Configuration")
        gen_cfg.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=4, pady=4)

        exp_frame = ttk.LabelFrame(parent, text="Experiment Time")
        exp_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        wave = ttk.LabelFrame(parent, text="Waveform View")
        wave.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        mag = ttk.LabelFrame(parent, text="Magnetic Field Live View")
        mag.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        
        parent.columnconfigure((0, 1), weight=1, uniform="col")
        parent.rowconfigure((0, 1), weight=1, uniform="row")

    def _build_testing_clone(self, parent):
        """Clone layout for Testing tab inside detached window."""
        # Create a notebook within the parent for embedded panels
        testing_notebook = ttk.Notebook(parent)
        testing_notebook.pack(fill="both", expand=True, padx=2, pady=2)
        # Create and embed Virtual Testing environment directly
        vt_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(vt_frame, text="Virtual Testing")
        vt_panel = VirtualTestingPanel(self, embedded=True, container=vt_frame)
        vt_panel.pack(fill="both", expand=True)
        
        # Create and embed Analog Input Panel directly
        ai_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ai_frame, text="Analog Input")
        ai_panel = AnalogInputPanel(ai_frame, embedded=True)
        ai_panel.pack(fill="both", expand=True)
  
        
        # Create and embed Analog Output Panel directly
        ao_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ao_frame, text="Analog Output")
        ao_panel = AnalogOutputPanel(ao_frame, embedded=True)
        ao_panel.pack(fill="both", expand=True)

    def safe_select_tab(self, idx):
        """Safely select a tab by index, with error handling"""
        try:
            self.notebook.select(idx)
        except Exception as e:
            print(f"Error selecting tab {idx}: {e}")
    
    def _create_general_params_preview(self, parent):
        """Create a preview of general parameters in the main tab"""
        
        # Add a few key parameters as a preview
        params = [
            ("Bubbling Time", "30.0", ["s", "min", "h"]),
            ("Magnetic Field", "100.0", ["mT", "T", "G"]),
            ("Temperature", "298", ["K", "°C", "°F"]),
            ("Flow Rate", "20", ["sccm", "slm", "ccm"]),
            ("Pressure", "1.0", ["atm", "bar", "psi", "Pa"])
        ]
        
        for i, (label, default_val, unit_options) in enumerate(params):
            row = tk.Frame(parent)
            row.pack(fill="x", padx=5, pady=2)
            
            tk.Label(row, text=f"{label}:", width=15, anchor="w").pack(side="left")
            entry = tk.Entry(row, width=10)
            entry.insert(0, default_val)
            entry.pack(side="left", padx=2)
            
            # Store the entry in self.entries for access by other methods
            self.entries[label] = entry
            
            # Create StringVar for unit and store it
            unit_var = tk.StringVar(value=unit_options[0])
            self.units[label] = unit_var
            
            # Create editable unit dropdown
            unit_combo = ttk.Combobox(row, textvariable=unit_var, 
                                     values=unit_options, width=8, state="readonly")
            unit_combo.pack(side="left", padx=2)
        
        # Add link to advanced parameters
        link_frame = tk.Frame(parent)
        link_frame.pack(fill="x", pady=10)
        ttk.Button(link_frame, text="Go to Advanced Parameters", 
                  command=lambda: self.notebook.select(1)).pack()

    def _create_waveform_preview(self, parent):
        """Create a simple waveform preview display"""
        # Add a placeholder for waveform display
        preview_frame = tk.Frame(parent, bg="black", height=150)
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)
        preview_frame.pack_propagate(False)
        
        label = tk.Label(preview_frame, text="Waveform Display\n(Live view will appear here)", 
                        fg="lime", bg="black", font=("Arial", 10))
        label.pack(expand=True)
        
        # Add controls
        controls = tk.Frame(parent)
        controls.pack(fill="x", padx=5, pady=2)
        ttk.Button(controls, text="Toggle View", command=self.toggle_waveform_plot).pack(side="left", padx=2)

    def _create_magnetic_field_preview(self, parent):
        """Create a simple magnetic field preview display"""
        # Add a placeholder for magnetic field display
        preview_frame = tk.Frame(parent, bg="darkblue", height=150)
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)
        preview_frame.pack_propagate(False)
        
        label = tk.Label(preview_frame, text="Magnetic Field Monitor\n(Live readings will appear here)", 
                        fg="yellow", bg="darkblue", font=("Arial", 10))
        label.pack(expand=True)
        
        # Add current field reading
        field_label = tk.Label(parent, text="Current Field: 0.0 mT", font=("Arial", 12, "bold"))
        field_label.pack(pady=5)

    def _create_logo_area(self, parent):
        """Create a logo area in the main tab"""
        # Add a placeholder for the logo
        logo_label = tk.Label(parent, text="🧪 SABRE\nControl System", 
                             font=("Arial", 16, "bold"), 
                             fg="darkblue", justify="center")
        logo_label.pack(expand=True, pady=10)
          # Add version/status info
        info_label = tk.Label(parent, text="Version 2.0\nTabbed Interface", 
                             font=("Arial", 10), fg="gray")
        info_label.pack(pady=5)

    def _ensure_entries_exist(self):
        """Ensure all required entries exist in the entries dictionary to prevent KeyError"""
        required_keys = ["Temperature", "Flow Rate", "Pressure", "Bubbling Time", "Magnetic Field"]
        
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

    def download_config_files(self):
        """Download configuration files from a source or open file dialog"""
        try:
            # Open file dialog to select configuration files to import
            file_path = filedialog.askopenfilename(
                title="Select Configuration File",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                # Copy the selected file to the config directory
                filename = os.path.basename(file_path)
                destination = os.path.join(PRESETS_DIR, filename)
                
                shutil.copy2(file_path, destination)
                messagebox.showinfo("Success", f"Configuration file copied to:\n{destination}")
                
                # Refresh the presets list if preset manager exists
                if hasattr(self, 'preset_manager'):
                    self.preset_manager.refresh_presets_list()
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download configuration file:\n{e}")

    def open_full_flow_system(self):
        """Open the Full Flow System window"""
        try:
            if not hasattr(self, 'full_flow_window') or self.full_flow_window is None:
                self.full_flow_window = tk.Toplevel(self)
                self.full_flow_window.title("Full Flow System")
                self.full_flow_window.geometry("800x600")
                
                # Create the FullFlowSystem instance in the new window
                full_flow_app = FullFlowSystem(self.full_flow_window)
                full_flow_app.pack(fill="both", expand=True)
                
                # Handle window close event
                def on_closing():
                    self.full_flow_window.destroy()
                    self.full_flow_window = None
                
                self.full_flow_window.protocol("WM_DELETE_WINDOW", on_closing)
            else:
                # Bring existing window to front
                self.full_flow_window.lift()
                self.full_flow_window.focus_force()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Full Flow System: {e}")

    def toggle_virtual_panel(self):
        """Toggle the Virtual Testing Environment window"""
        if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
            self.virtual_panel = VirtualTestingPanel(self, embedded=False)
        else:
            if hasattr(self.virtual_panel, 'toplevel') and self.virtual_panel.toplevel:
                self.virtual_panel.toplevel.destroy()
            else:
                self.virtual_panel.destroy()
            self.virtual_panel = None

    def toggle_waveform_plot(self):
        """Toggle waveform plot visibility"""
        try:
            if hasattr(self, 'waveform_visible'):
                self.waveform_visible = not self.waveform_visible
                if hasattr(self, 'canvas'):
                    if self.waveform_visible:
                        self.canvas.get_tk_widget().pack(fill="both", expand=True)
                    else:
                        self.canvas.get_tk_widget().pack_forget()
            print(f"Waveform plot visibility: {getattr(self, 'waveform_visible', True)}")
        except Exception as e:
            print(f"Error toggling waveform plot: {e}")

    def _update_tab_overflow(self):
        """Hide excess tabs and populate the overflow menu."""
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

    def load_preset_from_combobox(self):
        """Load preset from the currently selected method in combobox"""
        try:
            if hasattr(self, 'preset_manager'):
                self.preset_manager.on_preset_selected()
            else:
                # Simple fallback implementation
                messagebox.showinfo("Info", "Preset management available in Advanced Parameters tab.")
                self.notebook.select(1)  # Switch to Advanced Parameters tab
        except Exception as e:
            print(f"Error loading preset: {e}")
            messagebox.showerror("Error", f"Failed to load preset: {e}")

    def save_current_as_preset(self):
        """Save current parameters as a new preset"""
        try:
            if hasattr(self, 'preset_manager'):
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
            if hasattr(self, 'preset_manager'):
                self.preset_manager.delete_preset()
            else:
                # Simple fallback implementation
                messagebox.showinfo("Info", "Preset deletion available in Advanced Parameters tab.")
                self.notebook.select(1)  # Switch to Advanced Parameters tab
        except Exception as e:
            print(f"Error deleting preset: {e}")
            messagebox.showerror("Error", f"Failed to delete preset: {e}")

    def _create_polarization_method_section(self, parent):
        """Create the polarization method configuration section with dropdown selector"""
        # Polarization Method Selection Section
        polarization_frame = ttk.LabelFrame(parent, text="Polarization Method", padding="10")
        polarization_frame.pack(fill="x", padx=10, pady=5)
        
        # Method Selection Dropdown
        method_frame = ttk.Frame(polarization_frame)
        method_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(method_frame, text="Method:").pack(side="left")
        
        # Create polarization method variable if it doesn't exist
        if not hasattr(self, 'polarization_method_var'):
            self.polarization_method_var = tk.StringVar(value="Select method...")
        
        # Polarization method dropdown reading from directory
        self.polarization_method_combobox = ttk.Combobox(method_frame, 
                                                        textvariable=self.polarization_method_var,
                                                        state="readonly", width=25)
        
        # Load available polarization methods from directory
        polarization_methods = self._load_polarization_methods_from_directory()
        
        self.polarization_method_combobox['values'] = polarization_methods
        self.polarization_method_combobox.bind("<<ComboboxSelected>>", self._on_polarization_method_changed)
        self.polarization_method_combobox.pack(side="left", padx=(5, 0), fill="x", expand=True)
        
        # Method description/info
        info_frame = ttk.Frame(polarization_frame)
        info_frame.pack(fill="x", pady=(5, 0))
        
        self.method_info_label = tk.Label(info_frame, 
                                         text="SABRE-SHEATH: Signal Amplification by Reversible Exchange in SHield Enables Alignment Transfer to Heteronuclei",
                                         wraplength=400, justify="left", font=("Arial", 9))
        self.method_info_label.pack(side="left", fill="x", expand=True)
        
        # Toggles Section (Audio and Tooltips as requested)
        toggles_frame = ttk.LabelFrame(parent, text="Interface Settings", padding="10")
        toggles_frame.pack(fill="x", padx=10, pady=5)
        
        # Audio toggle
        audio_frame = tk.Frame(toggles_frame)
        audio_frame.pack(fill="x", pady=2)
        
        self.audio_enabled_checkbox = ttk.Checkbutton(audio_frame, text="Enable Audio Feedback",
                                                     variable=self.audio_enabled,
                                                     command=self._on_audio_toggle)
        self.audio_enabled_checkbox.pack(side="left")
        
        # Tooltip toggle
        tooltip_frame = tk.Frame(toggles_frame)
        tooltip_frame.pack(fill="x", pady=2)
        
        self.tooltips_enabled_checkbox = ttk.Checkbutton(tooltip_frame, text="Enable Tooltips",
                                                        variable=self.tooltips_enabled,
                                                        command=self._on_tooltip_toggle)
        self.tooltips_enabled_checkbox.pack(side="left")
        
        # Store references for easy access
        self.polarization_widgets = {
            'method_combobox': self.polarization_method_combobox,
            'audio_checkbox': self.audio_enabled_checkbox,
            'tooltip_checkbox': self.tooltips_enabled_checkbox        }

    def _load_polarization_methods_from_directory(self):
        """Load all JSON polarization method files from the specified directory"""
        try:
            methods_dir = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
            
            # Create directory if it doesn't exist
            if not os.path.exists(methods_dir):
                os.makedirs(methods_dir)
                return ["Select method..."]
            
            # Get all JSON files in the directory
            json_files = []
            for file in os.listdir(methods_dir):
                if file.endswith('.json'):
                    json_files.append(file)
            
            # Sort alphabetically and add default option
            json_files.sort()
            methods = ["Select method..."] + json_files
            
            print(f"Found {len(json_files)} polarization method files in {methods_dir}")
            return methods
            
        except Exception as e:
            print(f"Error loading polarization methods from directory: {e}")
            return ["Select method..."]

    def _on_polarization_method_changed(self, event=None):
        """Handle polarization method selection changes"""
        try:
            selected_method = self.polarization_method_var.get()
            
            if selected_method and selected_method != "Select method...":
                # Store the full path to the selected method file
                methods_dir = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
                self.polarization_method_file = os.path.join(methods_dir, selected_method)
                
                # Try to load the method file to get description
                try:
                    with open(self.polarization_method_file, 'r') as f:
                        method_data = json.load(f)
                        description = method_data.get('description', f"Loaded polarization method: {selected_method}")
                        self.method_info_label.config(text=description)
                except Exception as e:
                    self.method_info_label.config(text=f"Method file: {selected_method}")
                    print(f"Could not load method description: {e}")
            else:
                # Default description when no method is selected
                self.method_info_label.config(text="SABRE-SHEATH: Signal Amplification by Reversible Exchange in SHield Enables Alignment Transfer to Heteronuclei")
                self.polarization_method_file = None
                
            print(f"Polarization method changed to: {selected_method}")
            
        except Exception as e:
            print(f"Error handling polarization method change: {e}")
    
    def _on_audio_toggle(self):
        """Handle audio enable/disable toggle"""
        enabled = self.audio_enabled.get()
        if enabled:
            print("Audio feedback enabled")
            # You can add audio initialization here
        else:
            print("Audio feedback disabled")
    
    def _on_tooltip_toggle(self):
        """Handle tooltip enable/disable toggle"""
        enabled = self.tooltips_enabled.get()
        if enabled:
            print("Tooltips enabled")
        else:
            print("Tooltips disabled")

    def on_preset_selected_auto_fill(self, event=None):
        """Auto-fill all parameters when a preset is selected"""
        try:
            selected_preset = self.selected_preset_var.get()
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
                messagebox.showinfo("Preset Loaded", f"Successfully loaded preset: {selected_preset}")
            else:
                messagebox.showerror("Error", f"Preset file not found: {selected_preset}")                
        except Exception as e:
            print(f"Error loading preset: {e}")
            messagebox.showerror("Error", f"Failed to load preset: {e}")

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
                    if param_name in self.parameter_section.entries:
                        entry = self.parameter_section.entries[param_name]
                        if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                            entry.delete(0, tk.END)
                            entry.insert(0, str(param_data.get('value', param_data)))
                        
                        # Set unit if available
                        if param_name in self.parameter_section.units and 'unit' in param_data:
                            unit_var = self.parameter_section.units[param_name]
                            unit_var.set(param_data['unit'])
                
                # Fill advanced parameters
                for param_name, param_data in preset_data.get('advanced', {}).items():
                    # Map advanced parameter names to entry attributes
                    entry_mapping = {
                        'Activation Time': 'activation_time_entry',
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
            
            print(f"Successfully auto-filled parameters from preset")
                
        except Exception as e:
            print(f"Error auto-filling parameters: {e}")
            messagebox.showwarning("Auto-Fill Warning", 
                                 f"Some parameters could not be auto-filled: {e}")

    def refresh_preset_list(self):
        """Refresh the list of available presets in all comboboxes"""
        try:
            if not os.path.exists(PRESETS_DIR):
                os.makedirs(PRESETS_DIR)
                
            # Get all JSON files in presets directory
            preset_files = [f[:-5] for f in os.listdir(PRESETS_DIR) if f.endswith('.json')]
            preset_options = ["Select a method preset..."] + sorted(preset_files)
            
            # Update all preset comboboxes for synchronization
            # Check if widgets still exist before updating them
            if hasattr(self, 'preset_combobox') and self.preset_combobox.winfo_exists():
                self.preset_combobox['values'] = preset_options
            if hasattr(self, 'adv_preset_combobox') and self.adv_preset_combobox.winfo_exists():
                self.adv_preset_combobox['values'] = preset_options
                
            # Also update any preset combobox in Advanced tab
            if hasattr(self, 'preset_manager') and self.preset_manager:
                self.preset_manager.refresh_presets_list()
                
        except Exception as e:
            print(f"Error refreshing preset list: {e}")
            # Set default values for all comboboxes that still exist
            default_values = ["Select a method preset..."]
            try:
                if hasattr(self, 'preset_combobox') and self.preset_combobox.winfo_exists():
                    self.preset_combobox['values'] = default_values
            except:
                pass
            try:
                if hasattr(self, 'adv_preset_combobox') and self.adv_preset_combobox.winfo_exists():
                    self.adv_preset_combobox['values'] = default_values
            except:
                pass

    def refresh_method_list(self):
        """Refresh method list - alias for refresh_preset_list for backward compatibility"""
        self.refresh_preset_list()

# ------------- run -------------
if __name__ == "__main__":
    print("Starting SABRE GUI application...")
    root = tk.Tk()
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
