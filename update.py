import os, json, re, time, urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
TRACKING_ID = os.environ.get("AMAZON_TRACKING_ID", "skusagi8655-22")
client = genai.Client(api_key=API_KEY)

def get_openbd_cover(isbn):
  if not isbn: return None
  try:
    req = urllib.request.Request("https://api.openbd.jp/v1/get?isbn=" + str(isbn), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as res:
      data = json.loads(res.read().decode("utf-8"))
      if data and data[0]: return data[0].get("summary", {}).get("cover")
  except Exception: return None
  return None

def search_book_cover_api(query_str):
  try:
    gb_url = "https://www.googleapis.com/books/v1/volumes?q=" + quote(query_str) + "&maxResults=10"
    req = urllib.request.Request(gb_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=6) as res:
      items = json.loads(res.read().decode("utf-8")).get("items", [])
      for item in items:
        links = item.get("volumeInfo", {}).get("imageLinks", {})
        thumb = links.get("thumbnail") or links.get("smallThumbnail")
        if thumb: return thumb.replace("http://", "https://").replace("&edge=curl", "")
      for item in items:
        for id_obj in item.get("volumeInfo", {}).get("industryIdentifiers", []):
          if id_obj.get("type") in ("ISBN_13", "ISBN_10"):
            cover = get_openbd_cover(id_obj.get("identifier"))
            if cover: return cover
  except Exception: return None
  return None

def fetch_book_cover(title, author=""):
  t = re.sub(r"[\(（【\[].*?[\)）】\]]", "", title)
  t = re.sub(r"\s*第?\d+巻.*$", "", t)
  t = re.sub(r"\s*\d+$", "", t).strip() or title
  a = re.sub(r"[\(（【\[].*?[\)）】\]]", "", author).split("/")[0].split("・")[0].strip()
  if a:
    c = search_book_cover_api(t + " " + a)
    if c: return c
  c = search_book_cover_api(t + " コミック")
  if c: return c
  c = search_book_cover_api(t)
  if c: return c
  return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300&q=80"

prompt = "あなたは日本の大型書店の敏腕バイヤーです。現在Kindleでセール・ポイント還元中、または話題の人気漫画・書籍から、評価と話題性が高い35〜40作品を厳選し、JSON形式で出力してください。人気・高評価順に上から並べること。カテゴリは '50pct'（50%以上還元）、'free'（1〜3巻無料・激安）、'completed'（全巻完結・名作）の3種類に均等に振り分けること。出力JSON形式: {\"items\": [{\"title\": \"作品名\", \"author\": \"著者名\", \"category\": \"50pct または free または completed\", \"badge\": \"50%還元 などの短い表記\", \"badge_color\": \"bg-amber-600 または bg-emerald-600 または bg-indigo-600\", \"tags\": \"#青年コミック など\", \"sale_price\": \"実質 ○○円 または 無料\", \"original_price\": \"定価（不明なら空文字）\", \"search_query\": \"Amazon検索キーワード\", \"highlight\": \"35〜50文字の書店POP風おすすめコメント\"}]}"

config = types.GenerateContentConfig(response_mime_type="application/json", max_output_tokens=8192, temperature=0.7)
response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt, config=config)

text = response.text.strip()
if text.startswith("```json"): text = text[7:]
if text.startswith("```"): text = text[3:]
if text.endswith("```"): text = text[:-3]

data = json.loads(text.strip())
items = data.get("items", [])
if not items: raise ValueError("Empty items")

for item in items:
  q = quote(item.get("search_query", item["title"]))
  item["url"] = "[https://www.amazon.co.jp/s?k=](https://www.amazon.co.jp/s?k=)" + q + "&i=digital-text&tag=" + TRACKING_ID
  item["image_url"] = fetch_book_cover(item["title"], item.get("author", ""))
  time.sleep(0.2)

JST = timezone(timedelta(hours=9))
data["updated_at"] = datetime.now(JST).strftime("%Y/%m/%d %H:%M")

with open("data.json", "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)

print("Success:", len(items))
