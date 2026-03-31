# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Settings view – source directory selection and LLM configuration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import t, get_language, set_language


class SettingsView(QWidget):
    """Screen 1: project configuration and scan launch."""

    scan_requested  = Signal(object)  # Path
    settings_changed = Signal()       # emitted whenever any LLM setting changes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        title = QLabel(t("app_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        # ── Source directory ─────────────────────────────────────────────
        src_group = QGroupBox(t("scan_target_group"))
        src_layout = QHBoxLayout(src_group)

        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText(t("source_path_placeholder"))
        src_layout.addWidget(self._src_edit)

        browse_btn = QPushButton(t("browse_btn"))
        browse_btn.clicked.connect(self._browse_source)
        src_layout.addWidget(browse_btn)

        root.addWidget(src_group)

        # ── Local LLM ────────────────────────────────────────────────────
        local_group = QGroupBox(t("local_llm_group"))
        local_form = QFormLayout(local_group)

        self._ollama_url_edit = QLineEdit("http://localhost:11434")
        local_form.addRow(t("endpoint_label"), self._ollama_url_edit)

        self._local_model_edit = QLineEdit("ollama/codellama")
        local_form.addRow(t("model_label"), self._local_model_edit)

        root.addWidget(local_group)

        # ── External LLM ─────────────────────────────────────────────────
        ext_group = QGroupBox(t("external_llm_group"))
        ext_form = QFormLayout(ext_group)

        self._ext_model_edit = QLineEdit("anthropic/claude-sonnet-4-6")
        ext_form.addRow(t("model_label"), self._ext_model_edit)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setPlaceholderText(t("api_key_placeholder"))
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ext_form.addRow(t("api_key_label"), self._api_key_edit)

        root.addWidget(ext_group)

        # Emit settings_changed whenever any LLM field is edited
        for field in (
            self._ollama_url_edit,
            self._local_model_edit,
            self._ext_model_edit,
            self._api_key_edit,
        ):
            field.textChanged.connect(lambda _: self.settings_changed.emit())

        # ── Language selector ─────────────────────────────────────────────
        lang_row = QHBoxLayout()
        lang_row.addStretch()
        lang_row.addWidget(QLabel(t("language_label")))
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("English", "en")
        self._lang_combo.addItem("\u65e5\u672c\u8a9e", "ja")
        # Set current selection from saved config
        current_lang = get_language()
        idx = self._lang_combo.findData(current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(self._lang_combo)
        root.addLayout(lang_row)

        root.addStretch()

        # ── Scan button ───────────────────────────────────────────────────
        scan_btn = QPushButton(t("scan_start_btn"))
        scan_btn.setFixedHeight(40)
        scan_btn.clicked.connect(self._on_scan_clicked)
        root.addWidget(scan_btn)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, t("browse_source_dialog")
        )
        if directory:
            self._src_edit.setText(directory)

    def _on_scan_clicked(self) -> None:
        path = Path(self._src_edit.text().strip())
        if not path.is_dir():
            QMessageBox.warning(
                self,
                t("invalid_path_title"),
                t("invalid_path_msg", path=path),
            )
            return
        self.scan_requested.emit(path)

    def _on_language_changed(self, index: int) -> None:
        lang = self._lang_combo.itemData(index)
        try:
            set_language(lang)
        except Exception:
            pass
        QMessageBox.information(
            self,
            t("restart_required_title"),
            t("restart_required_msg"),
        )

    # ── Accessors ─────────────────────────────────────────────────────────

    @property
    def source_dir(self) -> Path | None:
        text = self._src_edit.text().strip()
        return Path(text) if text else None

    @property
    def ollama_url(self) -> str:
        return self._ollama_url_edit.text().strip()

    @property
    def local_model(self) -> str:
        return self._local_model_edit.text().strip()

    @property
    def external_model(self) -> str:
        return self._ext_model_edit.text().strip()

    @property
    def api_key(self) -> str:
        return self._api_key_edit.text().strip()
