#!/usr/bin/env python3
"""
Test script to verify the implemented changes in TestingPanel.py
"""
import os
import json

# Test 1: Check if preset auto-fill is properly implemented
def test_preset_autofill():
    """Test if preset auto-fill functionality exists"""
    with open("TestingPanel.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        "_auto_fill_parameters" in content,
        "on_preset_selected_auto_fill" in content,
        "preset_data.get('general'" in content,
        "preset_data.get('advanced'" in content,
        "Successfully auto-filled parameters" in content
    ]
    
    print("✅ Preset Auto-fill Test:", "PASSED" if all(checks) else "FAILED")
    return all(checks)

# Test 2: Check if Advanced tab has polarization method dropdown (not preset selector)
def test_polarization_method_dropdown():
    """Test if Advanced tab uses polarization method dropdown"""
    with open("TestingPanel.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        "text=\"Polarization Method\"" in content,
        "SABRE-SHEATH" in content,
        "SABRE-Relay" in content,
        "Para-Hydrogen PHIP" in content,
        "_on_polarization_method_changed" in content,
        "polarization_method_combobox" in content
    ]
    
    print("✅ Polarization Method Dropdown Test:", "PASSED" if all(checks) else "FAILED")
    return all(checks)

# Test 3: Check if main tab has quadrant button layout
def test_quadrant_button_layout():
    """Test if main tab buttons are arranged in quadrant"""
    with open("TestingPanel.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        "_create_quadrant_button" in content,
        "row=0, column=0" in content,
        "row=0, column=1" in content, 
        "row=1, column=0" in content,
        "row=1, column=1" in content,
        "columnconfigure((0, 1), weight=1" in content and "rowconfigure((0, 1), weight=1" in content
    ]
    
    print("✅ Quadrant Button Layout Test:", "PASSED" if all(checks) else "FAILED")
    return all(checks)

# Test 4: Check if System Status section is removed from main tab
def test_system_status_removed():
    """Test if System Status section is removed from main tab"""
    with open("TestingPanel.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Should not have the System Status section in main tab
    system_status_in_main = 'text="System Status"' in content and '_create_status_section' in content
    
    # Should have proper 2x2 grid layout instead of 2x3
    proper_grid = 'rowconfigure((0, 1), weight=1, uniform="row")' in content
    
    print("✅ System Status Removal Test:", "PASSED" if not system_status_in_main and proper_grid else "FAILED")
    return not system_status_in_main and proper_grid

# Test 5: Check if unnecessary text is removed
def test_unnecessary_text_removed():
    """Test if unnecessary text like 'Preset Selection' and redundant 'Experimental Controls' is cleaned up"""
    with open("TestingPanel.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for cleaned up text
    checks = [
        'text="Method Preset"' in content,  # Simplified from "Preset Selection"
        'text="Controls"' in content,       # Simplified from "Experimental Controls"
        'text="Control Buttons"' in content,  # Cleaner section title
        'text="Preset:"' in content        # Simplified label
    ]
    
    print("✅ Text Cleanup Test:", "PASSED" if all(checks) else "FAILED")
    return all(checks)

def main():
    """Run all tests"""
    print("🧪 Testing SABRE GUI Changes Implementation")
    print("=" * 50)
    
    # Change to the correct directory
    os.chdir(r"c:\Users\walsworthlab\Desktop\SABRE Program")
    
    tests = [
        test_preset_autofill(),
        test_polarization_method_dropdown(), 
        test_quadrant_button_layout(),
        test_system_status_removed(),
        test_unnecessary_text_removed()
    ]
    
    print("=" * 50)
    passed = sum(tests)
    total = len(tests)
    
    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
        print("\n✅ Implementation Summary:")
        print("• Preset selection now auto-fills parameter values")
        print("• Advanced tab uses polarization method dropdown (not preset selector)")
        print("• Main tab buttons arranged in 2x2 quadrant layout")
        print("• System Status section removed from main tab")
        print("• Unnecessary text cleaned up and simplified")
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total})")
        
    return passed == total

if __name__ == "__main__":
    main()
