import tkinter as tk
from tkinter import messagebox
import os

# Import the classes that WindowManager needs to instantiate
from TestPanels_AI_AO import AnalogInputPanel, AnalogOutputPanel
from SLIC_Control import SLICSequenceControl
from Polarization_Calc import PolarizationApp
from FullFlowSystem import FullFlowSystem
from Virtual_Testing_Panel import VirtualTestingPanel


class WindowManager:
    """Manages detached windows and panel creation"""
    
    def __init__(self, parent):
        self.parent = parent
        self.detached_windows = {}
        
    def open_panel(self, panel_type):
        """Open various test panels"""
        try:
            if panel_type == "ai":
                AnalogInputPanel(self.parent, embedded=False)
            elif panel_type == "ao":
                AnalogOutputPanel(self.parent, embedded=False)
            elif panel_type == "slic":
                SLICSequenceControl(self.parent, embedded=False)
            elif panel_type == "polarization":
                PolarizationApp(self.parent, embedded=False)
            elif panel_type == "full_flow":
                self._open_full_flow_system()
            elif panel_type == "virtual":
                self._toggle_virtual_panel()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {panel_type} panel: {e}")
    
    def _open_full_flow_system(self):
        """Open the Full Flow System window"""
        if not hasattr(self.parent, 'full_flow_window') or self.parent.full_flow_window is None:
            self.parent.full_flow_window = tk.Toplevel(self.parent)
            self.parent.full_flow_window.title("Full Flow System")
            self.parent.full_flow_window.geometry("800x600")
            
            # Create the FullFlowSystem instance in the new window
            full_flow_app = FullFlowSystem(self.parent.full_flow_window)
            full_flow_app.pack(fill="both", expand=True)
            
            # Handle window close event
            def on_closing():
                self.parent.full_flow_window.destroy()
                self.parent.full_flow_window = None
            
            self.parent.full_flow_window.protocol("WM_DELETE_WINDOW", on_closing)
        else:
            # Bring existing window to front
            self.parent.full_flow_window.lift()
            self.parent.full_flow_window.focus_force()
    
    def _toggle_virtual_panel(self):
        """Toggle the Virtual Testing Environment window"""
        if self.parent.virtual_panel is None or not self.parent.virtual_panel.winfo_exists():
            self.parent.virtual_panel = VirtualTestingPanel(self.parent, embedded=False)
        else:
            if hasattr(self.parent.virtual_panel, 'toplevel') and self.parent.virtual_panel.toplevel:
                self.parent.virtual_panel.toplevel.destroy()
            else:
                self.parent.virtual_panel.destroy()
            self.parent.virtual_panel = None 