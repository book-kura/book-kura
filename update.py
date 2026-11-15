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
        url = "https://api.openbd.jp/v1/get?isbn=" + str(isbn)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
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
        gb_url = "https://www.googleapis.com/books/v1/volumes?q=" + encoded + "&maxResults=10"
        req = urllib.request.Request(gb_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as res:
            gb_data = json.loads(res.read().decode("utf-8"))
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
                        
