# ESP32 Music Streaming Guide

## MCP Music Streamer Tools

### 1. `search_music` - Tìm nhạc trên YouTube
```json
{
  "query": "see tình",
  "max_results": 5
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "id": "video_id",
      "title": "Sẽ Tình - Hoàng Thùy Linh",
      "duration": 240,
      "url": "https://youtube.com/watch?v=..."
    }
  ]
}
```

### 2. `get_stream_url` - Lấy URL stream cho ESP32
```json
{
  "url": "dQw4w9WgXcQ",
  "format": "esp32"
}
```

**Response:**
```json
{
  "success": true,
  "stream": {
    "url": "https://rr1---sn-xxx.googlevideo.com/...",
    "title": "Song Name",
    "duration": 240,
    "ext": "m4a",
    "abr": 128,
    "acodec": "opus"
  }
}
```

### 3. `get_music_info` - Lấy thông tin chi tiết
```json
{
  "url": "https://youtube.com/watch?v=dQw4w9WgXcQ"
}
```

## ESP32 Example Code

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include "Audio.h"

Audio audio;

void setup() {
    // Connect WiFi
    WiFi.begin("SSID", "PASSWORD");
    while (WiFi.status() != WL_CONNECTED) delay(500);
    
    // Setup I2S
    audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
    audio.setVolume(15);
    
    // Get stream URL from MCP (via your app)
    String streamUrl = getStreamUrlFromMCP("dQw4w9WgXcQ");
    
    // Play stream
    audio.connecttohost(streamUrl.c_str());
}

void loop() {
    audio.loop();
}

String getStreamUrlFromMCP(String videoId) {
    // Your app calls MCP tool "get_stream_url"
    // Then sends the URL to ESP32 via HTTP/MQTT/etc
    // For demo, you can hardcode a test URL
    return "http://example.com/audio.mp3";
}
```

## How It Works

1. **User Request** → Your app/AI agent
2. **App calls MCP** `search_music("see tình")`
3. **MCP returns** list of songs
4. **App calls MCP** `get_stream_url(selected_video_id)`
5. **MCP uses yt-dlp** to get direct stream URL
6. **App sends URL** to ESP32 (HTTP API/MQTT)
7. **ESP32 plays** the stream

## Stream URL Characteristics

- ✅ Direct HTTP/HTTPS URL
- ✅ Audio-only (128kbps optimal for ESP32)
- ✅ M4A/Opus format (widely supported)
- ⚠️ Temporary (expires after ~6 hours)
- ⚠️ Requires refresh for continuous playback

## Integration Options

### Option A: REST API
Create a simple REST API that ESP32 can call:
```
GET /api/stream?q=see+tinh
Response: {"url": "https://...", "title": "..."}
```

### Option B: MQTT
ESP32 subscribes to topic, receives stream URLs:
```
Topic: esp32/music/play
Payload: {"url": "https://..."}
```

### Option C: Direct HTTP Proxy
MCP server proxies the stream:
```
GET /stream/VIDEO_ID
→ Streams audio directly to ESP32
```

## Notes for ESP32

- Use PSRAM for buffering (you have 8MB!)
- Lower bitrate = more reliable (128kbps recommended)
- Handle URL expiration (re-request after 4-5 hours)
- Consider local cache for frequently played songs

## Next Steps

1. Deploy MCP server to cloud (Render, Railway, etc.)
2. Create REST API wrapper for ESP32
3. Build ESP32 firmware with Audio library
4. Test with your favorite songs! 🎵
