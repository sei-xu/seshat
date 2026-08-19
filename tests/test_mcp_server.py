"""Tests for MCP server."""

from pathlib import Path

import pytest

from seshat.core import VaultClient
from seshat.mcp.server import MCPServer, ServerConfig
from seshat.mcp.schemas import TOOL_SCHEMAS, get_tool_schema, get_tool_schemas


class TestMCPSchemas:
    def test_all_nine_tools_defined(self):
        """Test that all 9 tools have schemas defined."""
        expected_tools = {
            "list_projects",
            "get_project",
            "create_project",
            "append_history",
            "create_fragment",
            "list_references",
            "create_reference",
            "update_project_status",
            "search_vault",
        }
        assert set(TOOL_SCHEMAS.keys()) == expected_tools

    def test_tool_schemas_have_required_fields(self):
        """Test that each tool schema is properly formatted."""
        for tool_name, schema in TOOL_SCHEMAS.items():
            assert "name" in schema
            assert schema["name"] == tool_name
            assert "description" in schema
            assert "input_schema" in schema
            assert "type" in schema["input_schema"]
            assert "properties" in schema["input_schema"]

    def test_get_tool_schemas_returns_list(self):
        """Test that get_tool_schemas returns proper format."""
        schemas = get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 9
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema

    def test_get_tool_schema_by_name(self):
        """Test getting individual tool schema."""
        schema = get_tool_schema("list_projects")
        assert schema is not None
        assert schema["name"] == "list_projects"

    def test_get_missing_schema_returns_none(self):
        """Test that missing tool returns None."""
        schema = get_tool_schema("nonexistent")
        assert schema is None


class TestMCPServerConfig:
    def test_server_config_initialization(self, tmp_path):
        """Test that server config initializes properly."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(
            vault_root=tmp_path,
            api_key="test-key",
            host="localhost",
            port=8080,
        )
        assert config.vault_root == tmp_path
        assert config.api_key == "test-key"
        assert config.host == "localhost"
        assert config.port == 8080

    def test_server_initializes_without_error(self, tmp_path):
        """Test that MCPServer initializes with valid vault."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path)
        server = MCPServer(config)
        assert server.vault is not None
        assert server.git is not None
        assert len(server.tools) == 9

    def test_server_tools_are_callable(self, tmp_path):
        """Test that all tools in server are callable."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path)
        server = MCPServer(config)
        for tool_name, tool_fn in server.tools.items():
            assert callable(tool_fn)
            assert tool_name in TOOL_SCHEMAS

    def test_server_initializes_git_with_remote(self, tmp_path):
        """Test that server initializes git when remote is configured."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(
            vault_root=tmp_path,
            git_remote_url="https://example.com/vault.git",
        )
        server = MCPServer(config)
        assert server.git.is_initialized()

    def test_server_without_git_remote(self, tmp_path):
        """Test that server doesn't auto-init git without remote."""
        for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
            (tmp_path / folder).mkdir()

        config = ServerConfig(vault_root=tmp_path)  # no git_remote_url
        server = MCPServer(config)
        assert not server.git.is_initialized()
