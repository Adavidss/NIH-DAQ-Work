import tkinter as tk
from tkinter import ttk
import nidaqmx
import time
import threading
import json
import os

# DAQ setup
DAQ_DEVICE = "Dev5"
DIO_CHANNEL = f"{DAQ_DEVICE}/port0/line0"  # PFI 0/P0.0 (Pin 25 on USB-6421)

class VirtualTestingPanel(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Virtual Testing Environment")
        self.geometry("800x200")
        
        # Create main frame for circles
        self.circle_frame = tk.Frame(self)
        self.circle_frame.pack(pady=20)
        
        # Create canvas objects for each circle
        self.circles = []
        self.circle_states = [False] * 8  # Track state of each circle (False = LOW, True = HIGH)
        
        for i in range(8):
            # Create frame for each circle and its label
            circle_container = tk.Frame(self.circle_frame)
            circle_container.pack(side=tk.LEFT, padx=10)
            
            # Create canvas for circle
            canvas = tk.Canvas(circle_container, width=50, height=50)
            canvas.pack()
            
            # Draw circle (initially red for LOW state)
            circle = canvas.create_oval(5, 5, 45, 45, fill='red')
            self.circles.append(circle)
            
            # Add number label below circle
            tk.Label(circle_container, text=str(i + 1)).pack()
            
            # Store canvas reference
            circle_container.canvas = canvas
    
    def update_circle_state(self, index, state):
        """Update the state and color of a specific circle"""
        self.circle_states[index] = state
        color = 'green' if state else 'red'
        circle_container = self.circle_frame.winfo_children()[index]
        circle_container.canvas.itemconfig(self.circles[index], fill=color)

class SABREGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SABRE Control Panel")
        self.geometry("450x700")
        self.create_widgets()
        self.timer_thread = None  # To handle the countdown timer in a separate thread
        self.virtual_panel = None  # Reference to virtual testing panel
        self.advanced_visible = False  # Track state of advanced options

    def create_widgets(self):
        # Parameters Section
        parameters = [
            ("Bubbling Time", ["sec", "min"], "sec", ["none", "SLIC timing"]),
            ("Magnetic Field", ["T", "mT", "T"], "T"),
            ("Temperature", ["K", "C", "F"], "K"),
            ("Flow Rate", [], "sccm"),
            ("Pressure", ["psi", "bar", "atm"], "psi"),
        ]
        
        tk.Label(self, text="Parameters", font=("Arial", 12, "bold")).pack(anchor="w")
        self.entries, self.units = {}, {}

        for param, unit_options, default_unit, *extra_options in parameters:
            frame = tk.Frame(self)
            frame.pack(fill="x", padx=5, pady=2)
            tk.Label(frame, text=param, width=25, anchor="w").pack(side="left")

            entry = tk.Entry(frame, width=10)
            entry.pack(side="left")
            self.entries[param] = entry  # Store input field

            if unit_options:  # If there are unit choices, create dropdown
                unit_var = tk.StringVar(value=default_unit)
                ttk.Combobox(frame, textvariable=unit_var, values=unit_options, width=5, state="readonly").pack(side="left")
                self.units[param] = unit_var  # Store selected unit
            else:  # If no dropdown is needed, just display the unit label
                tk.Label(frame, text=default_unit).pack(side="left")
            
            if extra_options:
                extra_var = tk.StringVar(value=extra_options[0][0])
                ttk.Combobox(frame, textvariable=extra_var, values=extra_options[0], width=10, state="readonly").pack(side="left")

        # Polarization Transfer Method (Dropdown Only)
        frame = tk.Frame(self)
        frame.pack(fill="x", padx=5, pady=2)
        tk.Label(frame, text="Polarization Transfer Method", width=25, anchor="w").pack(side="left")
        self.polarization_method = tk.StringVar(value="SLIC")
        ttk.Combobox(frame, textvariable=self.polarization_method, values=["SLIC"], width=10, state="readonly").pack(side="left")

        # Advanced Options Section (Collapsible)
        self.advanced_container = tk.Frame(self)
        self.advanced_container.pack(fill="x", padx=5, pady=2)

        self.advanced_toggle = tk.Button(self.advanced_container, text="Advanced Options", command=self.toggle_advanced, anchor="w")
        self.advanced_toggle.pack(fill="x")

        self.advanced_frame = tk.Frame(self)

        # Add Virtual Testing Environment button
        self.virtual_test_button = ttk.Button(self.advanced_frame, text="Virtual Testing Environment", command=self.toggle_virtual_panel)
        self.virtual_test_button.pack(fill="x", pady=2)

        # Valve Control Timing
        valve_frame = tk.Frame(self.advanced_frame)
        valve_frame.pack(fill="x", padx=5, pady=2)
        tk.Label(valve_frame, text="Valve Control Timing", width=25, anchor="w").pack(side="left")
        self.valve_time_entry = tk.Entry(valve_frame, width=10)
        self.valve_time_entry.pack(side="left")
        tk.Label(valve_frame, text="sec").pack(side="left")
        
        # Activation Time
        activation_frame = tk.Frame(self.advanced_frame)
        activation_frame.pack(fill="x", padx=5, pady=2)
        tk.Label(activation_frame, text="Activation Time", width=25, anchor="w").pack(side="left")
        self.activation_time_entry = tk.Entry(activation_frame, width=10)
        self.activation_time_entry.pack(side="left")
        tk.Label(activation_frame, text="sec").pack(side="left")
        
        # Degassing Time
        degassing_frame = tk.Frame(self.advanced_frame)
        degassing_frame.pack(fill="x", padx=5, pady=2)
        tk.Label(degassing_frame, text="Degassing Time", width=25, anchor="w").pack(side="left")
        self.degassing_time_entry = tk.Entry(degassing_frame, width=10)
        self.degassing_time_entry.pack(side="left")
        tk.Label(degassing_frame, text="sec").pack(side="left")
        
        # Injection Time
        injection_frame = tk.Frame(self.advanced_frame)
        injection_frame.pack(fill="x", padx=5, pady=2)
        tk.Label(injection_frame, text="Injection Time", width=25, anchor="w").pack(side="left")
        self.injection_time_entry = tk.Entry(injection_frame, width=10)
        self.injection_time_entry.pack(side="left")
        tk.Label(injection_frame, text="sec").pack(side="left")

        # Save and Load Parameters Buttons
        ttk.Button(self.advanced_frame, text="Save Parameters").pack(fill="x", pady=2)
        ttk.Button(self.advanced_frame, text="Load Parameters").pack(fill="x", pady=2)
        
        # Download Config Files Button
        ttk.Button(self.advanced_frame, text="Download Config Files").pack(fill="x", pady=2)

        # Activate Button (Blue color)
        button_frame = tk.Frame(self)
        button_frame.pack(fill="x", padx=5, pady=5)

        self.activate_button = tk.Button(button_frame, text="Activate", bg="blue", width=12, command=self.activate_experiment)
        self.activate_button.pack(side="left", expand=True)

        # Start and Scram Buttons
        self.start_button = tk.Button(button_frame, text="Start", bg="green", width=12, command=self.start_experiment)
        self.start_button.pack(side="left", expand=True)

        self.scram_button = tk.Button(button_frame, text="Scram", bg="red", width=12, command=self.scram_experiment)
        self.scram_button.pack(side="right", expand=True)

        # Experiment Timer
        tk.Label(self, text="Experiment Time", font=("Arial", 12, "bold")).pack(anchor="w")
        self.timer_label = tk.Label(self, text="00:00", font=("Arial", 14))
        self.timer_label.pack()

        self.state_label = tk.Label(self, text="State: Idle", font=("Arial", 10))
        self.state_label.pack()

        # Waveform Live View
        tk.Label(self, text="Waveform Live View", font=("Arial", 12, "bold")).pack(anchor="w")
        waveform_frame = tk.Frame(self)
        waveform_frame.pack(fill="x", padx=5, pady=2)
        tk.Label(waveform_frame, text="Input Waveform", width=25, anchor="w").pack(side="left")
        self.waveform_type = tk.StringVar(value="Sine")
        ttk.Combobox(waveform_frame, textvariable=self.waveform_type, values=["Sine", "Square", "Triangle"], width=10, state="readonly").pack(side="left")

        # Magnetic Field Live View
        tk.Label(self, text="Magnetic Field Live View", font=("Arial", 12, "bold")).pack(anchor="w")
        magnetic_field_frame = tk.Frame(self)
        magnetic_field_frame.pack(fill="x", padx=5, pady=2)

    def toggle_advanced(self):
        """Toggle visibility of advanced options"""
        if self.advanced_visible:
            self.advanced_frame.pack_forget()
            self.advanced_toggle.config(text="â–¶ Advanced Options")
        else:
            self.advanced_frame.pack(fill="x", padx=5, pady=2, after=self.advanced_container)
            self.advanced_toggle.config(text="â–¼ Advanced Options")
        self.advanced_visible = not self.advanced_visible

    def toggle_virtual_panel(self):
        """Toggle the virtual testing panel visibility"""
        if self.virtual_panel is None or not self.virtual_panel.winfo_exists():
            self.virtual_panel = VirtualTestingPanel(self)
        else:
            self.virtual_panel.destroy()
            self.virtual_panel = None

    def activate_experiment(self):
        # Check for missing input values
        missing_params = []
        required_fields = [
            ("Activation Time", self.activation_time_entry),
            ("Temperature", self.entries["Temperature"]),
            ("Flow Rate", self.entries["Flow Rate"]),
            ("Pressure", self.entries["Pressure"]),
            ("Injection Time", self.injection_time_entry),
            ("Valve Control Timing", self.valve_time_entry),
            ("Degassing Time", self.degassing_time_entry),
        ]
        
        for param, entry in required_fields:
            if not entry.get():  # Check if the field is empty
                missing_params.append(param)
        
        if missing_params:
            self.show_error_popup(missing_params)
        else:
            if self.virtual_panel and self.virtual_panel.winfo_exists():
                # Update first circle to HIGH state when activating
                self.virtual_panel.update_circle_state(0, True)
            # Continue with experiment activation

    def show_error_popup(self, missing_params):
        error_message = "Missing the following parameters:\n" + "\n".join(missing_params)
        
        error_popup = tk.Toplevel(self)
        error_popup.title("Error")
        error_popup.geometry("300x150")
        
        # Create the red X in a circle
        canvas = tk.Canvas(error_popup, width=100, height=100)
        canvas.pack(pady=20)
        canvas.create_oval(10, 10, 90, 90, fill="red")
        canvas.create_line(20, 20, 80, 80, width=4, fill="white")
        canvas.create_line(20, 80, 80, 20, width=4, fill="white")
        
        # Error message next to the red X
        tk.Label(error_popup, text=error_message, font=("Arial", 12), justify="left").pack()

    def start_experiment(self):
        if self.virtual_panel and self.virtual_panel.winfo_exists():
            # Example: Set circles 2 and 3 to HIGH state when starting
            self.virtual_panel.update_circle_state(1, True)
            self.virtual_panel.update_circle_state(2, True)
        # Add your start experiment logic here

    def scram_experiment(self):
        if self.virtual_panel and self.virtual_panel.winfo_exists():
            # Set all circles to LOW state when scramming
            for i in range(8):
                self.virtual_panel.update_circle_state(i, False)
        
        # Immediately stop the DIO signal
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(DIO_CHANNEL)
            task.write(False)
            print("DIO 0 set LOW (0) - Scram")
        
        # Reset timer and state
        self.timer_label.config(text="00:00")
        self.state_label.config(text="State: Idle")
        print("Scram triggered: Experiment stopped")


def load_config(state):
    """Load JSON configuration for the given state and set the DAQ outputs accordingly."""
    config_path = os.path.join(CONFIG_DIR, f"{state}.json")

    if not os.path.exists(config_path):
        print(f"Warning: Configuration file for {state} not found: {config_path}")
        return
    
    try:
        with open(config_path, "r") as file:
            config = json.load(file)

        # Extract and convert all 8 digital states (HIGH → True, LOW → False)
        state_values = []
        for i in range(8):
            dio_key = f"DIO{i+1}"
            value = config.get(dio_key, "LOW").strip().upper()  # Handle formatting
            state_values.append(value == "HIGH")

        print(f"Loaded {state}: {state_values}")

        # Apply to DAQ
        with nidaqmx.Task() as task:
            channels = [f"{DAQ_DEVICE}/port0/line{i}" for i in range(8)]
            task.do_channels.add_do_chan(",".join(channels))
            task.write(state_values)  # Apply all states at once

        print(f"Applied {state}: {state_values}")

    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON in {config_path}. Please check the file format.")
    except Exception as e:
        print(f"Error loading state {state}: {e}")

def run_experiment_sequence(valve_time, injection_time, degassing_time, activation_time):
    """Run the full state transition sequence with correct timing."""
    try:
        state_sequence = [
            ("Injection_State_Start", 0),  # Start immediately
            ("Initial_State", float(valve_time)),
            ("Injection_State", float(injection_time)),
            ("Degassing", float(degassing_time)),
            ("Activation_State_Initial", float(activation_time)),
            ("Activation_State_Final", 0)  # Hold final state indefinitely
        ]

        for state, wait_time in state_sequence:
            load_config(state)  # Load config for the current state
            print(f"Now in {state}, waiting {wait_time}s...")

            if wait_time > 0:
                start_time = time.time()
                while time.time() - start_time < wait_time:
                    if app.scram_button_pressed:  # Ensure `app` is defined or removed
                        print("SCRAM activated! Resetting to Initial_State.")
                        load_config("Initial_State")
                        return
                    time.sleep(0.1)

        print("Experiment sequence completed. Holding at Activation_State_Final.")

        # Stay in Activation_State_Final unless SCRAM is pressed
        while True:
            if app.scram_button_pressed:  # Ensure `app` is defined or removed
                print("SCRAM activated! Resetting to Initial_State.")
                load_config("Initial_State")
                break
            time.sleep(0.1)

    except Exception as e:
        print(f"Error in experiment sequence: {e}")

# Start experiment sequence in a separate thread
# Replace `app` values with appropriate ones or pass them as parameters
experiment_thread = threading.Thread(target=run_experiment_sequence, args=(5, 10, 15, 20), daemon=True)  # Replace with real values
experiment_thread.start()

if __name__ == "__main__":
    app = SABREGUI()
    app.mainloop()