# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Local LLM integration via Ollama + LiteLLM.

Responsibilities:
- Option 1: directly identify OSS from raw source code (stays local)
- Option 2: summarise C/C++ functions into natural language (stays local)

Source code never leaves the local machine via this module.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable, Optional

from litellm import completion  # type: ignore[import]

from analyzer.models import Component, FunctionSummary
from analyzer.parser import extract_functions
from .prompts import format_direct_oss_prompt, format_summarise_prompt


class LocalLLM:
    """Wrapper around a locally hosted Ollama model via LiteLLM."""

    def __init__(
        self,
        model: str,
        api_base: str = "http://localhost:11434",
        timeout: int = 60,
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.timeout = timeout

    # ── Core API ──────────────────────────────────────────────────────────

    def query_direct(self, source_code: str) -> str:
        """Option 1: send *source_code* directly to the local LLM to identify OSS.

        Returns the LLM response as a hint string, or ``[ERROR] …`` on failure.
        Source code never leaves the local machine.
        """
        messages = format_direct_oss_prompt(source_code)
        try:
            response = completion(
                model=self.model,
                messages=messages,
                api_base=self.api_base,
                timeout=self.timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            return f"[ERROR] Local LLM call failed: {exc}"

    def summarise_function(self, function_body: str) -> str:
        """Summarise *function_body* in plain English.

        Returns the summary string, or an error message prefixed with
        ``[ERROR]`` so callers can detect failures without raising.
        """
        messages = format_summarise_prompt(function_body)
        try:
            response = completion(
                model=self.model,
                messages=messages,
                api_base=self.api_base,
                timeout=self.timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            return f"[ERROR] Local LLM call failed: {exc}"

    def summarise_component(
        self,
        component: Component,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Component:
        """Extract functions from *component*'s files and summarise each one.

        Populates ``component.function_summaries`` in place and returns the
        component.  Source code never leaves the local machine.

        Args:
            component: An UNKNOWN component whose files will be analysed.
            progress_callback: Optional ``(current, total, function_name)``
                callback for progress reporting.

        Returns:
            The same *component* with ``function_summaries`` populated.
        """
        all_functions = []
        for file_path in component.files:
            all_functions.extend(extract_functions(file_path))

        summaries: list[FunctionSummary] = []
        for i, fn in enumerate(all_functions):
            if progress_callback:
                progress_callback(i, len(all_functions), fn.name)

            summary_text = self.summarise_function(fn.body)
            summaries.append(FunctionSummary(
                function_name=fn.name,
                file_path=fn.file_path,
                start_line=fn.start_line,
                end_line=fn.end_line,
                body=fn.body,
                summary=summary_text,
            ))

        component.function_summaries = summaries
        return component

    # ── Availability check ────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True if the Ollama endpoint is reachable."""
        try:
            with urllib.request.urlopen(self.api_base, timeout=5):
                return True
        except Exception:
            return False
