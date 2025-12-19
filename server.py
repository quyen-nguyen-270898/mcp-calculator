#!/usr/bin/env python3
"""
Wrapper server for Render deployment
Runs MCP pipe in background while providing HTTP health check endpoint
and exposes music streaming routes (download-to-serve) on the same port.
"""
import asyncio
import subprocess
import os
import sys
from aiohttp import web
import logging

from stream_proxy import init_app as register_stream_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RenderServer')

# Global process handle
mcp_process = None

async def health_check(request):
    """Health check endpoint for Render"""
    client_ip = request.remote
    logger.info(f"Health check request from {client_ip}")
    if mcp_process and mcp_process.poll() is None:
        return web.Response(text="OK", status=200)
    logger.warning(f"Health check failed - MCP process not running")
    return web.Response(text="MCP process not running", status=503)

async def status(request):
    """Status endpoint"""
    client_ip = request.remote
    user_agent = request.headers.get('User-Agent', 'Unknown')
    logger.info(f"Status request from {client_ip} - User-Agent: {user_agent}")
    
    status_info = {
        "service": "MCP Calculator Bridge",
        "mcp_running": mcp_process is not None and mcp_process.poll() is None,
        "endpoint": os.environ.get('MCP_ENDPOINT', 'not set')[:50] + "...",
        "uptime": "running" if mcp_process and mcp_process.poll() is None else "stopped"
    }
    return web.json_response(status_info)

async def read_mcp_output(process):
    """Read and log MCP process output in real-time"""
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, process.stdout.readline)
            if not line:
                break
            line = line.strip()
            if line:
                # Forward MCP logs with prefix
                logger.info(f"[MCP] {line}")
        except Exception as e:
            logger.error(f"Error reading MCP output: {e}")
            break

async def start_mcp_pipe():
    """Start MCP pipe as subprocess"""
    global mcp_process
    
    endpoint = os.environ.get('MCP_ENDPOINT')
    if not endpoint:
        logger.warning("MCP_ENDPOINT not set - skipping MCP pipe startup")
        return
    
    logger.info(f"Starting MCP pipe connecting to: {endpoint[:50]}...")
    mcp_process = subprocess.Popen(
        [sys.executable, 'mcp_pipe.py'],
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1  # Line buffered
    )
    logger.info(f"MCP process started with PID: {mcp_process.pid}")
    
    # Start reading output in background
    output_task = asyncio.create_task(read_mcp_output(mcp_process))
    
    # Monitor process
    restart_count = 0
    while True:
        if mcp_process.poll() is not None:
            restart_count += 1
            logger.error(f"MCP process died (restart #{restart_count}), restarting in 5s...")
            output_task.cancel()
            await asyncio.sleep(5)
            
            mcp_process = subprocess.Popen(
                [sys.executable, 'mcp_pipe.py'],
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            logger.info(f"MCP process restarted with PID: {mcp_process.pid}")
            output_task = asyncio.create_task(read_mcp_output(mcp_process))
        await asyncio.sleep(10)

async def start_background_tasks(app):
    """Start background tasks on app startup"""
    # Only start MCP pipe if endpoint is configured
    endpoint = os.environ.get('MCP_ENDPOINT')
    if endpoint:
        # Don't await - let it run in background
        app['mcp_task'] = asyncio.create_task(start_mcp_pipe())
        logger.info("MCP pipe task scheduled (running in background)")
    else:
        logger.warning("MCP_ENDPOINT not set - MCP pipe will not start")
        app['mcp_task'] = None
    
    # Return immediately so server can start accepting connections
    logger.info("Startup tasks completed - server ready to accept connections")

async def cleanup_background_tasks(app):
    """Cleanup on shutdown"""
    global mcp_process
    logger.info("Shutting down server...")
    
    # Terminate MCP process
    if mcp_process:
        logger.info(f"Terminating MCP process (PID: {mcp_process.pid})")
        mcp_process.terminate()
        mcp_process.wait()
    
    if app.get('mcp_task'):
        app['mcp_task'].cancel()
        try:
            await app['mcp_task']
        except asyncio.CancelledError:
            pass
    logger.info("Cleanup complete")

@web.middleware
async def logging_middleware(request, handler):
    """Log all incoming requests"""
    client_ip = request.remote
    method = request.method
    path = request.path
    logger.info(f">>> {method} {path} from {client_ip}")
    
    try:
        response = await handler(request)
        logger.info(f"<<< {method} {path} - Status: {response.status}")
        return response
    except Exception as e:
        logger.error(f"<<< {method} {path} - Error: {e}")
        raise

def main():
    """Main entry point"""
    try:
        port_env = os.environ.get('PORT')
        if not port_env:
            logger.warning("PORT env not set; defaulting to 10000 (suitable for local dev only)")
            # For Render: try common Render port if PORT not set
            port = 10000
        else:
            port = int(port_env)
        
        logger.info(f"Attempting to bind to port: {port}")
        logger.info(f"Environment PORT variable: {port_env or 'NOT SET'}")
        
        app = web.Application(middlewares=[logging_middleware])
        app.router.add_get('/health', health_check)
        app.router.add_get('/status', status)
        app.router.add_get('/', status)

        # Expose music streaming routes on the same public port
        logger.info("Registering stream proxy routes...")
        register_stream_routes(app)
        logger.info("Stream proxy routes registered successfully")
        
        app.on_startup.append(start_background_tasks)
        app.on_cleanup.append(cleanup_background_tasks)
        
        logger.info(f"=" * 60)
        logger.info(f"MCP Calculator Bridge Server Starting")
        logger.info(f"Port: {port}")
        logger.info("Endpoints: /health, /status, /audio/{id}, /url/{id}, /stream/{id}")
        logger.info(f"=" * 60)
        
        logger.info(f"Starting aiohttp web server on 0.0.0.0:{port}...")
        
        # Use print to ensure output even if logging fails
        print(f"DEBUG: About to call web.run_app on port {port}", flush=True)
        
        try:
            web.run_app(app, host='0.0.0.0', port=port, access_log=logger, print=logger.info)
        except Exception as run_error:
            logger.error(f"web.run_app failed: {run_error}", exc_info=True)
            print(f"FATAL: web.run_app crashed: {run_error}", flush=True)
            raise
            
    except Exception as e:
        logger.error(f"FATAL ERROR during startup: {e}", exc_info=True)
        print(f"FATAL STARTUP ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    main()
