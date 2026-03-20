"""Tests for gui.sbom_view."""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from analyzer.classifier import Classification
from analyzer.models import Component
from gui.sbom_view import SbomView


def make_component(name: str, cls: Classification, tmp_path: Path) -> Component:
    return Component(
        name=name,
        directory=tmp_path,
        classification=cls,
        classification_reason="test",
        license_expression="MIT" if cls == Classification.CONFIRMED else None,
        files=[tmp_path / f"{name}.c"],
    )


class TestSbomView:
    def test_creates_without_error(self, qtbot):
        view = SbomView()
        qtbot.addWidget(view)

    def test_set_components_populates_table(self, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        comps = [
            make_component("zlib", Classification.CONFIRMED, tmp_path),
            make_component("mystery", Classification.UNKNOWN, tmp_path),
        ]
        view.set_components(comps)

        assert view._table.rowCount() == 2
        assert view._table.item(0, 0).text() == "zlib"
        assert view._table.item(1, 0).text() == "mystery"

    def test_classification_shown_in_table(self, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        comp = make_component("zlib", Classification.CONFIRMED, tmp_path)
        view.set_components([comp])

        assert view._table.item(0, 1).text() == "CONFIRMED"

    def test_license_shown_in_table(self, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        comp = make_component("zlib", Classification.CONFIRMED, tmp_path)
        view.set_components([comp])

        assert view._table.item(0, 2).text() == "MIT"

    def test_unknown_license_shows_fallback(self, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        comp = make_component("mystery", Classification.UNKNOWN, tmp_path)
        view.set_components([comp])

        assert view._table.item(0, 2).text() == "不明"

    def test_back_signal(self, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        received = []
        view.back_requested.connect(lambda: received.append(True))

        with qtbot.waitSignal(view.back_requested, timeout=1000):
            view.back_requested.emit()

        assert received

    @patch("gui.sbom_view.QMessageBox.information")
    def test_export_writes_spdx_file(self, mock_info, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        comp = make_component("zlib", Classification.CONFIRMED, tmp_path)
        view.set_components([comp])

        out = tmp_path / "sbom.spdx"
        view._out_edit.setText(str(out))

        for btn in view._fmt_group.buttons():
            if btn.property("format_value") == "spdx":
                btn.setChecked(True)
                break

        view._on_export()
        assert out.exists()
        assert "zlib" in out.read_text()

    @patch("gui.sbom_view.QMessageBox.information")
    def test_export_writes_cyclonedx_json(self, mock_info, qtbot, tmp_path):
        view = SbomView()
        qtbot.addWidget(view)

        comp = make_component("mylib", Classification.INFERRED, tmp_path)
        view.set_components([comp])

        out = tmp_path / "bom.json"
        view._out_edit.setText(str(out))

        for btn in view._fmt_group.buttons():
            if btn.property("format_value") == "cdx_json":
                btn.setChecked(True)
                break

        view._on_export()
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["bomFormat"] == "CycloneDX"
