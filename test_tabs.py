#!/usr/bin/env python
"""
Quick test script to verify TestingPanel.py tabs are working correctly
"""
import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # Try to import the main class
    from TestingPanel import SABREGUI
    print("✓ Successfully imported SABREGUI")
    
    # Try to create a basic instance to test initialization
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # Hide the window for testing
    
    try:
        app = SABREGUI(master=root)
        print("✓ Successfully created SABREGUI instance")
        
        # Check if all expected tabs exist
        expected_tabs = ["Main", "Advanced Parameters", "Testing", "SLIC Control", "Polarization Cal"]
        actual_tabs = []
        
        for i in range(len(app.notebook.tabs())):
            tab_text = app.notebook.tab(i, "text")
            actual_tabs.append(tab_text)
        
        print(f"✓ Found tabs: {actual_tabs}")
        
        missing_tabs = set(expected_tabs) - set(actual_tabs)
        extra_tabs = set(actual_tabs) - set(expected_tabs)
        
        if missing_tabs:
            print(f"⚠ Missing tabs: {missing_tabs}")
        if extra_tabs:
            print(f"⚠ Extra tabs: {extra_tabs}")
        
        if not missing_tabs and not extra_tabs:
            print("✓ All expected tabs present and no extra tabs found")
        
        # Check if method comboboxes exist
        if hasattr(app, 'method_combobox'):
            print("✓ Main tab method combobox exists")
        else:
            print("⚠ Main tab method combobox missing")
            
        if hasattr(app, 'adv_method_combobox'):
            print("✓ Advanced Parameters method combobox exists")
        else:
            print("⚠ Advanced Parameters method combobox missing")
        
        # Check if control buttons exist
        control_buttons = ['activate_button', 'start_button', 'test_field_button', 'scram_button']
        for button_name in control_buttons:
            if hasattr(app, button_name):
                print(f"✓ {button_name} exists")
            else:
                print(f"⚠ {button_name} missing")
        
        # Check if timer exists
        if hasattr(app, 'timer_label'):
            print("✓ Timer label exists")
        else:
            print("⚠ Timer label missing")
            
        print("\n✓ Tab structure test completed successfully!")
        
    except Exception as e:
        print(f"✗ Error creating SABREGUI instance: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        root.destroy()
        
except Exception as e:
    print(f"✗ Error importing SABREGUI: {e}")
    import traceback
    traceback.print_exc()

print("\nTest completed.")
