#!/usr/bin/env python3
"""
Wrapper server for Render deployment
Runs MCP pipe in background while providing HTTP health check endpoint
"""
import asyncio
import subprocess
import os
import sys
from aiohttp import web
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RenderServer')

# Global process handle
mcp_process = None

async def health_check(request):
    """Health check endpoint for Render"""
    if mcp_process and mcp_process.poll() is None:
        return web.Response(text="OK", status=200)
    return web.Response(text="MCP process not running", status=503)

async def status(request):
    """Status endpoint"""
    status_info = {
        "service": "MCP Calculator Bridge",
        "mcp_running": mcp_process is not None and mcp_process.poll() is None,
        "endpoint": os.environ.get('MCP_ENDPOINT', 'not set')[:50] + "..."
    }
    return web.json_response(status_info)

async def start_mcp_pipe():
    """Start MCP pipe as subprocess"""
    global mcp_process
    
    endpoint = os.environ.get('MCP_ENDPOINT')
    if not endpoint:
        logger.error("MCP_ENDPOINT not set!")
        return
    
    logger.info("Starting MCP pipe...")
    mcp_process = subprocess.Popen(
        [sys.executable, 'mcp_pipe.py'],
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Monitor output
    while True:
        if mcp_process.poll() is not None:
            logger.error("MCP process died, restarting...")
            await asyncio.sleep(5)
            mcp_process = subprocess.Popen(
                [sys.executable, 'mcp_pipe.py'],
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
        await asyncio.sleep(10)

async def start_background_tasks(app):
    """Start background tasks on app startup"""
    app['mcp_task'] = asyncio.create_task(start_mcp_pipe())

async def cleanup_background_tasks(app):
    """Cleanup on shutdown"""
    global mcp_process
    if mcp_process:
        mcp_process.terminate()
        mcp_process.wait()
    app['mcp_task'].cancel()
    await app['mcp_task']

def main():
    """Main entry point"""
    port = int(os.environ.get('PORT', 10000))
    
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', status)
    app.router.add_get('/', status)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    logger.info(f"Starting HTTP server on port {port}...")
    web.run_app(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
