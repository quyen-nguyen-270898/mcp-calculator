#!/usr/bin/env python3
"""
Simple Local Music Proxy for ESP32
Run this on your local computer/Raspberry Pi

Usage:
    python3 local_music_proxy.py

Then from ESP32:
    http://YOUR_LOCAL_IP:5000/stream/VIDEO_ID
"""

from flask import Flask, redirect, jsonify, request
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MusicProxy')

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "service": "ESP32 Music Proxy",
        "endpoints": {
            "/stream/<video_id>": "Get stream URL and redirect",
            "/url/<video_id>": "Get stream URL as JSON",
            "/info/<video_id>": "Get video info"
        },
        "example": "http://localhost:5000/stream/FN7ALfpGxiI"
    })

@app.route('/stream/<video_id>')
def stream(video_id):
    """Redirect to actual stream URL"""
    try:
        logger.info(f"Getting stream for video: {video_id}")
        
        result = subprocess.run(
            ['yt-dlp', '-f', 'bestaudio[abr<=128]/bestaudio', '--get-url', 
             f'https://youtube.com/watch?v={video_id}'],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"yt-dlp failed: {result.stderr}")
            return jsonify({"error": "Failed to get stream"}), 500
        
        stream_url = result.stdout.strip()
        logger.info(f"Redirecting to: {stream_url[:80]}...")
        
        return redirect(stream_url)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/url/<video_id>')
def get_url(video_id):
    """Return stream URL as JSON"""
    try:
        logger.info(f"Getting URL for video: {video_id}")
        
        result = subprocess.run(
            ['yt-dlp', '-f', 'bestaudio[abr<=128]/bestaudio', '--get-url',
             f'https://youtube.com/watch?v={video_id}'],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({"error": "Failed to get stream"}), 500
        
        stream_url = result.stdout.strip()
        
        return jsonify({
            "success": True,
            "video_id": video_id,
            "stream_url": stream_url,
            "note": "URL expires in ~6 hours"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/info/<video_id>')
def get_info(video_id):
    """Get video information"""
    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--skip-download',
             f'https://youtube.com/watch?v={video_id}'],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({"error": "Failed to get info"}), 500
        
        import json
        data = json.loads(result.stdout)
        
        return jsonify({
            "video_id": video_id,
            "title": data.get("title"),
            "duration": data.get("duration"),
            "uploader": data.get("uploader"),
            "thumbnail": data.get("thumbnail")
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("=" * 60)
    print("🎵 ESP32 Music Proxy Server")
    print("=" * 60)
    print(f"Running on: http://{local_ip}:5000")
    print(f"Local:      http://localhost:5000")
    print()
    print("ESP32 Example:")
    print(f'  audio.connecttohost("http://{local_ip}:5000/stream/VIDEO_ID");')
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
