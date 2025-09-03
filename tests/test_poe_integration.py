"""Test POE API integration."""

import os
from unittest.mock import patch

import pytest

from quantalogic_react.quantalogic.quantlitellm import PROVIDERS, ModelProviderConfig


class TestPOEIntegration:
    """Test POE provider integration."""

    def test_poe_provider_configuration(self):
        """Test that POE provider is properly configured."""
        assert "poe" in PROVIDERS
        poe_config = PROVIDERS["poe"]
        
        assert isinstance(poe_config, ModelProviderConfig)
        assert poe_config.prefix == "poe/"
        assert poe_config.provider == "openai"
        assert poe_config.base_url == "https://api.poe.com/v1"
        assert poe_config.env_var == "POE_API_KEY"

    def test_poe_provider_configure_method(self):
        """Test POE provider configuration method."""
        poe_config = PROVIDERS["poe"]
        
        # Test with API key present
        with patch.dict(os.environ, {"POE_API_KEY": "test-api-key"}):
            kwargs = {"model": "poe/Claude-Sonnet-4"}
            
            poe_config.configure("poe/Claude-Sonnet-4", kwargs)
            
            assert kwargs["model"] == "Claude-Sonnet-4"  # prefix removed
            assert kwargs["custom_llm_provider"] == "openai"
            assert kwargs["base_url"] == "https://api.poe.com/v1"
            assert kwargs["api_key"] == "test-api-key"

    def test_poe_provider_missing_api_key(self):
        """Test POE provider fails gracefully when API key is missing."""
        poe_config = PROVIDERS["poe"]
        
        # Test without API key
        with patch.dict(os.environ, {}, clear=True):
            kwargs = {"model": "poe/Claude-Sonnet-4"}
            
            with pytest.raises(ValueError, match="POE_API_KEY is not set"):
                poe_config.configure("poe/Claude-Sonnet-4", kwargs)

    def test_poe_model_name_handling(self):
        """Test different POE model name formats."""
        poe_config = PROVIDERS["poe"]
        
        test_cases = [
            ("poe/Claude-Sonnet-4", "Claude-Sonnet-4"),
            ("poe/Gemini-2.0-Flash", "Gemini-2.0-Flash"),
            ("poe/GPT-4o", "GPT-4o"),
            ("poe/o3-mini", "o3-mini"),
        ]
        
        with patch.dict(os.environ, {"POE_API_KEY": "test-key"}):
            for input_model, expected_model in test_cases:
                kwargs = {"model": input_model}
                poe_config.configure(input_model, kwargs)
                assert kwargs["model"] == expected_model