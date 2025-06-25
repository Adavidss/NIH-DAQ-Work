import json
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winsound

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import nidaqmx
from nidaqmx.constants import AcquisitionType
from nidaqmx.stream_writers import AnalogSingleChannelWriter
import numpy as np
from PIL import Image, ImageTk

# Set up path for nested programs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Nested_Programs"))

# Sampling Adjustment Code [Begin]
def build_composite_waveform(ramp_sequences, dc_offset=0.0, samples_per_cycle=200):
    """Return (buf, sample_rate)
    Handles both traditional ramp sequences and SLIC sequence formats.
    """
    import numpy as np

    # Check if this is a SLIC sequence
    if isinstance(ramp_sequences, dict) and ramp_sequences.get("type") == "SLIC_sequence":
        params = ramp_sequences["params"]
        data = ramp_sequences["data"]
        sample_rate = params["SamplingRate"]
        return np.array(data, dtype=np.float64), sample_rate

    # Original ramp sequence handling
    sine_freqs = [seq.get("frequency", 1.0) 
                 for seq in ramp_sequences 
                 if seq["waveform"] == "sine"]
    max_f = max(sine_freqs) if sine_freqs else 1.0
    sample_rate = int(max_f * samples_per_cycle)

    big_buf = []
    for seq in ramp_sequences:
        dur = seq.get("duration", 0.0)

        if seq["waveform"] == "sine":
            f   = seq["frequency"]
            amp = seq["amplitude"]
            n   = int(sample_rate * dur)
            t   = np.linspace(0, dur, n, endpoint=False)
            slice_buf = amp * np.sin(2*np.pi*f*t) + dc_offset
        elif seq["waveform"] == "hold":  # Add hold waveform support
            v = seq["voltage"]
            n = max(2, int(sample_rate * dur))
            slice_buf = np.full(n, v, dtype=np.float64)
        else:  # linear ramp
            v0  = seq.get("start_voltage", dc_offset)
            v1  = seq.get("end_voltage",   dc_offset)
            n   = max(2, int(sample_rate * dur))
            slice_buf = np.linspace(v0, v1, n, dtype=np.float64)

        big_buf.append(slice_buf)

    return np.concatenate(big_buf), sample_rate
# Sampling Adjustment Code [End]

# CODE IMPORTS (Nested_Programs)===============================
from Constants_Paths import (
    BASE_DIR,
    CONFIG_DIR,
    DAQ_DEVICE,
    DIO_CHANNELS,
    INITIAL_STATE,
    STATE_MAPPING
)
from Utility_Functions import (
    convert_value,
    get_value,
    save_parameters_to_file,
    load_parameters_from_file,
    ensure_default_state_files
)
from Nested_Programs.TestPanels_AI_AO import AnalogInputPanel, AnalogOutputPanel
from Virtual_Testing_Panel import VirtualTestingPanel
from FullFlowSystem import FullFlowSystem
from Nested_Programs.SLIC_Control import SLICSequenceControl  # Add this import

# Initialize state files
try:
    ensure_default_state_files()
except Exception as e:
    print(f"Error creating config directory and files: {e}")
    sys.exit(1)

# ==== MAIN WINDOW : SABREGUI ===============================
class SABREGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SABRE Control Panel")
        self.geometry("540x730")  # 20% wider than original 450x550
        
        # Add icon to the window
        try:
            icon_path = os.path.join(BASE_DIR, "SABREAppICON.png")
            icon_image = Image.open(icon_path)
            icon_photo = ImageTk.PhotoImage(icon_image)
            self.iconphoto(True, icon_photo)
        except Exception as e:
            print(f"Error loading application icon: {e}")
            
        self.setup_variables()
        self.create_scrollable_frame()
        self.create_widgets()
        self.time_window = None  # Store the time window for plotting
        self.start_time = None   # Track when plotting starts
        self.stop_polarization = False  # Add this flag
        self.task_lock = threading.Lock()  # Add task lock

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

    def open_ai_panel(self):
        """Launch the miniature AI test panel."""
        AnalogInputPanel(self)

    def open_ao_panel(self):
        """Launch the miniature AO test panel."""
        AnalogOutputPanel(self)

    #-----------------------
    # GUI Setup Methods
    #-----------------------
    def setup_variables(self):
        """Initialize all instance variables"""
        self.polarization_method_file = None
        self.voltage_data = []
        self.time_data = []
        self.plotting = False
        self.timer_thread = None
        self.virtual_panel = None
        self.advanced_visible = False
        self.entries = {}
        self.units = {}
        self.audio_enabled = tk.BooleanVar(value=False)  # Initialize audio toggle only once here
        self.current_method_duration = None  # Add this line to track method duration
        self.test_task = None  # Add this line to track test_field task

    def create_scrollable_frame(self):
        """Create scrollable frame with working scrollbar"""
        # Create a frame to contain the canvas and scrollbar
        container = tk.Frame(self)
        container.pack(fill="both", expand=True)
        
        # Create canvas - rename to scroll_canvas to avoid confusion with matplotlib canvas
        self.scroll_canvas = tk.Canvas(container)
        self.scrollbar = tk.Scrollbar(container, orient="vertical", command=self.scroll_canvas.yview)
        
        # Create a frame inside the canvas which will be scrolled with the scrollbar
        self.scrollable_frame = tk.Frame(self.scroll_canvas)
        
        # Configure the canvas
        self.scrollable_frame.bind("<Configure>", 
            lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))
        
        # Bind mouse wheel to scrolling
        self.scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Create window inside canvas to hold the scrollable frame
        self.scroll_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack everything
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.scroll_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_widgets(self):
        # Define Parameters Section
        tk.Label(self.scrollable_frame, text="Parameters", font=("Arial", 12, "bold")).pack(anchor="w")
        self.entries, self.units = {}, {}

        # Create parameter input fields with the same format as advanced inputs
        self._create_advanced_input(self.scrollable_frame, "Bubbling Time", "bubbling_time_entry")
        self._create_advanced_input(self.scrollable_frame, "Magnetic Field", "magnetic_field_entry", units=["T", "mT", "µT"])
        self._create_advanced_input(self.scrollable_frame, "Temperature", "temperature_entry", units=["K", "C", "F"])
        self._create_advanced_input(self.scrollable_frame, "Flow Rate", "flow_rate_entry", units=["sccm"])
        self._create_advanced_input(self.scrollable_frame, "Pressure", "pressure_entry", units=["psi", "bar", "atm"])

        # Polarization Transfer Method
        self._create_polarization_method_input(self.scrollable_frame)
        
                # ---------- NI-MAX style quick-test buttons ----------
        test_f = tk.Frame(self.scrollable_frame)
        test_f.pack(fill="x", padx=5, pady=2)

        tk.Button(test_f, text="AI Test Panel",
                  command=self.open_ai_panel, width=14).pack(side="left", expand=True)
        tk.Button(test_f, text="AO Test Panel",
                  command=self.open_ao_panel, width=14).pack(side="left", expand=True)
        
        # Advanced Options Section
        self.advanced_container = tk.Frame(self.scrollable_frame)
        self.advanced_container.pack(fill="x", padx=5, pady=2)
        self.advanced_toggle = tk.Button(self.advanced_container, text="Advanced Options", command=self.toggle_advanced, anchor="w")
        self.advanced_toggle.pack(fill="x")
        self.advanced_frame = tk.Frame(self.scrollable_frame)

        # Virtual Testing Environment Button
        self.virtual_test_button = ttk.Button(self.advanced_frame, text="Virtual Testing Environment", command=self.toggle_virtual_panel)
        self.virtual_test_button.pack(fill="x", pady=2)

        # SLIC Sequence Control Button
        self.slic_control_button = ttk.Button(self.advanced_frame, text="SLIC Sequence Control", command=self.open_slic_control)
        self.slic_control_button.pack(fill="x", pady=2)

        # Advanced Input Fields
        self._create_advanced_input(self.advanced_frame, "Valve Control Timing", "valve_time_entry")
        self._create_advanced_input(self.advanced_frame, "Activation Time", "activation_time_entry")
        self._create_advanced_input(self.advanced_frame, "Degassing Time", "degassing_time_entry")
        self._create_advanced_input(self.advanced_frame, "Injection Time", "injection_time_entry")
        self._create_advanced_input(self.advanced_frame, "Transfer Time", "transfer_time_entry")
        self._create_advanced_input(self.advanced_frame, "Recycle Time", "recycle_time_entry")

        # Additional Buttons
        self._create_advanced_button("Save Parameters")
        self._create_advanced_button("Load Parameters")
        self._create_advanced_button("Download Config Files")

        # Control Buttons
        button_frame = tk.Frame(self.scrollable_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        self._create_control_button(button_frame, "Activate", "blue", self.activate_experiment, "left")
        self._create_control_button(button_frame, "Start", "green", self.start_experiment, "left")
        self._create_control_button(button_frame, "Test Field", "purple", self.test_field, "left")  # New button
        self._create_control_button(button_frame, "Scram", "red", self.scram_experiment, "right")

        # Experiment Timer
        timer_frame = tk.Frame(self.scrollable_frame)
        timer_frame.pack(fill="x", pady=2)
        
        # Timer label with audio toggle
        timer_header = tk.Frame(timer_frame)
        timer_header.pack(fill="x")
        tk.Label(timer_header, text="Experiment Time", font=("Arial", 12, "bold")).pack(side="left")
        
        # Add small audio toggle button
        audio_btn = ttk.Checkbutton(
            timer_header, 
            text="Audio", 
            variable=self.audio_enabled,
            style='Small.TCheckbutton'
        )
        audio_btn.pack(side="left", padx=5)
        
        # Create small button style
        style = ttk.Style()
        style.configure('Small.TCheckbutton', font=('Arial', 8))

        # Timer labels
        self.timer_label = tk.Label(timer_frame, text="00:00:000", font=("Arial", 14))
        self.timer_label.pack()
        self.state_label = tk.Label(timer_frame, text="State: Idle", font=("Arial", 10))
        self.state_label.pack()

        # Waveform Live View
        self._create_waveform_live_view(self.scrollable_frame)

        # Magnetic Field Live View
        self._create_live_view("Magnetic Field Live View", "Magnetic Field")

    def test_field(self):
        """Load the polarization method and send it to ao3"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        print(f"Test Field activated - Loading method from: {self.polarization_method_file}")
        
        def run_test_field():
            with self.task_lock:  # Ensure exclusive access to task resources
                try:
                    # Clean up any existing tasks first
                    self.cleanup_tasks()
                    
                    if self.stop_polarization:  # Check if stopped before starting
                        return
                        
                    with open(self.polarization_method_file) as f:
                        cfg = json.load(f)

                    # Check if this is a SLIC sequence file
                    if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                        # Use the entire method_config for SLIC sequences
                        buf, sr = build_composite_waveform(cfg)
                        daq_channel = "Dev1/ao3"  # Default channel for SLIC
                        voltage_range = {"min": -10.0, "max": 10.0}  # Default range for SLIC
                        initial_voltage = 0.0
                        final_voltage = 0.0
                    else:
                        # Original handling for regular methods
                        daq_channel = cfg.get("daq_channel", "Dev1/ao3")
                        voltage_range = cfg.get("voltage_range", {"min": -10.0, "max": 10.0})
                        initial_voltage = cfg.get("initial_voltage", 0.0)
                        final_voltage = cfg.get("final_voltage", 0.0)
                        buf, sr = build_composite_waveform(cfg["ramp_sequences"],
                                                         dc_offset=initial_voltage)

                    # ------ create & configure one task only ---------------
                    self.test_task = nidaqmx.Task()
                    self.test_task.ao_channels.add_ao_voltage_chan(
                            daq_channel,
                            min_val=voltage_range["min"],
                            max_val=voltage_range["max"])

                    # Set up UI update rate (10 Hz)
                    ui_fps = 10
                    chunk = max(1, int(sr / ui_fps))

                    self.test_task.timing.cfg_samp_clk_timing(
                            sr,
                            sample_mode=AcquisitionType.FINITE,
                            samps_per_chan=len(buf))

                    writer = AnalogSingleChannelWriter(self.test_task.out_stream,
                                                       auto_start=False)
                    writer.write_many_sample(buf)
                    self.test_task.start()

                    # quick GUI preview (sparse updates)
                    self.plotting = True
                    for i in range(0, len(buf), chunk):
                        if self.stop_polarization:
                            break
                        self.update_waveform_plot(float(buf[i]), time.time())
                        time.sleep(1.0/ui_fps)  # Maintain consistent update rate

                    self.test_task.wait_until_done(timeout=len(buf)/sr + 2.0)

                except Exception as e:
                    if not self.stop_polarization:
                        messagebox.showerror("Error",
                            f"Failed to send polarization method to ao3:\n{e}")
                finally:
                    if self.test_task:
                        try:
                            self.test_task.close()
                        except:
                            pass
                    self.test_task = None
                    self.plotting  = False
                    self.stop_polarization = False

        # Run the method in a separate thread to prevent freezing
        threading.Thread(target=run_test_field, daemon=True).start()

    def cleanup_tasks(self):
        """Clean up any existing DAQ tasks"""
        try:
            # First close our own task if it exists
            if hasattr(self, 'test_task') and self.test_task:
                try:
                    self.test_task.stop()
                    self.test_task.close()
                except:
                    pass
                self.test_task = None

            # Then try to clean up any other hanging tasks
            system = nidaqmx.system.System.local()
            for task in system.tasks:
                try:
                    task.stop()
                    task.close()
                except:
                    pass
        except Exception as e:
            print(f"Error cleaning up tasks: {e}")

    def run_polarization_method(self):
        """Run the selected polarization method from a .json file"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        self.cleanup_tasks()
        try:
            with open(self.polarization_method_file, "r") as f:
                method_config = json.load(f)

            # Check if this is a SLIC sequence file
            if isinstance(method_config, dict) and method_config.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(method_config)
                daq_channel = "Dev1/ao3"
                voltage_range = {"min": -10.0, "max": 10.0}
            else:
                daq_channel = method_config.get("daq_channel", "Dev1/ao3")
                voltage_range = method_config.get("voltage_range", {"min": -10.0, "max": 10.0})
                initial_voltage = method_config.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(method_config["ramp_sequences"],
                                               dc_offset=initial_voltage)

            # Configure task
            task = nidaqmx.Task()
            try:
                # Configure channel
                task.ao_channels.add_ao_voltage_chan(
                    daq_channel,
                    min_val=voltage_range["min"],
                    max_val=voltage_range["max"]
                )

                # Configure timing with exact buffer size
                task.timing.cfg_samp_clk_timing(
                    sr,
                    sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                    samps_per_chan=len(buf)
                )

                # Use single writer for better performance
                writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(
                    task.out_stream, auto_start=False)

                # Write all samples at once
                writer.write_many_sample(buf)

                # Start the task
                task.start()

                # Update plot at reasonable intervals
                plot_interval = max(1, sr // 100)  # Update plot ~100 times during sequence
                self.plotting = True
                
                for i in range(0, len(buf), plot_interval):
                    if self.stop_polarization:
                        break
                    self.update_waveform_plot(float(buf[i]), time.time())
                    
                # Wait for completion with timeout
                task.wait_until_done(timeout=len(buf)/sr + 1.0)

            finally:
                try:
                    if task.is_task_done():
                        task.write(0.0)  # Set to 0V before closing
                    task.close()
                except:
                    pass
                self.set_voltage_to_zero()

        except Exception as e:
            print(f"Polarization method error: {e}")
            messagebox.showerror("Error", f"Failed to run polarization method: {e}")
        finally:
            self.plotting = False
            self.stop_polarization = False

    #-----------------------
    # Input Field Methods
    #-----------------------
    def _create_advanced_input(self, parent, label_text, entry_attr, units=None):
        """Create advanced input with unit selection"""
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=5, pady=2)
        
        # Label
        tk.Label(frame, text=label_text, width=25, anchor="w").pack(side="left")
        
        # Entry field
        entry = tk.Entry(frame, width=10)
        entry.pack(side="left")
        
        # Unit dropdown
        if units is None:
            units = ["sec", "min", "ms"]
        unit_var = tk.StringVar(value=units[0])
        unit_dropdown = ttk.Combobox(
            frame, 
            textvariable=unit_var,
            values=units,
            width=12,
            state="readonly"
        )
        unit_dropdown.pack(side="left")
        
        # Store both entry and unit variable
        setattr(self, entry_attr, entry)
        setattr(self, f"{entry_attr}_unit", unit_var)
        self.entries[label_text] = entry
        self.units[label_text] = unit_var
        
    def convert_value(self, value, unit, conversion_type="time"):
        """Universal value converter"""
        try:
            value = float(value)
            conversions = {
                "time": {"sec": 1, "min": 60, "ms": 0.001},
                "magnetic": {"T": 1, "mT": 1e-3, "µT": 1e-6},
                "pressure": {"psi": 1, "bar": 14.5038, "atm": 14.696},
                "temperature": {
                    "K": lambda x: x,
                    "C": lambda x: x + 273.15,
                    "F": lambda x: (x - 32) * 5/9 + 273.15
                }
            }
            conv = conversions.get(conversion_type, {})
            converter = conv.get(unit)
            return converter(value) if callable(converter) else value * (converter or 0)
        except (ValueError, KeyError, TypeError):
            return 0

    def get_value(self, entry_attr, conversion_type="time"):
        """Universal getter for converted values"""
        entry = getattr(self, entry_attr)
        unit_var = getattr(self, f"{entry_attr}_unit")
        return self.convert_value(entry.get(), unit_var.get(), conversion_type)

    def _create_advanced_button(self, text):
        command = None
        if text == "Save Parameters":
            command = self.save_parameters
        elif text == "Load Parameters":
            command = self.load_parameters
        elif text == "Download Config Files":
            command = self.download_config_files
        ttk.Button(self.advanced_frame, text=text, command=command).pack(fill="x", pady=2)

    def _create_control_button(self, parent, text, color, command, side):
        tk.Button(parent, text=text, bg=color, width=12, command=command).pack(side=side, expand=True)

    def _create_live_view(self, section_title, label_text, combobox_values=None):
        tk.Label(self.scrollable_frame, text=section_title, font=("Arial", 12, "bold")).pack(anchor="w")
        frame = tk.Frame(self.scrollable_frame)
        frame.pack(fill="x", padx=5, pady=2)
        tk.Label(frame, text=label_text, width=25, anchor="w").pack(side="left")
        if combobox_values:
            var = tk.StringVar(value=combobox_values[0])
            ttk.Combobox(frame, textvariable=var, values=combobox_values, width=10, state="readonly").pack(side="left")

    def _create_polarization_method_input(self, parent):
        """Create input for selecting polarization transfer method .json file"""
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=5, pady=2)
        tk.Label(frame, text="Polarization Transfer Method", width=25, anchor="w").pack(side="left")
        self.polarization_method_button = ttk.Button(frame, text="Select Method", command=self.select_polarization_method)
        self.polarization_method_button.pack(side="left")
        self.selected_method_label = tk.Label(frame, text="No file selected", width=25, anchor="w")
        self.selected_method_label.pack(side="left")

    def select_polarization_method(self):
        """Prompt user to select a .json file for polarization transfer method"""
        file_path = filedialog.askopenfilename(
            initialdir=r"C:\Users\walsworthlab\Desktop\SABRE Panel Program\config_files_SABRE\PolarizationMethods",
            title="Select Polarization Method",
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            self.polarization_method_file = file_path
            self.selected_method_label.config(text=os.path.basename(file_path))

    def open_slic_control(self):
        """Open the SLIC Sequence Control panel"""
        SLICSequenceControl(self)

    #-----------------------
    # Plot and Display Methods
    #-----------------------
    def _create_waveform_live_view(self, parent):
        """Create the waveform live view plot"""
        tk.Label(parent, text="Waveform Live View", font=("Arial", 12, "bold")).pack(anchor="w")
        self.fig, self.ax = plt.subplots(figsize=(5, 4))
        self.ax.set_title("Voltage vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.y_min = float('inf')
        self.y_max = float('-inf')

    def update_waveform_plot(self, voltage, timestamp):
        """Update the waveform plot with new data"""
        if not self.plotting:
            return

        if self.start_time is None:
            self.start_time = timestamp
            # Use the method duration for the time window if available
            if self.current_method_duration:
                self.time_window = max(self.current_method_duration, 0.1)  # Ensure minimum window
            else:
                self.time_window = max(
                    self.get_value('bubbling_time_entry') +
                    self.get_value('valve_time_entry') * 3 +
                    self.get_value('transfer_time_entry') +
                    self.get_value('recycle_time_entry'),
                    0.1  # Minimum time window of 0.1 seconds
                )

        # Update data
        relative_time = timestamp - self.start_time
        self.voltage_data.append(voltage)
        self.time_data.append(relative_time)
        
        # Update y-axis limits
        self.y_min = min(self.y_min, voltage)
        self.y_max = max(self.y_max, voltage)
        y_range = max(self.y_max - self.y_min, 0.1)  # Ensure non-zero range
        y_padding = y_range * 0.1
        
        # Clear and redraw
        self.ax.clear()
        self.ax.plot(self.time_data, self.voltage_data, 'b-', label="Voltage")
        
        # Set axis limits with minimum range
        self.ax.set_xlim(0, max(self.time_window, relative_time + 0.1))
        self.ax.set_ylim([self.y_min - y_padding, self.y_max + y_padding])
        
        # Add labels and title
        self.ax.set_title("Voltage vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.grid(True)
        self.ax.legend()
        
        # Force canvas update
        self.canvas.draw()
        self.canvas.flush_events()

    def reset_waveform_plot(self):
        """Reset the waveform plot"""
        self.voltage_data.clear()
        self.time_data.clear()
        self.start_time = None
        self.y_min = float('inf')
        self.y_max = float('-inf')
        self.ax.clear()
        self.ax.set_title("Voltage vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.canvas.draw()

    #-----------------------
    # Experiment Control Methods
    #-----------------------
    def activate_experiment(self):
        """Activate the experiment sequence"""
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
            if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
                self.virtual_panel = VirtualTestingPanel(self)
            # Load initial state with DAQ interaction
            self.virtual_panel.load_config("Initial_State")
            self.virtual_panel.start_sequence()

    def start_experiment(self):
        """Start the bubbling sequence"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        missing_params = []
        required_fields = [
            ("Bubbling Time", self.bubbling_time_entry),
            ("Valve Control Timing", self.valve_time_entry),
            ("Transfer Time", self.transfer_time_entry),
            ("Recycle Time", self.recycle_time_entry),
        ]
        for param, entry in required_fields:
            if not entry.get():
                missing_params.append(param)
        if missing_params:
            self.show_error_popup(missing_params)
            return

        # Reset plot before starting new experiment
        self.reset_waveform_plot()
        
        if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
            self.virtual_panel = VirtualTestingPanel(self)
        # Load initial bubbling state with DAQ interaction
        self.virtual_panel.load_config("Bubbling_State_Initial")
        self.virtual_panel.start_sequence_bubbling()

        # Run the selected polarization method in a separate thread
        threading.Thread(target=self.run_polarization_method, daemon=True).start()

    def run_polarization_method(self):
        """Run the selected polarization method from a .json file"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        self.cleanup_tasks()
        try:
            with open(self.polarization_method_file, "r") as f:
                method_config = json.load(f)

            # Check if this is a SLIC sequence file
            if isinstance(method_config, dict) and method_config.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(method_config)
                daq_channel = "Dev1/ao3"
                voltage_range = {"min": -10.0, "max": 10.0}
            else:
                daq_channel = method_config.get("daq_channel", "Dev1/ao3")
                voltage_range = method_config.get("voltage_range", {"min": -10.0, "max": 10.0})
                initial_voltage = method_config.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(method_config["ramp_sequences"],
                                               dc_offset=initial_voltage)

            # Configure task
            task = nidaqmx.Task()
            try:
                # Configure channel
                task.ao_channels.add_ao_voltage_chan(
                    daq_channel,
                    min_val=voltage_range["min"],
                    max_val=voltage_range["max"]
                )

                # Configure timing with exact buffer size
                task.timing.cfg_samp_clk_timing(
                    sr,
                    sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                    samps_per_chan=len(buf)
                )

                # Use single writer for better performance
                writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(
                    task.out_stream, auto_start=False)

                # Write all samples at once
                writer.write_many_sample(buf)

                # Start the task
                task.start()

                # Update plot at reasonable intervals
                plot_interval = max(1, sr // 100)  # Update plot ~100 times during sequence
                self.plotting = True
                
                for i in range(0, len(buf), plot_interval):
                    if self.stop_polarization:
                        break
                    self.update_waveform_plot(float(buf[i]), time.time())
                    
                # Wait for completion with timeout
                task.wait_until_done(timeout=len(buf)/sr + 1.0)

            finally:
                try:
                    if task.is_task_done():
                        task.write(0.0)  # Set to 0V before closing
                    task.close()
                except:
                    pass
                self.set_voltage_to_zero()

        except Exception as e:
            print(f"Polarization method error: {e}")
            messagebox.showerror("Error", f"Failed to run polarization method: {e}")
        finally:
            self.plotting = False
            self.stop_polarization = False

    #-----------------------
    # Timer Methods
    #-----------------------
    def start_timer(self, total_seconds):
        """Start the countdown timer"""
        self.end_time = time.time() + float(total_seconds)
        self.update_timer_label(float(total_seconds))
        if self.timer_thread:
            self.timer_thread.cancel()
        self.timer_thread = threading.Timer(0.001, self.countdown)
        self.timer_thread.start()

    def countdown(self):
        """Countdown timer logic"""
        remaining = self.end_time - time.time()
        if remaining > 0:
            self.update_timer_label(remaining)
            self.timer_thread = threading.Timer(0.001, self.countdown)
            self.timer_thread.start()
        else:
            self.update_timer_label(0)
            self.timer_label.config(text="00:00:000")
            self.timer_thread = None
            self.reset_waveform_plot()
            
            # Play sound if enabled - now this will work with BooleanVar
            try:
                if self.audio_enabled.get():
                    winsound.Beep(1000, 500)  # 1000Hz for 500ms
            except Exception as e:
                print(f"Error playing sound: {e}")

    def update_timer_label(self, remaining):
        """Update the timer label"""
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        milliseconds = int((remaining * 1000) % 1000)
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}")

    #-----------------------
    # Data Management Methods
    #-----------------------
    def save_parameters(self):
        """Save all current parameters to a config file"""
        # Collect all parameter values
        params = {
            # Main parameters with their units
            "Parameters": {
                param: {
                    "value": entry.get(),
                    "unit": self.units[param].get()
                } for param, entry in self.entries.items()
            },
            # Advanced parameters with their units
            "Advanced": {
                "Valve Control Timing": {
                    "value": self.valve_time_entry.get(),
                    "unit": self.valve_time_entry_unit.get()
                },
                "Activation Time": {
                    "value": self.activation_time_entry.get(),
                    "unit": self.activation_time_entry_unit.get()
                },
                "Degassing Time": {
                    "value": self.degassing_time_entry.get(),
                    "unit": self.degassing_time_entry_unit.get()
                },
                "Injection Time": {
                    "value": self.injection_time_entry.get(),
                    "unit": self.injection_time_entry_unit.get()
                },
                "Transfer Time": {
                    "value": self.transfer_time_entry.get(),
                    "unit": self.transfer_time_entry_unit.get()
                },
                "Recycle Time": {
                    "value": self.recycle_time_entry.get(),
                    "unit": self.recycle_time_entry_unit.get()
                }
            },
            # Polarization method
            "Polarization_Method": self.polarization_method_file
        }

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save Parameters"
        )
        if file_path:
            with open(file_path, "w") as f:
                json.dump(params, f, indent=4)
            print(f"Parameters saved to {file_path}")

    def load_parameters(self):
        """Load all parameters from a config file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Load Parameters"
        )
        if file_path:
            try:
                with open(file_path, "r") as f:
                    params = json.load(f)

                # Load main parameters
                for param, data in params.get("Parameters", {}).items():
                    if param in self.entries:
                        self.entries[param].delete(0, tk.END)
                        self.entries[param].insert(0, data["value"])
                        self.units[param].set(data["unit"])

                # Load advanced parameters
                advanced_params = params.get("Advanced", {})
                advanced_entries = {
                    "Valve Control Timing": (self.valve_time_entry, self.valve_time_entry_unit),
                    "Activation Time": (self.activation_time_entry, self.activation_time_entry_unit),
                    "Degassing Time": (self.degassing_time_entry, self.degassing_time_entry_unit),
                    "Injection Time": (self.injection_time_entry, self.injection_time_entry_unit),
                    "Transfer Time": (self.transfer_time_entry, self.transfer_time_entry_unit),
                    "Recycle Time": (self.recycle_time_entry, self.recycle_time_entry_unit)
                }

                for param, (entry, unit_var) in advanced_entries.items():
                    if param in advanced_params:
                        entry.delete(0, tk.END)
                        entry.insert(0, advanced_params[param]["value"])
                        unit_var.set(advanced_params[param]["unit"])

                # Load polarization method
                if "Polarization_Method" in params and params["Polarization_Method"]:
                    self.polarization_method_file = params["Polarization_Method"]
                    self.selected_method_label.config(
                        text=os.path.basename(params["Polarization_Method"])
                    )

                print(f"Parameters loaded from {file_path}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load parameters: {e}")

    def download_config_files(self):
        """Download config files to the Downloads folder"""
        download_dir = filedialog.askdirectory(title="Select Download Directory")
        if download_dir:
            dest_dir = os.path.join(download_dir, "config_files_SABRE")
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            for file_name in os.listdir(CONFIG_DIR):
                full_file_name = os.path.join(CONFIG_DIR, file_name)
                if os.path.isfile(full_file_name):
                    shutil.copy(full_file_name, dest_dir)
            print(f"Config files downloaded to {dest_dir}")

    #-----------------------
    # Hardware Interface Methods
    #-----------------------
    def send_daq_signals(self, dio_states):
        """Send digital signals to DAQ based on DIO states"""
        try:
            with nidaqmx.Task() as task:
                # Configure all channels at once
                task.do_channels.add_do_chan(','.join(DIO_CHANNELS))
                
                # Convert states to 1 for HIGH and 0 for LOW
                signals = [1 if dio_states[f"DIO{i}"] else 0 for i in range(8)]
                
                # Convert the list of signals to a single unsigned 32-bit integer
                signal_value = sum(val << idx for idx, val in enumerate(signals))
                
                # Write the signal as an unsigned 32-bit integer
                task.write(signal_value, auto_start=True)
                    
        except Exception as e:
            print(f"Error sending DAQ signals: {e}")
            self.show_error_popup(["DAQ communication error. Check hardware connection."])

    def set_voltage_to_zero(self):
        """Set the voltage to 0V on ao3 with proper cleanup"""
        try:
            # First try to cleanup any existing tasks
            self.cleanup_tasks()
            
            # Create new task with context manager
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan("Dev1/ao3", min_val=-10.0, max_val=10.0)
                task.write(0.0, auto_start=True)
                print("Set voltage to 0V")
                self.update_waveform_plot(0.0, time.time())
        except Exception as e:
            print(f"Error setting voltage to 0V: {e}")

    def load_config(self, state):
        """Load and apply configuration from file."""
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
            self.state_label.config(text=f"State: {human_readable_state}")
            self.virtual_state_label.config(text=f"Current State: {state}")

            # Map valve numbers to DIO channels (Valve 1 = DIO0, etc)
            dio_states = {}
            for i in range(8):
                dio_states[f"DIO{i}"] = config_data.get(f"DIO{i}", "LOW").upper() == "HIGH"

            # Update virtual indicators
            for dio, is_active in dio_states.items():
                self.update_circle_state(dio, is_active)
            
            # Send signals to DAQ
            self.send_daq_signals(dio_states)

            return True

        except Exception as error:
            print(f"Error loading state {state}: {error}")
            return False

    #-----------------------
    # GUI Control Methods
    #-----------------------
    def toggle_advanced(self):
        """Toggle visibility of advanced options"""
        if self.advanced_visible:
            self.advanced_frame.pack_forget()
            self.advanced_toggle.config(text="Advanced Options ▼")
        else:
            self.advanced_frame.pack(fill="x", padx=5, pady=2, after=self.advanced_container)
            self.advanced_toggle.config(text="Advanced Options ▲")
        self.advanced_visible = not self.advanced_visible

    def toggle_virtual_panel(self):
        """Toggle the Virtual Testing Environment window"""
        if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
            self.virtual_panel = VirtualTestingPanel(self)
        else:
            self.virtual_panel.destroy()
            self.virtual_panel = None

    def open_full_flow_system(self):
        """Open the Full Flow System window"""
        FullFlowSystem(self)

    def load_config_visual(self, state):
        """Load configuration for visual testing only - no DAQ interaction"""
        try:
            config_file = os.path.join(CONFIG_DIR, f"{state}.json")
            
            if not os.path.exists(config_file):
                print(f"Configuration file not found: {config_file}")
                return False

            with open(config_file, "r") as file:
                config_data = json.load(file)

            # Update state labels (visual only)
            human_readable_state = self.state_mapping.get(state, "Unknown State")
            self.state_label.config(text=f"Current State: {state}")

            # Update hourglass colors only
            dio_states = {f"DIO{i}": config_data.get(f"DIO{i}", "LOW").upper() == "HIGH" for i in range(8)}
            for dio, is_active in dio_states.items():
                self.update_hourglass_state(dio, is_active)

            return True

        except Exception as error:
            print(f"Error in visual simulation: {error}")
            return False

    def show_error_popup(self, missing_params):
        """Display error popup with missing parameters"""
        error_message = "Missing required parameters:\n" + "\n".join(f"• {param}" for param in missing_params)
        messagebox.showerror("Missing Parameters", error_message)

    def _fast_reset_daq(self):
        """Hard-reset NI device, drop all tasks, return outputs to safe state."""
        try:
            if self.test_task:
                self.test_task.stop()
                self.test_task.close()
                self.test_task = None
        except Exception:
            pass

        try:
            nidaqmx.system.System.local().devices[DAQ_DEVICE].reset()
        except Exception as e:
            print(f"Device reset failed: {e}")

        try:
            with nidaqmx.Task() as ao_task:
                ao_task.ao_channels.add_ao_voltage_chan(f"{DAQ_DEVICE}/ao3",
                                                        min_val=-10.0, max_val=10.0)
                ao_task.write(0.0, auto_start=True)
            with nidaqmx.Task() as do_task:
                do_task.do_channels.add_do_chan(','.join(DIO_CHANNELS))
                do_task.write([0]*8, auto_start=True)
        except Exception as e:
            print(f"Post-reset voltage/DIO step failed: {e}")

    def scram_experiment(self):
        """Emergency stop – immediate GUI feedback plus async hardware reset."""
        self.stop_polarization = True
        self.plotting = False
        if self.timer_thread:
            self.timer_thread.cancel()
            self.timer_thread = None

        # kick off fast hardware reset without blocking UI
        threading.Thread(target=self._fast_reset_daq, daemon=True).start()

        # GUI clean-up
        self.timer_label.config(text="00:00:000")
        self.state_label.config(text="State: Idle")
        self.reset_waveform_plot()
        if self.virtual_panel and self.virtual_panel.winfo_exists():
            self.virtual_panel.running = False
            self.virtual_panel.load_config("Initial_State")
        if self.audio_enabled.get():
            threading.Thread(target=lambda: winsound.Beep(2000, 400), daemon=True).start()

        self.start_time = None
        self.time_window = None
        self.stop_polarization = False
        self.plotting = False
        print("Emergency stop completed (fast-path)")

# ==== END MAIN WINDOW : SABREGUI ==========================

# ==== MAIN WINDOW : Main ===============================
if __name__ == "__main__":
    app = SABREGUI()
    app.mainloop()
# ==== END MAIN WINDOW : Main ==========================