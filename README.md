# MCP Multi-Tool Server

MCP servers providing calculator and music streaming capabilities.

## Available Servers

### 1. Calculator (`calculator.py`)
Evaluate Python mathematical expressions

### 2. Music Streamer (`music_streamer.py`)
Search music from YouTube

### 3. Stream Proxy (`stream_proxy.py`)
Provides audio streaming endpoints for ESP32

## 🎵 ESP32 Music Player Setup

**Complete cloud solution - no local server needed!**

1. **Deploy on Render** (done!)
2. **ESP32 connects** to `https://your-app.onrender.com/url/{video_id}`
3. **Get stream URL** and play!

📖 **[ESP32 Cloud Setup Guide](ESP32_CLOUD_SETUP.md)** - Complete ESP32 code & setup

**Quick Start:**
```cpp
// ESP32 code
String videoId = "FN7ALfpGxiI";  // From MCP search
String url = "https://your-app.onrender.com/url/" + videoId;
// Fetch URL → Parse JSON → Play stream
```

**Services on Render:**
- Port 10000: Health check + MCP wrapper
- Port 5001: Stream proxy for ESP32
- MCP: Calculator + Music search

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variable:
```bash
export MCP_ENDPOINT='wss://your-endpoint-url'
```

3. Run locally:
```bash
python3 mcp_pipe.py
```

## Deploy to Render

1. Push code to GitHub

2. Create new Web Service on Render:
   - Connect your GitHub repository
   - Select branch: `main`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python server.py`

3. Add Environment Variable:
   - Key: `MCP_ENDPOINT`
   - Value: Your WebSocket endpoint URL
   - (Optional) `YOUTUBE_API_KEY`: Official YouTube Data API key for reliable search

4. Deploy!

The service will:
- Start an HTTP server on port 10000 for Render health checks
- Run MCP pipe in background to connect calculator to your endpoint
- Auto-restart if MCP connection fails

Health check endpoint: `https://your-app.onrender.com/health`

### Streaming reliability tips

- Set `YOUTUBE_API_KEY` so searches use the official Data API instead of scraping.
- You can override proxy frontends without redeploying:
   - `PIPED_API_INSTANCES` – comma-separated list of Piped API hosts.
   - `INVIDIOUS_API_INSTANCES` – comma-separated list of Invidious API hosts.
- The ESP32 stream proxy caches resolved URLs for ~4 hours to minimize repeated proxy hits.
