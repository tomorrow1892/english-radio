#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NHK News RSS scraper and translation script using newspaper3k and Gemini API.
Runs periodically inside GitHub Actions.
"""

import json
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape

import feedparser
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
import requests
from bs4 import BeautifulSoup
from newspaper import Article, Config

# Configuration
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat0.xml"  # Legacy: kept for backward compatibility
RSS_FEEDS = {
    "main": {
        "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "max_articles": 5,
        "label": "主要ニュース"
    }
}
# "society": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat1.xml",
#         "max_articles": 5,
#         "label": "社会"
#     },
#     "culture_entertainment": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat2.xml",
#         "max_articles": 5,
#         "label": "文化・エンタメ"
#     },
#     "science_health": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat3.xml",
#         "max_articles": 5,
#         "label": "科学・医療"
#     },
#     "politics": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat4.xml",
#         "max_articles": 5,
#         "label": "政治"
#     },
#     "economy": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat5.xml",
#         "max_articles": 5,
#         "label": "経済"
#     },
#     "international": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat6.xml",
#         "max_articles": 5,
#         "label": "国際"
#     },
#     "sports": {
#         "url": "https://www3.nhk.or.jp/rss/news/cat7.xml",
#         "max_articles": 5,
#         "label": "スポーツ"
#     }
MAX_ARTICLES = 5  # Legacy: kept for backward compatibility
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

# Rate limiting: Track API calls to stay under 20 calls per minute
api_calls_in_window = []
RATE_LIMIT_CALLS = 20
RATE_LIMIT_WINDOW_SECONDS = 60

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


def rate_limit_check():
    """Check and enforce rate limit (20 calls per 60 seconds).
    If limit reached, sleep until the oldest call is outside the window.
    """
    global api_calls_in_window
    now = time.time()
    
    # Remove calls older than 60 seconds from the window
    api_calls_in_window = [call_time for call_time in api_calls_in_window 
                           if now - call_time < RATE_LIMIT_WINDOW_SECONDS]
    
    if len(api_calls_in_window) >= RATE_LIMIT_CALLS:
        # Calculate wait time until oldest call leaves the window
        oldest_call = api_calls_in_window[0]
        wait_time = RATE_LIMIT_WINDOW_SECONDS - (now - oldest_call)
        if wait_time > 0:
            print(f"\n⏳ Rate limit approaching (20/20 calls). Waiting {wait_time:.1f}s...")
            time.sleep(wait_time + 0.5)  # Add small buffer
            api_calls_in_window = []  # Reset window after waiting
    
    # Record this API call
    api_calls_in_window.append(time.time())


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

        # Check rate limit before calling Gemini API
        rate_limit_check()
        
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


def fetch_from_feed(feed_key, feed_config):
    """Fetch and process articles from a single RSS feed with parallel processing."""
    print(f"\nFetching from {feed_config['label']}: {feed_config['url']}")
    
    try:
        feed = feedparser.parse(feed_config['url'])
        entries = feed.entries
        print(f"Found {len(entries)} entries in RSS feed.")
        
        # Collect articles to process
        articles_to_process = []
        for entry in entries[:feed_config['max_articles']]:
            url = entry.link
            title = entry.title
            date = entry.get("published", entry.get("updated", "今日"))
            rss_summary = entry.get("summary", "")
            articles_to_process.append((url, title, date, rss_summary))
        
        # Process articles in parallel with ThreadPoolExecutor
        curated_articles = []
        fetched = 0
        total = len(articles_to_process)
        
        # Use max_workers=4 to limit concurrent API calls (respects rate_limit_check)
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            futures = {
                executor.submit(process_article, url, title, date, rss_summary): title
                for url, title, date, rss_summary in articles_to_process
            }
            
            # Process results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result and result.get("sentences"):
                        curated_articles.append(result)
                        fetched += 1
                        print(f"  ✓ Fetched article {fetched}/{total}: {futures[future]}")
                except Exception as e:
                    print(f"  ✗ Failed to process {futures[future]}: {e}")
        
        print(f"Feed summary for {feed_config['label']}: {fetched}/{total} succeeded")
        return curated_articles
    
    except Exception as error:
        print(f"Error fetching from {feed_config['label']}: {error}")
        traceback.print_exc()
        return []


def main():
    load_local_env()
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("Warning: GEMINI_API_KEY not found in environment variables.")
        mock_data = generate_mock_data()
        curated_output = {
            "main_news": mock_data[:1],
            "category_news": {
                "mock": mock_data[1:] if len(mock_data) > 1 else []
            }
        }
        print(f"Generated mock news with {len(mock_data)} articles")
    else:
        print("Initializing Gemini API client...")
        genai.configure(api_key=api_key)
        model_names = get_gemini_model_names()
        print(f"Gemini models to try: {', '.join(model_names)}")

        curated_output = {
            "main_news": [],
            "category_news": {}
        }
        
        # Fetch from all RSS feeds
        for feed_key, feed_config in RSS_FEEDS.items():
            articles = fetch_from_feed(feed_key, feed_config)
            
            if feed_key == "main":
                curated_output["main_news"] = articles
            else:
                # Store category news with the feed key as category name
                category_name = feed_config.get("label", feed_key)
                curated_output["category_news"][category_name] = articles
        
        # If no articles were fetched, try to keep existing data
        total_articles = len(curated_output["main_news"]) + sum(
            len(articles) for articles in curated_output["category_news"].values()
        )
        
        if total_articles == 0:
            existing = load_existing_news()
            if existing:
                print("No new articles curated; keeping existing news.json.")
                return
            print("No articles curated and no existing data found; writing empty news.json.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(curated_output, file, ensure_ascii=False, indent=2)

    total_count = len(curated_output["main_news"]) + sum(
        len(articles) for articles in curated_output["category_news"].values()
    )
    print(f"Successfully wrote {total_count} articles to {OUTPUT_FILE}")
    print(f"  Main news: {len(curated_output['main_news'])} articles")
    print(f"  Category news: {len(curated_output['category_news'])} categories")


if __name__ == "__main__":
    main()
