"""Unit tests for llm.prompts."""

import pytest
from i18n import t
from llm.prompts import (
    format_summarise_prompt,
    format_oss_similarity_prompt,
    format_direct_oss_prompt,
    parse_oss_response,
)


class TestFormatSummarisePrompt:
    def test_returns_two_messages(self):
        msgs = format_summarise_prompt("void foo() {}")
        assert len(msgs) == 2

    def test_system_role(self):
        msgs = format_summarise_prompt("void foo() {}")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == t("prompt_summarise_system")

    def test_user_role(self):
        msgs = format_summarise_prompt("void foo() {}")
        assert msgs[1]["role"] == "user"

    def test_function_body_included(self):
        body = "int add(int a, int b) { return a + b; }"
        msgs = format_summarise_prompt(body)
        assert body in msgs[1]["content"]

    def test_empty_body(self):
        msgs = format_summarise_prompt("")
        assert msgs[1]["role"] == "user"


class TestFormatOssSimilarityPrompt:
    def test_returns_two_messages(self):
        msgs = format_oss_similarity_prompt(["computes CRC32"])
        assert len(msgs) == 2

    def test_system_role(self):
        msgs = format_oss_similarity_prompt(["foo"])
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == t("prompt_oss_similarity_system")

    def test_summaries_numbered(self):
        msgs = format_oss_similarity_prompt(["first summary", "second summary"])
        content = msgs[1]["content"]
        assert "1." in content
        assert "2." in content
        assert "first summary" in content
        assert "second summary" in content

    def test_single_summary(self):
        msgs = format_oss_similarity_prompt(["computes CRC32 checksum"])
        assert "computes CRC32 checksum" in msgs[1]["content"]

    def test_empty_list(self):
        msgs = format_oss_similarity_prompt([])
        assert msgs[1]["role"] == "user"


class TestParseOssResponse:
    def test_valid_json(self):
        result = parse_oss_response('{"component": "zlib 1.2.11", "license": "Zlib", "hint": "CRC32 match"}')
        assert result == ("zlib 1.2.11", "Zlib", "CRC32 match")

    def test_noassertion(self):
        result = parse_oss_response('{"component": "NOASSERTION", "license": "NOASSERTION", "hint": "No match"}')
        assert result == ("NOASSERTION", "NOASSERTION", "No match")

    def test_markdown_fence(self):
        result = parse_oss_response('```json\n{"component": "openssl 3.0", "license": "Apache-2.0", "hint": "TLS"}\n```')
        assert result == ("openssl 3.0", "Apache-2.0", "TLS")

    def test_missing_hint_field(self):
        result = parse_oss_response('{"component": "zlib", "license": "Zlib"}')
        assert result == ("zlib", "Zlib", "")

    def test_free_text_returns_none(self):
        assert parse_oss_response("I think this might be zlib.") is None

    def test_empty_string_returns_none(self):
        assert parse_oss_response("") is None

    def test_error_prefix_returns_none(self):
        assert parse_oss_response("[ERROR] LLM call failed") is None
