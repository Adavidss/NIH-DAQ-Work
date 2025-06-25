import tkinter as tk  # Ensure tkinter is imported for the tooltip functionality

# ==== ENHANCED TOOLTIP CLASS ==============================
class ToolTip:
    """Enhanced tooltip implementation for tkinter widgets with multi-tab support"""
    
    # Class-level registry for all tooltips
    _tooltip_registry = {}
    _global_enabled = True
    
    def __init__(self, widget, text, parent=None, tab_name=None):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.parent = parent  # Reference to main window for tooltip toggle check
        self.tab_name = tab_name
        self.widget_id = id(widget)
        
        # Register this tooltip
        if tab_name not in ToolTip._tooltip_registry:
            ToolTip._tooltip_registry[tab_name] = []
        ToolTip._tooltip_registry[tab_name].append(self)
        
        # Bind events
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<Motion>", self.on_motion)

    def on_enter(self, event=None):
        # Check if tooltips are enabled globally and for parent
        if not ToolTip._global_enabled:
            return
        if self.parent and hasattr(self.parent, 'tooltips_enabled') and not self.parent.tooltips_enabled.get():
            return
        self.show_tooltip()

    def on_leave(self, event=None):
        self.hide_tooltip()

    def on_motion(self, event=None):
        if self.tooltip_window:
            self.update_tooltip_position(event)

    def show_tooltip(self):
        if self.tooltip_window:
            return
        
        # Try to get widget position, with robust fallback
        try:
            if hasattr(self.widget, 'bbox'):
                bbox_result = self.widget.bbox("insert")
                if bbox_result and len(bbox_result) >= 4:
                    x, y, _, _ = bbox_result
                else:
                    x, y = 0, 0
            else:
                x, y = 0, 0
        except:
            x, y = 0, 0
        
        # Calculate tooltip position relative to widget
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        # Enhanced tooltip styling
        label = tk.Label(self.tooltip_window, text=self.text, 
                        background="#ffffe0", relief="solid", borderwidth=1,
                        font=("Arial", 8), wraplength=200, justify="left")
        label.pack()
        
        # Add tab information if available
        if self.tab_name:
            tab_label = tk.Label(self.tooltip_window, text=f"Tab: {self.tab_name}",
                               background="#e0e0e0", relief="solid", borderwidth=1,
                               font=("Arial", 7), fg="gray")
            tab_label.pack()

    def update_tooltip_position(self, event):
        if self.tooltip_window:
            x = self.widget.winfo_rootx() + event.x + 15
            y = self.widget.winfo_rooty() + event.y + 15
            self.tooltip_window.wm_geometry(f"+{x}+{y}")

    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    @classmethod
    def register_widget_tooltip(cls, widget, text, parent=None, tab_name=None):
        """Register a tooltip for any widget on any tab"""
        return cls(widget, text, parent, tab_name)
    
    @classmethod
    def enable_all_tooltips(cls):
        """Enable all tooltips globally"""
        cls._global_enabled = True
    
    @classmethod
    def disable_all_tooltips(cls):
        """Disable all tooltips globally"""
        cls._global_enabled = False
        # Hide any currently visible tooltips
        for tab_tooltips in cls._tooltip_registry.values():
            for tooltip in tab_tooltips:
                tooltip.hide_tooltip()
    
    @classmethod
    def toggle_tooltips_for_tab(cls, tab_name, enabled):
        """Toggle tooltips for a specific tab"""
        if tab_name in cls._tooltip_registry:
            for tooltip in cls._tooltip_registry[tab_name]:
                if enabled:
                    # Re-enable event bindings
                    tooltip.widget.bind("<Enter>", tooltip.on_enter)
                    tooltip.widget.bind("<Leave>", tooltip.on_leave)
                    tooltip.widget.bind("<Motion>", tooltip.on_motion)
                else:
                    # Hide current tooltip and disable events
                    tooltip.hide_tooltip()
                    tooltip.widget.unbind("<Enter>")
                    tooltip.widget.unbind("<Leave>")
                    tooltip.widget.unbind("<Motion>")
    
    @classmethod
    def get_tooltip_count(cls, tab_name=None):
        """Get the number of registered tooltips for a tab or all tabs"""
        if tab_name:
            return len(cls._tooltip_registry.get(tab_name, []))
        else:
            return sum(len(tooltips) for tooltips in cls._tooltip_registry.values())
    
    @classmethod
    def cleanup_destroyed_widgets(cls):
        """Clean up tooltips for destroyed widgets"""
        for tab_name in list(cls._tooltip_registry.keys()):
            cls._tooltip_registry[tab_name] = [
                tooltip for tooltip in cls._tooltip_registry[tab_name]
                if tooltip.widget.winfo_exists()
            ]
