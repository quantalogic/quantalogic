#!/usr/bin/env python3
"""Fix internal imports in quantalogic_react after reorganization."""

import os
import re
import glob

def fix_internal_imports():
    """Fix internal quantalogic imports in moved files."""
    
    # Find all Python files in quantalogic_react
    python_files = glob.glob("quantalogic_react/**/*.py", recursive=True)
    
    print(f"🔧 Found {len(python_files)} Python files to process")
    
    # Pattern to match internal quantalogic imports
    pattern = r'^(\s*)from quantalogic\.([^_\s]+)(.*)$'
    replacement = r'\1from quantalogic_react.quantalogic.\2\3'
    
    files_modified = 0
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            modified_lines = []
            file_changed = False
            
            for line in lines:
                # Check for internal quantalogic imports (not quantalogic_flow or quantalogic_codeact)
                if re.match(r'^\s*from quantalogic\.(?!flow|codeact)', line):
                    # Replace with quantalogic_react.quantalogic prefix
                    new_line = re.sub(pattern, replacement, line)
                    if new_line != line:
                        modified_lines.append(new_line)
                        file_changed = True
                        print(f"  📝 {file_path}: {line.strip()} → {new_line.strip()}")
                    else:
                        modified_lines.append(line)
                else:
                    modified_lines.append(line)
            
            if file_changed:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(modified_lines))
                files_modified += 1
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
    
    print(f"✅ Modified {files_modified} files")
    return files_modified

if __name__ == "__main__":
    print("🔧 Fixing internal imports in quantalogic_react...")
    modified_count = fix_internal_imports()
    print(f"🎉 Import fix completed! Modified {modified_count} files.")
