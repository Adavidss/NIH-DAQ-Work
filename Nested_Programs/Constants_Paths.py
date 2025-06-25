import os

# ==== CONSTANTS & PATHS ====================================
# Go up one level to SABRE Program directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config_files_SABRE")
PRESETS_DIR = os.path.join(BASE_DIR, "config_files_SABRE", "PolarizationMethods", "Presets")
METHODS_DIR = os.path.join(BASE_DIR, "config_files_SABRE", "PolarizationMethods")
DAQ_DEVICE = "Dev1"
DIO_CHANNELS = [f"{DAQ_DEVICE}/port0/line{i}" for i in range(8)]

INITIAL_STATE = "Initial_State"
STATE_MAPPING = {
    "Activation_State_Final": "Activating the Sample",
    "Activation_State_Initial": "Activating the Sample",
    "Bubbling_State_Final": "Bubbling the Sample",
    "Bubbling_State_Initial": "Bubbling the Sample",
    "Degassing": "Degassing Solution",
    "Recycle": "Recycling Solution",
    "Injection_State_Start": "Injecting the Sample",
    "Transfer_Final": "Transferring the Sample",
    "Transfer_Initial": "Transferring the Sample",
    INITIAL_STATE: "Idle",
}

# ==== END CONSTANTS & PATHS ===============================