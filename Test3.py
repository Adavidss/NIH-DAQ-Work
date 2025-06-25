import json
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
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
    
    def __init__(self, master=None):
        super().__init__(master=master)
            
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
                  foreground=[("selected", "white")])        # Create scrollable frame first
        self.create_scrollable_frame()
        
        # Create necessary widgets using parent class method
        self.create_widgets()
        
        # Build the main tab UI
        self._build_main_tab_ui()
        
        # bind <Configure> to handle overflow
        self.bind("<Configure>", lambda e: self._update_tab_overflow())        # bind right-click for tear-off (not left-click)
        self.notebook.bind("<Button-3>", self._maybe_clone_tab, add="+")
        # ------------------------------------------------------------
        
        self.time_window = None  # Store the time window for plotting
        self.start_time = None   # Track when plotting starts
        self.stop_polarization = False  # Add this flag
        self.task_lock = threading.Lock()  # Add task lock
        
        # Timer variables
        self.timer_active = False
        self.timer_start_time = None
        self.timer_duration = 0.0
        self.timer_update_job = None  # For after() job tracking        # Track any Tk "after" job IDs so we can cancel them
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
        
        # Timer variables
        self.timer_active = False
        self.timer_start_time = None
        self.timer_duration = 0.0
        
        # Ensure entries exist to prevent KeyError
        self._ensure_entries_exist()

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
        AnalogInputPanel(self, embedded=False)

    def open_ao_panel(self):
        """Launch the miniature AO test panel."""
        AnalogOutputPanel(self, embedded=False)

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
            
            # Clear any timers
            if hasattr(self, 'timer_update_id') and self.timer_update_id:
                self.after_cancel(self.timer_update_id)
                self.timer_update_id = None
                
            # Reset timer
            self.timer_active = False
            self.timer_seconds = 0
            if hasattr(self, 'timer_label'):
                self.timer_label.config(text="00:00")
            
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

    def start_timer(self, duration):
        """Start the experiment timer"""
        try:
            self.timer_active = True
            self.timer_start_time = time.time()
            self.timer_duration = duration
            self._update_timer()
            print(f"Timer started for {duration} seconds")
        except Exception as e:
            print(f"Error starting timer: {e}")

    def _update_timer(self):
        """Update the timer display"""
        try:
            if not self.timer_active or not hasattr(self, 'timer_label'):
                return
                
            if self.timer_start_time is None:
                return
                
            elapsed = time.time() - self.timer_start_time
            remaining = max(0, self.timer_duration - elapsed)
            
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining % 1) * 1000)
            
            time_str = f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
            self.timer_label.config(text=time_str)
            
            if remaining > 0:
                self.after_job_id = self.after(100, self._update_timer)
            else:
                self.timer_active = False
                self.timer_label.config(text="00:00:000")
                
        except Exception as e:
            print(f"Error updating timer: {e}")

    def _reset_run_state(self):
        """Reset the running state and clean up any active processes"""
        try:
            self.running = False
            self.stop_polarization = True
            
            # Stop any active timer
            if hasattr(self, 'timer_active') and self.timer_active:
                self.timer_active = False
            
            # Cancel any pending after jobs
            if hasattr(self, 'after_job_id') and self.after_job_id:
                try:
                    self.after_cancel(self.after_job_id)
                except:
                    pass
                self.after_job_id = None
                
            print("Run state reset successfully")
            
        except Exception as e:
            print(f"Error resetting run state: {e}")

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
            self.virtual_panel = VirtualTestingPanel(self, embedded=False)
        else:
            if hasattr(self.virtual_panel, 'toplevel') and self.virtual_panel.toplevel:
                self.virtual_panel.toplevel.destroy()
            else:
                self.virtual_panel.destroy()
            self.virtual_panel = None

    def open_full_flow_system(self):
        """Open the Full Flow System window"""
        FullFlowSystem(self, embedded=False)

    def scram_experiment(self):
        """Emergency stop - immediately halt all operations"""
        try:
            print("SCRAM button pressed - Emergency stop initiated")
            
            # Set stop event to terminate threads
            self.stop_event.set()
            
            # Clear any timers
            if hasattr(self, 'timer_update_id') and self.timer_update_id:
                self.after_cancel(self.timer_update_id)
                self.timer_update_id = None
                
            # Reset timer
            self.timer_active = False
            self.timer_seconds = 0
            if hasattr(self, 'timer_label'):
                self.timer_label.config(text="00:00")
            
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

    def start_timer(self, duration):
        """Start the experiment timer"""
        try:
            self.timer_active = True
            self.timer_start_time = time.time()
            self.timer_duration = duration
            self._update_timer()
            print(f"Timer started for {duration} seconds")
        except Exception as e:
            print(f"Error starting timer: {e}")

    def _update_timer(self):
        """Update the timer display"""
        try:
            if not self.timer_active or not hasattr(self, 'timer_label'):
                return
                
            if self.timer_start_time is None:
                return
                
            elapsed = time.time() - self.timer_start_time
            remaining = max(0, self.timer_duration - elapsed)
            
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining % 1) * 1000)
            
            time_str = f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
            self.timer_label.config(text=time_str)
            
            if remaining > 0:
                self.after_job_id = self.after(100, self._update_timer)
            else:
                self.timer_active = False
                self.timer_label.config(text="00:00:000")
                
        except Exception as e:
            print(f"Error updating timer: {e}")

    def _reset_run_state(self):
        """Reset the running state and clean up any active processes"""
        try:
            self.running = False
            self.stop_polarization = True
            
            # Stop any active timer
            if hasattr(self, 'timer_active') and self.timer_active:
                self.timer_active = False
            
            # Cancel any pending after jobs
            if hasattr(self, 'after_job_id') and self.after_job_id:
                try:
                    self.after_cancel(self.after_job_id)
                except:
                    pass
                self.after_job_id = None
                
            print("Run state reset successfully")
            
        except Exception as e:
            print(f"Error resetting run state: {e}")

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
            self.virtual_panel = VirtualTestingPanel(self, embedded=False)
        else:
            if hasattr(self.virtual_panel, 'toplevel') and self.virtual_panel.toplevel:
                self.virtual_panel.toplevel.destroy()
            else:
                self.virtual_panel.destroy()
            self.virtual_panel = None

    def open_full_flow_system(self):
        """Open the Full Flow System window"""
        FullFlowSystem(self, embedded=False)

    def scram_experiment(self):
        """Emergency stop - immediately halt all operations"""
        try:
            print("SCRAM button pressed - Emergency stop initiated")
            
            # Set stop event to terminate threads
            self.stop_event.set()
            
            # Clear any timers
            if hasattr(self, 'timer_update_id') and self.timer_update_id:
                self.after_cancel(self.timer_update_id)
                self.timer_update_id = None
                
            # Reset timer
            self.timer_active = False
            self.timer_seconds = 0
            if hasattr(self, 'timer_label'):
                self.timer_label.config(text="00:00")
            
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

    def start_timer(self, duration):
        """Start the experiment timer"""
        try:
            self.timer_active = True
            self.timer_start_time = time.time()
            self.timer_duration = duration
            self._update_timer()
            print(f"Timer started for {duration} seconds")
        except Exception as e:
            print(f"Error starting timer: {e}")

    def _update_timer(self):
        """Update the timer display"""
        try:
            if not self.timer_active or not hasattr(self, 'timer_label'):
                return
                
            if self.timer_start_time is None:
                return
                
            elapsed = time.time() - self.timer_start_time
            remaining = max(0, self.timer_duration - elapsed)
            
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining % 1) * 1000)
            
            time_str = f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
            self.timer_label.config(text=time_str)
            
            if remaining > 0:
                self.after_job_id = self.after(100, self._update_timer)
            else:
                self.timer_active = False
                self.timer_label.config(text="00:00:000")
                
        except Exception as e:
            print(f"Error updating timer: {e}")

    def _reset_run_state(self):
        """Reset the running state and clean up any active processes"""
        try:
            self.running = False
            self.stop_polarization = True
            
            # Stop any active timer
            if hasattr(self, 'timer_active') and self.timer_active:
                self.timer_active = False
            
            # Cancel any pending after jobs
            if hasattr(self, 'after_job_id') and self.after_job_id:
                try:
                    self.after_cancel(self.after_job_id)
                except:
                    pass
                self.after_job_id = None
                
            print("Run state reset successfully")
            
        except Exception as e:
            print(f"Error resetting run state: {e}")

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
                
                # Write the signal value
                temp_dio_task.write([signal_value])
                
                print(f"Sent signals to DAQ: {signals}")
        except Exception as e:
            print(f"Error sending DAQ signals: {e}")
    
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
                  command=lambda: self.notebook.select(1)).pack()
          # Refresh the method list for the new combobox
        self.refresh_method_list()

    def _maybe_clone_tab(self, event):
        """If user right-clicks directly on a tab label, clone that tab into new window."""
        elem = self.notebook.identify(event.x, event.y)
        if elem != "label":
            return
        index = self.notebook.index("@%d,%d" % (event.x, event.y))
        tab_text = self.notebook.tab(index, "text")
        self._clone_tab(tab_text)

    def _clone_tab(self, tab_text):
        """Create a Toplevel containing a fresh copy of the dashboard frame."""
        if tab_text not in self._tabs:
            return
        
        try:
            win = tk.Toplevel(self)
            win.title(f"{tab_text} (Detached)")
            win.geometry("800x600")  # Set reasonable default size
            container = ttk.Frame(win)
            container.pack(fill="both", expand=True)
            
            # Create appropriate content based on tab type
            if tab_text == "Main":
                self._build_main_clone(container)
            elif tab_text == "Advanced Parameters":
                param_section = ParameterSection(self, container)
            elif tab_text == "Testing":
                self._build_testing_clone(container)
            elif tab_text == "SLIC Control":
                slic_panel = SLICSequenceControl(container, embedded=True)
                slic_panel.pack(fill="both", expand=True)
            elif tab_text == "Polarization Cal":
                pol_panel = PolarizationApp(container, embedded=True)
                pol_panel.pack(fill="both", expand=True)
            
            container.update_idletasks()
            container.pack(fill="both", expand=True)
            
        except Exception as e:
            print(f"Error creating detached tab '{tab_text}': {e}")
            messagebox.showerror("Error", f"Could not detach tab '{tab_text}': {e}")

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
        testing_notebook.pack(fill="both", expand=True, padx=2, pady=2)        # Create and embed Virtual Testing environment directly
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
            
    def safe_select_tab(self, idx):
        """Safely select a tab by index, with error handling"""
        try:
            self.notebook.select(idx)
        except Exception as e:
            print(f"Error selecting tab {idx}: {e}")    # Add missing methods that will be called
    def edit_preset(self):
        """Edit the selected preset - redirect to advanced tab"""
        messagebox.showinfo("Info", "Please use the Advanced Parameters tab for full preset management.")
        self.notebook.select(1)  # Switch to Advanced Parameters tab

    def delete_preset(self):
        """Delete the selected preset - redirect to advanced tab"""
        messagebox.showinfo("Info", "Please use the Advanced Parameters tab for full preset management.")
        self.notebook.select(1)  # Switch to Advanced Parameters tab

    def refresh_method_list(self):
        """Refresh the list of available polarization methods for all comboboxes"""
        try:
            method_files = []
            if os.path.exists(self.polarization_methods_dir):
                for file in os.listdir(self.polarization_methods_dir):
                    if file.endswith('.json'):
                        method_files.append(file)
            
            method_options = ["Select a method..."] + sorted(method_files)
            
            # Update all method comboboxes
            if hasattr(self, 'method_combobox'):
                self.method_combobox['values'] = method_options
            if hasattr(self, 'adv_method_combobox'):
                self.adv_method_combobox['values'] = method_options
                
            # Reset selection if current selection no longer exists
            if self.selected_method_var.get() not in method_options:
                self.selected_method_var.set("Select a method...")
                self.polarization_method_file = None
                
        except Exception as e:
            print(f"Error refreshing methods list: {e}")
            # Set default values for all comboboxes
            default_values = ["Select a method..."]
            if hasattr(self, 'method_combobox'):
                self.method_combobox['values'] = default_values
            if hasattr(self, 'adv_method_combobox'):
                self.adv_method_combobox['values'] = default_values

    def on_method_selected(self, event=None):
        """Handle method selection from any combobox"""
        selected = self.selected_method_var.get()
        if selected and selected != "Select a method...":
            file_path = os.path.join(self.polarization_methods_dir, selected)
            if os.path.exists(file_path):
                self.polarization_method_file = file_path
                print(f"Selected polarization method: {file_path}")
            else:
                self.polarization_method_file = None
        else:
            self.polarization_method_file = None

    def _create_general_params_preview(self, parent):
        """Create a preview of general parameters in the main tab"""
        
        # Add a few key parameters as a preview
        params = [
            ("Bubbling Time", "30.0", "s"),
            ("Magnetic Field", "100.0", "mT"),
            ("Temperature", "298", "K"),
            ("Flow Rate", "20", "sccm"),
            ("Pressure", "1.0", "atm")
        ]
        
        for i, (label, default_val, unit) in enumerate(params):
            row = tk.Frame(parent)
            row.pack(fill="x", padx=5, pady=2)
            
            tk.Label(row, text=f"{label}:", width=15, anchor="w").pack(side="left")
            entry = tk.Entry(row, width=10)
            entry.insert(0, default_val)
            entry.pack(side="left", padx=2)
            
            # Store the entry in self.entries for access by other methods
            self.entries[label] = entry
            
            # Create StringVar for unit and store it
            unit_var = tk.StringVar(value=unit)
            self.units[label] = unit_var
            
            # Make the unit label clearly non-editable with different styling
            unit_label = tk.Label(row, text=unit, width=8, anchor="w", 
                                bg="#f0f0f0", relief="sunken", bd=1, 
                                font=("Arial", 9, "italic"), fg="#666666")
            unit_label.pack(side="left", padx=2)
        
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

    def _create_presets_preview(self, parent):
        """Create a simple method selection preview in the main tab"""
        # Method selection
        method_frame = tk.Frame(parent)
        method_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(method_frame, text="Method:", anchor="w").pack(side="left")
        method_combo = ttk.Combobox(method_frame, textvariable=self.selected_method_var,
                                   state="readonly", width=20)
        method_combo.pack(side="left", fill="x", expand=True, padx=5)
        
        # Link to advanced parameters for full preset management
        link_frame = tk.Frame(parent)
        link_frame.pack(fill="x", pady=10)
        ttk.Button(link_frame, text="Manage Presets in Advanced Tab", 
                  command=lambda: self.notebook.select(1)).pack()

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
            if not hasattr(self, attr):
                entry = tk.Entry(dummy_frame)
                entry.insert(0, "0.0")  # Default value
                setattr(self, attr, entry)
        # Don't pack dummy_frame

# ------------- run -------------
if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    
    # Configure style for dark tab
    style.configure("DarkTab.TNotebook.Tab", padding=[10, 2],
                   background="#333333", foreground="white")
    style.configure("DarkTab.TNotebook", background="#f0f0f0")
    style.map("DarkTab.TNotebook.Tab",
             background=[("selected", "#555555"), ("active", "#444444")],
             foreground=[("selected", "white"), ("active", "white")])
    
    app = SABREGUI(master=root)
    app.mainloop()
