import sys
import importlib
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_tool_registry():
    """Test the new TOOL_REGISTRY system"""
    try:
        # Explicitly add the project directory to sys.path
        project_dir = "/Users/raphaelmansuy/Github/03-working/quantalogic"
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        logger.debug(f"sys.path: {sys.path}")
        
        # Import the TOOL_REGISTRY
        from quantalogic.tools import TOOL_REGISTRY
        logger.debug(f"TOOL_REGISTRY contains {len(TOOL_REGISTRY)} tools")
        
        # Test a few specific tools
        test_tools = [
            "search_definition_names",  # Special case tool
            "read_file",               # Standard tool
            "llm",                    # Another standard tool
            "non_existent_tool"       # Tool that doesn't exist
        ]
        
        for tool_type in test_tools:
            logger.debug(f"\nTesting tool: {tool_type}")
            if tool_type in TOOL_REGISTRY:
                module_path, class_name, is_optional = TOOL_REGISTRY[tool_type]
                logger.debug(f"Found in registry: module={module_path}, class={class_name}, optional={is_optional}")
                
                # Try to import the tool using the registry info
                try:
                    full_module_path = f"quantalogic.tools{module_path}"
                    logger.debug(f"Importing from {full_module_path}")
                    module = importlib.import_module(full_module_path)
                    tool_class = getattr(module, class_name)
                    logger.debug(f"Successfully imported {class_name}: {tool_class}")
                except Exception as e:
                    logger.error(f"Failed to import {class_name} from {full_module_path}: {e}")
            else:
                logger.warning(f"Tool '{tool_type}' not found in registry")
    except Exception as e:
        logger.error(f"Error in test_tool_registry: {e}")
        import traceback
        traceback.print_exc()

def test_get_tool_class():
    """Test the get_tool_class function"""
    try:
        # Import the get_tool_class function
        from quantalogic.agent_config import get_tool_class
        
        # Test the same tools
        test_tools = [
            "search_definition_names",  # Special case tool
            "read_file",               # Standard tool
            "llm",                    # Another standard tool
            "non_existent_tool"       # Tool that doesn't exist
        ]
        
        for tool_type in test_tools:
            logger.debug(f"\nTesting get_tool_class for: {tool_type}")
            tool_class = get_tool_class(tool_type)
            if tool_class:
                logger.debug(f"Successfully got tool class for {tool_type}: {tool_class}")
            else:
                logger.warning(f"Failed to get tool class for {tool_type}")
    
    except Exception as e:
        logger.error(f"Error in test_get_tool_class: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n===== Testing TOOL_REGISTRY =====\n")
    test_tool_registry()
    
    print("\n===== Testing get_tool_class =====\n")
    test_get_tool_class()
