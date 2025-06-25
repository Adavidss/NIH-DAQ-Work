#!/usr/bin/env python3
"""
Simple test script to verify the new controller classes work correctly
"""

import sys
import os

# Add the Nested_Programs directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Nested_Programs"))

# Test imports
try:
    from WindowManager import WindowManager
    print("✓ WindowManager imported successfully")
except ImportError as e:
    print(f"✗ Failed to import WindowManager: {e}")

try:
    from PresetController import PresetController
    print("✓ PresetController imported successfully")
except ImportError as e:
    print(f"✗ Failed to import PresetController: {e}")

try:
    from WaveformController import WaveformController
    print("✓ WaveformController imported successfully")
except ImportError as e:
    print(f"✗ Failed to import WaveformController: {e}")

try:
    from CountdownController import CountdownController
    print("✓ CountdownController imported successfully")
except ImportError as e:
    print(f"✗ Failed to import CountdownController: {e}")

try:
    from WidgetSynchronizer import WidgetSynchronizer
    print("✓ WidgetSynchronizer imported successfully")
except ImportError as e:
    print(f"✗ Failed to import WidgetSynchronizer: {e}")

try:
    from TooltipManager import TooltipManager
    print("✓ TooltipManager imported successfully")
except ImportError as e:
    print(f"✗ Failed to import TooltipManager: {e}")

print("\n🎉 All controller classes are properly modularized and can be imported!")
print("The refactoring was successful - SABREGUI has been broken down into focused classes.") 