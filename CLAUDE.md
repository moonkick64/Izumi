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
  │   ├─ test_gui/
  │   ├─ test_sbom/
  │   └─ test_llm/
  └─ .github/
      ├─ dependabot.yml          # Dependabot週次更新設定
      └─ workflows/
          ├─ security.yml        # pip-audit による脆弱性チェック
          └─ sbom-validate.yml   # SBOM出力検証・NTIA準拠チェック
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
- OSS特定プロンプトはLLMに `{"component": "...", "license": "...", "hint": "..."}` の**JSON形式**で返答させる。特定できない場合は `"NOASSERTION"` を使わせる
- プロンプト文字列は `i18n/en.json` / `i18n/ja.json` の `prompt_*` キーで管理し、UI言語に応じて自動切り替え
- `llm/prompts.py` の `parse_oss_response()` でJSONをパース：成功時は `hint` をヒント欄に表示しマッチングUIに自動入力、失敗時は `✗` マーカーを表示してエラーメッセージを表示する

---

## LLM解析の実装ルール

- 解析ボタンは**一括解析のみ**。単一関数モードは実装しない
- すべてのオプション（1〜3）で関数単位で解析する
- 解析結果は `~/.izumi/results/<project_name>_<hash>/llm_results.json` に**関数1件ごとに即時保存**する（スキャン対象ツリーは汚染しない）
- レビュー画面を開いたとき既存の結果ファイルがあれば**自動ロード**する
- UIから結果ファイルを**削除**できるボタンを設ける
- LLMヒントをもとにユーザーがコンポーネント名・ライセンスを決定する**マッチングUI**を実装する
  - 決定内容は `matched_component` / `matched_license` として結果ファイルに保存
  - SBOM出力時、マッチング決定済みのファイルは元コンポーネントから**分離**し、`(コンポーネント名, ライセンス)` ごとに独立した新コンポーネントを生成する（1件のマッチングが無関係なファイル全体に波及しないようにするため）
  - SBOMにはディレクトリ情報は含めない。コンポーネント名はユーザーが決定したOSS名を使用する

---

## スコープ外（実装しないこと）

- スニペットマッチング（DBとのハッシュ照合）
- 脆弱性スキャン（CVE検出等）
- クラウド連携・SaaS提供
- パッケージマネージャ対応（npm, pip 等）

---

## SBOM出力の補足

- SPDX・CycloneDX ともに各パッケージに PURL（`pkg:generic/{name}@{version}`）を付与する
- `PackageSupplier` はユーザーが SBOM 出力画面の詳細パネルで入力した場合のみ出力する。未入力時は `NOASSERTION`
- `PackageVersion` はバージョンが判明している場合のみ出力する。不明な場合はフィールドを省略する（SPDX 2.3 仕様では `PackageVersion` はオプションフィールドであり、`NOASSERTION` は文法上無効なためパーサーエラーになる）
- `project_name` / `project_version` は SPDX の `DocumentName` フィールドに反映する（例: `my-firmware-1.0.0`）。別パッケージとしては追加しない
- SBOM 出力画面はテーブル（読み取り専用・概要）＋詳細パネル（選択中コンポーネントの編集）の 2 層構造。詳細パネルで Name / Version / License / Supplier を編集できる
- NTIA最小要素の対応状況：作成者・タイムスタンプ・コンポーネント名・PURL・依存関係 → 自動で充足。バージョン・供給者 → SBOM 出力画面の詳細パネルで入力することで補完できる
- CI（`sbom-validate.yml`）はパースエラー・名前・PURL・依存関係の欠落を検出したときに失敗し、バージョン・供給者の欠落は情報として出力するのみ

---

## 静的解析の補足

- `analyzer/copyright.py` の `CopyrightInfo` には `license_candidates: list[str]` フィールドがある。SPDX タグを持たないファイルのヘッダから `"Licensed under"` 等のパターンで抽出した自由記述テキストを保存する
- スキャン画面でファイルを選択すると「分類の変更」パネルが常に表示される。分類は CONFIRMED / INFERRED / UNKNOWN の間で自由に変更可能。`classification_changed` シグナル経由で main_window が分類を更新し、コンポーネントを再構築する
- ライセンスフィールドは既存の `spdx_license_id` を優先し、なければ `guess_spdx_id()` で `license_candidates` の先頭テキストから SPDX ID を推定して事前入力する
- スキャン結果（分類・コンポーネント）はメモリ上のみに保持される。`~/.izumi/results/` に保存されるのは LLM 解析結果（`llm_results.json`）のみ

### 分類基準

| 分類 | 条件 |
|------|------|
| CONFIRMED | `SPDX-License-Identifier` タグあり、または同一ディレクトリの LICENSE ファイルから `guess_spdx_id()` でライセンスが特定できる |
| INFERRED | LICENSE ファイルはあるがライセンス名を特定できない、copyright 表記あり、またはサードパーティディレクトリ内 |
| UNKNOWN | 上記のいずれにも該当しない |

- **CONFIRMED は「ライセンスが特定できている」ことを意味する。** LICENSE ファイルが存在するだけでは CONFIRMED にしない（`guess_spdx_id()` で SPDX ID が得られた場合のみ）

### LLM によるライセンスファイル解析（スキャン時オプション）

- 設定画面のローカル LLM / 外部 LLM グループにチェックボックスがあり、有効にするとスキャン完了後に自動実行される
- 対象: `license_expression` が `None` または `NOASSERTION` のコンポーネントが参照する LICENSE ファイル
- `llm/license_analyzer.py` の `analyze_license_text()` が SPDX ID のみを返すプロンプトで LLM に問い合わせる
- 結果は `Component.license_expression` に即時反映され、スキャン結果画面も更新される
- 外部 LLM が有効な場合は外部 LLM を優先し、ローカル LLM のみの場合はローカル LLM を使用する
- プロンプトは `prompt_license_system` / `prompt_license_user` キーで管理（他のプロンプトと同様）

---

## 未決定事項

- [ ] ローカルLLMの推奨モデル（Ollama上で動かすモデル、例：codellama, deepseek-coder等）
