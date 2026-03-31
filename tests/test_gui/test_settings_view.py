# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Tests for gui.settings_view."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui.settings_view import SettingsView


class TestSettingsView:
    def test_creates_without_error(self, qtbot):
        view = SettingsView()
        qtbot.addWidget(view)

    def test_initial_source_dir_is_none(self, qtbot):
        view = SettingsView()
        qtbot.addWidget(view)
        assert view.source_dir is None

    def test_ollama_default_url(self, qtbot):
        view = SettingsView()
        qtbot.addWidget(view)
        assert "localhost" in view.ollama_url

    def test_local_model_default(self, qtbot):
        view = SettingsView()
        qtbot.addWidget(view)
        assert "codellama" in view.local_model

    def test_external_model_default(self, qtbot):
        view = SettingsView()
        qtbot.addWidget(view)
        assert view.external_model  # Not empty

    def test_scan_requested_signal_emitted(self, qtbot, tmp_path):
        view = SettingsView()
        qtbot.addWidget(view)

        view._src_edit.setText(str(tmp_path))

        received: list[Path] = []
        view.scan_requested.connect(lambda p: received.append(p))

        with qtbot.waitSignal(view.scan_requested, timeout=1000):
            view._on_scan_clicked()

        assert len(received) == 1
        assert received[0] == tmp_path

    @patch("gui.settings_view.QMessageBox.warning")
    def test_scan_not_emitted_for_invalid_path(self, mock_warn, qtbot):
        view = SettingsView()
        qtbot.addWidget(view)

        view._src_edit.setText("/nonexistent/path/that/does/not/exist")

        received: list = []
        view.scan_requested.connect(lambda p: received.append(p))
        view._on_scan_clicked()

        assert received == []

    def test_api_key_echo_mode_is_password(self, qtbot):
        from PySide6.QtWidgets import QLineEdit
        view = SettingsView()
        qtbot.addWidget(view)
        assert view._api_key_edit.echoMode() == QLineEdit.EchoMode.Password
