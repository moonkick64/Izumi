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

        root.addWidget(QLabel("SBOM 出力"))

        # Component summary table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["コンポーネント", "分類", "ライセンス", "ファイル数"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self._table)

        # Output options
        opt_group = QGroupBox("出力設定")
        opt_layout = QVBoxLayout(opt_group)

        # Format radio buttons
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("フォーマット:"))

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
        path_row.addWidget(QLabel("出力先:"))
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("出力ファイルのパス")
        path_row.addWidget(self._out_edit)

        browse_btn = QPushButton("参照…")
        browse_btn.clicked.connect(self._browse_output)
        path_row.addWidget(browse_btn)

        opt_layout.addLayout(path_row)
        root.addWidget(opt_group)

        # Buttons
        btn_row = QHBoxLayout()
        back_btn = QPushButton("← スキャン結果に戻る")
        back_btn.clicked.connect(self.back_requested)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()

        export_btn = QPushButton("SBOM を出力")
        export_btn.setFixedHeight(36)
        export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(export_btn)

        root.addLayout(btn_row)

    # ── Data population ───────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._components))
        for row, comp in enumerate(self._components):
            self._table.setItem(row, 0, QTableWidgetItem(comp.name))
            self._table.setItem(row, 1, QTableWidgetItem(comp.classification.value))
            self._table.setItem(row, 2, QTableWidgetItem(comp.license_expression or "不明"))
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
        path, _ = QFileDialog.getSaveFileName(
            self, "SBOM 出力先", "", filters.get(fmt, "All files (*)")
        )
        if path:
            self._out_edit.setText(path)

    def _on_export(self) -> None:
        out_path = Path(self._out_edit.text().strip())
        if not out_path.name:
            QMessageBox.warning(self, "出力先未設定", "出力先ファイルを指定してください。")
            return

        fmt = self._selected_format()
        try:
            if fmt.startswith("spdx"):
                from sbom.spdx_writer import write_spdx
                write_spdx(self._components, out_path)
            else:
                from sbom.cyclonedx_writer import write_cyclonedx
                output_format = "xml" if fmt == "cdx_xml" else "json"
                write_cyclonedx(self._components, out_path, output_format=output_format)

            QMessageBox.information(
                self, "出力完了", f"SBOM を出力しました:\n{out_path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "出力エラー", str(exc))

    def _selected_format(self) -> str:
        checked = self._fmt_group.checkedButton()
        if checked:
            return checked.property("format_value")
        return "spdx"
