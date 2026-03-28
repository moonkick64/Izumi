"""Unit tests for llm.local_llm (LiteLLM calls are mocked)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from analyzer.classifier import Classification
from analyzer.models import Component, FunctionSummary
from llm.local_llm import LocalLLM


# ── Fixtures ──────────────────────────────────────────────────────────────

def make_component(tmp_path: Path, name: str = "mystery") -> Component:
    return Component(
        name=name,
        directory=tmp_path,
        classification=Classification.UNKNOWN,
        classification_reason="no info",
    )


def _mock_completion(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    return response


# ── summarise_function tests ──────────────────────────────────────────────

class TestSummariseFunction:
    @patch("llm.local_llm.completion")
    def test_returns_summary(self, mock_completion):
        mock_completion.return_value = _mock_completion("Computes a CRC32 checksum.")
        llm = LocalLLM("ollama/codellama")
        result = llm.summarise_function("uint32_t crc32(const uint8_t *data, size_t len) {...}")
        assert result == "Computes a CRC32 checksum."

    @patch("llm.local_llm.completion")
    def test_strips_whitespace(self, mock_completion):
        mock_completion.return_value = _mock_completion("  Summary text.  \n")
        llm = LocalLLM("ollama/codellama")
        result = llm.summarise_function("void foo() {}")
        assert result == "Summary text."

    @patch("llm.local_llm.completion")
    def test_error_returns_error_prefix(self, mock_completion):
        mock_completion.side_effect = Exception("connection refused")
        llm = LocalLLM("ollama/codellama")
        result = llm.summarise_function("void foo() {}")
        assert result.startswith("[ERROR]")
        assert "connection refused" in result

    @patch("llm.local_llm.completion")
    def test_correct_model_and_api_base_used(self, mock_completion):
        mock_completion.return_value = _mock_completion("ok")
        llm = LocalLLM(model="ollama/mistral", api_base="http://myserver:11434")
        llm.summarise_function("void f() {}")
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "ollama/mistral"
        assert call_kwargs["api_base"] == "http://myserver:11434"


# ── summarise_component tests ─────────────────────────────────────────────

class TestSummariseComponent:
    @patch("llm.local_llm.completion")
    def test_populates_function_summaries(self, mock_completion, tmp_path):
        mock_completion.return_value = _mock_completion("Does something.")

        # Create a simple C file with a function
        c_file = tmp_path / "foo.c"
        c_file.write_text("void foo(void) { int x = 1; }\n", encoding="utf-8")

        comp = make_component(tmp_path)
        comp.files = [c_file]

        llm = LocalLLM("ollama/codellama")
        result = llm.summarise_component(comp)

        assert result is comp  # Returns the same object
        assert len(result.function_summaries) >= 1

    @patch("llm.local_llm.completion")
    def test_empty_files_no_summaries(self, mock_completion, tmp_path):
        comp = make_component(tmp_path)
        comp.files = []
        llm = LocalLLM("ollama/codellama")
        result = llm.summarise_component(comp)
        assert result.function_summaries == []

    @patch("llm.local_llm.completion")
    def test_progress_callback_called(self, mock_completion, tmp_path):
        mock_completion.return_value = _mock_completion("Summary.")

        c_file = tmp_path / "bar.c"
        c_file.write_text("void bar(void) { return; }\n", encoding="utf-8")

        comp = make_component(tmp_path)
        comp.files = [c_file]

        calls = []
        llm = LocalLLM("ollama/codellama")
        llm.summarise_component(comp, progress_callback=lambda i, n, name: calls.append((i, n, name)))

        assert len(calls) >= 1

    @patch("llm.local_llm.completion")
    def test_summary_info_fields_populated(self, mock_completion, tmp_path):
        mock_completion.return_value = _mock_completion("Does X.")

        c_file = tmp_path / "baz.c"
        c_file.write_text("int baz(int x) { return x * 2; }\n", encoding="utf-8")

        comp = make_component(tmp_path)
        comp.files = [c_file]

        llm = LocalLLM("ollama/codellama")
        llm.summarise_component(comp)

        if comp.function_summaries:
            fs = comp.function_summaries[0]
            assert fs.function_name
            assert fs.file_path == c_file
            assert fs.start_line >= 1
            assert fs.summary == "Does X."


# ── is_available tests ────────────────────────────────────────────────────

class TestIsAvailable:
    @patch("llm.local_llm.urllib.request.urlopen")
    def test_available_when_endpoint_reachable(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        llm = LocalLLM("ollama/codellama")
        assert llm.is_available() is True

    @patch("llm.local_llm.urllib.request.urlopen")
    def test_not_available_on_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("refused")
        llm = LocalLLM("ollama/codellama")
        assert llm.is_available() is False
