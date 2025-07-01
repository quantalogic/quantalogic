#!/bin/bash
# Migration Script: Move quantalogic to quantalogic_react
# This script automates the reorganization process

set -e  # Exit on any error

echo "🚀 QuantaLogic Reorganization Migration Script"
echo "=============================================="

# Configuration
BACKUP_DIR="../quantalogic_backup_$(date +%Y%m%d_%H%M%S)"
REACT_DIR="quantalogic_react"

# Step 1: Create additional backup (safety first)
echo "📦 Creating migration backup..."
if [ ! -d "$BACKUP_DIR" ]; then
    cp -r . "$BACKUP_DIR"
    echo "✅ Migration backup created: $BACKUP_DIR"
else
    echo "⚠️  Backup directory already exists, skipping backup"
fi

# Step 2: Create quantalogic_react directory structure
echo "📁 Creating quantalogic_react directory structure..."
mkdir -p "$REACT_DIR"
echo "✅ Created $REACT_DIR directory"

# Step 3: Move quantalogic source to quantalogic_react/quantalogic
echo "🔄 Moving quantalogic source code..."
mv quantalogic "$REACT_DIR/"
echo "✅ Moved quantalogic/ → $REACT_DIR/quantalogic/"

# Step 4: Create root quantalogic package with re-exports
echo "📄 Creating root quantalogic re-export package..."
mkdir -p quantalogic

# Create new root __init__.py with re-exports
cat > quantalogic/__init__.py << 'EOF'
"""QuantaLogic package initialization - Re-export from quantalogic_react."""

import warnings
from importlib.metadata import version as get_version

# Suppress specific warnings related to Pydantic's V2 configuration changes
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.*",
    message=".*config keys have changed in V2:.*|.*'fields' config key is removed in V2.*",
)

try:
    __version__: str = get_version("quantalogic")
except Exception as e:
    __version__ = "unknown"
    print(f"Unable to retrieve version: {e}")

# Re-export public API from quantalogic_react
from quantalogic_react.quantalogic.agent import Agent  # noqa: E402
from quantalogic_react.quantalogic.console_print_events import console_print_events  # noqa: E402
from quantalogic_react.quantalogic.console_print_token import console_print_token  # noqa: E402
from quantalogic_react.quantalogic.create_custom_agent import create_custom_agent  # noqa: E402
from quantalogic_react.quantalogic.event_emitter import EventEmitter  # noqa: E402
from quantalogic_react.quantalogic.memory import AgentMemory, VariableMemory  # noqa: E402

__all__ = [
    "Agent",
    "EventEmitter",
    "AgentMemory",
    "VariableMemory",
    "console_print_events",
    "console_print_token",
    "create_custom_agent"
]
EOF

echo "✅ Created root quantalogic/__init__.py with re-exports"

# Step 5: Create tools re-export
echo "🛠️  Creating tools re-export..."
mkdir -p quantalogic/tools
cat > quantalogic/tools/__init__.py << 'EOF'
"""Tools re-export from quantalogic_react."""
from quantalogic_react.quantalogic.tools import *  # noqa: F403,F401
EOF

echo "✅ Created quantalogic/tools/__init__.py"

# Step 6: Create flow re-export (preserve existing)
echo "🌊 Creating flow re-export..."
mkdir -p quantalogic/flow
cat > quantalogic/flow/__init__.py << 'EOF'
"""Stub alias for backwards compatibility: re-export Flow API from the quantalogic_flow package."""
from quantalogic_flow import (
    Nodes,
    Workflow,
    WorkflowEngine,
    WorkflowManager,
    extract_workflow_from_file,
    generate_executable_script,
    generate_mermaid_diagram,
    validate_workflow_definition,
)

__all__ = [
    "extract_workflow_from_file",
    "generate_executable_script",
    "generate_mermaid_diagram",
    "Nodes",
    "validate_workflow_definition",
    "Workflow",
    "WorkflowEngine",
    "WorkflowManager",
]
EOF

echo "✅ Created quantalogic/flow/__init__.py"

# Step 7: Create main CLI re-export
echo "⚙️  Creating main CLI re-export..."
cat > quantalogic/main.py << 'EOF'
"""Main CLI re-export from quantalogic_react."""
from quantalogic_react.quantalogic.main import cli

if __name__ == "__main__":
    cli()
EOF

echo "✅ Created quantalogic/main.py"

# Step 8: Update pyproject.toml CLI pointer
echo "📝 Updating pyproject.toml CLI pointer..."
sed -i.bak 's/quantalogic = "quantalogic.main:cli"/quantalogic = "quantalogic_react.quantalogic.main:cli"/' pyproject.toml
echo "✅ Updated pyproject.toml CLI pointer"

echo ""
echo "🎉 Migration completed successfully!"
echo "📍 New structure:"
echo "   - quantalogic_react/quantalogic/  (moved React source)"
echo "   - quantalogic/                    (re-export package)" 
echo "   - pyproject.toml                  (updated CLI pointer)"
echo ""
echo "⚠️  Next steps:"
echo "   1. Test imports: python -c 'from quantalogic import Agent'"
echo "   2. Test CLI: quantalogic --help"
echo "   3. Run test suite"
echo "   4. If issues, rollback with rollback_migration.sh"
