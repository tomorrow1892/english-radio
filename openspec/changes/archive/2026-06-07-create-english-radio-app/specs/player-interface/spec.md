## ADDED Requirements

### Requirement: Web Speech API English Playback
システムは、ブラウザ標準の Web Speech API (SpeechSynthesis) を利用して、完全に無料で動作する英語テキストの音声読み上げ機能を提供する。

#### Scenario: Play and Pause Text Speech
- **WHEN** ユーザーがプレイヤーの「再生」または「一時停止」ボタンをクリックしたとき
- **THEN** Web Speech APIの `speechSynthesis.speak()` または `pause() / resume()` が呼び出され、選択されている英文の音声再生・一時停止が制御される。

### Requirement: Playback Parameter Control
ユーザーは、音声読み上げの速度および英語の話者（国、性別など）を自由にカスタマイズできる。

#### Scenario: Adjusting Speech Rate
- **WHEN** ユーザーが速度スライダー（0.5倍〜2.0倍）を変更したとき
- **THEN** Web Speech APIの `SpeechSynthesisUtterance.rate` にその値が設定され、即座に読み上げ速度が反映される。

#### Scenario: Selecting Speech Voice
- **WHEN** ユーザーが音声ドロップダウンメニューから特定の話者（例：Google US English, Microsoft Ziraなど）を選択したとき
- **THEN** 音声合成オブジェクトの `voice` プロパティが切り替わり、選択した音声で英語が読み上げられる。

### Requirement: Synchronized Bilingual Highlighting
プレイヤーは、現在音声で読み上げられている「文（sentence）」または「パラグラフ」を画面上でハイライト表示し、同時に対応する日本語対訳を同期して強調表示する。

#### Scenario: Highlighting Currently Spoken Sentence
- **WHEN** 音声合成の読み上げ位置が特定の文に移動したとき（Web Speech APIの `boundary` イベントまたは文ごとの再生分割制御による）
- **THEN** プレイヤーUI上の該当する英文テキストにハイライトスタイル（例：背景色またはテキストカラーの変更）が適用され、かつ対応する日本語テキストが自動でスクロールインし目立たせて表示される。
