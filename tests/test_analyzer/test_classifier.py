"""Unit tests for analyzer.classifier."""

import pytest
from pathlib import Path

from analyzer.copyright import CopyrightInfo
from analyzer.scanner import FileInfo, ScanResult
from analyzer.classifier import (
    Classification,
    ClassifiedFile,
    ClassificationResult,
    classify,
    _classify_file,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def make_file_info(
    path: Path = Path("/src/foo.c"),
    *,
    spdx_license_id: str | None = None,
    copyright_texts: list[str] | None = None,
    spdx_copyright_texts: list[str] | None = None,
    license_file: Path | None = None,
    third_party_dir: str | None = None,
) -> FileInfo:
    ci = CopyrightInfo(
        spdx_license_id=spdx_license_id,
        copyright_texts=copyright_texts or [],
        spdx_copyright_texts=spdx_copyright_texts or [],
    )
    return FileInfo(
        path=path,
        copyright_info=ci,
        license_file=license_file,
        third_party_dir=third_party_dir,
    )


# ── _classify_file (unit) tests ───────────────────────────────────────────

class TestClassifyFile:
    # ── CONFIRMED rules ───────────────────────────────────────────────────

    def test_confirmed_spdx_license_id(self):
        fi = make_file_info(spdx_license_id="MIT")
        cf = _classify_file(fi)
        assert cf.classification == Classification.CONFIRMED
        assert "MIT" in cf.reason

    def test_confirmed_spdx_with_copyright(self):
        fi = make_file_info(
            spdx_license_id="Apache-2.0",
            spdx_copyright_texts=["2021 Foo Corp"],
        )
        cf = _classify_file(fi)
        assert cf.classification == Classification.CONFIRMED

    def test_confirmed_license_file_same_dir(self, tmp_path):
        src = tmp_path / "foo.c"
        lic = tmp_path / "LICENSE"
        fi = make_file_info(path=src, license_file=lic)
        cf = _classify_file(fi)
        assert cf.classification == Classification.CONFIRMED
        assert "LICENSE" in cf.reason

    def test_not_confirmed_license_file_in_parent_dir(self, tmp_path):
        src = tmp_path / "sub" / "foo.c"
        lic = tmp_path / "LICENSE"
        # License is in parent dir, not same dir → should NOT be CONFIRMED
        fi = make_file_info(path=src, license_file=lic)
        cf = _classify_file(fi)
        assert cf.classification != Classification.CONFIRMED

    # ── INFERRED rules ────────────────────────────────────────────────────

    def test_inferred_copyright_text(self):
        fi = make_file_info(copyright_texts=["Copyright 2020 Acme"])
        cf = _classify_file(fi)
        assert cf.classification == Classification.INFERRED
        assert "Copyright" in cf.reason

    def test_inferred_spdx_copyright_text(self):
        fi = make_file_info(spdx_copyright_texts=["2020 Acme Corp"])
        cf = _classify_file(fi)
        assert cf.classification == Classification.INFERRED

    def test_confirmed_third_party_license_same_dir(self, tmp_path):
        """LICENSE in same dir takes precedence → CONFIRMED, even in vendor."""
        lic = tmp_path / "vendor" / "libz" / "LICENSE"
        fi = make_file_info(
            path=tmp_path / "vendor" / "libz" / "foo.c",
            third_party_dir="vendor",
            license_file=lic,
        )
        cf = _classify_file(fi)
        assert cf.classification == Classification.CONFIRMED
        assert "LICENSE" in cf.reason

    def test_inferred_third_party_with_parent_license(self, tmp_path):
        """LICENSE in parent dir + third-party dir → INFERRED."""
        lic = tmp_path / "vendor" / "LICENSE"
        fi = make_file_info(
            path=tmp_path / "vendor" / "libz" / "foo.c",
            third_party_dir="vendor",
            license_file=lic,
        )
        cf = _classify_file(fi)
        assert cf.classification == Classification.INFERRED
        assert "vendor" in cf.reason

    def test_inferred_third_party_no_license(self):
        fi = make_file_info(third_party_dir="extern")
        cf = _classify_file(fi)
        assert cf.classification == Classification.INFERRED
        assert "extern" in cf.reason

    # ── UNKNOWN ───────────────────────────────────────────────────────────

    def test_unknown_no_info(self):
        fi = make_file_info()
        cf = _classify_file(fi)
        assert cf.classification == Classification.UNKNOWN

    def test_unknown_license_file_in_parent_no_copyright(self, tmp_path):
        # Parent dir has LICENSE but file itself has no copyright → UNKNOWN
        # (parent LICENSE alone is not enough for CONFIRMED or INFERRED)
        src = tmp_path / "sub" / "foo.c"
        lic = tmp_path / "LICENSE"
        fi = make_file_info(path=src, license_file=lic)
        cf = _classify_file(fi)
        assert cf.classification == Classification.UNKNOWN

    # ── Rule precedence ───────────────────────────────────────────────────

    def test_spdx_takes_precedence_over_copyright(self):
        fi = make_file_info(
            spdx_license_id="MIT",
            copyright_texts=["Copyright 2020 Foo"],
        )
        cf = _classify_file(fi)
        assert cf.classification == Classification.CONFIRMED
        assert "MIT" in cf.reason


# ── classify (integration) tests ─────────────────────────────────────────

class TestClassify:
    def _make_scan(self, files: list[FileInfo], root: Path = Path("/root")) -> ScanResult:
        return ScanResult(root_path=root, source_files=files)

    def test_empty_scan(self):
        result = classify(self._make_scan([]))
        assert result.summary() == {'confirmed': 0, 'inferred': 0, 'unknown': 0, 'total': 0}

    def test_mixed_classification(self):
        files = [
            make_file_info(spdx_license_id="MIT"),
            make_file_info(copyright_texts=["Copyright 2020 Foo"]),
            make_file_info(),
        ]
        result = classify(self._make_scan(files))
        assert len(result.confirmed) == 1
        assert len(result.inferred) == 1
        assert len(result.unknown) == 1

    def test_summary_totals_match(self):
        files = [make_file_info() for _ in range(5)]
        result = classify(self._make_scan(files))
        s = result.summary()
        assert s['total'] == s['confirmed'] + s['inferred'] + s['unknown']

    def test_all_files_property(self):
        files = [
            make_file_info(spdx_license_id="GPL-2.0"),
            make_file_info(third_party_dir="vendor"),
            make_file_info(),
        ]
        result = classify(self._make_scan(files))
        assert len(result.all_files) == 3

    def test_from_scan_result(self, tmp_path):
        """Integration: scan a real temp tree then classify."""
        (tmp_path / "app.c").write_text(
            "// SPDX-License-Identifier: MIT\nvoid app(){}", encoding='utf-8'
        )
        vendor = tmp_path / "vendor" / "libz"
        vendor.mkdir(parents=True)
        (vendor / "zlib.c").write_text("void compress(){}", encoding='utf-8')
        own = tmp_path / "src"
        own.mkdir()
        (own / "secret.c").write_text("void proprietary(){}", encoding='utf-8')

        from analyzer.scanner import scan_tree
        scan = scan_tree(tmp_path)
        result = classify(scan)

        assert any(cf.classification == Classification.CONFIRMED for cf in result.all_files)
        assert any(cf.classification == Classification.INFERRED for cf in result.all_files)
        assert any(cf.classification == Classification.UNKNOWN for cf in result.all_files)
