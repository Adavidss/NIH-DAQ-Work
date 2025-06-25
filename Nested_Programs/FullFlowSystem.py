import os
import tkinter as tk
from PIL import Image, ImageTk
import json  # Missing import for JSON handling

from Constants_Paths import BASE_DIR, CONFIG_DIR

class FullFlowSystem(tk.Frame):
    def __init__(self, parent, embedded=False):
        self.parent = parent
        self.embedded = embedded
        
        if not embedded:
            # Create a Toplevel window to host this panel
            self.toplevel = tk.Toplevel(parent)
            self.toplevel.title("Full Flow System")
            self.toplevel.geometry("950x650")  # Set appropriate size
            super().__init__(self.toplevel)
            self.pack(fill="both", expand=True)
        else:
            # Frame is embedded in the parent
            super().__init__(parent)
            self.toplevel = None
        
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

        # Initial hourglass positions with exact coordinates from actual positions
        hourglass_positions = [
            (199, 154, True),
            (600, 317, False),
            (558, 302, True),
            (612, 302, True),
            (509, 259, False),
            (576, 249, True),
            (576, 219, True),
            (239, 304, False)
        ]
        
        # Create hourglasses with dimensions derived from positions (30x30)
        for i, (x, y, sideways) in enumerate(hourglass_positions):
            self.create_single_hourglass(i, x, y, 30, 30, sideways)
        
        self.set_initial_states()

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
            
            # Center the image on the canvas and add background tag
            x = (target_width - new_width) // 2
            y = (target_height - new_height) // 2
            self.main_canvas.create_image(x, y, image=self.sabre_image, anchor='nw', tags=("background",))
            
            # Keep background image behind other elements
            self.main_canvas.tag_lower("background")
            
        except Exception as e:
            print(f"Error loading image: {e}")

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
            width=2
        )
        
        self.hourglasses[f"DIO{index}"] = hourglass

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
        """Load and apply configuration from file"""
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

    def set_initial_states(self):
        """Set initial states for hourglasses"""
        initial_states = [False, False, False, False, True, True, False, False]  # LOW, LOW, LOW, LOW, HIGH, HIGH, LOW, LOW
        for i, state in enumerate(initial_states):
            self.update_hourglass_state(i, state)
