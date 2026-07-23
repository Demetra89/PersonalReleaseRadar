import urllib.request
import xml.etree.ElementTree as ET
import re

url = 'http://144.31.148.133/telegram/channel/USANEWRAP'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    root = ET.fromstring(resp.read().decode('utf-8'))
    for item in root.findall('.//item'):
        if '8054' in item.find('link').text:
            desc = item.find('description').text
            clean = re.sub(r'<[^>]+>', '\n', desc)
            print("=== FRIDAY RELEASES POST 8054 ===")
            print(clean)
