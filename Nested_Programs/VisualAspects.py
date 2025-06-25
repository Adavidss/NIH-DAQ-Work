import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
import numpy as np
from collections import deque

# Import constants if needed
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from Constants_Paths import BASE_DIR
except ImportError:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class VisualAspects(tk.Frame):
    """Base class for handling all visual aspects of the SABRE GUI"""
    
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("SABRE Control Panel")
        self.master.geometry("620x900")  # Increased from 540x730 for better visibility
        
        # Configure minimum size to prevent content from being cut off
        self.master.minsize(300, 500)
          # Initialize method selection variables - MOVED HERE FROM LATER IN THE METHOD
        # to ensure it's available before create_widgets() is called
        self.selected_method_var = tk.StringVar(value="Select a method...")
        self.polarization_method_file = None
        self.polarization_methods_dir = r"C:\\Users\\walsworthlab\\Desktop\\SABRE Program\\config_files_SABRE\\PolarizationMethods"        # Initialize waveform visibility state
        self.waveform_visible = True

        # Initialize toggle variables
        self.audio_enabled = tk.BooleanVar(value=True)
        self.tooltips_enabled = tk.BooleanVar(value=True)

        # Add icon to the window
        try:
            icon_path = os.path.join(BASE_DIR, "SABREAppICON.png")
            icon_image = Image.open(icon_path)
            icon_photo = ImageTk.PhotoImage(icon_image)
            self.master.iconphoto(True, icon_photo)
        except Exception as e:
            print(f"Error loading application icon: {e}")
    
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
        
        # keep a reference to the window item inside the canvas
        self.canvas_win_id = self.scroll_canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
          # Pack everything
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.scroll_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_widgets(self):
        """Create basic widgets - called by subclass if needed"""
        # This method is overridden by the main class
        # Basic widget creation happens in the main SABREGUI class
        pass

    def create_advanced_tab_widgets(self, advanced_tab):
        """Create widgets for the advanced tab - to be called by main class"""
        # Toggles Section in Advanced Tab
        toggles_frame = ttk.LabelFrame(advanced_tab, text="Toggles", padding=10)
        toggles_frame.pack(fill="x", padx=5, pady=5)
        
        toggle_container = tk.Frame(toggles_frame)
        toggle_container.pack(fill="x")
        
        # Create small button style for toggles
        style = ttk.Style()
        style.configure('Small.TCheckbutton', font=('Arial', 10))
        
        # Audio toggle
        audio_btn = ttk.Checkbutton(
            toggle_container, 
            text="Audio Notifications", 
            variable=self.audio_enabled,
            style='Small.TCheckbutton'
        )
        audio_btn.pack(side="left", padx=10)
        
        # Tooltip toggle
        tooltip_btn = ttk.Checkbutton(
            toggle_container, 
            text="Show Tooltips", 
            variable=self.tooltips_enabled,
            style='Small.TCheckbutton'
        )
        tooltip_btn.pack(side="left", padx=10)

        # Testing Panel (NI-MAX style quick-test buttons)
        testing_frame = ttk.LabelFrame(advanced_tab, text="Hardware Testing", padding=10)
        testing_frame.pack(fill="x", padx=5, pady=5)
        
        test_f = tk.Frame(testing_frame)
        test_f.pack(fill="x", padx=5, pady=2)

        tk.Button(test_f, text="AI Test Panel",
                  command=self.open_ai_panel, width=14).pack(side="left", expand=True)
        tk.Button(test_f, text="AO Test Panel",
                  command=self.open_ao_panel, width=14).pack(side="left", expand=True)

        # Virtual Testing Environment Button
        self.virtual_test_button = ttk.Button(advanced_tab, text="Virtual Testing Environment", command=self.toggle_virtual_panel)
        self.virtual_test_button.pack(fill="x", pady=2)

        # SLIC Sequence Control Button
        self.slic_control_button = ttk.Button(advanced_tab, text="SLIC Sequence Control", command=self.open_slic_control)
        self.slic_control_button.pack(fill="x", pady=2)

        # Percent Polarization Calculator Button
        self.polarization_calc_button = ttk.Button(advanced_tab, text="Percent Polarization Calculator", command=self.open_polarization_calculator)
        self.polarization_calc_button.pack(fill="x", pady=2)

        # Valve Timing Configuration Section (now using parameter_section)
        if hasattr(self, 'parameter_section'):
            self.parameter_section.create_valve_timing_section(advanced_tab)

        # Presets Management Section (now using preset_manager)
        if hasattr(self, 'preset_manager'):
            self.preset_manager.create_presets_management(advanced_tab)

    def _create_waveform_live_view(self, parent):
        """Create the voltage-vs-time live plot and initialize ring buffers."""
        # Create a frame for the waveform section
        self.waveform_frame = tk.Frame(parent)
        self.waveform_frame.pack(fill="x", expand=True)

        # Create header frame for title and toggle button
        header_frame = tk.Frame(self.waveform_frame)
        header_frame.pack(fill="x")

        # Add title and toggle button side by side
        tk.Label(header_frame, text="Waveform View", font=("Arial", 12, "bold")).pack(side="left")
        self.waveform_toggle = ttk.Button(header_frame, text="Hide Plot", command=self.toggle_waveform_plot)
        self.waveform_toggle.pack(side="right", padx=5)

        # Create the plot container frame with padding
        self.plot_container = tk.Frame(self.waveform_frame)
        self.plot_container.pack(fill="both", expand=True, pady=(0, 10))

        # Matplotlib figure/axes with adjusted size and tight layout
        self.fig, self.ax = plt.subplots(figsize=(5, 3))
        self.fig.tight_layout(pad=2.0)  # Add padding to prevent cropping
        self.line = None  # Initialize as None, will create on first plot
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.set_title("Voltage vs Time")
        self.ax.grid(True, linestyle="--", linewidth=0.3)

        # Embed in Tkinter with proper expansion
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_container)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Fast ring buffers
        self.time_buf: deque = deque(maxlen=2000)
        self.voltage_buf: deque = deque(maxlen=2000)

        # Runtime bookkeeping  
        self.start_time: float | None = None
        self.plotting = False
        self.waveform_visible = True  # Initialize waveform visibility state

        # Add reset button to header frame
        self.plot_reset_button = ttk.Button(header_frame, text="Reset Plot", 
                                          command=self.reset_waveform_plot)
        self.plot_reset_button.pack(side="right", padx=5)

    def toggle_waveform_plot(self):
        """Toggle the visibility of the waveform plot."""
        if self.waveform_visible:
            self.plot_container.pack_forget()
            self.waveform_toggle.config(text="Show Plot")
        else:
            self.plot_container.pack(fill="both", expand=True, pady=(0, 10))
            self.waveform_toggle.config(text="Hide Plot")
        self.waveform_visible = not self.waveform_visible

    def update_waveform_plot(self, voltage: float, timestamp: float):
        """Append a data point and refresh the live plot."""
        if not self.plotting:
            return

        # Zero-time reference
        if self.start_time is None:
            self.start_time = timestamp
        t_rel = timestamp - self.start_time

        # Store new sample
        self.time_buf.append(t_rel)
        self.voltage_buf.append(voltage)

        # Create or update line
        if self.line is None:
            self.line, = self.ax.plot(self.time_buf, self.voltage_buf, lw=1.2)
        else:
            self.line.set_data(self.time_buf, self.voltage_buf)

        # Adaptive x-axis (show full buffer)
        if len(self.time_buf) > 1:
            self.ax.set_xlim(self.time_buf[0], self.time_buf[-1])

        # Adaptive y-axis with 5% padding
        v_min, v_max = min(self.voltage_buf), max(self.voltage_buf)
        pad = 0.05 * max(1e-3, v_max - v_min)     # avoid zero span
        self.ax.set_ylim(v_min - pad, v_max + pad)

        # Lightweight redraw
        self.canvas.draw_idle()

    def _create_live_view_in_tab(self, parent, title, y_label):
        """Create a live view panel with matplotlib plot in the specified tab."""
        # Create the main container frame
        live_view_frame = tk.Frame(parent)
        live_view_frame.pack(fill="x", expand=True, pady=5)
        
        # Create header frame for title and controls
        header_frame = tk.Frame(live_view_frame)
        header_frame.pack(fill="x")
        
        # Add title and toggle button
        tk.Label(header_frame, text=title, font=("Arial", 12, "bold")).pack(side="left")
        
        # Create a container for the plot
        plot_frame = tk.Frame(live_view_frame)
        plot_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create matplotlib figure and axes
        fig, ax = plt.subplots(figsize=(5, 3))
        fig.tight_layout(pad=2.0)
        
        # Set up basic plot
        line, = ax.plot([], [], 'b-', lw=1.2)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel(y_label)
        ax.set_title(f"{y_label} vs Time")
        ax.grid(True, linestyle="--", linewidth=0.3)
        
        # Default axis limits
        ax.set_xlim(0, 10)
        ax.set_ylim(-0.1, 0.1)
        
        # Embed in Tkinter
        canvas = FigureCanvasTkAgg(fig, master=plot_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Store references for later use
        if title == "Magnetic Field Live View":
            self.mf_fig = fig
            self.mf_ax = ax
            self.mf_line = line
            self.mf_canvas = canvas
            
            # Create data buffers for magnetic field
            self.mf_time_buf = deque(maxlen=1000)
            self.mf_field_buf = deque(maxlen=1000)
        
        return live_view_frame

    def _create_control_button(self, parent, text, color, command, side="left"):
        """Create a styled control button with the specified color and command"""
        # Define color mapping for different button types
        color_map = {
            "blue": {"bg": "#4a86e8", "fg": "white", "hover_bg": "#3a76d8"},
            "green": {"bg": "#6aa84f", "fg": "white", "hover_bg": "#5a9840"},
            "red": {"bg": "#cc0000", "fg": "white", "hover_bg": "#b00000"},
            "purple": {"bg": "#9900ff", "fg": "white", "hover_bg": "#8800dd"},
            "gray": {"bg": "#999999", "fg": "white", "hover_bg": "#777777"}
        }
        
        # Default to gray if color not found
        style = color_map.get(color.lower(), color_map["gray"])
        
        # Create the button with specified style and better sizing
        button = tk.Button(
            parent,
            text=text,
            background=style["bg"],
            foreground=style["fg"],
            activebackground=style["hover_bg"],
            activeforeground=style["fg"],
            font=("Arial", 10, "bold"),
            relief="raised",
            borderwidth=2,
            padx=15,
            pady=8,
            width=12,  # Fixed width for consistency
            command=command
        )
        
        # Pack the button with proper spacing
        if side == "right":
            button.pack(side=side, padx=(5, 0), pady=2)
        else:
            button.pack(side=side, padx=(0, 10), pady=2)
        
        return button

    def show_error_popup(self, missing_params):
        """Display error popup with missing parameters"""
        error_message = "Missing required parameters:\n" + "\n".join(f"• {param}" for param in missing_params)
        messagebox.showerror("Missing Parameters", error_message)

    def reset_waveform_plot(self):
        """Reset the waveform plot to initial state"""
        try:
            if hasattr(self, 'ax') and self.ax is not None and hasattr(self, 'canvas') and self.canvas is not None:
                self.ax.clear()
                self.line = None  # Reset line reference
                self.ax.set_xlabel("Time (s)")
                self.ax.set_ylabel("Voltage (V)")
                self.ax.set_title("Voltage vs Time")
                self.ax.grid(True, linestyle="--", linewidth=0.3)
                self.ax.set_xlim(0, 10)  # Set default x-axis limits
                self.ax.set_ylim(-0.1, 0.1)  # Set default y-axis limits
                self.canvas.draw_idle()
            else:
                print("Warning: Cannot reset waveform plot - plotting components not initialized")
        except Exception as e:
            print(f"Error resetting waveform plot: {e}")
        
        # Clear data buffers safely
        try:
            if hasattr(self, 'time_buf') and self.time_buf:
                self.time_buf.clear()
            if hasattr(self, 'voltage_buf') and self.voltage_buf:
                self.voltage_buf.clear()
        except Exception as e:
            print(f"Error clearing buffers: {e}")
          # Reset plotting state
        self.plotting = False
        self.start_time = None
        self.current_method_duration = None
        
        print("Waveform plot reset complete")

    def format_time(self, seconds):
        """Format time in seconds to MM:SS:mmm format"""
        minutes = int(seconds // 60)
        seconds_part = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{minutes:02d}:{seconds_part:02d}:{milliseconds:03d}"

    def _plot_waveform_buffer(self, buf: np.ndarray, sample_rate: float) -> None:
        """Plot the exact voltage buffer and store its duration."""
        try:
            if buf is None or len(buf) == 0 or sample_rate <= 0:
                return  # nothing to plot or bad rate

            # Check if plotting components are initialized
            if not hasattr(self, 'ax') or self.ax is None:
                print("Warning: Plotting components not initialized, cannot plot waveform")
                return
                
            if not hasattr(self, 'canvas') or self.canvas is None:
                print("Warning: Canvas not initialized, cannot plot waveform")
                return

            t = np.arange(len(buf), dtype=np.float64) / float(sample_rate)

            self.ax.clear()
            self.ax.plot(t, buf, linewidth=1.0)
            self.current_method_duration = len(buf) / sample_rate
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Voltage (V)")
            self.ax.set_title("Voltage vs Time (buffer preview)")
            self.ax.grid(True)
            self.canvas.draw_idle()
            
            print(f"Successfully plotted waveform: {len(buf)} samples, {self.current_method_duration:.2f}s duration")
            
        except Exception as e:
            print(f"Error plotting waveform buffer: {e}")
            # Try to initialize plotting components if they don't exist
            try:
                if hasattr(self, '_initialize_plotting_components'):
                    self._initialize_plotting_components()
            except Exception as init_error:
                print(f"Error initializing plotting components: {init_error}")

    def _create_polarization_method_input(self, parent):
        """Create input for selecting polarization transfer method using a combobox"""
        method_frame = ttk.LabelFrame(parent, text="Polarization Method Selection", padding=10)
        method_frame.pack(fill="x", padx=5, pady=5)
        
        # Method selection row
        selection_frame = tk.Frame(method_frame)
        selection_frame.pack(fill="x", pady=2)
        
        tk.Label(selection_frame, text="Select Method:", width=15, anchor="w").pack(side="left")
        
        # Create method combobox
        self.method_combobox = ttk.Combobox(
            selection_frame,
            textvariable=self.selected_method_var,  # This line was failing before
            width=25,
            state="readonly"
        )
        self.method_combobox.pack(side="left", padx=5, fill="x", expand=True)
        self.method_combobox.bind("<<ComboboxSelected>>", self.on_method_selected)
        
        # Refresh button
        ttk.Button(selection_frame, text="Refresh List", 
                   command=self.refresh_method_list).pack(side="left", padx=2)
        
        # Initialize method list
        self.refresh_method_list()
    
    def refresh_method_list(self):
        """Refresh the list of available polarization methods from directory"""
        try:
            method_files = []
            if os.path.exists(self.polarization_methods_dir):
                for file in os.listdir(self.polarization_methods_dir):
                    if file.endswith('.json'):
                        method_files.append(file)
            
            method_options = ["Select a method..."] + sorted(method_files)
            self.method_combobox['values'] = method_options
            
            # Reset selection if current selection no longer exists
            if self.selected_method_var.get() not in method_options:
                self.selected_method_var.set("Select a method...")
                self.polarization_method_file = None
                
        except Exception as e:
            print(f"Error refreshing methods list: {e}")
            self.method_combobox['values'] = ["Select a method..."]
    
    def on_method_selected(self, event=None):
        """Handle method selection from combobox"""
        selected = self.selected_method_var.get()
        if selected != "Select a method...":
            # Set the full path to the selected method file
            self.polarization_method_file = os.path.join(self.polarization_methods_dir, selected)
            print(f"Selected polarization method: {self.polarization_method_file}")
        else:
            self.polarization_method_file = None

    def _reset_selected_method_label(self):
        """Reset the method selection to default"""
        self.selected_method_var.set("Select a method...")
        self.polarization_method_file = None
