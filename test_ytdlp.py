#!/usr/bin/env python3
"""
Test yt-dlp search functionality locally
"""
import subprocess
import json

def test_search(query):
    print(f"\n{'='*60}")
    print(f"Testing search for: {query}")
    print('='*60)
    
    # Test 1: ytsearch
    print("\n[Test 1] ytsearch method:")
    cmd1 = ['yt-dlp', '--dump-json', '--flat-playlist', '--skip-download', 
            '--extractor-args', 'youtube:player_client=android', f'ytsearch5:{query}']
    result1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=30)
    print(f"Return code: {result1.returncode}")
    print(f"Stdout lines: {len(result1.stdout.strip().split(chr(10))) if result1.stdout else 0}")
    if result1.stdout:
        for line in result1.stdout.strip().split('\n')[:2]:
            try:
                data = json.loads(line)
                print(f"  - {data.get('title')}")
            except:
                pass
    
    # Test 2: Direct URL
    print("\n[Test 2] Direct search URL method:")
    import urllib.parse
    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    cmd2 = ['yt-dlp', '--dump-json', '--flat-playlist', '--playlist-end', '5',
            '--extractor-args', 'youtube:player_client=android', search_url]
    result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
    print(f"Return code: {result2.returncode}")
    print(f"Stdout lines: {len(result2.stdout.strip().split(chr(10))) if result2.stdout else 0}")
    if result2.stdout:
        for line in result2.stdout.strip().split('\n')[:2]:
            try:
                data = json.loads(line)
                print(f"  - {data.get('title')}")
            except:
                pass

if __name__ == "__main__":
    test_search("Thằng Cuội")
    test_search("See Tình")
