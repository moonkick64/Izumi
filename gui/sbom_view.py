# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""SBOM export view – format selection and file output."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analyzer.classifier import Classification
from analyzer.models import Component
from i18n import t


_FMT_EXTENSIONS: dict[str, str] = {
    "spdx":     ".spdx",
    "spdx_json": ".json",
    "cdx_json":  ".json",
    "cdx_xml":   ".xml",
}


class SbomView(QWidget):
    """Screen 4: final component confirmation and SBOM file output."""

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._components: list[Component] = []
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────

    def set_components(self, components: list[Component]) -> None:
        self._components = components
        self._refresh_table()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(QLabel(t("sbom_title")))

        # Component summary table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([
            t("col_component"), t("col_classification"),
            t("col_license"),   t("col_file_count"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self._table)

        # Project information
        proj_group = QGroupBox(t("project_info_group"))
        proj_layout = QHBoxLayout(proj_group)
        proj_layout.addWidget(QLabel(t("project_name_label")))
        self._proj_name_edit = QLineEdit()
        self._proj_name_edit.setPlaceholderText(t("project_name_placeholder"))
        proj_layout.addWidget(self._proj_name_edit, 3)
        proj_layout.addWidget(QLabel(t("project_version_label")))
        self._proj_version_edit = QLineEdit()
        self._proj_version_edit.setPlaceholderText(t("project_version_placeholder"))
        proj_layout.addWidget(self._proj_version_edit, 1)
        root.addWidget(proj_group)

        # Output options
        opt_group = QGroupBox(t("output_settings_group"))
        opt_layout = QVBoxLayout(opt_group)

        # Format radio buttons
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(t("format_label")))

        self._fmt_group = QButtonGroup(self)
        for label, value in [
            ("SPDX 2.3 (tag-value)", "spdx"),
            ("SPDX 2.3 (JSON)", "spdx_json"),
            ("CycloneDX 1.5 (JSON)", "cdx_json"),
            ("CycloneDX 1.5 (XML)", "cdx_xml"),
        ]:
            rb = QRadioButton(label)
            rb.setProperty("format_value", value)
            self._fmt_group.addButton(rb)
            fmt_row.addWidget(rb)
            if value == "spdx":
                rb.setChecked(True)

        fmt_row.addStretch()
        opt_layout.addLayout(fmt_row)

        # Output path
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel(t("output_path_label")))
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText(t("output_path_placeholder"))
        path_row.addWidget(self._out_edit)

        browse_btn = QPushButton(t("browse_btn"))
        browse_btn.clicked.connect(self._browse_output)
        path_row.addWidget(browse_btn)

        opt_layout.addLayout(path_row)
        root.addWidget(opt_group)

        # Buttons
        btn_row = QHBoxLayout()
        back_btn = QPushButton(t("back_to_scan_btn"))
        back_btn.clicked.connect(self.back_requested)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()

        export_btn = QPushButton(t("export_sbom_btn"))
        export_btn.setFixedHeight(36)
        export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(export_btn)

        root.addLayout(btn_row)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _ensure_extension(self, path: Path, fmt: str) -> Path:
        """Return *path* with the correct extension for *fmt*, adding or replacing if needed."""
        expected = _FMT_EXTENSIONS.get(fmt, "")
        if not expected:
            return path
        if path.suffix == expected:
            return path
        if path.suffix:
            return path.with_suffix(expected)
        return Path(str(path) + expected)

    # ── Data population ───────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._components))
        for row, comp in enumerate(self._components):
            self._table.setItem(row, 0, QTableWidgetItem(comp.name))
            self._table.setItem(row, 1, QTableWidgetItem(comp.classification.value))
            self._table.setItem(row, 2, QTableWidgetItem(comp.license_expression or t("unknown_license")))
            self._table.setItem(row, 3, QTableWidgetItem(str(len(comp.files))))

    # ── Slots ─────────────────────────────────────────────────────────────

    def _browse_output(self) -> None:
        fmt = self._selected_format()
        filters = {
            "spdx":     "SPDX tag-value (*.spdx)",
            "spdx_json":"SPDX JSON (*.json)",
            "cdx_json": "CycloneDX JSON (*.json)",
            "cdx_xml":  "CycloneDX XML (*.xml)",
        }
        default_name = "sbom" + _FMT_EXTENSIONS.get(fmt, "")
        path, _ = QFileDialog.getSaveFileName(
            self, t("sbom_output_dialog"), default_name, filters.get(fmt, "All files (*)")
        )
        if path:
            out_path = self._ensure_extension(Path(path), fmt)
            self._out_edit.setText(str(out_path))

    def _on_export(self) -> None:
        out_path = Path(self._out_edit.text().strip())
        if not out_path.name:
            QMessageBox.warning(self, t("no_output_path_title"), t("no_output_path_msg"))
            return

        fmt = self._selected_format()
        out_path = self._ensure_extension(out_path, fmt)
        self._out_edit.setText(str(out_path))

        proj_name    = self._proj_name_edit.text().strip()
        proj_version = self._proj_version_edit.text().strip()

        try:
            if fmt.startswith("spdx"):
                from sbom.spdx_writer import write_spdx
                write_spdx(
                    self._components, out_path,
                    project_name=proj_name, project_version=proj_version,
                )
            else:
                from sbom.cyclonedx_writer import write_cyclonedx
                output_format = "xml" if fmt == "cdx_xml" else "json"
                write_cyclonedx(
                    self._components, out_path, output_format=output_format,
                    project_name=proj_name, project_version=proj_version,
                )

            QMessageBox.information(
                self, t("export_complete_title"), t("export_complete_msg", out_path=out_path)
            )
        except Exception as exc:
            QMessageBox.critical(self, t("export_error_title"), str(exc))

    def _selected_format(self) -> str:
        checked = self._fmt_group.checkedButton()
        if checked:
            return checked.property("format_value")
        return "spdx"
