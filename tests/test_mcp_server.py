"""Tests for MCP Server."""

import unittest
from unittest.mock import Mock

from src.mcp_server.server import MCPServer


class TestMCPServer(unittest.TestCase):
    """Test cases for MCP Server."""

    def setUp(self):
        """Set up test fixtures."""
        self.server = MCPServer()

    def test_mcp_server_initialization(self):
        """Test MCP Server initialization."""
        self.assertIsNotNone(self.server)

    def test_register_tool(self):
        """Test registering a tool."""
        mock_handler = Mock()
        self.server.register_tool(
            "test_tool", mock_handler, "Test tool", {"param1": {"type": "string"}}
        )
        self.assertIn("test_tool", self.server.tools)

    def test_get_tool_list(self):
        """Test getting tool list."""
        tools = self.server.get_tool_list()
        self.assertIsInstance(tools, list)

    def test_register_resource(self):
        """Test registering a resource."""

        def mock_resource():
            return {"status": "ok"}

        self.server.register_resource("resource_test", mock_resource, "Test resource")
        self.assertIn("resource_test", self.server.resources)
        resources = self.server.get_resource_list()
        self.assertIsInstance(resources, list)
        self.assertEqual(resources[0]["name"], "resource_test")


if __name__ == "__main__":
    unittest.main()
