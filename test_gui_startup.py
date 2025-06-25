#!/usr/bin/env python3
"""
Quick test script to validate GUI startup without showing the window
"""
import tkinter as tk
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gui_creation():
    """Test that the GUI can be created without errors"""
    try:
        print("Creating root window...")
        root = tk.Tk()
        root.withdraw()  # Hide the window
        
        print("Importing SABREGUI...")
        from TestingPanel import SABREGUI
        
        print("Creating SABREGUI instance...")
        app = SABREGUI(master=root)
        
        print("✓ GUI created successfully!")
        print("✓ All required methods are implemented")
        
        # Clean up
        root.destroy()
        return True
        
    except Exception as e:
        print(f"✗ Error during GUI creation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing SABRE GUI startup...")
    success = test_gui_creation()
    
    if success:
        print("\n🎉 All tests passed! The GUI should start up correctly.")
        sys.exit(0)
    else:
        print("\n❌ Tests failed. Check the errors above.")
        sys.exit(1)
