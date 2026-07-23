import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

print("Starting Snippets & Upcoming Drops Radar Pipeline...")

channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm']
tg_posts = []

for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:15]:
                title = item.find('title').text if item.find('title') is not None else ''
                desc = item.find('description').text if item.find('description') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                import re
                clean_desc = re.sub(r'<[^>]+>', ' ', desc)
                tg_posts.append({
                    'channel': ch,
                    'title': title,
                    'text': (title + " " + clean_desc)[:300],
                    'link': link
                })
    except Exception as e:
        pass

print(f"Collected {len(tg_posts)} Telegram posts for Snippets classification...")

# Ask Gemini AI to filter snippets, teasers, leaks & upcoming Friday drops
prompt_classify = f"""Ты — классификатор музыкальных анонсов и сниппетов.
Тебе даны посты из музыкальных телеграм-каналов (cloudeluxe, USANEWRAP, rhymesm).
Выдели ТОЛЬКО ТЕ ПОСТЫ, где содержатся:
- СНИППЕТЫ (отрывки невышедших треков/видео)
- АНОНСЫ (объявления даты выхода трека/альбома в эту или следующую пятницу)
- ТИЗЕРЫ или СЛИВЫ предстоящих релизов.

Игнорируй уже вышедшие релизы, мемы, драмы, вопросы к подписчикам, рекламу.

Верни JSON-массив объектов:
[
  {{
    "artist": "Имя артиста",
    "title": "Название трека/альбома или суть сниппета",
    "type": "snippet или announcement или leak",
    "details": "короткая суть анонса или когда обещают дроп",
    "url": "ссылка на пост"
  }}
]

Посты:
{json.dumps(tg_posts, ensure_ascii=False)}
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
classified_snippets = []

try:
    gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt_classify}]}]}).encode('utf-8')
    req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        ai_text = res['candidates'][0]['content']['parts'][0]['text'].strip()
        if '```' in ai_text:
            ai_text = ai_text.split('```')[1].replace('json', '').strip()
        classified_snippets = json.loads(ai_text)
except Exception as e:
    print("Gemini AI classification error:", e)

print(f"AI classified {len(classified_snippets)} snippets & upcoming drops.")

# Generate Digest
prompt_digest = f"""Ты составляешь дайджест СНИППЕТОВ И АНОНСОВ перед пятничными дропами в Telegram.
Заголовок: 🔮 *Сниппеты & Ожидаемые дропы к Пятнице*

Раздели на 2 секции:
1. 🎬 *Сниппеты и тизеры*
2. 🗓 *Анонсы релизов к пятнице*

Правила:
- Делай прямые ссылки на посты вида [Артист — Название/Сниппет](url)
- Коротко (1 фраза) поясни суть сниппета или дату ожидания дропа
- Если в одной из секций ничего нет — просто не показывай её!
- Используй только Telegram Markdown (*bold*, [ссылка](url)).

Данные:
{json.dumps(classified_snippets, ensure_ascii=False)}
"""

digest_text = ""
try:
    gemini_body = json.dumps({"contents": [{"parts": [{"text": prompt_digest}]}]}).encode('utf-8')
    req = urllib.request.Request(gemini_url, data=gemini_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        digest_text = res['candidates'][0]['content']['parts'][0]['text']
except Exception as e:
    print("Gemini Digest Error:", e)

# Send to Telegram
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
tg_body = json.dumps({
    "chat_id": TELEGRAM_CHAT_ID,
    "text": digest_text if digest_text else "🔮 *Сниппеты & Анонсы*\n\nНа этой неделе пока новых сниппетов не выходило.",
    "parse_mode": "Markdown",
    "disable_web_page_preview": True
}).encode('utf-8')

try:
    req = urllib.request.Request(tg_url, data=tg_body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("Telegram send result:", resp.read().decode('utf-8'))
except Exception as e:
    print("Telegram send error:", e)

print("Snippets pipeline completed!")
