"""
Plots + linear fits with ALL drive-amplitudes and σ already converted to volts (V)

• Plot 1 – input set-voltage (0–7 V)  →  X, Y, Z magnetic-field components (µT)
• Plot 2 – measured coil amplitude (V, ±σ)  →  X, Y, Z magnetic-field components
• Slopes / intercepts printed for both calibrations
"""

import numpy as np
import matplotlib.pyplot as plt

# ── 1. Input-set voltages ─────────────────────────────────────────────
V_input = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=float)

# ── 2. Measured coil amplitudes (already in V) and 1-σ std-devs (V) ──
x_amp_V  = np.array([0.00330, 0.28905, 0.57598, 0.87057, 1.15000, 1.45000, 1.73000, 2.04000])
x_std_V  = np.array([0.000962, 0.00368 , 0.000235, 0.00354 , 0.00745 , 0.00957 , 0.01000 , 0.00426 ])

y_amp_V  = np.array([0.00276, 0.18175, 0.34781, 0.51992, 0.68757, 0.86382, 1.03000, 1.20000])
y_std_V  = np.array([0.000972, 0.00228 , 0.000840, 0.000800, 0.00206 , 0.00118 , 0.00228 , 0.000740])

z_amp_V  = np.array([0.00350, 0.03600, 0.04090, 0.05639, 0.07200, 0.09106, 0.10787, 0.12473])
z_std_V  = np.array([0.000845, 0.000860, 0.00169 , 0.00171 , 0.000900, 0.00105 , 0.000985, 0.000968])

# ── 3. Magnetic-field readings (µT) ───────────────────────────────────
B_x = np.array([ 1.3, 10.8, 20.9, 31.1, 41.0, 50.9, 61.1, 71.1])
B_y = np.array([-1.6,  3.4,  9.5, 15.5, 21.4, 27.3, 33.4, 39.5])
B_z = np.array([ 1.7,  1.9,  2.5,  3.1,  3.7,  4.3,  4.8,  5.3])

# ── 4. Plot A – input-set voltage vs µT ───────────────────────────────
plt.figure(figsize=(7, 5))
plt.plot(V_input, B_x, 'o-', label='X')
plt.plot(V_input, B_y, 's-', label='Y')
plt.plot(V_input, B_z, '^-', label='Z')
plt.xlabel('Input voltage set-point (V)')
plt.ylabel('Magnetic field (µT)')
plt.title('Field vs input set-point')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# ── 5. Plot B – measured amplitude vs µT (±σ) ─────────────────────────
plt.figure(figsize=(7, 5))
plt.errorbar(x_amp_V, B_x, xerr=x_std_V, fmt='o-', label='X')
plt.errorbar(y_amp_V, B_y, xerr=y_std_V, fmt='s-', label='Y')
plt.errorbar(z_amp_V, B_z, xerr=z_std_V, fmt='^-', label='Z')
plt.xlabel('Measured coil amplitude (V)')
plt.ylabel('Magnetic field (µT)')
plt.title('Field vs measured amplitude (error bars = ±1 σ)')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# ── 6. Linear fits & printed slopes/intercepts ────────────────────────
def fit_and_report(x, y, label):
    m, b = np.polyfit(x, y, 1)
    print(f'{label:7}: m = {m:8.3f} µT/V   b = {b:8.3f} µT')
    return m, b

print('Fit: Field vs Input-Set Voltage')
fit_and_report(V_input, B_x, 'X-axis')
fit_and_report(V_input, B_y, 'Y-axis')
fit_and_report(V_input, B_z, 'Z-axis')

print('\nFit: Field vs Measured Amplitude')
fit_and_report(x_amp_V, B_x, 'X-axis')
fit_and_report(y_amp_V, B_y, 'Y-axis')
fit_and_report(z_amp_V, B_z, 'Z-axis')