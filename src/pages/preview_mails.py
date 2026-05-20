from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPlainTextEdit, QPushButton, QSplitter, QWidget,
)


class PreviewMailsDialog(QDialog):
    """Show a list of imported files and a plain-text preview of the parsed mail."""

    def __init__(self, app_window, parent=None):
        super().__init__(parent)
        self.app = app_window
        self.setWindowTitle("Preview Imported Mails")
        self.setMinimumSize(760, 420)
        # Ensure high-contrast text colors for readability and dark button labels
        self.setStyleSheet("""
            QDialog{background:#F8FAFC;color:#1E2A3A;}
            QListWidget{background:#FFFFFF;color:#1E2A3A;border:1px solid #DCE3EA;}
            QListWidget::item{padding:6px 8px;}
            QListWidget::item:selected{background:#E3F2FD;color:#1E2A3A;}
            QPlainTextEdit{background:#FFFFFF;color:#1E2A3A;border:1px solid #DCE3EA;}
            QDialog QPushButton{
                min-width:80px;min-height:28px;
                background:#FFFFFF; color:#1E2A3A;
                border:1px solid #B0BEC5; border-radius:4px; padding:6px 10px;
            }
            QDialog QPushButton:default{ background:#FFFFFF; color:#1E2A3A; }
            QDialog QPushButton:disabled{ background:#E9EEF3; color:#90A4AE; }
            QDialog QPushButton:hover{ background:#E3F2FD; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hdr = QLabel("Preview imported mail contents — select a file to view its parsed text.")
        hdr.setStyleSheet("font-size:13px;color:#607080;")
        layout.addWidget(hdr)

        splitter = QSplitter(Qt.Horizontal)

        self.list_w = QListWidget()
        self.list_w.setMinimumWidth(240)
        self.list_w.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self.list_w)

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(
            "font-family: Consolas, monospace; font-size:12px; color:#1E2A3A; background:#FFFFFF;"
        )
        rlay.addWidget(self.preview)
        splitter.addWidget(right)

        layout.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        # Ensure this button is not treated as the dialog default (which some styles render with white text)
        try:
            close_btn.setDefault(False)
            close_btn.setAutoDefault(False)
        except Exception:
            pass
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._populate_list()

    def _populate_list(self):
        ip = getattr(self.app, "import_page", None)
        files = []
        if ip:
            files = list(ip._file_rows.keys())
        for p in files:
            item = QListWidgetItem(Path(p).name)
            item.setData(Qt.UserRole, p)
            self.list_w.addItem(item)

        if self.list_w.count():
            self.list_w.setCurrentRow(0)

    def _on_select(self):
        items = self.list_w.selectedItems()
        if not items:
            self.preview.setPlainText("")
            return
        path = items[0].data(Qt.UserRole)
        try:
            from src.services.email_parser import parse_file
            text = parse_file(path)
        except Exception as exc:
            text = f"Error parsing file: {exc}\n\nFile: {path}"
        self.preview.setPlainText(text)
