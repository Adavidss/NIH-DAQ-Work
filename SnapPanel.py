import json
import math
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------- NI-DAQmx imports (install with: pip install nidaqmx) ----------
try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType, Edge
    NIDAQMX_AVAILABLE = True
    print("NI-DAQmx available")
except ImportError:
    NIDAQMX_AVAILABLE = False
    print("NI-DAQmx not available - using simulation mode")

# ------------ default parameters -------------
DEFAULTS = {
    "coilcalibration": 6.487,        # uT / V  – coil B1 field per volt
    "B1_SLIC": 1.8,                  # uT       – CW SLIC B1 amplitude
    "f_SLIC": 535.25,                # Hz       – SLIC carrier frequency
    "TimeSLIC_approx": 40,          # s        – requested CW duration (rounded later)
    "df": 50,                        # Hz       – linear sweep range during 90° pulse
    "Length90Pulse": 4,              # s        – **full** triangular width (rise+fall)
    "B1_Pulse": 4,                   # uT       – peak of triangular 90° pulse
    "sample_rate": 10_000,           # Sa / s   – samples per second
    "ao_channel": "ao1",             # Analog output channel
}

UNITS = {
    "coilcalibration": "µT / V",
    "B1_SLIC":        "µT",
    "f_SLIC":         "Hz",
    "TimeSLIC_approx":"s",
    "df":             "Hz",
    "Length90Pulse":  "s",
    "B1_Pulse":       "µT",
    "sample_rate":    "Sa / s",
    "ao_channel":     "",
}

SAVE_ROOT = Path(
    r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods"
)
SAVE_ROOT.mkdir(parents=True, exist_ok=True)

# ------------ Proper DAQ implementation ----------------------
def send_sequence_to_ao1(
    json_path: Path,
    duration_s: float,
    sample_rate: int,
    ao_channel: str,
    stop_event: threading.Event,
):
    """
    Properly configured NI-DAQmx finite waveform output with accurate timing.
    """
    sequence_start = time.time()  # Add overall timing start
    try:
        # Load waveform data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        waveform = np.array(data['data'], dtype=np.float64)
        n_samples = len(waveform)
        expected_duration = n_samples / sample_rate
        
        print(f"[DAQ] Loading {json_path.name}")
        print(f"[DAQ] Waveform: {n_samples} samples @ {sample_rate/1_000:.1f} kSa/s")
        print(f"[DAQ] Expected duration: {expected_duration:.5f} s")
        
        if not NIDAQMX_AVAILABLE:
            # Simulation mode
            print("[DAQ] SIMULATION MODE - NI-DAQmx not available")
            t0 = time.perf_counter()
            while not stop_event.is_set() and (time.perf_counter() - t0) < expected_duration:
                time.sleep(0.05)
            print(f"[DAQ] Simulation completed in {time.perf_counter() - t0:.3f} s")
            return
        
        # Create and configure DAQ task
        channel_name = f"Dev1/{ao_channel}"
        
        with nidaqmx.Task() as task:
            # Create analog output channel (fixed method name)
            task.ao_channels.add_ao_voltage_chan(
                channel_name,
                min_val=-10.0,
                max_val=10.0
            )
            
            # CRITICAL: Configure finite sample timing (fixed parameter name)
            task.timing.cfg_samp_clk_timing(
                rate=sample_rate,
                source='',  # Use internal clock
                active_edge=Edge.RISING,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=n_samples  # Fixed parameter name
            )
            
            # Get the actual sample rate (may be coerced by hardware)
            actual_rate = task.timing.samp_clk_rate
            actual_duration = n_samples / actual_rate
            
            if abs(actual_rate - sample_rate) > 1.0:
                print(f"[DAQ] WARNING: Sample rate coerced from {sample_rate} to {actual_rate:.1f} Hz")
                print(f"[DAQ] Duration adjusted from {expected_duration:.5f} to {actual_duration:.5f} s")
            
            # Write the entire waveform to the buffer
            print(f"[DAQ] Writing {n_samples} samples to buffer...")
            samples_written = task.write(waveform, auto_start=False)
            
            if samples_written != n_samples:
                raise RuntimeError(f"Expected to write {n_samples} samples, but wrote {samples_written}")
            
            print(f"[DAQ] Buffer loaded successfully. Starting finite generation...")
            
            # Start the task
            start_time = time.perf_counter()
            task.start()
            
            # Wait for completion or stop signal
            # For finite tasks, we need to wait for the exact duration
            while not stop_event.is_set():
                elapsed = time.perf_counter() - start_time
                
                # Check if task is still running
                if not task.is_task_done():
                    if elapsed < actual_duration + 1.0:  # Add 1s tolerance
                        time.sleep(0.01)  # Short sleep to avoid busy waiting
                        continue
                    else:
                        print("[DAQ] WARNING: Task taking longer than expected")
                        break
                else:
                    # Task completed normally
                    break
            
            elapsed_time = time.perf_counter() - start_time
            
            # Stop the task if still running
            if not task.is_task_done():
                task.stop()
                print(f"[DAQ] Task stopped manually after {elapsed_time:.3f} s")
            else:
                print(f"[DAQ] Task completed successfully in {elapsed_time:.5f} s")
                print(f"[DAQ] Expected: {actual_duration:.5f} s, Actual: {elapsed_time:.5f} s")
                
                # Check timing accuracy
                timing_error = abs(elapsed_time - actual_duration)
                if timing_error > 0.001:  # 1ms tolerance
                    print(f"[DAQ] WARNING: Timing error of {timing_error*1000:.1f} ms")
                else:
                    print("[DAQ] Timing within specification")
        
        # Add overall sequence completion timing        
        total_duration = time.time() - sequence_start
        print(f"[DAQ] Total sequence execution time: {total_duration:.3f} seconds")
            
    except Exception as e:
        print(f"[DAQ] ERROR: {e}")
        import traceback
        traceback.print_exc()


# ============ GUI ===========================
class SLICSequenceControl(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("SLIC-SABRE Sequence Control")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.geometry("900x700")

        self.stop_event = threading.Event()
        self.play_thread: threading.Thread | None = None
        self.current_json: Path | None = None
        self.waveform: np.ndarray | None = None
        self.time_axis: np.ndarray | None = None
        
        # Add timer variables
        self.countdown_running = False
        self.countdown_end_time = None
        self.after_id = None

        self.make_widgets()

    # -------- layout --------
    def make_widgets(self):
        # Parameters frame
        param_frame = ttk.LabelFrame(self, text="Sequence Parameters")
        param_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        self.vars: dict[str, tk.StringVar] = {}
        for i, (key, val) in enumerate(DEFAULTS.items()):
            ttk.Label(param_frame, text=key).grid(row=i, column=0, sticky="e", padx=5)
            v = tk.StringVar(value=str(val))
            self.vars[key] = v
            if key == "ao_channel":
                # Create dropdown for AO channels
                combo = ttk.Combobox(param_frame, textvariable=v, width=12, state="readonly")
                combo['values'] = ["ao0", "ao1", "ao2", "ao3"]
                combo.grid(row=i, column=1, sticky="w", padx=5)
            else:
                entry = ttk.Entry(param_frame, textvariable=v, width=15)
                entry.grid(row=i, column=1, sticky="w", padx=5)
            ttk.Label(param_frame, text=UNITS[key]).grid(row=i, column=2, sticky="w", padx=(4, 0))

        # Status frame
        status_frame = ttk.LabelFrame(self, text="Timing Status")
        status_frame.grid(row=1, column=0, padx=6, pady=6, sticky="ew")
        
        self.status_text = tk.Text(status_frame, height=4, width=60)
        self.status_text.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.status_text.configure(yscrollcommand=scrollbar.set)
        status_frame.grid_columnconfigure(0, weight=1)

        # Add countdown timer frame after status frame
        countdown_frame = ttk.LabelFrame(self, text="Countdown Timer")
        countdown_frame.grid(row=2, column=0, padx=6, pady=6, sticky="ew")
        
        self.countdown_label = ttk.Label(countdown_frame, text="00:00.000", 
                                       font=("Courier", 24, "bold"))
        self.countdown_label.pack(pady=5)

        # Move button frame to row 3
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0, pady=4, sticky="ew")
        
        buttons = [
            ("Generate Sequence", self.generate_sequence),
            ("Send Sequence", self.send_sequence),
            ("Look at Sequence", self.look_at_sequence),
            ("Stop Sequence", self.stop_sequence),
            ("Test DAQ", self.test_daq)
        ]
        
        for i, (text, cmd) in enumerate(buttons):
            ttk.Button(btn_frame, text=text, command=cmd).grid(row=0, column=i, padx=4, sticky="ew")
            btn_frame.grid_columnconfigure(i, weight=1)

        # Plot frame
        fig, ax = plt.subplots(figsize=(10, 4))
        self.ax = ax
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.get_tk_widget().grid(row=4, column=0, sticky="nsew", padx=6, pady=6)
        
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def log_status(self, message):
        """Add message to status text widget"""
        self.status_text.insert(tk.END, f"{time.strftime('%H:%M:%S')}: {message}\n")
        self.status_text.see(tk.END)
        self.update_idletasks()

    # -------- sequence math --------
    def build_waveform(self):
        p = {k: float(v.get()) if k not in ['ao_channel'] else v.get() 
             for k, v in self.vars.items()}
        sr = int(p["sample_rate"])
        dt = 1.0 / sr

        # ---- CW part: integer number of cycles ----------------------
        cycles_cw = math.floor(p["TimeSLIC_approx"] * p["f_SLIC"])
        t_cw_exact = cycles_cw / p["f_SLIC"]          # s
        n_cw = int(round(t_cw_exact * sr))            # samples

        # ---- 90° triangular pulse -------------------
        n_pulse = int(round(p["Length90Pulse"] * sr))
        t_pulse_exact = n_pulse / sr                   # s (quantised)

        # ---- total timing ------------------------------------------
        n_samples = n_cw + n_pulse
        total_time = n_samples / sr

        # ---- time axis ---------------------------------------------
        t = np.arange(n_samples, dtype=np.float64) / sr

        # ---- voltages ---------------------------------------------
        coilcal = p["coilcalibration"]
        v_cw    = (p["B1_SLIC"] / coilcal)
        v_peak  = (p["B1_Pulse"] / coilcal)

        wf = np.zeros(n_samples, dtype=np.float64)

        # ---- CW section with proper phase tracking ----------------
        phase_cw = 2 * np.pi * p["f_SLIC"] * t[:n_cw]
        wf[:n_cw] = v_cw * np.sin(phase_cw)
        
        # Phase at the end of CW section for continuity
        phase_end_cw = phase_cw[-1] if n_cw > 0 else 0.0

        # ---- Single triangular pulse with frequency sweep ----------
        t_pulse = t[n_cw:] - t[n_cw]  # Reset time for pulse section
        
        # Linear envelope from peak to 0
        env_pulse = v_peak * (1.0 - t_pulse / t_pulse_exact)
        
        # Frequency sweep from f_SLIC to f_SLIC + df 
        f_pulse = p["f_SLIC"] + p["df"] * (t_pulse / t_pulse_exact)
        
        # Integrate frequency to get phase
        phase_pulse = np.zeros_like(t_pulse)
        if len(t_pulse) > 1:
            phase_pulse[1:] = np.cumsum(0.5 * (f_pulse[:-1] + f_pulse[1:]) * np.diff(t_pulse))
        phase_pulse = 2 * np.pi * phase_pulse + phase_end_cw
        
        wf[n_cw:] = env_pulse * np.sin(phase_pulse)

        meta = {
            "sample_rate":       sr,
            "total_time":        total_time,
            "TimeSLIC_exact":    t_cw_exact,
            "Length90Pulse":     t_pulse_exact,
            "f_SLIC":            p["f_SLIC"],
            "df":                p["df"],
            "n_samples":         n_samples,
            "requested_TimeSLIC": p["TimeSLIC_approx"],
            "units":             UNITS,
            "cw_cycles":         cycles_cw,
            "pulse_samples":     n_pulse,
            "ao_channel":        p["ao_channel"],
            "timing_errors": {
                "cw_error_s": t_cw_exact - p["TimeSLIC_approx"],
                "pulse_error_s": t_pulse_exact - p["Length90Pulse"],
            },
            "voltage_range": {
                "min_v": float(np.min(wf)),
                "max_v": float(np.max(wf)),
                "rms_v": float(np.sqrt(np.mean(wf**2)))
            }
        }

        # Log timing information
        self.log_status(f"Waveform calculated: {n_samples} samples, {total_time:.5f} s")
        self.log_status(f"CW: {cycles_cw} cycles, {t_cw_exact:.5f} s")
        self.log_status(f"Pulse: {t_pulse_exact:.5f} s")

        self.waveform, self.time_axis = wf, t
        return wf, t, total_time, meta

    # -------- button callbacks --------
    def test_daq(self):
        """Test DAQ availability and device"""
        try:
            ao_channel = self.vars["ao_channel"].get()
            
            if not NIDAQMX_AVAILABLE:
                self.log_status("NI-DAQmx not available - install with: pip install nidaqmx")
                return
            
            # Test device connection
            import nidaqmx.system
            system = nidaqmx.system.System.local()
            devices = [device.name for device in system.devices]
            
            self.log_status(f"Available devices: {devices}")
            
            if "Dev1" not in devices:
                self.log_status(f"ERROR: Device 'Dev1' not found")
                return
                
            # Test channel
            device = system.devices["Dev1"]
            channel_name = f"Dev1/{ao_channel}"
            
            # Test channel by attempting to create a task
            try:
                with nidaqmx.Task() as task:
                    task.ao_channels.add_ao_voltage_chan(  # Fixed method name here too
                        channel_name,
                        min_val=-10.0,
                        max_val=10.0
                    )
                    task.write(0.0)  # Write 0V to test
                    self.log_status(f"Successfully tested channel: {channel_name}")
            except Exception as channel_error:
                self.log_status(f"ERROR: Channel '{channel_name}' test failed: {channel_error}")
                return
                
            self.log_status(f"SUCCESS: Device and channel verified")
                
        except Exception as e:
            self.log_status(f"DAQ test failed: {e}")

    def generate_sequence(self):
        try:
            wf, _, dur, meta = self.build_waveform()
        except ValueError as e:
            messagebox.showerror("Input error", str(e))
            return
            
        filepath = filedialog.asksaveasfilename(
            parent=self, initialdir=SAVE_ROOT, defaultextension=".json",
            filetypes=[("JSON files", "*.json")], title="Save SLIC sequence as…"
        )
        if not filepath:
            return
            
        self.write_json(Path(filepath), wf, meta)
        self.plot_waveform()
        
        # Show timing information
        timing_info = (
            f"Sequence saved to:\n{filepath}\n\n"
            f"Timing Details:\n"
            f"Requested CW time: {meta['requested_TimeSLIC']:.3f} s\n"
            f"Actual CW time: {meta['TimeSLIC_exact']:.5f} s\n"
            f"CW cycles: {meta['cw_cycles']}\n"
            f"Pulse duration: {meta['Length90Pulse']:.5f} s\n"
            f"Total duration: {meta['total_time']:.5f} s\n"
            f"Total samples: {meta['n_samples']}\n"
            f"Voltage range: {meta['voltage_range']['min_v']:.3f} to {meta['voltage_range']['max_v']:.3f} V"
        )
        messagebox.showinfo("Saved", timing_info)
        self.current_json = Path(filepath)
        self.log_status(f"Sequence saved: {filepath}")

    def start_countdown(self, duration_s):
        """Start countdown timer for given duration in seconds"""
        self.countdown_end_time = time.time() + duration_s
        self.countdown_running = True
        self.update_countdown()

    def update_countdown(self):
        """Update countdown display every millisecond"""
        if not self.countdown_running:
            return
            
        remaining = max(0, self.countdown_end_time - time.time())
        
        if remaining > 0:
            # Format time as MM:SS.mmm
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining % 1) * 1000)
            
            self.countdown_label.config(
                text=f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            )
            
            # Schedule next update in 1ms
            self.after_id = self.after(1, self.update_countdown)
        else:
            self.countdown_label.config(text="00:00.000")
            self.countdown_running = False

    def stop_countdown(self):
        """Stop the countdown timer"""
        self.countdown_running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def send_sequence(self):
        if self.play_thread and self.play_thread.is_alive():
            messagebox.showwarning("Busy", "Sequence already running.")
            return
            
        try:
            wf, _, dur, meta = self.build_waveform()
            tmp_path = SAVE_ROOT / "SLIC_TEMP_FILE.json"
            self.write_json(tmp_path, wf, meta)
            self.plot_waveform()

            ao_channel = meta["ao_channel"]
            sample_rate = meta["sample_rate"]

            self.log_status("Starting sequence transmission...")
            
            self.stop_event.clear()
            # Start countdown timer
            self.start_countdown(dur)
            
            self.play_thread = threading.Thread(
                target=send_sequence_to_ao1,
                args=(tmp_path, dur, sample_rate, ao_channel, self.stop_event),
                daemon=True,
            )
            self.play_thread.start()
            self.current_json = tmp_path

            messagebox.showinfo(
                "Running",
                f"Sequence running:\n"
                f"Device: Dev1/{ao_channel}\n"
                f"Duration: {dur:.5f} s\n"
                f"Sample rate: {sample_rate/1_000:.1f} kSa/s\n"
                f"Total samples: {meta['n_samples']}\n"
                f"CW cycles: {meta['cw_cycles']}\n"
                f"CW time: {meta['TimeSLIC_exact']:.5f} s",
            )
        except Exception as e:
            self.log_status(f"ERROR: {e}")
            messagebox.showerror("Error", f"Failed to start sequence:\n{e}")

    def look_at_sequence(self):
        self.build_waveform()
        self.plot_waveform()

    def stop_sequence(self):
        self.stop_event.set()
        self.stop_countdown()  # Stop countdown when sequence is stopped
        self.log_status("Stop signal issued")
        messagebox.showinfo("Stop", "Stop signal issued.")

    # -------- utilities --------
    @staticmethod
    def write_json(path: Path, data: np.ndarray, params: dict):
        with open(path, "w") as f:
            json.dump(
                {
                    "type": "SLIC_sequence",
                    "params": {**params, "SamplingRate": params["sample_rate"]},
                    "data": data.tolist(),
                },
                f,
                indent=2,
            )

    def plot_waveform(self):
        if self.waveform is None:
            return
            
        self.ax.cla()
        
        # Plot full waveform
        self.ax.plot(self.time_axis, self.waveform, 'b-', linewidth=0.8, label='Waveform')
        
        # Add section boundaries
        try:
            wf, _, _, meta = self.build_waveform()
            cw_end_time = meta['TimeSLIC_exact']
            total_time = meta['total_time']
            
            self.ax.axvline(x=cw_end_time, color='red', linestyle='--', alpha=0.7, 
                          label=f'CW end ({cw_end_time:.3f} s)')
            
            # Add voltage range info
            v_min, v_max = meta['voltage_range']['min_v'], meta['voltage_range']['max_v']
            self.ax.set_ylim(v_min * 1.1, v_max * 1.1)
            
            self.ax.set_title(f'SLIC Waveform - Duration: {total_time:.3f} s, Range: {v_min:.2f} to {v_max:.2f} V')
            
        except:
            self.ax.set_title('SLIC Waveform')
            
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()
        
        self.canvas.draw_idle()

    # -------- housekeeping --------
    def on_close(self):
        self.stop_event.set()
        self.stop_countdown()  # Clean up countdown timer
        self.destroy()


# ------------- run -------------
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()                      # hide empty root
    SLICSequenceControl(root)
    root.mainloop()