"""LLM SCA review view – file-level analysis with 3 LLM options."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
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
from PySide6.QtGui import QColor

from analyzer.classifier import Classification, ClassificationResult, ClassifiedFile
from analyzer.models import Component, FunctionSummary
from analyzer.parser import extract_functions
from llm.local_llm import LocalLLM
from llm.external_llm import ExternalLLM


# ── Classification filter options ──────────────────────────────────────────────

_FILTER_ALL      = "全て"
_FILTER_UNKNOWN  = "UNKNOWN のみ"
_FILTER_INFERRED = "INFERRED のみ"
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


# ── Background workers ─────────────────────────────────────────────────────────

class _DirectQueryWorker(QThread):
    """Runs a direct OSS identification query (Option 1 or 3) in background."""

    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, source_code: str, llm_callable) -> None:
        super().__init__()
        self._source_code = source_code
        self._llm_callable = llm_callable

    def run(self) -> None:
        try:
            result = self._llm_callable(self._source_code)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _SummariseWorker(QThread):
    """Extracts and summarises functions in a single file (Option 2 step a–b)."""

    progress = Signal(int, int, str)   # current, total, function_name
    finished = Signal(list)            # list[FunctionSummary]
    error    = Signal(str)

    def __init__(self, file_path: Path, llm: LocalLLM) -> None:
        super().__init__()
        self._file_path = file_path
        self._llm = llm

    def run(self) -> None:
        try:
            functions = extract_functions(self._file_path)
            summaries: list[FunctionSummary] = []
            for i, fn in enumerate(functions):
                if not self.isInterruptionRequested():
                    self.progress.emit(i, len(functions), fn.name)
                summary_text = self._llm.summarise_function(fn.body)
                summaries.append(FunctionSummary(
                    function_name=fn.name,
                    file_path=fn.file_path,
                    start_line=fn.start_line,
                    end_line=fn.end_line,
                    body=fn.body,
                    summary=summary_text,
                ))
            self.finished.emit(summaries)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Main view ──────────────────────────────────────────────────────────────────

class ReviewView(QWidget):
    """Screen 3: LLM SCA review at the source file level."""

    back_requested   = Signal()
    export_requested = Signal(list)  # list[Component]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_files: list[ClassifiedFile] = []
        self._components: list[Component] = []
        self._source_root: Optional[Path] = None
        self._current_file: Optional[ClassifiedFile] = None
        self._current_summary_index: int = -1
        self._worker: Optional[QThread] = None

        # Per-file LLM result storage
        self._file_hints: dict[Path, str] = {}
        self._file_summaries: dict[Path, list[FunctionSummary]] = {}

        self._local_llm  = LocalLLM()
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
        """Apply LLM settings from the settings view."""
        self._local_llm   = LocalLLM(model=local_model, api_base=ollama_url)
        self._external_llm = ExternalLLM(model=external_model, api_key=api_key)

    def set_data(
        self,
        classification: ClassificationResult,
        components: list[Component],
        source_root: Optional[Path] = None,
    ) -> None:
        self._all_files   = classification.all_files
        self._components  = components
        self._source_root = source_root
        self._file_hints.clear()
        self._file_summaries.clear()
        self._current_file = None
        self._refresh_file_list()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(QLabel("LLM SCA レビュー（ソースファイル単位）"))

        # ── LLM option selector ────────────────────────────────────────────────
        option_group = QGroupBox("LLM 解析オプション")
        option_layout = QVBoxLayout(option_group)

        self._opt1_radio = QRadioButton(
            "オプション1: ローカルLLMにソースコードを直接送信して特定"
        )
        self._opt2_radio = QRadioButton(
            "オプション2: ローカルLLMで要約 → ユーザー確認・編集 → 外部LLMに送信（機密情報保護）"
        )
        self._opt3_radio = QRadioButton(
            "オプション3: 外部LLMにソースコードを直接送信して特定"
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

        # ── Main splitter: left=file list, right=detail ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Left: filter + file list + action button
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("表示:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            _FILTER_UNKNOWN,
            _FILTER_ALL,
            _FILTER_INFERRED,
            _FILTER_CONFIRMED,
        ])
        self._filter_combo.currentTextChanged.connect(self._refresh_file_list)
        filter_row.addWidget(self._filter_combo)
        left_layout.addLayout(filter_row)

        left_layout.addWidget(QLabel("ファイル一覧"))
        self._file_list = QListWidget()
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self._file_list)

        self._action_btn = QPushButton("LLM で解析")
        self._action_btn.clicked.connect(self._on_action_clicked)
        left_layout.addWidget(self._action_btn)

        splitter.addWidget(left)

        # Right: detail panels
        right = QWidget()
        self._right_layout = QVBoxLayout(right)
        self._right_layout.setContentsMargins(4, 0, 0, 0)

        # File header
        self._file_header = QLabel("")
        self._file_header.setWordWrap(True)
        self._right_layout.addWidget(self._file_header)

        # Option 2 panel (summary edit + approve)
        self._opt2_panel = QWidget()
        opt2_layout = QVBoxLayout(self._opt2_panel)
        opt2_layout.setContentsMargins(0, 0, 0, 0)

        opt2_layout.addWidget(QLabel("関数一覧と要約"))
        self._summary_list = QListWidget()
        self._summary_list.currentRowChanged.connect(self._on_summary_selected)
        opt2_layout.addWidget(self._summary_list)

        edit_group = QGroupBox("要約（編集可能）")
        edit_layout = QVBoxLayout(edit_group)
        self._summary_edit = QPlainTextEdit()
        self._summary_edit.setPlaceholderText(
            "ローカルLLMで要約を生成してください。"
            "機密情報が含まれる場合はここで編集してから送信してください。"
        )
        edit_layout.addWidget(self._summary_edit)

        approve_row = QHBoxLayout()
        self._approve_check = QCheckBox("外部LLMへの送信を承認")
        approve_row.addWidget(self._approve_check)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save_summary)
        approve_row.addWidget(save_btn)
        edit_layout.addLayout(approve_row)
        opt2_layout.addWidget(edit_group)

        send_ext_btn = QPushButton("承認済み要約を外部LLMに送信")
        send_ext_btn.clicked.connect(self._on_send_external)
        opt2_layout.addWidget(send_ext_btn)

        self._right_layout.addWidget(self._opt2_panel)

        # Hint display (shared across all options)
        hint_group = QGroupBox("LLMからのヒント（参考情報・確定情報ではありません）")
        hint_layout = QVBoxLayout(hint_group)
        self._hint_edit = QTextEdit()
        self._hint_edit.setReadOnly(True)
        self._hint_edit.setPlaceholderText("LLMで解析すると、ここにヒントが表示されます。")
        hint_layout.addWidget(self._hint_edit)
        self._right_layout.addWidget(hint_group)

        splitter.addWidget(right)
        splitter.setSizes([280, 820])

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        # Bottom buttons
        btn_row = QHBoxLayout()
        back_btn = QPushButton("← スキャン結果に戻る")
        back_btn.clicked.connect(self.back_requested)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        export_btn = QPushButton("SBOM 出力 →")
        export_btn.clicked.connect(lambda: self.export_requested.emit(self._components))
        btn_row.addWidget(export_btn)
        root.addLayout(btn_row)

        self._update_ui_for_option(OPTION_2_LOCAL_SUMMARY)

    # ── Filter & file list ─────────────────────────────────────────────────────

    def _filtered_files(self) -> list[ClassifiedFile]:
        sel = self._filter_combo.currentText()
        if sel == _FILTER_UNKNOWN:
            return [f for f in self._all_files if f.classification == Classification.UNKNOWN]
        if sel == _FILTER_INFERRED:
            return [f for f in self._all_files if f.classification == Classification.INFERRED]
        if sel == _FILTER_CONFIRMED:
            return [f for f in self._all_files if f.classification == Classification.CONFIRMED]
        return list(self._all_files)

    def _refresh_file_list(self) -> None:
        self._file_list.clear()
        files = self._filtered_files()
        for cf in files:
            label = self._file_label(cf)
            item = QListWidgetItem(label)
            item.setBackground(QColor(_CLASS_BG[cf.classification]))
            item.setForeground(QColor(_CLASS_FG[cf.classification]))
            self._file_list.addItem(item)
        if files:
            self._file_list.setCurrentRow(0)

    def _file_label(self, cf: ClassifiedFile) -> str:
        path = cf.file_info.path
        if self._source_root:
            try:
                path = path.relative_to(self._source_root)
            except ValueError:
                pass
        return f"[{cf.classification.value}] {path}"

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
        self._action_btn.setText(labels.get(option_id, "LLM で解析"))

    def _selected_option(self) -> int:
        return self._option_btn_group.checkedId()

    # ── File selection ─────────────────────────────────────────────────────────

    @Slot(int)
    def _on_file_selected(self, row: int) -> None:
        files = self._filtered_files()
        if row < 0 or row >= len(files):
            self._current_file = None
            self._file_header.setText("")
            self._hint_edit.clear()
            self._summary_list.clear()
            return

        cf = self._current_file = files[row]
        fg = _CLASS_FG[cf.classification]
        path = cf.file_info.path
        display_path = path
        if self._source_root:
            try:
                display_path = path.relative_to(self._source_root)
            except ValueError:
                pass
        self._file_header.setText(
            f"[{cf.classification.value}]  {display_path}  —  {cf.reason}"
        )
        self._file_header.setStyleSheet(
            f"color: {fg}; background: {_CLASS_BG[cf.classification]}; padding: 2px 4px;"
        )

        # Restore any existing results for this file
        hint = self._file_hints.get(path, "")
        self._hint_edit.setPlainText(hint)
        self._refresh_summary_list()

    # ── Summary list (Option 2) ────────────────────────────────────────────────

    def _refresh_summary_list(self) -> None:
        self._summary_list.clear()
        if not self._current_file:
            return
        summaries = self._file_summaries.get(self._current_file.file_info.path, [])
        for fs in summaries:
            label = (
                f"{'✓' if fs.approved else '○'} "
                f"{fs.function_name} (:{fs.start_line})"
            )
            self._summary_list.addItem(label)

    @Slot(int)
    def _on_summary_selected(self, row: int) -> None:
        if not self._current_file or row < 0:
            return
        summaries = self._file_summaries.get(self._current_file.file_info.path, [])
        if row >= len(summaries):
            return
        self._current_summary_index = row
        fs = summaries[row]
        self._summary_edit.setPlainText(fs.summary)
        self._approve_check.setChecked(fs.approved)

    def _on_save_summary(self) -> None:
        if not self._current_file or self._current_summary_index < 0:
            return
        summaries = self._file_summaries.get(self._current_file.file_info.path, [])
        if self._current_summary_index >= len(summaries):
            return
        fs = summaries[self._current_summary_index]
        fs.summary  = self._summary_edit.toPlainText().strip()
        fs.approved = self._approve_check.isChecked()
        self._refresh_summary_list()

    # ── Action button ──────────────────────────────────────────────────────────

    def _on_action_clicked(self) -> None:
        option = self._selected_option()
        if option == OPTION_1_LOCAL_DIRECT:
            self._run_direct_query(use_external=False)
        elif option == OPTION_2_LOCAL_SUMMARY:
            self._run_summarise()
        elif option == OPTION_3_EXTERNAL_DIRECT:
            self._run_direct_query(use_external=True)

    # ── Option 1 / 3: direct query ─────────────────────────────────────────────

    def _run_direct_query(self, use_external: bool) -> None:
        if not self._current_file:
            QMessageBox.information(self, "未選択", "解析するファイルを選択してください。")
            return

        if use_external:
            confirm = QMessageBox.question(
                self,
                "外部LLMへの送信確認",
                "ソースコードをそのまま外部LLMに送信します。\n"
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

        try:
            source_code = self._current_file.file_info.path.read_text(errors="replace")
        except OSError as exc:
            QMessageBox.critical(self, "読み込みエラー", str(exc))
            return

        self._set_busy(True)
        self._worker = _DirectQueryWorker(source_code, llm_callable)
        self._worker.finished.connect(self._on_direct_query_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(str)
    def _on_direct_query_finished(self, hint: str) -> None:
        self._set_busy(False)
        if self._current_file:
            self._file_hints[self._current_file.file_info.path] = hint
        self._hint_edit.setPlainText(hint)

    # ── Option 2: summarise ────────────────────────────────────────────────────

    def _run_summarise(self) -> None:
        if not self._current_file:
            QMessageBox.information(self, "未選択", "解析するファイルを選択してください。")
            return
        if not self._local_llm.is_available():
            QMessageBox.warning(
                self, "Ollama 未接続",
                f"Ollama に接続できません ({self._local_llm.api_base})。\n"
                "Ollama が起動しているか確認してください。",
            )
            return

        self._set_busy(True)
        self._worker = _SummariseWorker(self._current_file.file_info.path, self._local_llm)
        self._worker.progress.connect(self._on_summarise_progress)
        self._worker.finished.connect(self._on_summarise_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(int, int, str)
    def _on_summarise_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)

    @Slot(list)
    def _on_summarise_finished(self, summaries: list[FunctionSummary]) -> None:
        self._set_busy(False)
        if self._current_file:
            self._file_summaries[self._current_file.file_info.path] = summaries
        self._refresh_summary_list()

    def _on_send_external(self) -> None:
        if not self._current_file:
            return
        summaries = self._file_summaries.get(self._current_file.file_info.path, [])
        approved = [fs for fs in summaries if fs.approved]
        if not approved:
            QMessageBox.information(
                self, "承認済み要約なし",
                "送信する要約を選択し、「承認」チェックボックスをオンにして保存してください。",
            )
            return

        approved_texts = [
            fs.summary for fs in approved
            if fs.summary and not fs.summary.startswith("[ERROR]")
        ]
        try:
            hint = self._external_llm.find_similar_oss(approved_texts)
            if self._current_file:
                self._file_hints[self._current_file.file_info.path] = hint
            self._hint_edit.setPlainText(hint or "ヒントなし")
        except Exception as exc:
            QMessageBox.critical(self, "外部LLMエラー", str(exc))

    # ── Shared helpers ─────────────────────────────────────────────────────────

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "LLMエラー", message)

    def _set_busy(self, busy: bool) -> None:
        self._action_btn.setEnabled(not busy)
        self._filter_combo.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
