import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta

cutoff = datetime.now() - timedelta(days=14)
artist = 'ILLENIUM'

for country in ['US', 'RU']:
    for entity in ['album', 'song']:
        url = f'https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity={entity}&country={country}&limit=5'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f"=== {artist} ({country}/{entity}) results: {data.get('resultCount')} ===")
                for r in data.get('results', []):
                    name = r.get('collectionName') or r.get('trackName')
                    rel_date = r.get('releaseDate', '')[:10]
                    print(f" - [{rel_date}] {r.get('artistName')} — {name}")
        except Exception as e:
            print("Error:", e)
