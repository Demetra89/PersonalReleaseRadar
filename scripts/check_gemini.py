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

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    for m in data.get('models', []):
        if 'flash' in m['name']:
            print(m['name'])

# Test generating content with gemini-2.5-flash
test_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
test_body = json.dumps({"contents": [{"parts": [{"text": "Привет! Ответь одним словом: Работает!"}]}]}).encode('utf-8')

try:
    req = urllib.request.Request(test_url, data=test_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("Gemini Test Response:", res['candidates'][0]['content']['parts'][0]['text'])
except Exception as e:
    print("Gemini Test Error:", e)
