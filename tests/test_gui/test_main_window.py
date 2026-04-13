# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Tests for gui.main_window – focused on classification change handling."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from analyzer.classifier import Classification, ClassificationResult, ClassifiedFile
from analyzer.copyright import CopyrightInfo
from analyzer.models import Component
from analyzer.scanner import FileInfo


def make_cf(path: Path, cls: Classification, spdx_id: str | None = None) -> ClassifiedFile:
    ci = CopyrightInfo(spdx_license_id=spdx_id)
    fi = FileInfo(path=path, copyright_info=ci)
    return ClassifiedFile(fi, cls, "test")


class TestOnClassificationChanged:
    """Unit tests for MainWindow._on_classification_changed without launching the full GUI."""

    def _make_window_with_classification(self, qtbot, tmp_path):
        from gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

        fa = tmp_path / "a.c"
        fb = tmp_path / "b.c"
        fc = tmp_path / "c.c"
        for f in (fa, fb, fc):
            f.write_text("// src")

        classification = ClassificationResult()
        classification.unknown.append(make_cf(fa, Classification.UNKNOWN))
        classification.unknown.append(make_cf(fb, Classification.UNKNOWN))
        classification.confirmed.append(make_cf(fc, Classification.CONFIRMED, "GPL-3.0-only"))

        win._classification = classification
        win._source_dir = tmp_path
        win._components = []
        return win, fa, fb, fc

    def test_single_change_moves_file_to_new_list(self, qtbot, tmp_path):
        win, fa, fb, fc = self._make_window_with_classification(qtbot, tmp_path)

        win._on_classification_changed([(fa, Classification.CONFIRMED.value, "MIT")])

        paths_confirmed = {cf.file_info.path for cf in win._classification.confirmed}
        paths_unknown = {cf.file_info.path for cf in win._classification.unknown}
        assert fa in paths_confirmed
        assert fa not in paths_unknown

    def test_single_change_sets_license(self, qtbot, tmp_path):
        win, fa, fb, fc = self._make_window_with_classification(qtbot, tmp_path)

        win._on_classification_changed([(fa, Classification.CONFIRMED.value, "MIT")])

        cf = next(cf for cf in win._classification.confirmed if cf.file_info.path == fa)
        assert cf.file_info.copyright_info.spdx_license_id == "MIT"

    def test_bulk_change_applies_to_all_files(self, qtbot, tmp_path):
        """Both unknown files become CONFIRMED with the same license in one call."""
        win, fa, fb, fc = self._make_window_with_classification(qtbot, tmp_path)

        changes = [
            (fa, Classification.CONFIRMED.value, "Zlib"),
            (fb, Classification.CONFIRMED.value, "Zlib"),
        ]
        win._on_classification_changed(changes)

        paths_confirmed = {cf.file_info.path for cf in win._classification.confirmed}
        assert fa in paths_confirmed
        assert fb in paths_confirmed
        assert len(win._classification.unknown) == 0

    def test_bulk_change_rebuilds_components_once(self, qtbot, tmp_path):
        """group_into_components is called exactly once regardless of change count."""
        win, fa, fb, fc = self._make_window_with_classification(qtbot, tmp_path)

        changes = [
            (fa, Classification.CONFIRMED.value, "Zlib"),
            (fb, Classification.CONFIRMED.value, "Zlib"),
        ]

        with patch("gui.main_window.group_into_components", return_value=[]) as mock_group:
            win._on_classification_changed(changes)

        mock_group.assert_called_once()

    def test_unknown_path_is_silently_skipped(self, qtbot, tmp_path):
        win, fa, fb, fc = self._make_window_with_classification(qtbot, tmp_path)
        ghost = tmp_path / "nonexistent.c"

        win._on_classification_changed([(ghost, Classification.CONFIRMED.value, "MIT")])

        assert len(win._classification.unknown) == 2

    def test_no_license_leaves_spdx_id_unchanged(self, qtbot, tmp_path):
        win, fa, fb, fc = self._make_window_with_classification(qtbot, tmp_path)

        win._on_classification_changed([(fa, Classification.CONFIRMED.value, "")])

        cf = next(cf for cf in win._classification.confirmed if cf.file_info.path == fa)
        assert cf.file_info.copyright_info.spdx_license_id is None
