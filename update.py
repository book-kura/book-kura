import os, json, re, time, urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
TRACKING_ID = os.environ.get("AMAZON_TRACKING_ID", "skusagi8655-22")
client = genai.Client(api_key=API_KEY)

def check_image_exists(url):
  if not url: return False
  try:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=4) as res:
      return res.status == 200 and int(res.headers.get("Content-Length", 1000)) > 500
  except Exception: return False

def get_cover_by_isbn(isbn):
  if not isbn: return None
  isbn = re.sub(r"[^0-9X]", "", str(isbn))
  # 1. 国立国会図書館サーチ書影API（日本のコミック表紙に非常に強い）
  if len(isbn) == 13:
    ndl_url = "https://ndlsearch.ndl.go.jp/thumbnail/" + isbn + ".jpg"
    if check_image_exists(ndl_url): return ndl_url
    hanmoto_url = "https://www.hanmoto.com/bd/img/" + isbn + ".jpg"
    if check_image_exists(hanmoto_url): return hanmoto_url
  # 2. OpenBD
  try:
    req = urllib.request.Request("https://api.openbd.jp/v1/get?isbn=" + isbn, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=4) as res:
      data = json.loads(res.read().decode("utf-8"))
      if data and data[0]:
        cover = data[0].get("summary", {}).get("cover")
        if cover: return cover
  except Exception: pass
  return None

def search_book_cover_api(query_str):
  try:
    gb_url = "https://www.googleapis.com/books/v1/volumes?q=" + quote(query_str) + "&maxResults=10&country=JP"
    req = urllib.request.Request(gb_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=6) as res:
      items = json.loads(res.read().decode("utf-8")).get("items", [])
      # まずISBNから日本の公式書影（NDL・版元・OpenBD）を探す
      for item in items:
        for id_obj in item.get("volumeInfo", {}).get("industryIdentifiers", []):
          if id_obj.get("type") == "ISBN_13":
            cover = get_cover_by_isbn(id_obj.get("identifier"))
            if cover: return cover
      # 次にGoogle Books自身のサムネイルを確認
      for item in items:
        links = item.get("volumeInfo", {}).get("imageLinks", {})
        thumb = links.get("thumbnail") or links.get("
