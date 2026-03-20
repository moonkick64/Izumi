"""Tests for gui.scan_view."""

import os
import pytest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from analyzer.classifier import Classification, ClassificationResult, ClassifiedFile
from analyzer.copyright import CopyrightInfo
from analyzer.models import Component
from analyzer.scanner import FileInfo
from gui.scan_view import ScanView


# ── Helpers ───────────────────────────────────────────────────────────────

def make_component(name: str, cls: Classification, tmp_path: Path) -> Component:
    return Component(
        name=name,
        directory=tmp_path,
        classification=cls,
        classification_reason="test",
    )


def make_classification(
    confirmed: int, inferred: int, unknown: int, tmp_path: Path
) -> tuple[ClassificationResult, list[Component]]:
    result = ClassificationResult()
    components: list[Component] = []

    for i in range(confirmed):
        comp = make_component(f"confirmed-{i}", Classification.CONFIRMED, tmp_path)
        components.append(comp)

    for i in range(inferred):
        comp = make_component(f"inferred-{i}", Classification.INFERRED, tmp_path)
        components.append(comp)

    for i in range(unknown):
        comp = make_component(f"unknown-{i}", Classification.UNKNOWN, tmp_path)
        components.append(comp)

    # ClassificationResult is derived from files, but for GUI tests we just
    # set its lists manually using dummy FileInfo objects
    fi = FileInfo(path=tmp_path / "dummy.c", copyright_info=CopyrightInfo())
    for i in range(confirmed):
        result.confirmed.append(ClassifiedFile(fi, Classification.CONFIRMED, "test"))
    for i in range(inferred):
        result.inferred.append(ClassifiedFile(fi, Classification.INFERRED, "test"))
    for i in range(unknown):
        result.unknown.append(ClassifiedFile(fi, Classification.UNKNOWN, "test"))

    return result, components


# ── Tests ─────────────────────────────────────────────────────────────────

class TestScanView:
    def test_creates_without_error(self, qtbot):
        view = ScanView()
        qtbot.addWidget(view)

    def test_set_data_updates_labels(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(3, 2, 1, tmp_path)
        view.set_data(result, components)

        assert "3" in view._confirmed_label.text()
        assert "2" in view._inferred_label.text()
        assert "1" in view._unknown_label.text()

    def test_set_data_populates_tables(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(2, 1, 3, tmp_path)
        view.set_data(result, components)

        assert view._tab_confirmed.rowCount() == 2
        assert view._tab_inferred.rowCount() == 1
        assert view._tab_unknown.rowCount() == 3

    def test_review_button_enabled_with_unknown(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(1, 0, 2, tmp_path)
        view.set_data(result, components)

        assert view._review_btn.isEnabled()

    def test_review_button_disabled_without_unknown(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(2, 1, 0, tmp_path)
        view.set_data(result, components)

        assert not view._review_btn.isEnabled()

    def test_review_signal_emits_only_unknown(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(1, 1, 2, tmp_path)
        view.set_data(result, components)

        received: list[list[Component]] = []
        view.review_requested.connect(received.append)

        with qtbot.waitSignal(view.review_requested, timeout=1000):
            view._on_review_clicked()

        assert len(received) == 1
        assert all(c.classification == Classification.UNKNOWN for c in received[0])
        assert len(received[0]) == 2

    def test_export_signal_emits_all_components(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(1, 1, 1, tmp_path)
        view.set_data(result, components)

        received: list[list[Component]] = []
        view.export_requested.connect(received.append)

        with qtbot.waitSignal(view.export_requested, timeout=1000):
            view._on_export_clicked()

        assert len(received) == 1
        assert len(received[0]) == 3

    def test_tab_titles_show_counts(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(5, 3, 1, tmp_path)
        view.set_data(result, components)

        assert "5" in view._tabs.tabText(0)
        assert "3" in view._tabs.tabText(1)
        assert "1" in view._tabs.tabText(2)
