#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NHK News RSS scraper and translation script using newspaper3k and Gemini API.
Runs periodically inside GitHub Actions.
"""

import os
import sys
import json
import traceback
import feedparser
from newspaper import Article
import google.generativeai as genai

# Configuration
RSS_URL = "https://news.web.nhk/n-data/conf/na/rss/cat0.xml"
MAX_ARTICLES = 5
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "news.json")

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
"""

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
            "ja": "東京で桜が満開となり、多くの人が地元の公園を訪れています。"
          },
          {
            "en": "Weather officials say this year's bloom arrived slightly earlier than average due to warmer temperatures.",
            "ja": "気象庁によると、温暖な気候のため、今年の開花は平年より少し早かったということです。"
          },
          {
            "en": "Many families and tourists are enjoying outdoor picnics under the beautiful pink flowers.",
            "ja": "多くの家族連れや観光客が、美しいピンクの桜の下でピクニックを楽しんでいます。"
          },
          {
            "en": "Local authorities are reminding visitors to clean up their trash to keep the parks clean.",
            "ja": "地元自治体は、公園を綺麗に保つため、ゴミを持ち帰るよう呼びかけています。"
          },
          {
            "en": "The viewing season is expected to last for another week if the weather remains stable.",
            "ja": "天気が安定していれば、花見シーズンはあと1週間ほど続く見込みです。"
          }
        ]
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
            "ja": "次世代のアシスタントロボットが、国際宇宙ステーションに無事到着しました。"
          },
          {
            "en": "The autonomous machine was launched last week from a spaceport in southern Japan.",
            "ja": "この自律型ロボットは、先週日本南部の宇宙基地から打ち上げられました。"
          },
          {
            "en": "It is designed to perform routine maintenance tasks, reducing the workload of human astronauts.",
            "ja": "宇宙飛行士の負担を軽減するため、日常のメンテナンス作業を自動で行うよう設計されています。"
          },
          {
            "en": "Researchers hope this technology will pave the way for fully automated deep space missions in the future.",
            "ja": "研究者らは、この技術が将来の完全自動ディープスペース探査への道を開くことを期待しています。"
          }
        ]
      }
    ]
    return mock_data

def process_article(url, title, date, model):
    """Scrapes article body and generates English translation using Gemini API."""
    print(f"Scraping content from: {url}")
    try:
        article = Article(url, language='ja')
        article.download()
        article.parse()
        body_text = article.text
        
        if not body_text or len(body_text.strip()) < 50:
            print(f"Skipping {url}: Extracted body text is too short.")
            return None
        
        print(f"Article body fetched ({len(body_text)} chars). Generating translation via Gemini API...")
        
        prompt = f"{SYSTEM_PROMPT}\n\nInput Japanese News Content:\n{body_text}"
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        raw_json_str = response.text.strip()
        
        # Clean potential markdown output just in case
        if raw_json_str.startswith("```"):
            lines = raw_json_str.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            raw_json_str = "\n".join(lines).strip()
            
        data = json.loads(raw_json_str)
        
        # Structure final format
        curated_article = {
            "url": url,
            "title": title,
            "title_ja": data.get("title_ja", title),
            "date": date,
            "summary": data.get("summary", ""),
            "sentences": data.get("sentences", [])
        }
        return curated_article

    except Exception as e:
        print(f"Error processing article {url}: {e}")
        traceback.print_exc()
        return None

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # If no API key is provided, generate mock data and exit (facilitates local dev/testing)
    if not api_key:
        print("Warning: GEMINI_API_KEY not found in environment variables.")
        curated_news = generate_mock_data()
    else:
        print("Initializing Gemini API client...")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        print(f"Parsing RSS Feed: {RSS_URL}")
        feed = feedparser.parse(RSS_URL)
        entries = feed.entries
        print(f"Found {len(entries)} entries in RSS.")
        
        curated_news = []
        count = 0
        
        for entry in entries:
            if count >= MAX_ARTICLES:
                break
                
            url = entry.link
            title = entry.title
            date = entry.get("published", entry.get("updated", "今日"))
            
            curated_item = process_article(url, title, date, model)
            if curated_item:
                curated_news.append(curated_item)
                count += 1
                
    # Create data directory if not exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Write to static JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(curated_news, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully wrote {len(curated_news)} articles to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
