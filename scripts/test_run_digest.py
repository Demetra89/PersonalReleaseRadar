import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

print("Starting test run of Friday Release Radar Pipeline...")

# 1. Fetch artists from Postgres
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
artists = [line.strip() for line in artists_output.split('\n') if line.strip()]
print(f"Loaded {len(artists)} artists from database.")

# 2. Check iTunes API for new releases (last 14 days for testing)
new_releases = []
seven_days_ago = datetime.now() - timedelta(days=14)

for artist in artists[:20]:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&limit=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for album in results:
                rel_date_str = album.get('releaseDate')
                if rel_date_str:
                    rel_date = datetime.strptime(rel_date_str.split('T')[0], '%Y-%m-%d')
                    if rel_date >= seven_days_ago:
                        new_releases.append({
                            'artist': album.get('artistName'),
                            'title': album.get('collectionName'),
                            'release_type': 'album' if album.get('collectionType') == 'Album' else 'single',
                            'source': 'taste',
                            'url': album.get('collectionViewUrl'),
                            'match_reason': 'Из вашего списка любимых артистов'
                        })
    except Exception as e:
        pass

print(f"Found {len(new_releases)} releases from iTunes API.")

# 3. Format final message with Gemini
prompt = f"""Ты собираешь для меня пятничный дайджест новой музыки в Telegram.
На вход дают JSON со списком релизов, у каждого элемента есть:
artist, title, release_type, source (taste / ru_cloud / us_rap), url (если есть), match_reason.

Правила:
- Раздели вывод на секции по source с понятными заголовками: "🎧 Новое от твоих артистов", "☁️ RU cloud/андеграунд", "🇺🇸 US рэп"
- В секции "твои артисты" коротко (1 фраза) укажи, почему это может зайти, используя match_reason
- Формат — Markdown для Telegram (используй *bold*, не используй заголовки H1/H2)
- Максимум 15 релизов в сообщении

Данные:
{json.dumps(new_releases, ensure_ascii=False)}
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')

digest_text = ""
try:
    req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        digest_text = res['candidates'][0]['content']['parts'][0]['text']
except Exception as e:
    print("Gemini API error:", e)
    digest_text = "🎧 *Пятничный дайджест*\n\nНа этой неделе новых релизов не нашлось."

# 4. Send to Telegram
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

print("Test run completed!")
