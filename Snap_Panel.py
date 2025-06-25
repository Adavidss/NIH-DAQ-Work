import json
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import winsound

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

from Constants_Paths import (
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
    
    def __init__(self):
        super().__init__()
            
        # Initialize ScramController with new implementation
        self.scram = ScramController(self)
        
        self.setup_variables()
        self.create_scrollable_frame()
        
        # Initialize ParameterSection after scrollable_frame is created
        self.parameter_section = ParameterSection(self, self.scrollable_frame)
        
        # Initialize PresetManager after ParameterSection
        self.preset_manager = PresetManager(self, self.parameter_section)
        
        self.create_widgets()
        self.time_window = None  # Store the time window for plotting
        self.start_time = None   # Track when plotting starts
        self.stop_polarization = False  # Add this flag
        self.task_lock = threading.Lock()  # Add task lock
        
        # Timer variables
        self.timer_active = False
        self.timer_start_time = None
        self.timer_duration = 0.0
        self.timer_update_job = None  # For after() job tracking

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
        self.audio_enabled = tk.BooleanVar(value=False)  # Initialize audio toggle only once here
        self.tooltips_enabled = tk.BooleanVar(value=True)  # Initialize tooltip toggle to be ON by default
        self.current_method_duration = None  # Track method duration
        self.test_task = None  # Track test_field task
        self.dio_task = None  # Add persistent DIO task tracking
        
        # Timer variables
        self.timer_active = False
        self.timer_start_time = None
        self.timer_duration = 0.0

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
            self.start_timer(total_time)

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
            self.load_config("Initial_State")  # Always return to initial state
            # Update virtual panel if it exists
            if self.virtual_panel and self.virtual_panel.winfo_exists():
                self.virtual_panel.load_config_visual("Initial_State")

    def start_experiment(self):
        """Start the bubbling sequence with integrated method timing"""
        # always begin from a clean baseline
        self._reset_run_state()

        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        missing_params = []
        required_fields = [
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
            self.start_timer(total_time)
            
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
        """Load the polarization method and send it to ao1 with proper DAQ interaction"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        print(f"Test Field activated - Loading method from: {self.polarization_method_file}")
        
        # Load and plot the waveform on the main thread first
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
            
            # Calculate method duration and start timer on main thread
            method_duration = len(buf) / sr
            self.start_timer(method_duration)
            
            # Plot the waveform on the main thread
            self._plot_waveform_buffer(buf, sr)
            
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
                        
                    # Reload the config (we already validated it exists above)
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

                        writer = AnalogSingleChannelWriter(self.test_task.out_stream,
                                                       auto_start=False)
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

    def set_voltage_to_zero(self):
        """Delegate voltage zeroing to ScramController"""
        self.scram.set_voltage_to_zero()

    def open_slic_control(self):
        """Open the SLIC Sequence Control window"""
        try:
            SLICSequenceControl(self)
        except Exception as e:
            print(f"Error opening SLIC Sequence Control: {e}")
            messagebox.showerror("Error", f"Failed to open SLIC Sequence Control: {e}")

    def open_polarization_calculator(self):
        """Open the Polarization Calculator window"""
        try:
            PolarizationApp(self)
        except Exception as e:
            print(f"Error opening Polarization Calculator: {e}")
            messagebox.showerror("Error", f"Failed to open Polarization Calculator: {e}")

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
                temp_dio_task.write(signal_value, auto_start=True)
                
            # Task automatically closes when exiting context manager
            # DIO lines will maintain their states until explicitly changed
                    
        except Exception as e:
            print(f"Error sending DAQ signals: {e}")
            self.show_error_popup(["DAQ communication error. Check hardware connection."])

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

    def scram_experiment(self):
        """Instant emergency stop with proper DAQ interaction."""
        print("EMERGENCY STOP ACTIVATED")
        # Stop timer
        self.stop_timer()
        self.reset_timer()
        
        # Stop polarization and running flag
        self.stop_polarization = True
        if hasattr(self, 'running'):
            self.running = False  # Added flag to stop sequences
        
        # Use ScramController to handle emergency stop
        self.scram()
    
        # Reset state label
        self.state_label.config(text="State: EMERGENCY STOP")
        
        # Alert user
        if self.audio_enabled.get():
            try:
                winsound.Beep(2000, 100)
                winsound.Beep(1500, 100)
                winsound.Beep(1000, 100)
            except Exception as e:
                print(f"Audio alert error: {e}")

    def _reset_run_state(self, clear_plot: bool = True):
        """Fully reset timers, DAQ tasks, buffers, and button states."""
        # 1 ) stop timers
        if self.timer_thread:
            self.timer_thread.cancel()
            self.timer_thread = None
        
        # Only reset end_time if we're doing a full reset (clear_plot=True)
        if clear_plot:
            self.end_time = None

        # 2 ) cancel any Tk `after` job
        if self.after_job_id:
            self.after_cancel(self.after_job_id)
            self.after_job_id = None

        # 3 ) shut down DAQ tasks
        try:
            self.scram.cleanup_tasks()          # zeroes AO + closes tasks
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

        # 4 ) reset flags
        self.stop_polarization = False
        self.plotting = False
        self.start_time = None

        # 5 ) clear / recreate plot
        if clear_plot:
            self.reset_waveform_plot()

        # 6 ) return GUI to idle
        self.state_label.config(text="State: Idle")
        for child in self.scrollable_frame.winfo_children():
            if isinstance(child, tk.Button):
                child.config(state="normal")

    def start_timer(self, total_seconds):
        """Start the countdown timer"""
        # Stop any existing timer
        self.stop_timer()
        
        # Set up the end time for countdown
        self.end_time = time.time() + float(total_seconds)
        
        # Initialize display with full time
        self.update_timer_label(float(total_seconds))
        
        # Set timer to active
        self.timer_active = True
        
        # Start the countdown immediately
        self.countdown()
        
        # Play audio alert if enabled
        if self.audio_enabled.get():
            try:
                winsound.Beep(1000, 500)  # 1000 Hz for 500 ms
            except Exception as e:
                print(f"Audio alert error: {e}")
            

    def countdown(self):
        """Countdown timer logic"""
        if not self.timer_active:
            return
            
        if not hasattr(self, 'end_time') or self.end_time is None:
            return
            
        remaining = max(0, self.end_time - time.time())
        
        if remaining > 0:
            # Update the display with remaining time
            self.update_timer_label(remaining)
            
            # Schedule next update (about 10 updates per second)
            self.timer_update_job = self.after(100, self.countdown)
        else:
            # Timer complete
            self.update_timer_label(0)
            self.timer_label.config(fg="green")
            
            # Play completion sound if audio enabled
            if self.audio_enabled.get():
                try:
                    winsound.Beep(880, 200)
                    winsound.Beep(1760, 300)
                except Exception as e:
                    print(f"Audio alert error: {e}")
            
            # Start flashing animation
            self._flash_timer()
            
            # Reset timer state
            self.timer_active = False
            self.timer_update_job = None

    def _flash_timer(self):
        """Flash the timer when complete"""
        if not hasattr(self, 'timer_label') or not self.timer_label.winfo_exists():
            return
            
        # Toggle between green and blue 3 times
        colors = ["green", "blue", "green", "blue", "green"]
        
        def flash_sequence(index=0):
            if index >= len(colors):
                self.timer_label.config(fg="green")  # Final color
                return
                
            self.timer_label.config(fg=colors[index])
            self.after(300, flash_sequence, index + 1)
            
        flash_sequence()

    def stop_timer(self):
        """Stop the experiment timer"""
        self.timer_active = False
        
        # Cancel any pending after() job
        if hasattr(self, 'timer_update_job') and self.timer_update_job:
            try:
                self.after_cancel(self.timer_update_job)
            except Exception as e:
                print(f"Error cancelling timer job: {e}")
            self.timer_update_job = None
        
        # Reset timer variables
        if hasattr(self, 'end_time'):
            self.end_time = None

    def reset_timer(self):
        """Reset timer to initial state"""
        self.stop_timer()
        if hasattr(self, 'timer_label'):
            self.timer_label.config(text="00:00:000", fg="black")
        if hasattr(self, 'end_time'):
            self.end_time = None
        self.timer_duration = 0.0

    def update_timer_label(self, remaining):
        """Update the timer label with formatted remaining time"""
        if hasattr(self, 'timer_label'):
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining * 1000) % 1000)
            self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}")
            
    def download_config_files(self):
        """Download config files to a user-selected directory"""
        download_dir = filedialog.askdirectory(title="Select Download Directory")
        if download_dir:
            dest_dir = os.path.join(download_dir, "config_files_SABRE")
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            for file_name in os.listdir(CONFIG_DIR):
                full_file_name = os.path.join(CONFIG_DIR, file_name)
                if os.path.isfile(full_file_name):
                    shutil.copy(full_file_name, dest_dir)
            messagebox.showinfo("Success", f"Config files downloaded to {dest_dir}")
            print(f"Config files downloaded to {dest_dir}")

# ==== MAIN WINDOW : Main ===============================
if __name__ == "__main__":
    app = SABREGUI()
    app.mainloop()
# ==== END MAIN WINDOW : Main ==========================