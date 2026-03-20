"""Scan results view – CONFIRMED / INFERRED / UNKNOWN tabs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analyzer.classifier import Classification, ClassificationResult
from analyzer.models import Component


_CLASSIFICATION_COLORS: dict[Classification, str] = {
    Classification.CONFIRMED: "#d4edda",   # light green
    Classification.INFERRED:  "#fff3cd",   # light yellow
    Classification.UNKNOWN:   "#f8d7da",   # light red
}


class ScanView(QWidget):
    """Screen 2: classified file listing with per-tab counts."""

    review_requested = Signal(list)   # list[Component] – UNKNOWN ones
    export_requested = Signal(list)   # list[Component] – all

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._components: list[Component] = []
        self._classification: ClassificationResult | None = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────

    def set_data(
        self,
        classification: ClassificationResult,
        components: list[Component],
    ) -> None:
        self._classification = classification
        self._components = components
        self._refresh()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Summary bar
        summary_row = QHBoxLayout()
        self._confirmed_label = QLabel("CONFIRMED: 0")
        self._inferred_label  = QLabel("INFERRED: 0")
        self._unknown_label   = QLabel("UNKNOWN: 0")

        for lbl in (self._confirmed_label, self._inferred_label, self._unknown_label):
            lbl.setFont(QFont("monospace", 10))
            summary_row.addWidget(lbl)

        summary_row.addStretch()
        root.addLayout(summary_row)

        # Tabs
        self._tabs = QTabWidget()
        self._tab_confirmed = self._make_table()
        self._tab_inferred  = self._make_table()
        self._tab_unknown   = self._make_table()

        self._tabs.addTab(self._tab_confirmed, "CONFIRMED")
        self._tabs.addTab(self._tab_inferred,  "INFERRED")
        self._tabs.addTab(self._tab_unknown,   "UNKNOWN")
        root.addWidget(self._tabs)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._review_btn = QPushButton("UNKNOWN をレビュー →")
        self._review_btn.clicked.connect(self._on_review_clicked)
        btn_row.addWidget(self._review_btn)

        self._export_btn = QPushButton("SBOM 出力 →")
        self._export_btn.clicked.connect(self._on_export_clicked)
        btn_row.addWidget(self._export_btn)

        root.addLayout(btn_row)

    @staticmethod
    def _make_table() -> QTableWidget:
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["コンポーネント", "ファイル数", "分類根拠"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    # ── Data population ───────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._classification:
            return

        s = self._classification.summary()
        self._confirmed_label.setText(f"CONFIRMED: {s['confirmed']}")
        self._inferred_label.setText(f"INFERRED: {s['inferred']}")
        self._unknown_label.setText(f"⚠ UNKNOWN: {s['unknown']}")

        by_class: dict[Classification, list[Component]] = {
            Classification.CONFIRMED: [],
            Classification.INFERRED:  [],
            Classification.UNKNOWN:   [],
        }
        for comp in self._components:
            by_class[comp.classification].append(comp)

        self._populate_table(self._tab_confirmed, by_class[Classification.CONFIRMED])
        self._populate_table(self._tab_inferred,  by_class[Classification.INFERRED])
        self._populate_table(self._tab_unknown,   by_class[Classification.UNKNOWN])

        self._tabs.setTabText(0, f"CONFIRMED ({len(by_class[Classification.CONFIRMED])})")
        self._tabs.setTabText(1, f"INFERRED ({len(by_class[Classification.INFERRED])})")
        self._tabs.setTabText(2, f"UNKNOWN ({len(by_class[Classification.UNKNOWN])})")

        has_unknown = bool(by_class[Classification.UNKNOWN])
        self._review_btn.setEnabled(has_unknown)

    @staticmethod
    def _populate_table(table: QTableWidget, components: list[Component]) -> None:
        table.setRowCount(len(components))
        for row, comp in enumerate(components):
            table.setItem(row, 0, QTableWidgetItem(comp.name))
            table.setItem(row, 1, QTableWidgetItem(str(len(comp.files))))
            table.setItem(row, 2, QTableWidgetItem(comp.classification_reason))

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_review_clicked(self) -> None:
        unknown = [c for c in self._components if c.classification == Classification.UNKNOWN]
        self.review_requested.emit(unknown)

    def _on_export_clicked(self) -> None:
        self.export_requested.emit(self._components)
