# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""LLM-based license file identifier.

Sends LICENSE file content to a LLM and returns the SPDX identifier.
Used as a fallback when guess_spdx_id() cannot identify the license.
"""

from __future__ import annotations

import logging

from litellm import completion  # type: ignore[import]

from i18n import t

_log = logging.getLogger(__name__)


def analyze_license_text(
    license_text: str,
    model: str,
    api_base: str = "",
    api_key: str = "",
) -> str:
    """Return the SPDX identifier for *license_text*, or ``'NOASSERTION'``.

    Sends up to the first 8000 characters of the license text to the LLM.
    This covers even long licenses such as GPL-3.0 (~35 000 chars) partially,
    while staying well within the context window of typical 7 B local models.
    """
    excerpt = license_text[:8000]
    messages = [
        {"role": "system", "content": t("prompt_license_system")},
        {"role": "user",   "content": f"{t('prompt_license_user')}\n\n---\n{excerpt}"},
    ]

    kwargs: dict = {"model": model, "messages": messages, "timeout": 60}
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    response = completion(**kwargs)
    raw = (response.choices[0].message.content or "").strip().strip("\"'")
    _log.debug("raw response: %r", raw)
    first = raw.split()[0] if raw.split() else "NOASSERTION"
    return first if first else "NOASSERTION"
