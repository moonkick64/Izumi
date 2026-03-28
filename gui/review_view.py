"""LLM SCA review view – function-level analysis with 3 LLM options.

All three options operate on C/C++ functions extracted from source files:
  Option 1: send function body directly to local LLM
  Option 2: local LLM summarises → user edits/approves → external LLM identifies OSS
  Option 3: send function body directly to external LLM
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QFont

from analyzer.classifier import Classification, ClassificationResult, ClassifiedFile
from analyzer.models import Component, FunctionSummary
from analyzer.parser import extract_functions, FunctionInfo
from llm.local_llm import LocalLLM
from llm.external_llm import ExternalLLM


# ── Classification filter ──────────────────────────────────────────────────────

_FILTER_UNKNOWN   = "UNKNOWN のみ"
_FILTER_ALL       = "全て"
_FILTER_INFERRED  = "INFERRED のみ"
_FILTER_CONFIRMED = "CONFIRMED のみ"

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


# ── Key type for per-function storage ─────────────────────────────────────────

def _fn_key(fn: FunctionInfo) -> tuple:
    return (fn.file_path, fn.name, fn.start_line)


# ── Background workers ─────────────────────────────────────────────────────────

class _ExtractWorker(QThread):
    """Extracts C/C++ functions from a list of files."""

    progress = Signal(int, int, str)   # current, total, filename
    finished = Signal(list)            # list[FunctionInfo]
    error    = Signal(str)

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


class _AnalyseWorker(QThread):
    """Sends a function body to LLM (Option 1 direct local / Option 3 direct external)."""

    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, function_body: str, llm_callable) -> None:
        super().__init__()
        self._function_body = function_body
        self._llm_callable  = llm_callable

    def run(self) -> None:
        try:
            result = self._llm_callable(self._function_body)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _SummariseWorker(QThread):
    """Summarises a single function body via local LLM (Option 2 step a–b)."""

    finished = Signal(str)   # summary text
    error    = Signal(str)

    def __init__(self, function_body: str, llm: LocalLLM) -> None:
        super().__init__()
        self._function_body = function_body
        self._llm = llm

    def run(self) -> None:
        try:
            result = self._llm.summarise_function(self._function_body)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _BatchWorker(QThread):
    """Runs LLM analysis on multiple functions sequentially (Options 1 / 3)."""

    fn_started  = Signal(int, int, str)   # current, total, func_name
    fn_finished = Signal(object, str)     # FunctionInfo, hint
    all_finished = Signal()

    def __init__(self, functions: list[FunctionInfo], llm_callable) -> None:
        super().__init__()
        self._functions   = functions
        self._llm_callable = llm_callable

    def run(self) -> None:
        for i, fn in enumerate(self._functions):
            if self.isInterruptionRequested():
                break
            self.fn_started.emit(i, len(self._functions), fn.name)
            try:
                hint = self._llm_callable(fn.body)
            except Exception as exc:
                hint = f"[ERROR] {exc}"
            self.fn_finished.emit(fn, hint)
        self.all_finished.emit()


# ── Main view ──────────────────────────────────────────────────────────────────

class ReviewView(QWidget):
    """Screen 3: LLM SCA review at the function level."""

    back_requested   = Signal()
    export_requested = Signal(list)  # list[Component]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._all_files: list[ClassifiedFile] = []
        self._components: list[Component] = []
        self._source_root: Optional[Path] = None
        self._preselected_paths: Optional[set[Path]] = None

        # Extracted functions and current selection
        self._extracted_functions: list[FunctionInfo] = []
        self._current_fn: Optional[FunctionInfo] = None

        # Per-function storage: key = (file_path, func_name, start_line)
        self._fn_hints: dict[tuple, str] = {}
        self._fn_summaries: dict[tuple, FunctionSummary] = {}

        self._worker: Optional[QThread] = None

        self._local_llm    = LocalLLM()
        self._external_llm = ExternalLLM()

        self._build_ui()

    # ── Public API ─────────────────────────────────────────────────────────────

    def configure_llm(
        self,
        ollama_url: str = "http://localhost:11434",
        local_model: str = "ollama/codellama",
        external_model: str = "claude-sonnet-4-20250514",
        api_key: str = "",
    ) -> None:
        self._local_llm    = LocalLLM(model=local_model, api_base=ollama_url)
        self._external_llm = ExternalLLM(model=external_model, api_key=api_key)

    def set_data(
        self,
        classification: ClassificationResult,
        components: list[Component],
        source_root: Optional[Path] = None,
        preselected_paths: Optional[list[Path]] = None,
    ) -> None:
        self._all_files          = classification.all_files
        self._components         = components
        self._source_root        = source_root
        self._preselected_paths  = set(preselected_paths) if preselected_paths else None
        self._extracted_functions = []
        self._current_fn          = None
        self._fn_hints.clear()
        self._fn_summaries.clear()
        self._refresh_file_list()
        self._function_list.clear()
        self._body_view.clear()
        self._hint_edit.clear()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(QLabel("LLM SCA レビュー（関数単位）"))

        # ── LLM option selector ────────────────────────────────────────────────
        option_group = QGroupBox("LLM 解析オプション")
        option_layout = QVBoxLayout(option_group)

        self._opt1_radio = QRadioButton(
            "オプション1: 関数のソースコードをローカルLLMに直接送信して特定"
        )
        self._opt2_radio = QRadioButton(
            "オプション2: ローカルLLMで要約 → ユーザー確認・編集 → 外部LLMに送信（機密情報保護）"
        )
        self._opt3_radio = QRadioButton(
            "オプション3: 関数のソースコードを外部LLMに直接送信して特定"
        )
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

        # ── Left: file list (top) + function list (bottom) ─────────────────────
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # File list pane
        file_pane = QWidget()
        file_layout = QVBoxLayout(file_pane)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(4)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("表示:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            _FILTER_UNKNOWN, _FILTER_ALL, _FILTER_INFERRED, _FILTER_CONFIRMED,
        ])
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo)
        file_layout.addLayout(filter_row)

        file_layout.addWidget(QLabel("ファイル一覧"))
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._file_list.itemSelectionChanged.connect(self._on_file_selection_changed)
        file_layout.addWidget(self._file_list)

        extract_btn = QPushButton("選択ファイルの関数を抽出")
        extract_btn.clicked.connect(self._on_extract_clicked)
        file_layout.addWidget(extract_btn)

        left_splitter.addWidget(file_pane)

        # Function list pane
        fn_pane = QWidget()
        fn_layout = QVBoxLayout(fn_pane)
        fn_layout.setContentsMargins(0, 0, 0, 0)
        fn_layout.setSpacing(4)

        fn_layout.addWidget(QLabel("関数一覧"))
        self._function_list = QListWidget()
        self._function_list.currentRowChanged.connect(self._on_function_selected)
        fn_layout.addWidget(self._function_list)

        btn_row = QHBoxLayout()
        self._analyse_btn = QPushButton("LLM で解析")
        self._analyse_btn.clicked.connect(self._on_analyse_clicked)
        btn_row.addWidget(self._analyse_btn)
        self._batch_btn = QPushButton("一括解析")
        self._batch_btn.clicked.connect(self._on_batch_clicked)
        btn_row.addWidget(self._batch_btn)
        fn_layout.addLayout(btn_row)

        left_splitter.addWidget(fn_pane)
        left_splitter.setSizes([200, 200])
        h_splitter.addWidget(left_splitter)

        # ── Right: body viewer + option-2 panel + hint ─────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        body_group = QGroupBox("関数ソースコード")
        body_layout = QVBoxLayout(body_group)
        self._body_view = QPlainTextEdit()
        self._body_view.setReadOnly(True)
        self._body_view.setFont(QFont("monospace", 9))
        self._body_view.setPlaceholderText("関数を選択するとここにソースコードが表示されます。")
        body_layout.addWidget(self._body_view)
        right_layout.addWidget(body_group, 2)

        # Option 2 panel (summary edit + approve)
        self._opt2_panel = QGroupBox("要約（編集可能・外部LLMへの送信前に確認してください）")
        opt2_layout = QVBoxLayout(self._opt2_panel)

        self._summary_edit = QPlainTextEdit()
        self._summary_edit.setPlaceholderText(
            "「LLMで解析」を押すとローカルLLMが要約を生成します。"
            "機密情報が含まれる場合はここで編集してから送信してください。"
        )
        opt2_layout.addWidget(self._summary_edit)

        approve_row = QHBoxLayout()
        self._approve_check = QCheckBox("外部LLMへの送信を承認")
        approve_row.addWidget(self._approve_check)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save_summary)
        approve_row.addWidget(save_btn)
        send_ext_btn = QPushButton("承認済み要約を外部LLMに送信")
        send_ext_btn.clicked.connect(self._on_send_external)
        approve_row.addWidget(send_ext_btn)
        opt2_layout.addLayout(approve_row)
        right_layout.addWidget(self._opt2_panel, 1)

        # Hint display (shared)
        hint_group = QGroupBox("LLMからのヒント（参考情報・確定情報ではありません）")
        hint_layout = QVBoxLayout(hint_group)
        self._hint_edit = QTextEdit()
        self._hint_edit.setReadOnly(True)
        self._hint_edit.setPlaceholderText("LLMで解析すると、ここにヒントが表示されます。")
        hint_layout.addWidget(self._hint_edit)
        right_layout.addWidget(hint_group, 1)

        h_splitter.addWidget(right)
        h_splitter.setSizes([280, 820])

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        back_btn = QPushButton("← スキャン結果に戻る")
        back_btn.clicked.connect(self.back_requested)
        bottom_row.addWidget(back_btn)
        bottom_row.addStretch()
        export_btn = QPushButton("SBOM 出力 →")
        export_btn.clicked.connect(lambda: self.export_requested.emit(self._components))
        bottom_row.addWidget(export_btn)
        root.addLayout(bottom_row)

        self._update_ui_for_option(OPTION_2_LOCAL_SUMMARY)

    # ── Option switching ───────────────────────────────────────────────────────

    @Slot(int, bool)
    def _on_option_changed(self, option_id: int, checked: bool) -> None:
        if checked:
            self._update_ui_for_option(option_id)

    def _update_ui_for_option(self, option_id: int) -> None:
        self._opt2_panel.setVisible(option_id == OPTION_2_LOCAL_SUMMARY)
        labels = {
            OPTION_1_LOCAL_DIRECT:    "ローカルLLMで直接解析",
            OPTION_2_LOCAL_SUMMARY:   "ローカルLLMで要約生成",
            OPTION_3_EXTERNAL_DIRECT: "外部LLMで直接解析",
        }
        self._analyse_btn.setText(labels.get(option_id, "LLM で解析"))

    def _selected_option(self) -> int:
        return self._option_btn_group.checkedId()

    # ── File list ──────────────────────────────────────────────────────────────

    def _filtered_files(self) -> list[ClassifiedFile]:
        files = self._all_files
        if self._preselected_paths is not None:
            files = [f for f in files if f.file_info.path in self._preselected_paths]
        sel = self._filter_combo.currentText()
        if sel == _FILTER_UNKNOWN:
            return [f for f in files if f.classification == Classification.UNKNOWN]
        if sel == _FILTER_INFERRED:
            return [f for f in files if f.classification == Classification.INFERRED]
        if sel == _FILTER_CONFIRMED:
            return [f for f in files if f.classification == Classification.CONFIRMED]
        return list(files)

    def _refresh_file_list(self) -> None:
        self._file_list.clear()
        for cf in self._filtered_files():
            label = self._file_label(cf)
            item = QListWidgetItem(label)
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
        # Selection change only clears the view; functions are extracted on demand
        pass

    def _selected_classified_files(self) -> list[ClassifiedFile]:
        """Return ClassifiedFile objects for currently selected rows in file list."""
        filtered = self._filtered_files()
        return [
            filtered[idx.row()]
            for idx in self._file_list.selectedIndexes()
            if idx.row() < len(filtered)
        ]

    # ── Function extraction ────────────────────────────────────────────────────

    def _on_extract_clicked(self) -> None:
        files = self._selected_classified_files()
        if not files:
            files = self._filtered_files()
        if not files:
            QMessageBox.information(self, "対象なし", "解析するファイルがありません。")
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
    def _on_extract_finished(self, functions: list) -> None:
        self._set_busy(False)
        self._extracted_functions = functions
        self._refresh_function_list()

    def _refresh_function_list(self) -> None:
        self._function_list.clear()
        for fn in self._extracted_functions:
            has_result = _fn_key(fn) in self._fn_hints or _fn_key(fn) in self._fn_summaries
            marker = "✓ " if has_result else ""
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
            self._hint_edit.clear()
            self._summary_edit.clear()
            return

        fn = self._current_fn = self._extracted_functions[row]
        self._body_view.setPlainText(fn.body)

        key = _fn_key(fn)
        self._hint_edit.setPlainText(self._fn_hints.get(key, ""))

        if key in self._fn_summaries:
            fs = self._fn_summaries[key]
            self._summary_edit.setPlainText(fs.summary)
            self._approve_check.setChecked(fs.approved)
        else:
            self._summary_edit.clear()
            self._approve_check.setChecked(False)

    # ── Option 1 / 3: direct analyse ──────────────────────────────────────────

    def _on_analyse_clicked(self) -> None:
        option = self._selected_option()
        if option == OPTION_1_LOCAL_DIRECT:
            self._run_direct(use_external=False)
        elif option == OPTION_2_LOCAL_SUMMARY:
            self._run_summarise()
        elif option == OPTION_3_EXTERNAL_DIRECT:
            self._run_direct(use_external=True)

    def _run_direct(self, use_external: bool) -> None:
        if not self._current_fn:
            QMessageBox.information(self, "未選択", "解析する関数を選択してください。")
            return

        if use_external:
            confirm = QMessageBox.question(
                self, "外部LLMへの送信確認",
                "関数のソースコードをそのまま外部LLMに送信します。\n"
                "機密情報が含まれていないか確認してください。\n\n送信しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            llm_callable = self._external_llm.query_direct
        else:
            if not self._local_llm.is_available():
                QMessageBox.warning(
                    self, "Ollama 未接続",
                    f"Ollama に接続できません ({self._local_llm.api_base})。\n"
                    "Ollama が起動しているか確認してください。",
                )
                return
            llm_callable = self._local_llm.query_direct

        self._set_busy(True)
        self._worker = _AnalyseWorker(self._current_fn.body, llm_callable)
        self._worker.finished.connect(self._on_direct_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(str)
    def _on_direct_finished(self, hint: str) -> None:
        self._set_busy(False)
        if self._current_fn:
            self._fn_hints[_fn_key(self._current_fn)] = hint
            self._refresh_function_list()
            # Restore selection
            row = self._function_list.currentRow()
            if row >= 0:
                self._function_list.setCurrentRow(row)
        self._hint_edit.setPlainText(hint)

    # ── Option 2: summarise ────────────────────────────────────────────────────

    def _run_summarise(self) -> None:
        if not self._current_fn:
            QMessageBox.information(self, "未選択", "要約する関数を選択してください。")
            return
        if not self._local_llm.is_available():
            QMessageBox.warning(
                self, "Ollama 未接続",
                f"Ollama に接続できません ({self._local_llm.api_base})。\n"
                "Ollama が起動しているか確認してください。",
            )
            return

        self._set_busy(True)
        self._worker = _SummariseWorker(self._current_fn.body, self._local_llm)
        self._worker.finished.connect(self._on_summarise_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(str)
    def _on_summarise_finished(self, summary: str) -> None:
        self._set_busy(False)
        if not self._current_fn:
            return
        key = _fn_key(self._current_fn)
        fn = self._current_fn
        fs = FunctionSummary(
            function_name=fn.name,
            file_path=fn.file_path,
            start_line=fn.start_line,
            end_line=fn.end_line,
            body=fn.body,
            summary=summary,
        )
        self._fn_summaries[key] = fs
        self._summary_edit.setPlainText(summary)
        self._approve_check.setChecked(False)

    def _on_save_summary(self) -> None:
        if not self._current_fn:
            return
        key = _fn_key(self._current_fn)
        fn = self._current_fn
        if key not in self._fn_summaries:
            self._fn_summaries[key] = FunctionSummary(
                function_name=fn.name,
                file_path=fn.file_path,
                start_line=fn.start_line,
                end_line=fn.end_line,
                body=fn.body,
            )
        fs = self._fn_summaries[key]
        fs.summary  = self._summary_edit.toPlainText().strip()
        fs.approved = self._approve_check.isChecked()
        self._refresh_function_list()

    def _on_send_external(self) -> None:
        approved = [
            fs.summary for fs in self._fn_summaries.values()
            if fs.approved and fs.summary and not fs.summary.startswith("[ERROR]")
        ]
        if not approved:
            QMessageBox.information(
                self, "承認済み要約なし",
                "送信する要約を選択し「承認」チェックをオンにして保存してください。",
            )
            return
        try:
            hint = self._external_llm.find_similar_oss(approved)
            self._hint_edit.setPlainText(hint or "ヒントなし")
        except Exception as exc:
            QMessageBox.critical(self, "外部LLMエラー", str(exc))

    # ── Batch analysis (Options 1 / 3) ────────────────────────────────────────

    def _on_batch_clicked(self) -> None:
        option = self._selected_option()
        if option == OPTION_2_LOCAL_SUMMARY:
            QMessageBox.information(
                self, "非対応",
                "一括解析はオプション1・3のみ対応しています。\n"
                "オプション2は関数ごとに要約・確認・承認が必要です。",
            )
            return

        if not self._extracted_functions:
            QMessageBox.information(self, "関数なし", "先に「選択ファイルの関数を抽出」を実行してください。")
            return

        if option == OPTION_1_LOCAL_DIRECT:
            if not self._local_llm.is_available():
                QMessageBox.warning(self, "Ollama 未接続",
                    f"Ollama に接続できません ({self._local_llm.api_base})。")
                return
            llm_callable = self._local_llm.query_direct
        else:
            confirm = QMessageBox.question(
                self, "外部LLMへの送信確認",
                f"{len(self._extracted_functions)} 個の関数のソースコードをそのまま外部LLMに送信します。\n"
                "機密情報が含まれていないか確認してください。\n\n送信しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            llm_callable = self._external_llm.query_direct

        self._set_busy(True)
        self._worker = _BatchWorker(self._extracted_functions, llm_callable)
        self._worker.fn_started.connect(self._on_batch_fn_started)
        self._worker.fn_finished.connect(self._on_batch_fn_finished)
        self._worker.all_finished.connect(self._on_batch_all_finished)
        self._worker.start()

    @Slot(int, int, str)
    def _on_batch_fn_started(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)

    @Slot(object, str)
    def _on_batch_fn_finished(self, fn: FunctionInfo, hint: str) -> None:
        self._fn_hints[_fn_key(fn)] = hint
        if self._current_fn and _fn_key(fn) == _fn_key(self._current_fn):
            self._hint_edit.setPlainText(hint)

    @Slot()
    def _on_batch_all_finished(self) -> None:
        self._set_busy(False)
        self._refresh_function_list()

    # ── Shared helpers ─────────────────────────────────────────────────────────

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "LLMエラー", message)

    def _set_busy(self, busy: bool) -> None:
        self._analyse_btn.setEnabled(not busy)
        self._batch_btn.setEnabled(not busy)
        self._filter_combo.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
