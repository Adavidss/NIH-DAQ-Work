# SABRE Control System - Architecture Overview

## Main Program File

### SABREPanelProgram.py
**Primary Function**: Main application entry point and core GUI framework
- Contains the `SABREGUI` class which serves as the central controller
- Implements modular architecture with specialized controllers and managers
- Manages the main UI structure including tabbed interface
- Coordinates all subsystems and provides the main event loop
- Handles experiment sequences (activation, start, test field, SCRAM)
- Integrates all nested program modules through delegation patterns

**Key Classes**:
- `SABREGUI`: Main application class that orchestrates all functionality
- `TabManager`: Manages tab creation and organization
- `ExperimentController`: Handles experiment sequences and state management

## Core Controller Modules

### Nested_Programs/CountdownController.py
**Function**: Manages countdown timer functionality for experiments
- Provides real-time countdown display during experiments
- Handles timer start/stop/update operations
- Integrates with experiment sequences to show remaining time

**Connection to Main**: Instantiated as `self.countdown_controller` in SABREGUI

### Nested_Programs/WaveformController.py
**Function**: Handles live waveform plotting and management
- Refreshes waveform plots when polarization methods change
- Forces immediate waveform updates across tabs
- Manages waveform display visibility and reset operations

**Connection to Main**: Instantiated as `self.waveform_controller` in SABREGUI

### Nested_Programs/PresetController.py
**Function**: Handles all preset-related functionality
- Auto-fills parameters when presets are selected
- Manages preset loading and application
- Synchronizes preset data across Main and Advanced tabs

**Connection to Main**: Instantiated as `self.preset_controller` in SABREGUI

### Nested_Programs/PlotController.py
**Function**: Manages all plotting operations including live data visualization
- Handles matplotlib figure management
- Provides live plotting capabilities during experiments
- Manages waveform buffer plotting and axis formatting

**Connection to Main**: Instantiated as `self.plot_controller` in SABREGUI

### Nested_Programs/StateManager.py
**Function**: Manages system states and configurations
- Loads state configurations from JSON files
- Provides centralized state management for the system

**Connection to Main**: Instantiated as `self.state_manager` in SABREGUI

### Nested_Programs/DAQController.py
**Function**: Handles all DAQ (Data Acquisition) communication
- Sends digital signals to valve controls
- Manages analog output operations
- Provides hardware abstraction layer for NI-DAQ devices

**Connection to Main**: Instantiated as `self.daq_controller` in SABREGUI

### Nested_Programs/MethodManager.py
**Function**: Handles polarization method selection and management
- Loads polarization methods from directory
- Computes polarization duration for timing
- Manages method file selection and validation

**Connection to Main**: Instantiated as `self.method_manager` in SABREGUI

### Nested_Programs/UIManager.py
**Function**: Handles UI creation and styling
- Creates control buttons with consistent styling
- Shows error popups for missing parameters
- Provides UI element creation utilities

**Connection to Main**: Instantiated as `self.ui_manager` in SABREGUI

## Specialized Controllers

### Nested_Programs/ScramController.py
**Function**: Emergency stop functionality
- Provides immediate system shutdown capabilities
- Sets all DAQ outputs to safe states
- Handles emergency cleanup of running tasks

**Connection to Main**: Instantiated as `self.scram` in SABREGUI

### Nested_Programs/ThemeManager.py
**Function**: Manages application themes and visual styling
- Applies different color schemes (Light, Dark, High-Contrast)
- Recursively updates all widgets with theme colors
- Handles theme persistence and switching

**Connection to Main**: Instantiated as `self.theme_manager` in SABREGUI

### Nested_Programs/WindowManager.py
**Function**: Manages external windows and panels
- Opens and manages auxiliary panels (AI/AO testing, SLIC control, etc.)
- Handles window lifecycle and cleanup
- Provides centralized window management

**Connection to Main**: Instantiated as `self.window_manager` in SABREGUI

### Nested_Programs/TooltipManager.py
**Function**: Manages tooltips across different panels
- Adds comprehensive tooltips to various UI components
- Provides context-sensitive help for different panels

**Connection to Main**: Instantiated as `self.tooltip_manager` in SABREGUI

### Nested_Programs/WidgetSynchronizer.py
**Function**: Synchronizes widget values between different tabs/windows
- Keeps parameter values synchronized across Main and Advanced tabs
- Handles bidirectional widget synchronization

**Connection to Main**: Instantiated as `self.widget_synchronizer` in SABREGUI

## User Interface Panels

### Nested_Programs/Virtual_Testing_Panel.py
**Function**: Virtual testing environment for valve control visualization
- Provides visual representation of valve states using hourglass graphics
- Allows manual valve control for testing
- Shows system state changes visually
- Includes individual valve control window

**Connection to Main**: Created on-demand via `self.window_manager.open_panel("virtual")`

### Nested_Programs/FullFlowSystem.py
**Function**: Complete flow path visualization
- Shows full system flow diagram with valve states
- Provides comprehensive view of the entire SABRE system
- Visual feedback for system state changes

**Connection to Main**: Embedded in Testing tab and accessible via window manager

### Nested_Programs/TestPanels_AI_AO.py
**Function**: Analog Input/Output testing panels
- `AnalogInputPanel`: Monitors analog input channels in real-time
- `AnalogOutputPanel`: Manual control of analog output channels
- Provides hardware testing capabilities

**Connection to Main**: Embedded in Testing tab of main interface

### Nested_Programs/SLIC_Control.py
**Function**: SLIC (Spin-Lock Induced Crossing) sequence control
- Generates and sends magnetic field sequences
- Provides specialized control for SLIC experiments
- Includes waveform generation and visualization

**Connection to Main**: Available as separate tab and detachable window

### Nested_Programs/Polarization_Calc.py
**Function**: Polarization percentage calculator
- Calculates polarization from NMR data
- Provides data analysis and plotting capabilities
- Supports multiple datasets and statistical analysis

**Connection to Main**: Available as separate tab and detachable window

## Utility and Support Modules

### Nested_Programs/ParameterSection.py
**Function**: Manages parameter input sections in Advanced tab
- Creates parameter input widgets with units
- Handles parameter validation and conversion
- Provides tooltip integration for parameters

**Connection to Main**: Instantiated as `self.parameter_section` in SABREGUI

### Nested_Programs/PresetManager.py
**Function**: Advanced preset management functionality
- Provides comprehensive preset CRUD operations
- Handles preset file management
- Integrates with parameter sections for data collection

**Connection to Main**: Instantiated as `self.preset_manager` in SABREGUI

### Nested_Programs/TimerWidget.py
**Function**: Reusable timer widget component
- Provides countdown display in HH:MM:SS format
- Self-contained timer functionality
- Used by various panels requiring timing display

**Connection to Main**: Used by CountdownController and other timing components

### Nested_Programs/ToolTip.py & ToolTip_enhanced.py
**Function**: Tooltip implementation for user interface help
- `ToolTip.py`: Basic tooltip functionality
- `ToolTip_enhanced.py`: Enhanced version with multi-tab support and global management
- Provides context-sensitive help throughout the application

**Connection to Main**: Used throughout the application for user guidance

### Nested_Programs/VisualAspects.py
**Function**: Visual interface components and styling
- Provides additional visual elements for the interface
- Handles scrollable frames and visual feedback
- Includes waveform display components

**Connection to Main**: Provides visual components used throughout the application

### Nested_Programs/Utility_Functions.py
**Function**: Common utility functions used across the application
- Value conversion functions for units
- Parameter saving/loading utilities
- Waveform generation functions
- File management utilities

**Connection to Main**: Functions imported and used throughout the application

### Nested_Programs/Constants_Paths.py
**Function**: Central location for application constants and file paths
- Defines directory paths for configuration files
- DAQ device configurations
- State mapping definitions

**Connection to Main**: Constants imported and used throughout the application

## System Architecture

The SABRE Control System follows a modular architecture where:

1. **SABREPanelProgram.py** serves as the central orchestrator
2. **Controller modules** handle specific aspects of functionality (countdown, waveform, presets, etc.)
3. **Manager modules** provide higher-level coordination (UI, themes, windows, etc.)
4. **Panel modules** implement specific user interfaces (testing, SLIC, polarization calc)
5. **Utility modules** provide common functions and support

This architecture promotes:
- **Separation of concerns**: Each module has a specific responsibility
- **Maintainability**: Changes to one module don't affect others
- **Testability**: Individual modules can be tested independently
- **Extensibility**: New functionality can be added by creating new modules
- **Code reuse**: Common functionality is centralized in utility modules

## Data Flow

1. User interactions in the main GUI trigger methods in SABREGUI
2. SABREGUI delegates specific tasks to appropriate controller/manager modules
3. Controllers coordinate with DAQ hardware and state management
4. Visual feedback is provided through plot controllers and panel updates
5. Configuration and state changes are persisted through state and preset managers

This modular approach ensures that the complex SABRE control system remains manageable and extensible while providing a comprehensive user interface for scientific experiments.

## Module Dependencies

```
SABREPanelProgram.py
├── Core Controllers
│   ├── CountdownController.py
│   ├── WaveformController.py → PlotController.py
│   ├── PresetController.py → Constants_Paths.py
│   ├── PlotController.py
│   ├── StateManager.py
│   ├── DAQController.py
│   └── MethodManager.py → Utility_Functions.py
├── Specialized Controllers
│   ├── ScramController.py → Constants_Paths.py
│   ├── ThemeManager.py
│   ├── WindowManager.py
│   ├── TooltipManager.py → ToolTip.py
│   └── WidgetSynchronizer.py
├── UI Panels
│   ├── Virtual_Testing_Panel.py → Constants_Paths.py
│   ├── FullFlowSystem.py
│   ├── TestPanels_AI_AO.py
│   ├── SLIC_Control.py → Utility_Functions.py
│   └── Polarization_Calc.py
└── Utility Modules
    ├── ParameterSection.py → ToolTip.py
    ├── PresetManager.py → Constants_Paths.py
    ├── TimerWidget.py
    ├── ToolTip.py / ToolTip_enhanced.py
    ├── VisualAspects.py
    ├── Utility_Functions.py
    └── Constants_Paths.py
```

## Getting Started

1. **Main Entry Point**: Run `SABREPanelProgram.py` to start the application
2. **Dependencies**: Ensure all required Python packages are installed (tkinter, matplotlib, nidaqmx, numpy, PIL)
3. **Configuration**: The application will automatically create necessary configuration directories
4. **Hardware**: Connect NI-DAQ hardware for full functionality (virtual mode available for testing)

## Development Guidelines

- **New Features**: Create new modules in the `Nested_Programs` directory
- **Controllers**: Follow the pattern of instantiating in SABREGUI's `__init__` method
- **UI Components**: Use the UIManager for consistent styling
- **Hardware Communication**: Route all DAQ operations through DAQController or ScramController
- **State Management**: Use StateManager for configuration persistence
- **Error Handling**: Use UIManager for consistent error displays 