import json
from Utility_Functions import build_composite_waveform


class WaveformController:
    """Handles live waveform plotting and management"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def refresh_live_waveform(self):
        """Refresh the live waveform plot"""
        try:
            if not hasattr(self.parent, 'polarization_method_file') or not self.parent.polarization_method_file:
                return
                
            with open(self.parent.polarization_method_file, 'r') as f:
                cfg = json.load(f)
                
            # Build the waveform buffer
            if isinstance(cfg, dict) and cfg.get("type") == "SLIC_sequence":
                buf, sr = build_composite_waveform(cfg)
            else:
                initial_voltage = cfg.get("initial_voltage", 0.0)
                buf, sr = build_composite_waveform(cfg["ramp_sequences"], dc_offset=initial_voltage)
            
            # Clear and re-plot using plot controller
            if hasattr(self.parent, 'plot_controller') and self.parent.plot_controller:
                self.parent.plot_controller.plot_waveform_buffer(buf, sr)
                print(f"Waveform plot updated: {len(buf)} samples, {buf.max():.3f}V max, {buf.min():.3f}V min")
            
            # Force GUI update to ensure the plot is refreshed
            self.parent.update_idletasks()
            self.parent.after_idle(lambda: self.parent.update())
                    
        except Exception as e:
            print(f"Error refreshing live waveform: {e}")
            
    def force_waveform_update(self):
        """Force an immediate waveform plot update with enhanced refresh"""
        try:
            # Call the standard refresh method
            self.refresh_live_waveform()
            
            # Additional forced updates to ensure visibility across tabs
            if hasattr(self.parent, 'plot_controller') and self.parent.plot_controller:
                if hasattr(self.parent.plot_controller, 'main_canvas') and self.parent.plot_controller.main_canvas:
                    # Force multiple canvas refresh operations
                    self.parent.plot_controller.main_canvas.draw()
                    self.parent.plot_controller.main_canvas.draw_idle()
                    self.parent.after(10, lambda: self.parent.plot_controller.main_canvas.draw() if 
                              hasattr(self.parent.plot_controller.main_canvas, 'draw') else None)
                    
            # Force GUI refresh
            self.parent.update_idletasks()
            self.parent.update()
            
            print("Force waveform update completed")
            
        except Exception as e:
            print(f"Error in force waveform update: {e}")
            
    def toggle_waveform_plot(self):
        """Toggle waveform plot visibility"""
        if hasattr(self.parent, 'plot_controller'):
            self.parent.plot_controller.toggle_waveform_plot()

    def plot_waveform_buffer(self, buf, sr):
        """Plot waveform buffer for preview"""
        if hasattr(self.parent, 'plot_controller'):
            self.parent.plot_controller.plot_waveform_buffer(buf, sr)

    def reset_waveform_plot(self):
        """Reset waveform plot"""
        if hasattr(self.parent, 'plot_controller'):
            self.parent.plot_controller.reset_waveform_plot() 