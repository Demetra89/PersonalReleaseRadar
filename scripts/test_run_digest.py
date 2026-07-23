import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import html
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

print("Starting Global Unlimited Spotify Release Radar Pipeline...")

# 1. Fetch ALL 229 favorite artists from Postgres database
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
favorite_artists = set(line.strip().lower() for line in artists_output.split('\n') if line.strip())
print(f"Loaded ALL {len(favorite_artists)} favorite artists from database.")

channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm', 'theflow']
all_parsed_drops = []

# 2. Parse full post text from Telegram channels (RU/Western drop lists)
for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:25]:
                desc = item.find('description').text if item.find('description') is not None else ''
                clean = re.sub(r'<[^>]+>', '\n', desc)
                clean = html.unescape(clean)
                for line in clean.split('\n'):
                    line = line.strip()
                    l_lower = line.lower()
                    if 'присылайте' in l_lower or 'забыли' in l_lower or 'альбомы:' in l_lower or 'синглы:' in l_lower:
                        continue
                    if line.startswith('•') or line.startswith('-') or line.startswith('—') or (len(line) > 2 and line[0].isdigit() and (line[1] == '.' or line[2] == '.')):
                        cleaned_line = re.sub(r'^[•—\-*\d.\s]+', '', line).strip()
                        if '—' in cleaned_line or '-' in cleaned_line:
                            parts = re.split(r'\s+[—\-]\s+', cleaned_line, 1)
                            if len(parts) == 2:
                                art_name = parts[0].strip()
                                trk_name = parts[1].replace('«', '').replace('»', '').replace('"', '').strip()
                                trk_name = re.sub(r'\[\d{2}\.\d{2}\.\d{4}\]', '', trk_name).strip()
                                if len(art_name) > 1 and len(trk_name) > 1 and len(art_name) + len(trk_name) < 75:
                                    all_parsed_drops.append({
                                        'artist': art_name,
                                        'title': trk_name
                                    })
    except Exception as e:
        pass

# 3. Check iTunes Search API for ALL favorite Western & RU artists (last 14 days)
date_cutoff = datetime.now() - timedelta(days=14)
for artist in list(favorite_artists):
    for country in ['US', 'RU']:
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=album&country={country}&limit=3"
            req = urllib.request.Request(url, headers={'User-Agent': 'iTunes/12.9.5 (Windows; N)'})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
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

# Deduplicate all drops & build Spotify search URLs
dedup_drops = {}
for d in all_parsed_drops:
    art_clean = html.unescape(d['artist']).strip()
    trk_clean = html.unescape(d['title']).strip()
    
    key = f"{art_clean.lower()}_{trk_clean.lower()}"
    if key not in dedup_drops:
        search_q = urllib.parse.quote(f"{art_clean} {trk_clean}")
        dedup_drops[key] = {
            'artist': art_clean,
            'title': trk_clean,
            'url': f"https://open.spotify.com/search/{search_q}"
        }

unique_drops = list(dedup_drops.values())
print(f"Total clean unique drops gathered globally: {len(unique_drops)}")

# 4. Categorize drops strictly: FAVORITES vs GENERAL
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

# 5. Build UNLIMITED Telegram Markdown message (All drops, NO cuts)
msg_lines = ["🔥 *ПЯТНИЧНЫЙ МУЗЫКАЛЬНЫЙ РАДАР РЕЛИЗОВ* 🔥\n"]

if taste_list:
    msg_lines.append("🎧 *Твои любимые артисты*\n")
    for item in taste_list:
        msg_lines.append(f"• [{item['artist']} — {item['title']}]({item['url']})")
    msg_lines.append("\n")

if general_list:
    msg_lines.append("⚡️ *Горячие новинки недели (РФ и Запад)*\n")
    for item in general_list:
        msg_lines.append(f"• [{item['artist']} — {item['title']}]({item['url']})")
    msg_lines.append("\n")

msg_lines.append("Нажмите на любой релиз, чтобы открыть его в Spotify! 🎧✨")
digest_text = "\n".join(msg_lines)

# Split message into chunks if > 4000 chars (Telegram max message limit is 4096 chars)
def send_tg_message(text):
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    tg_body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }).encode('utf-8')
    try:
        req = urllib.request.Request(tg_url, data=tg_body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("Telegram send result:", resp.read().decode('utf-8'))
    except Exception as e:
        print("Telegram send error:", e)

if len(digest_text) <= 3800:
    send_tg_message(digest_text)
else:
    # Send in clean chunks
    chunks = []
    curr = ""
    for line in digest_text.split('\n'):
        if len(curr) + len(line) + 1 > 3500:
            chunks.append(curr)
            curr = line + "\n"
        else:
            curr += line + "\n"
    if curr:
        chunks.append(curr)
    for c in chunks:
        send_tg_message(c)

print("Global Unlimited Release Radar completed!")
