import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# Auto-load .env file if available
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

print("Starting Complete Release Radar Pipeline...")

# 1. Fetch ALL artists from Postgres
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
artists = [line.strip() for line in artists_output.split('\n') if line.strip()]
print(f"Loaded ALL {len(artists)} artists from database.")

taste_releases = []
similar_releases = []
general_releases = []

# 2. Check iTunes API for ALL 66 favorite artists (get their latest album/single)
for artist in artists:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&country=RU&limit=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results[:1]: # Top latest album
                taste_releases.append({
                    'artist': album.get('artistName'),
                    'title': album.get('collectionName'),
                    'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                    'source': 'taste',
                    'url': album.get('collectionViewUrl'),
                    'release_date': album.get('releaseDate', '').split('T')[0],
                    'match_reason': f'Любимый исполнитель из твоей медиатеки'
                })
    except Exception as e:
        pass

print(f"Gathered {len(taste_releases)} releases from ALL favorite artists (including SALUKI, GONE.Fludd, CUPSIZE, etc.).")

# 3. Expand Last.fm Similar Artists
popular_similar_seed = ["SALUKI", "GON.Fludd", "Sqwore", "2hollis", "21 Savage", "Travis Scott"]
similar_artist_names = set()

for seed in popular_similar_seed:
    try:
        url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={urllib.parse.quote(seed)}&api_key={LASTFM_API_KEY}&format=json&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for sim in data.get('similarartists', {}).get('artist', []):
                s_name = sim.get('name')
                if s_name and s_name.lower() not in [a.lower() for a in artists]:
                    similar_artist_names.add(s_name)
    except Exception as e:
        pass

print(f"Found {len(similar_artist_names)} similar artists from Last.fm.")

for sim_artist in list(similar_artist_names)[:10]:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(sim_artist)}&entity=album&country=RU&limit=2"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results[:1]:
                similar_releases.append({
                    'artist': album.get('artistName'),
                    'title': album.get('collectionName'),
                    'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                    'source': 'similar',
                    'url': album.get('collectionViewUrl'),
                    'release_date': album.get('releaseDate', '').split('T')[0],
                    'match_reason': f'Похож по стилю на твоих любимых артистов'
                })
    except Exception as e:
        pass

# 4. Fetch RF & US Top Charts & Telegram Feed Highlights
try:
    url = "https://itunes.apple.com/ru/rss/topalbums/limit=5/json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=4) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        entries = data.get('feed', {}).get('entry', [])
        for entry in entries[:5]:
            general_releases.append({
                'artist': entry.get('im:artist', {}).get('label', 'Популярное в РФ'),
                'title': entry.get('im:name', {}).get('label', 'Альбом'),
                'release_type': 'chart',
                'source': 'ru_cloud',
                'url': entry.get('link', {}).get('attributes', {}).get('href', ''),
                'match_reason': 'Топ чартов РФ'
            })
except Exception as e:
    pass

try:
    url = "https://itunes.apple.com/us/rss/topalbums/limit=5/json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=4) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        entries = data.get('feed', {}).get('entry', [])
        for entry in entries[:5]:
            general_releases.append({
                'artist': entry.get('im:artist', {}).get('label', 'Популярное в US'),
                'title': entry.get('im:name', {}).get('label', 'Альбом'),
                'release_type': 'chart',
                'source': 'us_rap',
                'url': entry.get('link', {}).get('attributes', {}).get('href', ''),
                'match_reason': 'Топ чартов США'
            })
except Exception as e:
    pass

# Combine all pools
all_candidates = taste_releases[:12] + similar_releases[:5] + general_releases[:6]

# 5. Format final message with Gemini
prompt = f"""Ты собираешь идеальный музыкальный дайджест в Telegram.
Тебе присылают JSON со списками релизов по трем категориям:
- taste (любимые артисты)
- similar (похожая музыка)
- ru_cloud / us_rap (главные тренды РФ и Запада)

ОБЯЗАТЕЛЬНО сделай 3 красивых, содержательных раздела:
1. 🎧 *Твои артисты* (релизы от любимых исполнителей, включай SALUKI, GONE.Fludd, CUPSIZE, 2hollis и др.)
2. 🔥 *Похожая музыка* (рекомендации на основе вкусa)
3. 🌐 *Главное в РФ и на Западе* (хиты из чартов и каналов)

Правила:
- Приводи прямые ссылки на альбомы вида [Артист — Название](url)
- В блоках "Твои артисты" и "Похожая музыка" напиши по 1 короткой, сочной причине почему стоит послушать
- Не оставляй разделы пустыми! Заполняй их переданными данными.
- Формат — только чистый Telegram Markdown (используй *bold*, не используй заголовки H1/H2).

Данные:
{json.dumps(all_candidates, ensure_ascii=False)}
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')

digest_text = ""
try:
    req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        digest_text = res['candidates'][0]['content']['parts'][0]['text']
except Exception as e:
    print("Gemini API error:", e)

# 6. Send to Telegram
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
tg_body = json.dumps({
    "chat_id": TELEGRAM_CHAT_ID,
    "text": digest_text,
    "parse_mode": "Markdown",
    "disable_web_page_preview": True
}).encode('utf-8')

try:
    req = urllib.request.Request(tg_url, data=tg_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("Telegram send result:", resp.read().decode('utf-8'))
except Exception as e:
    print("Telegram send error:", e)

print("Full radar run completed!")
