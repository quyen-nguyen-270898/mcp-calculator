"""MCP Calculator Server using official MCP SDK"""
import math
import random
from typing import Any

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server


async def main():
    """Main server function"""
    app = Server("calculator")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        """List available tools"""
        return [
            types.Tool(
                name="calculator",
                description="For mathematical calculation, always use this tool to calculate the result of a python expression. You can use 'math' or 'random' directly, without 'import'.",
                inputSchema={
                    "type": "object",
                    "required": ["python_expression"],
                    "properties": {
                        "python_expression": {
                            "type": "string",
                            "description": "A valid Python expression to evaluate"
                        }
                    },
                },
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
        """Handle tool calls"""
        if name != "calculator":
            raise ValueError(f"Unknown tool: {name}")
        
        if "python_expression" not in arguments:
            raise ValueError("Missing required argument 'python_expression'")
        
        python_expression = arguments["python_expression"]
        
        try:
            # Safely evaluate the expression
            result = eval(python_expression, {"__builtins__": {}}, {"math": math, "random": random})
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Result: {result}"
                )
            ]
        except Exception as e:
            raise ValueError(f"Calculation error: {str(e)}")

    # Run stdio server
    from mcp.server.stdio import stdio_server

    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


def run():
    """Entry point for the server"""
    anyio.run(main)
