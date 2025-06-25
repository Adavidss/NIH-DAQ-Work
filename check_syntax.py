#!/usr/bin/env python3
"""
Simple syntax check for TestingPanel.py
"""
import ast
import sys

def check_syntax(filename):
    """Check if a Python file has valid syntax"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Parse the AST to check for syntax errors
        ast.parse(source, filename=filename)
        print(f"✓ {filename}: Syntax is valid")
        return True
        
    except SyntaxError as e:
        print(f"✗ {filename}: Syntax error at line {e.lineno}: {e.msg}")
        if e.text:
            print(f"  {e.text.strip()}")
        return False
    except Exception as e:
        print(f"✗ {filename}: Error checking syntax: {e}")
        return False

if __name__ == "__main__":
    files_to_check = [
        "TestingPanel.py",
        "Nested_Programs/ParameterSection.py", 
        "Nested_Programs/Virtual_Testing_Panel.py",
        "Nested_Programs/VisualAspects.py"
    ]
    
    all_valid = True
    for filename in files_to_check:
        try:
            if not check_syntax(filename):
                all_valid = False
        except FileNotFoundError:
            print(f"✗ {filename}: File not found")
            all_valid = False
    
    if all_valid:
        print("\n✓ All files have valid syntax!")
        sys.exit(0)
    else:
        print("\n✗ Some files have syntax errors")
        sys.exit(1)
