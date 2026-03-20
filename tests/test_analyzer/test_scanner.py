"""Unit tests for analyzer.scanner."""

import pytest
from pathlib import Path

from analyzer.scanner import (
    FileInfo,
    ScanResult,
    scan_tree,
    _detect_third_party_dir,
    _find_closest_license,
    SOURCE_EXTENSIONS,
    THIRD_PARTY_DIR_NAMES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

def create_tree(tmp_path: Path, structure: dict) -> None:
    """Recursively create directories and files from a nested dict.

    Values can be strings (file content) or dicts (subdirectories).
    """
    for name, content in structure.items():
        path = tmp_path / name
        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            create_tree(path, content)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')


# ── scan_tree tests ───────────────────────────────────────────────────────

class TestScanTree:
    def test_finds_source_files(self, tmp_path):
        create_tree(tmp_path, {
            "main.c": "int main() {}",
            "util.h": "void util(void);",
            "README.md": "# readme",
        })
        result = scan_tree(tmp_path)
        names = {f.path.name for f in result.source_files}
        assert "main.c" in names
        assert "util.h" in names
        assert "README.md" not in names

    def test_finds_license_files(self, tmp_path):
        create_tree(tmp_path, {
            "LICENSE": "MIT License",
            "src": {"foo.c": "void foo() {}"},
        })
        result = scan_tree(tmp_path)
        assert any(lf.name == "LICENSE" for lf in result.license_files)

    def test_license_case_insensitive(self, tmp_path):
        create_tree(tmp_path, {
            "license.txt": "Apache License",
            "foo.c": "int x;",
        })
        result = scan_tree(tmp_path)
        assert len(result.license_files) == 1

    def test_license_associated_with_file(self, tmp_path):
        create_tree(tmp_path, {
            "src": {
                "LICENSE": "MIT",
                "foo.c": "void foo() {}",
            }
        })
        result = scan_tree(tmp_path)
        foo = next(f for f in result.source_files if f.path.name == "foo.c")
        assert foo.license_file is not None
        assert foo.license_file.name == "LICENSE"

    def test_license_in_parent_dir(self, tmp_path):
        create_tree(tmp_path, {
            "LICENSE": "GPL",
            "src": {"deep": {"bar.c": "void bar() {}"}},
        })
        result = scan_tree(tmp_path)
        bar = next(f for f in result.source_files if f.path.name == "bar.c")
        assert bar.license_file is not None

    def test_no_source_files(self, tmp_path):
        create_tree(tmp_path, {"README.md": "hello"})
        result = scan_tree(tmp_path)
        assert result.total_files == 0

    def test_progress_callback(self, tmp_path):
        create_tree(tmp_path, {"a.c": "void a(){}", "b.c": "void b(){}"})
        calls = []
        scan_tree(tmp_path, progress_callback=lambda i, n, p: calls.append((i, n)))
        assert len(calls) == 2

    def test_cpp_extensions_included(self, tmp_path):
        for ext in ['.cpp', '.hpp', '.cc', '.cxx']:
            (tmp_path / f"file{ext}").write_text("void f(){}", encoding='utf-8')
        result = scan_tree(tmp_path)
        assert result.total_files == 4

    def test_third_party_detected(self, tmp_path):
        create_tree(tmp_path, {
            "vendor": {"libfoo": {"foo.c": "void foo(){}"}},
        })
        result = scan_tree(tmp_path)
        foo = result.source_files[0]
        assert foo.third_party_dir == "vendor"


# ── _detect_third_party_dir tests ────────────────────────────────────────

class TestDetectThirdPartyDir:
    @pytest.mark.parametrize("dir_name", list(THIRD_PARTY_DIR_NAMES))
    def test_known_dir_names(self, tmp_path, dir_name):
        subdir = tmp_path / dir_name
        subdir.mkdir()
        file = subdir / "foo.c"
        result = _detect_third_party_dir(file, tmp_path)
        assert result == dir_name

    def test_non_third_party(self, tmp_path):
        file = tmp_path / "src" / "foo.c"
        result = _detect_third_party_dir(file, tmp_path)
        assert result is None

    def test_nested_third_party(self, tmp_path):
        file = tmp_path / "src" / "vendor" / "lib" / "foo.c"
        result = _detect_third_party_dir(file, tmp_path)
        assert result == "vendor"

    def test_file_not_under_root(self, tmp_path):
        file = Path("/tmp/other/foo.c")
        result = _detect_third_party_dir(file, tmp_path)
        assert result is None
