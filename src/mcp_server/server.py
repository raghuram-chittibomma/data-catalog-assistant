"""
MCP Server - Model Context Protocol server for exposing tools.
"""

import logging
from threading import Thread
from typing import Dict, List, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP (Model Context Protocol) server.
    Exposes RAG tools that can be used by Claude and other agents.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize MCP server.

        Args:
            config: Server configuration
        """
        self.config = config or {}
        self.tools = {}
        self.resources = {}
        self.app = FastAPI(title="Data Catalog Assistant MCP Server")
        self._server = None
        self._thread = None

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._configure_routes()

        logger.info("Initialized MCP Server")

    def _configure_routes(self):
        self.app.add_api_route("/", self._root, methods=["GET"])
        self.app.add_api_route("/tools", self._list_tools, methods=["GET"])
        self.app.add_api_route("/tools/{tool_name}", self._execute_tool, methods=["POST"])
        self.app.add_api_route("/resources", self._list_resources, methods=["GET"])
        self.app.add_api_route("/resources/{resource_name}", self._execute_resource, methods=["POST"])

    async def _root(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "tools": self.get_tool_list(),
            "resources": self.get_resource_list()
        }

    async def _list_tools(self) -> Dict[str, Any]:
        return {"tools": self.get_tool_list()}

    async def _list_resources(self) -> Dict[str, Any]:
        return {"resources": self.get_resource_list()}

    async def _execute_tool(self, tool_name: str, payload: Dict[str, Any] = Body(default={})):
        tool = self.tools.get(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        handler = tool["handler"]
        try:
            result = handler(**payload) if isinstance(payload, dict) else handler(payload)
            return result
        except TypeError as te:
            raise HTTPException(status_code=400, detail=str(te))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _execute_resource(self, resource_name: str, payload: Dict[str, Any] = Body(default={})):
        resource = self.resources.get(resource_name)
        if not resource:
            raise HTTPException(status_code=404, detail=f"Resource '{resource_name}' not found")

        handler = resource["handler"]
        try:
            result = handler(**payload) if isinstance(payload, dict) else handler(payload)
            return result
        except TypeError as te:
            raise HTTPException(status_code=400, detail=str(te))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def register_tool(self, name: str, handler, description: str, parameters: Dict):
        """
        Register a tool with the server.

        Args:
            name: Tool name
            handler: Handler function
            description: Tool description
            parameters: Parameter schema
        """
        logger.debug(f"Registering tool: {name}")
        self.tools[name] = {
            "handler": handler,
            "description": description,
            "parameters": parameters
        }

    def register_resource(self, name: str, handler, description: str):
        """
        Register a resource with the server.

        Args:
            name: Resource name
            handler: Handler function
            description: Resource description
        """
        logger.debug(f"Registering resource: {name}")
        self.resources[name] = {
            "handler": handler,
            "description": description
        }

    def start(self, host: str = "localhost", port: int = 3000):
        """
        Start MCP server.

        Args:
            host: Server host
            port: Server port
        """
        logger.info(f"Starting MCP server on {host}:{port}")
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        self._server = uvicorn.Server(config=config)
        self._thread = Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop MCP server."""
        logger.info("Stopping MCP server")
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return [
            {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
            for name, tool in self.tools.items()
        ]

    def get_resource_list(self) -> List[Dict[str, Any]]:
        """Get list of available resources."""
        return [
            {
                "name": name,
                "description": resource["description"]
            }
            for name, resource in self.resources.items()
        ]
