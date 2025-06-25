import math
import statistics
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

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
# Tkinter GUI
# ---------------------------------------------------------------------------


class PolarizationApp(tk.Toplevel, PolarizationCalculator):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)

        self.title("Percent Polarization Calculator")
        self.geometry("1242x828")  # Increased by 15% from 1080x720

        # ---------------- Global constants ------------------
        constants_frame = ttk.LabelFrame(self, text="Global Constants & Settings")
        constants_frame.pack(fill=tk.X, padx=10, pady=5)

        # helper to make labeled entries
        def add_const(label, default, row, col):
            ttk.Label(constants_frame, text=label).grid(row=row, column=col * 2, sticky=tk.W, padx=4, pady=2)
            var = tk.StringVar(value=str(default))
            entry = ttk.Entry(constants_frame, width=12, textvariable=var)
            entry.grid(row=row, column=col * 2 + 1, padx=4, pady=2)
            return var

        # Physical constants (editable in case user wants to tweak)
        self.hbar_var = add_const("ℏ (J·s)", f"{6.626e-34 / (2 * math.pi):.6e}", 0, 0)
        self.gamma_var = add_const("γ (rad·s⁻¹·T⁻¹)", "67280000", 0, 1)
        self.B0_var = add_const("B₀ (T)", "1.1", 0, 2)
        self.kB_var = add_const("k_B (J·K⁻¹)", f"{1.380649e-23:.6e}", 0, 3)
        self.sa_ratio_var = add_const("SA ratio", "1.03", 0, 4)
        
        # Temperature and concentration/signal parameters on separate row
        self.T_var = add_const("T (K)", "278.0", 1, 0)
        self.conc_ref_var = add_const("Conc_ref", "", 1, 1)
        self.conc_free_var = add_const("Conc_free", "", 1, 2)
        self.conc_bound_var = add_const("Conc_bound", "", 1, 3)
        self.signal_ref_var = add_const("Signal_ref", "", 1, 4)
        
        # X-axis label on third row
        self.x_label_var = add_const("X-axis label", "X (user‑defined)", 2, 0)

        # ---------------- Data‑entry table ------------------
        table_frame = ttk.LabelFrame(self, text="Measurements (one row = one experiment)")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create a frame to hold both tables side by side
        tables_container = ttk.Frame(table_frame)
        tables_container.pack(fill=tk.BOTH, expand=True)

        # Left table - Raw measurements
        left_table_frame = ttk.Frame(tables_container)
        left_table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(left_table_frame, text="Raw Measurements", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)

        columns = ("X", "Signal_free", "Signal_bound", "P_free (%)", "P_bound (%)")
        self.tree = ttk.Treeview(left_table_frame, columns=columns, show="headings", height=8)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right table - Averaged results
        right_table_frame = ttk.Frame(tables_container)
        right_table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        ttk.Label(right_table_frame, text="Averaged Results", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)

        avg_columns = ("X", "P_free_avg (%)", "P_free_std", "P_bound_avg (%)", "P_bound_std")
        self.avg_tree = ttk.Treeview(right_table_frame, columns=avg_columns, show="headings", height=8)
        for col in avg_columns:
            self.avg_tree.heading(col, text=col)
            self.avg_tree.column(col, width=100, anchor=tk.CENTER)
        self.avg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        avg_scrollbar = ttk.Scrollbar(right_table_frame, orient=tk.VERTICAL, command=self.avg_tree.yview)
        self.avg_tree.configure(yscroll=avg_scrollbar.set)
        avg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ------ Row‑entry widgets (beneath the table) -------
        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create entry widgets only for input columns (not calculated results)
        input_columns = ("X", "Signal_free", "Signal_bound")
        self.entry_vars = {col: tk.StringVar() for col in input_columns}
        for i, col in enumerate(input_columns):
            ttk.Label(entry_frame, text=col).grid(row=0, column=2 * i, padx=2, pady=2)
            ttk.Entry(entry_frame, width=12, textvariable=self.entry_vars[col]).grid(row=0, column=2 * i + 1, padx=2, pady=2)

        ttk.Button(entry_frame, text="Add Data Point", command=self.add_datapoint).grid(row=1, column=0, columnspan=len(input_columns) * 2, pady=4)

        # ----------------- Control buttons ------------------
        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(controls, text="Compute & Plot", command=self.compute_and_plot).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Clear Data", command=self.clear_data).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Quit", command=self.destroy).pack(side=tk.RIGHT, padx=4)

        # ----------------- Matplotlib canvas ----------------
        self.fig, self.ax = plt.subplots()
        self.ax.set_xlabel("X (user‑defined)")
        self.ax.set_ylabel("Percent polarization (%)")
        self.ax.grid(True, which="both", linestyle=":", linewidth=0.6)

        # Add navigation toolbar with zoom functionality
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.draw()
        
        # Add toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, canvas_frame)
        toolbar.update()
        
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add hover functionality for coordinate display
        self.coord_label = ttk.Label(canvas_frame, text="Coordinates: ")
        self.coord_label.pack(side=tk.BOTTOM, anchor=tk.W)
        
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)

    # ---------------------------------------------------------------------

    def on_hover(self, event):
        """Display coordinates when hovering over the plot."""
        if event.inaxes:
            self.coord_label.config(text=f"Coordinates: X={event.xdata:.3f}, Y={event.ydata:.3f}")
        else:
            self.coord_label.config(text="Coordinates: ")

    def add_datapoint(self):
        """Validate entries and insert a new row into the table."""
        try:
            # Only validate input columns
            input_columns = ("X", "Signal_free", "Signal_bound")
            values = [float(self.entry_vars[col].get()) for col in input_columns]
            # Add empty strings for calculated columns
            values.extend(["", ""])
        except ValueError:
            messagebox.showerror("Invalid entry", "Please enter numeric values in all fields.")
            return

        self.tree.insert("", tk.END, values=[str(v) for v in values])
        for var in self.entry_vars.values():
            var.set("")  # clear after adding

    # ---------------------------------------------------------------------

    def clear_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.avg_tree.get_children():
            self.avg_tree.delete(item)
        self.ax.cla()
        x_label = self.x_label_var.get() or "X (user‑defined)"
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel("Percent polarization (%)")
        self.ax.grid(True, which="both", linestyle=":", linewidth=0.6)
        self.canvas.draw()

    # ---------------------------------------------------------------------

    def compute_and_plot(self):
        """Core calculation + plotting routine."""
        # First, grab global constants, converting to float
        try:
            hbar = float(self.hbar_var.get())
            gamma = float(self.gamma_var.get())
            B0 = float(self.B0_var.get())
            kB = float(self.kB_var.get())
            T = float(self.T_var.get())
            sa_ratio = float(self.sa_ratio_var.get())
            conc_ref = float(self.conc_ref_var.get())
            conc_free = float(self.conc_free_var.get())
            conc_bound = float(self.conc_bound_var.get())
            signal_ref = float(self.signal_ref_var.get())
            x_label = self.x_label_var.get() or "X (user‑defined)"
        except ValueError:
            messagebox.showerror("Invalid constants", "Global constants must be numeric.")
            return

        A0 = self.thermal_polarization(hbar, gamma, B0, kB, T)

        # Gather measurement rows
        rows = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            # Only extract the first 3 values (X, Signal_free, Signal_bound)
            # Skip the calculated columns (P_free %, P_bound %)
            row = [float(values[i]) for i in range(3)]
            rows.append(row)

        if not rows:
            messagebox.showwarning("No data", "Please add at least one measurement row.")
            return

        # Compute free and bound polarization for each row
        free_results = {}
        bound_results = {}
        xvals = []
        
        # Clear existing calculated values and update table
        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, (x, signal_free, signal_bound) in enumerate(rows):
            p_free = self.percent_polarization(A0, sa_ratio,
                                          conc_ref, conc_free,
                                          signal_free, signal_ref)

            p_bound = self.percent_polarization(A0, sa_ratio,
                                           conc_ref, conc_bound,
                                           signal_bound, signal_ref)

            # Insert row with calculated values
            self.tree.insert("", tk.END, values=[
                f"{x:.3f}", 
                f"{signal_free:.3f}", 
                f"{signal_bound:.3f}",
                f"{p_free:.3f}",
                f"{p_bound:.3f}"
            ])

            xvals.append(x)
            free_results.setdefault(x, []).append(p_free)
            bound_results.setdefault(x, []).append(p_bound)

        # Compute averages and std devs in order of unique sorted X
        unique_x = sorted(set(xvals))
        free_avg = []
        free_std = []
        bound_avg = []
        bound_std = []

        # Clear and populate the averaged results table
        for item in self.avg_tree.get_children():
            self.avg_tree.delete(item)

        for x in unique_x:
            f_list = free_results[x]
            b_list = bound_results[x]
            f_avg = statistics.mean(f_list)
            b_avg = statistics.mean(b_list)
            f_std = statistics.stdev(f_list) if len(f_list) > 1 else 0.0
            b_std = statistics.stdev(b_list) if len(b_list) > 1 else 0.0
            
            free_avg.append(f_avg)
            bound_avg.append(b_avg)
            free_std.append(f_std)
            bound_std.append(b_std)

            # Insert row into averaged results table
            self.avg_tree.insert("", tk.END, values=[
                f"{x:.3f}",
                f"{f_avg:.3f}",
                f"{f_std:.3f}",
                f"{b_avg:.3f}",
                f"{b_std:.3f}"
            ])

        # ---------------- Plotting -----------------
        self.ax.cla()
        self.ax.errorbar(unique_x, free_avg, yerr=free_std,
                         fmt="o", capsize=4, label="Free", color="red")
        self.ax.errorbar(unique_x, bound_avg, yerr=bound_std,
                         fmt="s", capsize=4, label="Bound", color="blue")

        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel("Percent polarization (%)")
        self.ax.legend()
        self.ax.grid(True, which="both", linestyle=":", linewidth=0.6)
        self.fig.tight_layout()
        self.canvas.draw()


# ------------- run -------------
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    PolarizationApp(root)
    root.mainloop()