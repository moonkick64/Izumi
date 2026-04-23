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
        self._selected_comp_idx: int | None = None
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
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            t("col_component"), t("col_classification"),
            t("col_license"),   t("col_version"), t("col_file_count"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_component_selected)
        root.addWidget(self._table)

        # Component detail panel (shown when a row is selected)
        self._detail_group = QGroupBox(t("component_detail_group"))
        detail_layout = QVBoxLayout(self._detail_group)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(t("detail_name_label")))
        self._detail_name_edit = QLineEdit()
        row1.addWidget(self._detail_name_edit, 2)
        row1.addWidget(QLabel(t("version_label")))
        self._detail_version_edit = QLineEdit()
        self._detail_version_edit.setPlaceholderText("e.g. 1.2.11")
        row1.addWidget(self._detail_version_edit, 1)
        detail_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(t("inferred_license_label")))
        self._detail_license_edit = QLineEdit()
        row2.addWidget(self._detail_license_edit, 2)
        row2.addWidget(QLabel(t("supplier_label")))
        self._detail_supplier_edit = QLineEdit()
        self._detail_supplier_edit.setPlaceholderText(t("supplier_placeholder"))
        row2.addWidget(self._detail_supplier_edit, 2)
        detail_layout.addLayout(row2)
        apply_btn = QPushButton(t("apply_component_btn"))
        apply_btn.clicked.connect(self._on_apply_component)
        detail_layout.addWidget(apply_btn, 0, Qt.AlignmentFlag.AlignRight)
        self._detail_group.setVisible(False)
        root.addWidget(self._detail_group)

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

    # ── Slots ────────────────────────────────────────────────────────────

    def _on_component_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._components):
            self._detail_group.setVisible(False)
            self._selected_comp_idx = None
            return
        comp = self._components[row]
        self._selected_comp_idx = row
        self._detail_group.setTitle(f"{t('component_detail_group')} — {comp.name}")
        self._detail_name_edit.setText(comp.name)
        self._detail_version_edit.setText(comp.version or "")
        self._detail_license_edit.setText(comp.license_expression or "")
        self._detail_supplier_edit.setText(comp.supplier or "")
        self._detail_group.setVisible(True)

    def _on_apply_component(self) -> None:
        if self._selected_comp_idx is None:
            return
        comp = self._components[self._selected_comp_idx]
        comp.name = self._detail_name_edit.text().strip() or comp.name
        comp.version = self._detail_version_edit.text().strip() or None
        comp.license_expression = self._detail_license_edit.text().strip() or None
        comp.supplier = self._detail_supplier_edit.text().strip() or None
        current_row = self._table.currentRow()
        self._refresh_table()
        self._table.setCurrentCell(current_row, 0)

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
            self._table.setItem(row, 3, QTableWidgetItem(comp.version or ""))
            self._table.setItem(row, 4, QTableWidgetItem(str(comp.confirmed_file_count)))

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

        try:
            if fmt.startswith("spdx"):
                from sbom.spdx_writer import write_spdx
                write_spdx(self._components, out_path)
            else:
                from sbom.cyclonedx_writer import write_cyclonedx
                output_format = "xml" if fmt == "cdx_xml" else "json"
                write_cyclonedx(self._components, out_path, output_format=output_format)

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
