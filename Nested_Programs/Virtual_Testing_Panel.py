import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from Constants_Paths import BASE_DIR, CONFIG_DIR, STATE_MAPPING
from FullFlowSystem import FullFlowSystem
# ==== VIRTUAL TESTING PANEL ================================
class VirtualTestingPanel(tk.Frame):
    def __init__(self, parent, embedded=False, container=None):
        # When embedded, parent should be the SABREGUI instance, container is the frame to pack into
        if embedded and container is None:
            # If no container specified but embedded, assume parent is both parent and container
            super().__init__(parent)
            self.parent = parent
            self.container = parent
        elif embedded and container is not None:
            # Parent is SABREGUI, container is the frame to pack into
            super().__init__(container)
            self.parent = parent
            self.container = container
        else:
            # Not embedded - parent is SABREGUI, create toplevel
            super().__init__(parent)
            self.parent = parent
            self.container = None
            
        self.embedded = embedded
        
        if not embedded:
            # Create a Toplevel window to host this panel
            self.toplevel = tk.Toplevel(parent)
            self.toplevel.title("Virtual Testing Environment")
            self.master = self.toplevel
            # Move the frame into the Toplevel
            self.pack(fill="both", expand=True)
        else:
            # Frame is already in the parent
            self.toplevel = None
        self.setup_panel()

    #-----------------------
    # UI Setup Methods
    #-----------------------
    def setup_panel(self):
        """Initialize panel components"""
        # Update photo path to use main program directory
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

        # Create button container
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10, fill="x", padx=5)
        
        # Left side buttons
        left_buttons = tk.Frame(button_frame)
        left_buttons.pack(side="left")
        ttk.Button(left_buttons, text="Test Activation Sequence", 
                  command=self.visual_activation_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_buttons, text="Test Bubbling Sequence", 
                  command=self.visual_bubbling_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_buttons, text="Full Flow System", 
                  command=self.open_full_flow_system).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_buttons, text="Stop", 
                  command=self.stop_visual_sequence).pack(side=tk.LEFT, padx=5)          # Right side button
        ttk.Button(button_frame, text="Individual Valve Control",
                  command=self.open_valve_control).pack(side="right", padx=5)

    def open_full_flow_system(self):
        """Open the Full Flow System page in a new window"""
        # Use the parent (SABREGUI instance) as the parent for the new window
        # This ensures it opens in a new toplevel window, not embedded
        try:
            FullFlowSystem(self.parent, embedded=False)
        except Exception as e:
            print(f"Error opening Full Flow System: {e}")
            # Fallback to using root window if parent fails
            root_window = self.winfo_toplevel()
            FullFlowSystem(root_window, embedded=False)

    def open_valve_control(self):
        """Open the Individual Valve Control panel"""
        IndividualValveControl(self)

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
        """Start the experiment sequence - now only updates visualization"""
        if self.running:
            return
        self.running = True
        
        # Update the visual state to match initial state
        self.load_config_visual("Initial_State")
        
        # The actual sequence is now run in the parent application
        # This method is just for visualization

    def start_sequence_bubbling(self):
        """Start the bubbling sequence - now only updates visualization"""
        if self.running:
            return
        self.running = True
          # Update the visual state to match bubbling state
        self.load_config_visual("Bubbling_State_Initial")
        
        # The actual sequence is now run in the parent application
        # This method is just for visualization

    def stop_sequence(self):
        """Stop the running sequence - now just updates visual state"""
        self.running = False
        self.load_config_visual("Initial_State")

    def visual_activation_sequence(self):
        """Run activation sequence with VISUAL feedback only (no actual DAQ control)"""
        if self.running:
            return
        self.running = True

        def run_activation_sequence():
            try:
                # Visual-only sequence - do NOT call real DAQ methods
                print("Starting VISUAL activation sequence (no DAQ control)")
                
                # Use default durations if parent methods are not available
                try:
                    valve_duration = self.parent.get_value('valve_time_entry') if hasattr(self.parent, 'get_value') else 2.0
                    injection_duration = self.parent.get_value('injection_time_entry') if hasattr(self.parent, 'get_value') else 3.0
                    degassing_duration = self.parent.get_value('degassing_time_entry') if hasattr(self.parent, 'get_value') else 5.0
                    activation_duration = self.parent.get_value('activation_time_entry') if hasattr(self.parent, 'get_value') else 10.0
                except:
                    # Use defaults if getting values fails
                    valve_duration = 2.0
                    injection_duration = 3.0
                    degassing_duration = 5.0
                    activation_duration = 10.0

                state_sequence = [
                    ("Initial_State", valve_duration),
                    ("Injection_State_Start", injection_duration),
                    ("Degassing", degassing_duration),
                    ("Activation_State_Initial", activation_duration),
                    ("Activation_State_Final", valve_duration),
                    ("Initial_State", None)
                ]

                print("Visual sequence will take approximately {:.1f} seconds".format(
                    sum(duration for _, duration in state_sequence if duration)))

                for state, duration in state_sequence:
                    if not self.running:
                        break
                    print(f"Visual state: {state} for {duration} seconds")
                    if self.load_config_visual(state) and duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and self.running:
                            time.sleep(0.1)

                print("Visual activation sequence complete")
            except Exception as error:
                print(f"Error in visual activation sequence: {error}")
            finally:
                self.running = False

        threading.Thread(target=run_activation_sequence, daemon=True).start()

    def visual_bubbling_sequence(self):
        """Run bubbling sequence with VISUAL feedback only (no actual DAQ control)"""
        if self.running:
            return
        self.running = True

        def run_bubbling_sequence():
            try:
                # Visual-only sequence - do NOT call real DAQ methods
                print("Starting VISUAL bubbling sequence (no DAQ control)")
                
                # Use default duration if parent method is not available
                try:
                    bubbling_duration = self.parent.get_value('bubbling_time_entry') if hasattr(self.parent, 'get_value') else 15.0
                except:
                    bubbling_duration = 15.0

                state_sequence = [
                    ("Initial_State", 2.0),
                    ("Bubbling_State_Initial", bubbling_duration),
                    ("Bubbling_State_Final", 2.0),
                    ("Initial_State", None)                ]

                print("Visual bubbling sequence will take approximately {:.1f} seconds".format(
                    sum(duration for _, duration in state_sequence if duration)))

                for state, duration in state_sequence:
                    if not self.running:
                        break
                    print(f"Visual state: {state} for {duration} seconds")
                    if self.load_config_visual(state) and duration:
                        start_time = time.time()
                        while time.time() - start_time < duration and self.running:
                            time.sleep(0.1)

                print("Visual bubbling sequence complete")
            except Exception as error:
                print(f"Error in visual bubbling sequence: {error}")
            finally:
                self.running = False

        threading.Thread(target=run_bubbling_sequence, daemon=True).start()

    def stop_visual_sequence(self):
        """Stop the visual sequence"""
        self.running = False
        self.load_config_visual("Initial_State")

    def set_initial_states(self):
        """Set initial states for hourglasses"""
        initial_states = [False, False, False, False, False, False, False, False]  # All LOW signals
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
            # Special handling for DIO4 and DIO5 - inverted colors
            if dio_identifier in ["DIO4", "DIO5"]:
                color = 'red' if is_active else 'green'
            else:
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

# Add new class for Individual Valve Control
class IndividualValveControl(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Individual Valve Control")
        self.setup_panel()

    def setup_panel(self):
        """Initialize panel components"""
        self.photo_path = self.parent.photo_path
        self.sabre_image = None
        self.hourglasses = {}
        self.running = False
        
        self.main_canvas = tk.Canvas(self, width=750, height=500)
        self.main_canvas.pack(pady=10)
        
        self.create_ui()
        self.setup_hourglass_bindings()

    def create_ui(self):
        """Setup all UI components"""
        self.display_image()
        self.create_hourglasses()
        
        # Create state label
        self.state_label = ttk.Label(self, text="Click hourglasses to toggle valves", font=('Arial', 12))
        self.state_label.pack(pady=10)
        
        # Set initial states after creating hourglasses
        self.set_initial_states_individual()

    def set_initial_states_individual(self):
        """Set initial states for individual valve control hourglasses"""
        initial_states = [False, False, False, False, False, False, False, False]  # All LOW signals
        for i, state in enumerate(initial_states):
            self.update_hourglass_state(i, state)

    def setup_hourglass_bindings(self):
        """Add click events to hourglasses"""
        for dio_id, hourglass in self.hourglasses.items():
            self.main_canvas.tag_bind(hourglass, '<Button-1>', lambda e, d=dio_id: self.toggle_valve(d))

    def toggle_valve(self, dio_id):
        """Toggle valve state and update DAQ"""
        current_color = self.main_canvas.itemcget(self.hourglasses[dio_id], 'fill')
        
        # For DIO4 and DIO5, the logic is inverted
        if dio_id in ["DIO4", "DIO5"]:
            # If currently green (LOW/open), turn red (HIGH/closed)
            # If currently red (HIGH/closed), turn green (LOW/open)
            new_state = current_color == 'green'  # Toggle: green->True, red->False
        else:
            # Normal logic: red->True (turn green), green->False (turn red)
            new_state = current_color == 'red'
        
        # Update visual state
        self.update_hourglass_state(dio_id, new_state)
        
        # Get current states from all hourglasses to maintain other states
        dio_states = {}
        for i in range(8):
            dio_key = f"DIO{i}"
            if dio_key in self.hourglasses:
                current_fill = self.main_canvas.itemcget(self.hourglasses[dio_key], 'fill')
                # Special handling for DIO4 and DIO5 - inverted logic
                if dio_key in ["DIO4", "DIO5"]:
                    dio_states[dio_key] = current_fill == 'red'  # RED = HIGH/closed, GREEN = LOW/open
                else:
                    dio_states[dio_key] = current_fill == 'green'  # GREEN = HIGH/open, RED = LOW/closed
            else:
                dio_states[dio_key] = False
        
        # Send complete state to DAQ to maintain all current states
        self.parent.parent.send_daq_signals(dio_states)

    # Inherit common methods from parent
    def display_image(self):
        """Display the SABRE system image on the canvas"""
        try:
            img = Image.open(self.photo_path)
            img = img.resize((750, 500), Image.Resampling.LANCZOS)
            self.sabre_image = ImageTk.PhotoImage(img)
            self.main_canvas.create_image(0, 0, image=self.sabre_image, anchor='nw')
        except Exception as e:
            print(f"Error loading image: {e}")

    def create_hourglasses(self):
        """Create clickable hourglass indicators"""
        # Use same positions as parent
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
        """Create a single clickable hourglass"""
        # Same hourglass creation logic as parent
        if sideways:
            points = [
                x, y,
                x, y + height,
                x + width/2, y + height/2,
                x + width, y + height,
                x + width, y,
                x + width/2, y + height/2
            ]
        else:
            points = [
                x, y,
                x + width, y,
                x + width/2, y + height/2,
                x + width, y + height,
                x, y + height,
                x + width/2, y + height/2
            ]
        
        hourglass = self.main_canvas.create_polygon(
            points, 
            outline='black',
            fill='red',
            width=2,
            tags=f"valve_{index}"
        )
        
        self.hourglasses[f"DIO{index}"] = hourglass

    def update_hourglass_state(self, dio_identifier, is_active):
        """Update hourglass color"""
        if isinstance(dio_identifier, int):
            dio_identifier = f"DIO{dio_identifier}"
        if dio_identifier in self.hourglasses:
            # Special handling for DIO4 and DIO5 - inverted colors
            if dio_identifier in ["DIO4", "DIO5"]:
                color = 'red' if is_active else 'green'
            else:
                color = 'green' if is_active else 'red'
            self.main_canvas.itemconfig(self.hourglasses[dio_identifier], fill=color)
        
        # Set initial states after creating hourglasses
        self.set_initial_states_individual()

    def set_initial_states_individual(self):
        """Set initial states for individual valve control hourglasses"""
        initial_states = [False, False, False, False, False, False, False, False]  # All LOW signals
        for i, state in enumerate(initial_states):
            self.update_hourglass_state(i, state)

    def setup_hourglass_bindings(self):
        """Add click events to hourglasses"""
        for dio_id, hourglass in self.hourglasses.items():
            self.main_canvas.tag_bind(hourglass, '<Button-1>', lambda e, d=dio_id: self.toggle_valve(d))

    def toggle_valve(self, dio_id):
        """Toggle valve state and update DAQ"""
        current_color = self.main_canvas.itemcget(self.hourglasses[dio_id], 'fill')
        
        # For DIO4 and DIO5, the logic is inverted
        if dio_id in ["DIO4", "DIO5"]:
            # If currently green (LOW/open), turn red (HIGH/closed)
            # If currently red (HIGH/closed), turn green (LOW/open)
            new_state = current_color == 'green'  # Toggle: green->True, red->False
        else:
            # Normal logic: red->True (turn green), green->False (turn red)
            new_state = current_color == 'red'
        
        # Update visual state
        self.update_hourglass_state(dio_id, new_state)
        
        # Get current states from all hourglasses to maintain other states
        dio_states = {}
        for i in range(8):
            dio_key = f"DIO{i}"
            if dio_key in self.hourglasses:
                current_fill = self.main_canvas.itemcget(self.hourglasses[dio_key], 'fill')
                # Special handling for DIO4 and DIO5 - inverted logic
                if dio_key in ["DIO4", "DIO5"]:
                    dio_states[dio_key] = current_fill == 'red'  # RED = HIGH/closed, GREEN = LOW/open
                else:
                    dio_states[dio_key] = current_fill == 'green'  # GREEN = HIGH/open, RED = LOW/closed
            else:
                dio_states[dio_key] = False
        
        # Send complete state to DAQ to maintain all current states
        self.parent.parent.send_daq_signals(dio_states)

    # Inherit common methods from parent
    def display_image(self):
        """Display the SABRE system image on the canvas"""
        try:
            img = Image.open(self.photo_path)
            img = img.resize((750, 500), Image.Resampling.LANCZOS)
            self.sabre_image = ImageTk.PhotoImage(img)
            self.main_canvas.create_image(0, 0, image=self.sabre_image, anchor='nw')
        except Exception as e:
            print(f"Error loading image: {e}")

    def create_hourglasses(self):
        """Create clickable hourglass indicators"""
        # Use same positions as parent
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
        """Create a single clickable hourglass"""
        # Same hourglass creation logic as parent
        if sideways:
            points = [
                x, y,
                x, y + height,
                x + width/2, y + height/2,
                x + width, y + height,
                x + width, y,
                x + width/2, y + height/2
            ]
        else:
            points = [
                x, y,
                x + width, y,
                x + width/2, y + height/2,
                x + width, y + height,
                x, y + height,
                x + width/2, y + height/2
            ]
        
        hourglass = self.main_canvas.create_polygon(
            points, 
            outline='black',
            fill='red',
            width=2,
            tags=f"valve_{index}"
        )
        
        self.hourglasses[f"DIO{index}"] = hourglass

    def update_hourglass_state(self, dio_identifier, is_active):
        """Update hourglass color"""
        if isinstance(dio_identifier, int):
            dio_identifier = f"DIO{dio_identifier}"
        if dio_identifier in self.hourglasses:
            # Special handling for DIO4 and DIO5 - inverted colors
            if dio_identifier in ["DIO4", "DIO5"]:
                color = 'red' if is_active else 'green'
            else:
                color = 'green' if is_active else 'red'
            self.main_canvas.itemconfig(self.hourglasses[dio_identifier], fill=color)
