#!/usr/bin/env python3
"""
Cloud-based Music Streaming Proxy for ESP32
Runs on Render alongside MCP servers
Provides HTTP endpoints for ESP32 to fetch audio streams
"""
import asyncio
import logging
import os
import time
from aiohttp import web

from youtube_proxy import get_audio_stream

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('StreamProxy')

# Cache stream URLs (expire after 4 hours)
stream_cache = {}
CACHE_DURATION = 4 * 3600  # 4 hours

async def get_stream_url_cached(video_id: str) -> dict:
    """Get stream URL with caching"""
    now = time.time()
    
    # Check cache
    if video_id in stream_cache:
        cached = stream_cache[video_id]
        if now - cached['timestamp'] < CACHE_DURATION:
            logger.info(f"Cache hit for {video_id}")
            return cached
    
    # Try to get fresh stream URL
    logger.info(f"Fetching fresh stream for {video_id}")
    
    try:
        loop = asyncio.get_running_loop()
        stream_info = await loop.run_in_executor(None, get_audio_stream, video_id, 'esp32')
        if stream_info and stream_info.get('stream_url'):
            result = {
                **stream_info,
                'video_id': video_id,
                'timestamp': now,
                'expires_at': now + CACHE_DURATION
            }
            stream_cache[video_id] = result
            logger.info(
                f"✅ Got stream via {stream_info.get('source', 'unknown')} for {stream_info.get('title', 'Unknown')}"
            )
            return result
        logger.error(f"No proxy stream available for {video_id}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting stream: {e}")
    
    return None

async def stream_endpoint(request):
    """Stream endpoint - returns direct stream URL or redirects"""
    video_id = request.match_info['video_id']
    
    logger.info(f"📻 Stream request for: {video_id}")
    
    result = await get_stream_url_cached(video_id)
    
    if result:
        # Redirect to actual stream URL
        logger.info(f"Redirecting to stream...")
        return web.HTTPFound(result['stream_url'])
    else:
        return web.json_response({
            'error': 'Failed to get stream URL',
            'video_id': video_id,
            'suggestion': 'Try again in a few moments or try different video'
        }, status=500)

async def url_endpoint(request):
    """Return stream URL as JSON (for ESP32 to handle redirect)"""
    video_id = request.match_info['video_id']
    
    logger.info(f"🔗 URL request for: {video_id}")
    
    result = await get_stream_url_cached(video_id)
    
    if result:
        return web.json_response({
            'success': True,
            'video_id': video_id,
            'stream_url': result['stream_url'],
            'title': result['title'],
            'expires_in_seconds': int(result['expires_at'] - time.time()),
            'note': 'URL will expire. Request new one when playback fails.'
        })
    else:
        return web.json_response({
            'success': False,
            'video_id': video_id,
            'error': 'Could not fetch stream URL'
        }, status=500)

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({
        'status': 'ok',
        'service': 'ESP32 Music Stream Proxy',
        'cached_streams': len(stream_cache),
        'endpoints': {
            '/stream/{video_id}': 'Redirect to stream (ESP32 with redirect support)',
            '/url/{video_id}': 'Get stream URL as JSON (parse and use manually)'
        }
    })

async def clear_expired_cache():
    """Periodically clear expired cache entries"""
    while True:
        await asyncio.sleep(3600)  # Every hour
        now = time.time()
        expired = [vid for vid, data in stream_cache.items() 
                  if now - data['timestamp'] > CACHE_DURATION]
        for vid in expired:
            del stream_cache[vid]
        if expired:
            logger.info(f"Cleared {len(expired)} expired cache entries")

def create_app():
    """Create the web application"""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/stream/{video_id}', stream_endpoint)
    app.router.add_get('/url/{video_id}', url_endpoint)
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    # Start cache cleanup task
    app.on_startup.append(lambda app: asyncio.create_task(clear_expired_cache()))
    
    return app

if __name__ == '__main__':
    port = int(os.environ.get('STREAM_PORT', 5001))
    
    logger.info("=" * 60)
    logger.info("🎵 ESP32 Music Stream Proxy")
    logger.info(f"Port: {port}")
    logger.info("=" * 60)
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=port)
