import tkinter as tk
from tkinter import ttk
import nidaqmx
import time
import threading
import json
import os
from threading import Thread

# DAQ setup
DAQ_DEVICE = "Dev5"
DIO_CHANNEL = f"{DAQ_DEVICE}/port0/line0"  # PFI 0/P0.0 (Pin 25 on USB-6421)

# Main GUI Class
class SABREGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SABRE Control Panel")
        self.geometry("450x700")
        self.create_widgets()
        self.timer_thread = None  # To handle the countdown timer in a separate thread
        self.virtual_panel = None
        self.advanced_visible = False  # Track state of advanced options
    # UI Setup
    def create_widgets(self):
        """Create the widgets for the main GUI window."""
        # Define the parameters and their units
        parameters = [
            ("Bubbling Time", ["sec", "min"], "sec"),
            ("Magnetic Field", ["T", "mT", "T"], "T"),
            ("Temperature", ["K", "C", "F"], "K"),
            ("Flow Rate", [], "sccm"),
            ("Pressure", ["psi", "bar", "atm"], "psi"),
        ]

        # Create the parameters section
        self.parameters_frame = tk.Frame(self)
        self.parameters_frame.pack(fill="x", padx=5, pady=2)
        tk.Label(self.parameters_frame, text="Parameters", font=("Arial", 12, "bold")).pack(anchor="w")

        # Create the parameter input fields
        self.entries, self.units = {}, {}
        for param, units, default_unit in parameters:
            frame = tk.Frame(self.parameters_frame)
            frame.pack(fill="x", padx=5, pady=2)
            tk.Label(frame, text=param, width=25, anchor="w").pack(side="left")
            entry = tk.Entry(frame, width=10)
            entry.pack(side="left")
            self.entries[param] = entry

            if units:
                unit_var = tk.StringVar(value=default_unit)
                ttk.Combobox(frame, textvariable=unit_var, values=units, width=5, state="readonly").pack(side="left")
                self.units[param] = unit_var
            else:
                tk.Label(frame, text=default_unit).pack(side="left")

        # Create the advanced options section
        self.advanced_frame = tk.Frame(self)
        self.advanced_frame.pack(fill="x", padx=5, pady=2)
        
        tk.Label(self.advanced_frame, text="Advanced Options", font=("Arial", 12, "bold")).pack(anchor="w")
        self._create_advanced_input("Valve Control Timing", "valve_time_entry")
        self._create_advanced_input("Activation Time", "activation_time_entry")
        self._create_advanced_input("Degassing Time", "degassing_time_entry")
        self._create_advanced_input("Injection Time", "injection_time_entry")

        # Create the virtual testing environment button
        self.virtual_test_button = ttk.Button(self.advanced_frame, text="Virtual Testing Environment", command=self.toggle_virtual_panel)
        self.virtual_test_button.pack(fill="x", pady=2)

        # Create the control buttons
        self._create_control_button("Activate", "blue", self.activate_experiment, "left")
        self._create_control_button("Start", "green", self.start_experiment, "left")
        self._create_control_button("Scram", "red", self.scram_experiment, "right")

        # Create the experiment timer
        tk.Label(self, text="Experiment Time", font=("Arial", 12, "bold")).pack(anchor="w")
        self.timer_label = tk.Label(self, text="00:00", font=("Arial", 14))
        self.timer_label.pack()
        self.state_label = tk.Label(self, text="State: Idle", font=("Arial", 10))
        self.state_label.pack()

        # Create the waveform live view
        self._create_live_view("Waveform Live View", "Input Waveform", ["Sine", "Square", "Triangle"])

        # Create the magnetic field live view
        self._create_live_view("Magnetic Field Live View", "Magnetic Field")

    def create_advanced_input(self, label_text, entry_attribute):
        """Create an input field for advanced options."""
        frame = tk.Frame(self.advanced_frame)
        frame.pack(fill="x", padx=5, pady=2)
        tk.Label(frame, text=label_text, width=25, anchor="w").pack(side="left")
        entry = tk.Entry(frame, width=10)
        entry.pack(side="left")
        tk.Label(frame, text="sec").pack(side="left")
        setattr(self, entry_attribute, entry)

    def create_advanced_button(self, text: str) -> None:
        """Create a button in the advanced options section."""
        ttk.Button(self.advanced_frame, text=text).pack(fill="x", pady=2)
    def _create_control_button(self, parent, text, color, command, side):
        tk.Button(parent, text=text, bg=color, width=12, command=command).pack(side=side, expand=True)
    def _create_live_view(self, section_title, label_text, combobox_values=None):
        tk.Label(self, text=section_title, font=("Arial", 12, "bold")).pack(anchor="w")
        frame = tk.Frame(self)
        frame.pack(fill="x", padx=5, pady=2)
        tk.Label(frame, text=label_text, width=25, anchor="w").pack(side="left")
        if combobox_values:
            var = tk.StringVar(value=combobox_values[0])
            ttk.Combobox(frame, textvariable=var, values=combobox_values, width=10, state="readonly").pack(side="left")

    # Event Handlers
    def toggle_advanced_options(self):
        """Toggle visibility of advanced options"""
        if self.advanced_options_visible:
            self.advanced_options_frame.pack_forget()
            self.advanced_options_toggle_button.config(text="Advanced Options")
        else:
            self.advanced_options_frame.pack(fill="x", padx=5, pady=2, after=self.advanced_options_container)
            self.advanced_options_toggle_button.config(text="Advanced Options")
        self.advanced_options_visible = not self.advanced_options_visible

    def toggle_virtual_testing_panel(self):
        """Toggle the virtual testing panel visibility"""
        if self.virtual_testing_panel is None or not self.virtual_testing_panel.winfo_exists():
            self.virtual_testing_panel = VirtualTestingPanel(self)
        else:
            self.virtual_testing_panel.destroy()
            self.virtual_testing_panel = None

    def activate_experiment(self):
        """Check for missing input values and activate the experiment."""
        missing_params = []
        required_fields = [
            ("activation_time", self.activation_time_entry),
            ("temperature", self.entries["Temperature"]),
            ("flow_rate", self.entries["Flow Rate"]),
            ("pressure", self.entries["Pressure"]),
            ("injection_time", self.injection_time_entry),
            ("valve_control_timing", self.valve_time_entry),
            ("degassing_time", self.degassing_time_entry),
        ]
        for param, entry in required_fields:
            if not entry.get():  # Check if the field is empty
                missing_params.append(param)
        if missing_params:
            self.show_error_popup(missing_params)
        else:
            if self.virtual_panel and self.virtual_panel.winfo_exists():
                self.virtual_panel.update_circle_state(0, True)

    def show_error_popup(self, missing_parameters):
        """Show a popup dialog with a red X icon and an error message."""
        error_message = "Missing the following parameters:\n" + "\n".join(missing_parameters)
        error_dialog = tk.Toplevel(self)
        error_dialog.title("Error")
        error_dialog.geometry("300x150")
        canvas = tk.Canvas(error_dialog, width=100, height=100)
        canvas.pack(pady=20)
        canvas.create_oval(10, 10, 90, 90, fill="red")
        canvas.create_line(20, 20, 80, 80, width=4, fill="white")
        canvas.create_line(20, 80, 80, 20, width=4, fill="white")
        tk.Label(error_dialog, text=error_message, font=("Arial", 12), justify="left").pack()

    def start_experiment(self):
        if self.virtual_panel and self.virtual_panel.winfo_exists():
            # Set circles 2 and 3 to HIGH state when starting
            self.virtual_panel.update_circle_state(1, True)
            self.virtual_panel.update_circle_state(2, True)
        # Add your start experiment logic here

    def scram_experiment(self):
        """Immediately stop the experiment and reset the timer and state."""
        if self._virtual_panel and self._virtual_panel.winfo_exists():
            for i in range(8):
                self._virtual_panel.update_circle_state(i, False)
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self._dio_channel)
            task.write(False)
        self._timer_label.config(text="00:00")
        self._state_label.config(text="State: Idle")



# Define the directory where the configuration files are stored
CONFIG_DIR = r"C:\Users\walsw\SABRE Panel Program\config_files_SABRE"

class VirtualTestingPanel(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Virtual Testing Environment")
        self.geometry("800x200")
        
        self.parent = parent  # Reference to parent SABREGUI
        
        # State label
        self.state_label = ttk.Label(self, text="Current State: None", font=('Arial', 12))
        self.state_label.pack(pady=10)
        
        # Initialize circles
        self.circle_frame = tk.Frame(self)
        self.circle_frame.pack(pady=20)
        self.circles = {f"DIO{i+1}": self._create_circle(self.circle_frame, i) for i in range(8)}
        
        # Control buttons
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Start Sequence", command=self.start_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Stop", command=self.stop_sequence).pack(side=tk.LEFT, padx=5)
        
        self.is_running = False

    def _create_circle(self, parent: tk.Frame, index: int) -> tuple[tk.Canvas, int]:
        """Create a circle canvas and label."""
        container = tk.Frame(parent)
        container.pack(side=tk.LEFT, padx=10)
        canvas = tk.Canvas(container, width=50, height=50)
        canvas.pack()
        circle = canvas.create_oval(5, 5, 45, 45, fill='red') 
        dio_label = tk.Label(container, text=f"DIO{index + 1}")
        dio_label.pack()
        return canvas, circle

    def update_circle_state(self, dio_identifier, is_active):
        """Update the circle color based on the digital I/O state"""
        if isinstance(dio_identifier, int):
            dio_identifier = f"DIO{dio_identifier + 1}"

        if dio_identifier in self.circles:
            color = 'green' if is_active else 'red'
            canvas, circle = self.circles[dio_identifier]
            canvas.itemconfig(circle, fill=color)

    def load_config(self, state):
        """Load and apply configuration from file."""
        try:
            config_file = os.path.join(CONFIG_DIR, f"{state.replace(' ', '_')}.json")
            if not os.path.exists(config_file):
                print(f"Configuration file not found: {config_file}")
                return False
                
            with open(config_file, "r") as file:
                config_data = json.load(file)
            
            # Update the state label
            self.state_label.config(text=f"Current State: {state}")
            
            # Update DIO states
            dio_states = {f"DIO{i+1}": config_data.get(f"DIO{i+1}", "LOW").upper() == "HIGH"
                          for i in range(8)}
            for dio, is_active in dio_states.items():
                self.update_circle_state(dio, is_active)
            
            return True

        except Exception as error:
            print(f"Error loading state {state}: {error}")
            return False

    def start_sequence(self):
        """Start the experiment sequence"""
        if self.running:
            return
        self.running = True
        def run_experiment_sequence():
            try:
                # Retrieve timing values from parent entries
                valve_duration = float(self.parent.valve_time_entry.get())
                injection_duration = float(self.parent.injection_time_entry.get())
                degassing_duration = float(self.parent.degassing_time_entry.get())
                activation_duration = float(self.parent.activation_time_entry.get())

                state_sequence = [
                    ("Injection_State_Start", 0),
                    ("Initial_State", valve_duration),
                    ("Injection_State", injection_duration),
                    ("Degassing", degassing_duration),
                    ("Activation_State_Initial", activation_duration),
                    ("Activation_State_Final", valve_duration),
                    ("Initial_State", None),
                ]

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

    def stop_sequence(self):
        """Stop the running sequence"""
        self.running = False
        self.load_config("Initial_State")

if __name__ == "__main__":
    app = SABREGUI()
    app.mainloop()