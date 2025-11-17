#!/usr/bin/env python3
"""Common helpers for YouTube search + streaming proxies.

This module centralises the logic for:
- Searching YouTube (preferring the official Data API when an API key is present).
- Fetching audio streams via trusted proxy frontends (Piped / Invidious) with
  graceful fallback to yt-dlp for local use.

The goal is to avoid hammering YouTube directly from cloud hosts (which often
triggers bot verification) while still providing reliable metadata/streams for
clients such as ESP32 devices.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("YouTubeProxy")

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_SEARCH_REGION = os.environ.get("YOUTUBE_SEARCH_REGION", "VN")
YOUTUBE_API_BASE = os.environ.get(
    "YOUTUBE_API_BASE", "https://www.googleapis.com/youtube/v3"
)
DEFAULT_USER_AGENT = os.environ.get(
    "YOUTUBE_PROXY_USER_AGENT",
    "Mozilla/5.0 (Linux; Android 12; Pixel 5 Build/SPB3.210618.013; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.61 Mobile Safari/537.36",
)
TARGET_ABR = int(os.environ.get("YOUTUBE_TARGET_ABR", "128"))
YTDLP_BINARY = os.environ.get("YT_DLP_BIN", "yt-dlp")
YTDLP_TIMEOUT = int(os.environ.get("YT_DLP_TIMEOUT", "25"))

PIPED_INSTANCES = [
    inst.strip().rstrip("/")
    for inst in os.environ.get(
        "PIPED_API_INSTANCES",
        "https://pipedapi.kavin.rocks,https://pipedapi.moomoo.me,https://pipedapi.tokhmi.xyz",
    ).split(",")
    if inst.strip()
]
INVIDIOUS_INSTANCES = [
    inst.strip().rstrip("/")
    for inst in os.environ.get(
        "INVIDIOUS_API_INSTANCES",
        "https://inv.nadeko.net,https://invidious.snopyta.org,https://invidious.osi.kr,"
        "https://y.com.sb,https://inv.riverside.rocks",
    ).split(",")
    if inst.strip()
]


def extract_video_id(value: str) -> str:
    """Extract the canonical YouTube video id from many URL styles."""
    if not value:
        return value
    value = value.strip()
    if re.match(r"^[a-zA-Z0-9_-]{11}$", value):
        return value

    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return value[-11:]


def _http_get_json(url: str, timeout: int = 12) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        data = response.read().decode(charset)
        return json.loads(data)


def _parse_iso8601_duration(value: str) -> Optional[int]:
    """Convert ISO8601 duration (e.g. PT4M12S) to seconds."""
    if not value or not value.startswith("P"):
        return None
    pattern = re.compile(
        r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
    )
    match = pattern.match(value)
    if not match:
        return None
    parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
    return (
        parts.get("days", 0) * 86400
        + parts.get("hours", 0) * 3600
        + parts.get("minutes", 0) * 60
        + parts.get("seconds", 0)
    )


def search_via_api(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    if not YOUTUBE_API_KEY:
        return []

    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 25),
            "videoEmbeddable": "true",
            "key": YOUTUBE_API_KEY,
            "regionCode": YOUTUBE_SEARCH_REGION,
        }
    )
    search_url = f"{YOUTUBE_API_BASE}/search?{params}"
    data = _http_get_json(search_url)
    if not data.get("items"):
        return []

    video_ids = [item["id"]["videoId"] for item in data["items"] if "id" in item]
    durations: Dict[str, Optional[int]] = {}
    if video_ids:
        params_info = urllib.parse.urlencode(
            {
                "part": "contentDetails",
                "id": ",".join(video_ids),
                "key": YOUTUBE_API_KEY,
            }
        )
        info_url = f"{YOUTUBE_API_BASE}/videos?{params_info}"
        info_data = _http_get_json(info_url)
        for item in info_data.get("items", []):
            vid = item.get("id")
            duration_str = item.get("contentDetails", {}).get("duration")
            durations[vid] = _parse_iso8601_duration(duration_str)

    results = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        results.append(
            {
                "id": video_id,
                "title": snippet.get("title"),
                "duration": durations.get(video_id),
                "url": f"https://youtube.com/watch?v={video_id}",
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                "source": "youtube-data-api",
            }
        )
    return results


def search_via_ytdlp(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    base_cmd = [
        YTDLP_BINARY,
        "--dump-json",
        "--flat-playlist",
        "--skip-download",
        "--extractor-args",
        "youtube:player_client=android",
    ]
    methods = [
        base_cmd + [f"ytsearch{max_results}:{query}"],
        base_cmd
        + [
            "--playlist-end",
            str(max_results),
            f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
        ],
    ]
    for cmd in methods:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=YTDLP_TIMEOUT,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            for line in proc.stdout.strip().splitlines():
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("_type") in (None, "url"):
                    vid = data.get("id") or data.get("url", "").split("v=")[-1][:11]
                    results.append(
                        {
                            "id": vid,
                            "title": data.get("title"),
                            "duration": data.get("duration"),
                            "url": data.get("url") or f"https://youtube.com/watch?v={vid}",
                            "source": "yt-dlp",
                        }
                    )
            if results:
                break
        except Exception as exc:  # noqa: BLE001 - broad by design for resiliency
            LOGGER.warning("yt-dlp search failed: %s", exc)
            continue
    return results[:max_results]


def search_tracks(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search YouTube with API preference and yt-dlp fallback."""
    if not query:
        return []
    api_results = []
    try:
        api_results = search_via_api(query, max_results)
    except urllib.error.HTTPError as exc:
        LOGGER.warning("YouTube Data API error: %s", exc)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("YouTube Data API unexpected error: %s", exc)
    if api_results:
        return api_results
    return search_via_ytdlp(query, max_results)


def _bitrate_to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.findall(r"\d+", str(value))
    if not digits:
        return 0
    number = int(digits[0])
    if str(value).lower().endswith("k"):
        return number * 1000
    return number


def _select_stream(audio_streams: List[Dict[str, Any]], quality: str) -> Optional[Dict[str, Any]]:
    if not audio_streams:
        return None
    # sort by bitrate to make selection deterministic
    ordered = sorted(audio_streams, key=lambda item: _bitrate_to_int(item.get("bitrate")))
    if quality == "high":
        return ordered[-1]
    if quality == "low":
        return ordered[0]
    # "esp32" or "medium" default -> pick closest to TARGET_ABR
    target = TARGET_ABR * 1000
    return min(ordered, key=lambda item: abs(_bitrate_to_int(item.get("bitrate")) - target))


def fetch_stream_via_piped(video_id: str, quality: str = "esp32") -> Optional[Dict[str, Any]]:
    for instance in PIPED_INSTANCES:
        try:
            data = _http_get_json(f"{instance}/streams/{video_id}")
            audio_streams = data.get("audioStreams", [])
            chosen = _select_stream(audio_streams, quality)
            if not chosen:
                continue
            bitrate = _bitrate_to_int(chosen.get("bitrate"))
            return {
                "video_id": video_id,
                "title": data.get("title"),
                "duration": data.get("duration"),
                "stream_url": chosen.get("url"),
                "bitrate": bitrate,
                "format": chosen.get("mimeType"),
                "source": "piped",
                "instance": instance,
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Piped instance %s failed: %s", instance, exc)
            continue
    return None


def fetch_stream_via_invidious(video_id: str, quality: str = "esp32") -> Optional[Dict[str, Any]]:
    for instance in INVIDIOUS_INSTANCES:
        try:
            data = _http_get_json(f"{instance}/api/v1/videos/{video_id}")
            audio_formats = [
                fmt
                for fmt in data.get("adaptiveFormats", [])
                if fmt.get("type", "").startswith("audio")
            ]
            chosen = _select_stream(audio_formats, quality)
            if not chosen:
                continue
            bitrate = _bitrate_to_int(chosen.get("bitrate"))
            return {
                "video_id": video_id,
                "title": data.get("title"),
                "duration": data.get("lengthSeconds"),
                "stream_url": chosen.get("url"),
                "bitrate": bitrate,
                "format": chosen.get("type"),
                "source": "invidious",
                "instance": instance,
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Invidious instance %s failed: %s", instance, exc)
            continue
    return None


def fetch_stream_via_ytdlp(video_id: str, quality: str = "esp32") -> Optional[Dict[str, Any]]:
    format_selector = "bestaudio[abr<=160]/bestaudio"
    try:
        proc_url = subprocess.run(
            [
                YTDLP_BINARY,
                "--get-url",
                "-f",
                format_selector,
                "--extractor-args",
                "youtube:player_client=android",
                f"https://youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT,
        )
        if proc_url.returncode != 0 or not proc_url.stdout.strip():
            return None
        stream_url = proc_url.stdout.strip().splitlines()[0]
        proc_info = subprocess.run(
            [
                YTDLP_BINARY,
                "--dump-json",
                "--skip-download",
                "--extractor-args",
                "youtube:player_client=android",
                f"https://youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT,
        )
        title = "Unknown"
        duration = None
        if proc_info.returncode == 0 and proc_info.stdout.strip():
            try:
                data = json.loads(proc_info.stdout)
                title = data.get("title", title)
                duration = data.get("duration")
            except json.JSONDecodeError:
                pass
        return {
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "stream_url": stream_url,
            "bitrate": None,
            "format": "yt-dlp",
            "source": "yt-dlp",
        }
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("yt-dlp fallback failed: %s", exc)
        return None


def get_audio_stream(video_id: str, quality: str = "esp32") -> Optional[Dict[str, Any]]:
    video_id = extract_video_id(video_id)
    pipeline = [fetch_stream_via_piped, fetch_stream_via_invidious, fetch_stream_via_ytdlp]
    for provider in pipeline:
        result = provider(video_id, quality)
        if result and result.get("stream_url"):
            result["quality_request"] = quality
            result["fetched_at"] = int(time.time())
            return result
    return None


def get_video_info(video_id: str) -> Optional[Dict[str, Any]]:
    """Return lightweight metadata using API when possible."""
    video_id = extract_video_id(video_id)
    if YOUTUBE_API_KEY:
        try:
            params = urllib.parse.urlencode(
                {
                    "part": "snippet,contentDetails,statistics",
                    "id": video_id,
                    "key": YOUTUBE_API_KEY,
                }
            )
            data = _http_get_json(f"{YOUTUBE_API_BASE}/videos?{params}")
            if data.get("items"):
                item = data["items"][0]
                snippet = item.get("snippet", {})
                return {
                    "id": video_id,
                    "title": snippet.get("title"),
                    "duration": _parse_iso8601_duration(
                        item.get("contentDetails", {}).get("duration")
                    ),
                    "uploader": snippet.get("channelTitle"),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    "description": snippet.get("description"),
                    "source": "youtube-data-api",
                }
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch info via API: %s", exc)

    # yt-dlp fallback
    try:
        proc = subprocess.run(
            [
                YTDLP_BINARY,
                "--dump-json",
                "--skip-download",
                "--extractor-args",
                "youtube:player_client=android,web",
                f"https://youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        data = json.loads(proc.stdout)
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "duration": data.get("duration"),
            "uploader": data.get("uploader"),
            "thumbnail": data.get("thumbnail"),
            "description": data.get("description"),
            "source": "yt-dlp",
        }
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("yt-dlp video info fallback failed: %s", exc)
        return None

