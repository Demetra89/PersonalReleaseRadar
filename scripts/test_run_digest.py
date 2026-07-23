import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Auto-load .env file if available
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.strip().split('=', 1)
                os.environ[key.strip()] = val.strip()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

print("Starting 15-20 Spotify Release Radar Pipeline...")

# Date cutoff: last 14 days to collect a rich pool of 15-20 drops
date_cutoff = datetime.now() - timedelta(days=14)

# 1. Fetch ALL artists from Postgres
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
artists = [line.strip() for line in artists_output.split('\n') if line.strip()]

fresh_taste_releases = []
fresh_telegram_releases = []

# 2. Check iTunes API for favorite artists with 14-day window
for artist in artists:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&country=RU&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results:
                rel_date_str = album.get('releaseDate')
                if rel_date_str:
                    rel_date = datetime.strptime(rel_date_str.split('T')[0], '%Y-%m-%d')
                    if rel_date >= date_cutoff:
                        search_q = urllib.parse.quote(f"{album.get('artistName')} {album.get('collectionName')}")
                        spotify_url = f"https://open.spotify.com/search/{search_q}"
                        fresh_taste_releases.append({
                            'artist': album.get('artistName'),
                            'title': album.get('collectionName'),
                            'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                            'source': 'taste',
                            'url': spotify_url,
                            'release_date': album.get('releaseDate', '').split('T')[0]
                        })
    except Exception as e:
        pass

# 3. Fetch Telegram channel feeds
channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm', 'theflow']
tg_posts_for_ai = []

for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:15]:
                title = item.find('title').text if item.find('title') is not None else ''
                desc = item.find('description').text if item.find('description') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                import re
                clean_desc = re.sub(r'<[^>]+>', ' ', desc)
                tg_posts_for_ai.append({
                    'channel': ch,
                    'title': title,
                    'text': (title + " " + clean_desc)[:300],
                    'link': link
                })
    except Exception as e:
        pass

# AI Classification of drops
if tg_posts_for_ai:
    prompt = f"""Ты — эксперт по музыкальным релизам.
Проанализируй посты из Телеграм-каналов (cloudeluxe, USANEWRAP, rhymesm, theflow).
Найди ВСЕ ПОСТЫ, где вышли СВЕЖИЕ ТРЕКИ, АЛЬБОМЫ ИЛИ СИНГЛЫ.
Отфильтруй мемы, рекламу и вопросы. Выдели до 15 отличных релизов.

Верни JSON-массив объектов:
[
  {{
    "artist": "Имя исполнителя",
    "title": "Название трека или альбома",
    "source": "ru_cloud или us_rap"
  }}
]

Посты:
{json.dumps(tg_posts_for_ai, ensure_ascii=False)}
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    try:
        gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')
        req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            ai_text = res['candidates'][0]['content']['parts'][0]['text'].strip()
            if '```' in ai_text:
                ai_text = ai_text.split('```')[1].replace('json', '').strip()
            classified = json.loads(ai_text)
            for item in classified:
                search_q = urllib.parse.quote(f"{item.get('artist')} {item.get('title')}")
                item['url'] = f"https://open.spotify.com/search/{search_q}"
                fresh_telegram_releases.append(item)
    except Exception as e:
        print("Gemini AI classification error:", e)

# Deduplicate releases
dedup_map = {}
for r in fresh_taste_releases + fresh_telegram_releases:
    key = f"{r['artist'].lower()}_{r['title'].lower()}"
    if key not in dedup_map:
        dedup_map[key] = r

final_pool = list(dedup_map.values())
print(f"Total pool of fresh drops for digest: {len(final_pool)}")

# 4. Generate Digest with Gemini
prompt_final = f"""Ты собираешь ПЯТНИЧНЫЙ МУЗЫКАЛЬНЫЙ РАДАР РЕЛИЗОВ в Telegram.
Твоя цель — собрать БОЛЬШОЙ, НАСЫЩЕННЫЙ ДАЙДЖЕСТ (ровно 15-20 позиций).

Сформируй 2 раздела:
1. 🎧 *Твои любимые артисты* (из источника taste)
2. ⚡️ *Горячие новинки недели (РФ и Запад)* (из источников ru_cloud и us_rap)

ПРАВИЛА ОФОРМЛЕНИЯ ССЫЛОК:
- Для КАЖДОГО трека/альбома ОБЯЗАТЕЛЬНО делай ссылку на Spotify прямо в названии!
  Формат: [Артист — Название](url)
- Категорически запрещено изменять ссылки url из входных данных!
- Постарайся вывести МАКСИМАЛЬНО МНОГО РЕЛИЗОВ (15-20 штук суммарно), чтобы пользователю было что послушать!
- Используй только Telegram Markdown (*bold*, [ссылка](url)).

Данные:
{json.dumps(final_pool[:25], ensure_ascii=False)}
"""

digest_text = ""
try:
    gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt_final}]}]}).encode('utf-8')
    req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        digest_text = res['candidates'][0]['content']['parts'][0]['text']
except Exception as e:
    print("Gemini Digest Error:", e)

# 5. Send to Telegram
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

print("15-20 Spotify Release Radar completed!")
