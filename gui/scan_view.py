"""Scan results view – VS Code-style file tree + source code viewer."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analyzer.classifier import Classification, ClassificationResult, ClassifiedFile
from analyzer.models import Component
from i18n import t


_CLASS_BG: dict[Classification, str] = {
    Classification.CONFIRMED: "#d4edda",
    Classification.INFERRED:  "#fff3cd",
    Classification.UNKNOWN:   "#f8d7da",
}

_CLASS_FG: dict[Classification, str] = {
    Classification.CONFIRMED: "#155724",
    Classification.INFERRED:  "#856404",
    Classification.UNKNOWN:   "#721c24",
}


class ScanView(QWidget):
    """Screen 2: VS Code-style file tree with source code viewer."""

    review_requested        = Signal(list)    # list[Path] – selected files (empty = all)
    export_requested        = Signal(list)    # list[Component] – all
    classification_confirmed = Signal(object, str)  # Path, license_spdx_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._components: list[Component] = []
        self._classification: ClassificationResult | None = None
        self._source_root: Path | None = None
        self._item_to_file: dict[QTreeWidgetItem, ClassifiedFile] = {}
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────

    def set_data(
        self,
        classification: ClassificationResult,
        components: list[Component],
        source_root: Path | None = None,
    ) -> None:
        self._classification = classification
        self._components = components
        self._source_root = source_root
        self._refresh()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Summary bar
        summary_row = QHBoxLayout()
        self._confirmed_label = QLabel("CONFIRMED: 0")
        self._confirmed_label.setStyleSheet(
            f"color: {_CLASS_FG[Classification.CONFIRMED]}; font-weight: bold;"
        )
        self._inferred_label = QLabel("INFERRED: 0")
        self._inferred_label.setStyleSheet(
            f"color: {_CLASS_FG[Classification.INFERRED]}; font-weight: bold;"
        )
        self._unknown_label = QLabel("UNKNOWN: 0")
        self._unknown_label.setStyleSheet(
            f"color: {_CLASS_FG[Classification.UNKNOWN]}; font-weight: bold;"
        )
        mono10 = QFont("monospace", 10)
        for lbl in (self._confirmed_label, self._inferred_label, self._unknown_label):
            lbl.setFont(mono10)
            summary_row.addWidget(lbl)
        summary_row.addStretch()
        root.addLayout(summary_row)

        # Main splitter: left=tree, right=viewer
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)  # stretch=1 so it fills all available height

        # ── Left: file tree ───────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(4)

        tree_header = QLabel(t("file_tree_label"))
        tree_header.setFont(QFont("monospace", 9))
        left_layout.addWidget(tree_header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.currentItemChanged.connect(self._on_tree_item_changed)
        left_layout.addWidget(self._tree)

        splitter.addWidget(left)

        # ── Right: file info header + source viewer ───────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        self._file_info_label = QLabel("")
        self._file_info_label.setWordWrap(True)
        self._file_info_label.setFont(QFont("monospace", 9))
        self._file_info_label.setContentsMargins(4, 2, 4, 2)
        right_layout.addWidget(self._file_info_label)

        self._source_view = QPlainTextEdit()
        self._source_view.setReadOnly(True)
        self._source_view.setFont(QFont("monospace", 10))
        self._source_view.setPlaceholderText(t("source_placeholder"))
        right_layout.addWidget(self._source_view)

        # INFERRED license confirmation panel
        self._confirm_group = QGroupBox(t("inferred_confirm_group"))
        confirm_layout = QVBoxLayout(self._confirm_group)
        self._candidates_label = QLabel("")
        self._candidates_label.setWordWrap(True)
        self._candidates_label.setFont(QFont("monospace", 9))
        confirm_layout.addWidget(self._candidates_label)
        confirm_fields = QHBoxLayout()
        confirm_fields.addWidget(QLabel(t("inferred_license_label")))
        self._confirm_license_edit = QLineEdit()
        confirm_fields.addWidget(self._confirm_license_edit, 1)
        self._mark_confirmed_btn = QPushButton(t("mark_confirmed_btn"))
        self._mark_confirmed_btn.clicked.connect(self._on_mark_confirmed_clicked)
        confirm_fields.addWidget(self._mark_confirmed_btn)
        confirm_layout.addLayout(confirm_fields)
        right_layout.addWidget(self._confirm_group)
        self._confirm_group.setVisible(False)

        splitter.addWidget(right)
        splitter.setSizes([280, 820])

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._review_btn = QPushButton(t("llm_analysis_btn"))
        self._review_btn.clicked.connect(self._on_review_clicked)
        btn_row.addWidget(self._review_btn)

        self._export_btn = QPushButton(t("sbom_export_btn"))
        self._export_btn.clicked.connect(self._on_export_clicked)
        btn_row.addWidget(self._export_btn)

        root.addLayout(btn_row)

    # ── Data population ───────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._classification:
            return

        s = self._classification.summary()
        self._confirmed_label.setText(f"CONFIRMED: {s['confirmed']}")
        self._inferred_label.setText(f"INFERRED: {s['inferred']}")
        self._unknown_label.setText(f"⚠ UNKNOWN: {s['unknown']}")
        self._review_btn.setEnabled(s['total'] > 0)

        self._build_tree()

    def _build_tree(self) -> None:
        self._tree.clear()
        self._item_to_file.clear()

        if not self._classification:
            return

        # Group files by parent directory
        dirs: dict[Path, list[ClassifiedFile]] = {}
        for cf in self._classification.all_files:
            dirs.setdefault(cf.file_info.path.parent, []).append(cf)

        source_root = self._source_root
        mono9 = QFont("monospace", 9)

        # Cache of dir_path → QTreeWidgetItem to build nested structure
        dir_items: dict[Path, QTreeWidgetItem] = {}

        def get_or_create_dir_item(dir_path: Path) -> QTreeWidgetItem:
            if dir_path in dir_items:
                return dir_items[dir_path]

            if source_root is None or dir_path == source_root:
                label = dir_path.name or str(dir_path)
                item = QTreeWidgetItem([label])
                item.setFont(0, mono9)
                self._tree.addTopLevelItem(item)
            else:
                try:
                    dir_path.relative_to(source_root)
                    parent_item = get_or_create_dir_item(dir_path.parent)
                    item = QTreeWidgetItem([dir_path.name])
                    item.setFont(0, mono9)
                    parent_item.addChild(item)
                except ValueError:
                    # dir_path is outside source_root – add as top-level
                    item = QTreeWidgetItem([str(dir_path)])
                    item.setFont(0, mono9)
                    self._tree.addTopLevelItem(item)

            dir_items[dir_path] = item
            return item

        # Process in sorted order so parent dirs are created before children
        for dir_path in sorted(dirs):
            dir_item = get_or_create_dir_item(dir_path)
            for cf in sorted(dirs[dir_path], key=lambda x: x.file_info.path.name):
                file_item = QTreeWidgetItem([cf.file_info.path.name])
                file_item.setBackground(0, QColor(_CLASS_BG[cf.classification]))
                file_item.setForeground(0, QColor(_CLASS_FG[cf.classification]))
                file_item.setFont(0, mono9)
                dir_item.addChild(file_item)
                self._item_to_file[file_item] = cf

        self._tree.expandAll()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_tree_item_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None or current not in self._item_to_file:
            self._file_info_label.setText("")
            self._file_info_label.setStyleSheet("")
            self._source_view.clear()
            self._confirm_group.setVisible(False)
            return

        cf = self._item_to_file[current]
        fg = _CLASS_FG[cf.classification]
        self._file_info_label.setText(
            f"[{cf.classification.value}]  {cf.file_info.path}  —  {cf.reason}"
        )
        self._file_info_label.setStyleSheet(
            f"color: {fg}; background: {_CLASS_BG[cf.classification]}; padding: 2px 4px;"
        )

        try:
            text = cf.file_info.path.read_text(errors="replace")
        except OSError as exc:
            text = t("read_error", exc=exc)
        self._source_view.setPlainText(text)

        if cf.classification == Classification.INFERRED:
            candidates = cf.file_info.copyright_info.license_candidates
            if candidates:
                lines = t("inferred_candidates_label") + "\n" + "\n".join(
                    f"  \u2022 {c}" for c in candidates[:5]
                )
                self._candidates_label.setText(lines)
                self._confirm_license_edit.setPlaceholderText(candidates[0][:60])
            else:
                self._candidates_label.setText(t("inferred_no_license"))
                self._confirm_license_edit.setPlaceholderText("")
            self._confirm_license_edit.clear()
            self._confirm_group.setVisible(True)
        else:
            self._confirm_group.setVisible(False)

    def _on_mark_confirmed_clicked(self) -> None:
        item = self._tree.currentItem()
        if item is None or item not in self._item_to_file:
            return
        cf = self._item_to_file[item]
        license_id = self._confirm_license_edit.text().strip()
        self.classification_confirmed.emit(cf.file_info.path, license_id)

    def _on_review_clicked(self) -> None:
        selected_paths: list[Path] = [
            self._item_to_file[item].file_info.path
            for item in self._tree.selectedItems()
            if item in self._item_to_file
        ]
        self.review_requested.emit(selected_paths)

    def _on_export_clicked(self) -> None:
        self.export_requested.emit(self._components)
