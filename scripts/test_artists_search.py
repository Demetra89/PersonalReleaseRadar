import urllib.request
import urllib.parse
import json

artists_to_test = ['Cold Carti', 'колд карти', 'Дора', 'Toxi$', 'SALUKI']

for a in artists_to_test:
    url = f'https://itunes.apple.com/search?term={urllib.parse.quote(a)}&entity=album&country=RU&limit=5'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"=== Query: {a} (Found {data.get('resultCount')} results) ===")
            for r in data.get('results', []):
                print(f" - [{r.get('releaseDate', '')[:10]}] {r.get('artistName')} — {r.get('collectionName')}")
    except Exception as e:
        print(f"Error for {a}:", e)
