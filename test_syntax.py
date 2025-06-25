#!/usr/bin/env python3
"""Test script to check for syntax errors in TestingPanel.py"""

import ast
import sys

def check_syntax(filename):
    """Check Python file for syntax errors"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Try to parse the AST
        ast.parse(source, filename=filename)
        print(f"✅ {filename} - No syntax errors found")
        return True
        
    except SyntaxError as e:
        print(f"❌ {filename} - Syntax error on line {e.lineno}: {e.msg}")
        print(f"   Text: {e.text}")
        return False
    except Exception as e:
        print(f"❌ {filename} - Error: {e}")
        return False

if __name__ == "__main__":
    files_to_check = [
        "TestingPanel.py"
    ]
    
    all_good = True
    for filename in files_to_check:
        if not check_syntax(filename):
            all_good = False
    
    if all_good:
        print("\n🎉 All files passed syntax check!")
    else:
        print("\n💥 Some files have syntax errors.")
        sys.exit(1)
