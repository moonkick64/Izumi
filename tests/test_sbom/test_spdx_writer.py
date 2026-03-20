"""Unit tests for sbom.spdx_writer."""

import pytest
from pathlib import Path

from analyzer.classifier import Classification
from analyzer.models import Component
from sbom.spdx_writer import write_spdx, _spdx_safe_id


# ── Fixtures ──────────────────────────────────────────────────────────────

def confirmed_component(directory: Path) -> Component:
    return Component(
        name="zlib",
        directory=directory,
        files=[directory / "zlib.c"],
        classification=Classification.CONFIRMED,
        classification_reason="SPDX-License-Identifier: Zlib",
        license_expression="Zlib",
        copyright_texts=["Copyright 1995-2022 Jean-loup Gailly and Mark Adler"],
        version="1.2.11",
    )


def unknown_component(directory: Path) -> Component:
    return Component(
        name="mystery-lib",
        directory=directory,
        files=[directory / "mystery.c"],
        classification=Classification.UNKNOWN,
        classification_reason="No copyright or license found",
        oss_hint="Possibly similar to cJSON",
        user_comment="Needs manual review",
    )


# ── _spdx_safe_id tests ───────────────────────────────────────────────────

class TestSpdxSafeId:
    def test_plain_name(self):
        assert _spdx_safe_id("zlib") == "zlib"

    def test_spaces_replaced(self):
        result = _spdx_safe_id("my lib")
        assert " " not in result

    def test_leading_digit(self):
        result = _spdx_safe_id("1stlib")
        assert not result[0].isdigit()

    def test_empty_string(self):
        result = _spdx_safe_id("")
        assert result  # Not empty

    def test_special_chars(self):
        result = _spdx_safe_id("lib/foo.bar")
        assert "/" not in result
        assert "." not in result


# ── write_spdx tests ──────────────────────────────────────────────────────

class TestWriteSpdx:
    def test_writes_json(self, tmp_path):
        comp = confirmed_component(tmp_path)
        out = tmp_path / "sbom.json"
        write_spdx([comp], out)
        assert out.exists()
        content = out.read_text()
        assert "zlib" in content
        assert "SPDX" in content

    def test_writes_tag_value(self, tmp_path):
        comp = confirmed_component(tmp_path)
        out = tmp_path / "sbom.spdx"
        write_spdx([comp], out)
        assert out.exists()
        content = out.read_text()
        assert "PackageName: zlib" in content

    def test_writes_yaml(self, tmp_path):
        comp = confirmed_component(tmp_path)
        out = tmp_path / "sbom.yaml"
        write_spdx([comp], out)
        assert out.exists()
        content = out.read_text()
        assert "zlib" in content

    def test_multiple_components(self, tmp_path):
        comp1 = confirmed_component(tmp_path)
        comp2 = unknown_component(tmp_path)
        out = tmp_path / "sbom.spdx"
        write_spdx([comp1, comp2], out)
        content = out.read_text()
        assert "zlib" in content
        assert "mystery-lib" in content

    def test_empty_components(self, tmp_path):
        out = tmp_path / "sbom.spdx"
        write_spdx([], out)
        assert out.exists()

    def test_component_without_license(self, tmp_path):
        comp = Component(
            name="noinfo",
            directory=tmp_path,
            classification=Classification.UNKNOWN,
            classification_reason="test",
        )
        out = tmp_path / "sbom.spdx"
        write_spdx([comp], out)
        content = out.read_text()
        assert "noinfo" in content

    def test_oss_hint_in_comment(self, tmp_path):
        comp = unknown_component(tmp_path)
        out = tmp_path / "sbom.spdx"
        write_spdx([comp], out)
        content = out.read_text()
        assert "cJSON" in content

    def test_document_name_in_output(self, tmp_path):
        comp = confirmed_component(tmp_path)
        out = tmp_path / "sbom.spdx"
        write_spdx([comp], out, document_name="MyProject-SBOM")
        content = out.read_text()
        assert "MyProject-SBOM" in content
