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

def fetch_book_cover(title, author=""):
    """Google Books API と OpenBD から本物の表紙画像URLを取得する"""
    # 検索ノイズを減らすため「(1)」「1巻」「Kindle版」などの巻数・括弧表記を除去
    clean_title = re.sub(r'[\(（【\[].*?[\)）】\]]', '', title)
    clean_title = re.sub(r'\s*\d+巻.*$', '', clean_title).strip()
    if not clean_title:
        clean_title = title

    # 1. Google Books API で検索（書影のヒット率が非常に高い）
    try:
        query = quote(f"intitle:{clean_title}")
        gb_url = f"https://www.googleapis.com/books/v1/volumes?q={query}&langRestrict=ja&maxResults=5"
        req = urllib.request.Request(gb_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as res:
            gb_data = json.loads(res.read().decode('utf-8'))
            for item in gb_data.get("items", []):
                image_links = item.get("volumeInfo", {}).get("imageLinks", {})
                thumb = image_links.get("thumbnail") or image_links.get("smallThumbnail")
                if thumb:
                    # httpをhttpsに変換し、ズームパラメータを調整して画質を安定化
                    thumb = thumb.replace("http://", "https://").replace("&edge=curl", "")
                    return thumb
    except Exception:
        pass

    # 2. 見つからない場合はフォールバック（代官山蔦屋風の落ち着いた本の画像）
    return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300&q=80"

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

    # 各作品にAmazonアソシエイトURLと本物の表紙画像URLを付与
    for item in data.get("items", []):
        query = item.get("search_query", item["title"])
        encoded_query = quote(query)
        item["url"] = f"[https://www.amazon.co.jp/s?k=](https://www.amazon.co.jp/s?k=){encoded_query}&i=digital-text&tag={TRACKING_ID}"
        
        # 表紙画像を自動検索してセット（API負荷軽減のため0.2秒間隔）
        item["image_url"] = fetch_book_cover(item["title"], item.get("author", ""))
        time.sleep(0.2)

    # 更新日時をJST（日本時間）で記録
    JST = timezone(timedelta(hours=+9), 'JST')
    now = datetime.now(JST)
    data["updated_at"] = now.strftime("%Y/%m/%d %H:%M")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"data.json successfully generated with {len(data.get('items', []))} items!")

except Exception as e:
    print(f"Error occurred: {e}")
    raise e
