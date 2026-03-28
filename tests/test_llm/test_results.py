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


def make_store(tmp_path: Path) -> LLMResultsStore:
    """Create a store that writes under tmp_path/app instead of ~/.izumi."""
    source_root = tmp_path / "project"
    source_root.mkdir()
    return LLMResultsStore(source_root, app_dir=tmp_path / "app")


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestLLMResultsStore:
    def test_exists_false_initially(self, tmp_path):
        store = make_store(tmp_path)
        assert not store.exists()

    def test_load_returns_empty_when_no_file(self, tmp_path):
        store = make_store(tmp_path)
        assert store.load() == []

    def test_save_creates_file(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="looks like zlib")
        assert store.exists()

    def test_results_stored_under_app_dir(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="hint")
        assert store._results_path.is_relative_to(tmp_path / "app")

    def test_save_and_load_roundtrip(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="looks like zlib")

        results = store.load()
        assert len(results) == 1
        assert results[0]["function"] == "my_func"
        assert results[0]["hint"] == "looks like zlib"
        assert results[0]["option"] == 1
        assert results[0]["start_line"] == 10

    def test_file_path_stored_as_relative(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="hint")

        results = store.load()
        assert not Path(results[0]["file"]).is_absolute()

    def test_upsert_overwrites_existing(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="first")
        store.save_result(fn, option=1, hint="updated")

        results = store.load()
        assert len(results) == 1
        assert results[0]["hint"] == "updated"

    def test_multiple_functions_saved(self, tmp_path):
        store = make_store(tmp_path)
        fn1 = make_fn(store._source_root, name="func_a", start=1)
        fn2 = make_fn(store._source_root, name="func_b", start=20)
        store.save_result(fn1, option=1, hint="hint a")
        store.save_result(fn2, option=3, hint="hint b")

        results = store.load()
        assert len(results) == 2

    def test_hints_by_key(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="zlib crc32")

        hints = store.hints_by_key()
        assert len(hints) == 1
        key = (fn.file_path.resolve(), fn.name, fn.start_line)
        assert hints[key] == "zlib crc32"

    def test_delete_removes_file(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="hint")
        assert store.exists()

        store.delete()
        assert not store.exists()

    def test_delete_noop_when_no_file(self, tmp_path):
        store = make_store(tmp_path)
        store.delete()  # should not raise
        assert not store.exists()

    def test_load_returns_empty_on_corrupt_file(self, tmp_path):
        store = make_store(tmp_path)
        store._results_path.parent.mkdir(parents=True, exist_ok=True)
        store._results_path.write_text("{ invalid json }")
        assert store.load() == []

    def test_json_contains_metadata(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="hint")

        raw = json.loads(store._results_path.read_text())
        assert "source_root" in raw
        assert "created_at" in raw
        assert "updated_at" in raw

    def test_source_root_recorded_as_absolute(self, tmp_path):
        store = make_store(tmp_path)
        fn = make_fn(store._source_root)
        store.save_result(fn, option=1, hint="hint")

        raw = json.loads(store._results_path.read_text())
        assert Path(raw["source_root"]).is_absolute()

    def test_different_projects_use_different_dirs(self, tmp_path):
        src_a = tmp_path / "project_a"
        src_b = tmp_path / "project_b"
        src_a.mkdir()
        src_b.mkdir()
        app_dir = tmp_path / "app"

        store_a = LLMResultsStore(src_a, app_dir=app_dir)
        store_b = LLMResultsStore(src_b, app_dir=app_dir)

        assert store_a._results_path != store_b._results_path
