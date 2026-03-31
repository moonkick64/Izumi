# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Unit tests for analyzer.grouper."""

import pytest
from pathlib import Path

from analyzer.classifier import Classification, ClassifiedFile, ClassificationResult
from analyzer.copyright import CopyrightInfo
from analyzer.grouper import (
    group_into_components,
    _component_key,
    _component_name,
    _subdir_under_third_party,
)
from analyzer.scanner import FileInfo


# ── Helpers ───────────────────────────────────────────────────────────────

def make_fi(
    path: Path,
    *,
    spdx_id: str | None = None,
    copyright_texts: list[str] | None = None,
    license_file: Path | None = None,
    third_party_dir: str | None = None,
) -> FileInfo:
    ci = CopyrightInfo(
        spdx_license_id=spdx_id,
        copyright_texts=copyright_texts or [],
    )
    return FileInfo(
        path=path,
        copyright_info=ci,
        license_file=license_file,
        third_party_dir=third_party_dir,
    )


def make_cf(fi: FileInfo, cls: Classification, reason: str = "test") -> ClassifiedFile:
    return ClassifiedFile(file_info=fi, classification=cls, reason=reason)


def make_result(*cfs: ClassifiedFile) -> ClassificationResult:
    r = ClassificationResult()
    for cf in cfs:
        if cf.classification == Classification.CONFIRMED:
            r.confirmed.append(cf)
        elif cf.classification == Classification.INFERRED:
            r.inferred.append(cf)
        else:
            r.unknown.append(cf)
    return r


# ── group_into_components tests ───────────────────────────────────────────

class TestGroupIntoComponents:
    def test_empty(self, tmp_path):
        result = make_result()
        comps = group_into_components(result, tmp_path)
        assert comps == []

    def test_single_unknown_file(self, tmp_path):
        fi = make_fi(tmp_path / "src" / "foo.c")
        cf = make_cf(fi, Classification.UNKNOWN)
        comps = group_into_components(make_result(cf), tmp_path)
        assert len(comps) == 1
        assert comps[0].classification == Classification.UNKNOWN
        assert comps[0].name == "src"

    def test_files_same_dir_grouped(self, tmp_path):
        fi1 = make_fi(tmp_path / "src" / "a.c")
        fi2 = make_fi(tmp_path / "src" / "b.c")
        result = make_result(
            make_cf(fi1, Classification.UNKNOWN),
            make_cf(fi2, Classification.UNKNOWN),
        )
        comps = group_into_components(result, tmp_path)
        assert len(comps) == 1
        assert len(comps[0].files) == 2

    def test_files_different_dirs_separate(self, tmp_path):
        fi1 = make_fi(tmp_path / "src" / "a.c")
        fi2 = make_fi(tmp_path / "lib" / "b.c")
        result = make_result(
            make_cf(fi1, Classification.UNKNOWN),
            make_cf(fi2, Classification.UNKNOWN),
        )
        comps = group_into_components(result, tmp_path)
        assert len(comps) == 2

    def test_grouped_by_license_file(self, tmp_path):
        lic = tmp_path / "vendor" / "zlib" / "LICENSE"
        fi1 = make_fi(tmp_path / "vendor" / "zlib" / "a.c", license_file=lic)
        fi2 = make_fi(tmp_path / "vendor" / "zlib" / "b.c", license_file=lic)
        result = make_result(
            make_cf(fi1, Classification.CONFIRMED),
            make_cf(fi2, Classification.CONFIRMED),
        )
        comps = group_into_components(result, tmp_path)
        assert len(comps) == 1
        assert comps[0].name == "zlib"

    def test_third_party_subdir_grouping(self, tmp_path):
        fi1 = make_fi(
            tmp_path / "vendor" / "zlib" / "a.c",
            third_party_dir="vendor",
        )
        fi2 = make_fi(
            tmp_path / "vendor" / "openssl" / "b.c",
            third_party_dir="vendor",
        )
        result = make_result(
            make_cf(fi1, Classification.INFERRED),
            make_cf(fi2, Classification.INFERRED),
        )
        comps = group_into_components(result, tmp_path)
        assert len(comps) == 2
        names = {c.name for c in comps}
        assert "zlib" in names
        assert "openssl" in names

    def test_confirmed_takes_priority_over_inferred(self, tmp_path):
        lic = tmp_path / "lib" / "LICENSE"
        fi1 = make_fi(tmp_path / "lib" / "a.c", license_file=lic, spdx_id="MIT")
        fi2 = make_fi(tmp_path / "lib" / "b.c", license_file=lic, copyright_texts=["Copyright 2020 Foo"])
        cf1 = make_cf(fi1, Classification.CONFIRMED)
        cf2 = make_cf(fi2, Classification.INFERRED)
        comps = group_into_components(make_result(cf1, cf2), tmp_path)
        assert len(comps) == 1
        assert comps[0].classification == Classification.CONFIRMED

    def test_license_expression_collected(self, tmp_path):
        fi = make_fi(tmp_path / "a.c", spdx_id="MIT")
        cf = make_cf(fi, Classification.CONFIRMED)
        comps = group_into_components(make_result(cf), tmp_path)
        assert comps[0].license_expression == "MIT"

    def test_copyright_texts_collected(self, tmp_path):
        fi = make_fi(tmp_path / "a.c", copyright_texts=["Copyright 2020 Acme"])
        cf = make_cf(fi, Classification.INFERRED)
        comps = group_into_components(make_result(cf), tmp_path)
        assert "Copyright 2020 Acme" in comps[0].copyright_texts

    def test_copyright_deduplication(self, tmp_path):
        fi1 = make_fi(tmp_path / "src" / "a.c", copyright_texts=["Copyright 2020 Foo"])
        fi2 = make_fi(tmp_path / "src" / "b.c", copyright_texts=["Copyright 2020 Foo"])
        result = make_result(
            make_cf(fi1, Classification.INFERRED),
            make_cf(fi2, Classification.INFERRED),
        )
        comps = group_into_components(result, tmp_path)
        assert comps[0].copyright_texts.count("Copyright 2020 Foo") == 1

    def test_integration_full_tree(self, tmp_path):
        """Full tree: confirmed SPDX file + inferred vendor + unknown own code."""
        # CONFIRMED: SPDX tag in own header
        fi_conf = make_fi(tmp_path / "include" / "api.h", spdx_id="MIT")

        # INFERRED: in vendor dir
        fi_inf = make_fi(
            tmp_path / "vendor" / "zlib" / "zlib.c",
            third_party_dir="vendor",
            copyright_texts=["Copyright 1995 Jean-loup Gailly"],
        )

        # UNKNOWN: no info
        fi_unk = make_fi(tmp_path / "src" / "engine.c")

        result = make_result(
            make_cf(fi_conf, Classification.CONFIRMED),
            make_cf(fi_inf, Classification.INFERRED),
            make_cf(fi_unk, Classification.UNKNOWN),
        )
        comps = group_into_components(result, tmp_path)
        assert len(comps) == 3
        classes = {c.classification for c in comps}
        assert Classification.CONFIRMED in classes
        assert Classification.INFERRED in classes
        assert Classification.UNKNOWN in classes


# ── _component_name tests ─────────────────────────────────────────────────

class TestComponentName:
    def test_skips_third_party_dir_name(self, tmp_path):
        key = tmp_path / "vendor" / "zlib"
        name = _component_name(key, tmp_path)
        assert name == "zlib"

    def test_plain_dir(self, tmp_path):
        key = tmp_path / "mylib"
        name = _component_name(key, tmp_path)
        assert name == "mylib"

    def test_root_itself(self, tmp_path):
        name = _component_name(tmp_path, tmp_path)
        # Falls back to directory name
        assert name == tmp_path.name
