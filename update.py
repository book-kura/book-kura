import os, json, re, time, urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
TAG = os.environ.get("AMAZON_TRACKING_ID", "skusagi8655-22")
client = genai.Client(api_key=API_KEY)

def ok_img(u):
  try:
    r = urllib.request.Request(u, method="HEAD")
    with urllib.request.urlopen(r, timeout=4) as res:
      return res.status == 200 and int(res.headers.get("Content-Length", 999)) > 500
  except Exception:
    return False

def get_cover(title, author=""):
  t = re.sub(r"[\(（【\[].*?[\)）】\]]", "", title)
  t = re.sub(r"\s*第?\d+巻.*$", "", t).strip() or title
  a = re.sub(r"[\(（【\[].*?[\)）】\]]", "", author).split("/")[0].strip()
  for q in [t + " 1 " + a, t + " " + a, t]:
    try:
      u = "https://www.googleapis.com/books/v1/volumes?q=" + quote(q) + "&maxResults=8&country=JP"
      with urllib.request.urlopen(u, timeout=6) as res:
        items = json.loads(res.read().decode("utf-8")).get("items", [])
      for it in items:
        for id_o in it.get("volumeInfo", {}).get("industryIdentifiers", []):
          if id_o.get("type") == "ISBN_13":
            isbn = id_o.get("identifier", "")
            for base in ["https://ndlsearch.ndl.go.jp/thumbnail/", "https://www.hanmoto.com/bd/img/"]:
              if ok_img(base + isbn + ".jpg"):
                return base + isbn + ".jpg"
      for it in items:
        lk = it.get("volumeInfo", {}).get("imageLinks", {})
        th = lk.get("thumbnail") or lk.get("smallThumbnail")
        if th:
          return th.replace("http://", "https://").replace("&edge=curl", "")
    except Exception:
      pass
  return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300&q=80"

p = "日本の人気漫画・書籍のKindleセール・高還元・完結名作を35作品厳選しJSONで出力。人気評価順に並べること。カテゴリは50pct,free,completedの3種。形式:{\"items\":[{\"title\":\"作品名\",\"author\":\"著者\",\"category\":\"50pct|free|completed\",\"badge\":\"50%還元等\",\"badge_color\":\"bg-amber-600|bg-emerald-600|bg-indigo-600\",\"tags\":\"#タグ\",\"sale_price\":\"実質○○円|無料\",\"original_price\":\"定価\",\"search_query\":\"検索語\",\"highlight\":\"40字前後のPOP文\"}]}"

cfg = types.GenerateContentConfig(response_mime_type="application/json", max_output_tokens=8192, temperature=0.7)
res = client.models.generate_content(model="gemini-3.8-flash", contents=p, config=cfg)

txt = res.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
data = json.loads(txt)
items = data.get("items", [])
if not items:
  raise ValueError("Empty")

for it in items:
  q = quote(it.get("search_query", it["title"]))
  it["url"] = "[https://www.amazon.co.jp/s?k=](https://www.amazon.co.jp/s?k=)" + q + "&i=digital-text&tag=" + TAG
  it["image_url"] = get_cover(it["title"], it.get("author", ""))
  time.sleep(0.15)

data["updated_at"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M")
with open("data.json", "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)

print("Done:", len(items))
