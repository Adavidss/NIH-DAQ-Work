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
import csv
from pathlib import Path

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

# Define polarization data sets directory
POLARIZATION_DATA_DIR = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationDataSets"

try:
    # Initialize state files
    ensure_default_state_files()
    # Ensure presets directory exists
    if not os.path.exists(PRESETS_DIR):
        os.makedirs(PRESETS_DIR)
    # Ensure polarization data directory exists
    if not os.path.exists(POLARIZATION_DATA_DIR):
        os.makedirs(POLARIZATION_DATA_DIR)
except Exception as e:
    print(f"Error creating config directory and files: {e}")
    sys.exit(1)


class EnhancedToolTip(ToolTip):
    """Enhanced tooltip class that works on all tabs with dynamic registration"""
    
    _registered_tooltips = []  # Class variable to track all tooltips
    
    def __init__(self, widget, text, parent=None, tab_name=None):
        super().__init__(widget, text, parent)
        self.tab_name = tab_name
        EnhancedToolTip._registered_tooltips.append(self)
    
    @classmethod
    def register_tooltip_for_widget(cls, widget, text, parent=None, tab_name=None):
        """Register a tooltip for any widget on any tab"""
        return cls(widget, text, parent, tab_name)
    
    @classmethod
    def toggle_all_tooltips(cls, enabled):
        """Toggle all registered tooltips"""
        for tooltip in cls._registered_tooltips:
            if hasattr(tooltip.parent, 'tooltips_enabled'):
                tooltip.parent.tooltips_enabled.set(enabled)


class DetachedTabWindow:
    """Manages detached tab windows with live synchronization"""
    
    def __init__(self, parent_gui, tab_name, tab_content_creator):
        self.parent_gui = parent_gui
        self.tab_name = tab_name
        self.tab_content_creator = tab_content_creator
        self.window = None
        self.synced_widgets = {}  # Track widgets that need synchronization
        
    def create_detached_window(self):
        """Create a detached window with live-synced content"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
            
        self.window = tk.Toplevel(self.parent_gui.master)
        self.window.title(f"SABRE - {self.tab_name} (Detached)")
        self.window.geometry("800x600")
        
        # Create tab content in detached window
        content_frame = ttk.Frame(self.window)
        content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create the tab content (this should create synchronized widgets)
        self.tab_content_creator(content_frame, detached=True)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        return self.window
    
    def on_window_close(self):
        """Handle detached window closing"""
        if self.window:
            self.window.destroy()
            self.window = None
    
    def sync_widget_values(self, widget_id, value):
        """Synchronize widget values between original and detached tabs"""
        if widget_id in self.synced_widgets:
            for widget in self.synced_widgets[widget_id]:
                try:
                    if hasattr(widget, 'set'):
                        widget.set(value)
                    elif hasattr(widget, 'insert'):
                        widget.delete(0, tk.END)
                        widget.insert(0, value)
                except:
                    pass  # Widget might be destroyed


class SABREGUI(VisualAspects):
    """Main SABRE control application that handles program logic and hardware interaction"""
    
    def __init__(self, master=None):
        super().__init__(master=master)
        
        # Pack self into master to make it visible
        self.pack(fill="both", expand=True)
            
        # Initialize ScramController with new implementation
        self.scram = ScramController(self)
        
        # Detached windows management
        self.detached_windows = {}
        
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
        # bind left-click for tab detaching (NEW: changed from right-click)
        self.notebook.bind("<Button-1>", self._maybe_detach_tab, add="+")
        # ------------------------------------------------------------
        
        self.time_window = None  # Store the time window for plotting
        self.start_time = None   # Track when plotting starts
        self.stop_polarization = False  # Add this flag
        self.task_lock = threading.Lock()  # Add task lock
        
        # Timer variables - Enhanced persistent timer
        self.timer_running = False
        self.timer_start_time = None
        self.timer_duration = 0
        self.timer_mode = "idle"  # "idle", "countdown", "elapsed"
        self.after_id = None

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
        self.audio_enabled = tk.BooleanVar(value=False)
        self.tooltips_enabled = tk.BooleanVar(value=True)
        self.current_method_duration = None  # Track method duration
        self.test_task = None  # Track test_field task
        self.dio_task = None  # Add persistent DIO task tracking
        
        # Preset-based method selection variables
        self.selected_preset_var = tk.StringVar(value="Select a method preset...")
        self.current_preset_data = {}  # Store current preset parameters
        
        # Waveform data for live plotting
        self.waveform_time_data = np.linspace(0, 1, 100)
        self.waveform_voltage_data = np.zeros(100)
        
        # Ensure entries exist to prevent KeyError
        self._ensure_entries_exist()

    def create_initial_widgets(self):
        """Create basic widgets needed before building dashboard tabs"""
        # Initialize stop event
        self.stop_event = threading.Event()
        
        # Create basic UI elements that other methods depend on
        self.state_label = tk.Label(self, text="State: Initial", font=('Arial', 12))
        
        # Enhanced persistent timer widget
        self.timer_label = tk.Label(self, text="Timer: 00:00:000", 
                                   font=('Arial', 14, 'bold'), 
                                   fg="blue", bg="white", relief="sunken", padx=5)
        
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
        
        # Create Polarization Calculator tab (renamed)
        print("Creating % Polarization Calculator tab...")
        pol_frame = ttk.Frame(self.notebook)
        self.notebook.add(pol_frame, text="% Polarization Calc")
        self._tabs["% Polarization Calc"] = pol_frame
        self._create_enhanced_polarization_tab(pol_frame)
        print("% Polarization Calculator tab created successfully!")
        print("All tabs created successfully!")
    
    def _create_main_tab(self, parent, detached=False):
        """Create the main control tab with enhanced layout and styling"""
        # Configure grid for equal-sized sections
        parent.columnconfigure((0, 1), weight=1, uniform="col")
        parent.rowconfigure((0, 1), weight=1, uniform="row")
        
        # General Configuration section (top-left) - enhanced
        gen_cfg = ttk.LabelFrame(parent, text="General Configuration")
        gen_cfg.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._create_general_params_preview(gen_cfg)
        
        # Enhanced Waveform Live View (bottom-left)
        waveform_frame = ttk.LabelFrame(parent, text="Live Waveform")
        waveform_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._create_enhanced_waveform_live_view(waveform_frame)

        # Experimental Controls section (top-right) - renamed and enhanced
        method_control_frame = ttk.LabelFrame(parent, text="Experimental Controls")
        method_control_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self._create_enhanced_method_and_control_section(method_control_frame)
        
        # Magnetic Field Live View (bottom-right)
        magnetic_frame = ttk.LabelFrame(parent, text="Magnetic Field Live View")
        magnetic_frame.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._create_magnetic_field_live_view_main(magnetic_frame)
        
        # Register tooltips for this tab
        if not detached:
            self._register_tab_tooltips(parent, "Main")
    
    def _create_advanced_tab(self, parent, detached=False):
        """Create the advanced parameters tab with enhanced styling"""
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
        
        # Enhanced Polarization Method controls (remove stray text)
        self._create_enhanced_polarization_method_section(scrollable_frame)
        
        # Initialize parameter section in advanced tab
        self.parameter_section = ParameterSection(self, scrollable_frame)
        
        # Create valve timing section
        self.parameter_section.create_valve_timing_section(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Register tooltips for this tab
        if not detached:
            self._register_tab_tooltips(parent, "Advanced Parameters")
    
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
        
        # Register tooltips for this tab
        self._register_tab_tooltips(parent, "Testing")
    
    def _create_slic_tab(self, parent):
        """Create the SLIC control tab"""
        try:
            slic_panel = SLICSequenceControl(parent, embedded=True)
            slic_panel.pack(fill="both", expand=True)
        except Exception as e:
            error_label = tk.Label(parent, text=f"SLIC Control Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
        
        # Register tooltips for this tab
        self._register_tab_tooltips(parent, "SLIC Control")
    
    def _create_enhanced_polarization_tab(self, parent):
        """Create the enhanced polarization calculator tab with Save/Load functionality"""
        # Main container
        main_container = ttk.Frame(parent)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Enhanced controls frame
        controls_frame = ttk.LabelFrame(main_container, text="Data Set Management")
        controls_frame.pack(fill="x", padx=5, pady=5)
        
        # Data set controls
        dataset_frame = tk.Frame(controls_frame)
        dataset_frame.pack(fill="x", padx=5, pady=5)
        
        # Save Data Set button
        save_btn = ttk.Button(dataset_frame, text="Save Data Set", 
                             command=self._save_polarization_dataset)
        save_btn.pack(side="left", padx=5)
        
        # Load Data Set dropdown
        tk.Label(dataset_frame, text="Load Data Set:").pack(side="left", padx=(20, 5))
        self.dataset_var = tk.StringVar(value="Select dataset...")
        self.dataset_combobox = ttk.Combobox(dataset_frame, textvariable=self.dataset_var,
                                           state="readonly", width=25)
        self.dataset_combobox.bind("<<ComboboxSelected>>", self._load_polarization_dataset)
        self.dataset_combobox.pack(side="left", padx=5)
        
        # Refresh datasets button
        refresh_btn = ttk.Button(dataset_frame, text="Refresh", 
                               command=self._refresh_dataset_list)
        refresh_btn.pack(side="left", padx=5)
        
        # Original polarization calculator
        try:
            pol_panel = PolarizationApp(main_container, embedded=True)
            pol_panel.pack(fill="both", expand=True)
            
            # Store reference to access data
            self.polarization_panel = pol_panel
        except Exception as e:
            error_label = tk.Label(main_container, text=f"Polarization Calculator Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
        
        # Initialize dataset list
        self._refresh_dataset_list()
        
        # Register tooltips for this tab
        self._register_tab_tooltips(parent, "% Polarization Calc")
    
    def _create_enhanced_waveform_live_view(self, parent):
        """Create enhanced waveform live view with actual matplotlib plot and refresh button"""
        # Create a frame for the waveform section
        waveform_container = tk.Frame(parent)
        waveform_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create header frame for title and refresh button
        header_frame = tk.Frame(waveform_container)
        header_frame.pack(fill="x", pady=(0, 5))

        # Add title and refresh button side by side
        tk.Label(header_frame, text="Live Waveform", font=("Arial", 10, "bold")).pack(side="left")
        refresh_btn = ttk.Button(header_frame, text="Refresh", command=self.refresh_waveform_plot)
        refresh_btn.pack(side="right", padx=2)

        # Create the plot container frame
        plot_container = tk.Frame(waveform_container, bg="black", height=120)
        plot_container.pack(fill="both", expand=True)
        plot_container.pack_propagate(False)

        # Create actual matplotlib figure for waveform display
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Create figure for main tab
            fig, ax = plt.subplots(figsize=(4, 2))
            fig.patch.set_facecolor('black')
            ax.set_facecolor('black')
            ax.tick_params(colors='lime', labelsize=8)
            ax.set_xlabel("Time (s)", color='lime', fontsize=8)
            ax.set_ylabel("Voltage (V)", color='lime', fontsize=8)
            ax.set_title("Live Waveform", color='lime', fontsize=9)
            ax.grid(True, color='darkgreen', alpha=0.3)
              # Initialize with sample waveform data
            self.waveform_line, = ax.plot(self.waveform_time_data, self.waveform_voltage_data, 
                                        color='lime', linestyle='-', linewidth=1)
            
            # Store figure reference
            self.main_waveform_fig = fig
            self.main_waveform_ax = ax
            
            # Embed in Tkinter
            canvas = FigureCanvasTkAgg(fig, master=plot_container)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)
            
            # Store canvas reference
            self.main_waveform_canvas = canvas
            
            # Initial plot refresh
            self.refresh_waveform_plot()
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(plot_container, 
                                    text="Enhanced Waveform Display\n(Matplotlib required)", 
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

        # Field strength bar or gauge
        self.field_display = tk.Canvas(display_container, bg="darkblue", highlightthickness=0)
        self.field_display.pack(fill="both", expand=True, padx=5, pady=5)

    def _create_enhanced_method_and_control_section(self, parent):
        """Create enhanced method selection and experiment controls section"""
        # Remove sub-section labels but keep frame structure
        
        # Preset Selection (no sub-label)
        preset_frame = tk.Frame(parent)
        preset_frame.pack(fill="x", padx=4, pady=4)
        
        # Preset selection
        preset_selection_frame = tk.Frame(preset_frame)
        preset_selection_frame.pack(fill="x", padx=4, pady=4)
        
        ttk.Label(preset_selection_frame, text="Method Preset:").pack(side="left")
        
        # Preset combobox that will auto-fill parameters
        if hasattr(self, 'preset_combobox'):
            self.preset_combobox.destroy()
        self.preset_combobox = ttk.Combobox(preset_selection_frame, 
                                          textvariable=self.selected_preset_var,
                                          state="readonly", width=25)
        self.preset_combobox.bind("<<ComboboxSelected>>", self.on_preset_selected_auto_fill)
        self.preset_combobox.pack(side="left", padx=(5, 0), fill="x", expand=True)
        
        # Preset management controls (no sub-label)
        presets_controls = tk.Frame(preset_frame)
        presets_controls.pack(fill="x", padx=4, pady=2)
        
        ttk.Button(presets_controls, text="Save Preset", 
                  command=self.save_current_as_preset).pack(side="left", padx=2)
        ttk.Button(presets_controls, text="Delete Preset", 
                  command=self.delete_selected_preset).pack(side="left", padx=2)
        
        # Enhanced persistent timer section (always visible)
        timer_frame = tk.Frame(preset_frame)
        timer_frame.pack(fill="x", padx=4, pady=5)
        
        ttk.Label(timer_frame, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(timer_frame, textvariable=self.status_var, 
                                font=('Arial', 10, 'bold'))
        status_label.pack(side="left", padx=(5, 15))
        
        # Enhanced persistent timer display
        self.timer_label = tk.Label(timer_frame, text="Timer: 00:00:000", 
                                   font=('Arial', 12, 'bold'), 
                                   fg="blue", bg="white", relief="sunken", padx=5)
        self.timer_label.pack(side="right")
        
        # Enhanced control buttons - shrunk and high-contrast colors
        controls_frame = tk.Frame(parent)
        controls_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Configure grid for quadrant layout
        controls_frame.columnconfigure((0, 1), weight=1, uniform="col")
        controls_frame.rowconfigure((0, 1), weight=1, uniform="row")
        
        # Create enhanced buttons with high-contrast colors and smaller size
        self._create_enhanced_control_button(controls_frame, "Activate", "#4CAF50", self.activate_experiment, 0, 0)
        self._create_enhanced_control_button(controls_frame, "Start", "#2196F3", self.start_experiment, 0, 1)
        self._create_enhanced_control_button(controls_frame, "Test Field", "#FF9800", self.test_field, 1, 0)
        self._create_enhanced_control_button(controls_frame, "SCRAM", "#F44336", self.scram_experiment, 1, 1)
        
        # Refresh the method list for the new combobox
        self.refresh_method_list()
    
    def _create_enhanced_control_button(self, parent, text, color, command, row, col):
        """Create enhanced control button with high-contrast colors and smaller size"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 9, 'bold'),  # Smaller font
                          height=1,  # Reduced height
                          relief="raised", bd=2,
                          bg=color, fg="white",
                          activebackground=self._darken_color(color),
                          activeforeground="white")
        
        button.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
        
        # Add enhanced tooltip
        EnhancedToolTip.register_tooltip_for_widget(
            button, f"{text} experiment control", self, "Main"
        )
        
        return button
    
    def _darken_color(self, color):
        """Darken a hex color for active state"""
        color_map = {
            "#4CAF50": "#45a049",  # Green
            "#2196F3": "#1976D2",  # Blue
            "#FF9800": "#F57C00",  # Orange
            "#F44336": "#D32F2F"   # Red
        }
        return color_map.get(color, color)
    
    def _create_enhanced_polarization_method_section(self, parent):
        """Create enhanced polarization method section without stray text"""
        method_frame = ttk.LabelFrame(parent, text="Polarization Method", padding=10)
        method_frame.pack(fill="x", padx=5, pady=5)
        
        # Method selection (clean, no extra text)
        selection_frame = tk.Frame(method_frame)
        selection_frame.pack(fill="x", pady=2)
        
        tk.Label(selection_frame, text="Method:", width=15, anchor="w").pack(side="left")
        
        # Enhanced method dropdown
        self.polarization_method_var = tk.StringVar(value="SABRE-SHEATH")
        self.polarization_method_combobox = ttk.Combobox(
            selection_frame,
            textvariable=self.polarization_method_var,
            values=["SABRE-SHEATH", "SABRE-Relay", "Para-Hydrogen PHIP", "SABRE-Catalyst"],
            state="readonly",
            width=25
        )
        self.polarization_method_combobox.pack(side="left", padx=5, fill="x", expand=True)
        self.polarization_method_combobox.bind("<<ComboboxSelected>>", self._on_polarization_method_changed)
        
        # Load methods from directory
        self._load_polarization_methods_from_directory()
    
    def _register_tab_tooltips(self, parent, tab_name):
        """Register tooltips for all widgets in a tab"""
        # This would be called for each tab to register tooltips
        # Implementation depends on the specific widgets in each tab
        pass
    
    # ============================================================================
    # TAB DETACHING FUNCTIONALITY
    # ============================================================================
    
    def _maybe_detach_tab(self, event):
        """Handle left-click on tab for detaching"""
        # Get the clicked tab
        try:
            clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if clicked_tab != "":
                tab_index = int(clicked_tab)
                tab_text = self.notebook.tab(tab_index, "text")
                
                # Check if this is a detach action (e.g., double-click or ctrl+click)
                if event.state & 0x4:  # Ctrl+click
                    self._detach_tab(tab_text, tab_index)
        except:
            pass  # Ignore click errors
    
    def _detach_tab(self, tab_name, tab_index):
        """Detach a tab to a new window with live synchronization"""
        if tab_name in self.detached_windows:
            # If already detached, just bring to front
            if self.detached_windows[tab_name].window:
                self.detached_windows[tab_name].window.lift()
                return
        
        # Create tab content creator function
        content_creators = {
            "Main": self._create_main_tab,
            "Advanced Parameters": self._create_advanced_tab,
            "Testing": self._create_testing_tab,
            "SLIC Control": self._create_slic_tab,
            "% Polarization Calc": self._create_enhanced_polarization_tab
        }
        
        if tab_name in content_creators:
            detached_window = DetachedTabWindow(self, tab_name, content_creators[tab_name])
            detached_window.create_detached_window()
            self.detached_windows[tab_name] = detached_window
    
    # ============================================================================
    # ENHANCED TIMER FUNCTIONALITY
    # ============================================================================
    
    def start_persistent_timer(self, duration_s=None, mode="countdown"):
        """Start enhanced persistent timer"""
        self.timer_mode = mode
        self.timer_start_time = time.time()
        self.timer_duration = duration_s if duration_s else 0
        self.timer_running = True
        self._update_persistent_timer()
        
    def stop_persistent_timer(self):
        """Stop the persistent timer"""
        self.timer_running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.timer_mode = "idle"
        self._update_timer_display("Timer: 00:00:000")
    
    def _update_persistent_timer(self):
        """Update persistent timer display"""
        if not self.timer_running:
            return
            
        current_time = time.time()
        
        if self.timer_mode == "countdown" and self.timer_duration:
            remaining = max(0, self.timer_duration - (current_time - self.timer_start_time))
            if remaining > 0:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                milliseconds = int((remaining % 1) * 1000)
                time_str = f"Timer: {minutes:02d}:{seconds:02d}:{milliseconds:03d}"
                self._update_timer_display(time_str)
                self.after_id = self.after(10, self._update_persistent_timer)
            else:
                self._update_timer_display("Timer: 00:00:000")
                self.timer_running = False
                
        elif self.timer_mode == "elapsed":
            elapsed = current_time - self.timer_start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            milliseconds = int((elapsed % 1) * 1000)
            time_str = f"Timer: {minutes:02d}:{seconds:02d}:{milliseconds:03d}"
            self._update_timer_display(time_str)
            self.after_id = self.after(10, self._update_persistent_timer)
    
    def _update_timer_display(self, text):
        """Update timer display text"""
        if hasattr(self, 'timer_label'):
            self.timer_label.config(text=text)
    
    # ============================================================================
    # ENHANCED WAVEFORM FUNCTIONALITY
    # ============================================================================
    
    def refresh_waveform_plot(self):
        """Refresh the waveform plot with current data"""
        if hasattr(self, 'main_waveform_ax') and hasattr(self, 'main_waveform_canvas'):
            try:
                # Update waveform data (simulate or use real data)
                self._update_waveform_data()
                
                # Update the plot line
                self.waveform_line.set_data(self.waveform_time_data, self.waveform_voltage_data)
                
                # Adjust axis limits
                self.main_waveform_ax.set_xlim(0, max(self.waveform_time_data))
                self.main_waveform_ax.set_ylim(min(self.waveform_voltage_data) - 0.1, 
                                             max(self.waveform_voltage_data) + 0.1)
                
                # Refresh canvas
                self.main_waveform_canvas.draw()
                
            except Exception as e:
                print(f"Error refreshing waveform plot: {e}")
    
    def _update_waveform_data(self):
        """Update waveform data (simulate real waveform or use actual data)"""
        try:
            # Generate sample waveform (replace with real data source)
            t = np.linspace(0, 2, 200)
            frequency = 1.0 + 0.5 * np.sin(time.time())  # Varying frequency
            amplitude = 2.0 + np.sin(time.time() * 0.5)  # Varying amplitude
            self.waveform_voltage_data = amplitude * np.sin(2 * np.pi * frequency * t) * np.exp(-t * 0.2)
            self.waveform_time_data = t
            
        except Exception as e:
            print(f"Error updating waveform data: {e}")
    
    # ============================================================================
    # POLARIZATION DATA SET MANAGEMENT
    # ============================================================================
    
    def _save_polarization_dataset(self):
        """Save current polarization data to CSV file"""
        try:
            # Prompt for dataset name
            dataset_name = simpledialog.askstring("Save Data Set", "Enter dataset name:")
            if not dataset_name:
                return
                
            # Ensure .csv extension
            if not dataset_name.endswith('.csv'):
                dataset_name += '.csv'
                
            filepath = os.path.join(POLARIZATION_DATA_DIR, dataset_name)
            
            # Get current data from polarization panel (if available)
            data_to_save = self._extract_polarization_data()
            
            # Save to CSV
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Parameter', 'Value', 'Unit'])  # Header
                for row in data_to_save:
                    writer.writerow(row)
            
            messagebox.showinfo("Success", f"Dataset saved as {dataset_name}")
            self._refresh_dataset_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save dataset: {e}")
    
    def _load_polarization_dataset(self, event=None):
        """Load selected polarization dataset from CSV file"""
        try:
            selected_dataset = self.dataset_var.get()
            if selected_dataset == "Select dataset...":
                return
                
            filepath = os.path.join(POLARIZATION_DATA_DIR, selected_dataset)
            
            # Load from CSV
            data = []
            with open(filepath, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header
                for row in reader:
                    data.append(row)
            
            # Apply loaded data to polarization panel
            self._apply_polarization_data(data)
            
            messagebox.showinfo("Success", f"Dataset {selected_dataset} loaded")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load dataset: {e}")
    
    def _refresh_dataset_list(self):
        """Refresh the list of available datasets"""
        try:
            if os.path.exists(POLARIZATION_DATA_DIR):
                datasets = [f for f in os.listdir(POLARIZATION_DATA_DIR) if f.endswith('.csv')]
                datasets.sort()
                
                if hasattr(self, 'dataset_combobox'):
                    self.dataset_combobox['values'] = datasets
                    
        except Exception as e:
            print(f"Error refreshing dataset list: {e}")
    
    def _extract_polarization_data(self):
        """Extract current polarization data for saving"""
        # This would extract data from the polarization calculator panel
        # For now, return sample data
        return [
            ['Temperature', '295', 'K'],
            ['Magnetic Field', '150', 'mT'],
            ['Pressure', '1.2', 'atm'],
            ['Flow Rate', '25', 'sccm']
        ]
    
    def _apply_polarization_data(self, data):
        """Apply loaded polarization data to the interface"""
        # This would apply data to the polarization calculator panel
        # Implementation depends on the polarization panel structure
        pass
    
    # ============================================================================
    # EXISTING METHODS (preserved)
    # ============================================================================
    
    def _ensure_entries_exist(self):
        """Ensure basic entries exist to prevent KeyError"""
        basic_entries = [
            'bubbling_time_entry', 'magnetic_field_entry', 'temperature_entry',
            'flow_rate_entry', 'pressure_entry'
        ]
        
        for entry_name in basic_entries:
            if not hasattr(self, entry_name):
                setattr(self, entry_name, tk.Entry(self))
    
    def _create_general_params_preview(self, parent):
        """Create general parameters preview section"""
        # This creates a preview of main parameters
        params_frame = tk.Frame(parent)
        params_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Sample parameters (would be connected to real parameter widgets)
        params = [
            ("Bubbling Time", "45.0 s"),
            ("Magnetic Field", "150.0 mT"),
            ("Temperature", "295 K"),
            ("Flow Rate", "25 sccm"),
            ("Pressure", "1.2 atm")
        ]
        
        for i, (param, value) in enumerate(params):
            param_frame = tk.Frame(params_frame)
            param_frame.pack(fill="x", pady=1)
            
            tk.Label(param_frame, text=f"{param}:", width=15, anchor="w").pack(side="left")
            tk.Label(param_frame, text=value, width=10, anchor="w", 
                    fg="blue", font=("Arial", 9, "bold")).pack(side="left")
    
    # Placeholder methods for button commands
    def activate_experiment(self):
        """Activate experiment"""
        print("Activating experiment...")
        self.start_persistent_timer(30, "countdown")  # 30 second countdown
        self.status_var.set("Activating...")
    
    def start_experiment(self):
        """Start experiment"""
        print("Starting experiment...")
        self.start_persistent_timer(mode="elapsed")  # Elapsed timer
        self.status_var.set("Running...")
    
    def test_field(self):
        """Test magnetic field"""
        print("Testing field...")
        self.start_persistent_timer(10, "countdown")  # 10 second test
        self.status_var.set("Testing Field...")
    
    def scram_experiment(self):
        """Emergency stop"""
        print("SCRAM - Emergency stop!")
        self.stop_persistent_timer()
        self.status_var.set("SCRAMMED")
        if hasattr(self, 'scram'):
            self.scram()
    
    def on_preset_selected_auto_fill(self, event=None):
        """Auto-fill parameters when preset is selected"""
        try:
            selected_preset = self.selected_preset_var.get()
            if selected_preset != "Select a method preset...":
                print(f"Loading preset: {selected_preset}")
                # Implementation would load and apply preset data
        except Exception as e:
            print(f"Error loading preset: {e}")
    
    def save_current_as_preset(self):
        """Save current parameters as preset"""
        preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
        if preset_name:
            print(f"Saving preset: {preset_name}")
            # Implementation would save current parameters
    
    def delete_selected_preset(self):
        """Delete selected preset"""
        selected_preset = self.selected_preset_var.get()
        if selected_preset != "Select a method preset...":
            if messagebox.askyesno("Delete Preset", f"Delete preset '{selected_preset}'?"):
                print(f"Deleting preset: {selected_preset}")
                # Implementation would delete preset
    
    def refresh_method_list(self):
        """Refresh method list"""
        try:
            # Implementation would refresh the method/preset list
            print("Refreshing method list...")
        except Exception as e:
            print(f"Error refreshing method list: {e}")
    
    def _load_polarization_methods_from_directory(self):
        """Load polarization methods from directory"""
        try:
            methods_dir = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
            if os.path.exists(methods_dir):
                methods = [f.replace('.json', '') for f in os.listdir(methods_dir) if f.endswith('.json')]
                if hasattr(self, 'polarization_method_combobox'):
                    current_values = list(self.polarization_method_combobox['values'])
                    current_values.extend(methods)
                    self.polarization_method_combobox['values'] = list(set(current_values))
        except Exception as e:
            print(f"Error loading polarization methods: {e}")
    
    def _on_polarization_method_changed(self, event=None):
        """Handle polarization method change"""
        selected_method = self.polarization_method_var.get()
        print(f"Polarization method changed to: {selected_method}")
    
    def _update_tab_overflow(self):
        """Handle tab overflow"""
        # Implementation for tab overflow management
        pass


# ------------- run -------------
if __name__ == "__main__":
    print("Starting Enhanced SABRE GUI application...")
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
    
    print("Creating Enhanced SABREGUI instance...")
    try:
        app = SABREGUI(master=root)
        print("Enhanced SABREGUI created successfully, starting mainloop...")
        app.mainloop()
    except Exception as e:
        print(f"Error creating Enhanced SABREGUI: {e}")
        import traceback
        traceback.print_exc()
