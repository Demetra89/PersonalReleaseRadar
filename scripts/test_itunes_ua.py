import urllib.request
import urllib.parse
import json

artists_to_test = ['ILLENIUM', 'Travis Scott', '21 Savage', 'Juice WRLD', 'cold carti']

for artist in artists_to_test:
    url = f'https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&entity=song&limit=10'
    req = urllib.request.Request(url, headers={'User-Agent': 'iTunes/12.9.5 (Windows; N)'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"=== iTunes Search ({artist}): {data.get('resultCount')} ===")
            for r in data.get('results', []):
                print(f" - [{r.get('releaseDate', '')[:10]}] {r.get('artistName')} — {r.get('trackName')}")
    except Exception as e:
        print(f"Error for {artist}:", e)
