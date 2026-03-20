"""LLM SCA review view – UNKNOWN component analysis with 3 LLM options."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
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

from analyzer.classifier import Classification
from analyzer.models import Component, FunctionSummary
from llm.local_llm import LocalLLM
from llm.external_llm import ExternalLLM


# ── LLM option constants ───────────────────────────────────────────────────────

OPTION_1_LOCAL_DIRECT = 1
OPTION_2_LOCAL_SUMMARY = 2
OPTION_3_EXTERNAL_DIRECT = 3


# ── Background workers ─────────────────────────────────────────────────────────

class _DirectQueryWorker(QThread):
    """Runs a direct OSS identification query (Option 1 or 3) in background."""

    finished = Signal(str)   # hint text
    error = Signal(str)

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
    """Summarises a component's functions via local LLM (Option 2 step a–b)."""

    progress = Signal(int, int, str)
    finished = Signal(object)  # Component
    error = Signal(str)

    def __init__(self, component: Component, llm: LocalLLM) -> None:
        super().__init__()
        self._component = component
        self._llm = llm

    def run(self) -> None:
        try:
            self._llm.summarise_component(
                self._component,
                progress_callback=lambda i, n, name: self.progress.emit(i, n, name),
            )
            self.finished.emit(self._component)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Main view ──────────────────────────────────────────────────────────────────

class ReviewView(QWidget):
    """Screen 3: LLM SCA review for UNKNOWN components."""

    back_requested = Signal()
    export_requested = Signal(list)  # list[Component]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._components: list[Component] = []
        self._current_component: Optional[Component] = None
        self._current_summary_index: int = -1
        self._worker: Optional[QThread] = None

        self._local_llm = LocalLLM()
        self._external_llm = ExternalLLM()

        self._build_ui()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_components(self, components: list[Component]) -> None:
        self._components = components
        self._refresh_component_list()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        root.addWidget(QLabel("UNKNOWN コンポーネントの LLM SCA レビュー"))

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

        # ── Main splitter: left=component list, right=detail ───────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # Left: component list + action button
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("コンポーネント一覧"))

        self._component_list = QListWidget()
        self._component_list.currentRowChanged.connect(self._on_component_selected)
        left_layout.addWidget(self._component_list)

        self._action_btn = QPushButton("LLM で解析")
        self._action_btn.clicked.connect(self._on_action_clicked)
        left_layout.addWidget(self._action_btn)

        splitter.addWidget(left)

        # Right: stacked detail panels
        right = QWidget()
        self._right_layout = QVBoxLayout(right)
        self._right_layout.setContentsMargins(0, 0, 0, 0)

        # -- Option 2 panel (summary edit + approve) --
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

        # -- Hint display (shared across all options) --
        hint_group = QGroupBox("LLMからのヒント（参考情報・確定情報ではありません）")
        hint_layout = QVBoxLayout(hint_group)
        self._hint_edit = QTextEdit()
        self._hint_edit.setReadOnly(True)
        self._hint_edit.setPlaceholderText("LLMで解析すると、ここにヒントが表示されます。")
        hint_layout.addWidget(self._hint_edit)
        self._right_layout.addWidget(hint_group)

        splitter.addWidget(right)
        splitter.setSizes([250, 750])

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

    # ── Option switching ───────────────────────────────────────────────────────

    @Slot(int, bool)
    def _on_option_changed(self, option_id: int, checked: bool) -> None:
        if checked:
            self._update_ui_for_option(option_id)

    def _update_ui_for_option(self, option_id: int) -> None:
        is_opt2 = option_id == OPTION_2_LOCAL_SUMMARY
        self._opt2_panel.setVisible(is_opt2)

        labels = {
            OPTION_1_LOCAL_DIRECT: "ローカルLLMで直接解析",
            OPTION_2_LOCAL_SUMMARY: "ローカルLLMで要約生成",
            OPTION_3_EXTERNAL_DIRECT: "外部LLMで直接解析",
        }
        self._action_btn.setText(labels.get(option_id, "LLM で解析"))

    def _selected_option(self) -> int:
        return self._option_btn_group.checkedId()

    # ── Data population ────────────────────────────────────────────────────────

    def _refresh_component_list(self) -> None:
        self._component_list.clear()
        for comp in self._components:
            self._component_list.addItem(comp.name)
        if self._components:
            self._component_list.setCurrentRow(0)

    def _refresh_summary_list(self) -> None:
        self._summary_list.clear()
        if not self._current_component:
            return
        for fs in self._current_component.function_summaries:
            label = (
                f"{'✓' if fs.approved else '○'} "
                f"{fs.function_name} ({fs.file_path.name}:{fs.start_line})"
            )
            self._summary_list.addItem(label)

    # ── Slots ──────────────────────────────────────────────────────────────────

    @Slot(int)
    def _on_component_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._components):
            return
        self._current_component = self._components[row]
        self._refresh_summary_list()
        if self._current_component.oss_hint:
            self._hint_edit.setPlainText(self._current_component.oss_hint)
        else:
            self._hint_edit.clear()

    @Slot(int)
    def _on_summary_selected(self, row: int) -> None:
        if not self._current_component or row < 0:
            return
        summaries = self._current_component.function_summaries
        if row >= len(summaries):
            return
        self._current_summary_index = row
        fs = summaries[row]
        self._summary_edit.setPlainText(fs.summary)
        self._approve_check.setChecked(fs.approved)

    def _on_save_summary(self) -> None:
        if not self._current_component or self._current_summary_index < 0:
            return
        summaries = self._current_component.function_summaries
        if self._current_summary_index >= len(summaries):
            return
        fs = summaries[self._current_summary_index]
        fs.summary = self._summary_edit.toPlainText().strip()
        fs.approved = self._approve_check.isChecked()
        self._refresh_summary_list()

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
        if not self._current_component:
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
                    self,
                    "Ollama 未接続",
                    f"Ollama に接続できません ({self._local_llm.api_base})。\n"
                    "Ollama が起動しているか確認してください。",
                )
                return
            llm_callable = self._local_llm.query_direct

        # Collect all source code from component files
        source_parts: list[str] = []
        for file_path in self._current_component.files:
            try:
                source_parts.append(file_path.read_text(errors="replace"))
            except OSError:
                pass
        source_code = "\n\n".join(source_parts)

        if not source_code.strip():
            QMessageBox.information(self, "ソースなし", "解析対象のソースコードが見つかりません。")
            return

        self._set_busy(True)
        self._worker = _DirectQueryWorker(source_code, llm_callable)
        self._worker.finished.connect(self._on_direct_query_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(str)
    def _on_direct_query_finished(self, hint: str) -> None:
        self._set_busy(False)
        if self._current_component is not None:
            self._current_component.oss_hint = hint
        self._hint_edit.setPlainText(hint)

    # ── Option 2: summarise ────────────────────────────────────────────────────

    def _run_summarise(self) -> None:
        if not self._current_component:
            return
        if not self._local_llm.is_available():
            QMessageBox.warning(
                self,
                "Ollama 未接続",
                f"Ollama に接続できません ({self._local_llm.api_base})。\n"
                "Ollama が起動しているか確認してください。",
            )
            return

        self._set_busy(True)
        self._worker = _SummariseWorker(self._current_component, self._local_llm)
        self._worker.progress.connect(self._on_summarise_progress)
        self._worker.finished.connect(self._on_summarise_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @Slot(int, int, str)
    def _on_summarise_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)

    @Slot(object)
    def _on_summarise_finished(self, component: Component) -> None:
        self._set_busy(False)
        self._refresh_summary_list()

    def _on_send_external(self) -> None:
        if not self._current_component:
            return
        approved = [
            fs for fs in self._current_component.function_summaries if fs.approved
        ]
        if not approved:
            QMessageBox.information(
                self,
                "承認済み要約なし",
                "送信する要約を選択し、「承認」チェックボックスをオンにして保存してください。",
            )
            return

        try:
            self._external_llm.analyse_component(self._current_component)
            self._hint_edit.setPlainText(
                self._current_component.oss_hint or "ヒントなし"
            )
        except Exception as exc:
            QMessageBox.critical(self, "外部LLMエラー", str(exc))

    # ── Shared helpers ─────────────────────────────────────────────────────────

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "LLMエラー", message)

    def _set_busy(self, busy: bool) -> None:
        self._action_btn.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
