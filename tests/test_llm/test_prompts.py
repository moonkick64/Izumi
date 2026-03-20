"""Unit tests for llm.prompts."""

import pytest
from llm.prompts import (
    format_summarise_prompt,
    format_oss_similarity_prompt,
    SUMMARISE_FUNCTION_SYSTEM,
    OSS_SIMILARITY_SYSTEM,
)


class TestFormatSummarisePrompt:
    def test_returns_two_messages(self):
        msgs = format_summarise_prompt("void foo() {}")
        assert len(msgs) == 2

    def test_system_role(self):
        msgs = format_summarise_prompt("void foo() {}")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == SUMMARISE_FUNCTION_SYSTEM

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
        assert msgs[0]["content"] == OSS_SIMILARITY_SYSTEM

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
