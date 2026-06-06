## ADDED Requirements

### Requirement: Multi-Category News Fetching
システムは、複数のNHKニュースカテゴリRSSフィード（主要ニュース、地域別ニュース等）から並列でニュース記事を取得する機能を提供する。各フィードから指定された件数のニュースを段階的に取得し、カテゴリ別にキュレーションされたデータ構造を生成する。

#### Scenario: Fetching Main News and Category News in Parallel
- **WHEN** GitHub Actionsのスケジュール実行により、ニュース取得プロセスが起動したとき
- **THEN** システムは複数のRSSフィードURL（主要ニュース用、カテゴリA用、カテゴリB用等）に対して並列リクエストを送信し、各フィードから最新ニュース記事のタイトル、リンク、配信日時を取得する。

#### Scenario: Applying News Count Limits per Category
- **WHEN** RSSフィードから取得したニュース一覧を処理するとき
- **THEN** システムは以下のルールを適用する：主要ニュースフィードからは最新10件を選定、各カテゴリニュースフィードからは最新5件ずつを選定、最終的に `data/news.json` に出力する。

### Requirement: Categorized News JSON Data Structure
ニュースデータは、主要ニュースと各カテゴリ別ニュースに明示的に分離された新規JSON形式で生成・保存される。

#### Scenario: JSON Structure with Main and Category News
- **WHEN** ニュース取得・翻訳処理が完了したとき
- **THEN** `data/news.json` は以下の構造で生成される：
  ```
  {
    "main_news": [ { "id": "...", "title": "...", "summary": "...", "content": "...", "translation": "...", "timestamp": "..." }, ... ],
    "category_news": {
      "region_1": [ { ... }, ... ],
      "region_2": [ { ... }, ... ],
      ...
    }
  }
  ```

#### Scenario: Full Article Text Extraction for Each Category
- **WHEN** 各フィードから取得したニュースリンク先にリクエストを送信するとき
- **THEN** システムは `newspaper3k` ライブラリを使用して、主要ニュース（10件）とカテゴリ別ニュース（各5件）それぞれについて、ニュース本文全文を抽出する。
