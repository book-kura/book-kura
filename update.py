import os
import json
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
TRACKING_ID = os.environ.get("AMAZON_TRACKING_ID", "skusagi8655-22")

client = genai.Client(api_key=API_KEY)

def get_openbd_cover(isbn):
    if not isbn:
        return None
    try:
        url = f"https://api.openbd.jp/v1/get?isbn={isbn}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
            if data and data[0]:
                cover = data[0].get("summary", {}).get("cover")
                if cover:
                    return cover
    except Exception:
        pass
    return None

def search_book_cover_api(query_str):
    try:
        encoded = quote(query_str)
        gb_url = f"https://www.googleapis.com/books/v1/volumes?q={encoded}&maxResults=10"
        req = urllib.request.Request(gb_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as res:
            gb_data = json.loads(res.read().decode('utf-8'))
            items = gb_data.get("items", [])

            for item in items:
                vol = item.get("volumeInfo", {})
                image_links = vol.get("imageLinks", {})
                thumb = image_links.get("thumbnail") or image_links.get("smallThumbnail")
                if thumb:
                    return thumb.replace("http://", "https://").replace("&edge=curl", "")

            for item in items:
                vol = item.get("volumeInfo", {})
                for id_obj in vol.get("industryIdentifiers", []):
                    if id_obj.get("type") in ("ISBN_13", "ISBN_10"):
                        isbn = id_obj.get("identifier")
                        openbd_cover = get_openbd_cover(isbn)
                        if openbd_cover:
                            return openbd_cover
    except Exception:
        pass
    return None

def fetch_book_cover(title, author=""):
    clean_title = re.sub(r'[\(（【\[].*?[\)）】\]]', '', title)
    clean_title = re.sub(r'\s*\d+巻.*$', '', clean_title)
    clean_title = re.sub(r'\s*第?\d+巻.*$', '', clean_title)
    clean_title = re.sub(r'\s*\d+$', '', clean_title).strip()
    if not clean_title:
        clean_title = title

    clean_author = re.sub(r'[\(（【\[].*?[\)）】\]]', '', author).split('/')[0].split('・')[0].strip()

    if clean_author:
        cover = search_book_cover_api(f"{clean_title} {clean_author}")
        if cover:
            return cover

    cover = search_book_cover_api(f"{clean_title} コミック")
    if cover:
        return cover

    cover = search_book_cover_api(clean_title)
    if cover:
        return cover

    return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300&q=80"

prompt = """あなたは日本最大級の大型書店の敏腕バイヤー兼書評家です。
現在Kindleでセール・ポイント還元中、または話題となっている人気漫画・書籍の中から、
読者評価と話題性が極めて高い作品を【35〜40作品】厳選し、以下のJSON形式で出力してください。

【厳選・並び順ルール】
1. 出力件数：35〜40作品を出力すること。
2. ソート順（重要）：Amazonの読者レビュー評価（星4.3以上・レビュー数多数）および世間的な人気・話題性が高い順に、上から降順（人気・高評価が上）で並べること。
3. カテゴリ配分：以下の3種類にバランスよく振り分けること（各カテゴリ12〜14作品程度）。
   - "50pct"：50%以上ポイント還元、実質半額、まとめ買い高還元対象作
   - "free"：1〜3巻（またはそれ以上）無料、99円均一などの大幅割引キャンペーン作
   - "completed"：全巻完結済みの不朽の名作、アニメ化・実写化済みのイッキ読み推奨作
4. ジャンルバランス：少年・青年・少女・女性コミックを中心に、人気のビジネス書・小説・教養書も1〜2割程度織り交ぜること。
5. 見どころ
