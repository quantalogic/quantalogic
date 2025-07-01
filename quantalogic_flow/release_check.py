#!/usr/bin/env python3
"""Release verification script for quantalogic-flow v0.6.3"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n✓ {description}")
    print(f"  Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent)
        if result.returncode == 0:
            print("  ✅ Success")
            return True
        else:
            print(f"  ❌ Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    print("🚀 Quantalogic Flow v0.6.3 Release Verification")
    print("=" * 50)
    
    checks = [
        ("python -m pytest --tb=short -q", "Running all tests"),
        ("python -c \"import quantalogic_flow; print('Import successful')\"", "Testing import"),
        ("python -c \"from quantalogic_flow import WorkflowManager; print('WorkflowManager import OK')\"", "Testing WorkflowManager import"),
        ("poetry build", "Building package"),
        ("python -c \"import toml; data=toml.load('pyproject.toml'); print(f'Version in pyproject.toml: {data[\\\"tool\\\"][\\\"poetry\\\"][\\\"version\\\"]}')\"", "Checking version in pyproject.toml"),
    ]
    
    success_count = 0
    for cmd, desc in checks:
        if run_command(cmd, desc):
            success_count += 1
    
    print(f"\n📊 Results: {success_count}/{len(checks)} checks passed")
    
    if success_count == len(checks):
        print("\n🎉 All checks passed! Ready for release.")
        print("\nTo publish:")
        print("  poetry publish --build")
        return 0
    else:
        print("\n❌ Some checks failed. Please review before release.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
