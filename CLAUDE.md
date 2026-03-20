# Izumi - CLAUDE.md

## プロジェクト概要

C/C++組み込みソフトウェアのソースツリーから未知のOSS混入を検出し、SBOMの作成を支援するデスクトップGUIツール。

パッケージマネージャを使わない組み込み開発（大量のソースコード＋Makefile構成）を主なターゲットとする。
BlackDuckのようなスニペットマッチングは使わず、LLMを活用した柔軟な検出とユーザーへのヒント提示を行う。

詳細仕様は `docs/spec.md` を参照。

---

## 設計思想（必ず守ること）

- **ツールは判断しない。ヒントを出す。** 最終判断は常にユーザーに委ねる
- **確認作業を最小化する。** UNKNOWNのものだけをユーザーに提示する
- **信頼できる情報と不確かな情報を明確に分ける。** 曖昧なものはUNKNOWNとして明示する
- **機密情報の外部漏洩を設計で防ぐ。** ローカルLLMで要約→ユーザーが確認・編集→外部LLMへ送信

---

## 技術スタック

| 項目 | 選定 |
|------|------|
| 言語 | Python 3.11以上 |
| GUI | PySide6 |
| ローカルLLM | Ollama + LiteLLM |
| 外部LLM | LiteLLM（Claude, Gemini, GPT-4, DeepSeek, Qwen等に対応） |
| C/C++パーサ | libclang（失敗時は正規表現にフォールバック） |
| SBOM出力 | spdx-tools / cyclonedx-bom |
| ライセンス | GPL v3 |

---

## ディレクトリ構成

```
sbom-tool/
  ├─ CLAUDE.md
  ├─ docs/
  │   └─ spec.md          # 詳細仕様書
  ├─ main.py              # エントリーポイント
  ├─ analyzer/            # 静的解析エンジン
  │   ├─ __init__.py
  │   ├─ scanner.py       # ソースツリースキャン
  │   ├─ copyright.py     # copyright/SPDX抽出
  │   ├─ classifier.py    # CONFIRMED/INFERRED/UNKNOWN分類
  │   └─ parser/
  │       ├─ clang_parser.py   # libclangによる関数抽出
  │       └─ regex_parser.py   # フォールバック用正規表現パーサ
  ├─ llm/
  │   ├─ __init__.py
  │   ├─ local_llm.py     # Ollama経由のローカルLLM（要約生成）
  │   ├─ external_llm.py  # 外部LLM（OSS類似検索）
  │   └─ prompts.py       # プロンプトテンプレート
  ├─ gui/
  │   ├─ __init__.py
  │   ├─ main_window.py   # メインウィンドウ
  │   ├─ scan_view.py     # スキャン結果一覧画面
  │   ├─ review_view.py   # UNKNOWNレビュー画面
  │   ├─ sbom_view.py     # SBOM出力画面
  │   └─ settings_view.py # 設定画面
  ├─ sbom/
  │   ├─ __init__.py
  │   ├─ spdx_writer.py   # SPDX出力
  │   └─ cyclonedx_writer.py  # CycloneDX出力
  ├─ tests/
  │   ├─ test_analyzer/
  │   └─ test_llm/
  └─ requirements.txt
```

---

## 処理フロー

```
1. ソースツリースキャン（analyzer/scanner.py）
   └─ LICENSEファイル、COPYINGファイル、READMEを検出
   └─ ソースファイルのヘッダからcopyright/SPDX識別子を抽出
   └─ ディレクトリ名のヒューリスティック（third_party/, vendor/, extern/等）

2. 3段階分類（analyzer/classifier.py）
   ├─ CONFIRMED: ライセンス・copyrightが明確（自動通過）
   ├─ INFERRED:  状況証拠から推定（自動通過・根拠を記録）
   └─ UNKNOWN:   判断できない → フェーズ2へ

3. LLMによるOSS混入検出（UNKNOWNのみ）
   a. libclangで関数単位に分割
   b. ローカルLLM（Ollama）で各関数を自然言語で要約
   c. ユーザーが要約を確認・編集（機密除去）
   d. 承認された要約を外部LLMに送信
   e. 「XXライブラリに似ている可能性」をヒントとして提示

4. SBOM出力
   └─ SPDX 2.3 または CycloneDX 1.5 形式で出力
```

---

## 分類の定義

| 分類 | 意味 | ユーザー確認 |
|------|------|------------|
| CONFIRMED | LICENSEファイルまたはSPDXタグで明確に特定できる | 不要 |
| INFERRED | ディレクトリ名・copyright表記等の状況証拠から推定 | 不要（根拠を記録） |
| UNKNOWN | 判断できない・copyright/ライセンス記載なし | 必要 |

---

## LLMの使い方の原則

- ローカルLLM（Ollama）：**要約生成のみ**。ソースコードを直接外部に送らないための中間ステップ
- 外部LLM（LiteLLM）：**類似OSSの特定**。ユーザーが承認した要約のみ送信する
- LLMの回答は**ヒント**として扱う。確定情報として扱わない
- ハルシネーションの可能性をUIで常に明示する

---

## LiteLLMの使い方

```python
from litellm import completion

# 外部LLM
response = completion(model="claude-sonnet-4-20250514", messages=[...])
response = completion(model="gemini/gemini-2.0-flash", messages=[...])
response = completion(model="deepseek/deepseek-chat", messages=[...])

# ローカルLLM（Ollama）
response = completion(
    model="ollama/codellama",
    messages=[...],
    api_base="http://localhost:11434"
)
```

モデル名とAPIキーは設定ファイル（`~/.sbom-tool/config.json`）で管理する。

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



1. `analyzer/` - 静的解析エンジン（copyright/SPDX抽出・分類）
2. `gui/` - 基本的なGUI骨格（画面遷移）
3. `llm/` - ローカルLLM連携（要約生成）
4. `gui/review_view.py` - UNKNOWNレビュー画面
5. `llm/external_llm.py` - 外部LLM連携
6. `sbom/` - SBOM出力

---

## 開発時の注意事項

- 各モジュールは独立してテスト可能な設計にする
- GUIとロジックは分離する（analyzer/llm/sbomはGUIに依存しない）
- エラーは握りつぶさず、ユーザーに分かりやすく表示する
- 処理が長い場合はプログレスバーを表示する
