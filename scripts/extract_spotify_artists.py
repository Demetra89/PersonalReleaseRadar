import urllib.request
import json
import os
import sys
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

print("Fetching Spotify Web Token on VPS...")

artists = set()

try:
    token_url = 'https://open.spotify.com/get_access_token?reason=transport&productType=web_player'
    req = urllib.request.Request(token_url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        token = data.get('accessToken')
        print(f"Token received successfully! Length: {len(token) if token else 0}")
        
        if token:
            offset = 0
            while True:
                url = f'https://api.spotify.com/v1/playlists/7sLVehKGhom95tpCwTZ7H3/tracks?limit=100&offset={offset}&fields=items(track(artists(name))),next'
                req_tr = urllib.request.Request(url, headers={
                    'Authorization': f'Bearer {token}',
                    'User-Agent': 'Mozilla/5.0'
                })
                with urllib.request.urlopen(req_tr, timeout=10) as resp_tr:
                    res_tr = json.loads(resp_tr.read().decode('utf-8'))
                    items = res_tr.get('items', [])
                    if not items:
                        break
                    for it in items:
                        tr = it.get('track')
                        if tr and tr.get('artists'):
                            for a in tr['artists']:
                                name = a.get('name')
                                if name and len(name.strip()) > 0:
                                    artists.add(name.strip())
                    print(f"Processed offset {offset}, total artists so far: {len(artists)}")
                    if not res_tr.get('next'):
                        break
                    offset += 100
except Exception as e:
    print("Error fetching from Spotify Web API:", e)

sorted_artists = sorted(list(artists))
print(f"SUCCESSFULLY EXTRACTED ALL {len(sorted_artists)} UNIQUE ARTISTS FROM SPOTIFY PLAYLIST!")

if sorted_artists:
    pg_container = subprocess.check_output("docker ps -q -f name=postgres | head -n 1", shell=True).decode('utf-8').strip()
    sql_statements = []
    for artist in sorted_artists:
        escaped_name = artist.replace("'", "''")
        sql_statements.append(f"INSERT INTO artists (name, source) VALUES ('{escaped_name}', 'followed') ON CONFLICT DO NOTHING;")

    batch_sql = "\n".join(sql_statements)

    with open('/tmp/insert_artists.sql', 'w', encoding='utf-8') as f:
        f.write(batch_sql)

    subprocess.run(f"docker exec -i {pg_container} psql -U n8n -d n8n < /tmp/insert_artists.sql", shell=True)
    print("Database import complete!")

    res = subprocess.check_output(f"docker exec -i {pg_container} psql -U n8n -d n8n -c 'SELECT COUNT(*) FROM artists;'", shell=True).decode('utf-8')
    print("Total artists in Postgres database:\n", res)
