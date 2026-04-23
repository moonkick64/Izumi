# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""LLM-based license file identifier.

Sends LICENSE file content to a LLM and returns the SPDX identifier.
Used as a fallback when guess_spdx_id() cannot identify the license.
"""

from __future__ import annotations

from i18n import t


def analyze_license_text(
    license_text: str,
    model: str,
    api_base: str = "",
    api_key: str = "",
) -> str:
    """Return the SPDX identifier for *license_text*, or ``'NOASSERTION'``.

    Sends up to the first 4000 characters of the license text to the LLM
    and extracts a single SPDX identifier from the response.
    """
    from litellm import completion  # type: ignore[import]

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": t("prompt_license_system")},
            {"role": "user",   "content": t("prompt_license_user", license_text=license_text[:4000])},
        ],
        "temperature": 0,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    response = completion(**kwargs)
    raw = (response.choices[0].message.content or "").strip().strip("\"'")
    # Take first token only — the model should return just the identifier
    first = raw.split()[0] if raw.split() else "NOASSERTION"
    return first if first else "NOASSERTION"
