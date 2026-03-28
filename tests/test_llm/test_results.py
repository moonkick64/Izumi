"""Tests for llm.results.LLMResultsStore."""

from pathlib import Path
import json
import pytest

from analyzer.parser import FunctionInfo
from llm.results import LLMResultsStore


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_fn(tmp_path: Path, name: str = "my_func", start: int = 10) -> FunctionInfo:
    f = tmp_path / "foo.c"
    f.write_text("int my_func() { return 0; }")
    return FunctionInfo(
        name=name,
        file_path=f,
        start_line=start,
        end_line=start + 5,
        body="int my_func() { return 0; }",
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestLLMResultsStore:
    def test_exists_false_initially(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        assert not store.exists()

    def test_load_returns_empty_when_no_file(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        assert store.load() == []

    def test_save_creates_file(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="looks like zlib")
        assert store.exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="looks like zlib")

        results = store.load()
        assert len(results) == 1
        assert results[0]["function"] == "my_func"
        assert results[0]["hint"] == "looks like zlib"
        assert results[0]["option"] == 1
        assert results[0]["start_line"] == 10

    def test_file_path_stored_as_relative(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="hint")

        results = store.load()
        assert not Path(results[0]["file"]).is_absolute()

    def test_upsert_overwrites_existing(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="first")
        store.save_result(fn, option=1, hint="updated")

        results = store.load()
        assert len(results) == 1
        assert results[0]["hint"] == "updated"

    def test_multiple_functions_saved(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn1 = make_fn(tmp_path, name="func_a", start=1)
        fn2 = make_fn(tmp_path, name="func_b", start=20)
        store.save_result(fn1, option=1, hint="hint a")
        store.save_result(fn2, option=3, hint="hint b")

        results = store.load()
        assert len(results) == 2

    def test_hints_by_key(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="zlib crc32")

        hints = store.hints_by_key()
        assert len(hints) == 1
        key = (fn.file_path.resolve(), fn.name, fn.start_line)
        assert hints[key] == "zlib crc32"

    def test_delete_removes_file(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="hint")
        assert store.exists()

        store.delete()
        assert not store.exists()

    def test_delete_noop_when_no_file(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        store.delete()  # should not raise
        assert not store.exists()

    def test_load_returns_empty_on_corrupt_file(self, tmp_path):
        results_path = tmp_path / ".izumi" / "llm_results.json"
        results_path.parent.mkdir(parents=True)
        results_path.write_text("{ invalid json }")

        store = LLMResultsStore(tmp_path)
        assert store.load() == []

    def test_json_contains_source_root(self, tmp_path):
        store = LLMResultsStore(tmp_path)
        fn = make_fn(tmp_path)
        store.save_result(fn, option=1, hint="hint")

        raw = json.loads((tmp_path / ".izumi" / "llm_results.json").read_text())
        assert "source_root" in raw
        assert "created_at" in raw
        assert "updated_at" in raw
