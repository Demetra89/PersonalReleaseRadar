import urllib.request
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime, timedelta

channels = ['cloudeluxe', 'theflow', 'USANEWRAP', 'rhymesm']

print("Fetching fresh posts from Telegram music channels...")

posts = []

for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            print(f"Channel @{ch}: found {len(items)} posts.")
            for item in items[:10]:
                title = item.find('title').text if item.find('title') is not None else ''
                desc = item.find('description').text if item.find('description') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
                posts.append({
                    'channel': ch,
                    'title': title,
                    'desc': desc[:300],
                    'link': link,
                    'pub_date': pub_date
                })
    except Exception as e:
        print(f"Error fetching @{ch}:", e)

print(f"\nTotal Telegram posts collected: {len(posts)}")
for p in posts[:5]:
    print(f"[{p['channel']}] {p['title']} ({p['link']})")
