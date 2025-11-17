#!/usr/bin/env python3
"""
MCP Music Streamer Server
Provides music streaming capabilities for ESP32 and other clients
Supports YouTube, ZingMP3, and other sources
"""
import sys
import json
import logging
import os

from youtube_proxy import (
    extract_video_id,
    fetch_stream_via_invidious,
    get_audio_stream,
    get_video_info,
    search_tracks,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MusicStreamer')

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
                "name": "music-streamer",
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
                    "name": "search_music",
                    "description": "Search for music on YouTube. Returns video ID and title.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (song name, artist, etc.)"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 5)",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_stream_url",
                    "description": "Get direct audio stream URL for ESP32. Supports YouTube URL or video ID. Returns HTTP stream URL suitable for ESP32.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "YouTube URL or video ID (e.g., 'dQw4w9WgXcQ' or 'https://youtube.com/watch?v=...')"
                            },
                            "format": {
                                "type": "string",
                                "description": "Audio format preference: 'best' (highest quality) or 'esp32' (optimized for ESP32, ~128kbps)",
                                "enum": ["best", "esp32"],
                                "default": "esp32"
                            }
                        },
                        "required": ["url"]
                    }
                },
                {
                    "name": "get_music_info",
                    "description": "Get detailed information about a YouTube video (title, duration, thumbnail, etc.)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "YouTube URL or video ID"
                            }
                        },
                        "required": ["url"]
                    }
                },
                {
                    "name": "get_invidious_stream",
                    "description": "Get audio stream URL from Invidious (YouTube proxy). More reliable for ESP32 than direct YouTube.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "video_id": {
                                "type": "string",
                                "description": "YouTube video ID"
                            },
                            "quality": {
                                "type": "string",
                                "description": "Audio quality preference: 'low' (best for ESP32), 'medium', or 'high'",
                                "enum": ["low", "medium", "high"],
                                "default": "low"
                            }
                        },
                        "required": ["video_id"]
                    }
                },
                {
                    "name": "get_esp32_stream",
                    "description": "Get ready-to-use stream URL for ESP32. Returns direct stream URL that ESP32 can play immediately. Optimized for ESP32 (128kbps audio).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "video_id": {
                                "type": "string",
                                "description": "YouTube video ID (from search_music results)"
                            }
                        },
                        "required": ["video_id"]
                    }
                }
            ]
        }
    }

def search_youtube(query: str, max_results: int = 5) -> list:
    """Use shared helper to search music with API preference."""
    results = search_tracks(query, max_results)
    if results:
        logger.info("✅ Search succeeded via %s", results[0].get("source"))
        return results
    logger.error("❌ No search results for query: %s", query)
    return []

def handle_call_tool(request_id, params):
    """Handle tools/call request"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    logger.info(f"⚡ Tool Call: {tool_name} with args: {arguments}")
    
    try:
        if tool_name == "search_music":
            query = arguments.get("query", "")
            max_results = arguments.get("max_results", 5)
            
            logger.info(f"🔍 Searching: {query} (max {max_results} results)")
            results = search_youtube(query, max_results)
            
            logger.info(f"✅ Found {len(results)} results")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "success": True,
                                "results": results,
                                "count": len(results)
                            }, ensure_ascii=False)
                        }
                    ]
                }
            }
        
        elif tool_name == "get_stream_url":
            url = arguments.get("url", "")
            format_pref = arguments.get("format", "esp32")
            
            video_id = extract_video_id(url)
            logger.info(f"🎵 Getting stream for video: {video_id} (format: {format_pref})")
            
            stream_info = get_audio_stream(video_id, format_pref)
            
            if stream_info:
                logger.info(
                    "✅ Stream info obtained via %s", stream_info.get("source", "unknown")
                )
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({
                                    "success": True,
                                    "stream": stream_info
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                }
            else:
                logger.error(f"❌ Failed to get stream for {video_id}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": "Failed to get stream URL"
                    }
                }
        
        elif tool_name == "get_invidious_stream":
            video_id = arguments.get("video_id", "")
            quality = arguments.get("quality", "low")
            
            logger.info(f"🔄 Getting Invidious stream for: {video_id} (quality: {quality})")
            
            stream_info = fetch_stream_via_invidious(video_id, quality)
            if stream_info:
                logger.info(
                    "✅ Invidious stream ready (%s)", stream_info.get("instance", "unknown")
                )
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({
                                    "success": True,
                                    "stream_url": stream_info.get("stream_url"),
                                    "title": stream_info.get("title"),
                                    "duration": stream_info.get("duration"),
                                    "bitrate": stream_info.get("bitrate"),
                                    "format": stream_info.get("format"),
                                    "instance": stream_info.get("instance"),
                                    "video_id": video_id
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                }
            else:
                logger.error("❌ All Invidious instances failed for %s", video_id)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": "Invidious instances unavailable"
                    }
                }
        
        elif tool_name == "get_esp32_stream":
            video_id = arguments.get("video_id", "")
            
            logger.info(f"🎵 Getting ESP32-ready info for: {video_id}")
            
            try:
                info = get_video_info(video_id) or {}
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                logger.info(f"📝 Video: {title}")
                
                # Provide direct proxy stream URL plus Render proxy endpoint
                render_app_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://mcp-calculator-3q3k.onrender.com')
                proxy_url = f"{render_app_url}/url/{video_id}"
                stream_info = get_audio_stream(video_id, 'esp32')
                
                logger.info(f"✅ Returning proxy URL for ESP32")
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({
                                    "success": True,
                                    "video_id": video_id,
                                    "title": title,
                                    "duration": duration,
                                    "proxy_url": proxy_url,
                                    "direct_stream": stream_info,
                                    "youtube_url": f"https://youtube.com/watch?v={video_id}",
                                    "instructions": {
                                        "step_1": f"ESP32 GET request to: {proxy_url}",
                                        "step_2": "Parse JSON response to get 'stream_url'",
                                        "step_3": "Use: audio.connecttohost(stream_url)",
                                        "note": "Stream URL expires in ~6 hours, re-fetch if needed"
                                    },
                                    "esp32_code_example": f"HTTPClient http; http.begin(\"{proxy_url}\"); String json = http.getString(); // parse to get stream_url"
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                }
                    
            except Exception as e:
                logger.error(f"❌ Error getting ESP32 stream info: {e}", exc_info=True)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Failed to get info: {str(e)}"
                    }
                }
        
        elif tool_name == "get_music_info":
            url = arguments.get("url", "")
            video_id = extract_video_id(url)
            
            logger.info(f"ℹ️ Getting info for: {video_id}")
            
            info_data = get_video_info(video_id)
            if not info_data:
                raise RuntimeError("Failed to fetch video info")
            info = {
                "id": info_data.get("id"),
                "title": info_data.get("title"),
                "duration": info_data.get("duration"),
                "uploader": info_data.get("uploader"),
                "thumbnail": info_data.get("thumbnail"),
                "description": (info_data.get("description") or "")[:500]
            }
            
            logger.info(f"✅ Info retrieved: {info.get('title')}")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "success": True,
                                "info": info
                            }, ensure_ascii=False)
                        }
                    ]
                }
            }
        
        else:
            logger.warning(f"⚠️ Unknown tool: {tool_name}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
    
    except Exception as e:
        logger.error(f"❌ Tool execution error: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": f"Tool error: {str(e)}"
            }
        }

def main():
    """Main server loop"""
    logger.info("=" * 60)
    logger.info("🎵 Music Streamer MCP Server starting...")
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
            
            response = None
            if method == "initialize":
                response = handle_initialize(request_id, params)
                logger.info("✅ Initialized successfully")
            elif method == "tools/list":
                response = handle_list_tools(request_id, params)
                logger.info("✅ Sent tools list (3 tools)")
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
