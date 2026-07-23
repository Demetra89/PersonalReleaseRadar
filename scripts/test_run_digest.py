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

print("Starting STRICT FRESH (7-DAY) Release Radar Pipeline...")

# Date cutoff: strictly last 7 days
seven_days_ago = datetime.now() - timedelta(days=7)

# 1. Fetch ALL artists from Postgres
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
artists = [line.strip() for line in artists_output.split('\n') if line.strip()]
print(f"Loaded ALL {len(artists)} artists from database.")

fresh_taste_releases = []
fresh_telegram_releases = []

# 2. Check iTunes API for ALL 66 favorite artists — STRICTLY LAST 7 DAYS ONLY!
for artist in artists:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&country=RU&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results:
                rel_date_str = album.get('releaseDate')
                if rel_date_str:
                    rel_date = datetime.strptime(rel_date_str.split('T')[0], '%Y-%m-%d')
                    if rel_date >= seven_days_ago:
                        fresh_taste_releases.append({
                            'artist': album.get('artistName'),
                            'title': album.get('collectionName'),
                            'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                            'source': 'taste',
                            'url': album.get('collectionViewUrl'),
                            'release_date': album.get('releaseDate', '').split('T')[0],
                            'match_reason': f'Свежий релиз твоего любимого артиста {artist}'
                        })
    except Exception as e:
        pass

print(f"Found {len(fresh_taste_releases)} STRICTLY FRESH (7-day) releases from favorite artists.")

# 3. Fetch Telegram channel feeds and classify via Gemini AI
channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm']

tg_posts_for_ai = []
for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:10]:
                title = item.find('title').text if item.find('title') is not None else ''
                desc = item.find('description').text if item.find('description') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                import re
                clean_desc = re.sub(r'<[^>]+>', ' ', desc)
                tg_posts_for_ai.append({
                    'channel': ch,
                    'title': title,
                    'text': (title + " " + clean_desc)[:250],
                    'link': link
                })
    except Exception as e:
        pass

print(f"Collected {len(tg_posts_for_ai)} Telegram posts for AI classification...")

# Ask Gemini to filter strictly NEW MUSIC DROPS from Telegram posts
if tg_posts_for_ai:
    prompt = f"""Ты — строго фильтр свежих музыкальных релизов.
Тебе дан список постов из музыкальных Телеграм-каналов (cloudeluxe, USANEWRAP, rhymesm).
Проанализируй текст и выдели ТОЛЬКО ТЕ ПОСТЫ, где сообщается о ВЫХОДЕ НОВОГО ТРЕКА / АЛЬБОМА / СИНГЛА / ДРОПА.
Игнорируй мемы, слухи, драмы, вопросы к подписчикам, рекламу.

Верни JSON-массив объектов:
[
  {{
    "artist": "Имя исполнителя",
    "title": "Название трека или альбома",
    "source": "ru_cloud или us_rap",
    "url": "прямая ссылка на пост в telegram"
  }}
]

Посты:
{json.dumps(tg_posts_for_ai, ensure_ascii=False)}
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')

    try:
        req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            ai_text = res['candidates'][0]['content']['parts'][0]['text'].strip()
            if '```' in ai_text:
                ai_text = ai_text.split('```')[1].replace('json', '').strip()
            classified = json.loads(ai_text)
            for item in classified:
                fresh_telegram_releases.append(item)
    except Exception as e:
        print("Gemini AI classification error:", e)

print(f"AI classified {len(fresh_telegram_releases)} fresh drops from Telegram channels.")

# 4. Generate Digest with Gemini
all_fresh = fresh_taste_releases + fresh_telegram_releases

prompt_final = f"""Ты формируешь ПЯТНИЧНЫЙ РАДАР СВЕЖИХ РЕЛИЗОВ в Telegram.
Ввод содержит ТОЛЬКО СВЕЖИЕ РЕЛИЗЫ И ДРОПЫ ЭТОЙ НЕДЕЛИ.
КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать или добавлять старые треки прошлых лет!

Сформируй 2 или 3 чистые секции в Telegram Markdown:
1. 🎧 *Новое от твоих артистов* (релизы от любимых исполнителей)
2. ⚡️ *Горячие дропы этой недели (РФ и Запад)* (релизы из Телеграм-каналов)

Правила:
- Приводи прямые ссылки формата [Артист — Название](url)
- Если в секции ничего нет — просто не показывай её!
- Используй только Telegram Markdown (*bold*, [ссылка](url)).

Данные:
{json.dumps(all_fresh, ensure_ascii=False)}
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
    "text": digest_text if digest_text else "🎧 *Пятничный дайджест*\n\nНа этой неделе от ваших артистов свежих релизов не выходило.",
    "parse_mode": "Markdown",
    "disable_web_page_preview": True
}).encode('utf-8')

try:
    req = urllib.request.Request(tg_url, data=tg_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("Telegram send result:", resp.read().decode('utf-8'))
except Exception as e:
    print("Telegram send error:", e)

print("Strict 7-day Release Radar completed!")
