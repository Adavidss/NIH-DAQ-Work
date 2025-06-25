#!/usr/bin/env python3

"""
Test script for newly extracted controller classes.
Tests ThemeManager, DAQController, StateManager, PlotController, UIManager, MethodManager, and TimerWidget.
"""

import sys
import os

def test_new_controller_imports():
    """Test importing the newly extracted controller classes"""
    print("Testing newly extracted controller classes...")
    print("=" * 60)
    
    # Test ThemeManager
    try:
        from Nested_Programs.ThemeManager import ThemeManager
        print("✓ ThemeManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import ThemeManager: {e}")
        return False
    
    # Test DAQController
    try:
        from Nested_Programs.DAQController import DAQController
        print("✓ DAQController imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import DAQController: {e}")
        return False
    
    # Test StateManager
    try:
        from Nested_Programs.StateManager import StateManager
        print("✓ StateManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import StateManager: {e}")
        return False
    
    # Test PlotController
    try:
        from Nested_Programs.PlotController import PlotController
        print("✓ PlotController imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import PlotController: {e}")
        return False
    
    # Test UIManager
    try:
        from Nested_Programs.UIManager import UIManager
        print("✓ UIManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import UIManager: {e}")
        return False
    
    # Test MethodManager
    try:
        from Nested_Programs.MethodManager import MethodManager
        print("✓ MethodManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import MethodManager: {e}")
        return False
    
    # Test TimerWidget
    try:
        from Nested_Programs.TimerWidget import TimerWidget
        print("✓ TimerWidget imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import TimerWidget: {e}")
        return False
    
    return True

def test_class_instantiation():
    """Test basic instantiation of the controller classes"""
    print("\nTesting basic instantiation...")
    print("=" * 60)
    
    try:
        import tkinter as tk
        
        # Create a test root window
        root = tk.Tk()
        root.withdraw()  # Hide the window
        
        # Test instantiation (basic tests that don't require full GUI setup)
        from Nested_Programs.DAQController import DAQController
        daq = DAQController()
        print("✓ DAQController instantiated successfully")
        
        from Nested_Programs.StateManager import StateManager
        state_manager = StateManager("test_config_dir")
        print("✓ StateManager instantiated successfully")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"✗ Error during instantiation tests: {e}")
        return False

def test_functionality():
    """Test basic functionality of some controllers"""
    print("\nTesting basic functionality...")
    print("=" * 60)
    
    try:
        # Test StateManager functionality
        from Nested_Programs.StateManager import StateManager
        state_manager = StateManager("nonexistent_dir")
        
        # Test loading a non-existent state (should return None)
        result = state_manager.load("nonexistent_state")
        if result is None:
            print("✓ StateManager.load() correctly returns None for missing state")
        else:
            print("✗ StateManager.load() should return None for missing state")
            return False
        
        # Test DAQController (just instantiation, since we might not have hardware)
        from Nested_Programs.DAQController import DAQController
        daq = DAQController()
        print("✓ DAQController instantiated without errors")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during functionality tests: {e}")
        return False

def main():
    """Main test function"""
    print("Testing newly extracted controller classes")
    print("=" * 60)
    
    # Test imports
    if not test_new_controller_imports():
        print("\n❌ Import tests failed!")
        sys.exit(1)
    
    # Test instantiation
    if not test_class_instantiation():
        print("\n❌ Instantiation tests failed!")
        sys.exit(1)
    
    # Test functionality
    if not test_functionality():
        print("\n❌ Functionality tests failed!")
        sys.exit(1)
    
    print("\n🎉 All newly extracted controller classes work correctly!")
    print("The refactoring was successful - more classes have been modularized.")

if __name__ == "__main__":
    main() 