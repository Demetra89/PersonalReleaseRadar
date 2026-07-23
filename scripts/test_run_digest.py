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

print("Starting Clean 100% Deduplicated Release Radar Pipeline...")

# 1. Fetch ALL favorite artists from Postgres database
import subprocess
artists_output = subprocess.check_output("docker exec -i $(docker ps -q -f name=postgres | head -n 1) psql -U n8n -d n8n -t -c 'SELECT name FROM artists;'", shell=True).decode('utf-8')
favorite_artists = set(line.strip().lower() for line in artists_output.split('\n') if line.strip() and len(line.strip()) > 1)
print(f"Loaded {len(favorite_artists)} clean favorite artists from database.")

channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm', 'theflow']
all_parsed_drops = []
date_cutoff = datetime.now() - timedelta(days=14)

# 2. Check Deezer API for ALL favorite artists
for artist in list(favorite_artists):
    try:
        url_art = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(artist)}"
        req_art = urllib.request.Request(url_art, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_art, timeout=2.0) as resp:
            data_art = json.loads(resp.read().decode('utf-8'))
            art_items = data_art.get('data', [])
            if art_items:
                art_id = art_items[0]['id']
                art_name = art_items[0]['name']
                
                url_alb = f"https://api.deezer.com/artist/{art_id}/albums?limit=5"
                req_alb = urllib.request.Request(url_alb, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_alb, timeout=2.0) as resp_alb:
                    data_alb = json.loads(resp_alb.read().decode('utf-8'))
                    for alb in data_alb.get('data', []):
                        rel_date_str = alb.get('release_date')
                        if rel_date_str:
                            rel_date = datetime.strptime(rel_date_str, '%Y-%m-%d')
                            if rel_date >= date_cutoff:
                                record_type = 'album' if alb.get('record_type') in ['album', 'ep', 'mup'] else 'single'
                                all_parsed_drops.append({
                                    'artist': art_name,
                                    'title': alb.get('title'),
                                    'type': record_type
                                })
    except Exception as e:
        pass

# 3. Parse full post text from Telegram channels
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
                
                current_type = 'single'
                for line in clean.split('\n'):
                    line = line.strip()
                    l_lower = line.lower()
                    if 'альбомы' in l_lower or 'ep' in l_lower:
                        current_type = 'album'
                        continue
                    if 'синглы' in l_lower:
                        current_type = 'single'
                        continue
                    if 'присылайте' in l_lower or 'забыли' in l_lower:
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
                                        'title': trk_name,
                                        'type': current_type
                                    })
    except Exception as e:
        pass

# 4. Strict Title-Based Deduplication (Merges "Mayot — Дети бетона" and "Slatt Savage & MAYOT — Дети Бетона")
dedup_drops = {}
for d in all_parsed_drops:
    art_clean = html.unescape(d['artist']).strip()
    trk_clean = html.unescape(d['title']).strip()
    
    # Clean "- Single", "- EP", "- Album"
    trk_normalized = re.sub(r'\s*-\s*(single|ep|album)$', '', trk_clean, flags=re.IGNORECASE).strip()
    
    # Key strictly by normalized title
    title_key = re.sub(r'[^a-z0-9а-я]', '', trk_normalized.lower())
    
    if title_key not in dedup_drops:
        search_q = urllib.parse.quote(f"{art_clean} {trk_normalized}")
        dedup_drops[title_key] = {
            'artist': art_clean,
            'title': trk_normalized,
            'type': d.get('type', 'single'),
            'url': f"https://open.spotify.com/search/{search_q}"
        }
    else:
        # If new item has longer/more detailed artist name (e.g. Slatt Savage & MAYOT vs Mayot), update artist
        existing = dedup_drops[title_key]
        if len(art_clean) > len(existing['artist']):
            search_q = urllib.parse.quote(f"{art_clean} {trk_normalized}")
            existing['artist'] = art_clean
            existing['url'] = f"https://open.spotify.com/search/{search_q}"

unique_drops = list(dedup_drops.values())
print(f"Total clean unique drops after strict title deduplication: {len(unique_drops)}")

# 5. Strict Artist Matching (Only favorite artists match!)
fav_albums = []
fav_singles = []
general_albums = []
general_singles = []

for drop in unique_drops:
    art_lower = drop['artist'].lower()
    artist_tokens = [t.strip() for t in re.split(r'[,&;]|\bfeat\b|\bft\b|\bwith\b', art_lower) if t.strip()]
    
    is_fav = False
    for token in artist_tokens:
        for fav in favorite_artists:
            if fav == token or (len(fav) >= 3 and fav in token):
                is_fav = True
                break
        if is_fav:
            break
            
    if is_fav:
        if drop['type'] == 'album':
            fav_albums.append(drop)
        else:
            fav_singles.append(drop)
    else:
        if drop['type'] == 'album':
            general_albums.append(drop)
        else:
            general_singles.append(drop)

print(f"Fav Albums: {len(fav_albums)} | Fav Singles: {len(fav_singles)}")
print(f"General Albums: {len(general_albums)} | General Singles: {len(general_singles)}")

# 6. Build Clean Formatted Telegram Message
msg_lines = ["🔥 *ПЯТНИЧНЫЙ МУЗЫКАЛЬНЫЙ РАДАР РЕЛИЗОВ* 🔥\n"]

if fav_albums or fav_singles:
    msg_lines.append("🎧 *Твои любимые артисты*\n")
    if fav_albums:
        msg_lines.append("💿 *Альбомы & EP:*")
        for item in fav_albums:
            msg_lines.append(f"• [{item['artist']} — {item['title']}]({item['url']})")
        msg_lines.append("")
    if fav_singles:
        msg_lines.append("🎤 *Синглы:*")
        for item in fav_singles:
            msg_lines.append(f"• [{item['artist']} — {item['title']}]({item['url']})")
        msg_lines.append("")
    msg_lines.append("\n")

if general_albums or general_singles:
    msg_lines.append("⚡️ *Горячие новинки недели (РФ и Запад)*\n")
    if general_albums:
        msg_lines.append("💿 *Альбомы & EP:*")
        for item in general_albums:
            msg_lines.append(f"• [{item['artist']} — {item['title']}]({item['url']})")
        msg_lines.append("")
    if general_singles:
        msg_lines.append("🎤 *Синглы:*")
        for item in general_singles:
            msg_lines.append(f"• [{item['artist']} — {item['title']}]({item['url']})")
        msg_lines.append("")
    msg_lines.append("\n")

msg_lines.append("Нажмите на любой релиз, чтобы открыть его в Spotify! 🎧✨")
digest_text = "\n".join(msg_lines)

# Split into chunks if needed
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

print("Clean Deduplicated Release Radar completed!")
