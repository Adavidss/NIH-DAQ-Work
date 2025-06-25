import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import nidaqmx
from nidaqmx.constants import AcquisitionType, TerminalConfiguration
from nidaqmx.stream_writers import AnalogSingleChannelWriter
import numpy as np

from Constants_Paths import DAQ_DEVICE

# ==== MINI TEST PANELS (AI / AO) ============================
class AnalogInputPanel(tk.Frame):
    """Very small live-scope for a single AI channel (looks like NI-MAX)."""
    def __init__(self, parent, embedded=False):
        super().__init__(parent)
        self.embedded = embedded
        
        if not embedded:
            # Create a Toplevel window to host this panel
            self.toplevel = tk.Toplevel(parent)
            self.toplevel.title(f"AI Test Panel : {DAQ_DEVICE}")
            self.toplevel.protocol("WM_DELETE_WINDOW", self._close)
            self.master = self.toplevel
            # Move the frame into the Toplevel
            self.pack(fill="both", expand=True)
        else:
            # Frame is already in the parent
            self.toplevel = None
        
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
            print("Actual NI rate:", self._task.timing.samp_clk_rate, "Sa/s")

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

    def _close(self): 
        self._stop()
        if not self.embedded and hasattr(self, 'toplevel'):
            self.toplevel.destroy()
        else:
            self.destroy()


class AnalogOutputPanel(tk.Frame):
    """Very small generator for one AO channel."""
    def __init__(self, parent, embedded=False):
        super().__init__(parent)
        self.embedded = embedded
        
        if not embedded:
            # Create a Toplevel window to host this panel
            self.toplevel = tk.Toplevel(parent)
            self.toplevel.title(f"AO Test Panel : {DAQ_DEVICE}")
            self.toplevel.protocol("WM_DELETE_WINDOW", self._close)
            self.master = self.toplevel
            # Move the frame into the Toplevel
            self.pack(fill="both", expand=True)
        else:
            # Frame is already in the parent
            self.toplevel = None

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
                freq=float(self.freq_e.get()) 
                rate=float(self.rate_e.get())
                n = int(rate/freq)
                buf = amp*np.sin(2*np.pi*freq*np.arange(n)/rate)
                writer = AnalogSingleChannelWriter(self._task.out_stream, auto_start=False)
                self._task.timing.cfg_samp_clk_timing(rate,
                        sample_mode=C.AcquisitionType.CONTINUOUS,
                        samps_per_chan=len(buf))
                print("Actual NI rate:", self._task.timing.samp_clk_rate, "Sa/s")
                writer.write_many_sample(buf)
                self._task.start()

            # quick preview
            self.line.set_data(np.arange(buf.size), buf)
            self.ax.relim(); self.ax.autoscale(); self.canvas.draw_idle()

            self._run=True; self.start_b.config(state="disabled")
            self.stop_b.config(state="normal")
        except Exception as e:
            messagebox.showerror("AO Error", str(e))
            if self._task:
                try:
                    self._task.close()
                except:
                    pass
                self._task = None
            self._stop()

    def _stop(self):
        self._run=False
        self.start_b.config(state="normal")
        self.stop_b.config(state="disabled")
        if self._task:
            try:
                if self._task.is_task_done():
                    self._task.write(0.0)  # Set voltage to 0 before closing
                self._task.stop()
                self._task.close()
            except Exception as e:
                print(f"Error stopping task: {e}")
            finally:                self._task = None
    
    def _close(self):
        self._stop()
        if not self.embedded and hasattr(self, 'toplevel'):
            self.toplevel.destroy()
        else:
            self.destroy()

    def __del__(self):
        if hasattr(self, '_task') and self._task:
            try:
                self._task.close()
            except:
                pass
# ==== END MINI TEST PANELS (AI / AO) =======================