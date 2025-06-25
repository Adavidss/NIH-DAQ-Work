import tkinter as tk


class TooltipManager:
    """Manages all tooltip functionality across the application"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def add_virtual_testing_tooltips(self, virtual_panel):
        """Add comprehensive tooltips to Virtual Testing Environment components"""
        try:
            from ToolTip import ToolTip
            
            # Add tooltips to main Virtual Testing panel if it has UI components
            if hasattr(virtual_panel, 'main_canvas'):
                ToolTip(virtual_panel.main_canvas, 
                       "VIRTUAL TESTING CANVAS: Interactive SABRE system visualization.\n"
                       "• Click on hourglasses to toggle individual valves\n"
                       "• Visual feedback shows current valve states\n"
                       "• Green = valve open (HIGH), Red = valve closed (LOW)\n"
                       "• Real-time system state monitoring", 
                       parent=self.parent)
            
            # Add tooltips to control buttons if they exist
            for child in virtual_panel.winfo_children():
                if isinstance(child, tk.Button):
                    button_text = child.cget('text') if hasattr(child, 'cget') else ""
                    if "Start" in button_text:
                        ToolTip(child, 
                               "START SEQUENCE: Begin automated valve sequence.\n"
                               "• Runs predefined activation or bubbling sequence\n"
                               "• Visual indicators show progress\n"
                               "• Automatically returns to initial state when complete", 
                               parent=self.parent)
                    elif "Stop" in button_text:
                        ToolTip(child, 
                               "STOP SEQUENCE: Halt current automated sequence.\n"
                               "• Immediately stops all running sequences\n"
                               "• Returns system to safe initial state\n"
                               "• Use for emergency stops or sequence interruption", 
                               parent=self.parent)
                    elif "Load" in button_text:
                        ToolTip(child, 
                               "LOAD CONFIG: Apply a specific system configuration.\n"
                               "• Loads valve states from configuration files\n"
                               "• Updates both visual display and hardware\n"
                               "• Available configs: Initial, Activation, Bubbling, Transfer", 
                               parent=self.parent)
                        
        except Exception as e:
            print(f"Error adding virtual testing tooltips: {e}")
            
    def add_full_flow_tooltips(self, full_flow_panel):
        """Add comprehensive tooltips to Full Flow System components"""
        try:
            from ToolTip import ToolTip
            
            # Add tooltip to the main canvas
            if hasattr(full_flow_panel, 'main_canvas'):
                ToolTip(full_flow_panel.main_canvas, 
                       "FULL FLOW SYSTEM: Complete SABRE flow path visualization.\n"
                       "• Shows entire gas and liquid flow network\n"
                       "• Interactive valve controls with visual feedback\n"
                       "• Real-time flow direction and state indicators\n"
                       "• Monitor complete system flow dynamics", 
                       parent=self.parent)
            
            # Add tooltips to any control buttons
            for child in full_flow_panel.winfo_children():
                if isinstance(child, tk.Button):
                    button_text = child.cget('text') if hasattr(child, 'cget') else ""
                    if "Reset" in button_text:
                        ToolTip(child, 
                               "RESET SYSTEM: Return all valves to initial positions.\n"
                               "• Sets all valves to safe default states\n"
                               "• Clears any active sequences\n"
                               "• Prepares system for new operations", 
                               parent=self.parent)
                               
        except Exception as e:
            print(f"Error adding full flow tooltips: {e}")
            
    def add_analog_input_tooltips(self, ai_panel):
        """Add comprehensive tooltips to Analog Input panel components"""
        try:
            from ToolTip import ToolTip
            
            # Add tooltips to the main panel
            ToolTip(ai_panel, 
                   "ANALOG INPUT MONITORING: Real-time sensor data acquisition.\n"
                   "• Monitor voltage levels from connected sensors\n"
                   "• Temperature, pressure, and field measurements\n"
                   "• Configurable sampling rates and ranges\n"
                   "• Live data plotting and logging capabilities", 
                   parent=self.parent)
            
            # Add tooltips to specific input channels if they exist
            for child in ai_panel.winfo_children():
                if isinstance(child, tk.Frame):
                    for subchild in child.winfo_children():
                        if isinstance(subchild, tk.Label):
                            label_text = subchild.cget('text') if hasattr(subchild, 'cget') else ""
                            if "AI" in label_text and any(char.isdigit() for char in label_text):
                                ToolTip(subchild, 
                                       f"ANALOG INPUT CHANNEL: {label_text}\n"
                                       "• Real-time voltage measurement\n"
                                       "• Configurable input range and filtering\n"
                                       "• Used for sensor data acquisition\n"
                                       "• Connects to temperature, pressure, or field sensors", 
                                       parent=self.parent)
                        elif isinstance(subchild, tk.Button):
                            button_text = subchild.cget('text') if hasattr(subchild, 'cget') else ""
                            if "Start" in button_text:
                                ToolTip(subchild, 
                                       "START MONITORING: Begin continuous data acquisition.\n"
                                       "• Starts real-time sensor data collection\n"
                                       "• Updates display with live measurements\n"
                                       "• Configurable sampling rate and duration", 
                                       parent=self.parent)
                            elif "Stop" in button_text:
                                ToolTip(subchild, 
                                       "STOP MONITORING: End data acquisition.\n"
                                       "• Stops continuous sensor monitoring\n"
                                       "• Preserves collected data for analysis\n"
                                       "• Frees DAQ resources for other operations", 
                                       parent=self.parent)
                               
        except Exception as e:
            print(f"Error adding analog input tooltips: {e}")
            
    def add_analog_output_tooltips(self, ao_panel):
        """Add comprehensive tooltips to Analog Output panel components"""
        try:
            from ToolTip import ToolTip
            
            # Add tooltip to the main panel
            ToolTip(ao_panel, 
                   "ANALOG OUTPUT CONTROL: Manual control of analog output channels.\n"
                   "• Set precise voltage levels on AO channels\n"
                   "• Control magnetic field coils and other devices\n"
                   "• Real-time voltage adjustment and monitoring\n"
                   "• Safety limits and emergency stop capabilities", 
                   parent=self.parent)
            
            # Add tooltips to output controls if they exist
            for child in ao_panel.winfo_children():
                if isinstance(child, tk.Frame):
                    for subchild in child.winfo_children():
                        if isinstance(subchild, tk.Label):
                            label_text = subchild.cget('text') if hasattr(subchild, 'cget') else ""
                            if "AO" in label_text and any(char.isdigit() for char in label_text):
                                ToolTip(subchild, 
                                       f"ANALOG OUTPUT CHANNEL: {label_text}\n"
                                       "• Precision voltage output control\n"
                                       "• Typically ±10V range with high resolution\n"
                                       "• Used for magnetic field coil control\n"
                                       "• Real-time voltage adjustment capabilities", 
                                       parent=self.parent)
                        elif isinstance(subchild, tk.Entry):
                            ToolTip(subchild, 
                                   "VOLTAGE SETTING: Enter desired output voltage.\n"
                                   "• Specify exact voltage level to output\n"
                                   "• Typical range: -10V to +10V\n"
                                   "• High precision for sensitive applications\n"
                                   "• Press Enter or click Set to apply", 
                                   parent=self.parent)
                               
        except Exception as e:
            print(f"Error adding analog output tooltips: {e}") 