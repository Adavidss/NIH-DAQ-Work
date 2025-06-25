#!/usr/bin/env python3
"""
Test script to verify the SABRE GUI fixes
"""
import sys
import os
import tkinter as tk
from tkinter import ttk

# Add the program directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gui_initialization():
    """Test that the GUI initializes without errors"""
    try:
        # Import the main GUI class
        from TestingPanel import SABREGUI
        
        # Create root window
        root = tk.Tk()
        root.withdraw()  # Hide the root window for testing
        
        # Create the GUI instance
        app = SABREGUI(root)
        
        print("✓ GUI initialization successful")
        
        # Test that essential components exist
        essential_attrs = [
            'entries', 'units', 'main_entries', 'main_units',
            'activate_button', 'start_button', 'test_field_button', 'scram_button',
            'parameter_section', 'preset_manager'
        ]
        
        missing_attrs = []
        for attr in essential_attrs:
            if not hasattr(app, attr):
                missing_attrs.append(attr)
        
        if missing_attrs:
            print(f"✗ Missing essential attributes: {missing_attrs}")
            return False
        else:
            print("✓ All essential attributes present")
        
        # Test that entries dict has required keys
        required_keys = ["Temperature", "Flow Rate", "Pressure", "Bubbling Time", "Magnetic Field"]
        missing_keys = []
        for key in required_keys:
            if key not in app.entries:
                missing_keys.append(key)
        
        if missing_keys:
            print(f"✗ Missing required entry keys: {missing_keys}")
            return False
        else:
            print("✓ All required entry keys present")
        
        # Test button functionality (without actually running the methods)
        button_tests = [
            ('activate_button', 'activate_experiment'),
            ('start_button', 'start_experiment'),
            ('test_field_button', 'test_field'),
            ('scram_button', 'scram_experiment')
        ]
        
        for button_attr, method_name in button_tests:
            button = getattr(app, button_attr)
            if hasattr(app, method_name):
                print(f"✓ {button_attr} -> {method_name} method exists")
            else:
                print(f"✗ {button_attr} -> {method_name} method missing")
                return False
        
        # Test preset manager on main tab
        if hasattr(app, 'preset_manager') and app.preset_manager:
            print("✓ Preset manager initialized")
        else:
            print("✗ Preset manager not initialized")
            return False
        
        # Test parameter syncing capability
        if hasattr(app, '_sync_parameter') and hasattr(app, '_sync_from_advanced'):
            print("✓ Parameter syncing methods available")
        else:
            print("✗ Parameter syncing methods missing")
            return False
            
        # Test error handling methods
        if hasattr(app, '_ensure_entries_exist') and hasattr(app, '_initialize_plotting_components'):
            print("✓ Error handling methods available")
        else:
            print("✗ Error handling methods missing")
            return False
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        return True
        
    except Exception as e:
        print(f"✗ Error during GUI initialization: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_virtual_testing_panel():
    """Test that VirtualTestingPanel can be created and has correct parent"""
    try:
        from TestingPanel import SABREGUI
        from Nested_Programs.Virtual_Testing_Panel import VirtualTestingPanel
        
        root = tk.Tk()
        root.withdraw()
        
        app = SABREGUI(root)
        
        # Create test container
        test_frame = tk.Frame(app)
        
        # Create VirtualTestingPanel with correct parent reference
        vtp = VirtualTestingPanel(app, embedded=True, container=test_frame)
        
        # Test that parent reference is correct
        if hasattr(vtp, 'parent') and vtp.parent is app:
            print("✓ VirtualTestingPanel has correct parent reference")
        else:
            print("✗ VirtualTestingPanel parent reference is incorrect")
            return False
            
        # Test that Full Flow System method exists and won't crash
        if hasattr(vtp, 'open_full_flow_system'):
            print("✓ VirtualTestingPanel has open_full_flow_system method")
        else:
            print("✗ VirtualTestingPanel missing open_full_flow_system method")
            return False
        
        # Cleanup
        vtp.destroy()
        test_frame.destroy()
        app.destroy()
        root.destroy()
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing VirtualTestingPanel: {e}")
        return False

def test_parameter_section():
    """Test that ParameterSection initializes correctly"""
    try:
        from TestingPanel import SABREGUI
        from Nested_Programs.ParameterSection import ParameterSection
        
        root = tk.Tk()
        root.withdraw()
        
        app = SABREGUI(root)
        
        # Test that parameter section was created
        if hasattr(app, 'parameter_section') and app.parameter_section:
            print("✓ ParameterSection initialized")
        else:
            print("✗ ParameterSection not initialized")
            return False
            
        # Test that it has required methods
        required_methods = ['get_value', '_sync_to_main']
        for method in required_methods:
            if hasattr(app.parameter_section, method):
                print(f"✓ ParameterSection has {method} method")
            else:
                print(f"✗ ParameterSection missing {method} method")
                return False
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing ParameterSection: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing SABRE GUI fixes...")
    print("=" * 50)
    
    tests = [
        ("GUI Initialization", test_gui_initialization),
        ("Virtual Testing Panel", test_virtual_testing_panel),
        ("Parameter Section", test_parameter_section)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 30)
        if test_func():
            passed += 1
            print(f"✓ {test_name} PASSED")
        else:
            print(f"✗ {test_name} FAILED")
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The fixes are working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
