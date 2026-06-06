## ADDED Requirements

### Requirement: RSS Feed Parsing and Curation
システムは、NHKニュースの主要ニュースRSSフィード（`https://news.web.nhk/n-data/conf/na/rss/cat0.xml`）から最新のニュースリンクを取得し、さらにそのリンク（URL）先からニュース記事の本文全文を取得する機能を提供する。この処理はGitHub Actionsによりスケジュール実行され、サーバーレスで動作する。

#### Scenario: Scheduled RSS Fetching and Crawling
- **WHEN** GitHub Actionsのcronスケジュール（例：1日3回）が起動したとき
- **THEN** システムはRSSフィードから最新ニュース記事のタイトル、リンク、配信日時を取得し、さらに各記事のURLにリクエストを送信して、ニュース抽出ライブラリ `newspaper3k` を使用してニュース本文全文（日本語テキスト）を抽出して一時的に保持する。

### Requirement: Gemini API News Translation and Summarization
システムは、取得したニュース記事の日本語本文全文を Google Gemini API に送信し、記事の全体内容に基づいた学習用の英語要約、自然な英語学習テキスト、および文単位で対応する日本語対訳データを生成する。

#### Scenario: Generating Curated JSON
- **WHEN** 取得した日本語ニュースの本文全文をGemini API（無料枠）に送信したとき
- **THEN** Gemini APIはニュース本文の内容に基づいて「英語の要約（約1-2文）」「詳細な学習用英文（約5-10文）」「文単位で対応する日本語対訳」を含むJSONデータを生成し、システムはこれを `data/news.json` としてリポジトリに保存し、GitHub Pagesにデプロイする。


