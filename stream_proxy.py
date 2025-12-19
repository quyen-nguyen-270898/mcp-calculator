#!/usr/bin/env python3
"""
Cloud-based Music Streaming Proxy for ESP32
Downloads YouTube audio as MP3 then serves locally to avoid
bot/verifications when Render cannot access YouTube streams directly.
"""
from __future__ import annotations
import asyncio
import logging
import os
import subprocess
import time
import urllib.request
import json
from pathlib import Path

from aiohttp import web

from youtube_proxy import (
    YTDLP_BINARY,
    extract_video_id,
    get_video_info,
    fetch_stream_via_invidious,
    fetch_stream_via_piped,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StreamProxy")

# Cache and download settings
CACHE_DIR = Path(os.environ.get("AUDIO_CACHE_DIR", "/tmp/audio_cache"))
# Don't create at import time - defer to runtime
CACHE_DURATION = int(os.environ.get("AUDIO_CACHE_TTL", str(6 * 3600)))
AUDIO_FORMAT = os.environ.get("AUDIO_FORMAT", "mp3")
AUDIO_QUALITY = os.environ.get("AUDIO_QUALITY", "192")  # kbps for yt-dlp
DOWNLOAD_TIMEOUT = int(os.environ.get("YTDLP_TIMEOUT", "60"))
COOKIES_FILE = os.environ.get("YOUTUBE_COOKIES_FILE", "")  # Path to cookies.txt

# Per-video locks to avoid duplicate downloads
download_locks: dict[str, asyncio.Lock] = {}


def _audio_path(video_id: str) -> Path:
    return CACHE_DIR / f"{video_id}.{AUDIO_FORMAT}"


async def _download_via_proxy_stream(video_id: str, target: Path) -> bool:
    """Download audio by fetching stream URL from Invidious/Piped, then downloading it."""
    loop = asyncio.get_running_loop()
    
    # Try Piped first
    try:
        logger.info("Getting stream URL from Piped for %s", video_id)
        stream_info = await loop.run_in_executor(None, fetch_stream_via_piped, video_id, "esp32")
        
        if stream_info and stream_info.get("stream_url"):
            stream_url = stream_info["stream_url"]
            logger.info("Got Piped stream URL, downloading to file...")
            
            def _download():
                req = urllib.request.Request(stream_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    with open(target, 'wb') as f:
                        f.write(resp.read())
            
            await loop.run_in_executor(None, _download)
            
            if target.exists() and target.stat().st_size > 0:
                logger.info("✅ Downloaded via Piped stream: %s (%.1f MB)", video_id, target.stat().st_size / 1e6)
                return True
    except Exception as exc:
        logger.warning("Piped stream download failed: %s", exc)
    
    # Try Invidious
    try:
        logger.info("Getting stream URL from Invidious for %s", video_id)
        stream_info = await loop.run_in_executor(None, fetch_stream_via_invidious, video_id, "esp32")
        
        if stream_info and stream_info.get("stream_url"):
            stream_url = stream_info["stream_url"]
            logger.info("Got Invidious stream URL, downloading to file...")
            
            def _download():
                req = urllib.request.Request(stream_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    with open(target, 'wb') as f:
                        f.write(resp.read())
            
            await loop.run_in_executor(None, _download)
            
            if target.exists() and target.stat().st_size > 0:
                logger.info("✅ Downloaded via Invidious stream: %s (%.1f MB)", video_id, target.stat().st_size / 1e6)
                return True
    except Exception as exc:
        logger.warning("Invidious stream download failed: %s", exc)
    
    return False


async def _download_via_api(video_id: str, target: Path) -> bool:
    """Download audio via third-party API."""
    
    # Method 1: Try y2mate.is API (stable, no key needed)
    try:
        logger.info("Trying y2mate.is API for %s", video_id)
        loop = asyncio.get_running_loop()
        
        def _fetch_y2mate():
            # Step 1: Get conversion options
            url1 = f"https://www.y2mate.com/mates/analyzeV2/ajax"
            data1 = f"k_query=https://youtube.com/watch?v={video_id}&k_page=home&hl=en&q_auto=0"
            req1 = urllib.request.Request(
                url1,
                data=data1.encode('utf-8'),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "*/*"
                }
            )
            with urllib.request.urlopen(req1, timeout=20) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                
            if result.get("status") != "ok":
                return None
                
            # Find audio link (mp3)
            links = result.get("links", {}).get("mp3", {})
            # Try 128kbps first
            if "128" in links:
                k_value = links["128"]["k"]
            elif links:
                k_value = list(links.values())[0]["k"]
            else:
                return None
            
            # Step 2: Get download link
            url2 = "https://www.y2mate.com/mates/convertV2/index"
            data2 = f"vid={video_id}&k={k_value}"
            req2 = urllib.request.Request(
                url2,
                data=data2.encode('utf-8'),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0"
                }
            )
            with urllib.request.urlopen(req2, timeout=30) as resp:
                convert_result = json.loads(resp.read().decode('utf-8'))
            
            if convert_result.get("status") != "ok":
                return None
                
            download_url = convert_result.get("dlink")
            if not download_url:
                return None
            
            # Step 3: Download file
            req3 = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req3, timeout=120) as resp:
                with open(target, 'wb') as f:
                    f.write(resp.read())
            
            return target if target.exists() and target.stat().st_size > 0 else None
        
        result = await loop.run_in_executor(None, _fetch_y2mate)
        if result:
            logger.info("✅ Downloaded via y2mate.is: %s (%.1f MB)", video_id, target.stat().st_size / 1e6)
            return True
            
    except Exception as exc:
        logger.warning("y2mate.is API failed: %s", exc)
    
    # Method 2: Try yt1s.io API
    try:
        logger.info("Trying yt1s.io API for %s", video_id)
        loop = asyncio.get_running_loop()
        
        def _fetch_yt1s():
            # Get download link
            url = "https://yt1s.io/api/ajaxSearch"
            data = json.dumps({
                "q": f"https://youtube.com/watch?v={video_id}",
                "vt": "mp3"
            })
            req = urllib.request.Request(
                url,
                data=data.encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0"
                }
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            
            if result.get("status") != "ok":
                return None
            
            # Find mp3 128kbps link
            links = result.get("links", {}).get("mp3", {})
            download_url = None
            for quality in ["128", "192", "256", "320"]:
                if quality in links:
                    download_url = links[quality].get("url")
                    break
            
            if not download_url:
                return None
            
            # Download file
            req2 = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=120) as resp:
                with open(target, 'wb') as f:
                    f.write(resp.read())
            
            return target if target.exists() and target.stat().st_size > 0 else None
        
        result = await loop.run_in_executor(None, _fetch_yt1s)
        if result:
            logger.info("✅ Downloaded via yt1s.io: %s (%.1f MB)", video_id, target.stat().st_size / 1e6)
            return True
            
    except Exception as exc:
        logger.warning("yt1s.io API failed: %s", exc)
    
    return False


async def _download_via_ytdlp_enhanced(video_id: str, target: Path) -> bool:
    """Download using yt-dlp with enhanced options to bypass bot detection."""
    loop = asyncio.get_running_loop()
    output_template = str(CACHE_DIR / f"{video_id}.%(ext)s")
    
    def _run_download():
        cmd = [
            YTDLP_BINARY,
            "--no-playlist",
            "--extract-audio",
            "--audio-format", AUDIO_FORMAT,
            "--audio-quality", AUDIO_QUALITY,
            "--ignore-errors",  # Continue on errors
        ]
        
        # Add cookies if available
        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            logger.info("Using cookies file: %s", COOKIES_FILE)
            # Copy to writable location since yt-dlp tries to update cookies
            cookies_copy = str(CACHE_DIR / "cookies.txt")
            try:
                import shutil
                shutil.copy(COOKIES_FILE, cookies_copy)
                cmd.extend(["--cookies", cookies_copy])
                # Use ONLY web client with cookies (ios/android don't support cookies)
                cmd.extend(["--extractor-args", "youtube:player_client=web"])
                logger.info("Using web client with cookies")
            except Exception as exc:
                logger.warning("Failed to copy cookies: %s", exc)
                cmd.extend(["--extractor-args", "youtube:player_client=android"])
        else:
            logger.warning("No cookies file found - using android client")
            cmd.extend(["--extractor-args", "youtube:player_client=android"])
        
        cmd.extend([
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            # Fallback to lower quality if signature solving fails
            "--format", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
            "-o", output_template,
            f"https://youtube.com/watch?v={video_id}",
        ])
        
        logger.info("Running yt-dlp with command: %s", " ".join(cmd[:10]) + "...")
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT,
        )
    
    proc = await loop.run_in_executor(None, _run_download)
    if proc.returncode != 0:
        logger.error("yt-dlp enhanced failed for %s: %s", video_id, proc.stderr.strip())
        return False
    
    # Find downloaded file
    for path in CACHE_DIR.glob(f"{video_id}.*"):
        if path.is_file():
            if path.suffix != f".{AUDIO_FORMAT}":
                try:
                    path.rename(target)
                    path = target
                except Exception as exc:
                    logger.warning("Failed to normalize extension for %s: %s", path, exc)
            logger.info("✅ Downloaded via yt-dlp: %s (%.1f MB)", video_id, path.stat().st_size / 1e6)
            return True
    
    return False


def _audio_path(video_id: str) -> Path:
    return CACHE_DIR / f"{video_id}.{AUDIO_FORMAT}"


async def ensure_audio_file(video_id: str) -> Path | None:
    """Ensure an MP3 exists locally for the given video.

    Returns the path if available or None on failure.
    """
    # Ensure cache dir exists (do it here, not at module import)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.error(f"Failed to create cache dir {CACHE_DIR}: {exc}")
        return None

    video_id = extract_video_id(video_id)
    target = _audio_path(video_id)

    # Reuse recent cache
    if target.exists():
        age = time.time() - target.stat().st_mtime
        if age < CACHE_DURATION:
            logger.info("Cache hit for %s (age %.0fs)", video_id, age)
            return target

    lock = download_locks.setdefault(video_id, asyncio.Lock())
    async with lock:
        # Another waiter may have completed the download
        if target.exists():
            age = time.time() - target.stat().st_mtime
            if age < CACHE_DURATION:
                logger.info("Cache hit after wait for %s (age %.0fs)", video_id, age)
                return target

        logger.info("⬇️  Downloading audio for %s as %s", video_id, AUDIO_FORMAT)
        
        # Try method 1: Download via Invidious/Piped proxy stream
        try:
            downloaded = await _download_via_proxy_stream(video_id, target)
            if downloaded:
                return target
        except Exception as exc:
            logger.warning("Proxy stream download failed for %s: %s", video_id, exc)
        
        # Try method 2: Use third-party API
        try:
            downloaded = await _download_via_api(video_id, target)
            if downloaded:
                return target
        except Exception as exc:
            logger.warning("API download failed for %s: %s", video_id, exc)
        
        # Try method 2: yt-dlp with extra options to bypass bot detection
        try:
            downloaded = await _download_via_ytdlp_enhanced(video_id, target)
            if downloaded:
                return target
        except Exception as exc:
            logger.error("yt-dlp enhanced failed for %s: %s", video_id, exc)

        logger.error("All download methods failed for %s", video_id)
        return None


async def stream_file_response(video_id: str) -> web.StreamResponse:
    path = await ensure_audio_file(video_id)
    if not path:
        return web.json_response(
            {
                "success": False,
                "video_id": video_id,
                "error": "Failed to prepare audio file",
            },
            status=500,
        )

    logger.info("📻 Serving cached audio for %s", video_id)
    return web.FileResponse(
        path,
        headers={
            "Content-Type": "audio/mpeg",
            "Cache-Control": "no-store",
        },
    )


async def stream_endpoint(request):
    video_id = request.match_info["video_id"]
    return await stream_file_response(video_id)


async def audio_endpoint(request):
    video_id = request.match_info["video_id"]
    return await stream_file_response(video_id)


async def url_endpoint(request):
    video_id = request.match_info["video_id"]
    logger.info("🔗 URL request for: %s", video_id)

    path = await ensure_audio_file(video_id)
    if not path:
        return web.json_response(
            {
                "success": False,
                "video_id": video_id,
                "error": "Could not download audio",
            },
            status=500,
        )

    stream_url = str(request.url.with_path(f"/audio/{video_id}").with_query(None))
    info = await asyncio.get_running_loop().run_in_executor(None, get_video_info, video_id)

    return web.json_response(
        {
            "success": True,
            "video_id": video_id,
            "stream_url": stream_url,
            "title": (info or {}).get("title"),
            "duration": (info or {}).get("duration"),
            "note": "Audio is cached locally on server; URL does not expire until cache evicts.",
        }
    )


async def health_check(request):
    # Ensure cache dir on first health check
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    
    files = list(CACHE_DIR.glob(f"*.{AUDIO_FORMAT}")) if CACHE_DIR.exists() else []
    total_size = sum(p.stat().st_size for p in files) if files else 0
    return web.json_response(
        {
            "status": "ok",
            "service": "ESP32 Music Stream Proxy",
            "cache_files": len(files),
            "cache_mb": round(total_size / 1e6, 2),
            "endpoints": {
                "/stream/{video_id}": "Stream/download audio (alias)",
                "/audio/{video_id}": "Stream/download audio",
                "/url/{video_id}": "Get stream URL as JSON",
            },
        }
    )


async def clear_expired_cache():
    """Periodically clear expired cache entries"""
    while True:
        await asyncio.sleep(1800)
        if not CACHE_DIR.exists():
            continue
        now = time.time()
        removed = 0
        for path in CACHE_DIR.glob(f"*.{AUDIO_FORMAT}"):
            if now - path.stat().st_mtime > CACHE_DURATION:
                try:
                    path.unlink()
                    removed += 1
                except FileNotFoundError:
                    continue
        if removed:
            logger.info("🧹 Cleared %d expired audio files", removed)


def init_app(app: web.Application) -> None:
    """Attach routes and cleanup task to an existing aiohttp app."""
    app.router.add_get("/stream/{video_id}", stream_endpoint)
    app.router.add_get("/audio/{video_id}", audio_endpoint)
    app.router.add_get("/url/{video_id}", url_endpoint)
    app.router.add_get("/health", health_check)

    async def start_cache_cleanup(_app):
        """Startup handler to begin cache cleanup task"""
        _app['cache_cleanup_task'] = asyncio.create_task(clear_expired_cache())
        logger.info("Cache cleanup task started")
    
    app.on_startup.append(start_cache_cleanup)


def create_app():
    app = web.Application()
    init_app(app)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("STREAM_PORT", 5001))

    logger.info("=" * 60)
    logger.info("🎵 ESP32 Music Stream Proxy (download-to-serve)")
    logger.info(f"Port: {port}")
    logger.info("Cache dir: %s", CACHE_DIR)
    logger.info("=" * 60)

    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
