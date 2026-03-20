"""Prompt templates for local and external LLM calls."""

# ── Local LLM (Ollama): function summarisation ────────────────────────────

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

# ── External LLM: OSS similarity search ───────────────────────────────────

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
