# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
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

def make_file_info(path: Path) -> FileInfo:
    return FileInfo(path=path, copyright_info=CopyrightInfo())


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

    fi = make_file_info(tmp_path / "dummy.c")

    for i in range(confirmed):
        result.confirmed.append(ClassifiedFile(fi, Classification.CONFIRMED, "test"))
        components.append(make_component(f"confirmed-{i}", Classification.CONFIRMED, tmp_path))

    for i in range(inferred):
        result.inferred.append(ClassifiedFile(fi, Classification.INFERRED, "test"))
        components.append(make_component(f"inferred-{i}", Classification.INFERRED, tmp_path))

    for i in range(unknown):
        result.unknown.append(ClassifiedFile(fi, Classification.UNKNOWN, "test"))
        components.append(make_component(f"unknown-{i}", Classification.UNKNOWN, tmp_path))

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

    def test_tree_populated_with_files(self, qtbot, tmp_path):
        # Create actual files so the tree has something to show
        (tmp_path / "foo.c").write_text("// foo")
        (tmp_path / "bar.c").write_text("// bar")

        fi_foo = make_file_info(tmp_path / "foo.c")
        fi_bar = make_file_info(tmp_path / "bar.c")

        result = ClassificationResult()
        result.confirmed.append(ClassifiedFile(fi_foo, Classification.CONFIRMED, "spdx"))
        result.unknown.append(ClassifiedFile(fi_bar, Classification.UNKNOWN, "no info"))

        view = ScanView()
        qtbot.addWidget(view)
        view.set_data(result, [], tmp_path)

        # Tree should have exactly one top-level dir item
        assert view._tree.topLevelItemCount() == 1
        dir_item = view._tree.topLevelItem(0)
        # Both files are in the same dir, so 2 children
        assert dir_item.childCount() == 2

    def test_file_colors_by_classification(self, qtbot, tmp_path):
        from PySide6.QtGui import QColor
        from gui.scan_view import _CLASS_BG

        (tmp_path / "ok.c").write_text("")
        (tmp_path / "unknown.c").write_text("")

        fi_ok = make_file_info(tmp_path / "ok.c")
        fi_unk = make_file_info(tmp_path / "unknown.c")

        result = ClassificationResult()
        result.confirmed.append(ClassifiedFile(fi_ok, Classification.CONFIRMED, "spdx"))
        result.unknown.append(ClassifiedFile(fi_unk, Classification.UNKNOWN, "no info"))

        view = ScanView()
        qtbot.addWidget(view)
        view.set_data(result, [], tmp_path)

        dir_item = view._tree.topLevelItem(0)
        file_names = {
            dir_item.child(i).text(0): dir_item.child(i)
            for i in range(dir_item.childCount())
        }

        assert "ok.c" in file_names
        assert "unknown.c" in file_names
        expected_confirmed_bg = QColor(_CLASS_BG[Classification.CONFIRMED])
        assert file_names["ok.c"].background(0).color() == expected_confirmed_bg

    def test_source_viewer_loads_on_click(self, qtbot, tmp_path):
        src_file = tmp_path / "hello.c"
        src_file.write_text("int main() { return 0; }")

        fi = make_file_info(src_file)
        result = ClassificationResult()
        result.confirmed.append(ClassifiedFile(fi, Classification.CONFIRMED, "spdx"))

        view = ScanView()
        qtbot.addWidget(view)
        view.set_data(result, [], tmp_path)

        dir_item = view._tree.topLevelItem(0)
        file_item = dir_item.child(0)
        view._tree.setCurrentItem(file_item)

        assert "int main" in view._source_view.toPlainText()

    def test_review_button_enabled_with_any_files(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(1, 0, 0, tmp_path)
        view.set_data(result, components)

        assert view._review_btn.isEnabled()

    def test_review_button_disabled_without_files(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(0, 0, 0, tmp_path)
        view.set_data(result, components)

        assert not view._review_btn.isEnabled()

    def test_review_signal_emits_path_list(self, qtbot, tmp_path):
        view = ScanView()
        qtbot.addWidget(view)

        result, components = make_classification(1, 1, 2, tmp_path)
        view.set_data(result, components)

        received = []
        view.review_requested.connect(received.append)

        with qtbot.waitSignal(view.review_requested, timeout=1000):
            view._on_review_clicked()

        assert len(received) == 1
        assert isinstance(received[0], list)

    def test_nested_directories_build_nested_tree(self, qtbot, tmp_path):
        # tmp_path/sub/deep/foo.c  →  root > sub > deep > foo.c
        deep_dir = tmp_path / "sub" / "deep"
        deep_dir.mkdir(parents=True)
        (deep_dir / "foo.c").write_text("// foo")

        fi = make_file_info(deep_dir / "foo.c")
        result = ClassificationResult()
        result.unknown.append(ClassifiedFile(fi, Classification.UNKNOWN, "no info"))

        view = ScanView()
        qtbot.addWidget(view)
        view.set_data(result, [], tmp_path)

        # Top-level should be the root dir
        assert view._tree.topLevelItemCount() == 1
        root_item = view._tree.topLevelItem(0)
        # root > sub
        assert root_item.childCount() == 1
        sub_item = root_item.child(0)
        assert sub_item.text(0) == "sub"
        # sub > deep
        assert sub_item.childCount() == 1
        deep_item = sub_item.child(0)
        assert deep_item.text(0) == "deep"
        # deep > foo.c
        assert deep_item.childCount() == 1
        assert deep_item.child(0).text(0) == "foo.c"

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
