"""Settings view – source directory selection and LLM configuration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsView(QWidget):
    """Screen 1: project configuration and scan launch."""

    scan_requested  = Signal(object)  # Path
    settings_changed = Signal()       # emitted whenever any LLM setting changes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        title = QLabel("Izumi – OSS 検出 & SBOM 支援")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        # ── Source directory ─────────────────────────────────────────────
        src_group = QGroupBox("スキャン対象")
        src_layout = QHBoxLayout(src_group)

        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText("スキャンするソースツリーのパス")
        src_layout.addWidget(self._src_edit)

        browse_btn = QPushButton("参照…")
        browse_btn.clicked.connect(self._browse_source)
        src_layout.addWidget(browse_btn)

        root.addWidget(src_group)

        # ── Local LLM ────────────────────────────────────────────────────
        local_group = QGroupBox("ローカルLLM (Ollama)")
        local_form = QFormLayout(local_group)

        self._ollama_url_edit = QLineEdit("http://localhost:11434")
        local_form.addRow("エンドポイント:", self._ollama_url_edit)

        self._local_model_edit = QLineEdit("ollama/codellama")
        local_form.addRow("モデル:", self._local_model_edit)

        root.addWidget(local_group)

        # ── External LLM ─────────────────────────────────────────────────
        ext_group = QGroupBox("外部LLM")
        ext_form = QFormLayout(ext_group)

        self._ext_model_edit = QLineEdit("claude-sonnet-4-20250514")
        ext_form.addRow("モデル:", self._ext_model_edit)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setPlaceholderText("APIキー（オプション・環境変数でも可）")
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ext_form.addRow("APIキー:", self._api_key_edit)

        root.addWidget(ext_group)

        # Emit settings_changed whenever any LLM field is edited
        for field in (
            self._ollama_url_edit,
            self._local_model_edit,
            self._ext_model_edit,
            self._api_key_edit,
        ):
            field.textChanged.connect(lambda _: self.settings_changed.emit())

        root.addStretch()

        # ── Scan button ───────────────────────────────────────────────────
        scan_btn = QPushButton("スキャン開始")
        scan_btn.setFixedHeight(40)
        scan_btn.clicked.connect(self._on_scan_clicked)
        root.addWidget(scan_btn)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "スキャン対象ディレクトリを選択"
        )
        if directory:
            self._src_edit.setText(directory)

    def _on_scan_clicked(self) -> None:
        path = Path(self._src_edit.text().strip())
        if not path.is_dir():
            QMessageBox.warning(
                self,
                "パスが無効",
                f"'{path}' はディレクトリではありません。",
            )
            return
        self.scan_requested.emit(path)

    # ── Accessors ─────────────────────────────────────────────────────────

    @property
    def source_dir(self) -> Path | None:
        text = self._src_edit.text().strip()
        return Path(text) if text else None

    @property
    def ollama_url(self) -> str:
        return self._ollama_url_edit.text().strip()

    @property
    def local_model(self) -> str:
        return self._local_model_edit.text().strip()

    @property
    def external_model(self) -> str:
        return self._ext_model_edit.text().strip()

    @property
    def api_key(self) -> str:
        return self._api_key_edit.text().strip()
