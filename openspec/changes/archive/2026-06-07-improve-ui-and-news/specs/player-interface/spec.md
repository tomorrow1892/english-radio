## MODIFIED Requirements

### Requirement: Web Speech API English Playback
システムは、ブラウザ標準の Web Speech API (SpeechSynthesis) を利用して、完全に無料で動作する英語テキストの音声読み上げ機能を提供する。ホワイト基調のUIテーマの中で、再生・一時停止ボタンが鮮やかなアクセント色で視認されやすく設計されている。

#### Scenario: Play and Pause Text Speech
- **WHEN** ユーザーがプレイヤーの「再生」または「一時停止」ボタン（ホワイトテーマ適用後）をクリックしたとき
- **THEN** Web Speech APIの `speechSynthesis.speak()` または `pause() / resume()` が呼び出され、選択されている英文の音声再生・一時停止が制御される。

### Requirement: Playback Parameter Control
ユーザーは、音声読み上げの速度および英語の話者（国、性別など）を自由にカスタマイズできる。これらのコントロール要素は、ホワイト基調で明るいUIに統一される。

#### Scenario: Adjusting Speech Rate
- **WHEN** ユーザーが速度スライダー（0.5倍〜2.0倍）を変更したとき
- **THEN** Web Speech APIの `SpeechSynthesisUtterance.rate` にその値が設定され、即座に読み上げ速度が反映される。スライダーはホワイトテーマの色彩に合わせて表示される。

#### Scenario: Selecting Speech Voice
- **WHEN** ユーザーが音声ドロップダウンメニューから特定の話者（例：Google US English, Microsoft Ziraなど）を選択したとき
- **THEN** 音声合成オブジェクトの `voice` プロパティが切り替わり、選択した音声で英語が読み上げられる。ドロップダウンはホワイト基調のUIに統一される。

### Requirement: Synchronized Bilingual Highlighting
プレイヤーは、現在音声で読み上げられている「文（sentence）」または「パラグラフ」を画面上でハイライト表示し、同時に対応する日本語対訳を同期して強調表示する。ハイライト色は、ホワイト基調UIに適した色（例：薄いブルーまたは黄色）で設計される。

#### Scenario: Highlighting Currently Spoken Sentence
- **WHEN** 音声合成の読み上げ位置が特定の文に移動したとき（Web Speech APIの `boundary` イベントまたは文ごとの再生分割制御による）
- **THEN** プレイヤーUI上の該当する英文テキストにハイライトスタイル（例：薄いブルーの背景 #E8F4FF または黄色の背景）が適用され、かつ対応する日本語テキストが自動でスクロールインし目立たせて表示される。

## ADDED Requirements

### Requirement: Optimized Article Title Display for Long Text
記事タイトルが長い場合でも、日本語テキストが読みやすく表示される。CSS の `word-break`、行高さ、テキスト折り返し設定により実現される。

#### Scenario: Japanese Text Remains Readable in Lengthy Titles
- **WHEN** 記事一覧の表示エリアに長い記事タイトルが含まれるとき
- **THEN** システムは `word-break: break-word` と行高さ `line-height: 1.6` 以上の設定を適用し、日本語テキストが複数行に折り返されても、1文字ずつ切断されずに読みやすい形で表示される。
