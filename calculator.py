#!/usr/bin/env python3
"""Simple MCP Calculator Server using stdio transport"""
import sys
import json
import logging
import math
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Calculator')

def handle_initialize(request_id, params):
    """Handle initialize request"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "calculator",
                "version": "1.0.0"
            }
        }
    }

def handle_list_tools(request_id, params):
    """Handle tools/list request"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": [
                {
                    "name": "calculator",
                    "description": "For mathematical calculation, always use this tool to calculate the result of a python expression. You can use 'math' or 'random' directly, without 'import'.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "python_expression": {
                                "type": "string",
                                "description": "A valid Python expression to evaluate"
                            }
                        },
                        "required": ["python_expression"]
                    }
                }
            ]
        }
    }

def handle_call_tool(request_id, params):
    """Handle tools/call request"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if tool_name == "calculator":
        try:
            python_expression = arguments.get("python_expression", "")
            result = eval(python_expression, {"__builtins__": {}}, {"math": math, "random": random})
            logger.info(f"Calculating: {python_expression} = {result}")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"success": True, "result": result})
                        }
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": f"Calculation error: {str(e)}"
                }
            }
    
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Unknown tool: {tool_name}"
        }
    }

def main():
    """Main server loop"""
    logger.info("Calculator MCP Server starting...")
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            logger.info(f"Received request: {method}")
            
            response = None
            if method == "initialize":
                response = handle_initialize(request_id, params)
            elif method == "tools/list":
                response = handle_list_tools(request_id, params)
            elif method == "tools/call":
                response = handle_call_tool(request_id, params)
            elif method == "notifications/initialized":
                # No response needed for notification
                continue
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            if response:
                print(json.dumps(response), flush=True)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            if 'request_id' in locals():
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    main()
