# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Unit tests for llm.external_llm (LiteLLM calls are mocked)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from analyzer.classifier import Classification
from analyzer.models import Component, FunctionSummary
from llm.external_llm import ExternalLLM


# ── Helpers ───────────────────────────────────────────────────────────────

def _mock_completion(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    return response


def make_component_with_summaries(
    tmp_path: Path,
    summaries: list[tuple[str, bool]],  # (summary_text, approved)
) -> Component:
    comp = Component(
        name="test-lib",
        directory=tmp_path,
        classification=Classification.UNKNOWN,
        classification_reason="no info",
    )
    for text, approved in summaries:
        fs = FunctionSummary(
            function_name="fn",
            file_path=tmp_path / "f.c",
            start_line=1,
            end_line=5,
            body="void fn(){}",
            summary=text,
            approved=approved,
        )
        comp.function_summaries.append(fs)
    return comp


# ── find_similar_oss tests ────────────────────────────────────────────────

class TestFindSimilarOss:
    @patch("llm.external_llm.completion")
    def test_returns_hint(self, mock_completion):
        mock_completion.return_value = _mock_completion("Possibly similar to zlib crc32().")
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        result = llm.find_similar_oss(["computes CRC32"])
        assert "zlib" in result

    @patch("llm.external_llm.completion")
    def test_empty_list_returns_empty_string(self, mock_completion):
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        result = llm.find_similar_oss([])
        mock_completion.assert_not_called()
        assert result == ""

    @patch("llm.external_llm.completion")
    def test_error_returns_error_prefix(self, mock_completion):
        mock_completion.side_effect = Exception("API timeout")
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        result = llm.find_similar_oss(["some summary"])
        assert result.startswith("[ERROR]")

    @patch("llm.external_llm.completion")
    def test_correct_model_used(self, mock_completion):
        mock_completion.return_value = _mock_completion("ok")
        llm = ExternalLLM(model="gemini/gemini-2.0-flash")
        llm.find_similar_oss(["summary"])
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gemini/gemini-2.0-flash"

    @patch("llm.external_llm.completion")
    def test_strips_whitespace(self, mock_completion):
        mock_completion.return_value = _mock_completion("  Result.  \n")
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        result = llm.find_similar_oss(["s"])
        assert result == "Result."


# ── analyse_component tests ───────────────────────────────────────────────

class TestAnalyseComponent:
    @patch("llm.external_llm.completion")
    def test_sets_oss_hint(self, mock_completion, tmp_path):
        mock_completion.return_value = _mock_completion("Similar to openssl EVP_Digest.")
        comp = make_component_with_summaries(
            tmp_path,
            [("computes hash", True)],
        )
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        result = llm.analyse_component(comp)
        assert result is comp
        assert "openssl" in result.oss_hint

    @patch("llm.external_llm.completion")
    def test_only_approved_summaries_sent(self, mock_completion, tmp_path):
        mock_completion.return_value = _mock_completion("hint")
        comp = make_component_with_summaries(
            tmp_path,
            [
                ("approved summary", True),
                ("not approved", False),
            ],
        )
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        llm.analyse_component(comp)

        call_args = mock_completion.call_args[1]["messages"]
        user_content = next(m["content"] for m in call_args if m["role"] == "user")
        assert "approved summary" in user_content
        assert "not approved" not in user_content

    @patch("llm.external_llm.completion")
    def test_no_approved_summaries_skips_call(self, mock_completion, tmp_path):
        comp = make_component_with_summaries(
            tmp_path,
            [("unapproved", False)],
        )
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        llm.analyse_component(comp)
        mock_completion.assert_not_called()
        assert comp.oss_hint == ""

    @patch("llm.external_llm.completion")
    def test_error_summaries_excluded(self, mock_completion, tmp_path):
        mock_completion.return_value = _mock_completion("hint")
        comp = make_component_with_summaries(
            tmp_path,
            [
                ("[ERROR] LLM failed", True),   # approved but errored → skip
                ("valid summary", True),
            ],
        )
        llm = ExternalLLM("anthropic/claude-sonnet-4-6")
        llm.analyse_component(comp)

        user_content = next(
            m["content"]
            for m in mock_completion.call_args[1]["messages"]
            if m["role"] == "user"
        )
        assert "[ERROR]" not in user_content
        assert "valid summary" in user_content
