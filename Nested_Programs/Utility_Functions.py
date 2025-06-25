import json
import os
import sys
import numpy as np

from Constants_Paths import (
    CONFIG_DIR,
    INITIAL_STATE
)

# ==== PURE UTILITY FUNCTIONS (no-GUI) =======================
def convert_value(value, unit, conversion_type="time"):
    """Universal value converter"""
    try:
        value = float(value)
        conversions = {
            "time": {"sec": 1, "min": 60, "ms": 0.001},
            "magnetic": {"T": 1, "mT": 1e-3, "µT": 1e-6},
            "pressure": {"psi": 1, "bar": 14.5038, "atm": 14.696},
            "temperature": {
                "K": lambda x: x,
                "C": lambda x: x + 273.15,
                "F": lambda x: (x - 32) * 5/9 + 273.15
            }
        }
        conv = conversions.get(conversion_type, {})
        converter = conv.get(unit)
        return converter(value) if callable(converter) else value * (converter or 0)
    except (ValueError, KeyError, TypeError):
        return 0

def get_value(entry, unit_var, conversion_type="time"):
    """Get and convert a value from an entry widget"""
    return convert_value(entry.get(), unit_var.get(), conversion_type)

def save_parameters_to_file(filepath, entries, units, advanced_entries, polarization_file):
    """Save parameters to JSON file without GUI dependencies"""
    params = {
        "Parameters": {
            param: {
                "value": entry.get(),
                "unit": units[param].get()
            } for param, entry in entries.items()
        },
        "Advanced": {
            param: {
                "value": entry.get(),
                "unit": unit_var.get()
            } for param, (entry, unit_var) in advanced_entries.items()
        },
        "Polarization_Method": polarization_file
    }
    
    with open(filepath, "w") as f:
        json.dump(params, f, indent=4)
    return True

def load_parameters_from_file(filepath):
    """Load parameters from JSON file without GUI dependencies"""
    with open(filepath, "r") as f:
        return json.load(f)

def ensure_default_state_files():
    """Ensure default state configuration files exist"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        states = {
            INITIAL_STATE: ["LOW", "LOW", "LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW"],
            "Injection_State_Start": ["HIGH", "LOW", "LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW"],
            "Degassing": ["LOW", "HIGH", "HIGH", "LOW", "LOW", "LOW", "HIGH", "LOW"],
            "Activation_State_Initial": ["LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW", "HIGH", "LOW"],
            "Activation_State_Final": ["LOW", "LOW", "HIGH", "LOW", "LOW", "LOW", "HIGH", "LOW"],
            "Bubbling_State_Initial": ["LOW", "LOW", "HIGH", "HIGH", "LOW", "LOW", "HIGH", "LOW"],
            "Bubbling_State_Final": ["LOW", "LOW", "HIGH", "HIGH", "HIGH", "LOW", "HIGH", "LOW"],
            "Transfer_Initial": ["LOW", "LOW", "LOW", "LOW", "HIGH", "LOW", "HIGH", "HIGH"],
            "Transfer_Final": ["LOW", "LOW", "LOW", "LOW", "HIGH", "LOW", "HIGH", "LOW"],
            "Recycle": ["HIGH", "LOW", "LOW", "LOW", "HIGH", "LOW", "HIGH", "LOW"]
        }
        for state, dio_values in states.items():
            with open(os.path.join(CONFIG_DIR, f"{state}.json"), "w") as f:
                json.dump({f"DIO{i}": dio_values[i] for i in range(8)}, f, indent=4)

def build_composite_waveform(ramp_sequences, dc_offset=0.0, samples_per_cycle=200):
    """Return (buf, sample_rate)
    Handles both traditional ramp sequences and SLIC sequence formats.
    """
    if isinstance(ramp_sequences, dict) and ramp_sequences.get("type") == "SLIC_sequence":
        params = ramp_sequences["params"]
        data = ramp_sequences["data"]
        sample_rate = params["SamplingRate"]
        return np.array(data, dtype=np.float64), sample_rate

    # Original ramp sequence handling
    sine_freqs = [seq.get("frequency", 1.0) 
                 for seq in ramp_sequences 
                 if seq["waveform"] == "sine"]
    max_f = max(sine_freqs) if sine_freqs else 1.0
    sample_rate = int(max_f * samples_per_cycle)

    big_buf = []
    for seq in ramp_sequences:
        dur = seq.get("duration", 0.0)

        if seq["waveform"] == "sine":
            f   = seq["frequency"]
            amp = seq["amplitude"]
            n   = int(sample_rate * dur)
            t   = np.linspace(0, dur, n, endpoint=False)
            slice_buf = amp * np.sin(2*np.pi*f*t) + dc_offset
        elif seq["waveform"] == "hold":
            v = seq["voltage"]
            n = max(2, int(sample_rate * dur))
            slice_buf = np.full(n, v, dtype=np.float64)
        else:  # linear ramp
            v0  = seq.get("start_voltage", dc_offset)
            v1  = seq.get("end_voltage",   dc_offset)
            n   = max(2, int(sample_rate * dur))
            slice_buf = np.linspace(v0, v1, n, dtype=np.float64)

        big_buf.append(slice_buf)

    return np.concatenate(big_buf), sample_rate

# Initialize state files
try:
    ensure_default_state_files()
except Exception as e:
    print(f"Error creating config directory and files: {e}")
    sys.exit(1)

# ==== END PURE UTILITY FUNCTIONS (no-GUI) ==================