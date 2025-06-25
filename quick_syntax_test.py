#!/usr/bin/env python3
"""
Quick syntax test for TestingPanel.py
"""
import ast
import traceback

def test_syntax():
    try:
        with open("TestingPanel.py", 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Try to parse the AST
        ast.parse(source, filename="TestingPanel.py")
        print("✅ TestingPanel.py has valid syntax!")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in TestingPanel.py:")
        print(f"  Line {e.lineno}: {e.msg}")
        if e.text:
            print(f"  Code: {e.text.strip()}")
        return False
    except Exception as e:
        print(f"❌ Error checking syntax: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_syntax()
