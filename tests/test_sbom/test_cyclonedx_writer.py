# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Unit tests for sbom.cyclonedx_writer."""

import json
import pytest
from pathlib import Path

from analyzer.classifier import Classification
from analyzer.models import Component
from sbom.cyclonedx_writer import write_cyclonedx


# ── Fixtures ──────────────────────────────────────────────────────────────

def make_component(
    name: str,
    directory: Path,
    classification: Classification = Classification.CONFIRMED,
    license_expression: str | None = "MIT",
    copyright_texts: list[str] | None = None,
    version: str | None = "1.0.0",
    oss_hint: str | None = None,
) -> Component:
    return Component(
        name=name,
        directory=directory,
        classification=classification,
        classification_reason="test",
        license_expression=license_expression,
        copyright_texts=copyright_texts or ["Copyright 2020 Test"],
        version=version,
        oss_hint=oss_hint,
    )


# ── write_cyclonedx tests ─────────────────────────────────────────────────

class TestWriteCyclonedx:
    def test_writes_json(self, tmp_path):
        comp = make_component("mylib", tmp_path)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert "bomFormat" in data
        assert data["bomFormat"] == "CycloneDX"

    def test_writes_xml(self, tmp_path):
        comp = make_component("mylib", tmp_path)
        out = tmp_path / "bom.xml"
        write_cyclonedx([comp], out, output_format="xml")
        assert out.exists()
        content = out.read_text()
        assert "<?xml" in content
        assert "cyclonedx.org" in content

    def test_component_name_in_json(self, tmp_path):
        comp = make_component("zlib", tmp_path)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        names = [c["name"] for c in data.get("components", [])]
        assert "zlib" in names

    def test_component_version_in_json(self, tmp_path):
        comp = make_component("zlib", tmp_path, version="1.2.11")
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        versions = [c.get("version") for c in data.get("components", [])]
        assert "1.2.11" in versions

    def test_multiple_components(self, tmp_path):
        comp1 = make_component("zlib", tmp_path)
        comp2 = make_component("openssl", tmp_path, license_expression="OpenSSL")
        out = tmp_path / "bom.json"
        write_cyclonedx([comp1, comp2], out, output_format="json")
        data = json.loads(out.read_text())
        names = [c["name"] for c in data.get("components", [])]
        assert "zlib" in names
        assert "openssl" in names

    def test_empty_components(self, tmp_path):
        out = tmp_path / "bom.json"
        write_cyclonedx([], out, output_format="json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data.get("components", []) == []

    def test_no_license(self, tmp_path):
        comp = make_component("noinfo", tmp_path, license_expression=None)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        assert out.exists()

    def test_classification_property_present(self, tmp_path):
        comp = make_component(
            "unknown-lib",
            tmp_path,
            classification=Classification.UNKNOWN,
            license_expression=None,
        )
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        # Find the component and check its properties
        comps = data.get("components", [])
        assert len(comps) == 1
        props = {p["name"]: p["value"] for p in comps[0].get("properties", [])}
        assert props.get("izumi:classification") == "UNKNOWN"

    def test_oss_hint_property_present(self, tmp_path):
        comp = make_component(
            "mystery",
            tmp_path,
            oss_hint="Possibly zlib",
            license_expression=None,
        )
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        comps = data.get("components", [])
        props = {p["name"]: p["value"] for p in comps[0].get("properties", [])}
        assert "Possibly zlib" in props.get("izumi:oss_hint", "")

    def test_project_name_in_metadata(self, tmp_path):
        comp = make_component("zlib", tmp_path)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json", project_name="my-firmware")
        data = json.loads(out.read_text())
        metadata_comp = data.get("metadata", {}).get("component", {})
        assert metadata_comp.get("name") == "my-firmware"

    def test_project_version_in_metadata(self, tmp_path):
        comp = make_component("zlib", tmp_path)
        out = tmp_path / "bom.json"
        write_cyclonedx(
            [comp], out, output_format="json",
            project_name="my-firmware", project_version="1.2.3",
        )
        data = json.loads(out.read_text())
        metadata_comp = data.get("metadata", {}).get("component", {})
        assert metadata_comp.get("version") == "1.2.3"

    def test_no_project_name_no_metadata_component(self, tmp_path):
        comp = make_component("zlib", tmp_path)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        assert "component" not in data.get("metadata", {})

    # ── NTIA element tests ────────────────────────────────────────────────

    def test_purl_present_for_component(self, tmp_path):
        comp = make_component("zlib", tmp_path, version="1.2.11")
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        purls = [c.get("purl", "") for c in data.get("components", [])]
        assert any("pkg:generic/zlib" in p for p in purls)

    def test_purl_includes_version_when_known(self, tmp_path):
        comp = make_component("zlib", tmp_path, version="1.2.11")
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        purls = [c.get("purl", "") for c in data.get("components", [])]
        assert any("pkg:generic/zlib@1.2.11" in p for p in purls)

    def test_version_omitted_when_unknown(self, tmp_path):
        comp = make_component("zlib", tmp_path, version=None)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        comps = data.get("components", [])
        assert len(comps) == 1
        assert "version" not in comps[0]

    def test_no_fake_version_placeholder(self, tmp_path):
        comp = make_component("zlib", tmp_path, version=None)
        out = tmp_path / "bom.json"
        write_cyclonedx([comp], out, output_format="json")
        data = json.loads(out.read_text())
        comps = data.get("components", [])
        assert comps[0].get("version") not in ("NOASSERTION", "unknown", "")
