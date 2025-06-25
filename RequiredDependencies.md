# SABRE Control System - Required Dependencies

## Overview
The SABRE Control System requires several software dependencies, hardware drivers, and system components to function properly. This guide provides comprehensive installation instructions and troubleshooting tips.

## System Requirements

### Operating System
- **Primary Support**: Windows 10/11 (64-bit)
- **Minimum**: Windows 8.1 (64-bit)
- **Note**: The application is designed specifically for Windows due to NI-DAQ hardware integration

### Hardware Requirements
- **RAM**: Minimum 4GB, Recommended 8GB+
- **Storage**: 2GB free space for installation and data files
- **Display**: 1920x1080 minimum resolution recommended
- **Hardware**: National Instruments DAQ device (Dev1 configuration)

## Python Requirements

### Python Version
- **Required**: Python 3.8 or higher
- **Recommended**: Python 3.9 or 3.10
- **Download**: [python.org](https://www.python.org/downloads/)

### Installation Notes
- Ensure "Add Python to PATH" is checked during installation
- Install for all users (recommended for lab environments)
- Include pip package manager

## Required Python Packages

### Core Scientific Computing
```bash
pip install numpy>=1.20.0
pip install matplotlib>=3.5.0
```
- **numpy**: Numerical computing and array operations
- **matplotlib**: Plotting and data visualization
- **Source**: [NumPy](https://numpy.org/), [Matplotlib](https://matplotlib.org/)

### Image Processing
```bash
pip install Pillow>=8.0.0
```
- **Pillow (PIL)**: Image processing for application icons and graphics
- **Usage**: Application icon display, image handling in UI panels
- **Source**: [Pillow Documentation](https://pillow.readthedocs.io/)

### Data Acquisition (Critical)
```bash
pip install nidaqmx>=0.6.0
```
- **nidaqmx**: Python API for National Instruments DAQ hardware
- **Critical**: Required for hardware communication
- **Prerequisites**: NI-DAQmx drivers must be installed first (see Hardware Drivers section)
- **Source**: [NI-DAQmx Python Documentation](https://nidaqmx-python.readthedocs.io/)

### Built-in Python Modules (No Installation Required)
The following modules are included with Python standard library:
- **tkinter**: GUI framework (included with Python on Windows)
- **json**: JSON file handling
- **os, sys**: Operating system interfaces
- **threading**: Multi-threading support
- **time**: Time-related functions
- **csv**: CSV file handling
- **shutil**: File operations
- **functools**: Functional programming tools

## Hardware Drivers

### National Instruments DAQ Drivers

#### NI-DAQmx Runtime
- **Version Required**: 20.1 or later
- **Download**: [NI Software Downloads](https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html)
- **Purpose**: Core drivers for NI DAQ hardware communication
- **Installation Size**: ~1.5GB

#### Installation Steps:
1. Download NI-DAQmx Runtime from National Instruments website
2. Run installer as Administrator
3. Follow installation wizard (full installation recommended)
4. Restart computer after installation
5. Verify installation using NI MAX (Measurement & Automation Explorer)

#### Supported Hardware:
- USB DAQ devices (USB-6001, USB-6008, USB-6009, etc.)
- PCIe DAQ cards
- CompactDAQ systems
- **Default Configuration**: Dev1 (can be configured in NI MAX)

### Audio Drivers (Windows)
- **winsound**: Windows system audio (included with Windows)
- **Purpose**: Audio feedback for experiment notifications
- **No separate installation required**

## Installation Order (Recommended)

### 1. Python Installation
```bash
# Download Python 3.9+ from python.org
# Install with "Add to PATH" checked
# Verify installation:
python --version
pip --version
```

### 2. NI-DAQmx Drivers
```bash
# Download and install NI-DAQmx Runtime
# Restart computer
# Verify in NI MAX (Measurement & Automation Explorer)
```

### 3. Python Packages
```bash
# Install packages in order:
pip install numpy
pip install matplotlib
pip install Pillow
pip install nidaqmx
```

### 4. Verify Installation
```python
# Test script to verify all dependencies
import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import nidaqmx
print("All dependencies installed successfully!")
```

## Package Installation Commands

### All-in-One Installation
```bash
pip install numpy matplotlib Pillow nidaqmx
```

### Alternative: Requirements File
Create a `requirements.txt` file:
```text
numpy>=1.20.0
matplotlib>=3.5.0
Pillow>=8.0.0
nidaqmx>=0.6.0
```

Install using:
```bash
pip install -r requirements.txt
```

## Virtual Environment Setup (Recommended for Development)

### Creating Virtual Environment
```bash
# Create virtual environment
python -m venv sabre_env

# Activate (Windows)
sabre_env\Scripts\activate

# Install packages
pip install numpy matplotlib Pillow nidaqmx

# Deactivate when done
deactivate
```

## Troubleshooting Common Issues

### Python Package Issues

#### ImportError: No module named 'nidaqmx'
**Solution**:
```bash
pip install nidaqmx
# If still failing, try:
pip install --upgrade nidaqmx
```

#### NI-DAQmx Installation Issues
**Problem**: "DAQmx is not installed" error
**Solutions**:
1. Install NI-DAQmx Runtime from NI website
2. Restart computer after installation
3. Verify DAQ device appears in NI MAX
4. Check device is configured as "Dev1"

#### Matplotlib Display Issues
**Problem**: Plots not displaying correctly
**Solutions**:
```bash
# Try different matplotlib backend
pip install --upgrade matplotlib
# Or install Qt backend:
pip install PyQt5
```

#### PIL/Pillow Import Errors
**Problem**: Application icon not displaying
**Solutions**:
```bash
pip uninstall PIL  # Remove old PIL if present
pip install --upgrade Pillow
```

### Hardware Issues

#### DAQ Device Not Found
**Symptoms**: "Device Dev1 not found" errors
**Solutions**:
1. Open NI MAX (Measurement & Automation Explorer)
2. Expand "Devices and Interfaces"
3. Find your DAQ device
4. Right-click → "Rename" → Change to "Dev1"
5. Test device in NI MAX

#### Permission Errors
**Symptoms**: Access denied to DAQ device
**Solutions**:
1. Run application as Administrator
2. Check DAQ device isn't being used by another application
3. Restart NI-DAQmx service in Services.msc

### Windows-Specific Issues

#### tkinter Import Error
**Problem**: "No module named 'tkinter'"
**Solution**: 
- Reinstall Python with "tcl/tk and IDLE" option checked
- Or install tkinter separately (rare)

#### Path Issues
**Problem**: Commands not found in Command Prompt
**Solution**:
- Add Python to system PATH during installation
- Or manually add Python directory to PATH

## Version Compatibility Matrix

| Component | Minimum Version | Recommended | Latest Tested |
|-----------|----------------|-------------|---------------|
| Python | 3.8 | 3.9 | 3.11 |
| numpy | 1.20.0 | 1.21.0+ | 1.24.0 |
| matplotlib | 3.5.0 | 3.6.0+ | 3.7.0 |
| Pillow | 8.0.0 | 9.0.0+ | 10.0.0 |
| nidaqmx | 0.6.0 | 0.6.5+ | 0.7.0 |
| NI-DAQmx Runtime | 20.1 | 21.3+ | 23.3 |

## Development Dependencies (Optional)

### For Development and Testing
```bash
pip install pytest  # Unit testing
pip install black   # Code formatting
pip install flake8  # Code linting
```

### For Building Executables
```bash
pip install pyinstaller  # Create standalone executable
```

## Network and Firewall Considerations

### Python Package Installation
- Ensure internet access for pip downloads
- Corporate firewalls may block package installation
- Consider using offline installers if network restricted

### NI Software Downloads
- Requires free NI account for driver downloads
- Large file sizes (~1.5GB) - ensure adequate bandwidth

## Offline Installation

### For Air-Gapped Systems
1. Download all installers on internet-connected machine
2. Transfer to target system via USB/network
3. Install in order: Python → NI-DAQmx → Python packages
4. Use pip download with --only-binary for offline package installation

### Creating Offline Package Cache
```bash
# On internet-connected machine:
pip download numpy matplotlib Pillow nidaqmx -d offline_packages

# On offline machine:
pip install --find-links offline_packages --no-index numpy matplotlib Pillow nidaqmx
```

## Support and Resources

### Official Documentation
- [Python Documentation](https://docs.python.org/)
- [NumPy Documentation](https://numpy.org/doc/)
- [Matplotlib Documentation](https://matplotlib.org/stable/)
- [NI-DAQmx Python API](https://nidaqmx-python.readthedocs.io/)

### Hardware Support
- [National Instruments Support](https://www.ni.com/en-us/support.html)
- [NI Community Forums](https://forums.ni.com/)

### Quick Help Commands
```bash
# Check Python version
python --version

# List installed packages
pip list

# Check specific package version
pip show nidaqmx

# Upgrade all packages
pip list --outdated
pip install --upgrade [package_name]
```

## License Information

### Open Source Packages
- Python: PSF License
- NumPy: BSD License
- Matplotlib: PSF-based License
- Pillow: HPND License

### Proprietary Software
- NI-DAQmx: National Instruments License (free runtime)
- Windows: Microsoft License

## Final Verification Script

Save this as `verify_dependencies.py` and run to check all dependencies:

```python
#!/usr/bin/env python3
"""
SABRE Control System Dependencies Verification Script
Run this script to verify all required dependencies are properly installed.
"""

import sys
import importlib

def check_dependency(module_name, package_name=None):
    """Check if a dependency is available"""
    try:
        importlib.import_module(module_name)
        print(f"✓ {package_name or module_name} - OK")
        return True
    except ImportError as e:
        print(f"✗ {package_name or module_name} - MISSING ({e})")
        return False

def main():
    print("SABRE Control System - Dependencies Check")
    print("=" * 50)
    
    dependencies = [
        ("tkinter", "tkinter (GUI framework)"),
        ("numpy", "NumPy (numerical computing)"),
        ("matplotlib", "Matplotlib (plotting)"),
        ("PIL", "Pillow (image processing)"),
        ("nidaqmx", "NI-DAQmx (hardware interface)"),
        ("json", "JSON (built-in)"),
        ("threading", "Threading (built-in)"),
        ("time", "Time (built-in)"),
    ]
    
    all_ok = True
    for module, description in dependencies:
        if not check_dependency(module, description):
            all_ok = False
    
    print("=" * 50)
    if all_ok:
        print("✓ All dependencies are installed and available!")
        print("✓ SABRE Control System should run without issues.")
    else:
        print("✗ Some dependencies are missing.")
        print("✗ Please install missing packages before running SABRE.")
        sys.exit(1)

if __name__ == "__main__":
    main() 