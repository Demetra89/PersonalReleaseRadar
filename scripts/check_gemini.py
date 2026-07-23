import os
import json
import urllib.request

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

for model in ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash"]:
    test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    test_body = json.dumps({"contents": [{"parts": [{"text": "Привет! Напиши 'Работает'"}]}]}).encode('utf-8')
    try:
        req = urllib.request.Request(test_url, data=test_body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            print(f"[{model}] SUCCESS:", res['candidates'][0]['content']['parts'][0]['text'].strip())
            break
    except Exception as e:
        print(f"[{model}] ERROR:", e)
