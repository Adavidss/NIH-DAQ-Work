import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import numpy as np

class SLICSequenceControl(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("SLIC Sequence Control")
        self.geometry("600x400")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the user interface"""
        # Main container
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Sequence parameters
        param_frame = ttk.LabelFrame(main_frame, text="Sequence Parameters", padding="5")
        param_frame.pack(fill="x", pady=5)
        
        # Sample rate
        ttk.Label(param_frame, text="Sample Rate (Hz):").grid(row=0, column=0, padx=5, pady=5)
        self.sample_rate = ttk.Entry(param_frame)
        self.sample_rate.grid(row=0, column=1, padx=5, pady=5)
        self.sample_rate.insert(0, "10000")
        
        # Duration
        ttk.Label(param_frame, text="Duration (s):").grid(row=1, column=0, padx=5, pady=5)
        self.duration = ttk.Entry(param_frame)
        self.duration.grid(row=1, column=1, padx=5, pady=5)
        self.duration.insert(0, "1.0")
        
        # Control buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text="Generate Sequence", 
                  command=self.generate_sequence).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Load Sequence", 
                  command=self.load_sequence).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Save Sequence", 
                  command=self.save_sequence).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Send to AO", 
                  command=self.send_to_ao).pack(side="right", padx=5)
                  
        # Data preview
        preview_frame = ttk.LabelFrame(main_frame, text="Sequence Preview", padding="5")
        preview_frame.pack(fill="both", expand=True, pady=5)
        
        self.preview_text = tk.Text(preview_frame, height=10, width=50)
        self.preview_text.pack(fill="both", expand=True)
        
    def generate_sequence(self):
        """Generate a SLIC sequence based on parameters"""
        try:
            sr = float(self.sample_rate.get())
            dur = float(self.duration.get())
            
            # Example sequence generation (can be modified as needed)
            t = np.linspace(0, dur, int(sr * dur))
            data = np.sin(2 * np.pi * 10 * t)  # 10 Hz sine wave
            
            self.sequence_data = {
                "type": "SLIC_sequence",
                "params": {
                    "SamplingRate": sr,
                    "Duration": dur
                },
                "data": data.tolist()
            }
            
            # Update preview
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, f"Generated sequence:\n")
            self.preview_text.insert(tk.END, f"Sample rate: {sr} Hz\n")
            self.preview_text.insert(tk.END, f"Duration: {dur} s\n")
            self.preview_text.insert(tk.END, f"Samples: {len(data)}\n")
            
        except ValueError as e:
            messagebox.showerror("Error", "Invalid parameter values")
            
    def load_sequence(self):
        """Load a SLIC sequence from file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Load SLIC Sequence"
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    self.sequence_data = json.load(f)
                    
                if self.sequence_data.get("type") != "SLIC_sequence":
                    raise ValueError("Not a valid SLIC sequence file")
                    
                # Update UI with loaded parameters
                params = self.sequence_data["params"]
                self.sample_rate.delete(0, tk.END)
                self.sample_rate.insert(0, str(params["SamplingRate"]))
                self.duration.delete(0, tk.END)
                self.duration.insert(0, str(params["Duration"]))
                
                # Update preview
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, f"Loaded sequence from {file_path}\n")
                self.preview_text.insert(tk.END, f"Sample rate: {params['SamplingRate']} Hz\n")
                self.preview_text.insert(tk.END, f"Duration: {params['Duration']} s\n")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load sequence: {str(e)}")
                
    def save_sequence(self):
        """Save current SLIC sequence to file"""
        if not hasattr(self, 'sequence_data'):
            messagebox.showerror("Error", "No sequence to save")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save SLIC Sequence"
        )
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.sequence_data, f)
                messagebox.showinfo("Success", "Sequence saved successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save sequence: {str(e)}")
                
    def send_to_ao(self):
        """Send the sequence to the analog output"""
        if not hasattr(self, 'sequence_data'):
            messagebox.showerror("Error", "No sequence to send")
            return
            
        try:
            # Convert data to numpy array if it's not already
            data = np.array(self.sequence_data["data"])
            sr = self.sequence_data["params"]["SamplingRate"]
            
            # Use parent's method to send to AO
            self.parent._write_analog_waveform(data, sr)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send sequence: {str(e)}")
