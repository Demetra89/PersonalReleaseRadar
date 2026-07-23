import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
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

print("Starting Full Friday Release Radar Pipeline...")

# 1. Fetch ALL 83 favorite artists from Postgres database
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
favorite_artists = set(line.strip().lower() for line in artists_output.split('\n') if line.strip())
print(f"Loaded ALL {len(favorite_artists)} favorite artists from database.")

channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm', 'theflow']
all_parsed_drops = []

# 2. Parse full post text from Telegram channels
for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:15]:
                desc = item.find('description').text if item.find('description') is not None else ''
                clean = re.sub(r'<[^>]+>', '\n', desc)
                # Parse lines with bullet points or dashes
                for line in clean.split('\n'):
                    line = line.strip()
                    if line.startswith('•') or line.startswith('-') or line.startswith('—'):
                        cleaned_line = line.lstrip('•—-* ').strip()
                        if '—' in cleaned_line or '-' in cleaned_line:
                            parts = re.split(r'\s+[—\-]\s+', cleaned_line, 1)
                            if len(parts) == 2:
                                art_name = parts[0].strip()
                                trk_name = parts[1].replace('«', '').replace('»', '').replace('"', '').strip()
                                if len(art_name) > 1 and len(trk_name) > 1:
                                    all_parsed_drops.append({
                                        'artist': art_name,
                                        'title': trk_name
                                    })
    except Exception as e:
        pass

# Also check iTunes Search API for favorite artists (last 14 days)
date_cutoff = datetime.now() - timedelta(days=14)
for artist in list(favorite_artists)[:30]:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&country=RU&limit=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for album in data.get('results', []):
                rel_date_str = album.get('releaseDate')
                if rel_date_str:
                    rel_date = datetime.strptime(rel_date_str.split('T')[0], '%Y-%m-%d')
                    if rel_date >= date_cutoff:
                        all_parsed_drops.append({
                            'artist': album.get('artistName'),
                            'title': album.get('collectionName')
                        })
    except Exception as e:
        pass

# Deduplicate all drops
dedup_drops = {}
for d in all_parsed_drops:
    key = f"{d['artist'].lower()}_{d['title'].lower()}"
    if key not in dedup_drops:
        search_q = urllib.parse.quote(f"{d['artist']} {d['title']}")
        d['url'] = f"https://open.spotify.com/search/{search_q}"
        dedup_drops[key] = d

unique_drops = list(dedup_drops.values())
print(f"Total unique drops gathered: {len(unique_drops)}")

# 3. Categorize drops strictly: FAVORITES vs GENERAL
taste_list = []
general_list = []

for drop in unique_drops:
    art_lower = drop['artist'].lower()
    is_fav = False
    for fav in favorite_artists:
        if fav in art_lower or art_lower in fav:
            is_fav = True
            break
    if is_fav:
        taste_list.append(drop)
    else:
        general_list.append(drop)

print(f"Favorites drops found: {len(taste_list)} | General drops found: {len(general_list)}")

# 4. Format final message with Gemini
prompt = f"""Ты формируешь ПЯТНИЧНЫЙ МУЗЫКАЛЬНЫЙ РАДАР РЕЛИЗОВ в Telegram.
Твоя цель — сформировать ПОЛНЫЙ, НАСЫЩЕННЫЙ ДАЙДЖЕСТ (20-30 позиций).

Сформируй 2 БОЛЬШИХ РАЗДЕЛА:
1. 🎧 *Твои любимые артисты* (помести СТРОГО ВСЕ релизы из списка taste_drops: SALUKI, Дора & Toxi$, GONE.Fludd, VILLIAN, midwxst и т.д.)
2. ⚡️ *Горячие новинки недели (РФ и Запад)* (помести ВСЕ релизы из списка general_drops: ЛСП, SODA LUV, вышел покурить, Мэйби Бэйби, MAYOT, Rico Nasty и т.д.)

ПРАВИЛА ОФОРМЛЕНИЯ ССЫЛОК:
- Каждая строка: • [{drop['artist']} — {drop['title']}](url)
- Запрещено менять ссылки url из входных данных!
- Выведи ВСЕ переданные релизы, не вычеркивай и не сокращай список!
- Формат — только чистый Telegram Markdown (*bold*, [ссылка](url)).

Данные:
Любимые артисты (taste_drops): {json.dumps(taste_list, ensure_ascii=False)}
Общие новинки (general_drops): {json.dumps(general_list[:20], ensure_ascii=False)}
"""

digest_text = ""
try:
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')
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

print("Full 20-30 drops pipeline completed!")
