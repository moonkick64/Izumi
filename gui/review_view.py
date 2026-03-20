"""UNKNOWN review view – local-LLM summary display/edit and approval."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analyzer.classifier import Classification
from analyzer.models import Component, FunctionSummary
from llm.local_llm import LocalLLM
from llm.external_llm import ExternalLLM


# ── Background worker for local-LLM summarisation ─────────────────────────

class SummariseWorker(QThread):
    """Summarises a single component's functions via local LLM."""

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


# ── Main view ─────────────────────────────────────────────────────────────

class ReviewView(QWidget):
    """Screen 3: review LLM summaries for UNKNOWN components."""

    back_requested = Signal()
    export_requested = Signal(list)  # list[Component]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._components: list[Component] = []
        self._current_component: Optional[Component] = None
        self._current_summary_index: int = -1
        self._worker: Optional[SummariseWorker] = None

        self._local_llm = LocalLLM()
        self._external_llm = ExternalLLM()

        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────

    def set_components(self, components: list[Component]) -> None:
        self._components = components
        self._refresh_component_list()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        root.addWidget(QLabel("UNKNOWN コンポーネントのレビュー"))

        # Main splitter: left=component list, right=detail
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── Left: component list ──────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("コンポーネント一覧"))

        self._component_list = QListWidget()
        self._component_list.currentRowChanged.connect(self._on_component_selected)
        left_layout.addWidget(self._component_list)

        self._summarise_btn = QPushButton("ローカルLLMで要約生成")
        self._summarise_btn.clicked.connect(self._on_summarise_clicked)
        left_layout.addWidget(self._summarise_btn)

        splitter.addWidget(left)

        # ── Right: detail panel ───────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Function summary list
        right_layout.addWidget(QLabel("関数一覧と要約"))
        self._summary_list = QListWidget()
        self._summary_list.currentRowChanged.connect(self._on_summary_selected)
        right_layout.addWidget(self._summary_list)

        # Summary edit + approve
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

        right_layout.addWidget(edit_group)

        # Hint display
        hint_group = QGroupBox("外部LLMからのヒント（参考情報・確定情報ではありません）")
        hint_layout = QVBoxLayout(hint_group)
        self._hint_edit = QTextEdit()
        self._hint_edit.setReadOnly(True)
        self._hint_edit.setPlaceholderText("外部LLMへ送信すると、ここにヒントが表示されます。")
        hint_layout.addWidget(self._hint_edit)

        send_ext_btn = QPushButton("承認済み要約を外部LLMに送信")
        send_ext_btn.clicked.connect(self._on_send_external)
        hint_layout.addWidget(send_ext_btn)

        right_layout.addWidget(hint_group)

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

    # ── Data population ───────────────────────────────────────────────────

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
            label = f"{'✓' if fs.approved else '○'} {fs.function_name} ({fs.file_path.name}:{fs.start_line})"
            self._summary_list.addItem(label)

    # ── Slots ─────────────────────────────────────────────────────────────

    @Slot(int)
    def _on_component_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._components):
            return
        self._current_component = self._components[row]
        self._refresh_summary_list()

        # Show existing hint if any
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

    def _on_summarise_clicked(self) -> None:
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

        self._summarise_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(True)

        self._worker = SummariseWorker(self._current_component, self._local_llm)
        self._worker.progress.connect(self._on_summarise_progress)
        self._worker.finished.connect(self._on_summarise_finished)
        self._worker.error.connect(self._on_summarise_error)
        self._worker.start()

    @Slot(int, int, str)
    def _on_summarise_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)

    @Slot(object)
    def _on_summarise_finished(self, component: Component) -> None:
        self._progress_bar.setVisible(False)
        self._summarise_btn.setEnabled(True)
        self._refresh_summary_list()

    @Slot(str)
    def _on_summarise_error(self, message: str) -> None:
        self._progress_bar.setVisible(False)
        self._summarise_btn.setEnabled(True)
        QMessageBox.critical(self, "要約エラー", message)

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
