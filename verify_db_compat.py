#!/usr/bin/env python3
"""
Quick script to verify which db_compat file is being imported
Run this to see which db_compat is actually loaded
"""

import sys
import os

def check_db_compat():
    """Check which db_compat is being imported"""
    print("🔍 Checking db_compat import...")
    
    try:
        # Try to import db_compat
        import db_compat
        print(f"✅ Imported db_compat from: {db_compat.__file__}")
        print(f"   Absolute path: {os.path.abspath(db_compat.__file__)}")
        
        # Check if it's the root or src version
        if 'src' in db_compat.__file__:
            print("   📁 This is the src/db_compat.py version")
        else:
            print("   📁 This is the root db_compat.py version")
            
    except ImportError as e:
        print(f"❌ Could not import db_compat: {e}")
        return False
    
    try:
        # Try to import from src.db_compat
        import src.db_compat as src_db_compat
        print(f"✅ Imported src.db_compat from: {src_db_compat.__file__}")
        print(f"   Absolute path: {os.path.abspath(src_db_compat.__file__)}")
        
    except ImportError as e:
        print(f"❌ Could not import src.db_compat: {e}")
    
    return True

def check_imports():
    """Check what's in sys.modules"""
    print("\n🔍 Checking sys.modules for db_compat...")
    
    for module_name in sys.modules:
        if 'db_compat' in module_name:
            module = sys.modules[module_name]
            if hasattr(module, '__file__'):
                print(f"   {module_name}: {module.__file__}")

if __name__ == "__main__":
    print("🚀 db_compat Import Verification")
    print("=" * 50)
    
    check_db_compat()
    check_imports()
    
    print("\n" + "=" * 50)
    print("💡 To verify in your app, add this to your code:")
    print("   import src.db_compat as _dbc")
    print("   print('Using db_compat:', _dbc.__file__)")
