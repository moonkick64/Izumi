# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""LLM SCA review view – function-level analysis with 3 LLM options.

All three options operate on C/C++ functions extracted from source files:
  Option 1: send function body directly to local LLM
  Option 2: local LLM batch-summarises all → user reviews → external LLM identifies OSS
  Option 3: send function body directly to external LLM
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

from analyzer.classifier import Classification, ClassificationResult, ClassifiedFile
from analyzer.models import Component
from analyzer.parser import extract_functions, FunctionInfo
from llm.local_llm import LocalLLM
from llm.external_llm import ExternalLLM
from llm.prompts import parse_oss_response
from llm.results import LLMResultsStore
from i18n import t


# ── Classification colours ─────────────────────────────────────────────────────

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

# ── LLM option constants ───────────────────────────────────────────────────────

OPTION_1_LOCAL_DIRECT    = 1
OPTION_2_LOCAL_SUMMARY   = 2
OPTION_3_EXTERNAL_DIRECT = 3

_MAX_NAME_LEN = 40   # truncate long function names in progress label


# ── Key type ──────────────────────────────────────────────────────────────────

def _fn_key(fn: FunctionInfo) -> tuple:
    return (fn.file_path, fn.name, fn.start_line)


# ── Background workers ─────────────────────────────────────────────────────────

class _ExtractWorker(QThread):
    progress  = Signal(int, int, str)
    finished  = Signal(list)
    error     = Signal(str)

    def __init__(self, files: list[ClassifiedFile]) -> None:
        super().__init__()
        self._files = files

    def run(self) -> None:
        try:
            all_functions: list[FunctionInfo] = []
            for i, cf in enumerate(self._files):
                if self.isInterruptionRequested():
                    break
                self.progress.emit(i, len(self._files), cf.file_info.path.name)
                all_functions.extend(extract_functions(cf.file_info.path))
            self.finished.emit(all_functions)
        except Exception as exc:
            self.error.emit(str(exc))


class _BatchWorker(QThread):
    """Generic batch LLM worker (Options 1 / 2 / 3)."""

    fn_started   = Signal(int, int, str)   # current, total, func_name
    fn_finished  = Signal(object, str)     # FunctionInfo, result_text
    all_finished = Signal()

    def __init__(self, functions: list[FunctionInfo], llm_callable) -> None:
        super().__init__()
        self._functions    = functions
        self._llm_callable = llm_callable

    def run(self) -> None:
        for i, fn in enumerate(self._functions):
            if self.isInterruptionRequested():
                break
            self.fn_started.emit(i, len(self._functions), fn.name)
            try:
                result = self._llm_callable(fn.body)
            except Exception as exc:
                result = f"[ERROR] {exc}"
            self.fn_finished.emit(fn, result)
        self.all_finished.emit()


# ── Main view ──────────────────────────────────────────────────────────────────

class ReviewView(QWidget):
    """Screen 3: LLM SCA review at the function level."""

    back_requested   = Signal()
    export_requested = Signal(list)   # list[Component]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._all_files: list[ClassifiedFile] = []
        self._components: list[Component] = []
        self._source_root: Optional[Path] = None
        self._preselected_paths: Optional[set[Path]] = None

        self._extracted_functions: list[FunctionInfo] = []
        self._current_fn: Optional[FunctionInfo] = None

        # Per-function results (key = (file_path, func_name, start_line))
        self._fn_hints:       dict[tuple, str] = {}
        self._fn_summaries:   dict[tuple, str] = {}                   # option-2 intermediate summaries
        self._fn_matches:     dict[tuple, tuple[str, str]] = {}        # user-confirmed (component, license)
        self._fn_auto_parsed: dict[tuple, tuple[str, str, str]] = {}   # LLM-parsed (component, license, hint)
        self._fn_errors:      set[tuple] = set()                       # parse-failed functions

        self._worker: Optional[QThread] = None
        # "analyse" → store in _fn_hints  /  "summarise" → store in _fn_summaries
        self._batch_mode: str = "analyse"
        self._current_option: int = OPTION_1_LOCAL_DIRECT
        self._store: Optional[LLMResultsStore] = None

        self._local_llm:    Optional[LocalLLM]    = None
        self._external_llm: Optional[ExternalLLM] = None

        self._build_ui()

    # ── Public API ─────────────────────────────────────────────────────────────

    def configure_llm(
        self,
        ollama_url: str,
        local_model: str,
        external_model: str,
        api_key: str = "",
    ) -> None:
        self._local_llm    = LocalLLM(model=local_model, api_base=ollama_url) if local_model.strip() else None
        self._external_llm = ExternalLLM(model=external_model, api_key=api_key) if external_model.strip() else None

    def set_data(
        self,
        classification: ClassificationResult,
        components: list[Component],
        source_root: Optional[Path] = None,
        preselected_paths: Optional[list[Path]] = None,
    ) -> None:
        self._all_files         = classification.all_files
        self._components        = components
        self._source_root       = source_root
        self._preselected_paths = set(preselected_paths) if preselected_paths else None
        self._extracted_functions = []
        self._current_fn          = None
        self._fn_hints.clear()
        self._fn_summaries.clear()
        self._fn_matches.clear()
        self._fn_auto_parsed.clear()
        self._fn_errors.clear()

        if source_root:
            self._store = LLMResultsStore(source_root)
            hints   = self._store.hints_by_key()
            matches = self._store.matches_by_key()
            if hints:
                self._fn_hints.update(hints)
                for key, raw in hints.items():
                    parsed = parse_oss_response(raw)
                    if parsed is not None:
                        self._fn_auto_parsed[key] = parsed
                    else:
                        self._fn_errors.add(key)
            if matches:
                self._fn_matches.update(matches)
            count = len(hints)
            self._results_label.setText(t("loaded_results", count=count) if count else "")
        else:
            self._store = None
            self._results_label.setText("")

        self._refresh_file_list()
        self._function_list.clear()
        self._body_view.clear()
        self._hint_edit.clear()
        self._comp_edit.clear()
        self._lic_edit.clear()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(QLabel(t("review_title")))

        # ── LLM option selector ────────────────────────────────────────────────
        option_group = QGroupBox(t("llm_option_group"))
        option_layout = QVBoxLayout(option_group)

        self._opt1_radio = QRadioButton(t("option1_radio"))
        self._opt2_radio = QRadioButton(t("option2_radio"))
        self._opt3_radio = QRadioButton(t("option3_radio"))
        self._opt2_radio.setChecked(True)

        self._option_btn_group = QButtonGroup(self)
        self._option_btn_group.addButton(self._opt1_radio, OPTION_1_LOCAL_DIRECT)
        self._option_btn_group.addButton(self._opt2_radio, OPTION_2_LOCAL_SUMMARY)
        self._option_btn_group.addButton(self._opt3_radio, OPTION_3_EXTERNAL_DIRECT)
        self._option_btn_group.idToggled.connect(self._on_option_changed)

        option_layout.addWidget(self._opt1_radio)
        option_layout.addWidget(self._opt2_radio)
        option_layout.addWidget(self._opt3_radio)
        root.addWidget(option_group)

        # ── Main splitter ──────────────────────────────────────────────────────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(h_splitter, 1)

        # ── Left panel ────────────────────────────────────────────────────────
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # File list pane
        file_pane = QWidget()
        file_layout = QVBoxLayout(file_pane)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(4)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(t("display_label")))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            t("filter_unknown_only"),
            t("filter_all"),
            t("filter_inferred_only"),
            t("filter_confirmed_only"),
        ])
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo)
        file_layout.addLayout(filter_row)

        file_layout.addWidget(QLabel(t("file_list_label")))
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._file_list.itemSelectionChanged.connect(self._on_file_selection_changed)
        file_layout.addWidget(self._file_list)

        extract_btn = QPushButton(t("extract_btn"))
        extract_btn.clicked.connect(self._on_extract_clicked)
        file_layout.addWidget(extract_btn)

        left_splitter.addWidget(file_pane)

        # Function list pane
        fn_pane = QWidget()
        fn_layout = QVBoxLayout(fn_pane)
        fn_layout.setContentsMargins(0, 0, 0, 0)
        fn_layout.setSpacing(4)

        fn_layout.addWidget(QLabel(t("function_list_label")))
        self._function_list = QListWidget()
        self._function_list.currentRowChanged.connect(self._on_function_selected)
        fn_layout.addWidget(self._function_list)

        # Status label – fixed size to prevent layout shifts
        self._results_label = QLabel("")
        self._results_label.setStyleSheet("color: #555; font-size: 11px;")
        self._results_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        fn_layout.addWidget(self._results_label)

        btn_row = QHBoxLayout()
        self._analyse_btn = QPushButton(t("analyse_btn"))
        self._analyse_btn.clicked.connect(self._on_batch_clicked)
        btn_row.addWidget(self._analyse_btn)

        # Option-2 only: send to external LLM after summaries are ready
        self._opt2_ext_btn = QPushButton(t("option2_send_external_btn"))
        self._opt2_ext_btn.clicked.connect(self._on_opt2_send_external_clicked)
        self._opt2_ext_btn.setVisible(False)
        btn_row.addWidget(self._opt2_ext_btn)

        delete_btn = QPushButton(t("delete_results_btn"))
        delete_btn.clicked.connect(self._on_delete_results_clicked)
        btn_row.addWidget(delete_btn)
        fn_layout.addLayout(btn_row)

        left_splitter.addWidget(fn_pane)
        left_splitter.setSizes([200, 200])
        h_splitter.addWidget(left_splitter)

        # ── Right panel ────────────────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        body_group = QGroupBox(t("function_body_group"))
        body_layout = QVBoxLayout(body_group)
        self._body_view = QPlainTextEdit()
        self._body_view.setReadOnly(True)
        self._body_view.setFont(QFont("monospace", 9))
        self._body_view.setPlaceholderText(t("function_body_placeholder"))
        body_layout.addWidget(self._body_view)
        right_layout.addWidget(body_group, 2)

        # Option-2 summary panel (visible only for opt2)
        self._opt2_panel = QGroupBox(t("opt2_panel_title"))
        opt2_layout = QVBoxLayout(self._opt2_panel)
        self._summary_edit = QPlainTextEdit()
        self._summary_edit.setPlaceholderText(t("opt2_summary_placeholder"))
        opt2_layout.addWidget(self._summary_edit)
        right_layout.addWidget(self._opt2_panel, 1)

        # Hint display
        hint_group = QGroupBox(t("hint_group_title"))
        hint_layout = QVBoxLayout(hint_group)
        self._hint_edit = QTextEdit()
        self._hint_edit.setReadOnly(True)
        self._hint_edit.setPlaceholderText(t("hint_placeholder"))
        hint_layout.addWidget(self._hint_edit)
        right_layout.addWidget(hint_group, 1)

        # Match decision
        match_group = QGroupBox(t("match_group_title"))
        match_layout = QVBoxLayout(match_group)
        match_fields = QHBoxLayout()
        match_fields.addWidget(QLabel(t("component_label")))
        self._comp_edit = QLineEdit()
        self._comp_edit.setPlaceholderText(t("component_placeholder"))
        match_fields.addWidget(self._comp_edit, 2)
        match_fields.addWidget(QLabel(t("license_label_match")))
        self._lic_edit = QLineEdit()
        self._lic_edit.setPlaceholderText(t("license_placeholder"))
        match_fields.addWidget(self._lic_edit, 1)
        match_btn = QPushButton(t("match_btn"))
        match_btn.clicked.connect(self._on_match_clicked)
        match_fields.addWidget(match_btn)
        match_layout.addLayout(match_fields)
        right_layout.addWidget(match_group)

        h_splitter.addWidget(right)
        h_splitter.setSizes([280, 820])

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        back_btn = QPushButton(t("back_to_scan_btn"))
        back_btn.clicked.connect(self.back_requested)
        bottom_row.addWidget(back_btn)
        bottom_row.addStretch()
        export_btn = QPushButton(t("sbom_export_btn"))
        export_btn.clicked.connect(self._on_export_clicked)
        bottom_row.addWidget(export_btn)
        root.addLayout(bottom_row)

        self._update_ui_for_option(OPTION_2_LOCAL_SUMMARY)

    # ── Option switching ───────────────────────────────────────────────────────

    @Slot(int, bool)
    def _on_option_changed(self, option_id: int, checked: bool) -> None:
        if checked:
            self._update_ui_for_option(option_id)

    def _update_ui_for_option(self, option_id: int) -> None:
        is_opt2 = option_id == OPTION_2_LOCAL_SUMMARY
        self._opt2_panel.setVisible(is_opt2)
        self._opt2_ext_btn.setVisible(is_opt2)

        labels = {
            OPTION_1_LOCAL_DIRECT:    t("option1_label"),
            OPTION_2_LOCAL_SUMMARY:   t("option2_summarise_label"),
            OPTION_3_EXTERNAL_DIRECT: t("option3_label"),
        }
        self._analyse_btn.setText(labels.get(option_id, t("analyse_btn_default")))

    def _selected_option(self) -> int:
        return self._option_btn_group.checkedId()

    # ── File list ──────────────────────────────────────────────────────────────

    def _filtered_files(self) -> list[ClassifiedFile]:
        files = self._all_files
        if self._preselected_paths is not None:
            files = [f for f in files if f.file_info.path in self._preselected_paths]
        sel = self._filter_combo.currentText()
        if sel == t("filter_unknown_only"):
            return [f for f in files if f.classification == Classification.UNKNOWN]
        if sel == t("filter_inferred_only"):
            return [f for f in files if f.classification == Classification.INFERRED]
        if sel == t("filter_confirmed_only"):
            return [f for f in files if f.classification == Classification.CONFIRMED]
        return list(files)

    def _refresh_file_list(self) -> None:
        self._file_list.clear()
        for cf in self._filtered_files():
            item = QListWidgetItem(self._file_label(cf))
            item.setBackground(QColor(_CLASS_BG[cf.classification]))
            item.setForeground(QColor(_CLASS_FG[cf.classification]))
            self._file_list.addItem(item)
        if self._file_list.count():
            self._file_list.setCurrentRow(0)

    def _file_label(self, cf: ClassifiedFile) -> str:
        path = cf.file_info.path
        if self._source_root:
            try:
                path = path.relative_to(self._source_root)
            except ValueError:
                pass
        return f"[{cf.classification.value}] {path}"

    @Slot()
    def _on_filter_changed(self) -> None:
        self._refresh_file_list()
        self._extracted_functions = []
        self._function_list.clear()
        self._body_view.clear()

    @Slot()
    def _on_file_selection_changed(self) -> None:
        pass

    def _selected_classified_files(self) -> list[ClassifiedFile]:
        filtered = self._filtered_files()
        return [
            filtered[idx.row()]
            for idx in self._file_list.selectedIndexes()
            if idx.row() < len(filtered)
        ]

    # ── Function extraction ────────────────────────────────────────────────────

    def _on_extract_clicked(self) -> None:
        files = self._selected_classified_files() or self._filtered_files()
        if not files:
            QMessageBox.information(self, t("no_target_title"), t("no_target_msg"))
            return

        self._set_busy(True)
        self._extracted_functions = []
        self._function_list.clear()
        self._worker = _ExtractWorker(files)
        self._worker.progress.connect(self._on_extract_progress)
        self._worker.finished.connect(self._on_extract_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(int, int, str)
    def _on_extract_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)

    @Slot(list)
    def _hint_text_for(self, key: tuple) -> str:
        """Return the text to display in the hint area for *key*.

        - Parse error: error message + raw LLM response
        - Parse success: extracted hint field
        - No result: empty string
        """
        if key in self._fn_errors:
            raw = self._fn_hints.get(key, "")
            return t("parse_error_msg") + ("\n\n" + raw if raw else "")
        if key in self._fn_auto_parsed:
            _, _, hint = self._fn_auto_parsed[key]
            return hint
        return self._fn_hints.get(key, "")

    def _on_extract_finished(self, functions: list) -> None:
        self._set_busy(False)
        self._extracted_functions = functions
        self._refresh_function_list()

    def _refresh_function_list(self) -> None:
        self._function_list.clear()
        for fn in self._extracted_functions:
            key = _fn_key(fn)
            if key in self._fn_matches:
                marker = "\u2713 "   # ✓ matched
            elif key in self._fn_errors:
                marker = "\u2717 "   # ✗ parse error
            elif key in self._fn_hints or key in self._fn_summaries:
                marker = "~ "        # has result, not yet matched
            else:
                marker = "  "
            rel = fn.file_path
            if self._source_root:
                try:
                    rel = fn.file_path.relative_to(self._source_root)
                except ValueError:
                    pass
            self._function_list.addItem(f"{marker}{fn.name}  ({rel}:{fn.start_line})")
        if self._extracted_functions:
            self._function_list.setCurrentRow(0)

    # ── Function selection ─────────────────────────────────────────────────────

    @Slot(int)
    def _on_function_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._extracted_functions):
            self._current_fn = None
            self._body_view.clear()
            self._body_view.setExtraSelections([])
            self._hint_edit.clear()
            self._summary_edit.clear()
            self._comp_edit.clear()
            self._lic_edit.clear()
            return

        fn = self._current_fn = self._extracted_functions[row]
        try:
            full_text = fn.file_path.read_text(errors="replace")
        except OSError:
            full_text = fn.body
        self._body_view.setPlainText(full_text)
        self._highlight_function_lines(fn.start_line, fn.end_line)

        key = _fn_key(fn)
        self._hint_edit.setPlainText(self._hint_text_for(key))
        self._summary_edit.setPlainText(self._fn_summaries.get(key, ""))

        if key in self._fn_matches:
            comp, lic = self._fn_matches[key]
        elif key in self._fn_auto_parsed:
            comp, lic, _ = self._fn_auto_parsed[key]
        else:
            comp, lic = "", ""
        self._comp_edit.setText(comp)
        self._lic_edit.setText(lic)

    def _highlight_function_lines(self, start_line: int, end_line: int) -> None:
        """Highlight lines *start_line* through *end_line* (1-indexed) in the body view."""
        doc = self._body_view.document()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffffaa"))

        selections = []
        for line_no in range(start_line - 1, end_line):
            block = doc.findBlockByLineNumber(line_no)
            if not block.isValid():
                break
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)

        self._body_view.setExtraSelections(selections)

        # Scroll to the function start
        if start_line >= 1:
            block = doc.findBlockByLineNumber(start_line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                self._body_view.setTextCursor(cursor)
                self._body_view.ensureCursorVisible()

    # ── Option 2: save edited summary ─────────────────────────────────────────

    def _save_current_summary(self) -> None:
        """Save the edited summary text back to _fn_summaries."""
        if not self._current_fn:
            return
        self._fn_summaries[_fn_key(self._current_fn)] = (
            self._summary_edit.toPlainText().strip()
        )

    # ── Match decision ─────────────────────────────────────────────────────────

    def _on_match_clicked(self) -> None:
        if not self._current_fn:
            return
        comp = self._comp_edit.text().strip()
        lic  = self._lic_edit.text().strip()
        key  = _fn_key(self._current_fn)
        self._fn_matches[key] = (comp, lic)
        if self._store:
            self._store.save_match(self._current_fn, comp, lic)
        self._refresh_function_list()
        # Restore selection
        row = self._extracted_functions.index(self._current_fn)
        self._function_list.setCurrentRow(row)

    # ── Batch analysis ─────────────────────────────────────────────────────────

    def _on_batch_clicked(self) -> None:
        option = self._selected_option()

        if not self._extracted_functions:
            QMessageBox.information(self, t("no_functions_title"), t("no_functions_msg"))
            return

        if option == OPTION_1_LOCAL_DIRECT:
            if not self._local_llm:
                QMessageBox.warning(self, t("model_not_set_title"), t("local_model_not_set_msg"))
                return
            if not self._local_llm.is_available():
                QMessageBox.warning(self, t("ollama_not_connected_title"),
                    t("ollama_not_connected_msg_short", api_base=self._local_llm.api_base))
                return
            self._start_batch("analyse", self._extracted_functions,
                              self._local_llm.query_direct, option)

        elif option == OPTION_2_LOCAL_SUMMARY:
            if not self._local_llm:
                QMessageBox.warning(self, t("model_not_set_title"), t("local_model_not_set_msg"))
                return
            if not self._local_llm.is_available():
                QMessageBox.warning(self, t("ollama_not_connected_title"),
                    t("ollama_not_connected_msg_short", api_base=self._local_llm.api_base))
                return
            self._start_batch("summarise", self._extracted_functions,
                              self._local_llm.summarise_function, option)

        else:  # OPTION_3
            if not self._external_llm:
                QMessageBox.warning(self, t("model_not_set_title"), t("external_model_not_set_msg"))
                return
            confirm = QMessageBox.question(
                self, t("confirm_send_external_title"),
                t("confirm_send_external_msg", count=len(self._extracted_functions)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            self._start_batch("analyse", self._extracted_functions,
                              self._external_llm.query_direct, option)

    def _on_opt2_send_external_clicked(self) -> None:
        """Option 2 step 2: send all summaries to external LLM."""
        if not self._external_llm:
            QMessageBox.warning(self, t("model_not_set_title"), t("external_model_not_set_msg"))
            return

        # Save any pending edits to the current function's summary
        self._save_current_summary()

        fns_with_summary = [
            fn for fn in self._extracted_functions
            if self._fn_summaries.get(_fn_key(fn), "").strip()
        ]
        if not fns_with_summary:
            QMessageBox.information(self, t("no_summaries_title"), t("no_summaries_msg"))
            return

        confirm = QMessageBox.question(
            self, t("confirm_send_external_title"),
            t("confirm_send_external_msg", count=len(fns_with_summary)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Build copies of FunctionInfo using summary as the "body"
        fn_copies = [
            FunctionInfo(
                name=fn.name,
                file_path=fn.file_path,
                start_line=fn.start_line,
                end_line=fn.end_line,
                body=self._fn_summaries[_fn_key(fn)],
            )
            for fn in fns_with_summary
        ]
        self._start_batch("analyse", fn_copies,
                          self._external_llm.query_direct, OPTION_2_LOCAL_SUMMARY)

    def _start_batch(
        self,
        mode: str,
        functions: list[FunctionInfo],
        llm_callable,
        option: int,
    ) -> None:
        self._batch_mode     = mode
        self._current_option = option
        self._set_busy(True)
        self._worker = _BatchWorker(functions, llm_callable)
        self._worker.fn_started.connect(self._on_batch_fn_started)
        self._worker.fn_finished.connect(self._on_batch_fn_finished)
        self._worker.all_finished.connect(self._on_batch_all_finished)
        self._worker.start()

    @Slot(int, int, str)
    def _on_batch_fn_started(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        name_display = name[:_MAX_NAME_LEN] + "\u2026" if len(name) > _MAX_NAME_LEN else name
        if self._batch_mode == "summarise":
            self._results_label.setText(
                t("summarise_progress", current=current + 1, total=total, name=name_display)
            )
        else:
            self._results_label.setText(
                t("analysing_progress", current=current + 1, total=total, name=name_display)
            )

    @Slot(object, str)
    def _on_batch_fn_finished(self, fn: FunctionInfo, result: str) -> None:
        key = _fn_key(fn)
        if self._batch_mode == "summarise":
            self._fn_summaries[key] = result
        else:
            self._fn_hints[key] = result
            if self._store:
                self._store.save_result(fn, self._current_option, result)
            parsed = parse_oss_response(result)
            if parsed is not None:
                self._fn_auto_parsed[key] = parsed
                self._fn_errors.discard(key)
            else:
                self._fn_errors.add(key)
                self._fn_auto_parsed.pop(key, None)

        if self._current_fn and key == _fn_key(self._current_fn):
            if self._batch_mode == "summarise":
                self._summary_edit.setPlainText(result)
            else:
                self._hint_edit.setPlainText(self._hint_text_for(key))
                if key not in self._fn_matches:
                    comp, lic, _ = self._fn_auto_parsed.get(key, ("", "", ""))
                    self._comp_edit.setText(comp)
                    self._lic_edit.setText(lic)

    @Slot()
    def _on_batch_all_finished(self) -> None:
        self._set_busy(False)
        if self._batch_mode == "summarise":
            self._results_label.setText(
                t("summarise_complete", count=len(self._fn_summaries))
            )
        else:
            self._results_label.setText(
                t("analysis_complete", count=len(self._fn_hints))
            )
        self._refresh_function_list()

    # ── Delete results ─────────────────────────────────────────────────────────

    def _on_delete_results_clicked(self) -> None:
        if not self._store or not self._store.exists():
            QMessageBox.information(self, t("no_results_title"), t("no_results_msg"))
            return
        confirm = QMessageBox.question(
            self, t("delete_results_title"), t("delete_results_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._store.delete()
        self._fn_hints.clear()
        self._fn_summaries.clear()
        self._fn_matches.clear()
        self._fn_auto_parsed.clear()
        self._fn_errors.clear()
        self._results_label.setText(t("results_deleted"))
        self._refresh_function_list()
        self._hint_edit.clear()

    # ── SBOM export ────────────────────────────────────────────────────────────

    def _on_export_clicked(self) -> None:
        self._apply_matches_to_components()
        self.export_requested.emit(self._components)

    def _apply_matches_to_components(self) -> None:
        """Rebuild component list based on user match decisions.

        Matched files are split out of their original components into new
        per-decision components so that one function match does not silently
        alter every other file that shared a LICENSE directory.
        """
        if not self._fn_matches:
            return

        # Build file_path → (component_name, license) from matched functions
        file_matches: dict[Path, tuple[str, str]] = {}
        for fn in self._extracted_functions:
            key = _fn_key(fn)
            if key in self._fn_matches:
                comp_name, lic = self._fn_matches[key]
                if comp_name or lic:
                    file_matches[fn.file_path.resolve()] = (comp_name, lic)

        if not file_matches:
            return

        matched_paths = set(file_matches.keys())

        # Record original component for each file before we mutate anything
        original_comp: dict[Path, Component] = {}
        for comp in self._components:
            for f in comp.files:
                original_comp[f.resolve()] = comp

        # Keep original components but remove matched files from them
        surviving: list[Component] = []
        for comp in self._components:
            remaining = [f for f in comp.files if f.resolve() not in matched_paths]
            if remaining:
                comp.files = remaining
                surviving.append(comp)

        # Group matched files by their (comp_name, license) decision
        decision_groups: dict[tuple[str, str], list[Path]] = {}
        for fp, decision in file_matches.items():
            decision_groups.setdefault(decision, []).append(fp)

        prio = [Classification.CONFIRMED, Classification.INFERRED, Classification.UNKNOWN]
        for (comp_name, lic), file_paths in decision_groups.items():
            classes = {
                original_comp[fp].classification
                for fp in file_paths
                if fp in original_comp
            }
            main_class = next((c for c in prio if c in classes), Classification.UNKNOWN)
            surviving.append(Component(
                name=comp_name or "unknown",
                directory=file_paths[0].parent,
                files=file_paths,
                classification=main_class,
                license_expression=lic or None,
            ))

        self._components = surviving

    # ── Shared helpers ─────────────────────────────────────────────────────────

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, t("llm_error_title"), message)

    def _set_busy(self, busy: bool) -> None:
        self._analyse_btn.setEnabled(not busy)
        self._filter_combo.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
