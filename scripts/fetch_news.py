#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NHK News RSS scraper and translation script using newspaper3k and Gemini API.
Runs periodically inside GitHub Actions.
"""

import json
import os
import re
import traceback
from html import unescape

import feedparser
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
import requests
from bs4 import BeautifulSoup
from newspaper import Article, Config

# Configuration
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat0.xml"
MAX_ARTICLES = 5
MIN_BODY_CHARS = 30
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "news.json")
DEFAULT_GEMINI_MODELS = (
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www3.nhk.or.jp/",
}

BOILERPLATE_MARKERS = ("受信契約", "ご利用の場合は", "受信料の未納")

# System prompt for Gemini
SYSTEM_PROMPT = """
You are an expert English-Japanese bilingual translator and language teacher.
Your task is to take a Japanese news article body text and rewrite it into a high-quality English listening lesson.
You must output ONLY a raw JSON object conforming exactly to the schema below. Do not include markdown code block formatting (such as ```json ... ```) or any other extra text.

JSON Schema:
{
  "title_ja": "Brief Japanese title representing the news",
  "summary": "A concise English summary of the news (1-2 sentences)",
  "sentences": [
    {
      "en": "A natural, standard English sentence suitable for listening practice (intermediate level, 5-10 sentences in total for the whole article)",
      "ja": "Natural Japanese translation corresponding exactly to the English sentence above"
    }
  ]
}

Guidelines:
- Rewrite the news facts accurately in English.
- Avoid overly academic or archaic words, but use natural idiomatic English suited for learning.
- Ensure the sentences flow logically like a narrated radio broadcast or podcast script.
- The list of sentences MUST have exactly a 1-to-1 correlation between "en" and "ja".
- Generate between 5 and 10 sentences total.
- If the input is only a short RSS summary, expand it into a natural listening script while staying faithful to the stated facts. Do not invent unrelated details.
"""


def load_local_env():
    """Load .env from project root for local development."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, encoding="utf-8-sig") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_gemini_model_names():
    preferred = os.environ.get("GEMINI_MODEL", "").strip()
    if preferred:
        return [preferred] + [name for name in DEFAULT_GEMINI_MODELS if name != preferred]
    return list(DEFAULT_GEMINI_MODELS)


def generate_gemini_json(prompt):
    """Call Gemini with model fallback when a model name is unavailable."""
    last_error = None
    for model_name in get_gemini_model_names():
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
            )
            if model_name != get_gemini_model_names()[0]:
                print(f"  Used fallback Gemini model: {model_name}")
            return response
        except google_exceptions.NotFound as error:
            print(f"  Model '{model_name}' is not available.")
            last_error = error
    if last_error:
        raise last_error
    raise RuntimeError("No Gemini models configured.")


def generate_mock_data():
    """Generates mock data if GEMINI_API_KEY is not configured or in testing environment."""
    print("Generating mock news data...")
    mock_data = [
        {
            "url": "https://news.example.com/mock1",
            "title": "日本の桜、満開の季節を迎える",
            "title_ja": "日本の桜が満開に",
            "date": "2026-06-06",
            "summary": "Cherry blossoms are reaching full bloom in various regions across Japan, drawing crowds of visitors despite the mild weather.",
            "sentences": [
                {
                    "en": "Cherry blossoms have reached full bloom in Tokyo, attracting many visitors to local parks.",
                    "ja": "東京で桜が満開となり、多くの人が地元の公園を訪れています。",
                },
                {
                    "en": "Weather officials say this year's bloom arrived slightly earlier than average due to warmer temperatures.",
                    "ja": "気象庁によると、温暖な気候のため、今年の開花は平年より少し早かったということです。",
                },
                {
                    "en": "Many families and tourists are enjoying outdoor picnics under the beautiful pink flowers.",
                    "ja": "多くの家族連れや観光客が、美しいピンクの桜の下でピクニックを楽しんでいます。",
                },
                {
                    "en": "Local authorities are reminding visitors to clean up their trash to keep the parks clean.",
                    "ja": "地元自治体は、公園を綺麗に保つため、ゴミを持ち帰るよう呼びかけています。",
                },
                {
                    "en": "The viewing season is expected to last for another week if the weather remains stable.",
                    "ja": "天気が安定していれば、花見シーズンはあと1週間ほど続く見込みです。",
                },
            ],
        },
        {
            "url": "https://news.example.com/mock2",
            "title": "宇宙ステーションに新型ロボットが到着",
            "title_ja": "宇宙ステーションに新型ロボット到着",
            "date": "2026-06-05",
            "summary": "A new autonomous assistant robot has successfully docked at the International Space Station to help astronauts with daily maintenance.",
            "sentences": [
                {
                    "en": "A next-generation robotic assistant has successfully arrived at the International Space Station.",
                    "ja": "次世代のアシスタントロボットが、国際宇宙ステーションに無事到着しました。",
                },
                {
                    "en": "The autonomous machine was launched last week from a spaceport in southern Japan.",
                    "ja": "この自律型ロボットは、先週日本南部の宇宙基地から打ち上げられました。",
                },
                {
                    "en": "It is designed to perform routine maintenance tasks, reducing the workload of human astronauts.",
                    "ja": "宇宙飛行士の負担を軽減するため、日常のメンテナンス作業を自動で行うよう設計されています。",
                },
                {
                    "en": "Researchers hope this technology will pave the way for fully automated deep space missions in the future.",
                    "ja": "研究者らは、この技術が将来の完全自動ディープスペース探査への道を開くことを期待しています。",
                },
            ],
        },
    ]
    return mock_data


def clean_html_text(text):
    return unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def is_boilerplate(text):
    return any(marker in text for marker in BOILERPLATE_MARKERS)


def extract_json_ld_description(html):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if data.get("@type") != "NewsArticle":
            continue
        description = data.get("description", "")
        if isinstance(description, dict):
            description = description.get("@value", "")
        description = clean_html_text(description)
        if description and not is_boilerplate(description):
            return description
    return ""


def scrape_with_newspaper(url, html):
    config = Config()
    config.browser_user_agent = REQUEST_HEADERS["User-Agent"]
    config.request_timeout = 20

    article = Article(url, config=config, language="ja")
    article.download(input_html=html)
    article.parse()
    text = (article.text or "").strip()
    if text and len(text) >= MIN_BODY_CHARS and not is_boilerplate(text):
        return text
    return ""


def fetch_article_body(url, title="", rss_summary=""):
    """Fetch article text via scraping, JSON-LD, or RSS summary fallback."""
    summary_text = clean_html_text(rss_summary)

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=20, allow_redirects=True)
        if response.status_code == 200 and "/error/" not in response.url:
            body = scrape_with_newspaper(response.url, response.text)
            if body:
                print(f"  Extracted article body via HTML scrape ({len(body)} chars).")
                return body

            description = extract_json_ld_description(response.text)
            if description and len(description) >= MIN_BODY_CHARS:
                print(f"  Extracted article body via JSON-LD ({len(description)} chars).")
                return description
        else:
            print(f"  HTTP {response.status_code} while fetching article page.")
    except Exception as error:
        print(f"  Article page fetch failed: {error}")

    if summary_text:
        combined = f"{title}\n\n{summary_text}" if title else summary_text
        if len(combined.strip()) >= MIN_BODY_CHARS:
            print(f"  Using RSS summary fallback ({len(combined)} chars).")
            return combined.strip()

    return ""


def process_article(url, title, date, rss_summary):
    """Scrapes article body and generates English translation using Gemini API."""
    print(f"Fetching content from: {url}")
    try:
        body_text = fetch_article_body(url, title=title, rss_summary=rss_summary)
        if not body_text:
            print(f"Skipping {url}: No usable article text found.")
            return None

        print(f"Article text ready ({len(body_text)} chars). Generating translation via Gemini API...")

        prompt = f"{SYSTEM_PROMPT}\n\nInput Japanese News Content:\n{body_text}"
        response = generate_gemini_json(prompt)

        raw_json_str = response.text.strip()
        if raw_json_str.startswith("```"):
            lines = raw_json_str.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            raw_json_str = "\n".join(lines).strip()

        data = json.loads(raw_json_str)
        return {
            "url": url,
            "title": title,
            "title_ja": data.get("title_ja", title),
            "date": date,
            "summary": data.get("summary", ""),
            "sentences": data.get("sentences", []),
        }

    except Exception as error:
        print(f"Error processing article {url}: {error}")
        traceback.print_exc()
        return None


def load_existing_news():
    if not os.path.exists(OUTPUT_FILE):
        return []
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def main():
    load_local_env()
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("Warning: GEMINI_API_KEY not found in environment variables.")
        curated_news = generate_mock_data()
        print(f"Article fetch summary: {len(curated_news)} mock articles generated")
    else:
        print("Initializing Gemini API client...")
        genai.configure(api_key=api_key)
        model_names = get_gemini_model_names()
        print(f"Gemini models to try: {', '.join(model_names)}")

        print(f"Parsing RSS Feed: {RSS_URL}")
        feed = feedparser.parse(RSS_URL)
        entries = feed.entries
        print(f"Found {len(entries)} entries in RSS.")

        curated_news = []
        attempted = 0
        fetched = 0

        for entry in entries:
            if attempted >= MAX_ARTICLES:
                break

            attempted += 1
            url = entry.link
            title = entry.title
            date = entry.get("published", entry.get("updated", "今日"))
            rss_summary = entry.get("summary", "")

            curated_item = process_article(url, title, date, rss_summary)
            if curated_item and curated_item.get("sentences"):
                curated_news.append(curated_item)
                fetched += 1
                print(f"  ✓ Fetched article {fetched}/{MAX_ARTICLES}: {title}")

        print(f"Article fetch summary: {fetched}/{attempted} succeeded (RSS entries: {len(entries)})")

        if not curated_news:
            existing = load_existing_news()
            if existing:
                print("No new articles curated; keeping existing news.json.")
                return
            print("No articles curated and no existing data found; writing empty news.json.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(curated_news, file, ensure_ascii=False, indent=2)

    print(f"Successfully wrote {len(curated_news)} articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
