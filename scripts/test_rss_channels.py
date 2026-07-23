import urllib.request
import xml.etree.ElementTree as ET

channels = ['cloudeluxe', 'USANEWRAP', 'rhymesm', 'theflow']

for ch in channels:
    try:
        url = f'http://144.31.148.133/telegram/channel/{ch}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            print(f"=== @{ch}: {len(items)} posts ===")
            for item in items[:15]:
                title = item.find('title').text if item.find('title') is not None else ''
                desc = item.find('description').text if item.find('description') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                print(f" - {title[:100]} | {link}")
    except Exception as e:
        print(f"Error @{ch}:", e)
