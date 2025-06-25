import tkinter as tk
import tkinter.ttk as ttk


class ThemeManager:
    """Manages application themes and color schemes"""
    def __init__(self, parent):
        self.parent = parent
        self.current_theme = "Normal"
        
        # Define theme color schemes
        self.themes = {
            "Light": {
                "bg": "#f5f5f5",
                "fg": "#2c2c2c", 
                "button_bg": "#e8e8e8",
                "button_fg": "#2c2c2c",
                "button_active_bg": "#d0d0d0",
                "frame_bg": "#ffffff",
                "entry_bg": "#ffffff",
                "entry_fg": "#2c2c2c",
                "label_bg": "#f5f5f5",
                "label_fg": "#2c2c2c",
                "plot_bg": "#ffffff",
                "grid_color": "#cccccc",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "status_bg": "#f0f0f0",
                "status_fg": "#2c2c2c"
            },
            "Dark": {
                "bg": "#2d2d2d",
                "fg": "#e0e0e0",
                "button_bg": "#404040", 
                "button_fg": "#e0e0e0",
                "button_active_bg": "#505050",
                "frame_bg": "#3d3d3d",
                "entry_bg": "#404040",
                "entry_fg": "#e0e0e0",
                "label_bg": "#2d2d2d",
                "label_fg": "#e0e0e0",
                "plot_bg": "#2d2d2d",
                "grid_color": "#505050",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "status_bg": "#404040",
                "status_fg": "#e0e0e0"
            },
            "High-Contrast": {
                "bg": "#000000",
                "fg": "#ffffff",
                "button_bg": "#333333",
                "button_fg": "#ffffff", 
                "button_active_bg": "#555555",
                "frame_bg": "#1a1a1a",
                "entry_bg": "#333333",
                "entry_fg": "#ffffff",
                "label_bg": "#000000",
                "label_fg": "#ffffff",
                "plot_bg": "#000000",
                "grid_color": "#666666",
                "select_bg": "#ffffff",
                "select_fg": "#000000",
                "status_bg": "#333333",
                "status_fg": "#ffffff"
            },
            "Normal": {
                "bg": "#d9d9d9",
                "fg": "#000000",
                "button_bg": "#e1e1e1",
                "button_fg": "#000000",
                "button_active_bg": "#d1d1d1", 
                "frame_bg": "#d9d9d9",
                "entry_bg": "#ffffff",
                "entry_fg": "#000000",
                "label_bg": "#d9d9d9",
                "label_fg": "#000000",
                "plot_bg": "#d9d9d9",
                "grid_color": "#999999",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "status_bg": "#e0e0e0",
                "status_fg": "#000000"
            }
        }
        
        # Control buttons that should keep their original colors
        self.protected_buttons = ["Start", "Activate", "Test Field", "SCRAM"]
        
        # Initialize colors
        self.colors = self.get_theme_colors()
        
    def get_theme_colors(self, theme_name=None):
        """Get color scheme for specified theme"""
        theme_name = theme_name or self.current_theme
        return self.themes.get(theme_name, self.themes["Normal"])
        
    def color(self, key: str) -> str:
        """Return the active palette colour (bg, fg, etc.)."""
        return self.get_theme_colors()[key]
        
    def apply_theme(self, theme_name):
        """Apply theme to the entire application"""
        if theme_name not in self.themes:
            print(f"Unknown theme: {theme_name}")
            return
            
        self.current_theme = theme_name
        colors = self.get_theme_colors(theme_name)
        
        print(f"Applying {theme_name} theme...")
        
        # Apply theme to the root window first
        self._apply_theme_to_root(colors)
        
        # Apply theme to main window and all widgets
        self._apply_theme_recursive(self.parent, colors)
        
        # Apply theme to specific application elements
        self._apply_theme_to_specific_elements(colors)
        
        # Apply theme to ttk widgets (notebook tabs, etc.)
        self._apply_ttk_theme(colors)
        
        # Update plot backgrounds if they exist
        self._update_plot_themes(colors)
        
        print(f"{theme_name} theme applied successfully")
        
    def _apply_theme_to_root(self, colors):
        """Apply theme to the root window and main application background"""
        try:
            # Get the root window
            root = self.parent.winfo_toplevel()
            root.configure(bg=colors["bg"])
            
            # Apply to main parent widget
            if hasattr(self.parent, 'configure'):
                self.parent.configure(bg=colors["bg"])
            
        except Exception as e:
            print(f"Error applying theme to root: {e}")
            
    def _apply_theme_to_specific_elements(self, colors):
        """Apply theme to specific named application elements"""
        try:
            # Apply to status bar
            if hasattr(self.parent, 'status_timer_bar'):
                self.parent.status_timer_bar.configure(bg=colors["status_bg"])
                
            if hasattr(self.parent, 'status_label'):
                self.parent.status_label.configure(
                    bg=colors["status_bg"], 
                    fg=colors["status_fg"]
                )
                
            # Apply to notebook container
            if hasattr(self.parent, 'notebook_container'):
                self.parent.notebook_container.configure(bg=colors["frame_bg"])
                
            # Apply to more button
            if hasattr(self.parent, 'more_btn'):
                # TTK widget - will be handled by ttk theme
                pass
                
            # Apply to overflow menu
            if hasattr(self.parent, 'overflow_menu'):
                self.parent.overflow_menu.configure(
                    bg=colors["frame_bg"],
                    fg=colors["label_fg"],
                    activebackground=colors["button_active_bg"],
                    activeforeground=colors["button_fg"]
                )
                
        except Exception as e:
            print(f"Error applying theme to specific elements: {e}")
            
    def _apply_ttk_theme(self, colors):
        """Apply theme to ttk widgets like notebook tabs"""
        try:
            # Create or get the style object
            style = ttk.Style()
            
            # Configure notebook and tab styles
            style.configure("TNotebook", background=colors["frame_bg"])
            style.configure("TNotebook.Tab", 
                          background=colors["button_bg"],
                          foreground=colors["button_fg"],
                          padding=[12, 4])
            
            # Configure tab selection and hover states
            style.map("TNotebook.Tab",
                     background=[("selected", colors["button_active_bg"]), 
                               ("active", colors["button_active_bg"])],
                     foreground=[("selected", colors["button_fg"]), 
                               ("active", colors["button_fg"])])
            
            # Configure dark tab style specifically
            style.configure("DarkTab.TNotebook", background=colors["frame_bg"])
            style.configure("DarkTab.TNotebook.Tab", 
                          background=colors["button_bg"],
                          foreground=colors["button_fg"],
                          padding=[12, 4])
            
            style.map("DarkTab.TNotebook.Tab",
                     background=[("selected", colors["button_active_bg"]), 
                               ("active", colors["button_active_bg"])],
                     foreground=[("selected", colors["button_fg"]), 
                               ("active", colors["button_fg"])])
            
            # Configure other ttk widgets
            style.configure("TFrame", background=colors["frame_bg"])
            style.configure("TLabel", background=colors["label_bg"], foreground=colors["label_fg"])
            style.configure("TButton", background=colors["button_bg"], foreground=colors["button_fg"])
            style.configure("TEntry", fieldbackground=colors["entry_bg"], foreground=colors["entry_fg"])
            style.configure("TCombobox", fieldbackground=colors["entry_bg"], foreground=colors["entry_fg"])
            style.configure("TLabelframe", background=colors["frame_bg"], foreground=colors["label_fg"])
            style.configure("TLabelframe.Label", background=colors["frame_bg"], foreground=colors["label_fg"])
            style.configure("TMenubutton", background=colors["button_bg"], foreground=colors["button_fg"])
            style.configure("Horizontal.TScrollbar", background=colors["frame_bg"])
            style.configure("Vertical.TScrollbar", background=colors["frame_bg"])
            
            # Configure button states
            style.map("TButton",
                     background=[("active", colors["button_active_bg"])],
                     foreground=[("active", colors["button_fg"])])
            
            # force redraw
            style.theme_use(style.theme_use())
            
        except Exception as e:
            print(f"Error applying ttk theme: {e}")
        
    def _apply_theme_recursive(self, widget, colors):
        """Recursively apply theme to widget and all children"""
        try:
            widget_class = widget.winfo_class()
            widget_text = ""
            
            # Get widget text if it has text attribute
            try:
                if hasattr(widget, 'cget'):
                    widget_text = widget.cget('text')
            except:
                pass
                
            # Skip protected control buttons
            if widget_class == 'Button' and widget_text in self.protected_buttons:
                # Skip theme application for protected buttons - keep original colors
                pass
            elif widget_class in ('Frame', 'TFrame', 'Toplevel', 'Tk'):
                widget.configure(bg=colors["frame_bg"])
            elif widget_class in ('LabelFrame', 'TLabelframe'):
                widget.configure(bg=colors["frame_bg"], fg=colors["label_fg"])
            elif widget_class in ('Label', 'TLabel'):
                widget.configure(bg=colors["label_bg"], fg=colors["label_fg"])
            elif widget_class == 'Button':
                widget.configure(
                    bg=colors["button_bg"], 
                    fg=colors["button_fg"],
                    activebackground=colors["button_active_bg"],
                    activeforeground=colors["button_fg"]
                )
            elif widget_class in ('Entry', 'TEntry'):
                widget.configure(
                    bg=colors["entry_bg"], 
                    fg=colors["entry_fg"],
                    insertbackground=colors["entry_fg"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_fg"]
                )
            elif widget_class in ('Combobox', 'TCombobox'):
                # TTK Combobox handled by style engine
                pass
            elif widget_class == 'Text':
                widget.configure(
                    bg=colors["entry_bg"], 
                    fg=colors["entry_fg"],
                    insertbackground=colors["entry_fg"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_fg"]
                )
            elif widget_class == 'Listbox':
                widget.configure(
                    bg=colors["entry_bg"], 
                    fg=colors["entry_fg"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_fg"]
                )
            elif widget_class == 'Canvas':
                widget.configure(bg=colors["plot_bg"])
            elif widget_class == 'Menu':
                widget.configure(
                    bg=colors["frame_bg"],
                    fg=colors["label_fg"],
                    activebackground=colors["button_active_bg"],
                    activeforeground=colors["button_fg"]
                )
            elif widget_class == 'Menubutton':
                widget.configure(
                    bg=colors["button_bg"],
                    fg=colors["button_fg"],
                    activebackground=colors["button_active_bg"]
                )
            elif widget_class == 'Scale':
                widget.configure(
                    bg=colors["frame_bg"],
                    fg=colors["label_fg"],
                    activebackground=colors["button_active_bg"],
                    troughcolor=colors["entry_bg"]
                )
            elif widget_class == 'Scrollbar':
                widget.configure(
                    bg=colors["frame_bg"],
                    activebackground=colors["button_active_bg"],
                    troughcolor=colors["entry_bg"]
                )
            elif widget_class == 'Checkbutton':
                widget.configure(
                    bg=colors["frame_bg"],
                    fg=colors["label_fg"],
                    activebackground=colors["button_active_bg"],
                    selectcolor=colors["entry_bg"]
                )
            elif widget_class == 'Radiobutton':
                widget.configure(
                    bg=colors["frame_bg"],
                    fg=colors["label_fg"],
                    activebackground=colors["button_active_bg"],
                    selectcolor=colors["entry_bg"]
                )
            elif widget_class == 'LabelFrame':
                widget.configure(
                    bg=colors["frame_bg"],
                    fg=colors["label_fg"]
                )
            elif widget_class == 'PanedWindow':
                widget.configure(bg=colors["frame_bg"])
            elif widget_class.startswith("T"):
                # generic ttk widget → handled purely by style engine
                pass
                
        except Exception as e:
            # Skip widgets that don't support color configuration
            pass
            
        # Apply theme to all child widgets
        try:
            for child in widget.winfo_children():
                self._apply_theme_recursive(child, colors)
        except:
            pass
            
    def _update_plot_themes(self, colors):
        """Update matplotlib plot themes"""
        try:
            # Update main plot if it exists
            if (hasattr(self.parent, 'plot_controller') and 
                hasattr(self.parent.plot_controller, 'main_ax') and 
                self.parent.plot_controller.main_ax is not None):
                
                ax = self.parent.plot_controller.main_ax
                fig = self.parent.plot_controller.main_fig
                
                if fig and ax:
                    # Update plot colors
                    fig.patch.set_facecolor(colors["plot_bg"])
                    ax.set_facecolor(colors["plot_bg"])
                    ax.tick_params(colors=colors["fg"], labelsize=8)
                    ax.xaxis.label.set_color(colors["fg"])
                    ax.yaxis.label.set_color(colors["fg"])
                    ax.title.set_color(colors["fg"])
                    ax.grid(True, color=colors["grid_color"], alpha=0.3)
                    
                    # Update spine colors
                    for spine in ax.spines.values():
                        spine.set_color(colors["fg"])
                    
                    # Refresh canvas if available
                    if (hasattr(self.parent.plot_controller, 'main_canvas') and 
                        self.parent.plot_controller.main_canvas):
                        self.parent.plot_controller.main_canvas.draw()
            
            # Update field plot if it exists
            if (hasattr(self.parent, 'plot_controller') and 
                hasattr(self.parent.plot_controller, 'field_ax') and 
                self.parent.plot_controller.field_ax is not None):
                
                ax = self.parent.plot_controller.field_ax
                fig = self.parent.plot_controller.field_fig
                
                if fig and ax:
                    # Update field plot colors
                    fig.patch.set_facecolor(colors["plot_bg"])
                    ax.set_facecolor(colors["plot_bg"])
                    ax.tick_params(colors=colors["fg"], labelsize=8)
                    ax.xaxis.label.set_color(colors["fg"])
                    ax.yaxis.label.set_color(colors["fg"])
                    ax.title.set_color(colors["fg"])
                    ax.grid(True, color=colors["grid_color"], alpha=0.3)
                    
                    # Update spine colors
                    for spine in ax.spines.values():
                        spine.set_color(colors["fg"])
                    
                    # Refresh canvas if available
                    if (hasattr(self.parent.plot_controller, 'field_canvas') and 
                        self.parent.plot_controller.field_canvas):
                        self.parent.plot_controller.field_canvas.draw()
                        
        except Exception as e:
            print(f"Error updating plot themes: {e}") 