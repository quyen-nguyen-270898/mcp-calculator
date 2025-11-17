# ESP32 Music Player - Cloud Solution

## 🎯 Architecture

```
User → AI/App → MCP Search → Get Video ID
                    ↓
ESP32 → Render Stream Proxy → YouTube → Audio Stream
```

## 🚀 Setup

### 1. Deploy on Render (đã xong)

Server đang chạy 3 services:
- **Port 10000**: Health check + MCP wrapper
- **Port 5001**: Stream proxy cho ESP32
- MCP servers: Calculator + Music Search

### 2. ESP32 Code

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include "Audio.h"

// Config
const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";
const char* serverUrl = "https://your-app.onrender.com";

Audio audio;

void setup() {
    Serial.begin(115200);
    
    // Connect WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected!");
    
    // Setup I2S for audio
    audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
    audio.setVolume(15);
    
    // Play music by video ID
    playMusic("FN7ALfpGxiI");  // Nơi Này Có Anh
}

void loop() {
    audio.loop();
}

void playMusic(String videoId) {
    Serial.println("Getting stream URL...");
    
    HTTPClient http;
    String url = String(serverUrl) + "/url/" + videoId;
    
    http.begin(url);
    int httpCode = http.GET();
    
    if (httpCode == 200) {
        String payload = http.getString();
        
        // Parse JSON to get stream_url
        // Simple parsing (or use ArduinoJson library)
        int urlStart = payload.indexOf("\"stream_url\":\"") + 14;
        int urlEnd = payload.indexOf("\"", urlStart);
        String streamUrl = payload.substring(urlStart, urlEnd);
        
        Serial.println("Playing: " + streamUrl);
        audio.connecttohost(streamUrl.c_str());
    } else {
        Serial.println("Failed to get stream URL");
    }
    
    http.end();
}

// Audio events
void audio_info(const char *info) {
    Serial.print("Audio info: ");
    Serial.println(info);
}
```

### 3. Alternative: Direct Redirect (simpler)

Nếu ESP32 Audio library hỗ trợ HTTP redirect:

```cpp
void playMusic(String videoId) {
    String url = String(serverUrl) + "/stream/" + videoId;
    audio.connecttohost(url.c_str());
    // Server tự động redirect đến stream URL
}
```

## 📡 API Endpoints

### GET /url/{video_id}
Trả về stream URL dạng JSON:
```json
{
  "success": true,
  "stream_url": "https://rr1---sn-xxx.googlevideo.com/...",
  "title": "NƠI NÀY CÓ ANH",
  "expires_in_seconds": 14400
}
```

### GET /stream/{video_id}
HTTP 302 redirect trực tiếp đến stream URL

## 🎵 Complete Workflow

### From User to ESP32:

1. **User**: "Phát bài Nơi Này Có Anh"

2. **AI calls MCP**:
```javascript
search_music("Nơi này có anh Sơn Tùng MTP")
// Returns: video_id = "FN7ALfpGxiI"
```

3. **Send to ESP32** (via HTTP API, MQTT, etc):
```json
{
  "action": "play",
  "video_id": "FN7ALfpGxiI"
}
```

4. **ESP32 fetches stream**:
```cpp
GET https://your-app.onrender.com/url/FN7ALfpGxiI
```

5. **ESP32 plays**:
```cpp
audio.connecttohost(stream_url);
```

## 🔄 Handling Expiration

Stream URLs expire after ~6 hours. Implement retry logic:

```cpp
void audio_eof_stream(const char *info) {
    Serial.println("Stream ended, refreshing...");
    playMusic(currentVideoId);  // Re-fetch URL
}
```

## 🛠️ Troubleshooting

### Issue: "Failed to get stream URL"
- Check Render logs: `https://dashboard.render.com`
- YouTube might be blocking temporarily
- Try again after a few minutes

### Issue: Audio stuttering
- Reduce audio quality (already optimized for 128kbps)
- Check WiFi signal strength
- Increase ESP32 buffer size

### Issue: Stream stops after 5-6 hours
- Normal! Stream URLs expire
- Implement auto-refresh in `audio_eof_stream()`

## 📊 ESP32 Requirements

- **ESP32-S3 N16R8** (your board) ✅
- **8MB PSRAM** for buffering ✅
- **WiFi connection** ✅
- **I2S audio output** (DAC or amplifier)

## 🎼 Full Example Project

See `examples/esp32_music_player/` for complete working example with:
- WiFi reconnection
- Playlist management
- MQTT control
- Web interface
- Auto-refresh URLs

## 🌐 Communication Options

### Option 1: HTTP Polling
ESP32 polls server for commands:
```cpp
// Check every 5 seconds
if (millis() - lastCheck > 5000) {
    checkForNewSong();
}
```

### Option 2: MQTT (Recommended)
Real-time commands:
```cpp
mqtt.subscribe("esp32/music/play");
// Receive: {"video_id": "FN7ALfpGxiI"}
```

### Option 3: WebSocket
Persistent connection for instant control

## 🎉 That's It!

Với setup này:
- ✅ Hoàn toàn cloud-based
- ✅ Không cần local server
- ✅ ESP32 + Render server là đủ
- ✅ MCP search + Stream proxy
- ✅ Handle expiration tự động

Deploy và enjoy music trên ESP32! 🎵
