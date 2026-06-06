# News Curation Spec

## Purpose

Defines how the system collects, processes, and publishes English-learning news content by fetching multiple NHK RSS feeds, extracting article text, and generating categorized English summaries and bilingual translations via the Gemini API.

---

## Requirements

### Requirement: RSS Feed Parsing and Curation
システムは、NHKニュースの複数カテゴリRSSフィード（主要ニュース、地域別ニュース等）から最新のニュースリンクを取得し、さらにそのリンク（URL）先からニュース記事の本文全文を取得する機能を提供する。この処理はGitHub Actionsによりスケジュール実行され、サーバーレスで動作する。主要ニュースは10件、各カテゴリニュースは5件ずつを取得する。

#### Scenario: Scheduled RSS Fetching from Multiple Feeds with Count Limits
- **WHEN** GitHub Actionsのcronスケジュール（例：1日3回）が起動したとき
- **THEN** システムは複数のNHKニュースRSSフィード（`cat0`=主要、`cat1`以降=カテゴリ別）に並列リクエストを送信し、主要フィード（`cat0`）からは最新10件、その他カテゴリフィードからは各5件のニュース記事タイトル、リンク、配信日時を取得する。さらに各記事のURLに対してリクエストを送信し、`newspaper3k` ライブラリを使用して日本語本文全文を抽出して一時的に保持する。

### Requirement: Gemini API News Translation and Summarization
システムは、取得したニュース記事の日本語本文全文を Google Gemini API に送信し、記事の全体内容に基づいた学習用の英語要約、自然な英語学習テキスト、および文単位で対応する日本語対訳データを生成する。

#### Scenario: Generating Categorized and Structured JSON Output
- **WHEN** 取得した日本語ニュースの本文全文（主要10件、カテゴリ別各5件）をGemini API（無料枠）に送信したとき
- **THEN** Gemini APIはニュース本文の内容に基づいて「英語の要約（約1-2文）」「詳細な学習用英文（約5-10文）」「文単位で対応する日本語対訳」を含むJSONデータを生成し、システムはこれを以下の構造で `data/news.json` として保存する：
  ```
  {
    "main_news": [ { "id": "...", "title": "...", "summary": "...", "content": "...", "translation": "...", "timestamp": "..." }, ... ],
    "category_news": {
      "category_name": [ { ... }, ... ],
      ...
    }
  }
  ```
  最終的に GitHub Pagesにデプロイされる。
