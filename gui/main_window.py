"""Main application window."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from analyzer.classifier import classify
from analyzer.grouper import group_into_components
from analyzer.models import Component
from analyzer.scanner import scan_tree, ScanResult
from analyzer.classifier import ClassificationResult
from gui.scan_view import ScanView
from gui.review_view import ReviewView
from gui.sbom_view import SbomView
from gui.settings_view import SettingsView


# ── Background worker ─────────────────────────────────────────────────────

class ScanWorker(QThread):
    """Runs scan_tree + classify in a background thread."""

    progress = Signal(int, int, str)
    finished = Signal(object, object, object)  # ScanResult, ClassificationResult, list[Component]
    error = Signal(str)

    def __init__(self, source_dir: Path) -> None:
        super().__init__()
        self.source_dir = source_dir

    def run(self) -> None:
        try:
            scan_result = scan_tree(
                self.source_dir,
                progress_callback=lambda i, n, p: self.progress.emit(i, n, str(p)),
            )
            classification = classify(scan_result)
            components = group_into_components(classification, self.source_dir)
            self.finished.emit(scan_result, classification, components)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Page indices ──────────────────────────────────────────────────────────

_PAGE_SETTINGS = 0
_PAGE_SCAN = 1
_PAGE_REVIEW = 2
_PAGE_SBOM = 3


# ── Main window ───────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Izumi – OSS Detection & SBOM")
        self.resize(1100, 700)

        # Application state
        self._source_dir: Optional[Path] = None
        self._scan_result: Optional[ScanResult] = None
        self._classification: Optional[ClassificationResult] = None
        self._components: list[Component] = []
        self._scan_worker: Optional[ScanWorker] = None

        self._build_ui()
        self._build_menu()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Stacked widget for screen navigation
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Create screens
        self._settings_view = SettingsView()
        self._scan_view = ScanView()
        self._review_view = ReviewView()
        self._sbom_view = SbomView()

        self._stack.addWidget(self._settings_view)   # 0
        self._stack.addWidget(self._scan_view)        # 1
        self._stack.addWidget(self._review_view)      # 2
        self._stack.addWidget(self._sbom_view)        # 3

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)

        # Connect signals from screens
        self._settings_view.scan_requested.connect(self._on_scan_requested)
        self._scan_view.review_requested.connect(self._on_review_requested)
        self._scan_view.export_requested.connect(self._on_export_requested)
        self._review_view.back_requested.connect(lambda: self._show_page(_PAGE_SCAN))
        self._review_view.export_requested.connect(self._on_export_requested)
        self._sbom_view.back_requested.connect(lambda: self._show_page(_PAGE_SCAN))

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("ファイル(&F)")
        new_scan = QAction("新規スキャン(&N)", self)
        new_scan.triggered.connect(lambda: self._show_page(_PAGE_SETTINGS))
        file_menu.addAction(new_scan)
        file_menu.addSeparator()
        quit_action = QAction("終了(&Q)", self)
        quit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_action)

        view_menu = menu.addMenu("表示(&V)")
        actions = [
            ("設定", _PAGE_SETTINGS),
            ("スキャン結果", _PAGE_SCAN),
            ("LLM SCAレビュー", _PAGE_REVIEW),
            ("SBOM出力", _PAGE_SBOM),
        ]
        for label, page in actions:
            act = QAction(label, self)
            act.triggered.connect(lambda _=None, p=page: self._show_page(p))
            view_menu.addAction(act)

    # ── Navigation ────────────────────────────────────────────────────────

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ── Scan flow ─────────────────────────────────────────────────────────

    @Slot(object)
    def _on_scan_requested(self, source_dir: Path) -> None:
        self._source_dir = source_dir
        self._review_view.configure_llm(
            ollama_url=self._settings_view.ollama_url,
            local_model=self._settings_view.local_model,
            external_model=self._settings_view.external_model,
            api_key=self._settings_view.api_key,
        )
        self._status_bar.showMessage(f"スキャン中: {source_dir}")
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._progress_bar.setVisible(True)

        self._scan_worker = ScanWorker(source_dir)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    @Slot(int, int, str)
    def _on_scan_progress(self, current: int, total: int, path: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._status_bar.showMessage(f"スキャン中 {current}/{total}: {path}")

    @Slot(object, object, object)
    def _on_scan_finished(
        self,
        scan_result: ScanResult,
        classification: ClassificationResult,
        components: list[Component],
    ) -> None:
        self._scan_result = scan_result
        self._classification = classification
        self._components = components

        self._progress_bar.setVisible(False)
        summary = classification.summary()
        self._status_bar.showMessage(
            f"完了: CONFIRMED={summary['confirmed']}  "
            f"INFERRED={summary['inferred']}  "
            f"UNKNOWN={summary['unknown']}"
        )

        self._scan_view.set_data(classification, components, self._source_dir)
        self._show_page(_PAGE_SCAN)

    @Slot(str)
    def _on_scan_error(self, message: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_bar.showMessage("スキャンエラー")
        QMessageBox.critical(self, "スキャンエラー", message)

    # ── Review flow ───────────────────────────────────────────────────────

    @Slot(list)
    def _on_review_requested(self, selected_paths: list) -> None:
        if self._classification is not None:
            self._review_view.set_data(
                self._classification,
                self._components,
                self._source_dir,
                preselected_paths=selected_paths or None,
            )
        self._show_page(_PAGE_REVIEW)

    # ── Export flow ───────────────────────────────────────────────────────

    @Slot(list)
    def _on_export_requested(self, components: list[Component]) -> None:
        self._sbom_view.set_components(components)
        self._show_page(_PAGE_SBOM)

    # ── Window events ─────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.quit()
            self._scan_worker.wait(2000)
        event.accept()
