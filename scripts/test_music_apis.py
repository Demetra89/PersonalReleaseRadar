import urllib.request
import urllib.parse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 1. Testing Deezer API ===")
artists = ['ILLENIUM', 'SALUKI', 'cold carti', 'Дора', 'Travis Scott']

for a in artists:
    try:
        url = f"https://api.deezer.com/search/album?q={urllib.parse.quote(a)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('data', [])
            print(f"Deezer ({a}): found {len(items)} albums")
            for item in items[:3]:
                art = item.get('artist', {}).get('name')
                title = item.get('title')
                print(f" - {art} — {title}")
    except Exception as e:
        print(f"Deezer Error for {a}:", e)

print("\n=== 2. Testing YTMusic API ===")
try:
    from ytmusicapi import YTMusic
    ytm = YTMusic()
    for a in artists:
        res = ytm.search(a, filter='songs')
        print(f"YTMusic ({a}): found {len(res)} songs")
        for r in res[:3]:
            art_names = ', '.join([artist['name'] for artist in r.get('artists', [])])
            print(f" - {art_names} — {r.get('title')}")
except Exception as e:
    print("YTMusic Error:", e)
