# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
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

from analyzer.classifier import classify, Classification, ClassificationResult
from analyzer.grouper import group_into_components
from analyzer.models import Component
from analyzer.scanner import scan_tree, ScanResult
from gui.scan_view import ScanView
from gui.review_view import ReviewView
from gui.sbom_view import SbomView
from gui.settings_view import SettingsView
from i18n import t


# ── Background workers ────────────────────────────────────────────────────

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


class LicenseAnalysisWorker(QThread):
    """Sends unidentified LICENSE files to a LLM and emits per-file results."""

    progress = Signal(int, int)        # current, total
    result   = Signal(object, str)     # license_file Path, SPDX ID
    finished = Signal()
    error    = Signal(str)

    def __init__(
        self,
        license_files: list[Path],
        model: str,
        api_base: str = "",
        api_key: str = "",
    ) -> None:
        super().__init__()
        self.license_files = license_files
        self.model = model
        self.api_base = api_base
        self.api_key = api_key

    def run(self) -> None:
        from llm.license_analyzer import analyze_license_text
        total = len(self.license_files)
        for i, lf in enumerate(self.license_files, 1):
            self.progress.emit(i, total)
            try:
                text = lf.read_text(errors='replace')
                spdx_id = analyze_license_text(text, self.model, self.api_base, self.api_key)
            except Exception as exc:
                self.error.emit(str(exc))
                spdx_id = "NOASSERTION"
            self.result.emit(lf, spdx_id)
        self.finished.emit()


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
        self.setWindowTitle(t("window_title"))
        self.resize(1100, 700)

        # Application state
        self._source_dir: Optional[Path] = None
        self._scan_result: Optional[ScanResult] = None
        self._classification: Optional[ClassificationResult] = None
        self._components: list[Component] = []
        self._scan_worker: Optional[ScanWorker] = None
        self._license_worker: Optional[LicenseAnalysisWorker] = None
        self._license_error_shown: bool = False
        # User-assigned versions keyed by component directory; persisted across rebuilds
        self._component_versions: dict[Path, str] = {}
        # license_file → components that reference it (built after scan)
        self._license_file_to_comps: dict[Path, list[Component]] = {}

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
        self._settings_view.settings_changed.connect(self._on_settings_changed)
        self._scan_view.review_requested.connect(self._on_review_requested)
        self._scan_view.export_requested.connect(self._on_export_requested)
        self._scan_view.classification_changed.connect(self._on_classification_changed)
        self._review_view.back_requested.connect(lambda: self._show_page(_PAGE_SCAN))
        self._review_view.export_requested.connect(self._on_export_requested)
        self._sbom_view.back_requested.connect(lambda: self._show_page(_PAGE_SCAN))

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu(t("file_menu"))
        new_scan = QAction(t("new_scan_action"), self)
        new_scan.triggered.connect(lambda: self._show_page(_PAGE_SETTINGS))
        file_menu.addAction(new_scan)
        file_menu.addSeparator()
        quit_action = QAction(t("quit_action"), self)
        quit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_action)

        view_menu = menu.addMenu(t("view_menu"))
        actions = [
            (t("menu_settings"), _PAGE_SETTINGS),
            (t("menu_scan"),     _PAGE_SCAN),
            (t("menu_review"),   _PAGE_REVIEW),
            (t("menu_sbom"),     _PAGE_SBOM),
        ]
        for label, page in actions:
            act = QAction(label, self)
            act.triggered.connect(lambda _=None, p=page: self._show_page(p))
            view_menu.addAction(act)

    # ── Navigation ────────────────────────────────────────────────────────

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ── Scan flow ─────────────────────────────────────────────────────────

    def _on_settings_changed(self) -> None:
        self._review_view.configure_llm(
            ollama_url=self._settings_view.ollama_url,
            local_model=self._settings_view.local_model,
            external_model=self._settings_view.external_model,
            api_key=self._settings_view.api_key,
        )

    @Slot(object)
    def _on_scan_requested(self, source_dir: Path) -> None:
        self._source_dir = source_dir
        self._status_bar.showMessage(t("scanning_status", source_dir=source_dir))
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
        self._status_bar.showMessage(t("scan_progress_status", current=current, total=total, path=path))

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
            t("scan_complete_status",
              confirmed=summary['confirmed'],
              inferred=summary['inferred'],
              unknown=summary['unknown'])
        )

        self._scan_view.set_data(classification, components, self._source_dir)
        self._show_page(_PAGE_SCAN)

        # Start LLM license analysis if requested
        self._license_file_to_comps = self._build_license_file_map(classification, components)
        if self._license_file_to_comps:
            sv = self._settings_view
            if sv.license_analysis_external and sv.external_model:
                self._start_license_analysis(sv.external_model, "", sv.api_key)
            elif sv.license_analysis_local and sv.local_model:
                self._start_license_analysis(sv.local_model, sv.ollama_url, "")

    def _build_license_file_map(
        self,
        classification: ClassificationResult,
        components: list[Component],
    ) -> dict[Path, list[Component]]:
        """Map unidentified LICENSE files to the components that reference them."""
        file_to_comp: dict[Path, Component] = {
            fp: comp for comp in components for fp in comp.files
        }
        lic_to_comps: dict[Path, set[Component]] = {}
        for cf in classification.all_files:
            lf = cf.file_info.license_file
            if lf is None:
                continue
            comp = file_to_comp.get(cf.file_info.path)
            if comp is None or comp.license_expression not in (None, "NOASSERTION"):
                continue
            lic_to_comps.setdefault(lf, set()).add(comp)
        return {lf: list(comps) for lf, comps in lic_to_comps.items()}

    def _start_license_analysis(self, model: str, api_base: str, api_key: str) -> None:
        license_files = list(self._license_file_to_comps.keys())
        self._progress_bar.setRange(0, len(license_files))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        self._license_error_shown = False
        self._license_worker = LicenseAnalysisWorker(license_files, model, api_base, api_key)
        self._license_worker.progress.connect(self._on_license_progress)
        self._license_worker.result.connect(self._on_license_result)
        self._license_worker.finished.connect(self._on_license_finished)
        self._license_worker.error.connect(self._on_license_error)
        self._license_worker.start()

    @Slot(int, int)
    def _on_license_progress(self, current: int, total: int) -> None:
        self._progress_bar.setValue(current)
        self._status_bar.showMessage(
            t("license_analysis_status", current=current, total=total)
        )

    @Slot(object, str)
    def _on_license_result(self, license_file: Path, spdx_id: str) -> None:
        if spdx_id == "NOASSERTION":
            return
        comps = self._license_file_to_comps.get(license_file, [])
        for comp in comps:
            if comp.license_expression in (None, "NOASSERTION"):
                comp.license_expression = spdx_id
        if comps and self._classification is not None:
            self._scan_view.set_data(self._classification, self._components, self._source_dir)

    @Slot()
    def _on_license_finished(self) -> None:
        self._progress_bar.setVisible(False)
        identified = sum(
            1 for comp in self._components
            if comp.license_expression not in (None, "NOASSERTION")
        )
        self._status_bar.showMessage(t("license_analysis_complete", count=identified))

    @Slot(str)
    def _on_license_error(self, message: str) -> None:
        self._status_bar.showMessage(t("license_analysis_error", message=message))
        if not self._license_error_shown:
            self._license_error_shown = True
            QMessageBox.warning(self, t("license_analysis_error_title"), message)

    @Slot(str)
    def _on_scan_error(self, message: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_bar.showMessage(t("scan_error_status"))
        QMessageBox.critical(self, t("scan_error_title"), message)

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

    # ── Classification confirmation flow ──────────────────────────────────

    @Slot(list)
    def _on_classification_changed(self, changes: list) -> None:
        """User changed classification for one or more files."""
        if self._classification is None:
            return

        _list_for = {
            Classification.CONFIRMED: self._classification.confirmed,
            Classification.INFERRED:  self._classification.inferred,
            Classification.UNKNOWN:   self._classification.unknown,
        }
        path_to_cf = {cf.file_info.path: cf for cf in self._classification.all_files}

        for file_path, classification_value, license_id, version in changes:
            target_cf = path_to_cf.get(file_path)
            if target_cf is None:
                continue
            new_class = Classification(classification_value)
            _list_for[target_cf.classification].remove(target_cf)
            target_cf.classification = new_class
            target_cf.reason = f"User override: {license_id}" if license_id else "User override"
            if license_id:
                target_cf.file_info.copyright_info.spdx_license_id = license_id
            _list_for[new_class].append(target_cf)

            # Store version keyed by the file's component directory (survives rebuild)
            if version is not None:
                key = next(
                    (c.directory for c in self._components if file_path in c.files),
                    file_path.parent,
                )
                self._component_versions[key] = version

        # Rebuild components and re-apply user-assigned versions
        self._components = group_into_components(self._classification, self._source_dir)
        for comp in self._components:
            if comp.directory in self._component_versions:
                comp.version = self._component_versions[comp.directory] or None
        self._scan_view.set_data(self._classification, self._components, self._source_dir)

    # ── Export flow ───────────────────────────────────────────────────────

    @Slot(list)
    def _on_export_requested(self, components: list[Component]) -> None:
        self._sbom_view.set_components(components)
        self._show_page(_PAGE_SBOM)

    # ── Window events ─────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        for worker in (self._scan_worker, self._license_worker):
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(2000)
        event.accept()
