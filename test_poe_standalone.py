#!/usr/bin/env python3
"""
Standalone POE Integration Test

This script tests the POE API integration without requiring the full test suite infrastructure.
"""

import os
import sys
import tempfile
from typing import Any, Dict

# Add the project path
sys.path.insert(0, '/home/runner/work/quantalogic/quantalogic')


class MockResponse:
    """Mock LLM response for testing."""
    def __init__(self, content: str = "Test response"):
        self.choices = [MockChoice(content)]
        self.usage = MockUsage()


class MockChoice:
    """Mock choice for response."""
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockMessage:
    """Mock message."""
    def __init__(self, content: str):
        self.content = content


class MockUsage:
    """Mock usage stats."""
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.total_tokens = 30


def test_poe_provider_configuration():
    """Test POE provider configuration."""
    print("🧪 Testing POE Provider Configuration...")
    
    try:
        # Import the ModelProviderConfig directly
        from quantalogic_react.quantalogic.quantlitellm import ModelProviderConfig
        
        # Create POE configuration
        poe_config = ModelProviderConfig(
            prefix="poe/",
            provider="openai",
            base_url="https://api.poe.com/v1",
            env_var="POE_API_KEY",
        )
        
        # Test basic properties
        assert poe_config.prefix == "poe/"
        assert poe_config.provider == "openai"
        assert poe_config.base_url == "https://api.poe.com/v1"
        assert poe_config.env_var == "POE_API_KEY"
        
        print("✅ POE provider configuration properties are correct")
        
        # Test configure method without API key (should fail)
        kwargs = {"model": "poe/Claude-Sonnet-4"}
        try:
            poe_config.configure("poe/Claude-Sonnet-4", kwargs)
            print("❌ Should have failed without API key")
            return False
        except ValueError as e:
            if "POE_API_KEY is not set" in str(e):
                print("✅ Correctly failed without API key")
            else:
                print(f"❌ Wrong error message: {e}")
                return False
        
        # Test configure method with API key
        os.environ["POE_API_KEY"] = "test-api-key"
        kwargs = {"model": "poe/Claude-Sonnet-4"}
        poe_config.configure("poe/Claude-Sonnet-4", kwargs)
        
        expected = {
            "model": "Claude-Sonnet-4",  # prefix removed
            "custom_llm_provider": "openai",
            "base_url": "https://api.poe.com/v1",
            "api_key": "test-api-key"
        }
        
        for key, value in expected.items():
            if kwargs.get(key) != value:
                print(f"❌ Expected {key}={value}, got {kwargs.get(key)}")
                return False
        
        print("✅ POE provider configuration method works correctly")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_poe_providers_registry():
    """Test POE is in the PROVIDERS registry."""
    print("\n🧪 Testing POE in Providers Registry...")
    
    try:
        from quantalogic_react.quantalogic.quantlitellm import PROVIDERS
        
        if "poe" not in PROVIDERS:
            print("❌ POE provider not found in PROVIDERS registry")
            return False
        
        poe_config = PROVIDERS["poe"]
        
        # Verify all expected providers are present
        expected_providers = ["dashscope", "nvidia", "ovh", "poe"]
        for provider in expected_providers:
            if provider not in PROVIDERS:
                print(f"❌ Provider {provider} not found")
                return False
        
        print(f"✅ All expected providers found: {list(PROVIDERS.keys())}")
        
        # Verify POE configuration
        assert poe_config.prefix == "poe/"
        assert poe_config.provider == "openai"
        assert poe_config.base_url == "https://api.poe.com/v1"
        assert poe_config.env_var == "POE_API_KEY"
        
        print("✅ POE provider in registry with correct configuration")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_model_name_variations():
    """Test different POE model name variations."""
    print("\n🧪 Testing POE Model Name Variations...")
    
    try:
        from quantalogic_react.quantalogic.quantlitellm import PROVIDERS
        
        poe_config = PROVIDERS["poe"]
        os.environ["POE_API_KEY"] = "test-key"
        
        test_cases = [
            ("poe/Claude-Sonnet-4", "Claude-Sonnet-4"),
            ("poe/Claude-Opus-4.1", "Claude-Opus-4.1"),
            ("poe/Gemini-2.0-Flash", "Gemini-2.0-Flash"),
            ("poe/Grok-4", "Grok-4"),
            ("poe/GPT-4o", "GPT-4o"),
            ("poe/o3-mini", "o3-mini"),
            ("poe/DeepSeek-R1", "DeepSeek-R1"),
        ]
        
        for input_model, expected_model in test_cases:
            kwargs = {"model": input_model}
            poe_config.configure(input_model, kwargs)
            
            if kwargs["model"] != expected_model:
                print(f"❌ Model name transformation failed: {input_model} -> {kwargs['model']} (expected {expected_model})")
                return False
        
        print(f"✅ All {len(test_cases)} model name variations work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Error testing model variations: {e}")
        return False


def main():
    """Run all POE integration tests."""
    print("🚀 POE API Integration Tests")
    print("=" * 50)
    
    tests = [
        test_poe_provider_configuration,
        test_poe_providers_registry,
        test_model_name_variations,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All POE integration tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())