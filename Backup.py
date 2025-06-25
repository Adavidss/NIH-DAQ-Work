#######################
# IMPORTS AND GLOBALS #
#######################
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import nidaqmx
from nidaqmx.stream_writers import AnalogMultiChannelWriter, AnalogSingleChannelWriter  # Add this import
import numpy as np
import time
import threading
import json
import os
import shutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import winsound  # Add this import at the top

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config_files_SABRE")
DAQ_DEVICE = "Dev1"
DIO_CHANNELS = [f"{DAQ_DEVICE}/port0/line{i}" for i in range(8)]

#########################
# STATE CONFIGURATIONS  #
#########################
INITIAL_STATE = "Initial_State"
STATE_MAPPING = {
    "Activation_State_Final": "Activating the Sample",
    "Activation_State_Initial": "Activating the Sample",
    "Bubbling_State_Final": "Bubbling the Sample",
    "Bubbling_State_Initial": "Bubbling the Sample",
    "Degassing": "Degassing Solution",
    "Recycle": "Recycling Solution",
    "Injection_State_Start": "Injecting the Sample",
    "Transfer_Final": "Transferring the Sample",
    "Transfer_Initial": "Transferring the Sample",
    INITIAL_STATE: "Idle",
}

# Create config directory and initialize states
try:
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        states = {
            INITIAL_STATE: ["LOW", "LOW", "LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW"],
            "Injection_State_Start": ["HIGH", "LOW", "LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW"],
            "Degassing": ["LOW", "HIGH", "HIGH", "LOW", "LOW", "LOW", "HIGH", "LOW"],
            "Activation_State_Initial": ["LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW", "HIGH", "LOW"],
            "Activation_State_Final": ["LOW", "LOW", "HIGH", "LOW", "LOW", "LOW", "HIGH", "LOW"],
            "Bubbling_State_Initial": ["LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW", "HIGH", "LOW"],
            "Bubbling_State_Final": ["LOW", "LOW", "HIGH", "HIGH", "HIGH", "LOW", "HIGH", "LOW"],
            "Transfer_Initial": ["LOW", "LOW", "LOW", "LOW", "HIGH", "LOW", "HIGH", "HIGH"],
            "Transfer_Final": ["LOW", "LOW", "LOW", "LOW", "HIGH", "LOW", "HIGH", "LOW"],
            "Recycle": ["HIGH", "LOW", "LOW", "LOW", "HIGH", "LOW", "HIGH", "LOW"]
        }
        for state, dio_values in states.items():
            with open(os.path.join(CONFIG_DIR, f"{state}.json"), "w") as f:
                json.dump({f"DIO{i}": dio_values[i] for i in range(8)}, f, indent=4)
except Exception as e:
    print(f"Error creating config directory and files: {e}")
    sys.exit(1)

# ----------------------------------------------------------------------
# MINI TEST PANELS — copy / paste ABOVE class SABREGUI
# ----------------------------------------------------------------------
class AnalogInputPanel(tk.Toplevel):
    """Very small live-scope for a single AI channel (looks like NI-MAX)."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"AI Test Panel : {DAQ_DEVICE}")
        self.protocol("WM_DELETE_WINDOW", self._close)

        # ---------- controls ----------
        c = tk.Frame(self); c.pack(side="left", padx=8, pady=6)
        tk.Label(c, text="Channel").grid(row=0, column=0, sticky="w")
        chans = [f"{DAQ_DEVICE}/ai{i}" for i in range(24)]
        self.chan = tk.StringVar(value=chans[-1])
        ttk.Combobox(c, textvariable=self.chan, values=chans,
                     width=12, state="readonly").grid(row=0, column=1)

        tk.Label(c, text="Rate (Hz)").grid(row=1, column=0, sticky="w")
        self.rate_e = tk.Entry(c, width=8); self.rate_e.grid(row=1, column=1)
        self.rate_e.insert(0, "1000")

        tk.Label(c, text="Samples").grid(row=2, column=0, sticky="w")
        self.samps_e = tk.Entry(c, width=8); self.samps_e.grid(row=2, column=1)
        self.samps_e.insert(0, "1000")

        self.start_b = ttk.Button(c, text="Start", command=self._start)
        self.stop_b  = ttk.Button(c, text="Stop",  command=self._stop, state="disabled")
        self.start_b.grid(row=3, column=0, pady=4); self.stop_b.grid(row=3, column=1, pady=4)

        # ---------- plot ----------
        fig, ax = plt.subplots(figsize=(5,4)); fig.tight_layout(pad=2)
        ax.set_facecolor("black"); ax.tick_params(colors="white")
        for s in ax.spines.values(): s.set_color("white")
        ax.set_title("Amplitude vs Samples", color="white")
        ax.set_xlabel("Samples", color="white"); ax.set_ylabel("Amplitude (V)", color="white")
        ax.grid(True, color="darkgreen", alpha=0.5)

        self.line, = ax.plot([], [], color="lime", lw=1); self.ax = ax
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)

        self._task=None; self._run=False

    # ---------- NI-DAQmx ----------
    def _start(self):
        if self._run: return
        import nidaqmx.constants as C
        from nidaqmx.stream_readers import AnalogSingleChannelReader
        try:
            rate  = float(self.rate_e.get())
            samps = int(self.samps_e.get())
            self._buf = np.zeros(samps, dtype=np.float64)

            self._task = nidaqmx.Task()
            self._task.ai_channels.add_ai_voltage_chan(
                self.chan.get(), min_val=-10, max_val=10,
                terminal_config=C.TerminalConfiguration.DIFF)
            self._task.timing.cfg_samp_clk_timing(
                rate, sample_mode=C.AcquisitionType.CONTINUOUS,
                samps_per_chan=samps)

            self._reader = AnalogSingleChannelReader(self._task.in_stream)
            self._task.start()

            self._run=True
            self.start_b.config(state="disabled"); self.stop_b.config(state="normal")
            threading.Thread(target=self._loop, daemon=True).start()
        except Exception as e:
            messagebox.showerror("AI Error", str(e)); self._stop()

    def _loop(self):
        while self._run:
            try:
                self._reader.read_many_sample(self._buf,
                                              number_of_samples_per_channel=self._buf.size,
                                              timeout=2.0)
                x = np.arange(self._buf.size)
                self.line.set_data(x, self._buf)
                y0, y1 = self._buf.min(), self._buf.max()
                if y0 == y1: y0 -= .1; y1 += .1
                pad = (y1-y0)*.1
                self.ax.set_xlim(0, self._buf.size)
                self.ax.set_ylim(y0-pad, y1+pad)
                self.canvas.draw_idle()
            except Exception as e:
                print("AI loop:", e); break
        self._stop()

    def _stop(self):
        self._run=False
        self.start_b.config(state="normal"); self.stop_b.config(state="disabled")
        if self._task:
            try: self._task.stop(); self._task.close()
            except: pass
            self._task=None

    def _close(self): self._stop(); self.destroy()


class AnalogOutputPanel(tk.Toplevel):
    """Very small generator for one AO channel."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"AO Test Panel : {DAQ_DEVICE}")
        self.protocol("WM_DELETE_WINDOW", self._close)

        # ---------- controls ----------
        c = tk.Frame(self); c.pack(side="left", padx=8, pady=6)
        tk.Label(c, text="Channel").grid(row=0, column=0, sticky="w")
        chans = [f"{DAQ_DEVICE}/ao{i}" for i in range(4)]
        self.chan = tk.StringVar(value=chans[0])
        ttk.Combobox(c, textvariable=self.chan, values=chans,
                     width=12, state="readonly").grid(row=0, column=1)

        tk.Label(c, text="Mode").grid(row=1, column=0, sticky="w")
        self.mode = tk.StringVar(value="DC")
        mbox = ttk.Combobox(c, textvariable=self.mode,
                            values=["DC","Sine"], width=10, state="readonly")
        mbox.grid(row=1, column=1); mbox.bind("<<ComboboxSelected>>", self._toggle)

        tk.Label(c, text="Amplitude (V)").grid(row=2, column=0, sticky="w")
        self.amp_s = tk.Scale(c, from_=0, to=10, resolution=.1,
                              orient="horizontal", length=140)
        self.amp_s.set(1); self.amp_s.grid(row=2, column=1)

        tk.Label(c, text="Frequency (Hz)").grid(row=3, column=0, sticky="w")
        self.freq_e = tk.Entry(c, width=10); self.freq_e.grid(row=3, column=1)
        self.freq_e.insert(0, "20.0")

        tk.Label(c, text="Rate (Hz)").grid(row=4, column=0, sticky="w")
        self.rate_e = tk.Entry(c, width=10); self.rate_e.grid(row=4, column=1)
        self.rate_e.insert(0, "20000")

        self.start_b = ttk.Button(c, text="Start", command=self._start)
        self.stop_b  = ttk.Button(c, text="Stop",  command=self._stop, state="disabled")
        self.start_b.grid(row=5, column=0, pady=4); self.stop_b.grid(row=5, column=1, pady=4)

        # ---------- preview ----------
        fig, ax = plt.subplots(figsize=(5,3))
        ax.set_title("Amplitude vs Samples"); self.line, = ax.plot([], [])
        self.ax = ax; self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)

        self._task=None; self._run=False; self._toggle()

    def _toggle(self, *_):
        sine = self.mode.get()=="Sine"
        state = "normal" if sine else "disabled"
        self.freq_e.config(state=state); self.rate_e.config(state=state)

    def _start(self):
        if self._run: return
        import nidaqmx.constants as C
        try:
            self._task = nidaqmx.Task()
            self._task.ao_channels.add_ao_voltage_chan(self.chan.get(),
                                                       min_val=-10, max_val=10)
            if self.mode.get()=="DC":
                v = self.amp_s.get(); self._task.write(v, auto_start=True)
                buf = np.full(100, v)
            else:
                amp=float(self.amp_s.get())
                freq=float(self.freq_e.get()); rate=float(self.rate_e.get())
                n = int(rate/freq)
                buf = amp*np.sin(2*np.pi*freq*np.arange(n)/rate)
                # Create writer instance directly from nidaqmx 
                writer = AnalogSingleChannelWriter(self._task.out_stream, auto_start=False)
                self._task.timing.cfg_samp_clk_timing(rate,
                        sample_mode=C.AcquisitionType.CONTINUOUS,
                        samps_per_chan=len(buf))
                writer.write_many_sample(buf)
                self._task.start()

            # quick preview
            self.line.set_data(np.arange(buf.size), buf)
            self.ax.relim(); self.ax.autoscale(); self.canvas.draw_idle()

            self._run=True; self.start_b.config(state="disabled")
            self.stop_b.config(state="normal")
        except Exception as e:
            messagebox.showerror("AO Error", str(e)); self._stop()

    def _stop(self):
        if not self._run: return
        if self._task:
            try: self._task.stop(); self._task.close()
            except: pass
            self._task=None
        self._run=False
        self.start_b.config(state="normal"); self.stop_b.config(state="disabled")

    def _close(self): self._stop(); self.destroy()

    # ------------------------------------------------------------------
    # NI-MAX’s native Test-Panel launcher
    # ------------------------------------------------------------------
    def open_ni_test_panel(self):
        """Launch the official NI-MAX Test-Panel window for the DAQ."""
        from nidaqmx.system import System          # local import – keeps start-up fast
        try:
            # DAQ_DEVICE is your global “Dev1”
            System.local().devices[DAQ_DEVICE].open_test_panel()
        except Exception as e:
            messagebox.showerror("NI Device Test Panel",
                                 f"Could not open Test Panel for {DAQ_DEVICE}\n\n{e}")

##########################
# GUI INTERFACE CLASSES  #
##########################
class SABREGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SABRE Control Panel")
        self.geometry("450x550")
        
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

    # ------------------------------------------------------------------
    # NI-MAX style pop-ups
    # ------------------------------------------------------------------
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

        # Full Flow System Button
        self.full_flow_button = ttk.Button(self.advanced_frame, text="Full Flow System", command=self.open_full_flow_system)
        self.full_flow_button.pack(fill="x", pady=2)

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

    def _write_analog_waveform(self, data, rate, continuous=False):
        """Write a numpy 1-D array to AO with hardware timing"""
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

    def cleanup_tasks(self):
        """Clean up any existing DAQ tasks"""
        try:
            system = nidaqmx.system.System.local()
            for task_name in system.tasks:
                try:
                    task = nidaqmx.Task(task_name)
                    if task.is_task_done() is False:
                        task.stop()
                    task.close()
                except:
                    pass
        except Exception as e:
            print(f"Error cleaning up tasks: {e}")

    def test_field(self):
        """Load the polarization method and send it to Ao0"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        print(f"Test Field activated - Loading method from: {self.polarization_method_file}")
        
        def run_test_field():
            try:
                # Load and validate configuration
                with open(self.polarization_method_file, "r") as f:
                    method_config = json.load(f)
                print(f"Loaded configuration: {json.dumps(method_config, indent=2)}")
                
                if not isinstance(method_config, dict):
                    raise ValueError("Invalid configuration format - expected dictionary")

                # Get configuration with defaults
                daq_channel = "Dev1/ao0"  # Default to ao0
                if "daq_channel" in method_config and isinstance(method_config["daq_channel"], str):
                    daq_channel = method_config["daq_channel"]

                voltage_range = {"min": -10.0, "max": 10.0}  # Default range
                if "voltage_range" in method_config and isinstance(method_config["voltage_range"], dict):
                    voltage_range = method_config["voltage_range"]

                initial_voltage = method_config.get("initial_voltage", 0.0)
                final_voltage = method_config.get("final_voltage", 0.0)
                steps = method_config.get("steps", 100)

                # Validate sequences exist
                if "ramp_sequences" not in method_config or not isinstance(method_config["ramp_sequences"], list):
                    raise ValueError("Missing or invalid ramp_sequences configuration")

                # Create task and configure channel
                self.test_task = nidaqmx.Task()
                self.test_task.ao_channels.add_ao_voltage_chan(
                    daq_channel,
                    min_val=voltage_range["min"],
                    max_val=voltage_range["max"]
                )
                
                # Now we can safely write the initial voltage
                self.test_task.write(initial_voltage, auto_start=True)
                self.plotting = True

                # Process sequences
                for sequence in method_config.get("ramp_sequences", []):
                    if self.stop_polarization:
                        break
                    
                    if sequence.get("waveform") == "sine":
                        # Generate sine wave
                        frequency = sequence.get("frequency", 1.0)
                        amplitude = sequence.get("amplitude", 1.0)
                        duration = sequence.get("duration", 1.0)
                        
                        # Calculate number of samples
                        sample_rate = max(frequency * 20, steps / duration)
                        num_samples = int(duration * sample_rate)
                        
                        # Generate time points and voltages
                        t = np.linspace(0, duration, num_samples)
                        dt = duration / num_samples
                        voltages = amplitude * np.sin(2 * np.pi * frequency * t) + initial_voltage

                        # Output the sine wave
                        for v in voltages:
                            if self.stop_polarization:
                                break
                            self.test_task.write(v)
                            time.sleep(dt)
                    else:
                        # Handle linear ramp
                        start_voltage = sequence.get("start_voltage", initial_voltage)
                        end_voltage = sequence.get("end_voltage", final_voltage)
                        duration = sequence.get("duration", method_config.get("ramp_time", 1.0))

                        voltages = np.linspace(start_voltage, end_voltage, steps)
                        dt = duration / steps

                        for v in voltages:
                            if self.stop_polarization:
                                break
                            self.test_task.write(v)
                            time.sleep(dt)

                if not self.stop_polarization:
                    self.test_task.write(final_voltage)

            except Exception as e:
                if not self.stop_polarization:  # Only show error if not intentionally stopped
                    messagebox.showerror("Error", f"Failed to send polarization method to Ao0: {e}")
            finally:
                if self.test_task:
                    try:
                        if self.test_task.is_task_done():
                            self.test_task.write(0.0, auto_start=True)
                        self.test_task.close()
                    except:
                        pass
                self.test_task = None
                self.plotting = False

        # Run the method in a separate thread to prevent freezing
        threading.Thread(target=run_test_field, daemon=True).start()

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
                self.time_window = self.current_method_duration
            else:
                self.time_window = (
                    self.get_value('bubbling_time_entry') +
                    self.get_value('valve_time_entry') * 3 +
                    self.get_value('transfer_time_entry') +
                    self.get_value('recycle_time_entry')
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
        
        # Set axis limits
        self.ax.set_xlim([0, self.time_window])
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
            self.virtual_panel.update_circle_state(0, True)
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
            if not entry.get():  # Check if the field is empty
                missing_params.append(param)
        if missing_params:
            self.show_error_popup(missing_params)
            return

        # Reset plot before starting new experiment
        self.reset_waveform_plot()
        
        if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
            self.virtual_panel = VirtualTestingPanel(self)
        self.virtual_panel.update_circle_state(1, True)
        self.virtual_panel.update_circle_state(2, True)
        self.virtual_panel.start_sequence_bubbling()

        # Run the selected polarization method in a separate thread to avoid blocking the main thread
        threading.Thread(target=self.run_polarization_method, daemon=True).start()

    def run_polarization_method(self):
        """Run the selected polarization method from a .json file"""
        if not self.polarization_method_file:
            messagebox.showerror("Error", "No polarization transfer method selected.")
            return

        try:
            with open(self.polarization_method_file, "r") as f:
                method_config = json.load(f)

            daq_channel = method_config.get("daq_channel", "Dev1/ao0")
            voltage_range = method_config.get("voltage_range", {"min": -10.0, "max": 10.0})
            initial_voltage = method_config.get("initial_voltage", 0.0)
            final_voltage = method_config.get("final_voltage", 0.0)
            steps = method_config.get("steps", 100)

            # Calculate total duration from sequences
            total_duration = 0
            for sequence in method_config.get("ramp_sequences", []):
                total_duration += sequence.get("duration", 0)
            self.current_method_duration = total_duration
            self.plotting = True
            self.stop_polarization = False

            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(
                    daq_channel, 
                    min_val=voltage_range["min"], 
                    max_val=voltage_range["max"]
                )

                # Set initial voltage
                task.write(initial_voltage)
                self.update_waveform_plot(initial_voltage, time.time())

                # Process each sequence
                for sequence in method_config.get("ramp_sequences", []):
                    if self.stop_polarization:
                        break

                    if sequence.get("waveform") == "sine":
                        # Generate sine wave
                        frequency = sequence.get("frequency", 1.0)
                        amplitude = sequence.get("amplitude", 1.0)
                        duration = sequence.get("duration", 1.0)
                        
                        # Calculate number of samples based on frequency and duration
                        sample_rate = max(frequency * 20, steps / duration)  # At least 20 samples per cycle
                        num_samples = int(duration * sample_rate)
                        
                        # Generate time points and voltages
                        t = np.linspace(0, duration, num_samples)
                        dt = duration / num_samples
                        voltages = amplitude * np.sin(2 * np.pi * frequency * t) + initial_voltage

                        # Output the sine wave
                        for v in voltages:
                            if self.stop_polarization:
                                break
                            task.write(v)
                            self.update_waveform_plot(v, time.time())
                            time.sleep(dt)
                    else:
                        # Handle linear ramp sequences
                        start_voltage = sequence.get("start_voltage", initial_voltage)
                        end_voltage = sequence.get("end_voltage", final_voltage)
                        duration = sequence.get("duration", method_config.get("ramp_time", 1.0))

                        voltages = np.linspace(start_voltage, end_voltage, steps)
                        dt = duration / steps

                        for v in voltages:
                            if self.stop_polarization:
                                break
                            task.write(v)
                            self.update_waveform_plot(v, time.time())
                            time.sleep(dt)

                # Set final voltage if not stopped
                if not self.stop_polarization:
                    task.write(final_voltage)
                    self.update_waveform_plot(final_voltage, time.time())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to run polarization method: {e}")
        finally:
            self.set_voltage_to_zero()
            self.plotting = False
            self.stop_polarization = False

    def scram_experiment(self):
        """Emergency stop for all processes"""
        # Stop all ongoing processes
        self.stop_polarization = True
        self.plotting = False
        
        # Clean up tasks in order of importance
        if self.test_task:
            try:
                self.test_task.write(0.0)
                self.test_task.close()
            except:
                pass
            self.test_task = None
        
        # Clean up all remaining tasks
        self.cleanup_tasks()
        
        # Set everything to safe state with new tasks
        try:
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan("Dev1/ao0", min_val=-10.0, max_val=10.0)
                task.write(0.0, auto_start=True)
            print("Reset analog output to 0V")

            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(','.join(DIO_CHANNELS))
                initial_states = [0, 0, 0, 0, 1, 1, 0, 0]
                signal_value = sum(val << idx for idx, val in enumerate(initial_states))
                task.write(signal_value, auto_start=True)
            print("Reset digital outputs to initial state")
        except Exception as e:
            print(f"Error resetting outputs: {e}")

        # Reset GUI elements
        if self.timer_thread:
            self.timer_thread.cancel()
            self.timer_thread = None
        self.timer_label.config(text="00:00:000")
        self.state_label.config(text="State: Idle")

        # Reset virtual panel
        if self.virtual_panel and self.virtual_panel.winfo_exists():
            self.virtual_panel.running = False
            for i in range(8):
                self.virtual_panel.update_circle_state(i, i in [4, 5])
            self.virtual_panel.load_config("Initial_State")

        # Reset plotting
        self.reset_waveform_plot()
        self.start_time = None
        self.time_window = None

        # Play emergency stop sound if enabled
        if self.audio_enabled.get():
            try:
                winsound.Beep(2000, 1000)  # Higher pitch, longer duration for emergency
            except Exception as e:
                print(f"Error playing emergency sound: {e}")

        # Force update
        self.update_idletasks()

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
        """Set the voltage to 0V on 0"""
        try:
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan("Dev1/ao0", min_val=-10.0, max_val=10.0)
                task.write(0.0)
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

############################
# VIRTUAL TESTING CLASSES  #
############################
class VirtualTestingPanel(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Virtual Testing Environment")
        self.setup_panel()

    #-----------------------
    # UI Setup Methods
    #-----------------------
    def setup_panel(self):
        """Initialize panel components"""
        self.photo_path = os.path.join(BASE_DIR, "SABREPhoto.png")
        self.sabre_image = None
        self.hourglasses = {}
        self.running = False
        self.state_mapping = STATE_MAPPING
        
        self.main_canvas = tk.Canvas(self, width=750, height=500)
        self.main_canvas.pack(pady=10)
        
        self.create_ui()
        self.set_initial_states()

    def create_ui(self):
        """Setup all UI components"""
        # Load and display image
        self.display_image()
        
        # Create hourglass indicators
        self.create_hourglasses()
        
        # Create state label
        self.state_label = ttk.Label(self, text="Current State: Initial", font=('Arial', 12))
        self.state_label.pack(pady=10)

        # Add visual test buttons
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Test Activation Sequence", 
                  command=self.visual_activation_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Bubbling Sequence", 
                  command=self.visual_bubbling_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Full Flow System", 
                  command=self.open_full_flow_system).pack(side=tk.LEFT, padx=5)  # New button
        ttk.Button(button_frame, text="Stop", 
                  command=self.stop_visual_sequence).pack(side=tk.LEFT, padx=5)

    def open_full_flow_system(self):
        """Open the Full Flow System page"""
        FullFlowSystem(self)

    #-----------------------
    # State Management Methods
    #-----------------------
    def load_config(self, state):
        """Load and apply configuration from file."""
        try:
            config_file = os.path.join(CONFIG_DIR, f"{state}.json")
            
            # Check if config file exists
            if not os.path.exists(config_file):
                print(f"Configuration file not found: {config_file}")
                return False

            # Load config data
            with open(config_file, "r") as file:
                config_data = json.load(file)

            # Update state labels
            human_readable_state = self.state_mapping.get(state, "Unknown State")
            self.parent.state_label.config(text=f"State: {human_readable_state}")
            self.state_label.config(text=f"Current State: {state}")

            # Update DIO states
            dio_states = {f"DIO{i}": config_data.get(f"DIO{i}", "LOW").upper() == "HIGH" for i in range(8)}
            for dio, is_active in dio_states.items():
                self.update_circle_state(dio, is_active)

            # Send signals to DAQ
            self.parent.send_daq_signals(dio_states)

            return True

        except Exception as error:
            print(f"Error loading state {state}: {error}")
            return False

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

    #-----------------------
    # Sequence Control Methods
    #-----------------------
    def start_sequence(self):
        """Start the experiment sequence"""
        if self.running:
            return
        self.running = True

        def run_experiment_sequence():
            try:
                valve_duration = self.parent.get_value('valve_time_entry')
                injection_duration = self.parent.get_value('injection_time_entry')
                degassing_duration = self.parent.get_value('degassing_time_entry')
                activation_duration = self.parent.get_value('activation_time_entry')

                state_sequence = [
                    ("Initial_State", valve_duration),
                    ("Injection_State_Start", injection_duration),
                    ("Degassing", degassing_duration),
                    ("Activation_State_Initial", activation_duration),
                    ("Activation_State_Final", valve_duration),
                    ("Initial_State", None)
                ]

                total_time = sum(duration for _, duration in state_sequence if duration)
                self.parent.start_timer(total_time)

                for state, duration in state_sequence:
                    if not self.running:
                        break
                    if self.load_config(state) and duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and self.running:
                            time.sleep(0.1)

            except Exception as error:
                print(f"Error in experiment sequence: {error}")
            finally:
                self.running = False

        threading.Thread(target=run_experiment_sequence, daemon=True).start()

    def start_sequence_bubbling(self):
        """Start the bubbling sequence"""
        if self.running:
            return
        self.running = True

        def run_experiment_sequence_bubbling():
            try:
                valve_duration = self.parent.get_value('valve_time_entry')
                bubbling_time = self.parent.get_value('bubbling_time_entry')
                transfer_time = self.parent.get_value('transfer_time_entry')
                recycle_time = self.parent.get_value('recycle_time_entry')

                state_sequence = [
                    ("Bubbling_State_Initial", bubbling_time),
                    ("Bubbling_State_Final", valve_duration),
                    ("Transfer_Initial", valve_duration),
                    ("Transfer_Final", valve_duration),
                    ("Recycle", recycle_time),
                    ("Initial_State", None)
                ]

                total_time = sum(duration for _, duration in state_sequence if duration)
                self.parent.start_timer(total_time)

                for state, duration in state_sequence:
                    if not self.running:
                        break
                    if self.load_config(state) and duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and self.running:
                            time.sleep(0.1)

            except Exception as error:
                print(f"Error in experiment sequence: {error}")
            finally:
                self.running = False

        threading.Thread(target=run_experiment_sequence_bubbling, daemon=True).start()

    def stop_sequence(self):
        """Stop the running sequence"""
        self.running = False
        self.load_config("Initial_State")

    def visual_activation_sequence(self):
        """Run visual-only activation sequence"""
        if self.running:
            return
        self.running = True

        def run_visual_sequence():
            try:
                valve_duration = self.parent.get_value('valve_time_entry')
                injection_duration = self.parent.get_value('injection_time_entry')
                degassing_duration = self.parent.get_value('degassing_time_entry')
                activation_duration = self.parent.get_value('activation_time_entry')

                state_sequence = [
                    ("Initial_State", valve_duration),
                    ("Injection_State_Start", injection_duration),
                    ("Degassing", degassing_duration),
                    ("Activation_State_Initial", activation_duration),
                    ("Activation_State_Final", valve_duration),
                    ("Initial_State", None)
                ]

                total_time = sum(duration for _, duration in state_sequence if duration)
                self.parent.start_timer(total_time)

                for state, duration in state_sequence:
                    if not self.running:
                        break
                    if self.load_config_visual(state) and duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and self.running:
                            time.sleep(0.1)

            except Exception as error:
                print(f"Error in visual activation sequence: {error}")
            finally:
                self.running = False

        threading.Thread(target=run_visual_sequence, daemon=True).start()

    def visual_bubbling_sequence(self):
        """Run visual-only bubbling sequence"""
        if self.running:
            return
        self.running = True

        def run_visual_bubbling():
            try:
                valve_duration = self.parent.get_value('valve_time_entry')
                bubbling_time = self.parent.get_value('bubbling_time_entry')
                transfer_time = self.parent.get_value('transfer_time_entry')
                recycle_time = self.parent.get_value('recycle_time_entry')

                state_sequence = [
                    ("Bubbling_State_Initial", bubbling_time),
                    ("Bubbling_State_Final", valve_duration),
                    ("Transfer_Initial", valve_duration),
                    ("Transfer_Final", valve_duration),
                    ("Recycle", recycle_time),
                    ("Initial_State", None)
                ]

                total_time = sum(duration for _, duration in state_sequence if duration)
                self.parent.start_timer(total_time)

                for state, duration in state_sequence:
                    if not self.running:
                        break
                    if self.load_config_visual(state) and duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and self.running:
                            time.sleep(0.1)

            except Exception as error:
                print(f"Error in visual bubbling sequence: {error}")
            finally:
                self.running = False

        threading.Thread(target=run_visual_bubbling, daemon=True).start()

    def stop_sequence(self):
        """Stop the running sequence"""
        self.running = False
        self.load_config_visual("Initial_State")

    def set_initial_states(self):
        """Set initial states for hourglasses"""
        initial_states = [False, False, False, False, True, True, False, False]  # LOW, LOW, LOW, LOW, HIGH, HIGH, LOW, LOW
        for i, state in enumerate(initial_states):
            self.update_hourglass_state(i, state)

    def create_hourglasses(self):
        """Create hourglass shapes at specific positions"""
        hourglass_positions = [
            (545, 352, True),
            (321, 282, False),
            (369, 206, True),
            (264, 205, True),
            (537, 158, False),
            (204, 101, True),
            (204, 38, True),
            (545, 281, True)
        ]
        
        width, height = 50, 50
        
        for i, (x, y, sideways) in enumerate(hourglass_positions):
            self.create_single_hourglass(i, x, y, width, height, sideways)

    def create_single_hourglass(self, index, x, y, width, height, sideways):
        """Create a single hourglass shape with label"""
        if sideways:
            points = [
                x, y,                # Top left
                x, y + height,       # Bottom left
                x + width/2, y + height/2,  # Middle bottom
                x + width, y + height,    # Bottom right
                x + width, y,        # Top right
                x + width/2, y + height/2   # Middle top
            ]
        else:
            points = [
                x, y,                # Top left
                x + width, y,        # Top right
                x + width/2, y + height/2,  # Middle right
                x + width, y + height,    # Bottom right
                x, y + height,       # Bottom left
                x + width/2, y + height/2   # Middle left
            ]
        
        hourglass = self.main_canvas.create_polygon(
            points, 
            outline='black',
            fill='red',
            width=2
        )
        
        self.hourglasses[f"DIO{index}"] = hourglass

    def display_image(self):
        """Display the SABRE system image on the canvas"""
        try:
            img = Image.open(self.photo_path)
            img = img.resize((750, 500), Image.Resampling.LANCZOS)
            self.sabre_image = ImageTk.PhotoImage(img)
            self.main_canvas.create_image(0, 0, image=self.sabre_image, anchor='nw')
        except Exception as e:
            print(f"Error loading image: {e}")

    def update_hourglass_state(self, dio_identifier, is_active):
        """Update the hourglass color based on the digital I/O state"""
        if isinstance(dio_identifier, int):
            dio_identifier = f"DIO{dio_identifier}"
        if dio_identifier in self.hourglasses:
            color = 'green' if is_active else 'red'
            self.main_canvas.itemconfig(self.hourglasses[dio_identifier], fill=color)

    def update_circle_state(self, dio_identifier, is_active):
        """Redirect circle updates to hourglass updates"""
        self.update_hourglass_state(dio_identifier, is_active)

#-----------------------
# Full Flow System Class
#-----------------------
class FullFlowSystem(tk.Toplevel):
    def __init__(self, parent):
        
        super().__init__(parent)
        self.parent = parent
        self.title("Full Flow System")
        
        # Initialize drag and resize variables
        self.selected_hourglass = None
        self.resize_handle = None
        self.drag_data = {"x": 0, "y": 0}
        
        self.setup_full_flow_system()

    def setup_full_flow_system(self):
        """Initialize Full Flow System components"""
        self.photo_path = os.path.join(BASE_DIR, "SABREFullFlow.png")
        self.sabre_image = None
        self.hourglasses = {}

        # Create canvas
        self.main_canvas = tk.Canvas(self, width=900, height=600)
        self.main_canvas.pack(pady=10)

        # Display background image first
        self.display_image()

        # Initial hourglass positions - coordinates and orientations based on the exact positions
        hourglass_positions = [
            (196, 140, True),   # DIO0 - horizontal
            (586, 316, False),  # DIO1 - vertical
            (559, 286, True),   # DIO2 - horizontal
            (613, 286, True),   # DIO3 - horizontal
            (494, 260, False),  # DIO4 - vertical 
            (575, 234, True),   # DIO5 - horizontal
            (575, 204, True),   # DIO6 - horizontal
            (223, 303, False)   # DIO7 - vertical
        ]
        
        # Create hourglasses with exact dimensions
        for i, (x, y, sideways) in enumerate(hourglass_positions):
            self.create_single_hourglass(i, x, y, 30, 30, sideways)

        # Bind mouse events after creating hourglasses
        self.main_canvas.tag_bind("hourglass", "<Button-1>", self.on_hourglass_click)
        self.main_canvas.tag_bind("hourglass", "<B1-Motion>", self.on_hourglass_drag)
        self.main_canvas.tag_bind("resize_handle", "<Button-1>", self.on_resize_start)
        self.main_canvas.tag_bind("resize_handle", "<B1-Motion>", self.on_resize_drag)
        self.main_canvas.tag_bind("hourglass", "<ButtonRelease-1>", self.on_release)
        self.main_canvas.tag_bind("resize_handle", "<ButtonRelease-1>", self.on_release)
        
        self.set_initial_states()
        self.print_hourglass_positions()

    def display_image(self):
        """Display the SABRE Full Flow System image on the canvas"""
        try:
            img = Image.open(self.photo_path)
            # Calculate new dimensions while preserving aspect ratio
            target_width = 900
            target_height = 600
            img_width, img_height = img.size
            aspect_ratio = img_width / img_height
            
            if target_width / target_height > aspect_ratio:
                new_width = int(target_height * aspect_ratio)
                new_height = target_height
            else:
                new_width = target_width
                new_height = int(target_width / aspect_ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.sabre_image = ImageTk.PhotoImage(img)
            
            # Center the image on the canvas
            x = (target_width - new_width) // 2
            y = (target_height - new_height) // 2
            self.main_canvas.create_image(x, y, image=self.sabre_image, anchor='nw')
            
        except Exception as e:
            print(f"Error loading image: {e}")

    # Add new methods for drag and resize functionality
    def on_hourglass_click(self, event):
        self.selected_hourglass = self.main_canvas.find_closest(event.x, event.y)[0]
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_hourglass_drag(self, event):
        if not self.selected_hourglass:
            return
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.main_canvas.move(self.selected_hourglass, dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_resize_start(self, event):
        self.resize_handle = self.main_canvas.find_closest(event.x, event.y)[0]
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_resize_drag(self, event):
        if not self.resize_handle:
            return
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        # Update hourglass size based on resize handle movement
        coords = self.main_canvas.coords(self.resize_handle)
        # Update coordinates based on resize logic
        self.main_canvas.coords(self.resize_handle, *coords)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_release(self, event):
        self.selected_hourglass = None
        self.resize_handle = None
        self.print_hourglass_positions()

    def print_hourglass_positions(self):
        """Print current positions of all hourglasses"""
        for i in range(8):
            if f"DIO{i}" in self.hourglasses:
                coords = self.main_canvas.coords(self.hourglasses[f"DIO{i}"])
                print(f"DIO{i} position: {coords}")

    def set_initial_states(self):
        """Set initial states for hourglasses"""
        initial_states = [False, False, False, False, True, True, False, False]  # Example states
        for i, state in enumerate(initial_states):
            self.update_hourglass_state(i, state)

    def create_single_hourglass(self, index, x, y, width, height, sideways):
        """Create a single hourglass shape with label"""
        if sideways:
            points = [
                x, y - height/2,           # Top left
                x, y + height/2,           # Bottom left
                x + width/2, y,            # Middle bottom
                x + width, y + height/2,    # Bottom right
                x + width, y - height/2,    # Top right
                x + width/2, y             # Middle top
            ]
        else:
            points = [
                x - width/2, y,            # Top left
                x + width/2, y,            # Top right
                x, y + height/2,           # Middle right
                x + width/2, y + height,   # Bottom right
                x - width/2, y + height,   # Bottom left
                x, y + height/2            # Middle left
            ]
        
        hourglass = self.main_canvas.create_polygon(
            points, 
            outline='black',
            fill='red',
            width=2,
            tags=("hourglass",)
        )
        
        self.hourglasses[f"DIO{index}"] = hourglass

    def update_hourglass_state(self, dio_identifier, is_active):
        """Update the hourglass color based on the digital I/O state"""
        if isinstance(dio_identifier, int):
            dio_identifier = f"DIO{dio_identifier}"
        if dio_identifier in self.hourglasses:
            color = 'green' if is_active else 'red'
            self.main_canvas.itemconfig(self.hourglasses[dio_identifier], fill=color)

    def load_config(self, state):
        """Load and apply configuration from file."""
        try:
            config_file = os.path.join(CONFIG_DIR, f"{state}.json")
            
            if not os.path.exists(config_file):
                print(f"Configuration file not found: {config_file}")
                return False

            with open(config_file, "r") as file:
                config_data = json.load(file)

            # Update hourglass colors
            dio_states = {f"DIO{i}": config_data.get(f"DIO{i}", "LOW").upper() == "HIGH" for i in range(8)}
            for dio, is_active in dio_states.items():
                self.update_hourglass_state(dio, is_active)

            return True

        except Exception as error:
            print(f"Error loading state {state}: {error}")
            return False



############################
# MAIN PROGRAM ENTRY      #
############################
if __name__ == "__main__":
    app = SABREGUI()
    app.mainloop()