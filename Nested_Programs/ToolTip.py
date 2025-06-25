import tkinter as tk  # Ensure tkinter is imported for the tooltip functionality

# ==== STANDALONE TOOLTIP CLASS ==============================
class ToolTip:
    """Custom tooltip implementation for tkinter widgets"""
    def __init__(self, widget, text, parent=None):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.parent = parent  # Reference to main window for tooltip toggle check
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<Motion>", self.on_motion)

    def on_enter(self, event=None):
        # Check if tooltips are enabled before showing
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

        label = tk.Label(self.tooltip_window, text=self.text, 
                        background="#ffffe0", relief="solid", borderwidth=1,
                        font=("Arial", 8), wraplength=200)
        label.pack()

    def update_tooltip_position(self, event):
        if self.tooltip_window:
            x = self.widget.winfo_rootx() + event.x + 15
            y = self.widget.winfo_rooty() + event.y + 15
            self.tooltip_window.wm_geometry(f"+{x}+{y}")

    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
