import tkinter as tk
from tkinter import messagebox


class UIManager:
    """Handles UI creation and styling"""
    def __init__(self, parent):
        self.parent = parent
        
    def create_control_button(self, parent, text, color, command):
        """Create a control button with consistent styling"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 10, 'bold'),
                          width=12, height=2,
                          relief="raised", bd=2)
        
        # Set color scheme based on button type
        color_schemes = {
            "green": {"bg": "#4CAF50", "fg": "white", "activebackground": "#45a049"},
            "blue": {"bg": "#2196F3", "fg": "white", "activebackground": "#1976D2"},
            "orange": {"bg": "#FF9800", "fg": "white", "activebackground": "#F57C00"},
            "red": {"bg": "#F44336", "fg": "white", "activebackground": "#D32F2F"}
        }
        
        if color in color_schemes:
            button.config(**color_schemes[color])
        
        button.pack(side="left", padx=5, pady=2)
        return button
        
    def show_error_popup(self, missing_params):
        """Show error popup for missing parameters"""
        if missing_params:
            error_msg = "Missing required parameters:\n" + "\n".join(f"• {param}" for param in missing_params)
            messagebox.showwarning("Missing Parameters", error_msg)
        
    def create_quadrant_button(self, parent, text, color, command, row, col):
        """Create a quadrant experiment control button with consistent styling"""
        button = tk.Button(parent, text=text, 
                          command=command,
                          font=('Arial', 8, 'bold'),
                          relief="raised", bd=3,
                          width=8, height=1)
        
        # Hard-coded button palette
        color_schemes = {
            "Activate": {"bg": "#2E7D32", "fg": "white", "activebackground": "#2E7D32"},
            "Start": {"bg": "#1565C0", "fg": "white", "activebackground": "#1565C0"},
            "Test Field": {"bg": "#EF6C00", "fg": "white", "activebackground": "#EF6C00"},
            "SCRAM": {"bg": "#B71C1C", "fg": "white", "activebackground": "#B71C1C"}
        }
        
        if text in color_schemes:
            button.config(**color_schemes[text])
            
        button.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
        return button 