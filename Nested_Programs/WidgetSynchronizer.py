import tkinter as tk
from tkinter import ttk


class WidgetSynchronizer:
    """Handles synchronization between original and cloned widgets"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def sync_widget_values(self, src_frame, clone_frame):
        """Recursively sync widget values between original and clone frames"""
        try:
            src_children = src_frame.winfo_children()
            clone_children = clone_frame.winfo_children()
            
            for src_widget, clone_widget in zip(src_children, clone_children):
                # Sync Entry widgets
                if isinstance(src_widget, tk.Entry) and isinstance(clone_widget, tk.Entry):
                    def sync_entry(var_name, index, mode, src=src_widget, clone=clone_widget):
                        try:
                            if src.get() != clone.get():
                                clone.delete(0, tk.END)
                                clone.insert(0, src.get())
                        except:
                            pass
                    
                    src_var = tk.StringVar()
                    src_var.trace_add("write", sync_entry)
                    src_widget.config(textvariable=src_var)
                    
                # Sync Combobox widgets
                elif isinstance(src_widget, ttk.Combobox) and isinstance(clone_widget, ttk.Combobox):
                    def sync_combo(var_name, index, mode, src=src_widget, clone=clone_widget):
                        try:
                            if src.get() != clone.get():
                                clone.set(src.get())
                        except:
                            pass
                    
                    if hasattr(src_widget, 'textvariable') and src_widget['textvariable']:
                        src_widget['textvariable'].trace_add("write", sync_combo)
                
                # Recursively process child widgets
                if src_widget.winfo_children() and clone_widget.winfo_children():
                    self.sync_widget_values(src_widget, clone_widget)
                    
        except Exception as e:
            print(f"Error syncing widget values: {e}") 