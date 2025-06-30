"""Basic test to verify core functionality works before reorganization."""

def test_quantalogic_import():
    """Test that basic quantalogic imports work."""
    try:
        from quantalogic import Agent
        from quantalogic.tools import Tool
        from quantalogic.flow import Workflow
        assert Agent is not None
        assert Tool is not None  
        assert Workflow is not None
        return True
    except ImportError as e:
        print(f"Import failed: {e}")
        return False

def test_basic_functionality():
    """Test basic Agent instantiation."""
    try:
        from quantalogic import Agent
        
        # Try to create an agent with minimal config
        agent = Agent(
            model_name="gpt-3.5-turbo"
        )
        assert agent is not None
        return True
    except Exception as e:
        print(f"Agent creation failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing basic imports...")
    if test_quantalogic_import():
        print("✅ Basic imports work")
    else:
        print("❌ Basic imports failed")
        
    print("Testing basic functionality...")
    if test_basic_functionality():
        print("✅ Basic functionality works")
    else:
        print("❌ Basic functionality failed")
