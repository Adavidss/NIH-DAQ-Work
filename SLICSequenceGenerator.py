import numpy as np

# -------------------- user-defined parameters --------------------
B1_SLIC        = 1.8         # V   – CW SLIC B1 amplitude
f_SLIC         = 535.25      # Hz  – SLIC carrier frequency
TimeSLIC_approx = 100        # s   – requested CW duration (rounded later)
Δf             = 50          # Hz  – linear frequency sweep range during 90° pulse
Length90Pulse  = 4           # s   – triangular 90° pulse length
B1_Pulse       = 4           # V   – peak of triangular 90° pulse
SamplingRate   = 10_000      # samples per second
# -----------------------------------------------------------------

# --- exact CW length (Mathematica: Floor[TimeSLICapprox*f]/f) ---
TimeSLIC = np.floor(TimeSLIC_approx * f_SLIC) / f_SLIC

# --- time axis ---------------------------------------------------
dt = 1.0 / SamplingRate
t  = np.arange(0.0, TimeSLIC + Length90Pulse + dt/2, dt)   # inclusive upper bound

# --- piece-wise SLIC envelope -----------------------------------
# region 1: continuous-wave SLIC
cw_mask   = t < TimeSLIC
cw_wave   = B1_SLIC * np.sin(2*np.pi*f_SLIC * t)

# region 2: triangular 90° pulse with linear frequency sweep
pulse_mask = (t >= TimeSLIC) & (t < TimeSLIC + Length90Pulse)
τ          = t[pulse_mask] - TimeSLIC
tri_env    = B1_Pulse * (1.0 - τ / Length90Pulse)          # linear decay
inst_freq  = f_SLIC + Δf * (τ / Length90Pulse)             # chirp
pulse_wave = tri_env * np.sin(2*np.pi*inst_freq * t[pulse_mask])

# region 3: zeros after the pulse (already zero by initialization)

# --- assemble full waveform -------------------------------------
slic = np.zeros_like(t)
slic[cw_mask]     = cw_wave[cw_mask]
slic[pulse_mask]  = pulse_wave

# --- sanity check (length should be 1,040,001 samples) ----------
print("Samples:", slic.size)

# --- write to text file -----------------------------------------
save_path = r"C:\Users\walsworthlab\Desktop\SABRE Panel Program\config_files_SABRE\PolarizationMethods\SLICtest.txt"
np.savetxt(save_path, slic, fmt="%.9g")   # same folder; change path if desired