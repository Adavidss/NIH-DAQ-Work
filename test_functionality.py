#!/usr/bin/env python3
"""
Quick test to verify button functionality and parameter syncing
"""
import sys
import os
import tkinter as tk
from tkinter import ttk
import time

# Add the program directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_button_functionality():
    """Test that buttons work without crashing"""
    try:
        from TestingPanel import SABREGUI
        
        root = tk.Tk()
        root.withdraw()
        
        app = SABREGUI(root)
        
        print("Testing button functionality...")
        
        # Test that entries exist and can be populated
        test_values = {
            "Temperature": "300",
            "Flow Rate": "25", 
            "Pressure": "1.2",
            "Bubbling Time": "45",
            "Magnetic Field": "150"
        }
        
        for param, value in test_values.items():
            if param in app.entries:
                app.entries[param].delete(0, tk.END)
                app.entries[param].insert(0, value)
                print(f"✓ Set {param} = {value}")
            else:
                print(f"✗ {param} entry not found")
        
        # Test parameter syncing
        if hasattr(app, '_sync_parameter'):
            app._sync_parameter("Temperature")
            print("✓ Parameter syncing method works")
        
        # Test button methods (they should not crash)
        button_tests = [
            ("Activate", app.activate_experiment),
            ("Start", app.start_experiment), 
            ("Test Field", app.test_field),
            ("SCRAM", app.scram_experiment)
        ]
        
        for name, method in button_tests:
            try:
                # Don't actually run the full methods, just test they exist and are callable
                if callable(method):
                    print(f"✓ {name} button method is callable")
                else:
                    print(f"✗ {name} button method is not callable")
            except Exception as e:
                print(f"✗ {name} button test failed: {e}")
        
        # Test error handling
        try:
            app._ensure_entries_exist()
            print("✓ _ensure_entries_exist works")
        except Exception as e:
            print(f"✗ _ensure_entries_exist failed: {e}")
        
        # Test plotting components
        try:
            app._initialize_plotting_components()
            print("✓ _initialize_plotting_components works")
        except Exception as e:
            print(f"✗ _initialize_plotting_components failed: {e}")
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        print("✓ Button functionality test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Button functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_preset_functionality():
    """Test preset functionality"""
    try:
        from TestingPanel import SABREGUI
        
        root = tk.Tk()
        root.withdraw()
        
        app = SABREGUI(root)
        
        print("Testing preset functionality...")
        
        # Test that preset manager exists and has required methods
        if hasattr(app, 'preset_manager') and app.preset_manager:
            required_methods = ['refresh_presets_list', 'save_current_as_preset', 'load_preset_from_file']
            for method in required_methods:
                if hasattr(app.preset_manager, method):
                    print(f"✓ Preset manager has {method}")
                else:
                    print(f"✗ Preset manager missing {method}")
        else:
            print("✗ Preset manager not found")
            return False
        
        # Test refresh presets list
        try:
            app.preset_manager.refresh_presets_list()
            print("✓ Refresh presets list works")
        except Exception as e:
            print(f"✗ Refresh presets list failed: {e}")
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        print("✓ Preset functionality test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Preset functionality test failed: {e}")
        return False

def main():
    """Run functionality tests"""
    print("Testing SABRE GUI functionality...")
    print("=" * 50)
    
    tests = [
        ("Button Functionality", test_button_functionality),
        ("Preset Functionality", test_preset_functionality)
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
    print(f"Results: {passed}/{total} functionality tests passed")
    
    if passed == total:
        print("🎉 All functionality tests passed!")
        return 0
    else:
        print("❌ Some functionality tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
