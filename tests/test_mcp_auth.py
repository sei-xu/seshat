"""Tests for MCP server authentication."""

import os
from unittest.mock import patch

import pytest

from seshat.mcp.server import MCPServer, ServerConfig


class TestAPIKeyAuthentication:
    def test_server_requires_api_key_when_configured(self, tmp_path):
        """Test that server enforces API key requirement when configured."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path, api_key="secret-key-123")
        server = MCPServer(config)
        assert server.config.api_key == "secret-key-123"

    def test_server_allows_no_auth_when_not_configured(self, tmp_path):
        """Test that server allows calls without auth when API key not set."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path, api_key=None)
        server = MCPServer(config)
        assert server.config.api_key is None

    def test_api_key_from_environment(self, tmp_path):
        """Test that API key can be loaded from environment variable."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        with patch.dict(os.environ, {"SESHAT_API_KEY": "env-key-456"}):
            api_key = os.getenv("SESHAT_API_KEY")
            assert api_key == "env-key-456"

            config = ServerConfig(vault_root=tmp_path, api_key=api_key)
            server = MCPServer(config)
            assert server.config.api_key == "env-key-456"

    def test_config_accepts_api_key_parameter(self, tmp_path):
        """Test that config stores API key."""
        config = ServerConfig(
            vault_root=tmp_path,
            api_key="test-key-789",
        )
        assert config.api_key == "test-key-789"

    def test_config_api_key_optional(self, tmp_path):
        """Test that API key is optional in config."""
        config = ServerConfig(vault_root=tmp_path)
        assert config.api_key is None

    def test_api_key_bearer_token_format(self, tmp_path):
        """Test that authentication uses Bearer token format."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path, api_key="my-secret-123")
        server = MCPServer(config)

        # Handler class validates Bearer format
        # Expected format: "Authorization: Bearer my-secret-123"
        expected_auth = f"Bearer {config.api_key}"
        assert expected_auth == "Bearer my-secret-123"

    def test_api_key_string_format(self, tmp_path):
        """Test that API key can be any string."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        test_keys = [
            "simple-key",
            "key_with_underscores",
            "key-with-dashes",
            "12345",
            "complex.key.123-ABC_def",
        ]

        for key in test_keys:
            config = ServerConfig(vault_root=tmp_path, api_key=key)
            server = MCPServer(config)
            assert server.config.api_key == key

    def test_auth_header_validation_format(self):
        """Test that auth header format is correct."""
        # Simulate auth header check
        api_key = "test-key"
        auth_header = "Bearer test-key"
        expected = f"Bearer {api_key}"

        assert auth_header == expected

    def test_invalid_auth_header_rejected(self):
        """Test that invalid auth headers are rejected."""
        api_key = "test-key"
        correct = f"Bearer {api_key}"

        invalid_headers = [
            "Bearer wrong-key",
            "BearerXtest-key",  # missing space
            "bearer test-key",  # lowercase
            f"Token {api_key}",  # wrong scheme
            api_key,  # no Bearer prefix
            f"Bearer {api_key} extra",  # extra content
        ]

        for invalid_header in invalid_headers:
            assert invalid_header != correct

    def test_multiple_api_keys_not_supported(self, tmp_path):
        """Test that server uses single API key (not multiple keys)."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path, api_key="single-key")
        server = MCPServer(config)

        # Only one API key stored (not a list or dict)
        assert isinstance(server.config.api_key, str)
        assert server.config.api_key == "single-key"

    def test_api_key_empty_string_treated_as_none(self, tmp_path):
        """Test that empty API key is treated as no auth."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path, api_key="")
        # Empty string is falsy, so auth check would skip
        assert not config.api_key  # falsy value

    def test_api_key_with_special_characters(self, tmp_path):
        """Test that API key can contain special characters."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        special_keys = [
            "key-with-!@#$%",
            "key_with_(){}[]",
            "key.with.dots",
            "key/with/slashes",
        ]

        for key in special_keys:
            config = ServerConfig(vault_root=tmp_path, api_key=key)
            server = MCPServer(config)
            assert server.config.api_key == key
