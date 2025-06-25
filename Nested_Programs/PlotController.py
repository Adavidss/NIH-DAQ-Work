import time
import numpy as np


class PlotController:
    """Handles all plotting operations"""
    def __init__(self, parent):
        self.parent = parent
        self.main_fig = None
        self.main_ax = None
        self.main_canvas = None
        self.field_fig = None
        self.field_ax = None
        self.field_canvas = None
        self.waveform_visible = True
        
        # Live plotting variables
        self.line = None
        self.plotting_active = False
        
    def initialize_plots(self):
        """Initialize plot components if they exist"""
        try:
            if self.main_ax is not None:
                self.main_ax.clear()
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Live Waveform")
                self.main_ax.grid(True, alpha=0.3)
                if self.main_canvas is not None:
                    self.main_canvas.draw()
        except Exception as e:
            print(f"Error initializing plots: {e}")
            
    def start_live_plotting(self):
        """Start live waveform plotting"""
        try:
            self.plotting_active = True
            self.parent.voltage_data = []
            self.parent.time_data = []
            self.parent.start_time = time.time()
            self.line = None  # Reset line
            
            if self.main_ax is not None:
                self.main_ax.clear()
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Live Waveform - Recording")
                self.main_ax.grid(True, alpha=0.3)
                if self.main_canvas is not None:
                    self.main_canvas.draw()
                    
            print("Live plotting started")
        except Exception as e:
            print(f"Error starting live plotting: {e}")
            
    def update_live_plot(self, voltage, timestamp=None):
        """Update the live plot with new voltage data"""
        if not self.plotting_active:
            return
            
        try:
            if timestamp is None:
                timestamp = time.time()
                
            # Calculate relative time
            if self.parent.start_time is None:
                self.parent.start_time = timestamp
            relative_time = timestamp - self.parent.start_time
            
            # Add data to buffers
            self.parent.voltage_data.append(voltage)
            self.parent.time_data.append(relative_time)
            
            # Limit buffer size for performance
            max_points = 1000
            if len(self.parent.voltage_data) > max_points:
                self.parent.voltage_data = self.parent.voltage_data[-max_points:]
                self.parent.time_data = self.parent.time_data[-max_points:]
            
            # Update plot
            if self.main_ax is not None and len(self.parent.time_data) > 0:
                if self.line is None:
                    plot_result = self.main_ax.plot(self.parent.time_data, self.parent.voltage_data, 'b-', linewidth=1)
                    if plot_result:
                        self.line = plot_result[0]
                else:
                    self.line.set_data(self.parent.time_data, self.parent.voltage_data)
                
                # Update axis limits
                if len(self.parent.time_data) > 1:
                    self.main_ax.set_xlim(min(self.parent.time_data), max(self.parent.time_data))
                    
                if len(self.parent.voltage_data) > 0:
                    v_min, v_max = min(self.parent.voltage_data), max(self.parent.voltage_data)
                    padding = 0.1 * max(0.1, v_max - v_min)
                    self.main_ax.set_ylim(v_min - padding, v_max + padding)
                
                if self.main_canvas is not None:
                    self.main_canvas.draw_idle()
                    
        except Exception as e:
            print(f"Error updating live plot: {e}")
            
    def stop_live_plotting(self):
        """Stop live waveform plotting"""
        try:
            self.plotting_active = False
            if self.main_ax is not None:
                self.main_ax.set_title("Live Waveform")
                if self.main_canvas is not None:
                    self.main_canvas.draw()
            print("Live plotting stopped")
        except Exception as e:
            print(f"Error stopping live plotting: {e}")

    def plot_waveform_buffer(self, buf, sr):
        """Plot waveform buffer for preview"""
        try:
            if self.main_ax is not None and self.main_canvas is not None:
                self.main_ax.clear()
                time_axis = np.arange(len(buf)) / sr
                self.main_ax.plot(time_axis, buf, 'b-', linewidth=1)
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Polarization Method Waveform")
                self.main_ax.grid(True, alpha=0.3)
                
                # Force multiple canvas updates to ensure visibility
                self.main_canvas.draw()
                self.main_canvas.draw_idle()
                self.main_canvas.flush_events()
                
                print(f"Plotted waveform: {len(buf)} samples at {sr} Hz")
        except Exception as e:
            print(f"Error plotting waveform buffer: {e}")
            
    def reset_waveform_plot(self):
        """Reset the waveform plot"""
        try:
            if self.main_ax is not None:
                self.main_ax.clear()
                self.main_ax.set_xlabel("Time (s)")
                self.main_ax.set_ylabel("Voltage (V)")
                self.main_ax.set_title("Waveform Display")
                self.main_ax.grid(True, alpha=0.3)
                if self.main_canvas is not None:
                    self.main_canvas.draw()
        except Exception as e:
            print(f"Error resetting waveform plot: {e}")
            
    def toggle_waveform_plot(self):
        """Toggle waveform plot visibility"""
        try:
            self.waveform_visible = not self.waveform_visible
            if self.main_canvas is not None:
                if self.waveform_visible:
                    self.main_canvas.get_tk_widget().pack(fill="both", expand=True)
                else:
                    self.main_canvas.get_tk_widget().pack_forget()
            print(f"Waveform plot visibility: {self.waveform_visible}")
        except Exception as e:
            print(f"Error toggling waveform plot: {e}") 