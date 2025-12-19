# Hướng dẫn xuất cookies YouTube để bypass bot detection

## Cách 1: Dùng extension "Get cookies.txt LOCALLY"

1. **Cài extension**:
   - Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   - Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/

2. **Đăng nhập YouTube** trong trình duyệt

3. **Xuất cookies**:
   - Vào youtube.com
   - Click icon extension
   - Click "Export" → lưu file `cookies.txt`

4. **Upload lên Render**:
   ```bash
   # Tạo secret file trên Render
   # Dashboard → Service → Environment → Secret Files
   # Filename: /etc/secrets/youtube_cookies.txt
   # Content: paste nội dung cookies.txt
   ```

5. **Set biến môi trường**:
   ```bash
   YOUTUBE_COOKIES_FILE=/etc/secrets/youtube_cookies.txt
   ```

## Cách 2: Dùng yt-dlp để xuất cookies (nếu đã đăng nhập trên máy)

```bash
# Chrome
yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://youtube.com

# Firefox  
yt-dlp --cookies-from-browser firefox --cookies cookies.txt https://youtube.com

# Upload cookies.txt lên Render như trên
```

## Lưu ý

- Cookies **hết hạn sau vài tuần/tháng**, cần refresh định kỳ
- **Không share** cookies vì chứa session đăng nhập
- Nếu không dùng cookies, code sẽ log warning nhưng vẫn thử download (có thể fail)

## Test local

```bash
export YOUTUBE_COOKIES_FILE=/path/to/cookies.txt
python3 stream_proxy.py
curl http://localhost:5001/url/488ceQWoGGw
```
