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

# --- Core Controller Classes ---

class DAQController:
    """Handles all DAQ communication"""
    def send_digital(self, digital_outputs):
        try:
            import nidaqmx
            with nidaqmx.Task() as task:
                channels = ','.join(digital_outputs.keys())
                task.do_channels.add_do_chan(channels)
                signals = [1 if digital_outputs[k] else 0 for k in digital_outputs]
                task.write(signals)
        except Exception as e:
            print(f"Error sending digital signals: {e}")

    def send_analog(self, analog_outputs):
        try:
            import nidaqmx
            for channel, value in analog_outputs.items():
                with nidaqmx.Task() as task:
                    task.ao_channels.add_ao_voltage_chan(f"Dev1/{channel}", min_val=-10.0, max_val=10.0)
                    task.write(value)
        except Exception as e:
            print(f"Error sending analog signals: {e}")

class StateManager:
    """Manages system states and configurations"""
    def __init__(self, config_dir):
        self.config_dir = config_dir
        
    def load(self, state_name):
        try:
            config_file = os.path.join(self.config_dir, f"{state_name}.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                return config
            else:
                print(f"Config file not found for state: {state_name}")
                return None
        except Exception as e:
            print(f"Error loading config for state {state_name}: {e}")
            return None

class TimerController:
    """Handles all timer functionality"""
    def __init__(self, parent):
        self.parent = parent
        self.countdown_running = False
        self.countdown_end_time = None
        self.app_launch_time = time.time()
        
    def start_countdown(self, duration):
        """Start a countdown timer for the given duration in seconds."""
        if duration is None or duration <= 0:
            return
        self.countdown_end_time = time.time() + duration
        self.countdown_running = True
        self._update_countdown()

    def _update_countdown(self):
        """Update the countdown timer label."""
        if not hasattr(self.parent, "timer_label") or not self.parent.timer_label.winfo_exists():
            return
        if self.countdown_end_time is None:
            return
        remaining = int(self.countdown_end_time - time.time())
        if remaining < 0:
            remaining = 0
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.parent.timer_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        if remaining > 0:
            self.parent.after(1000, self._update_countdown)
        else:
            self.countdown_running = False

    def start_controls_countdown(self, duration):
        """Controls countdown removed - no operation"""
        pass

    def _update_controls_countdown(self):
        """Controls countdown removed - no operation"""
        pass

    def update_elapsed_timer(self):
        """Update elapsed time since app start"""
        if not hasattr(self.parent, "timer_label") or not self.parent.timer_label.winfo_exists():
            return
        elapsed = int(time.time() - self.app_launch_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.parent.timer_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.parent.after(1000, self.update_elapsed_timer)

class PlotController:
    """Handles all plotting operations"""
    def __init__(self, parent):
        self.parent = parent
        self.main_fig = None
        self.main_ax = None
        self.main_canvas = None
        self.field_fig = None
        self.field_ax = None
        self.field_canvas = None
        self.waveform_visible = True
        
        # Live plotting variables
        self.line = None
        self.plotting_active = False
        
    def initialize_plots(self):
        """Initialize plot components if they exist"""
        try:
            if self.main_ax is not None:
                self.main_ax.clear()
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Live Waveform")
                self.main_ax.grid(True, alpha=0.3)
                if self.main_canvas is not None:
                    self.main_canvas.draw()
        except Exception as e:
            print(f"Error initializing plots: {e}")
            
    def start_live_plotting(self):
        """Start live waveform plotting"""
        try:
            self.plotting_active = True
            self.parent.voltage_data = []
            self.parent.time_data = []
            self.parent.start_time = time.time()
            self.line = None  # Reset line
            
            if self.main_ax is not None:
                self.main_ax.clear()
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Live Waveform - Recording")
                self.main_ax.grid(True, alpha=0.3)
                if self.main_canvas is not None:
                    self.main_canvas.draw()
                    
            print("Live plotting started")
        except Exception as e:
            print(f"Error starting live plotting: {e}")
            
    def update_live_plot(self, voltage, timestamp=None):
        """Update the live plot with new voltage data"""
        if not self.plotting_active:
            return
            
        try:
            if timestamp is None:
                timestamp = time.time()
                
            # Calculate relative time
            if self.parent.start_time is None:
                self.parent.start_time = timestamp
            relative_time = timestamp - self.parent.start_time
            
            # Add data to buffers
            self.parent.voltage_data.append(voltage)
            self.parent.time_data.append(relative_time)
            
            # Limit buffer size for performance
            max_points = 1000
            if len(self.parent.voltage_data) > max_points:
                self.parent.voltage_data = self.parent.voltage_data[-max_points:]
                self.parent.time_data = self.parent.time_data[-max_points:]
            
            # Update plot
            if self.main_ax is not None and len(self.parent.time_data) > 0:
                if self.line is None:
                    plot_result = self.main_ax.plot(self.parent.time_data, self.parent.voltage_data, 'b-', linewidth=1)
                    if plot_result:
                        self.line = plot_result[0]
                else:
                    self.line.set_data(self.parent.time_data, self.parent.voltage_data)
                
                # Update axis limits
                if len(self.parent.time_data) > 1:
                    self.main_ax.set_xlim(min(self.parent.time_data), max(self.parent.time_data))
                    
                if len(self.parent.voltage_data) > 0:
                    v_min, v_max = min(self.parent.voltage_data), max(self.parent.voltage_data)
                    padding = 0.1 * max(0.1, v_max - v_min)
                    self.main_ax.set_ylim(v_min - padding, v_max + padding)
                
                if self.main_canvas is not None:
                    self.main_canvas.draw_idle()
                    
        except Exception as e:
            print(f"Error updating live plot: {e}")
            
    def stop_live_plotting(self):
        """Stop live waveform plotting"""
        try:
            self.plotting_active = False
            if self.main_ax is not None:
                self.main_ax.set_title("Live Waveform")
                if self.main_canvas is not None:
                    self.main_canvas.draw()
            print("Live plotting stopped")
        except Exception as e:
            print(f"Error stopping live plotting: {e}")

    def plot_waveform_buffer(self, buf, sr):
        """Plot waveform buffer for preview"""
        try:
            if self.main_ax is not None and self.main_canvas is not None:
                self.main_ax.clear()
                time_axis = np.arange(len(buf)) / sr
                self.main_ax.plot(time_axis, buf, 'b-', linewidth=1)
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Polarization Method Waveform")
                self.main_ax.grid(True, alpha=0.3)
                
                # Force multiple canvas updates to ensure visibility
                self.main_canvas.draw()
                self.main_canvas.draw_idle()
                self.main_canvas.flush_events()
                
                print(f"Plotted waveform: {len(buf)} samples at {sr} Hz")
        except Exception as e:
            print(f"Error plotting waveform buffer: {e}")
            
    def reset_waveform_plot(self):
        """Reset the waveform plot"""
        try:
            if self.main_ax is not None:
                self.main_ax.clear()
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Waveform Display")
                self.main_ax.grid(True, alpha=0.3)
                if self.main_canvas is not None:
                    self.main_canvas.draw()
        except Exception as e:
            print(f"Error resetting waveform plot: {e}")
            
    def toggle_waveform_plot(self):
        """Toggle waveform plot visibility"""
        try:
            self.waveform_visible = not self.waveform_visible
            if self.main_canvas is not None:
                if self.waveform_visible:
                    self.main_canvas.get_tk_widget().pack(fill="both", expand=True)
                else:
                    self.main_canvas.get_tk_widget().pack_forget()
            print(f"Waveform plot visibility: {self.waveform_visible}")
        except Exception as e:
            print(f"Error toggling waveform plot: {e}")

class UIManager:
    """Handles UI creation and styling"""
    def __init__(self, parent):
        self.parent = parent
        
    def create_control_button(self, parent, text, color, command):
        """Create a control button with consistent styling"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 10, 'bold'),
                          width=12, height=2,
                          relief="raised", bd=2)
        
        # Set color scheme based on button type
        color_schemes = {
            "green": {"bg": "#4CAF50", "fg": "white", "activebackground": "#45a049"},
            "blue": {"bg": "#2196F3", "fg": "white", "activebackground": "#1976D2"},
            "orange": {"bg": "#FF9800", "fg": "white", "activebackground": "#F57C00"},
            "red": {"bg": "#F44336", "fg": "white", "activebackground": "#D32F2F"}
        }
        
        if color in color_schemes:
            button.config(**color_schemes[color])
        
        button.pack(side="left", padx=5, pady=2)
        return button
        
    def show_error_popup(self, missing_params):
        """Show error popup for missing parameters"""
        if missing_params:
            error_msg = "Missing required parameters:\n" + "\n".join(f"• {param}" for param in missing_params)
            messagebox.showwarning("Missing Parameters", error_msg)
        
    def create_quadrant_button(self, parent, text, color, command, row, col):
        """Create a quadrant experiment control button with consistent styling"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 8, 'bold'),
                          relief="raised", bd=3,
                          width=8, height=1)
        
        # Hard-coded button palette
        color_schemes = {
            "Activate": {"bg": "#2E7D32", "fg": "white", "activebackground": "#2E7D32"},
            "Start": {"bg": "#1565C0", "fg": "white", "activebackground": "#1565C0"},
            "Test Field": {"bg": "#EF6C00", "fg": "white", "activebackground": "#EF6C00"},
            "SCRAM": {"bg": "#B71C1C", "fg": "white", "activebackground": "#B71C1C"}
        }
        
        if text in color_schemes:
            button.config(**color_schemes[text])
            
        button.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
        return button

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
        except Exception as e:
            print(f"Error handling method selection: {e}")
            
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
    
    def create_main_tab(self, parent, detached=False):
        """Create the main control tab with key controls and previews"""
        # Configure grid
        parent.columnconfigure((0, 1), weight=1, uniform="col")
        parent.rowconfigure((0, 1), weight=1, uniform="row")
        
        # General Configuration section (top-left)
        gen_cfg = ttk.LabelFrame(parent, text="General Configuration")
        gen_cfg.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.create_general_params_preview(gen_cfg)
        
        # Waveform Live View (bottom-left)
        waveform_frame = ttk.LabelFrame(parent, text="Waveform Live View")
        waveform_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.create_waveform_live_view_main(waveform_frame)

        # Method Selection and Experiment Controls section (top-right)
        method_control_frame = ttk.LabelFrame(parent, text="Experimental Controls")
        method_control_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self.create_method_and_control_section(method_control_frame)
        
        # Magnetic Field Live View (bottom-right)
        magnetic_frame = ttk.LabelFrame(parent, text="Magnetic Field Live View")
        magnetic_frame.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
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
        
        ao_frame = ttk.Frame(testing_notebook)
        testing_notebook.add(ao_frame, text="Analog Output")
        ao_panel = AnalogOutputPanel(ao_frame, embedded=True)
        ao_panel.pack(fill="both", expand=True)
    
    def create_slic_tab(self, parent):
        """Create the SLIC control tab"""
        try:
            slic_panel = SLICSequenceControl(parent, embedded=True)
            slic_panel.pack(fill="both", expand=True)
        except Exception as e:
            error_label = tk.Label(parent, text=f"SLIC Control Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
    
    def create_polarization_tab(self, parent):
        """Create the polarization calculator tab"""
        try:
            pol_panel = PolarizationApp(parent, embedded=True)
            pol_panel.pack(fill="both", expand=True)
        except Exception as e:
            error_label = tk.Label(parent, text=f"Polarization Calculator Error: {e}", 
                                 fg="red", font=("Arial", 12))
            error_label.pack(expand=True)
    
    def create_waveform_live_view_main(self, parent):
        """Create the waveform live view for the Main tab"""
        # Create a frame for the waveform section
        waveform_container = tk.Frame(parent)
        waveform_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create header frame for title and toggle button
        header_frame = tk.Frame(waveform_container)
        header_frame.pack(fill="x", pady=(0, 5))

        # Add title and refresh button side by side
        tk.Label(header_frame, text="Live Waveform", font=("Arial", 10, "bold")).pack(side="left")
        refresh_btn = ttk.Button(header_frame, text="Refresh", command=self.parent._refresh_live_waveform)
        refresh_btn.pack(side="right", padx=2)

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
            
            # Plot initial waveform if method is already selected
            self.parent.after(100, self.parent._refresh_live_waveform)
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(plot_container, 
                                    text="Waveform Display\n(Matplotlib required)", 
                                    fg="lime", bg="black", font=("Arial", 9))
            fallback_label.pack(expand=True)

    def create_magnetic_field_live_view_main(self, parent):
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
        self.parent.field_value_label = tk.Label(header_frame, text="0.0 mT", 
                                         font=("Arial", 9, "bold"), fg="blue")
        self.parent.field_value_label.pack(side="right")

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
                
        except ImportError:
            # Fallback if matplotlib not available
            fallback_label = tk.Label(display_container, 
                                    text="Magnetic Field Monitor\n(Matplotlib required)", 
                                    fg="yellow", bg="darkblue", font=("Arial", 9))
            fallback_label.pack(expand=True)

    def create_method_and_control_section(self, parent):
        """Create merged method selection and experiment controls section"""
        # Preset combobox at very top of Experimental Controls frame
        preset_combobox = ttk.Combobox(parent, 
                                      textvariable=self.parent.selected_preset_var,
                                          state="readonly", width=25)
        preset_combobox.bind("<<ComboboxSelected>>", self.parent.on_preset_selected_auto_fill)
        preset_combobox.pack(fill="x", padx=4, pady=4)
        self.parent.preset_combobox = preset_combobox
        
        # Three small buttons immediately under the combobox
        presets_controls = tk.Frame(parent)
        presets_controls.pack(fill="x", padx=4, pady=2)
        
        ttk.Button(presets_controls, text="Save Current as Preset", 
                  command=self.parent.save_current_as_preset).pack(side="left", padx=2)
        ttk.Button(presets_controls, text="Delete Preset", 
                  command=self.parent.delete_selected_preset).pack(side="left", padx=2)
        ttk.Button(presets_controls, text="Refresh Presets", 
                  command=self.parent.refresh_preset_list).pack(side="left", padx=2)
        
        # Add state and timer section
        controls_status_frame = tk.Frame(parent)
        controls_status_frame.pack(fill="x", padx=4, pady=4)
        ttk.Label(controls_status_frame, textvariable=self.parent.controls_state_var, 
                  font=("Arial", 10, "bold"), foreground="blue").pack(side="left", padx=(0, 10))
        
        # Add countdown timer (same implementation as SLIC_Control.py)
        self.parent.countdown_label = tk.Label(controls_status_frame, text="00:00.000", 
                                             font=("Arial", 10, "bold"), foreground="#003366")
        self.parent.countdown_label.pack(side="left")
        
        # Create buttons frame for 2x2 grid layout
        buttons_frame = tk.Frame(parent)
        buttons_frame.pack(fill="x", padx=4, pady=4)
        
        # Configure grid for quadrant layout in buttons frame
        buttons_frame.columnconfigure((0, 1), weight=1, uniform="col")
        buttons_frame.rowconfigure((0, 1), weight=1, uniform="row")

        # Create buttons in quadrant layout using pack-compatible approach
        activate_btn = tk.Button(buttons_frame, text="Activate", 
                                command=self.parent.activate_experiment,
                                font=('Arial', 8, 'bold'), relief="raised", bd=3,
                                width=8, height=1, bg="#2E7D32", fg="white", 
                                activebackground="#2E7D32")
        activate_btn.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        
        start_btn = tk.Button(buttons_frame, text="Start", 
                             command=self.parent.start_experiment,
                             font=('Arial', 8, 'bold'), relief="raised", bd=3,
                             width=8, height=1, bg="#1565C0", fg="white", 
                             activebackground="#1565C0")
        start_btn.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        
        test_btn = tk.Button(buttons_frame, text="Test Field", 
                            command=self.parent.test_field,
                            font=('Arial', 8, 'bold'), relief="raised", bd=3,
                            width=8, height=1, bg="#EF6C00", fg="white", 
                            activebackground="#EF6C00")
        test_btn.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)
        
        scram_btn = tk.Button(buttons_frame, text="SCRAM", 
                             command=self.parent.scram_experiment,
                             font=('Arial', 8, 'bold'), relief="raised", bd=3,
                             width=8, height=1, bg="#B71C1C", fg="white", 
                             activebackground="#B71C1C")
        scram_btn.grid(row=1, column=1, sticky="nsew", padx=3, pady=3)
        
        # Refresh the method list for the new combobox
        self.parent.refresh_method_list()
        
    def create_general_params_preview(self, parent):
        """Create a preview of general parameters in the main tab"""
        
        # Add a few key parameters as a preview
        params = [
            ("Bubbling Time", "", ["s", "min", "h"]),
            ("Magnetic Field", "", ["mT", "T", "G"]),
            ("Temperature", "", ["K", "°C", "°F"]),
            ("Flow Rate", "", ["sccm", "slm", "ccm"]),
            ("Pressure", "", ["atm", "bar", "psi", "Pa"])
        ]
        
        for i, (label, default_val, unit_options) in enumerate(params):
            row = tk.Frame(parent)
            row.pack(fill="x", padx=5, pady=2)
            
            tk.Label(row, text=f"{label}:", width=15, anchor="w").pack(side="left")
            entry = tk.Entry(row, width=10)
            entry.insert(0, default_val)
            entry.pack(side="left", padx=2)
            
            # Store the entry in self.parent.entries for access by other methods
            self.parent.entries[label] = entry
            
            # Create StringVar for unit and store it
            unit_var = tk.StringVar(value=unit_options[0])
            self.parent.units[label] = unit_var
            
            # Create editable unit dropdown
            unit_combo = ttk.Combobox(row, textvariable=unit_var, 
                                     values=unit_options, width=8, state="readonly")
            unit_combo.pack(side="left", padx=2)
        
        # Add link to advanced parameters
        link_frame = tk.Frame(parent)
        link_frame.pack(fill="x", pady=10)
        ttk.Button(link_frame, text="Go to Advanced Parameters", 
                  command=lambda: self.parent.notebook.select(1)).pack()
                  
    def create_polarization_method_section(self, parent):
        """Create the polarization method configuration section with dropdown selector"""
        # Polarization Method Selection Section
        polarization_frame = ttk.LabelFrame(parent, text="Polarization Method", padding="10")
        polarization_frame.pack(fill="x", padx=10, pady=5)
        
        # Method Selection Dropdown
        method_frame = ttk.Frame(polarization_frame)
        method_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(method_frame, text="Method:").pack(side="left")
        
        # Polarization method dropdown reading from directory
        self.parent.polarization_method_combobox = ttk.Combobox(method_frame, 
                                                        textvariable=self.parent.polarization_method_var,
                                                        state="readonly", width=25)
        
        # Load available polarization methods from directory
        polarization_methods = self.parent.method_manager.load_polarization_methods_from_directory()
        
        self.parent.polarization_method_combobox['values'] = polarization_methods
        self.parent.polarization_method_combobox.bind("<<ComboboxSelected>>", self.on_polarization_method_changed)
        self.parent.polarization_method_combobox.pack(side="left", padx=(5, 0), fill="x", expand=True)
        
        # Add refresh button next to the combobox
        refresh_button = ttk.Button(method_frame, text="Refresh", 
                                   command=self.parent.refresh_method_list)
        refresh_button.pack(side="left", padx=(5, 0))
        
        # Method description/info
        info_frame = ttk.Frame(polarization_frame)
        info_frame.pack(fill="x", pady=(5, 0))
        
        self.parent.method_info_label = tk.Label(info_frame, 
                                         text="SABRE-SHEATH: Signal Amplification by Reversible Exchange in SHield Enables Alignment Transfer to Heteronuclei",
                                         wraplength=400, justify="left", font=("Arial", 9))
        self.parent.method_info_label.pack(side="left", fill="x", expand=True)
        
        # Toggles Section (Audio and Tooltips as requested)
        toggles_frame = ttk.LabelFrame(parent, text="Interface Settings", padding="10")
        toggles_frame.pack(fill="x", padx=10, pady=5)
        
        # Audio toggle
        audio_frame = tk.Frame(toggles_frame)
        audio_frame.pack(fill="x", pady=2)
        
        self.parent.audio_enabled_checkbox = ttk.Checkbutton(audio_frame, text="Enable Audio Feedback",
                                                     variable=self.parent.audio_enabled,
                                                     command=self.on_audio_toggle)
        self.parent.audio_enabled_checkbox.pack(side="left")
        
        # Tooltip toggle
        tooltip_frame = tk.Frame(toggles_frame)
        tooltip_frame.pack(fill="x", pady=2)
        
        self.parent.tooltips_enabled_checkbox = ttk.Checkbutton(tooltip_frame, text="Enable Tooltips",
                                                        variable=self.parent.tooltips_enabled,
                                                        command=self.on_tooltip_toggle)
        self.parent.tooltips_enabled_checkbox.pack(side="left")
        
    def on_polarization_method_changed(self, event=None):
        """Handle polarization method selection changes - Ultra Simple Solution"""
        try:
            selected_method = self.parent.polarization_method_var.get()
            
            if selected_method and selected_method != "Select method...":
                # Store the full path to the selected method file
                methods_dir = r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
                self.parent.polarization_method_file = os.path.join(methods_dir, selected_method)
                
                # Try to load the method file to get description
                try:
                    with open(self.parent.polarization_method_file, 'r') as f:
                        method_data = json.load(f)
                        description = method_data.get('description', f"Loaded polarization method: {selected_method}")
                        self.parent.method_info_label.config(text=description)
        except Exception as e:
                    self.parent.method_info_label.config(text=f"Method file: {selected_method}")
                    print(f"Could not load method description: {e}")
                
                # ULTRA SIMPLE SOLUTION: Just plot directly
                self._plot_method_directly(self.parent.polarization_method_file, selected_method)
                
            else:
                # Default description when no method is selected
                self.parent.method_info_label.config(text="SABRE-SHEATH: Signal Amplification by Reversible Exchange in SHield Enables Alignment Transfer to Heteronuclei", fg="black")
                self.parent.polarization_method_file = None
                
            print(f"Polarization method changed to: {selected_method}")
            
        except Exception as e:
            print(f"Error handling polarization method change: {e}")
    
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
            
            # Clear and plot
            main_ax.clear()
            time_axis = [i / sr for i in range(len(buf))]
            main_ax.plot(time_axis, buf, 'b-', linewidth=1)
            main_ax.set_xlabel('Time (s)')
            main_ax.set_ylabel('Voltage (V)')
            main_ax.set_title(f'Polarization Method: {method_name}')
            main_ax.grid(True, alpha=0.3)
            
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

class ExperimentController:
    """Handles experiment sequences and state management"""
    def __init__(self, sabre_gui):
        self.gui = sabre_gui
        self.running = False
        self.stop_polarization = False
        # Add DAQ task management
        self.test_task = None
        self.dio_task = None
        self.task_lock = threading.Lock()

    def activate_experiment(self):
        """Activate the experiment sequence with proper DAQ interactions"""
        missing_params = []
        required_fields = [
            ("Activation Time", getattr(self.gui, 'activation_time_entry', None)),
            ("Temperature", self.gui.entries.get("Temperature")),
            ("Flow Rate", self.gui.entries.get("Flow Rate")),
            ("Pressure", self.gui.entries.get("Pressure")),
            ("Injection Time", getattr(self.gui, 'injection_time_entry', None)),
            ("Valve Control Timing", getattr(self.gui, 'valve_time_entry', None)),
            ("Degassing Time", getattr(self.gui, 'degassing_time_entry', None)),
            ("Bubbling Time", self.gui.entries.get("Bubbling Time")),
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
            if hasattr(self.gui, 'state_label'):
                self.gui.state_label.config(text="State: Activating")
            
            # Update virtual panel if it exists
            if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                self.gui.virtual_panel.load_config_visual("Initial_State")
            
            valve_duration = self.gui.get_value('valve_time_entry')
            injection_duration = self.gui.get_value('injection_time_entry')
            degassing_duration = self.gui.get_value('degassing_time_entry')
            activation_duration = self.gui.get_value('activation_time_entry')

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
                    
                    # Wait for duration
                    if duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and hasattr(self, 'running') and self.running:
                            time.sleep(0.1)

        except Exception as error:
            print(f"Error in activation sequence: {error}")
        finally:
            self.running = False
            self.load_config("Initial_State")  # Always return to initial state
            if hasattr(self.gui, 'state_label'):
                self.gui.state_label.config(text="State: Idle")
            # Update virtual panel if it exists
            if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                self.gui.virtual_panel.load_config_visual("Initial_State")

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
                
            if hasattr(self.gui, 'state_label'):
                self.gui.state_label.config(text="State: Bubbling the Sample")
            
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
                if hasattr(self.gui, 'virtual_panel') and self.gui.virtual_panel and self.gui.virtual_panel.winfo_exists():
                    self.gui.virtual_panel.load_config_visual("Initial_State")

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
                if hasattr(self.gui, 'state_label'):
                    self.gui.state_label.config(text="State: Applying Polarization Method")
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
            if hasattr(self.gui, 'state_label'):
                self.gui.state_label.config(text=f"State: {human_readable_state}")

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

# --- TimerWidget Helper Class ---
class TimerWidget(tk.Frame):
    def __init__(self, master, font=("Courier", 12, "bold"), **kwargs):
        super().__init__(master, **kwargs)
        self.label = tk.Label(self, text="00:00.000", font=font)
        self.label.pack()
        self._running = False
        self._end_time = None
        self._after_id = None
        
    def start(self, duration):
        self._end_time = time.time() + duration
        self._running = True
        self._update()
        
    def _update(self):
        if not self._running or self._end_time is None:
            return
        remaining = float(self._end_time - time.time())
        remaining = max(0, remaining)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        milliseconds = int((remaining % 1) * 1000)
        self.label.config(text=f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}")
        if remaining > 0.0:
            self._after_id = self.after(10, self._update)
            else:
            self._running = False
            self.label.config(text="00:00.000")
            
    def stop(self):
        self._running = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

# --- Main SABRE GUI Class ---
class SABREGUI(tk.Frame):
    """Main SABRE GUI application - now modular and organized"""
    
    def __init__(self, master=None):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        
        # Initialize core controllers and managers
        self.daq_controller = DAQController()
        self.state_manager = StateManager(CONFIG_DIR)
        self.timer_controller = TimerController(self)
        self.plot_controller = PlotController(self)
        self.ui_manager = UIManager(self)
        self.method_manager = MethodManager(self)
        self.tab_manager = TabManager(self)
        
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
        
        # Initialize timer
        self.timer_controller.update_elapsed_timer()
        
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
        self.tooltips_enabled = tk.BooleanVar(value=True)
        
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
        self.status_timer_bar = tk.Frame(self, bg="#e0e0e0", relief="groove", bd=2)
        self.status_timer_bar.pack(fill="x", side="top", padx=0, pady=(0, 2))
        self.status_var = tk.StringVar(value="System Ready")
        self.status_label = tk.Label(self.status_timer_bar, textvariable=self.status_var, 
                                   font=("Arial", 11, "bold"), fg="darkgreen", bg="#e0e0e0")
        self.status_label.pack(side="left", padx=(10, 20), pady=2)
        
        # Create basic widgets
        self.create_initial_widgets()
        
        # Build dashboard tabs
        self.tab_manager.build_dashboard_tabs()
        
        # Timer functionality removed
        
        # Bind events
        self.bind("<Configure>", lambda e: self._update_tab_overflow())
        self.notebook.bind("<Button-1>", self._maybe_clone_tab, add="+")
        
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
        """Handle right-click on tab for cloning"""
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
        """Create a detached window for Main or Advanced Parameters tabs."""
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
            
        except Exception as e:
            print(f"Error creating detached tab '{tab_text}': {e}")
            messagebox.showerror("Error", f"Could not detach tab '{tab_text}': {e}")
    
    def _on_detached_close(self, tab_text, window):
        """Handle closing of detached window"""
        detached_attr = f"_detached_{tab_text.replace(' ', '_').lower()}"
        if hasattr(self, detached_attr):
            delattr(self, detached_attr)
        window.destroy()

    # Panel opening methods
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

    def get_value(self, entry_attr, conversion_type="time"):
        """Get parameter value with unit conversion"""
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
        
        # Stop countdown timer
        self.stop_countdown()
        
        # Stop polarization and running flag
        self.stop_polarization = True
        if hasattr(self, 'running'):
            self.running = False  # Added flag to stop sequences
        
        # Use ScramController to handle emergency stop
        self.scram()
    
        # Reset state label
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
        if hasattr(self, 'controls_state_var'):
            self.controls_state_var.set(f"State: {state_name}")
            
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

    def toggle_waveform_plot(self):
        """Toggle waveform plot visibility"""
        self.plot_controller.toggle_waveform_plot()

    def _plot_waveform_buffer(self, buf, sr):
        """Plot waveform buffer for preview"""
        self.plot_controller.plot_waveform_buffer(buf, sr)

    def _compute_polarization_duration(self):
        """Compute polarization duration"""
        return self.method_manager.compute_polarization_duration()

    def reset_waveform_plot(self):
        """Reset waveform plot"""
        self.plot_controller.reset_waveform_plot()


        
    # Timer functionality (SLIC_Control.py implementation)
    def start_countdown(self, duration_s):
        """Start countdown timer for given duration in seconds"""
        if not hasattr(self, 'countdown_label'):
            print("Timer label not initialized yet")
            return
            
        self.countdown_end_time = time.time() + duration_s
        self.countdown_running = True
        self.update_countdown()
        print(f"Countdown started for {duration_s} seconds")

    def update_countdown(self):
        """Update countdown display every millisecond"""
        if not self.countdown_running:
            return
            
        remaining = max(0.0, self.countdown_end_time - time.time()) if self.countdown_end_time else 0.0
        
        if remaining > 0:
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        milliseconds = int((remaining % 1) * 1000)
            
            if hasattr(self, 'countdown_label') and self.countdown_label is not None:
                self.countdown_label.config(
                    text=f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                )
            
            self.after_id = self.after(1, self.update_countdown)
        else:
            if hasattr(self, 'countdown_label') and self.countdown_label is not None:
                self.countdown_label.config(text="00:00.000")
            self.countdown_running = False
            print("Countdown completed")

    def stop_countdown(self):
        """Stop the countdown timer"""
        self.countdown_running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        if hasattr(self, 'countdown_label') and self.countdown_label is not None:
            self.countdown_label.config(text="00:00.000")
        print("Countdown stopped")
        
    # Legacy method compatibility - redirect to new timer
    def start_timer(self, total_seconds):
        """Legacy method - redirect to countdown"""
        self.start_countdown(total_seconds)
        
    def stop_timer(self):
        """Legacy method - redirect to countdown"""
        self.stop_countdown()
        
    def reset_timer(self):
        """Legacy method - redirect to countdown"""
        self.stop_countdown()
        
    def start_countdown_timer(self, duration_seconds):
        """Legacy method - redirect to countdown"""
        self.start_countdown(duration_seconds)
        
    def stop_countdown_timer(self):
        """Legacy method - redirect to countdown"""
        self.stop_countdown()
        
    def _refresh_live_waveform(self):
        """Refresh the live waveform plot"""
        try:
            if not hasattr(self, 'polarization_method_file') or not self.polarization_method_file:
                return
                
            with open(self.polarization_method_file, 'r') as f:
                cfg = json.load(f)
                
            # Build the waveform buffer
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                initial_voltage = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"], dc_offset=initial_voltage)
            
            # Clear and re-plot using plot controller
            if hasattr(self, 'plot_controller') and self.plot_controller:
                self.plot_controller.plot_waveform_buffer(buf, sr)
                print(f"Waveform plot updated: {len(buf)} samples, {buf.max():.3f}V max, {buf.min():.3f}V min")
            
            # Force canvas update if we have direct access to it
            if hasattr(self, 'main_canvas') and self.main_canvas:
                self.main_canvas.draw_idle()
                self.main_canvas.flush_events()
                
            # Force GUI update to ensure the plot is refreshed
            self.update_idletasks()
            self.after_idle(lambda: self.update())
                    
        except Exception as e:
            print(f"Error refreshing live waveform: {e}")
            
    def _force_waveform_update(self):
        """Force an immediate waveform plot update with enhanced refresh"""
        try:
            # Call the standard refresh method
            self._refresh_live_waveform()
            
            # Additional forced updates to ensure visibility across tabs
            if hasattr(self, 'plot_controller') and self.plot_controller:
                if hasattr(self.plot_controller, 'main_canvas') and self.plot_controller.main_canvas:
                    # Force multiple canvas refresh operations
                    self.plot_controller.main_canvas.draw()
                    self.plot_controller.main_canvas.draw_idle()
                    self.after(10, lambda: self.plot_controller.main_canvas.draw())
                    
            # Force GUI refresh
            self.update_idletasks()
            self.update()
            
            print("Force waveform update completed")
            
        except Exception as e:
            print(f"Error in force waveform update: {e}")

    def sync_widget_values(self, src_frame, clone_frame):
        """Recursively sync widget values between original and clone frames"""
        try:
            src_children = src_frame.winfo_children()
            clone_children = clone_frame.winfo_children()
            
            for src_widget, clone_widget in zip(src_children, clone_children):
                # Sync Entry widgets
                if isinstance(src_widget, tk.Entry) and isinstance(clone_widget, tk.Entry):
                    def sync_entry(var_name, index, mode, src=src_widget, clone=clone_widget):
                        try:
                            if src.get() != clone.get():
                                clone.delete(0, tk.END)
                                clone.insert(0, src.get())
                        except:
                            pass
                    
                    src_var = tk.StringVar()
                    src_var.trace_add("write", sync_entry)
                    src_widget.config(textvariable=src_var)
                    
                # Sync Combobox widgets
                elif isinstance(src_widget, ttk.Combobox) and isinstance(clone_widget, ttk.Combobox):
                    def sync_combo(var_name, index, mode, src=src_widget, clone=clone_widget):
                        try:
                            if src.get() != clone.get():
                                clone.set(src.get())
                        except:
                            pass
                    
                    if hasattr(src_widget, 'textvariable') and src_widget['textvariable']:
                        src_widget['textvariable'].trace_add("write", sync_combo)
                
                # Recursively process child widgets
                if src_widget.winfo_children() and clone_widget.winfo_children():
                    self.sync_widget_values(src_widget, clone_widget)
                    
        except Exception as e:
            print(f"Error syncing widget values: {e}")
            
# ------------- Main Application Entry Point -------------
if __name__ == "__main__":
    print("Starting SABRE GUI application (Refactored)...")
    root = tk.Tk()
    root.title("SABRE Control System - Modular Architecture")
    root.geometry("1200x800")
    
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