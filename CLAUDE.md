# Izumi — CLAUDE.md

## プロジェクト概要

C/C++ 組み込みソフトウェアのソースツリーから未知のOSS混入を検出し、SBOMの作成を支援するデスクトップGUIツール。

パッケージマネージャを使わない組み込み開発（大量のソースコード＋Makefile構成）を主なターゲットとする。
BlackDuckのようなスニペットマッチングは使わず、LLMを活用した柔軟な検出とユーザーへのヒント提示を行う。

詳細仕様は `docs/architecture.md` を参照。

---

## 設計思想（必ず守ること）

- **ツールは判断しない。ヒントを出す。** 最終判断は常にユーザーに委ねる
- **確認作業を最小化する。** UNKNOWNのものだけをユーザーに提示する
- **信頼できる情報と不確かな情報を明確に分ける。** 曖昧なものはUNKNOWNとして明示する
- **機密情報の外部漏洩を設計で防ぐ。** LLMオプション2ではローカルLLMで要約→ユーザーが確認・編集→外部LLMへ送信
- **ユーザーが常にコントロールできる。** ライセンス変更・除外・LLMへの送信可否・プロンプト内容はすべてユーザーが設定・編集できる

---

## ディレクトリ構成

```
izumi/
  ├─ CLAUDE.md
  ├─ docs/
  │   └─ architecture.md   # 詳細仕様書
  ├─ main.py               # エントリーポイント
  ├─ analyzer/             # 静的解析エンジン
  │   ├─ __init__.py
  │   ├─ scanner.py        # ソースツリースキャン
  │   ├─ copyright.py      # copyright/SPDX抽出
  │   ├─ classifier.py     # CONFIRMED/INFERRED/UNKNOWN分類
  │   └─ parser/
  │       ├─ clang_parser.py    # libclangによる関数抽出
  │       └─ regex_parser.py    # フォールバック用正規表現パーサ
  ├─ llm/
  │   ├─ __init__.py
  │   ├─ local_llm.py      # Ollama経由のローカルLLM（要約生成・直接問い合わせ）
  │   ├─ external_llm.py   # 外部LLM（OSS類似検索）
  │   └─ prompts.py        # プロンプトテンプレート（ユーザーが設定で変更可能）
  ├─ gui/
  │   ├─ __init__.py
  │   ├─ main_window.py    # メインウィンドウ
  │   ├─ scan_view.py      # スキャン結果一覧画面（コードビューアー含む）
  │   ├─ review_view.py    # LLM SCAレビュー画面
  │   ├─ sbom_view.py      # SBOM出力画面
  │   └─ settings_view.py  # 設定画面
  ├─ i18n/
  │   ├─ __init__.py          # t() 関数・言語切り替え
  │   ├─ en.json              # 英語文字列（デフォルト）
  │   └─ ja.json              # 日本語文字列
  ├─ sbom/
  │   ├─ __init__.py
  │   ├─ spdx_writer.py    # SPDX出力
  │   └─ cyclonedx_writer.py   # CycloneDX出力
  ├─ tests/
  │   ├─ test_analyzer/
  │   └─ test_llm/
  └─ requirements.txt
```

---

## 開発環境

- パッケージ管理：uv（pip/venvは使わない）
- 依存追加：`uv add <package>`
- スクリプト実行：`uv run python main.py`
- 環境構築：`uv sync`

### セットアップ手順

```bash
# uvのインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# プロジェクトの初期化
git clone https://github.com/xxx/izumi
cd izumi
uv sync

# 実行
uv run python main.py
```

---

## 開発順序

1. `analyzer/` — 静的解析エンジン（copyright/SPDX抽出・分類）
2. `gui/` — 基本的なGUI骨格（画面遷移・コードビューアー）
3. `llm/` — ローカルLLM連携（要約生成・直接問い合わせ）
4. `gui/review_view.py` — LLM SCAレビュー画面
5. `llm/external_llm.py` — 外部LLM連携
6. `sbom/` — SBOM出力

---

## Git 運用方針

- git操作（commit / push / branch等）は原則ユーザーが行う
- Claudeはコミット案の提示までとし、実際のgitコマンド実行は行わない
- コミットメッセージのプレフィックス（`feat:` 等）は使わない
- 1行目は英語の命令形で簡潔に（例: `Add 3-option LLM analysis UI`）
- 詳細は箇条書きで記載する

---

## 開発時の注意事項

- 各モジュールは独立してテスト可能な設計にする
- GUIとロジックは分離する（analyzer / llm / sbom はGUIに依存しない）
- エラーは握りつぶさず、ユーザーに分かりやすく表示する
- 処理が長い場合はプログレスバーを表示する
- UIは Visual Studio に近い操作感を目指す（左ペインにファイルツリー、右ペインにソースビューアー）
- **`.py` ソースファイルに日本語（漢字・ひらがな・カタカナ）を書かない。** UI文字列はすべて `i18n/` の辞書に集約し、`t("key")` 経由で参照する

---

## LLMの使い方の原則

- LLMの回答は**ヒント**として扱う。確定情報として扱わない
- ハルシネーションの可能性をUIで常に明示する
- 外部LLMへの送信はユーザーが明示的に承認したものだけに限定する
- プロンプトのデフォルトは「この情報から何のOSSが含まれているか特定してください。心当たりがなければその旨を答えてください。」とするが、設定で変更可能にする

---

## LLM解析の実装ルール

- 解析ボタンは**一括解析のみ**。単一関数モードは実装しない
- すべてのオプション（1〜3）で関数単位で解析する
- 解析結果は `~/.izumi/results/<project_name>_<hash>/llm_results.json` に**関数1件ごとに即時保存**する（スキャン対象ツリーは汚染しない）
- レビュー画面を開いたとき既存の結果ファイルがあれば**自動ロード**する
- UIから結果ファイルを**削除**できるボタンを設ける
- LLMヒントをもとにユーザーがコンポーネント名・ライセンスを決定する**マッチングUI**を実装する
  - 決定内容は `matched_component` / `matched_license` として結果ファイルに保存
  - SBOM出力時にマッチング決定済みの情報をコンポーネント名・ライセンスとして反映する
  - SBOMにはディレクトリ情報は含めない。コンポーネント名はユーザーが決定したOSS名を使用する

---

## スコープ外（実装しないこと）

- スニペットマッチング（DBとのハッシュ照合）
- 脆弱性スキャン（CVE検出等）
- クラウド連携・SaaS提供
- パッケージマネージャ対応（npm, pip 等）

---

## 未決定事項

- [ ] ローカルLLMの推奨モデル（Ollama上で動かすモデル、例：codellama, deepseek-coder等）
- [ ] 外部LLMのプロンプト設計（精度に直結するため要実験）
