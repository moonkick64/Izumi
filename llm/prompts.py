"""Prompt templates for local and external LLM calls.

All default prompt strings are exposed as module-level constants so that
the settings UI can read and override them at runtime.
"""

# ── Option 2 – Local LLM (Ollama): function summarisation ────────────────────

SUMMARISE_FUNCTION_SYSTEM = (
    "You are a software analysis assistant. "
    "Summarise C/C++ functions concisely in plain language without revealing "
    "implementation details that might be proprietary. "
    "Focus on *what* the function does, not *how* it does it."
)

SUMMARISE_FUNCTION_USER = """\
Summarise the following C/C++ function in one or two sentences.
Describe what it does without mentioning variable names or internal algorithms.

```c
{function_body}
```
"""

# ── Option 2 – External LLM: OSS similarity search (from summaries) ──────────

OSS_SIMILARITY_SYSTEM = (
    "You are a software licensing expert. "
    "Given a natural language description of a function, identify any known "
    "open-source libraries or functions with similar behaviour. "
    "If you are not confident, say so explicitly. "
    "Never fabricate library names or version numbers."
)

OSS_SIMILARITY_USER = """\
The following descriptions are of functions found in an embedded C/C++ codebase.
For each description, identify any known open-source libraries or functions with \
similar behaviour.
If you are unsure, say "No confident match found."

{summaries}
"""

# ── Option 1 / 3 – Direct OSS identification from source code ─────────────────
# Default matches CLAUDE.md spec; user can edit via settings.

DIRECT_OSS_SYSTEM = (
    "You are a software licensing expert specialising in embedded C/C++ code. "
    "Identify open-source software (OSS) contained in or similar to the given "
    "source code. If you are not confident, say so explicitly. "
    "Never fabricate library names or version numbers."
)

DIRECT_OSS_USER = """\
この情報から何のOSSが含まれているか特定してください。心当たりがなければその旨を答えてください。

```c
{source_code}
```
"""


# ── Formatting helpers ────────────────────────────────────────────────────────

def format_summarise_prompt(function_body: str) -> list[dict]:
    return [
        {"role": "system", "content": SUMMARISE_FUNCTION_SYSTEM},
        {"role": "user", "content": SUMMARISE_FUNCTION_USER.format(
            function_body=function_body
        )},
    ]


def format_oss_similarity_prompt(summaries: list[str]) -> list[dict]:
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(summaries))
    return [
        {"role": "system", "content": OSS_SIMILARITY_SYSTEM},
        {"role": "user", "content": OSS_SIMILARITY_USER.format(summaries=numbered)},
    ]


def format_direct_oss_prompt(source_code: str) -> list[dict]:
    """Format a prompt for Option 1 (local direct) and Option 3 (external direct)."""
    return [
        {"role": "system", "content": DIRECT_OSS_SYSTEM},
        {"role": "user", "content": DIRECT_OSS_USER.format(source_code=source_code)},
    ]
