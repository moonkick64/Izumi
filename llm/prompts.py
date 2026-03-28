"""Prompt templates for local and external LLM calls.

Prompt strings are stored in i18n/en.json and i18n/ja.json under keys prefixed
with "prompt_", so the LLM's hint field is returned in the user's language.

OSS identification prompts (Options 1, 2-step2, 3) request structured JSON:

    {"component": "zlib 1.2.11", "license": "Zlib", "hint": "...reason..."}

Use parse_oss_response() to extract (component, license, hint) from the raw
LLM text.  Returns None on parse failure.
"""

from __future__ import annotations

import json
import re

from i18n import t


# ── Formatting helpers ────────────────────────────────────────────────────────

def format_summarise_prompt(function_body: str) -> list[dict]:
    return [
        {"role": "system", "content": t("prompt_summarise_system")},
        {"role": "user",   "content": t("prompt_summarise_user", function_body=function_body)},
    ]


def format_direct_oss_prompt(source_code: str) -> list[dict]:
    """Option 1 (local direct) and Option 3 (external direct)."""
    return [
        {"role": "system", "content": t("prompt_direct_oss_system")},
        {"role": "user",   "content": t("prompt_direct_oss_user", source_code=source_code)},
    ]


def format_oss_similarity_prompt(summaries: list[str]) -> list[dict]:
    """Option 2 step-2: external LLM receives function summaries."""
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(summaries))
    return [
        {"role": "system", "content": t("prompt_oss_similarity_system")},
        {"role": "user",   "content": t("prompt_oss_similarity_user", summaries=numbered)},
    ]


# ── Response parser ───────────────────────────────────────────────────────────

def parse_oss_response(text: str) -> tuple[str, str, str] | None:
    """Extract (component, license, hint) from a structured LLM response.

    Handles both raw JSON and JSON wrapped in markdown code fences.
    Returns None if parsing fails, so callers can treat the function as errored.

    Examples of accepted input:
        {"component": "zlib 1.2.11", "license": "Zlib", "hint": "CRC32 matches zlib"}
        ```json
        {"component": "NOASSERTION", "license": "NOASSERTION", "hint": "No match found"}
        ```
    """
    stripped = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    if m:
        stripped = m.group(1).strip()
    try:
        data = json.loads(stripped)
        component = str(data.get("component", "")).strip()
        license_  = str(data.get("license",   "")).strip()
        hint      = str(data.get("hint",       "")).strip()
        return component, license_, hint
    except Exception:
        return None
