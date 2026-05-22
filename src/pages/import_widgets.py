"""
Reusable visual widgets for the import page: DropZone, ModeBadge, SubEntryRow, FileRow.
"""
import struct
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)

# ---------------------------------------------------------------------------
# Outlook drag-drop helper
# ---------------------------------------------------------------------------
# FILEDESCRIPTORW layout (Windows SDK):
#   dwFlags(4) clsid(16) sizel(8) pointl(8) dwFileAttributes(4)
#   ftCreationTime(8) ftLastAccessTime(8) ftLastWriteTime(8)
#   nFileSizeHigh(4) nFileSizeLow(4) cFileName(MAX_PATH*2=520)
#   Total = 592 bytes
_FD_SIZE = 592
_FD_NAME_OFFSET = 72   # 4+16+8+8+4+8+8+8+4+4


def _extract_outlook_drop(mime_data) -> list[str]:
    """
    Extract virtual .msg files from an Outlook drag-and-drop operation.
    Saves each file to a temp directory and returns a list of real file paths.
    Qt can only retrieve the first item's contents via QMimeData; for each
    additional item the user will need to drop it separately.
    """
    try:
        raw = bytes(mime_data.data("FileGroupDescriptorW"))
    except Exception:
        return []

    if len(raw) < 4:
        return []

    num_items = struct.unpack_from("<I", raw, 0)[0]
    if num_items == 0:
        return []

    # Parse filenames from the descriptor array
    filenames: list[str] = []
    for i in range(num_items):
        base = 4 + i * _FD_SIZE
        try:
            raw_name = raw[base + _FD_NAME_OFFSET: base + _FD_NAME_OFFSET + 520]
            name = raw_name.decode("utf-16-le").rstrip("\x00")
        except Exception:
            name = ""
        if not name:
            name = f"outlook_email_{i + 1}.msg"
        elif not name.lower().endswith(".msg"):
            name += ".msg"
        filenames.append(name)

    # Qt's QMimeData wraps IDataObject but only exposes lindex=0.
    # Retrieve the first (and typically only) item's content.
    try:
        content = bytes(mime_data.data("FileContents"))
    except Exception:
        return []

    if not content:
        return []

    tmp = Path(tempfile.mkdtemp(prefix="nagarkot_drop_"))
    saved: list[str] = []

    p = tmp / filenames[0]
    try:
        p.write_bytes(content)
        saved.append(str(p))
    except Exception:
        pass

    return saved


# ---------------------------------------------------------------------------
# Drop zone
# ---------------------------------------------------------------------------
class DropZone(QLabel):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Force a native HWND so we can register a COM IDropTarget on Windows
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(130)
        self.setText(
            "Drop PDF / MSG / Excel / Word files here, or drag emails directly from Outlook\n\n"
            "or click  Browse Files  below"
        )
        self._idle_style()
        # COM IDropTarget is registered in showEvent (after Qt's own
        # RegisterDragDrop call during show), not here in __init__.
        self._outlook_target = None

    def _idle_style(self):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #B0BEC5;
                border-radius: 10px;
                background: #F8FAFC;
                color: #90A4AE;
                font-size: 14px;
            }
        """)

    def _active_style(self):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #1976D2;
                border-radius: 10px;
                background: #E3F2FD;
                color: #1565C0;
                font-size: 14px;
            }
        """)

    def showEvent(self, event):
        super().showEvent(event)
        # Qt calls RegisterDragDrop during its own show processing. We must
        # register our COM target AFTER that, so use a zero-delay timer to
        # defer until Qt's show sequence is fully complete.
        if sys.platform == "win32":
            QTimer.singleShot(0, self._register_com_target)

    def _register_com_target(self):
        if sys.platform != "win32":
            return
        try:
            from src.services.outlook_drop_target import OutlookDropTarget
            if self._outlook_target:
                self._outlook_target.revoke()
            self._outlook_target = OutlookDropTarget(self)
        except Exception as exc:
            print(f"[OutlookDrop] registration error: {exc}", flush=True)
            import traceback
            traceback.print_exc()

    def dragEnterEvent(self, event: QDragEnterEvent):
        md = event.mimeData()
        if md.hasUrls() or md.hasFormat("FileGroupDescriptorW"):
            event.acceptProposedAction()
            self._active_style()

    def dragLeaveEvent(self, event):
        self._idle_style()

    def dropEvent(self, event: QDropEvent):
        self._idle_style()
        md = event.mimeData()
        if md.hasFormat("FileGroupDescriptorW"):
            saved = _extract_outlook_drop(md)
            if saved:
                self.files_dropped.emit(saved)
        elif md.hasUrls():
            paths = [u.toLocalFile() for u in md.urls()]
            valid = [p for p in paths if p.lower().endswith(
                (".pdf", ".msg", ".xlsx", ".xls", ".xlsm", ".docx", ".doc")
            )]
            if valid:
                self.files_dropped.emit(valid)


# ---------------------------------------------------------------------------
# Mode badge — read-only pill showing detected quote type (Air / FCL / LCL)
# ---------------------------------------------------------------------------
class ModeBadge(QPushButton):
    _COLORS = {
        "air":   ("#1565C0", "#E3F2FD"),
        "fcl":   ("#00796B", "#E0F2F1"),
        "lcl":   ("#2E7D32", "#E8F5E9"),
        "mixed": ("#455A64", "#ECEFF1"),
        "":      ("#607080", "#F5F7FA"),
    }
    _LABELS = {"air": "Air", "fcl": "FCL", "lcl": "LCL", "mixed": "Mixed"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = ""
        self.setFlat(True)
        self.setFixedHeight(22)
        self.setVisible(False)
        self.setEnabled(False)

    def set_mode(self, mode: str):
        self._mode = mode.lower().strip()
        self.setText(self._LABELS.get(self._mode, self._mode.upper()))
        fg, bg = self._COLORS.get(self._mode, self._COLORS[""])
        self.setStyleSheet(
            f"QPushButton{{background:{bg};color:{fg};"
            f"border:1px solid {fg};border-radius:3px;"
            f"padding:1px 10px;font-size:11px;font-weight:700;}}"
        )
        self.setVisible(bool(self._mode))


# ---------------------------------------------------------------------------
# Sub-entry row — indented, shows one VendorData within a multi-result file
# ---------------------------------------------------------------------------
class SubEntryRow(QFrame):
    remove_requested = Signal(str)  # uid

    _MODE_COLORS = {
        "air": ("#1565C0", "#E3F2FD"),
        "fcl": ("#00796B", "#E0F2F1"),
        "lcl": ("#2E7D32", "#E8F5E9"),
    }

    def __init__(self, uid: str, label: str, mode: str, parent=None):
        super().__init__(parent)
        self.uid = uid
        self._build(label, mode)

    def _build(self, label: str, mode: str):
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(
            "background:#FAFBFC; border:none;"
            "border-left:3px solid #DCE3EA; margin-left:12px;"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 3, 10, 3)
        lay.setSpacing(8)

        fg, bg = self._MODE_COLORS.get(mode, ("#607080", "#F5F7FA"))
        pill = QLabel(mode.upper() if mode else "AIR")
        pill.setFixedWidth(36)
        pill.setAlignment(Qt.AlignCenter)
        pill.setStyleSheet(
            f"font-size:10px;font-weight:700;color:{fg};background:{bg};"
            f"border-radius:3px;padding:1px 0;border:1px solid {fg};"
        )
        lay.addWidget(pill)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet("font-size:12px;color:#607080;border:none;")
        lay.addWidget(name_lbl, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(18, 18)
        del_btn.setToolTip("Remove this entry")
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#B0BEC5;border:none;font-size:11px;}"
            "QPushButton:hover{color:#E53935;}"
        )
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self.uid))
        lay.addWidget(del_btn)


# ---------------------------------------------------------------------------
# Single file row
# ---------------------------------------------------------------------------
class FileRow(QFrame):
    remove_requested = Signal(str)  # file_path

    STATUS_STYLE = {
        "pending":    ("Pending",       "#607080", "#F5F7FA"),
        "processing": ("Extracting...", "#F57C00", "#FFF8E1"),
        "done":       ("Done",          "#27AE60", "#E8F5E9"),
        "error":      ("Error",         "#E53935", "#FFEBEE"),
    }

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._build(file_path)

    def _build(self, path: str):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("background:#FFFFFF; border-radius:6px; border:1px solid #DCE3EA;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        self.name_label = QLabel(Path(path).name)
        self.name_label.setToolTip(path)
        self.name_label.setStyleSheet("font-size:13px; color:#1E2A3A; border:none;")
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.name_label)

        self.vendor_label = QLabel("")
        self.vendor_label.setStyleSheet(
            "font-size:12px; color:#1976D2; border:none; font-style:italic;"
        )
        lay.addWidget(self.vendor_label)

        self.mode_badge = ModeBadge()
        lay.addWidget(self.mode_badge)

        self.status_badge = QLabel("Pending")
        self.status_badge.setFixedWidth(100)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setStyleSheet(
            "font-size:11px; color:#607080; background:#F5F7FA; "
            "border-radius:4px; padding:2px 6px; border:none;"
        )
        lay.addWidget(self.status_badge)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#90A4AE;border:none;font-size:13px;}"
            "QPushButton:hover{color:#E53935;}"
        )
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self.file_path))
        lay.addWidget(del_btn)

    def set_status(self, status: str, vendor_name: str = ""):
        text, color, bg = self.STATUS_STYLE.get(status, ("—", "#607080", "#F5F7FA"))
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"font-size:11px; color:{color}; background:{bg}; "
            "border-radius:4px; padding:2px 6px; border:none;"
        )
        if vendor_name:
            self.vendor_label.setText(vendor_name)

    def set_mode(self, mode: str):
        self.mode_badge.set_mode(mode)

    def set_error_tip(self, msg: str):
        self.status_badge.setToolTip(msg)
