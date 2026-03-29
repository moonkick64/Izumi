# Izumi

A cross-platform GUI tool for detecting unknown OSS in C/C++ source trees and assisting SBOM creation.

Targeted at projects without package managers — such as embedded development — where source code is managed directly as files rather than declared dependencies. Unlike traditional Software Composition Analysis (SCA) tools that assume declared dependencies or require database-backed snippet matching, Izumi uses LLMs to analyse source code directly without any pre-built database.

LLM responses are treated as hints, not conclusions — the tool is designed to support the user's judgment.

![screenshot](docs/images/screenshot.png)

---

## Features

- **Static analysis** — extracts copyright notices, SPDX tags, and LICENSE files; classifies each file as CONFIRMED / INFERRED / UNKNOWN
- **LLM-assisted OSS identification** — three options to suit your confidentiality requirements:
  - Option 1: send function source code directly to a local LLM (Ollama)
  - Option 2: summarize locally → review and edit → send summaries to external LLM (protects confidential code)
  - Option 3: send function source code directly to an external LLM
- **Match decision UI** — confirm component name and license based on LLM hints; results are saved per project
- **SBOM export** — SPDX 2.3 and CycloneDX 1.5
- **UI available in English and Japanese**

---

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) (required for Option 1 and Option 2)
- An external LLM API key (required for Option 2 step 2 and Option 3)

---

## Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Clone and install dependencies
git clone https://github.com/moonkick64/izumi
cd izumi
uv sync
```

---

## Usage

```bash
uv run python main.py
```

1. **Settings** — select the source tree to scan; configure local LLM (Ollama endpoint + model) and/or external LLM (model + API key)
2. **Scan** — static analysis classifies all files; UNKNOWN files are highlighted
3. **LLM SCA Review** — extract functions from UNKNOWN files, run LLM analysis, review hints, and confirm component/license matches
4. **SBOM Export** — export the final SBOM in SPDX or CycloneDX format

Analysis results are saved to `~/.izumi/results/<project>/llm_results.json` and reloaded automatically on next open.

---

## LLM Configuration

| Setting | Description |
|---------|-------------|
| Local LLM model | Ollama model name, e.g. `ollama/codellama` |
| Local LLM endpoint | Ollama API endpoint, default `http://localhost:11434` |
| External LLM model | LiteLLM model name, e.g. `anthropic/claude-sonnet-4-6` |
| External LLM API key | API key for the external provider (or set via environment variable) |

Any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers) can be used as the external LLM (Claude, GPT-4, Gemini, DeepSeek, etc.).

---

## Development

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov
```

See [docs/architecture.md](docs/architecture.md) for detailed design and specification.

