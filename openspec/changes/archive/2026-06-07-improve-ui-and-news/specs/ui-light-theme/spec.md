## ADDED Requirements

### Requirement: White Light Theme Color Scheme
システムは、ホワイト基調でポップで明るいカラースキームを提供する。ダークテーマから完全に移行し、背景は白系、テキストは濃い色、アクセント色は鮮やかな色（例：ブルー、グリーン）を採用する。

#### Scenario: White Background Theme Display
- **WHEN** ユーザーがアプリケーションを開いたとき
- **THEN** UIの背景色が白系（例：#FFFFFF または #F5F5F5）で表示され、すべてのテキストが濃い色（例：#333333）で表示される。

#### Scenario: Accent Colors in Buttons and Controls
- **WHEN** ユーザーが再生ボタン、一時停止ボタン、その他のインタラクティブ要素を視認しようとするとき
- **THEN** これらの要素が鮮やかなアクセント色（例：青 #0066FF、緑 #00AA00）で表示され、ポップで明るい印象を与える。

### Requirement: Readable Article Title Layout
記事タイトルの表示を最適化し、長いテキストでも日本語が読みやすい状態を実現する。行高さ、テキスト折り返し、字間を調整する。

#### Scenario: Long Title Text Wrapping
- **WHEN** 記事タイトルが画面幅を超える長さの場合
- **THEN** テキストは複数行に自動折り返され、各行が読みやすい高さ（行高さ1.6以上）で表示される。

#### Scenario: Japanese Text Clarity in Mixed Language Titles
- **WHEN** 記事タイトルが日本語と英語の混在テキストを含む場合
- **THEN** 適切な `word-break` ルール（例：`word-break: break-word`）が適用され、日本語テキストが埋もれず、英語単語の分断を最小化して表示される。
