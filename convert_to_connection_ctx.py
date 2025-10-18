#!/usr/bin/env python3
"""
Script to convert get_db_connection() calls to connection_ctx() context manager
"""

import os
import re
from pathlib import Path

def convert_file(file_path):
    """Convert a single file from get_db_connection() to connection_ctx()"""
    print(f"Converting {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern 1: Simple get_db_connection() with conn.close()
    # Match: conn = get_db_connection() ... conn.close()
    pattern1 = r'(\s+)(conn = get_db_connection\(\)\s*\n)(.*?)(\s+conn\.close\(\)\s*\n)'
    
    def replace_pattern1(match):
        indent = match.group(1)
        conn_line = match.group(2)
        middle_code = match.group(3)
        close_line = match.group(4)
        
        # Convert SQLite placeholders to PostgreSQL
        middle_code = re.sub(r'\?', '%s', middle_code)
        
        return f"""{indent}from src.db_compat import connection_ctx
{indent}
{indent}with connection_ctx(timeout=5) as conn:
{middle_code}"""
    
    content = re.sub(pattern1, replace_pattern1, content, flags=re.DOTALL)
    
    # Pattern 2: Functions that return early before conn.close()
    # This is more complex and needs manual review
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Converted {file_path}")
        return True
    else:
        print(f"⏭️  No changes needed for {file_path}")
        return False

def main():
    """Convert all files in the routes directory"""
    routes_dir = Path("src/routes")
    
    files_to_convert = [
        "rich_admin_interface.py",
        "rich_superadmin_interface1.py", 
        "superadmin.py",
        "comprehensive_superadmin.py",
        "tenant_admin.py",
        "comprehensive_admin.py",
        "public_leaderboard.py",
        "multitenant_routing.py",
        "theme_customization.py",
        "theme_customization1.py",
        "sportsbook_registration.py",
        "sportsbook_registration1.py",
        "json_sports.py"
    ]
    
    converted_count = 0
    
    for filename in files_to_convert:
        file_path = routes_dir / filename
        if file_path.exists():
            if convert_file(file_path):
                converted_count += 1
        else:
            print(f"❌ File not found: {file_path}")
    
    print(f"\n🎯 Conversion complete! {converted_count} files converted.")

if __name__ == "__main__":
    main()
