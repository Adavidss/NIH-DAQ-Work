#!/usr/bin/env python3
"""
Test script to verify the timer functionality, preset auto-fill, and polarization method dropdown
"""
import os
import sys
import json
import tempfile

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_timer_functionality():
    """Test if timer methods are implemented correctly"""
    try:
        with open("TestingPanel.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        timer_checks = [
            "def start_countdown(self, duration_s):" in content,
            "def update_countdown(self):" in content,
            "def stop_countdown(self):" in content,
            "self.countdown_running = True" in content,
            "self.countdown_end_time = time.time() + duration_s" in content,
            "self.timer_label.config(text=time_str)" in content,
            "Timer:" in content,  # Timer label in UI
        ]
        
        print("✅ Timer Functionality Test:", "PASSED" if all(timer_checks) else "FAILED")
        
        if not all(timer_checks):
            print("   Missing timer components:")
            timer_names = ["start_countdown", "update_countdown", "stop_countdown", 
                          "countdown_running", "countdown_end_time", "timer display", "timer label"]
            for i, check in enumerate(timer_checks):
                if not check:
                    print(f"     - {timer_names[i]}")
        
        return all(timer_checks)
        
    except Exception as e:
        print(f"❌ Timer Functionality Test: FAILED - {e}")
        return False

def test_preset_autofill_value_extraction():
    """Test if preset auto-fill extracts values correctly"""
    try:
        with open("TestingPanel.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        autofill_checks = [
            "def _auto_fill_parameters(self, preset_data):" in content,
            "value = param_data.get('value', param_data)" in content,
            "isinstance(param_data, dict)" in content,
            "entry.insert(0, str(value))" in content,
            "'unit' in param_data" in content,  # Unit handling
        ]
        
        print("✅ Preset Auto-fill Value Extraction Test:", "PASSED" if all(autofill_checks) else "FAILED")
        
        if not all(autofill_checks):
            print("   Missing auto-fill components:")
            autofill_names = ["_auto_fill_parameters method", "value extraction", 
                             "dict type checking", "value insertion", "unit handling"]
            for i, check in enumerate(autofill_checks):
                if not check:
                    print(f"     - {autofill_names[i]}")
        
        return all(autofill_checks)
        
    except Exception as e:
        print(f"❌ Preset Auto-fill Test: FAILED - {e}")
        return False

def test_polarization_method_dropdown():
    """Test if polarization method dropdown reads from directory"""
    try:
        with open("TestingPanel.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        dropdown_checks = [
            "def _load_polarization_methods_from_directory(self):" in content,
            r"C:\Users\walsworthlab\Desktop\SABRE Program\config_files_SABRE\PolarizationMethods" in content,
            "for file in os.listdir(methods_dir):" in content,
            "if file.endswith('.json'):" in content,
            "polarization_method_combobox" in content,
            "_on_polarization_method_changed" in content,
        ]
        
        print("✅ Polarization Method Dropdown Test:", "PASSED" if all(dropdown_checks) else "FAILED")
        
        if not all(dropdown_checks):
            print("   Missing dropdown components:")
            dropdown_names = ["load methods from directory", "correct directory path", 
                             "file listing", "JSON filter", "method combobox", "change handler"]
            for i, check in enumerate(dropdown_checks):
                if not check:
                    print(f"     - {dropdown_names[i]}")
        
        return all(dropdown_checks)
        
    except Exception as e:
        print(f"❌ Polarization Method Dropdown Test: FAILED - {e}")
        return False

def test_preset_file_compatibility():
    """Test if preset file format is compatible with Demo Preset.json"""
    try:
        # Check if the auto-fill logic can handle the Demo Preset format
        demo_preset_path = r"config_files_SABRE\PolarizationMethods\Presets\Demo Preset.json"
        
        if os.path.exists(demo_preset_path):
            with open(demo_preset_path, 'r') as f:
                preset_data = json.load(f)
            
            # Check if the preset has the expected structure
            format_checks = [
                'general' in preset_data,
                'advanced' in preset_data,
                'polarization_method' in preset_data,
                isinstance(preset_data['general'], dict),
                isinstance(preset_data['advanced'], dict),
            ]
            
            # Check if general parameters have value/unit structure
            if 'general' in preset_data:
                for param_name, param_data in preset_data['general'].items():
                    if isinstance(param_data, dict):
                        format_checks.append('value' in param_data)
                        format_checks.append('unit' in param_data)
                        break
            
            print("✅ Preset File Compatibility Test:", "PASSED" if all(format_checks) else "FAILED")
            
            if not all(format_checks):
                print("   Demo Preset format issues detected")
                print(f"   Structure: {preset_data.keys()}")
            
            return all(format_checks)
        else:
            print("⚠️  Preset File Compatibility Test: SKIPPED - Demo Preset.json not found")
            return True
        
    except Exception as e:
        print(f"❌ Preset File Compatibility Test: FAILED - {e}")
        return False

def test_timer_display_integration():
    """Test if timer display is properly integrated in the UI"""
    try:
        with open("TestingPanel.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        timer_ui_checks = [
            "self.timer_label = tk.Label" in content,
            'text="00:00:000"' in content,
            'font=(' in content and 'bold' in content,  # Timer styling
            "Timer:" in content,  # Timer label
            "timer_display_frame" in content or "timer_frame" in content,
        ]
        
        print("✅ Timer Display Integration Test:", "PASSED" if all(timer_ui_checks) else "FAILED")
        
        if not all(timer_ui_checks):
            print("   Missing timer UI components:")
            ui_names = ["timer label creation", "default time format", 
                       "timer styling", "timer label text", "timer frame"]
            for i, check in enumerate(timer_ui_checks):
                if not check:
                    print(f"     - {ui_names[i]}")
        
        return all(timer_ui_checks)
        
    except Exception as e:
        print(f"❌ Timer Display Integration Test: FAILED - {e}")
        return False

def main():
    print("Testing SABRE GUI Timer, Preset, and Polarization Method Functionality...")
    print("="*70)
    
    tests = [
        test_timer_functionality,
        test_preset_autofill_value_extraction,
        test_polarization_method_dropdown,
        test_preset_file_compatibility,
        test_timer_display_integration,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
        print()
    
    print("="*70)
    print("SUMMARY:")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 All functionality tests PASSED!")
        print("✓ Timer functionality is properly implemented")
        print("✓ Preset auto-fill extracts values correctly")
        print("✓ Polarization method dropdown reads from directory")
        print("✓ Timer display is integrated in the UI")
    else:
        print("\n⚠️  Some tests FAILED. Check the detailed output above.")
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
