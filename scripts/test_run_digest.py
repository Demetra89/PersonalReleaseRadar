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

print("Starting Enhanced Release Radar Pipeline...")

# 1. Fetch ALL artists from Postgres
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
artists = [line.strip() for line in artists_output.split('\n') if line.strip()]
print(f"Loaded ALL {len(artists)} artists from database.")

# 2. Check iTunes API with country=RU for recent releases (last 90 days to catch big drops like SALUKI)
new_releases = []
date_cutoff = datetime.now() - timedelta(days=90)

for artist in artists:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&country=RU&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results:
                rel_date_str = album.get('releaseDate')
                if rel_date_str:
                    rel_date = datetime.strptime(rel_date_str.split('T')[0], '%Y-%m-%d')
                    if rel_date >= date_cutoff:
                        new_releases.append({
                            'artist': album.get('artistName'),
                            'title': album.get('collectionName'),
                            'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                            'source': 'taste',
                            'url': album.get('collectionViewUrl'),
                            'release_date': album.get('releaseDate').split('T')[0],
                            'match_reason': f'Любимый исполнитель: {artist}'
                        })
    except Exception as e:
        pass

print(f"Found {len(new_releases)} releases from iTunes API across ALL artists.")

# 3. Add Last.fm Similar Artists
similar_artists = set()
for artist in artists[:10]:
    try:
        url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={urllib.parse.quote(artist)}&api_key={LASTFM_API_KEY}&format=json&limit=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for sim in data.get('similarartists', {}).get('artist', []):
                similar_artists.add(sim.get('name'))
    except Exception as e:
        pass

print(f"Found {len(similar_artists)} similar artists from Last.fm.")

# Fetch releases for top 10 similar artists
for sim_artist in list(similar_artists)[:10]:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(sim_artist)}&entity=album&country=RU&limit=2"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results:
                rel_date_str = album.get('releaseDate')
                if rel_date_str:
                    rel_date = datetime.strptime(rel_date_str.split('T')[0], '%Y-%m-%d')
                    if rel_date >= date_cutoff:
                        new_releases.append({
                            'artist': album.get('artistName'),
                            'title': album.get('collectionName'),
                            'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                            'source': 'similar',
                            'url': album.get('collectionViewUrl'),
                            'release_date': album.get('releaseDate').split('T')[0],
                            'match_reason': f'Похож на твоих артистов ({sim_artist})'
                        })
    except Exception as e:
        pass

# 4. Fetch RSS feeds for RU & US channels
rss_channels = [
    ('cloudeluxe', 'ru_cloud'),
    ('theflow', 'ru_cloud'),
    ('USANEWRAP', 'us_rap')
]

for channel_name, source_tag in rss_channels:
    try:
        url = f"http://localhost:1200/telegram/channel/{channel_name}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode('utf-8')
            import re
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', content)
            for t in titles[:5]:
                if len(t) > 10 and not 'http' in t:
                    new_releases.append({
                        'artist': 'Telegram Feed',
                        'title': t[:80],
                        'release_type': 'news',
                        'source': source_tag,
                        'url': f"https://t.me/{channel_name}",
                        'match_reason': f'Тренды из @{channel_name}'
                    })
    except Exception as e:
        pass

print(f"Total pool of releases gathered: {len(new_releases)}")

# 5. Deduplicate releases
dedup_map = {}
for r in new_releases:
    key = f"{r['artist'].lower()}_{r['title'].lower()}"
    if key not in dedup_map:
        dedup_map[key] = r

final_pool = list(dedup_map.values())

# 6. Format final message with Gemini
prompt = f"""Ты собираешь для меня музыкальный дайджест в Telegram.
На вход дают JSON со списком релизов и новостей:
artist, title, release_type, source (taste / similar / ru_cloud / us_rap), url, match_reason.

Правила:
- Раздели вывод на 3 четкие секции:
  1. "🎧 *Твои артисты*" (источники taste)
  2. "🔥 *Похожая музыка*" (источники similar)
  3. "🌐 *Главное в РФ и на Западе*" (источники ru_cloud и us_rap)
- Указывай прямые ссылки на альбомы/треки из url
- В секциях "Твои артисты" и "Похожая музыка" укажи коротко (1 фраза) причину рекомендаций
- Формат — идеальный Markdown для Telegram (bold, ссылки [название](url), без заголовков #)
- Максимум 15-20 лучших релизов суммарно

Данные:
{json.dumps(final_pool[:30], ensure_ascii=False)}
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

# 7. Send to Telegram
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
tg_body = json.dumps({
    "chat_id": TELEGRAM_CHAT_ID,
    "text": digest_text,
    "parse_mode": "Markdown"
}).encode('utf-8')

try:
    req = urllib.request.Request(tg_url, data=tg_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("Telegram send result:", resp.read().decode('utf-8'))
except Exception as e:
    print("Telegram send error:", e)

print("Enhanced test run completed!")
