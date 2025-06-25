import math
import statistics
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

# Create data directory for saving/loading datasets
DATA_DIR = Path(r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationDataSets")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Domain‑specific calculation class
# ---------------------------------------------------------------------------

class PolarizationCalculator:
    """Class containing polarization calculation methods."""
    
    @staticmethod
    def thermal_polarization(hbar, gamma, B0, k_B, T):
        """Compute the Boltzmann thermal polarization factor (tanh term)."""
        return math.tanh((gamma * B0 * hbar) / (2 * k_B * T))

    @staticmethod
    def percent_polarization(A0, sa_ratio, conc_ref, conc_sample, signal_sample, signal_ref):
        """Generic formula used for both free and bound species.

        Parameters
        ----------
        A0            : float
            Thermal polarization factor (dimensionless).
        sa_ratio      : float
            Signal‐averaging (SA) ratio between reference and sample spectra.
        conc_ref      : float
            Concentration of the reference (mM or arbitrary but consistent units).
        conc_sample   : float
            Concentration of the sample species (free or bound).
        signal_sample : float
            Integrated NMR signal (area or intensity) for the sample species.
        signal_ref    : float
            Integrated NMR signal for the reference.
        """
        return 100.0 * A0 * sa_ratio * (conc_ref / conc_sample) * (signal_sample / signal_ref)

# ---------------------------------------------------------------------------
# Tkinter GUI - Tab implementation
# ---------------------------------------------------------------------------

class PolarizationTab(ttk.Frame, PolarizationCalculator):
    """A single polarization calculation tab."""
    
    def __init__(self, parent, tab_id=1):
        ttk.Frame.__init__(self, parent)
        
        self.parent = parent
        self.tab_id = tab_id
        self.title = f"Dataset {tab_id}"
        self.file_path = None  # Path to the loaded/saved dataset

        # Dictionary to store notes for data points
        self.data_point_notes = {}
        # Dataset-level notes
        self.dataset_notes = ""
        # Variable to track selected item in the tree
        self.selected_item = None
        # Track if best fit lines are currently shown
        self.best_fit_visible = False
        # Store the best fit line objects
        self.best_fit_lines = {'free': None, 'bound': None}

        self._create_constants_frame()
        self._create_data_tables()
        self._create_entry_frame()
        self._create_controls()
        self._create_plotting_area()
        self._create_best_fit_frame()
        self._setup_context_menu()

    # UI Setup Methods
    def _create_constants_frame(self):
        """Create the frame for constants and settings."""
        constants_frame = ttk.LabelFrame(self, text="Global Constants & Settings")
        constants_frame.pack(fill=tk.X, padx=10, pady=5)

        # Helper to make labeled entries
        def add_const(label, default, row, col):
            ttk.Label(constants_frame, text=label).grid(row=row, column=col * 2, sticky=tk.W, padx=4, pady=2)
            var = tk.StringVar(value=str(default))
            entry = ttk.Entry(constants_frame, width=12, textvariable=var)
            entry.grid(row=row, column=col * 2 + 1, padx=4, pady=2)
            return var

        # Physical constants
        self.hbar_var = add_const("ℏ (J·s)", f"{6.626e-34 / (2 * math.pi):.6e}", 0, 0)
        self.gamma_var = add_const("γ (rad·s⁻¹·T⁻¹)", "67280000", 0, 1)
        self.B0_var = add_const("B₀ (T)", "1.1", 0, 2)
        self.kB_var = add_const("k_B (J·K⁻¹)", f"{1.380649e-23:.6e}", 0, 3)
        self.sa_ratio_var = add_const("SA ratio", "1.03", 0, 4)
        
        # Experiment parameters
        self.T_var = add_const("T (K)", "278.0", 1, 0)
        self.conc_ref_var = add_const("Conc_ref", "", 1, 1)
        self.conc_free_var = add_const("Conc_free", "", 1, 2)
        self.conc_bound_var = add_const("Conc_bound", "", 1, 3)
        self.signal_ref_var = add_const("Signal_ref", "", 1, 4)
        
        # X-axis label
        self.x_label_var = add_const("X-axis label", "X (user‑defined)", 2, 0)

    def _create_data_tables(self):
        """Create the data tables for raw and averaged measurements."""
        table_frame = ttk.LabelFrame(self, text="Measurements (one row = one experiment)")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Container for both tables
        tables_container = ttk.Frame(table_frame)
        tables_container.pack(fill=tk.BOTH, expand=True)
        
        # Raw measurements table (left)
        self._create_raw_measurements_table(tables_container)
        
        # Averaged results table (right)
        self._create_averaged_results_table(tables_container)
        
    def _create_raw_measurements_table(self, parent):
        """Create the raw measurements table."""
        left_table_frame = ttk.Frame(parent)
        left_table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(left_table_frame, text="Raw Measurements", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)

        columns = ("X", "Signal_free", "Signal_bound", "P_free (%)", "P_bound (%)")
        self.tree = ttk.Treeview(left_table_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor=tk.CENTER)
            
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind('<Double-1>', self.on_cell_double_click)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(left_table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_averaged_results_table(self, parent):
        """Create the averaged results table."""
        right_table_frame = ttk.Frame(parent)
        right_table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        ttk.Label(right_table_frame, text="Averaged Results", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)

        avg_columns = ("X", "P_free_avg (%)", "P_free_std", "P_bound_avg (%)", "P_bound_std")
        self.avg_tree = ttk.Treeview(right_table_frame, columns=avg_columns, show="headings", height=8)
        
        for col in avg_columns:
            self.avg_tree.heading(col, text=col)
            self.avg_tree.column(col, width=100, anchor=tk.CENTER)
            
        self.avg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        avg_scrollbar = ttk.Scrollbar(right_table_frame, orient=tk.VERTICAL, command=self.avg_tree.yview)
        self.avg_tree.configure(yscroll=avg_scrollbar.set)
        avg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_entry_frame(self):
        """Create the data entry form for new points."""
        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create entry widgets for input columns
        input_columns = ("X", "Signal_free", "Signal_bound")
        self.entry_vars = {col: tk.StringVar() for col in input_columns}
        
        for i, col in enumerate(input_columns):
            ttk.Label(entry_frame, text=col).grid(row=0, column=2 * i, padx=2, pady=2)
            ttk.Entry(entry_frame, width=12, textvariable=self.entry_vars[col]).grid(row=0, column=2 * i + 1, padx=2, pady=2)

        ttk.Button(entry_frame, text="Add Data Point", command=self.add_datapoint).grid(
            row=1, column=0, columnspan=len(input_columns) * 2, pady=4
        )

    def _create_controls(self):
        """Create the control buttons."""
        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=10, pady=5)

        # Left-aligned buttons
        ttk.Button(controls, text="Compute & Plot", command=self.compute_and_plot).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Clear Data", command=self.clear_data).pack(side=tk.LEFT, padx=4)
        
        # Best fit buttons
        self.best_fit_btn = ttk.Button(controls, text="Best Fit Line", command=self.calculate_best_fit)
        self.best_fit_btn.pack(side=tk.LEFT, padx=4)
        
        self.toggle_fit_btn = ttk.Button(controls, text="Hide Best Fit", command=self.toggle_best_fit)
        self.toggle_fit_btn.pack(side=tk.LEFT, padx=4)
        self.toggle_fit_btn.config(state=tk.DISABLED)
        
        # Dataset notes button
        ttk.Button(controls, text="Dataset Notes", command=self.edit_dataset_notes).pack(side=tk.LEFT, padx=4)
        
        # Detach tab button (only when in a detached window)
        self.reattach_btn = ttk.Button(controls, text="Re-attach Tab", command=self.reattach_tab)
        # Only shown when detached

    def _create_plotting_area(self):
        """Create the matplotlib plotting area."""
        self.fig, self.ax = plt.subplots()
        self.ax.set_xlabel("X (user‑defined)")
        self.ax.set_ylabel("Percent polarization (%)")
        self.ax.grid(True, which="both", linestyle=":", linewidth=0.6)

        # Frame to hold the plot and toolbar
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Canvas and toolbar
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_frame)
        toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Status indicators at bottom
        self.note_indicator = ttk.Label(self.canvas_frame, text="", font=("TkDefaultFont", 9, "italic"))
        self.note_indicator.pack(side=tk.BOTTOM, anchor=tk.W)
        
        self.coord_label = ttk.Label(self.canvas_frame, text="Coordinates: ")
        self.coord_label.pack(side=tk.BOTTOM, anchor=tk.W)
        
        # Connect events
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)

    def _create_best_fit_frame(self):
        """Create frame for displaying best fit results."""
        self.best_fit_frame = ttk.LabelFrame(self, text="Line of Best Fit")
        self.best_fit_label = ttk.Label(
            self.best_fit_frame, 
            text="Calculate best fit line to see results", 
            font=("TkDefaultFont", 10)
        )
        self.best_fit_label.pack(fill=tk.X, padx=5, pady=5)
        
        # Hide initially
        self.best_fit_frame.pack_forget()

    def _setup_context_menu(self):
        """Setup right-click context menu for data points."""
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Add/Edit Note", command=self.add_edit_note)
        self.context_menu.add_command(label="View Note", command=self.view_note)
        self.context_menu.add_command(label="Delete Note", command=self.delete_note)

    # Event Handlers
    def on_hover(self, event):
        """Display coordinates when hovering over the plot."""
        if event.inaxes:
            self.coord_label.config(text=f"Coordinates: X={event.xdata:.3f}, Y={event.ydata:.3f}")
        else:
            self.coord_label.config(text="Coordinates: ")

    def on_cell_double_click(self, event):
        """Handle double-click on a table cell to edit its value."""
        # Identify the clicked item and column
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
            
        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        
        if not item:
            return
            
        # Get column index (removing the # prefix)
        col_idx = int(column.replace('#', '')) - 1
        
        # Only allow editing of input columns (X, Signal_free, Signal_bound)
        editable_cols = ["X", "Signal_free", "Signal_bound"]
        if col_idx >= len(editable_cols):
            messagebox.showinfo("Info", "This column is calculated and cannot be edited directly.", parent=self.get_window())
            return
            
        # Get current values from the row
        values = self.tree.item(item, 'values')
        
        # Show input dialog for editing
        col_name = editable_cols[col_idx]
        current_value = values[col_idx]
        new_value = simpledialog.askfloat(
            f"Edit {col_name}",
            f"Enter new value for {col_name}:",
            initialvalue=float(current_value),
            parent=self.get_window()
        )
        
        if new_value is not None:  # User clicked OK
            # Update the values list with the new value
            values_list = list(values)
            values_list[col_idx] = f"{new_value:.3f}"
            
            # Clear calculated values (will be recalculated)
            values_list[3] = ""  # P_free
            values_list[4] = ""  # P_bound
            
            # Update the tree item
            self.tree.item(item, values=values_list)

    def get_window(self):
        """Return the current window containing this tab."""
        return self.winfo_toplevel()

    # Tab detachment/reattachment
    def detach_tab(self):
        """Detach this tab into a new window."""
        # Create new window
        window = tk.Toplevel(self.parent)
        window.title(f"Percent Polarization Calculator - {self.title}")
        window.geometry("1242x828")
        
        # Reparent this frame to the new window
        self.pack_forget()  # Remove from notebook
        self.parent = window
        self.pack(fill=tk.BOTH, expand=True)  # Pack into new window
        
        # Show reattach button
        self.reattach_btn.pack(side=tk.RIGHT, padx=4)
        
        # Update the matplotlib canvas parent
        self.canvas.get_tk_widget().master = self.canvas_frame
        
        return window

    def reattach_tab(self):
        """Reattach this tab to the main notebook."""
        # Get the notebook from the main app
        app = self.get_window().master  # Main app is the master of the Toplevel
        notebook = app.notebook
        
        # Remove from toplevel window and add back to notebook
        self.pack_forget()
        self.reattach_btn.pack_forget()  # Hide reattach button
        self.parent = notebook
        notebook.add(self, text=self.title)
        notebook.select(self)
        
        # Close the detached window
        toplevel = self.get_window()
        if isinstance(toplevel, tk.Toplevel):
            toplevel.destroy()

    # File Operations
    def save_dataset(self, path=None):
        """Save the current dataset to a JSON file."""
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=DATA_DIR,
                parent=self.get_window(),
                title="Save Dataset"
            )
            
        if not path:
            return False  # User cancelled
            
        self.file_path = path
        
        try:
            # Build data structure
            data = {
                "metadata": {
                    "type": "Polarization Calculator Dataset",
                    "version": "1.0"
                },
                "constants": {
                    "hbar": self.hbar_var.get(),
                    "gamma": self.gamma_var.get(),
                    "B0": self.B0_var.get(),
                    "kB": self.kB_var.get(),
                    "sa_ratio": self.sa_ratio_var.get(),
                    "T": self.T_var.get(),
                    "conc_ref": self.conc_ref_var.get(),
                    "conc_free": self.conc_free_var.get(),
                    "conc_bound": self.conc_bound_var.get(),
                    "signal_ref": self.signal_ref_var.get(),
                    "x_label": self.x_label_var.get()
                },
                "dataset_notes": self.dataset_notes,
                "data_points": []
            }
            
            # Add data points
            for item in self.tree.get_children():
                values = self.tree.item(item, "values")
                point = {
                    "X": values[0],
                    "Signal_free": values[1],
                    "Signal_bound": values[2],
                    "note": self.data_point_notes.get(item, "")
                }
                data["data_points"].append(point)
            
            # Save to file with nice formatting
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
                
            messagebox.showinfo("Save Successful", f"Dataset saved to {path}", parent=self.get_window())
            return True
            
        except Exception as e:
            messagebox.showerror("Error Saving Dataset", f"Error: {str(e)}", parent=self.get_window())
            return False

    def load_dataset(self, path=None):
        """Load a dataset from a JSON file."""
        if not path:
            path = filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=DATA_DIR,
                parent=self.get_window(),
                title="Open Dataset"
            )
            
        if not path or not os.path.exists(path):
            return False
            
        self.file_path = path
        
        try:
            # Clear existing data
            self.clear_data(confirm=False)
            
            # Load and parse JSON file
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Apply constants
            self._apply_constants(data.get("constants", {}))
            
            # Set dataset notes
            self.dataset_notes = data.get("dataset_notes", "")
            
            # Add data points
            for point in data.get("data_points", []):
                item_id = self.tree.insert("", tk.END, values=[
                    point["X"],
                    point["Signal_free"],
                    point["Signal_bound"],
                    "", ""  # Empty P_free and P_bound columns
                ])
                
                # Add note if present
                if point.get("note"):
                    self.data_point_notes[item_id] = point["note"]
                    self.tree.item(item_id, tags=("has_note",))
            
            # Configure tag for notes
            self.tree.tag_configure("has_note", background="#FFFFD0")
            
            # Update UI for notes
            self.update_ui_for_notes()
            
            # Calculate values and plot
            if data.get("data_points"):
                self.compute_and_plot()
                
            messagebox.showinfo("Load Successful", f"Dataset loaded from {path}", parent=self.get_window())
            return True
            
        except Exception as e:
            messagebox.showerror("Error Loading Dataset", f"Error: {str(e)}", parent=self.get_window())
            return False

    def _apply_constants(self, constants):
        """Apply loaded constants to the UI."""
        # Map from CSV keys to StringVar attributes
        var_mapping = {
            "hbar": self.hbar_var,
            "gamma": self.gamma_var,
            "B0": self.B0_var,
            "kB": self.kB_var,
            "sa_ratio": self.sa_ratio_var,
            "T": self.T_var,
            "conc_ref": self.conc_ref_var,
            "conc_free": self.conc_free_var,
            "conc_bound": self.conc_bound_var,
            "signal_ref": self.signal_ref_var,
            "x_label": self.x_label_var
        }
        
        # Update variables with loaded values
        for key, var in var_mapping.items():
            if key in constants:
                var.set(constants[key])

    def export_png(self, path=None):
        """Export the plot as a PNG file."""
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                parent=self.get_window(),
                title="Export Graph as PNG"
            )
            
        if not path:
            return False  # User cancelled
            
        try:
            self.fig.savefig(path, dpi=300)
            messagebox.showinfo("Export Successful", f"Graph exported to {path}", parent=self.get_window())
            return True
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting graph: {str(e)}", parent=self.get_window())
            return False

    # Note Management Methods
    def edit_dataset_notes(self):
        """Open a dialog to edit dataset-level notes."""
        dialog = tk.Toplevel(self.get_window())
        dialog.title("Dataset Notes")
        dialog.geometry("400x300")
        dialog.transient(self.get_window())
        dialog.grab_set()
        
        ttk.Label(dialog, text="Notes for this dataset:").pack(pady=(10,5), padx=10, anchor=tk.W)
        
        # Text widget for notes
        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(text_frame, height=10, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, self.dataset_notes)
        
        scrollbar.config(command=text_widget.yview)
        
        def save_notes():
            self.dataset_notes = text_widget.get("1.0", tk.END).strip()
            dialog.destroy()
            self.update_ui_for_notes()
        
        buttons = ttk.Frame(dialog)
        buttons.pack(fill=tk.X, pady=10)
        ttk.Button(buttons, text="Save", command=save_notes).pack(side=tk.RIGHT, padx=10)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def update_ui_for_notes(self):
        """Update UI elements to indicate presence of notes."""
        if self.dataset_notes:
            self.note_indicator.config(text="ℹ️ This dataset has notes. Use 'Dataset Notes' button to view.")
        elif any(self.data_point_notes.values()):
            self.note_indicator.config(text="ℹ️ Some data points have notes. Right-click to view.")
        else:
            self.note_indicator.config(text="")
    
    def show_context_menu(self, event):
        """Show context menu on right-click on a tree item."""
        # Get the tree item at the cursor position
        item = self.tree.identify_row(event.y)
        if item:
            # Select the item under cursor
            self.tree.selection_set(item)
            self.selected_item = item
            
            # Enable/disable menu items based on whether note exists
            has_note = item in self.data_point_notes and self.data_point_notes[item]
            state = tk.NORMAL if has_note else tk.DISABLED
            self.context_menu.entryconfig("View Note", state=state)
            self.context_menu.entryconfig("Delete Note", state=state)
                
            # Display context menu
            self.context_menu.post(event.x_root, event.y_root)
    
    def add_edit_note(self):
        """Add or edit note for the selected data point."""
        if not self.selected_item:
            return
            
        # Get current note if exists
        current_note = self.data_point_notes.get(self.selected_item, "")
        
        # Get data point details for the dialog title
        values = self.tree.item(self.selected_item, 'values')
        title = f"Note for data point X={values[0]}"
        
        # Show dialog to enter/edit note
        note = simpledialog.askstring(
            title, 
            "Enter note for this data point:", 
            initialvalue=current_note,
            parent=self.get_window()
        )
        
        if note is not None:  # None means user cancelled
            if note.strip():  # If note is not empty
                self.data_point_notes[self.selected_item] = note.strip()
                # Add visual indicator to the data point in the table
                current_tags = list(self.tree.item(self.selected_item, "tags") or [])
                if "has_note" not in current_tags:
                    current_tags.append("has_note")
                    self.tree.item(self.selected_item, tags=current_tags)
                    # Configure tag for visual styling
                    self.tree.tag_configure("has_note", background="#FFFFD0")  # Light yellow background
            else:
                # Remove empty note
                if self.selected_item in self.data_point_notes:
                    del self.data_point_notes[self.selected_item]
                # Remove visual indicator
                current_tags = list(self.tree.item(self.selected_item, "tags") or [])
                if "has_note" in current_tags:
                    current_tags.remove("has_note")
                    self.tree.item(self.selected_item, tags=current_tags)
            
            self.update_ui_for_notes()

    def view_note(self):
        """View note for the selected data point."""
        if not self.selected_item or self.selected_item not in self.data_point_notes:
            return
            
        note = self.data_point_notes[self.selected_item]
        values = self.tree.item(self.selected_item, 'values')
        
        # Show note in a dialog
        dialog = tk.Toplevel(self.get_window())
        dialog.title(f"Note for data point X={values[0]}")
        dialog.geometry("400x200")
        dialog.transient(self.get_window())
        dialog.grab_set()
        
        # Text widget to show note (read-only)
        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, height=5, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, note)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def delete_note(self):
        """Delete note for the selected data point."""
        if not self.selected_item or self.selected_item not in self.data_point_notes:
            return
            
        # Confirm deletion
        values = self.tree.item(self.selected_item, 'values')
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete note for data point X={values[0]}?",
                              parent=self.get_window()):
            # Delete note
            del self.data_point_notes[self.selected_item]
            
            # Remove visual indicator
            current_tags = list(self.tree.item(self.selected_item, "tags"))
            if "has_note" in current_tags:
                current_tags.remove("has_note")
                self.tree.item(self.selected_item, tags=current_tags)
                
            self.update_ui_for_notes()

    # Data Handling & Calculation Methods
    def add_datapoint(self):
        """Validate entries and insert a new row into the table."""
        try:
            # Only validate input columns
            input_columns = ("X", "Signal_free", "Signal_bound")
            values = [float(self.entry_vars[col].get()) for col in input_columns]
            # Add empty strings for calculated columns
            values.extend(["", ""])
        except ValueError:
            messagebox.showerror("Invalid entry", "Please enter numeric values in all fields.", parent=self.get_window())
            return

        # Simply add the data point without prompting for a note
        item_id = self.tree.insert("", tk.END, values=[str(v) for v in values])
            
        for var in self.entry_vars.values():
            var.set("")  # clear after adding

    def clear_data(self, confirm=True):
        """Clear all data and reset the UI."""
        # Ask for confirmation if needed
        if confirm and messagebox.askyesno("Confirm Clear", 
                                         "Are you sure you want to clear all data?",
                                         parent=self.get_window()) == False:
            return
        
        # Clear data point notes
        self.data_point_notes = {}
        
        # Ask if user wants to clear dataset notes too if they exist
        if confirm and self.dataset_notes and messagebox.askyesno("Clear Dataset Notes", 
                                                     "Do you want to clear dataset notes too?",
                                                     parent=self.get_window()):
            self.dataset_notes = ""
        
        # Clear tables
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.avg_tree.get_children():
            self.avg_tree.delete(item)
            
        # Reset plot
        self.ax.cla()
        x_label = self.x_label_var.get() or "X (user‑defined)"
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel("Percent polarization (%)")
        self.ax.grid(True, which="both", linestyle=":", linewidth=0.6)
        self.canvas.draw()
        
        # Reset best fit state
        self.best_fit_visible = False
        self.best_fit_lines = {'free': None, 'bound': None}
        self.toggle_fit_btn.config(text="Show Best Fit", state=tk.DISABLED)
        self.best_fit_frame.pack_forget()
        
        # Update UI for notes
        self.update_ui_for_notes()

    def compute_and_plot(self):
        """Core calculation + plotting routine."""
        # Get constants and check for validity
        try:
            constants = self._get_calculation_constants()
        except ValueError:
            messagebox.showerror("Invalid constants", "Global constants must be numeric.", parent=self.get_window())
            return

        # Gather measurement rows
        rows = self._get_measurement_rows()
        if not rows:
            messagebox.showwarning("No data", "Please add at least one measurement row.", parent=self.get_window())
            return

        # Save and restore notes
        self._prepare_for_recalculation()
        
        # Calculate polarization values for each row
        results = self._calculate_polarization_values(rows, constants)
        
        # Calculate statistics and update averaged results table
        self._calculate_statistics(results)
        
        # Plot the results
        self._plot_results(results, constants['x_label'])
        
        # Update UI state
        self._finalize_calculations()

    def _get_calculation_constants(self):
        """Extract and validate all calculation constants."""
        constants = {
            'hbar': float(self.hbar_var.get()),
            'gamma': float(self.gamma_var.get()),
            'B0': float(self.B0_var.get()),
            'kB': float(self.kB_var.get()),
            'T': float(self.T_var.get()),
            'sa_ratio': float(self.sa_ratio_var.get()),
            'conc_ref': float(self.conc_ref_var.get()),
            'conc_free': float(self.conc_free_var.get()),
            'conc_bound': float(self.conc_bound_var.get()),
            'signal_ref': float(self.signal_ref_var.get()),
            'x_label': self.x_label_var.get() or "X (user‑defined)",
        }
        
        # Compute thermal polarization factor
        constants['A0'] = self.thermal_polarization(
            constants['hbar'], constants['gamma'], 
            constants['B0'], constants['kB'], constants['T']
        )
        
        return constants

    def _get_measurement_rows(self):
        """Extract measurement rows from the tree."""
        rows = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            # Only extract the first 3 values (X, Signal_free, Signal_bound)
            row = [float(values[i]) for i in range(3)]
            rows.append(row)
        return rows

    def _prepare_for_recalculation(self):
        """Save current notes and prepare for recalculation."""
        # Preserve notes when recomputing
        self.old_data_point_notes = self.data_point_notes.copy()
        self.data_point_notes = {}
        
        # Map values to items for note restoration
        self.old_items = {}
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            old_values = (values[0], values[1], values[2])
            self.old_items[old_values] = item
            self.tree.delete(item)

    def _calculate_polarization_values(self, rows, constants):
        """Calculate polarization values for all data rows."""
        results = {
            'free_results': {},
            'bound_results': {},
            'xvals': []
        }
        
        # Process each row of input data
        for x, signal_free, signal_bound in rows:
            p_free = self.percent_polarization(
                constants['A0'], constants['sa_ratio'],
                constants['conc_ref'], constants['conc_free'],
                signal_free, constants['signal_ref']
            )

            p_bound = self.percent_polarization(
                constants['A0'], constants['sa_ratio'],
                constants['conc_ref'], constants['conc_bound'],
                signal_bound, constants['signal_ref']
            )

            # Format values as strings for display
            x_str = f"{x:.3f}"
            signal_free_str = f"{signal_free:.3f}"
            signal_bound_str = f"{signal_bound:.3f}"
            p_free_str = f"{p_free:.3f}"
            p_bound_str = f"{p_bound:.3f}"

            # Insert row with calculated values
            values_tuple = (x_str, signal_free_str, signal_bound_str)
            new_item = self.tree.insert("", tk.END, values=[
                x_str, signal_free_str, signal_bound_str,
                p_free_str, p_bound_str
            ])
            
            # Transfer notes from old items to new ones if they match
            if values_tuple in self.old_items and self.old_items[values_tuple] in self.old_data_point_notes:
                self.data_point_notes[new_item] = self.old_data_point_notes[self.old_items[values_tuple]]
                # Add visual indicator
                self.tree.item(new_item, tags=("has_note",))

            # Store results for statistics and plotting
            results['xvals'].append(x)
            results['free_results'].setdefault(x, []).append(p_free)
            results['bound_results'].setdefault(x, []).append(p_bound)
            
        return results

    def _calculate_statistics(self, results):
        """Calculate statistics and update averaged results table."""
        # Clear the averaged results table
        for item in self.avg_tree.get_children():
            self.avg_tree.delete(item)

        # Calculate statistics for each unique X value
        unique_x = sorted(set(results['xvals']))
        results['unique_x'] = unique_x
        results['free_avg'] = []
        results['free_std'] = []
        results['bound_avg'] = []
        results['bound_std'] = []
        
        for x in unique_x:
            f_list = results['free_results'][x]
            b_list = results['bound_results'][x]
            
            f_avg = statistics.mean(f_list)
            b_avg = statistics.mean(b_list)
            f_std = statistics.stdev(f_list) if len(f_list) > 1 else 0.0
            b_std = statistics.stdev(b_list) if len(b_list) > 1 else 0.0
            
            results['free_avg'].append(f_avg)
            results['bound_avg'].append(b_avg)
            results['free_std'].append(f_std)
            results['bound_std'].append(b_std)

            # Insert row into averaged results table
            self.avg_tree.insert("", tk.END, values=[
                f"{x:.3f}",
                f"{f_avg:.3f}",
                f"{f_std:.3f}",
                f"{b_avg:.3f}",
                f"{b_std:.3f}"
            ])
    
    def _plot_results(self, results, x_label):
        """Plot the calculated polarization values."""
        self.ax.cla()
        self.ax.errorbar(
            results['unique_x'], results['free_avg'], yerr=results['free_std'],
            fmt="o", capsize=4, label="Free", color="red"
        )
        self.ax.errorbar(
            results['unique_x'], results['bound_avg'], yerr=results['bound_std'],
            fmt="s", capsize=4, label="Bound", color="blue"
        )

        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel("Percent polarization (%)")
        self.ax.legend()
        self.ax.grid(True, which="both", linestyle=":", linewidth=0.6)
        self.fig.tight_layout()
        self.canvas.draw()
    
    def _finalize_calculations(self):
        """Update UI state after calculations."""
        # Reset best fit visibility state
        self.best_fit_visible = False
        self.best_fit_lines = {'free': None, 'bound': None}
        self.toggle_fit_btn.config(text="Show Best Fit", state=tk.NORMAL)
        self.best_fit_frame.pack_forget()
        
        # Update UI for notes
        self.update_ui_for_notes()
        
        # Configure tag for visual styling
        self.tree.tag_configure("has_note", background="#FFFFD0")  # Light yellow background

    # Best Fit Line Methods
    def calculate_best_fit(self):
        """Calculate and display lines of best fit for free and bound data."""
        # Check if we have data to analyze
        if not self.tree.get_children():
            messagebox.showinfo("No Data", "Please compute data before calculating best fit lines.", parent=self.get_window())
            return
            
        # Extract data points
        free_data, bound_data = self._extract_fit_data()
        
        # Remove any previous best fit lines
        self._remove_best_fit_lines()
        
        # Calculate and display best fit lines
        result_text = []
        
        if len(free_data) >= 2:
            self._add_best_fit_line(free_data, 'free', 'r--', result_text)
        else:
            result_text.append("Free: Insufficient data points")
            
        if len(bound_data) >= 2:
            self._add_best_fit_line(bound_data, 'bound', 'b--', result_text)
        else:
            result_text.append("Bound: Insufficient data points")
            
        # Show results
        self.best_fit_frame.pack(fill=tk.X, padx=10, pady=5, after=self.canvas_frame)
        self.best_fit_label.config(text="\n".join(result_text))
        
        # Update legend and redraw
        self.ax.legend()
        self.canvas.draw_idle()
        
        # Update UI state
        self.best_fit_visible = True
        self.toggle_fit_btn.config(text="Hide Best Fit", state=tk.NORMAL)

    def _extract_fit_data(self):
        """Extract data points for best fit calculation."""
        free_data = []
        bound_data = []
        
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            try:
                x = float(values[0])
                p_free = float(values[3])
                p_bound = float(values[4])
                free_data.append((x, p_free))
                bound_data.append((x, p_bound))
            except (ValueError, IndexError):
                continue
                
        # Sort data by x values
        free_data.sort(key=lambda point: point[0])
        bound_data.sort(key=lambda point: point[0])
        
        return free_data, bound_data

    def _add_best_fit_line(self, data_points, category, line_style, result_text):
        """Add a best fit line for the given category of data."""
        # Extract x and y values
        x_values = [point[0] for point in data_points]
        y_values = [point[1] for point in data_points]
        
        # Calculate line of best fit
        slope, intercept = np.polyfit(x_values, y_values, 1)
        r_squared = self._calculate_r_squared(x_values, y_values, slope, intercept)
        
        # Add to results text
        equation = f"{category.title()}: y = {slope:.4f}x + {intercept:.4f} (R² = {r_squared:.4f})"
        result_text.append(equation)
        
        # Add line to plot
        x_range = np.linspace(min(x_values), max(x_values), 100)
        y_fit = slope * x_range + intercept
        equation_label = f"{category.title()} best fit: y = {slope:.4f}x + {intercept:.4f}"
        line, = self.ax.plot(x_range, y_fit, line_style, linewidth=1.5, alpha=0.8, label=equation_label)
        self.best_fit_lines[category] = line

    def _remove_best_fit_lines(self):
        """Remove existing best fit lines from the plot."""
        for category, line in self.best_fit_lines.items():
            if line:
                line.remove()
                self.best_fit_lines[category] = None
                
        # Refresh legend to remove the entries
        self.ax.legend()
        self.canvas.draw_idle()

    def toggle_best_fit(self):
        """Toggle visibility of best fit lines."""
        if self.best_fit_visible:
            # Hide the best fit lines
            self._remove_best_fit_lines()
            self.best_fit_visible = False
            self.toggle_fit_btn.config(text="Show Best Fit")
            self.best_fit_frame.pack_forget()
        else:
            # Show the best fit lines (recalculate)
            self.calculate_best_fit()
            self.toggle_fit_btn.config(text="Hide Best Fit")

    def _calculate_r_squared(self, x, y, slope, intercept):
        """Calculate the R-squared value for the line of best fit."""
        y_pred = [slope * xi + intercept for xi in x]
        y_mean = sum(y) / len(y)
        ss_total = sum((yi - y_mean) ** 2 for yi in y)
        ss_residual = sum((yi - y_pred_i) ** 2 for yi, y_pred_i in zip(y, y_pred))
        r_squared = 1 - (ss_residual / ss_total) if ss_total != 0 else 0
        return r_squared


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class PolarizationApp(ttk.Frame):
    def __init__(self, master, embedded=False):
        super().__init__(master)
        
        self.embedded = embedded
        if not embedded:
            self.toplevel = tk.Toplevel(master)
            self.toplevel.title("Percent Polarization Calculator - multi-dataset")
            self.toplevel.geometry("1242x828")
            container = self.toplevel
        else:
            container = self
            self.pack(fill="both", expand=True)
        
        # Create the menu bar if not embedded
        if not embedded:
            self._create_menu_bar()
        
        # Create custom tab bar frame
        self.tab_bar_frame = ttk.Frame(container)
        self.tab_bar_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Create notebook container frame
        self.notebook_frame = ttk.Frame(container)
        self.notebook_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook to hold tabs
        self.notebook = ttk.Notebook(self.notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add double-click binding for tab detachment
        self.notebook.bind("<Double-Button-1>", self._on_tab_double_click)
        # Add right-click binding for context menu
        self.notebook.bind("<Button-3>", self._on_tab_right_click)
        
        # Create custom tab bar controls
        self._create_tab_bar_controls()
        
        # Track open tabs
        self.tabs = []
        self.tab_counter = 1
        
        # Create first tab by default
        self._new_dataset()

    def _create_tab_bar_controls(self):
        """Create the custom tab bar with + button and Save/Load buttons."""
        # Left side: New Dataset button (+ button)
        left_frame = ttk.Frame(self.tab_bar_frame)
        left_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # + Button for new dataset
        self.new_dataset_btn = ttk.Button(left_frame, text="+", width=3,
                                         command=self._show_new_dataset_menu)
        self.new_dataset_btn.pack(side=tk.LEFT)
        
        # Create popup menu for + button
        self.new_dataset_menu = tk.Menu(self, tearoff=0)
        self.new_dataset_menu.add_command(label="New Empty Dataset", command=self._new_dataset)
        self.new_dataset_menu.add_command(label="Duplicate Current Dataset", command=self._duplicate_current_dataset)
        self.new_dataset_menu.add_separator()
        self.new_dataset_menu.add_command(label="Import from CSV", command=self._import_csv_dataset)
        
        # Right side: Save and Load buttons
        right_frame = ttk.Frame(self.tab_bar_frame)
        right_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Load Dataset button
        self.load_dataset_btn = ttk.Button(right_frame, text="Load Dataset",
                                          command=self._open_dataset)
        self.load_dataset_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Save Dataset button
        self.save_dataset_btn = ttk.Button(right_frame, text="Save Dataset",
                                          command=self._save_dataset)
        self.save_dataset_btn.pack(side=tk.RIGHT)
        
        # Middle: Tab info label (optional)
        middle_frame = ttk.Frame(self.tab_bar_frame)
        middle_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        
        self.tab_info_label = ttk.Label(middle_frame, text="Right-click on tabs for more options")
        self.tab_info_label.pack(side=tk.LEFT)

    def _show_new_dataset_menu(self):
        """Show the new dataset menu when + button is clicked."""
        try:
            # Get the position of the + button
            x = self.new_dataset_btn.winfo_rootx()
            y = self.new_dataset_btn.winfo_rooty() + self.new_dataset_btn.winfo_height()
            
            # Show the menu
            self.new_dataset_menu.tk_popup(x, y)
        finally:
            self.new_dataset_menu.grab_release()

    def _duplicate_current_dataset(self):
        """Create a new dataset by duplicating the current one."""
        current_tab = self.notebook.select()
        if current_tab:
            tab_id = self.notebook.index(current_tab)
            current_tab_obj = self.tabs[tab_id]
            
            # Create new tab
            new_tab = PolarizationTab(self.notebook, tab_id=self.tab_counter)
            self.tab_counter += 1
            
            # Copy data from current tab to new tab
            self._copy_tab_data(current_tab_obj, new_tab)
            
            # Add tab to notebook
            self.notebook.add(new_tab, text=f"{new_tab.title} (Copy)")
            self.notebook.select(new_tab)
            
            # Add to tabs list
            self.tabs.append(new_tab)
        else:
            # No current tab, just create a new one
            self._new_dataset()

    def _copy_tab_data(self, source_tab, target_tab):
        """Copy data from source tab to target tab."""
        try:
            # Copy measurement data
            for item in source_tab.tree.get_children():
                values = source_tab.tree.item(item, 'values')
                target_tab.tree.insert('', 'end', values=values)
            
            # Copy constants if they exist
            if hasattr(source_tab, 'const_entries'):
                for key, entry in source_tab.const_entries.items():
                    if key in target_tab.const_entries:
                        target_tab.const_entries[key].delete(0, tk.END)
                        target_tab.const_entries[key].insert(0, entry.get())
            
            # Copy notes if they exist
            if hasattr(source_tab, 'notes') and source_tab.notes:
                target_tab.notes = source_tab.notes.copy()
                
        except Exception as e:
            print(f"Error copying tab data: {e}")

    def _import_csv_dataset(self):
        """Import dataset from CSV file."""
        from tkinter import filedialog
        
        path = filedialog.askopenfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Import CSV Dataset"
        )
        
        if path and os.path.exists(path):
            # Create new tab
            new_tab = PolarizationTab(self.notebook, tab_id=self.tab_counter)
            self.tab_counter += 1
            
            # Try to import CSV data
            try:
                self._import_csv_to_tab(path, new_tab)
                
                # Add tab to notebook
                filename = os.path.basename(path).replace('.csv', '')
                self.notebook.add(new_tab, text=f"Dataset {self.tab_counter-1} ({filename})")
                self.notebook.select(new_tab)
                
                # Add to tabs list
                self.tabs.append(new_tab)
                
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import CSV file:\n{e}")

    def _import_csv_to_tab(self, csv_path, target_tab):
        """Import CSV data into the specified tab."""
        import csv
        
        with open(csv_path, 'r', newline='') as csvfile:
            # Try to detect the dialect
            sniffer = csv.Sniffer()
            sample = csvfile.read(1024)
            csvfile.seek(0)
            
            try:
                delimiter = sniffer.sniff(sample).delimiter
            except:
                delimiter = ','  # Default to comma
            
            reader = csv.reader(csvfile, delimiter=delimiter)
            
            # Skip header if it looks like a header
            first_row = next(reader, None)
            if first_row:
                # Check if first row contains non-numeric data (likely header)
                try:
                    [float(val) for val in first_row if val.strip()]
                    # If we get here, it's numeric data, so rewind
                    csvfile.seek(0)
                    reader = csv.reader(csvfile, delimiter=delimiter)
                except ValueError:
                    # First row is likely a header, continue with next row
                    pass
            
            # Import data
            for row_num, row in enumerate(reader):
                if len(row) >= 3:  # Need at least X, Signal_free, Signal_bound
                    try:
                        x_val = float(row[0])
                        signal_free = float(row[1])
                        signal_bound = float(row[2])
                        
                        # Insert into the target tab's tree
                        target_tab.tree.insert('', 'end', values=(x_val, signal_free, signal_bound, '', ''))
                        
                    except ValueError:
                        continue  # Skip invalid rows

    def _on_tab_right_click(self, event):
        """Handle right-click on tab for context menu."""
        x, y, widget = event.x, event.y, event.widget
        element = widget.identify(x, y)
        
        # Only proceed if a tab was clicked
        if "tab" in element:
            index = widget.index("@%d,%d" % (x, y))
            
            if 0 <= index < len(self.tabs):
                # Select the tab first
                self.notebook.select(index)
                
                # Create context menu
                context_menu = tk.Menu(self, tearoff=0)
                context_menu.add_command(label="Detach Tab", 
                                       command=lambda: self._detach_tab_by_index(index))
                context_menu.add_command(label="Duplicate Tab", 
                                       command=lambda: self._duplicate_tab_by_index(index))
                context_menu.add_separator()
                context_menu.add_command(label="Rename Tab", 
                                       command=lambda: self._rename_tab_by_index(index))
                context_menu.add_command(label="Close Tab", 
                                       command=lambda: self._close_tab_by_index(index))
                
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()

    def _detach_tab_by_index(self, index):
        """Detach tab by index."""
        if 0 <= index < len(self.tabs):
            tab = self.tabs[index]
            self.notebook.forget(index)
            tab.detach_tab()
            self.tabs.pop(index)

    def _duplicate_tab_by_index(self, index):
        """Duplicate tab by index."""
        if 0 <= index < len(self.tabs):
            # Select the tab to duplicate
            self.notebook.select(index)
            self._duplicate_current_dataset()

    def _rename_tab_by_index(self, index):
        """Rename tab by index."""
        if 0 <= index < len(self.tabs):
            current_text = self.notebook.tab(index, "text")
            
            from tkinter import simpledialog
            new_name = simpledialog.askstring("Rename Tab", 
                                             "Enter new tab name:", 
                                             initialvalue=current_text)
            if new_name:
                self.notebook.tab(index, text=new_name)

    def _close_tab_by_index(self, index):
        """Close tab by index."""
        if 0 <= index < len(self.tabs):
            # Ask for confirmation if tab has data
            tab = self.tabs[index]
            if tab.tree.get_children():
                from tkinter import messagebox
                if not messagebox.askyesno("Close Tab", 
                                         "This tab contains data. Are you sure you want to close it?"):
                    return
            
            # Remove tab
            self.notebook.forget(index)
            self.tabs.pop(index)
            
            # If no tabs left, create a new one
            if not self.tabs:
                self._new_dataset()

    def _create_menu_bar(self):
        """Create the application menu bar."""
        menubar = tk.Menu(self.toplevel)
        self.toplevel.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        file_menu.add_command(label="New Dataset", command=self._new_dataset)
        file_menu.add_command(label="Open...", command=self._open_dataset)
        file_menu.add_command(label="Save Dataset", command=self._save_dataset)
        file_menu.add_command(label="Export Graph as PNG...", command=self._export_png)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.toplevel.destroy)
    
    def _new_dataset(self):
        """Create a new dataset tab."""
        # Create the tab
        tab = PolarizationTab(self.notebook, tab_id=self.tab_counter)
        self.tab_counter += 1
        
        # Add tab to notebook
        self.notebook.add(tab, text=tab.title)
        self.notebook.select(tab)
        
        # Add to tabs list
        self.tabs.append(tab)
    
    def _open_dataset(self):
        """Open a dataset from file."""
        from tkinter import filedialog
        
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=DATA_DIR,
            parent=self,
            title="Open Dataset"
        )
        
        if path and os.path.exists(path):
            # Check if we should use a new tab or current one
            current_tab = self.notebook.select()
            if current_tab:
                tab_id = self.notebook.index(current_tab)
                tab = self.tabs[tab_id]
                
                # Use current tab if it's empty, otherwise create a new one
                if not tab.tree.get_children():
                    tab.load_dataset(path)
                else:
                    self._new_dataset()
                    self.tabs[-1].load_dataset(path)
            else:
                # Create new tab if no tabs exist
                self._new_dataset()
                self.tabs[-1].load_dataset(path)
    
    def _save_dataset(self):
        """Save the current dataset to a file."""
        current_tab = self.notebook.select()
        if current_tab:
            tab_id = self.notebook.index(current_tab)
            self.tabs[tab_id].save_dataset()
    
    def _export_png(self):
        """Export the current graph as a PNG file."""
        current_tab = self.notebook.select()
        if current_tab:
            tab_id = self.notebook.index(current_tab)
            self.tabs[tab_id].export_png()
    
    def _on_tab_double_click(self, event):
        """Handle double-click on tab to detach it."""
        x, y, widget = event.x, event.y, event.widget
        element = widget.identify(x, y)
        
        # Only proceed if a tab was clicked (not whitespace)
        if "tab" in element:
            index = widget.index("@%d,%d" % (x, y))
            
            # Check that tab exists
            if 0 <= index < len(self.tabs):
                tab = self.tabs[index]
                
                # Detach the tab
                self.notebook.forget(index)
                tab.detach_tab()
                self.tabs.pop(index)


# ------------- run -------------
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    PolarizationApp(root)
    root.mainloop()