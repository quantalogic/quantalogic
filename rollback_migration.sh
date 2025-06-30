#!/bin/bash
# Rollback Script: Restore original quantalogic structure
# This script reverses the reorganization if issues occur

set -e  # Exit on any error

echo "🔄 QuantaLogic Reorganization Rollback Script"
echo "============================================="

# Find the latest backup
BACKUP_DIR=$(ls -td ../quantalogic_backup_* | head -1)

if [ -z "$BACKUP_DIR" ]; then
    echo "❌ No backup directory found! Cannot rollback."
    echo "Available backups:"
    ls -la ../quantalogic_backup_* 2>/dev/null || echo "None found"
    exit 1
fi

echo "📁 Found backup: $BACKUP_DIR"

# Confirm rollback
echo "⚠️  This will restore the original structure from backup."
echo "⚠️  Current changes will be lost!"
read -p "Are you sure you want to rollback? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Rollback cancelled"
    exit 1
fi

# Step 1: Remove current reorganized structure
echo "🗑️  Removing current reorganized structure..."
if [ -d "quantalogic_react" ]; then
    rm -rf quantalogic_react
    echo "✅ Removed quantalogic_react/"
fi

if [ -d "quantalogic" ]; then
    rm -rf quantalogic
    echo "✅ Removed current quantalogic/"
fi

# Step 2: Restore original structure from backup
echo "📦 Restoring original structure from backup..."
cp -r "$BACKUP_DIR/quantalogic" .
cp "$BACKUP_DIR/pyproject.toml" .
echo "✅ Restored quantalogic/ and pyproject.toml from backup"

# Step 3: Verify restoration
echo "🔍 Verifying restoration..."
if [ -f "quantalogic/__init__.py" ] && [ -f "quantalogic/main.py" ]; then
    echo "✅ Core files restored successfully"
else
    echo "❌ Restoration may have failed - check manually"
    exit 1
fi

# Step 4: Test basic functionality
echo "🧪 Testing basic functionality..."
if python -c "from quantalogic import Agent; print('✅ Import test passed')" 2>/dev/null; then
    echo "✅ Basic imports working"
else
    echo "⚠️  Import test failed - manual verification needed"
fi

echo ""
echo "🎉 Rollback completed successfully!"
echo "📍 Restored structure:"
echo "   - quantalogic/        (original React source)"
echo "   - pyproject.toml      (original configuration)"
echo ""
echo "ℹ️  The backup used: $BACKUP_DIR"
echo "ℹ️  You can delete backup directories when confident in the restoration"
