import os
import json
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from google import genai
from google.genai import types

# 環境変数からAPIキーとアソシエイトIDを取得
API_KEY = os.environ.get("GEMINI_API_KEY")
TRACKING_ID = os.environ.get("AMAZON_TRACKING_ID", "book-kura-22")

client = genai.Client(api_key=API_KEY)

def get_openbd_cover(isbn):
    """OpenBD（日本の出版書誌データベース）から公式書影URLを取得"""
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
    """Google Books APIでISBNと書影URLの両方を探し、OpenBDも併用して書影を取得"""
    try:
        encoded = quote(query_str)
        gb_url = f"https://www.googleapis.com/books/v1/volumes?q={encoded}&maxResults=10"
        req = urllib.request.Request(gb_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as res:
            gb_data = json.loads(res.read().decode('utf-8'))
            items = gb_data.get("items", [])

            # 1. まずGoogle Books自体にimageLinksがあるものを優先探索
            for item in items:
                vol = item.get("volumeInfo", {})
                image_links = vol.get("imageLinks", {})
                thumb = image_links.get("thumbnail") or image_links.get("smallThumbnail")
                if thumb:
                    return thumb.replace("http://", "https://").replace("&edge=curl", "")

            # 2. Google Booksに画像がない場合、取得できたISBNを使ってOpenBDから日本の公式書影を引く
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
    """作品名・著者名から本物の表紙画像URLを取得する"""
    # 括弧書き、巻数表記、Kindle表記を削除してベースの作品名を抽出
    clean_title = re.sub(r'[\(（【\[].*?[\)）】\]]', '', title)
    clean_title = re.sub(r'\s*\d+巻.*$', '', clean_title)
    clean_title = re.sub(r'\s*第?\d+巻.*$', '', clean_title)
    clean_title = re.sub(r'\s*\d+$', '', clean_title).strip()
    if not clean_title:
        clean_title = title

    clean_author = re.sub(r'[\(（【\[].*?[\)）】\]]', '', author).split('/')[0].split('・')[0].strip()

    # パターン1：作品名 ＋ 著者名（コミック指定なし・広め検索）
    if clean_author:
        cover = search_book_cover_api(f"{clean_title} {clean_author}")
        if cover:
            return cover, True

    # パターン2：作品名 ＋ コミック（単行本版ヒット狙い）
    cover = search_book_cover_api(f"{clean_title} コミック")
    if cover:
        return cover, True

    # パターン3：作品名のみ
    cover = search_book_cover_api(clean_title)
    if cover:
        return cover, True

    # 見つからない場合のみフォールバック
    return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300&q=80", False

prompt = """
あなたは日本最大級の大型書店の敏腕バイヤー兼書評家です。
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
5. 見どころ（highlight）：書店の手書きPOPのように「なぜ今読むべきか」を35〜50文字程度で簡潔にまとめること。

【出力JSONフォーマット】
{
  "items": [
    {
      "title": "作品名（巻数表記がある場合はそれも記載）",
      "author": "著者名",
      "category": "50pct" または "free" または "completed",
      "badge": "50%還元" や "1-3巻無料" などの短いバッジ表記,
      "badge_color": "bg-amber-600"（還元）または "bg-emerald-600"（無料）または "bg-indigo-600"（完結）,
      "tags": "#青年コミック #アニメ化 など",
      "sale_price": "実質 ○○円 または 無料 または ○○円",
      "original_price": "定価表記（あれば。不明なら空文字）",
      "search_query": "Amazon検索用キーワード（例: キングダム 1巻 Kindle）",
      "highlight": "35〜50文字の書店POP風おすすめコメント"
    }
  ]
}
"""

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=8192,
            temperature=0.7,
        ),
    )
    
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    data = json.loads(text)
    items = data.get("items", [])
    hit_count = 0

    # 各作品にAmazonアソシエイトURLと本物の表紙画像URLを付与
    for item in items:
        query = item.get("search_query", item["title"])
        encoded_query = quote(query)
        item["url"] = f"[https://www.amazon.co.jp/s?k=](https://www.amazon.co.jp/s?k=){encoded_query}&i=digital-text&tag={TRACKING_ID}"
        
        cover_url, is_hit = fetch_book_cover(item["title"], item.get("author", ""))
        item["image_url"] = cover_url
        if is_hit:
            hit_count += 1
        time.sleep(0.25)

    # 更新日時をJST（日本時間）で記録
    JST = timezone(timedelta(hours=+9), 'JST')
    now = datetime.now(JST)
    data["updated_at"] = now.strftime("%Y/%m/%d %H:%M")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"data.json generated: {len(items)} items (Real covers found: {hit_count}/{len(items)})")

except Exception as e:
    print(f"Error occurred: {e}")
    raise e
