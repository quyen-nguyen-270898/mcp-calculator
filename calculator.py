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
    
    logger.info(f"⚡ Tool Call: {tool_name} with args: {arguments}")
    
    if tool_name == "calculator":
        try:
            python_expression = arguments.get("python_expression", "")
            logger.info(f"📊 Computing: {python_expression}")
            
            result = eval(python_expression, {"__builtins__": {}}, {"math": math, "random": random})
            
            logger.info(f"✅ Result: {python_expression} = {result}")
            
            response = {
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
            logger.info(f"📤 Sending response: {json.dumps(response)[:200]}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Calculation error for '{python_expression}': {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": f"Calculation error: {str(e)}"
                }
            }
    
    logger.warning(f"⚠️ Unknown tool requested: {tool_name}")
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
    logger.info("=" * 60)
    logger.info("🧮 Calculator MCP Server starting...")
    logger.info("=" * 60)
    
    request_count = 0
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                logger.info("📪 EOF received, shutting down...")
                break
            
            line = line.strip()
            if not line:
                continue
            
            request_count += 1
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            logger.info(f"📥 Request #{request_count}: {method} (id: {request_id})")
            if params and method not in ["initialize", "notifications/initialized"]:
                logger.info(f"   Params: {json.dumps(params)[:200]}")
            
            response = None
            if method == "initialize":
                response = handle_initialize(request_id, params)
                logger.info("✅ Initialized successfully")
            elif method == "tools/list":
                response = handle_list_tools(request_id, params)
                logger.info("✅ Sent tools list")
            elif method == "tools/call":
                response = handle_call_tool(request_id, params)
            elif method == "notifications/initialized":
                logger.info("✅ Client initialized notification received")
                continue
            elif method == "ping":
                logger.info("🏓 Ping received")
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {}
                }
            else:
                logger.warning(f"⚠️ Unknown method: {method}")
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
                logger.info(f"✅ Response sent for request #{request_count}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            logger.error(f"   Raw line: {line[:200]}")
        except Exception as e:
            logger.error(f"❌ Error processing request: {e}", exc_info=True)
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
