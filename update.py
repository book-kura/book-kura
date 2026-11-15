import os, json, re, random
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
TAG = os.environ.get("AMAZON_TRACKING_ID", "skusagi8655-22")
client = genai.Client(api_key=API_KEY)

def make_cover_svg(title, author, category):
  palette = {
    "50pct": ("#FEF3C7", "#92400E", "#D97706"),
    "free": ("#D1FAE5", "#065F46", "#059669"),
    "completed": ("#E0E7FF", "#3730A3", "#4F46E5"),
  }
  bg, fg, accent = palette.get(category, ("#F5F5F4", "#292524", "#78716C"))
  t = re.sub(r"[&<>\"']", "", title)
  a = re.sub(r"[&<>\"']", "", author)[:14]
  lines = [t[i:i+9] for i in range(0, min(len(t), 27), 9)]
  tspans = "".join(
    f'<tspan x="100" dy="{24 if i else 0}">{ln}</tspan>'
    for i, ln in enumerate(lines)
  )
  svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="284" viewBox="0 0 200 284">'
    f'<rect width="200" height="284" fill="{bg}"/>'
    f'<rect x="12" y="12" width="176" height="260" fill="none" stroke="{accent}" stroke-width="2" rx="4"/>'
    f'<rect x="0" y="0" width="10" height="284" fill="{accent}" opacity="0.25"/>'
    f'<text x="100" y="105" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="16" fill="{fg}">{tspans}</text>'
    f'<line x1="50" y1="195" x2="150" y2="195" stroke="{accent}" stroke-width="1"/>'
    f'<text x="100" y="220" text-anchor="middle" font-family="sans-serif" font-size="11" fill="{fg}" opacity="0.85">{a}</text>'
    f'<text x="100" y="255" text-anchor="middle" font-family="sans-serif" font-size="9" fill="{accent}" font-weight="bold">MANGA KURA</text>'
    f'</svg>'
  )
  return "data:image/svg+xml;utf8," + quote(svg)

themes = [
  "社会派サスペンス・裏社会・頭脳戦の傑作を厚めに",
  "大人向けの静かなヒューマンドラマ・日常・グルメ名作を厚めに",
  "マンガ大賞・このマンガがすごい！上位の通好み話題作を中心に",
  "SF・歴史・知的好奇心をくすぐる骨太コミックを中心に",
  "全5〜15巻程度で週末にイッキ読みできる隠れた完結名作を多めに"
]
today_theme = random.choice(themes)

with open("prompt.txt", "r", encoding="utf-8") as f:
  prompt = f.read().replace("{today_theme}", today_theme)

cfg = types.GenerateContentConfig(response_mime_type="application/json", max_output_tokens=32768, temperature=0.95)
res = client.models.generate_content(model="gemini-3.8-flash", contents=prompt, config=cfg)

txt = res.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
data = json.loads(txt)
items = data.get("items", [])
if not items:
  raise ValueError("Empty")

for it in items:
  q = quote(it.get("search_query", it["title"]))
  it["url"] = "[https://www.amazon.co.jp/s?k=](https://www.amazon.co.jp/s?k=)" + q + "&i=digital-text&tag=" + TAG
  it["image_url"] = make_cover_svg(it["title"], it.get("author", ""), it.get("category", ""))

data["updated_at"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M")
with open("data.json", "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)

print("Done:", len(items), "Theme:", today_theme)
