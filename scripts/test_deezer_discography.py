import urllib.request
import urllib.parse
import json
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

artists = ['ILLENIUM', 'Travis Scott', '21 Savage', 'Juice WRLD', 'cold carti', 'SALUKI', 'Дора', 'Kanye West', 'Marshmello']
date_cutoff = datetime.now() - timedelta(days=14)

print("=== DEEZER DISCOGRAPHY API TEST ===")
for a in artists:
    try:
        url_art = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(a)}"
        req_art = urllib.request.Request(url_art, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_art, timeout=4) as resp:
            data_art = json.loads(resp.read().decode('utf-8'))
            art_items = data_art.get('data', [])
            if art_items:
                art_id = art_items[0]['id']
                art_name = art_items[0]['name']
                
                url_alb = f"https://api.deezer.com/artist/{art_id}/albums?limit=10"
                req_alb = urllib.request.Request(url_alb, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_alb, timeout=4) as resp_alb:
                    data_alb = json.loads(resp_alb.read().decode('utf-8'))
                    albums = data_alb.get('data', [])
                    print(f"Deezer ({art_name} ID:{art_id}) found {len(albums)} albums")
                    for alb in albums[:5]:
                        rel_date = alb.get('release_date', '')
                        print(f" - [{rel_date}] {art_name} — {alb.get('title')}")
    except Exception as e:
        print(f"Error for {a}:", e)
