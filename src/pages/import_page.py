import re
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QProgressBar, QMessageBox, QLineEdit,
    QDialog, QDoubleSpinBox, QComboBox,
)

from src.constants import QUOTE_TYPES
from src.models.vendor_data import VendorData
from src.pages.import_widgets import DropZone, FileRow, SubEntryRow
from src.pages.import_dialogs import _InquiryMismatchDialog, _QuoteModeMismatchDialog

_INQUIRY_RE = re.compile(r'^E\d{6}$', re.IGNORECASE)
_INQUIRY_VALID_STYLE = (
    "QLineEdit{border:1px solid #43A047;border-radius:5px;"
    "padding:0 10px;font-size:13px;color:#1E2A3A;background:#F1F8E9;}"
)
_INQUIRY_INVALID_STYLE = (
    "QLineEdit{border:1px solid #E53935;border-radius:5px;"
    "padding:0 10px;font-size:13px;color:#1E2A3A;background:#FFEBEE;}"
)


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------
class ExtractionWorker(QThread):
    file_started = Signal(str)        # file_path
    file_done    = Signal(str, list)  # file_path, list[result_dict]
    file_error   = Signal(str, str)   # file_path, error_message
    all_done     = Signal()

    def __init__(self, file_paths: list[str], ai_service, selected_mode: str, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.ai_service = ai_service
        self.selected_mode = selected_mode

    def run(self):
        from src.services.email_parser import parse_file
        for path in self.file_paths:
            self.file_started.emit(path)
            try:
                text = parse_file(path)
                results = self.ai_service.extract_charges(
                    text,
                    selected_mode=self.selected_mode,
                )
                self.file_done.emit(path, results)
            except Exception as exc:
                self.file_error.emit(path, str(exc))
        self.all_done.emit()


# ---------------------------------------------------------------------------
# Import Page
# ---------------------------------------------------------------------------
class ImportPage(QWidget):
    def __init__(self, app_window, parent=None):
        super().__init__(parent)
        self.app = app_window
        self._file_rows: dict[str, FileRow] = {}
        self._sub_rows:  dict[str, list[SubEntryRow]] = {}
        self._worker: ExtractionWorker | None = None
        self._done_count = 0
        self._extracted_paths: set[str] = set()
        self._mode_values = [mode.upper() for mode in QUOTE_TYPES]
        self._current_session: dict | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 20)
        root.setSpacing(16)

        title = QLabel("Import Vendor Quote Files")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#1E2A3A;")
        root.addWidget(title)

        sub = QLabel(
            "Upload one PDF or MSG file per vendor. "
            "Charges will be auto-extracted when you proceed."
        )
        sub.setStyleSheet("font-size:13px; color:#607080;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # Inquiry / mode / weight form
        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        inq_lbl = QLabel("Inquiry No.:")
        inq_lbl.setStyleSheet("font-size:13px; font-weight:600; color:#1E2A3A;")
        inq_lbl.setFixedWidth(100)
        form.addWidget(inq_lbl, 0, 0)

        self._inquiry_input = QLineEdit()
        self._inquiry_input.setPlaceholderText("e.g. E250950")
        self._inquiry_input.setFixedWidth(220)
        self._inquiry_input.setFixedHeight(34)
        self._inquiry_input.setMaxLength(7)
        self._inquiry_input.setStyleSheet(_INQUIRY_INVALID_STYLE)
        self._inquiry_input.textChanged.connect(self._on_inquiry_changed)
        form.addWidget(self._inquiry_input, 0, 1)

        self._inquiry_hint = QLabel("Required")
        self._inquiry_hint.setStyleSheet("font-size:11px;color:#E53935;margin-left:6px;")
        self._inquiry_hint.setMinimumWidth(130)
        form.addWidget(self._inquiry_hint, 0, 2)

        mode_lbl = QLabel("Quote Mode:")
        mode_lbl.setStyleSheet("font-size:13px; font-weight:600; color:#1E2A3A;")
        form.addWidget(mode_lbl, 0, 3)

        self._mode_combo = QComboBox()
        self._mode_combo.setFixedWidth(150)
        self._mode_combo.setFixedHeight(34)
        self._mode_combo.setStyleSheet(
            "QComboBox{border:1px solid #E53935;border-radius:5px;padding:0 10px;"
            "font-size:13px;color:#1E2A3A;background:#FFEBEE;}"
            "QComboBox:focus{border:1px solid #1976D2;}"
        )
        self._mode_combo.addItem("Select mode...", "")
        for mode in self._mode_values:
            self._mode_combo.addItem(mode, mode.lower())
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addWidget(self._mode_combo, 0, 4)

        self._mode_hint = QLabel("Required")
        self._mode_hint.setStyleSheet("font-size:11px;color:#E53935;margin-left:6px;")
        self._mode_hint.setMinimumWidth(85)
        form.addWidget(self._mode_hint, 0, 5)

        wt_lbl = QLabel("Chargeable Weight:")
        wt_lbl.setStyleSheet("font-size:13px; font-weight:600; color:#1E2A3A;")
        form.addWidget(wt_lbl, 1, 0)

        self._weight_input = QDoubleSpinBox()
        self._weight_input.setRange(0, 99999)
        self._weight_input.setDecimals(1)
        self._weight_input.setSuffix(" KG")
        self._weight_input.setSpecialValueText("— (not set)")
        self._weight_input.setValue(0)
        self._weight_input.setFixedWidth(140)
        self._weight_input.setFixedHeight(34)
        self._weight_input.setStyleSheet(
            "QDoubleSpinBox{border:1px solid #B0BEC5;border-radius:5px;"
            "padding:0 8px;font-size:13px;color:#1E2A3A;background:#FFFFFF;}"
            "QDoubleSpinBox:focus{border:1px solid #1976D2;}"
        )
        self._weight_input.valueChanged.connect(self._on_weight_changed)
        form.addWidget(self._weight_input, 1, 1)

        wt_hint = QLabel("(air freight — marks other weight slabs optional)")
        wt_hint.setStyleSheet("font-size:11px;color:#90A4AE;margin-left:4px;")
        wt_hint.setWordWrap(True)
        form.addWidget(wt_hint, 1, 2, 1, 4)
        self._weight_hint = wt_hint

        form.setColumnStretch(2, 1)
        form.setColumnStretch(5, 1)
        root.addLayout(form)

        # Session banner — shown when a saved session matches inquiry + mode
        self._session_banner = QFrame()
        self._session_banner.setVisible(False)
        self._session_banner.setStyleSheet(
            "QFrame{background:#E3F2FD;border:1px solid #90CAF9;"
            "border-radius:6px;padding:2px;}"
        )
        sb_lay = QHBoxLayout(self._session_banner)
        sb_lay.setContentsMargins(12, 6, 12, 6)
        sb_lay.setSpacing(10)
        self._session_info_lbl = QLabel("")
        self._session_info_lbl.setStyleSheet(
            "font-size:12px;color:#1565C0;font-weight:600;"
        )
        sb_lay.addWidget(self._session_info_lbl)
        sb_lay.addStretch()
        _load_btn = QPushButton("Load Session")
        _load_btn.setFixedHeight(28)
        _load_btn.setStyleSheet(
            "QPushButton{background:#1976D2;color:white;border:none;"
            "border-radius:4px;font-size:12px;font-weight:600;padding:0 12px;}"
            "QPushButton:hover{background:#1565C0;}"
        )
        _load_btn.clicked.connect(self._load_session)
        sb_lay.addWidget(_load_btn)
        _fresh_btn = QPushButton("Start Fresh")
        _fresh_btn.setFixedHeight(28)
        _fresh_btn.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#1E2A3A;"
            "border:1px solid #90A4AE;border-radius:4px;"
            "font-size:12px;padding:0 12px;}"
            "QPushButton:hover{background:#F0F4F8;}"
        )
        _fresh_btn.clicked.connect(self._dismiss_session)
        sb_lay.addWidget(_fresh_btn)
        root.addWidget(self._session_banner)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._add_files)
        root.addWidget(self.drop_zone)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Browse Files...")
        browse_btn.setFixedHeight(36)
        browse_btn.setStyleSheet(self._sec_btn_style())
        browse_btn.clicked.connect(self._browse)
        btn_row.addWidget(browse_btn)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setFixedHeight(36)
        self.clear_btn.setStyleSheet(self._sec_btn_style())
        self.clear_btn.clicked.connect(self._clear_all_files)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()

        self.load_sessions_btn = QPushButton("Load Session...")
        self.load_sessions_btn.setFixedHeight(36)
        self.load_sessions_btn.setStyleSheet(self._sec_btn_style())
        self.load_sessions_btn.setToolTip("Open a previously saved inquiry session")
        self.load_sessions_btn.clicked.connect(self._show_session_picker)
        btn_row.addWidget(self.load_sessions_btn)

        self.save_session_btn = QPushButton("Save Session")
        self.save_session_btn.setFixedHeight(36)
        self.save_session_btn.setEnabled(False)
        self.save_session_btn.setStyleSheet(self._sec_btn_style())
        self.save_session_btn.setToolTip("Save current inquiry state to disk")
        self.save_session_btn.clicked.connect(self._save_session_manual)
        btn_row.addWidget(self.save_session_btn)

        root.addLayout(btn_row)

        self.key_warn = QLabel(
            "Note: AI extraction is not configured. "
            "Charges will need to be entered manually on the mapping page."
        )
        self.key_warn.setStyleSheet(
            "background:#FFF8E1; color:#E65100; border:1px solid #FFE082; "
            "border-radius:6px; padding:8px 12px; font-size:12px;"
        )
        self.key_warn.setWordWrap(True)
        self.key_warn.setVisible(self.app.gemini_service is None)
        root.addWidget(self.key_warn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar{background:#E0E0E0;border-radius:3px;border:none;}"
            "QProgressBar::chunk{background:#1976D2;border-radius:3px;}"
        )
        root.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size:12px; color:#607080;")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        list_label = QLabel("Files")
        list_label.setStyleSheet("font-size:13px; font-weight:600; color:#1E2A3A;")
        root.addWidget(list_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none; background:transparent;")
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background:transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(4)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_container)
        root.addWidget(scroll, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#DCE3EA;")
        root.addWidget(sep)

        nav = QHBoxLayout()
        nav.addStretch()
        self.proceed_btn = QPushButton("Proceed to Map Vendors  →")
        self.proceed_btn.setFixedHeight(38)
        self.proceed_btn.setEnabled(False)
        self.proceed_btn.setStyleSheet(self._pri_btn_style())
        self.proceed_btn.clicked.connect(self._proceed)
        nav.addWidget(self.proceed_btn)
        root.addLayout(nav)

        # Lazy import of job utils when needed
        try:
            from src.services import job_utils  # noqa: F401
        except Exception:
            pass
        self._restore_initial_state()
        

    # ------------------------------------------------------------------
    def _on_weight_changed(self, value: float):
        self.app.chargeable_weight = value

    def _on_mode_changed(self, index: int):
        prev_mode = getattr(self.app, "selected_quote_mode", "")
        mode = (self._mode_combo.currentData() or "").strip().lower()
        self.app.selected_quote_mode = mode
        if mode:
            self._mode_combo.setStyleSheet(
                "QComboBox{border:1px solid #43A047;border-radius:5px;padding:0 10px;"
                "font-size:13px;color:#1E2A3A;background:#F1F8E9;}"
                "QComboBox:focus{border:1px solid #1976D2;}"
            )
            self._mode_hint.setText(mode.upper())
            self._mode_hint.setStyleSheet("font-size:11px;color:#43A047;margin-left:6px;")
        else:
            self._mode_combo.setStyleSheet(
                "QComboBox{border:1px solid #E53935;border-radius:5px;padding:0 10px;"
                "font-size:13px;color:#1E2A3A;background:#FFEBEE;}"
                "QComboBox:focus{border:1px solid #1976D2;}"
            )
            self._mode_hint.setText("Required")
            self._mode_hint.setStyleSheet("font-size:11px;color:#E53935;margin-left:6px;")
        if prev_mode and mode and prev_mode != mode:
            self._invalidate_extractions_for_mode_change()
        self._sync_pending_row_modes()
        self._update_weight_state()
        self._refresh_buttons()
        self._check_session()

    def _on_inquiry_changed(self, text: str):
        text = text.strip()
        if not text:
            self._inquiry_input.setStyleSheet(_INQUIRY_INVALID_STYLE)
            self._inquiry_hint.setText("Required")
            self._inquiry_hint.setStyleSheet("font-size:11px;color:#E53935;margin-left:6px;")
        elif _INQUIRY_RE.match(text):
            self._inquiry_input.setStyleSheet(_INQUIRY_VALID_STYLE)
            self._inquiry_hint.setText("Valid")
            self._inquiry_hint.setStyleSheet("font-size:11px;color:#43A047;margin-left:6px;")
        else:
            self._inquiry_input.setStyleSheet(_INQUIRY_INVALID_STYLE)
            self._inquiry_hint.setText("Format: E + 6 digits")
            self._inquiry_hint.setStyleSheet("font-size:11px;color:#E53935;margin-left:6px;")
        self.app.inquiry_number = self._get_inquiry_number()
        self._refresh_buttons()
        self._check_session()

    def _get_inquiry_number(self) -> str:
        """Return the validated inquiry number (uppercased), or '' if invalid."""
        text = self._inquiry_input.text().strip().upper()
        return text if _INQUIRY_RE.match(text) else ""

    def _get_selected_mode(self) -> str:
        return str(self._mode_combo.currentData() or "").strip().lower()

    def _restore_initial_state(self):
        if self.app.selected_quote_mode:
            idx = self._mode_combo.findData(self.app.selected_quote_mode)
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
        else:
            self._on_mode_changed(self._mode_combo.currentIndex())
        self._weight_input.setValue(getattr(self.app, "chargeable_weight", 0.0))
        self._update_weight_state()
        self.refresh_service_state()

    def refresh_service_state(self):
        self.key_warn.setVisible(self.app.gemini_service is None)

    def _update_weight_state(self):
        is_air = self._get_selected_mode() == "air"
        self._weight_input.setEnabled(is_air)
        self._weight_hint.setEnabled(is_air)
        if is_air:
            self._weight_input.setToolTip("Used to auto-mark non-matching air slabs as optional.")
            self._weight_hint.setText("(air freight — marks other weight slabs optional)")
            return

        if self._weight_input.value() != 0:
            self._weight_input.blockSignals(True)
            self._weight_input.setValue(0)
            self._weight_input.blockSignals(False)
            self.app.chargeable_weight = 0.0
        self._weight_input.setToolTip("Chargeable weight is only used for AIR imports.")
        self._weight_hint.setText("(used only when quote mode is AIR)")

    def _invalidate_extractions_for_mode_change(self):
        if not self._extracted_paths:
            return
        for path in list(self._extracted_paths):
            stale = [k for k, vd in self.app.vendors.items() if vd.source_file == path]
            for key in stale:
                del self.app.vendors[key]
            self._clear_sub_rows(path)
            row = self._file_rows.get(path)
            if row:
                row.vendor_label.setText("")
                row.set_mode("")
                row.set_status("pending")
        self._extracted_paths.clear()

    def _sync_pending_row_modes(self):
        mode = self._get_selected_mode()
        for path, row in self._file_rows.items():
            if path in self._extracted_paths:
                continue
            row.set_mode(mode)

    # ------------------------------------------------------------------
    def _browse(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Quote Files", "",
            "Quote Files (*.pdf *.msg);;PDF Files (*.pdf);;MSG Files (*.msg)"
        )
        if paths:
            self._add_files(paths)

    def _add_files(self, paths: list[str]):
        selected_mode = self._get_selected_mode()
        for path in paths:
            if path not in self._file_rows:
                row = FileRow(path)
                row.remove_requested.connect(self._remove_file)
                if selected_mode:
                    row.set_mode(selected_mode)
                self.list_layout.insertWidget(self.list_layout.count() - 1, row)
                self._file_rows[path] = row
        self._refresh_buttons()

    def _remove_file(self, path: str):
        self._clear_sub_rows(path)
        row = self._file_rows.pop(path, None)
        if row:
            row.setParent(None)
            row.deleteLater()
        to_remove = [k for k, vd in self.app.vendors.items() if vd.source_file == path]
        for k in to_remove:
            del self.app.vendors[k]
        self._extracted_paths.discard(path)
        self._refresh_buttons()

    def _clear_all_files(self):
        """Remove all selected files from the import list (with confirmation)."""
        if not self._file_rows:
            return
        # Prevent clearing while extraction is active
        if self._worker and getattr(self._worker, "isRunning", lambda: False)():
            QMessageBox.warning(self, "Cannot Clear", "Extraction is in progress. Please wait until it finishes.")
            return

        # Styled confirmation dialog with high-contrast text
        msg = QMessageBox(self)
        msg.setWindowTitle("Clear All Files")
        msg.setText("Remove all selected files from the import list?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet(
            "QMessageBox{background:#F8FAFC;color:#1E2A3A;}"
            "QMessageBox QLabel{color:#1E2A3A;font-size:12px;}"
            "QPushButton{min-width:80px;min-height:28px;border-radius:4px;"
            "background:#FFFFFF;color:#1E2A3A;border:1px solid #B0BEC5;}"
            "QPushButton:hover{background:#E3F2FD;}"
            "QPushButton:disabled{background:#E9EEF3;color:#90A4AE;}"
        )
        # Style the Yes/No buttons explicitly for clarity
        yes_btn = msg.button(QMessageBox.Yes)
        no_btn = msg.button(QMessageBox.No)
        # Buttons may be None until exec on some platforms; apply post-exec style if needed
        resp = msg.exec()
        if resp != QMessageBox.Yes:
            return
        for p in list(self._file_rows.keys()):
            self._remove_file(p)

    def _refresh_buttons(self):
        has_files = bool(self._file_rows)
        has_valid_inquiry = bool(self._get_inquiry_number())
        has_mode = bool(self._get_selected_mode())
        self.proceed_btn.setEnabled(has_files and has_valid_inquiry and has_mode)
        if hasattr(self, "clear_btn"):
            self.clear_btn.setEnabled(has_files)
        if hasattr(self, "save_session_btn"):
            self.save_session_btn.setEnabled(has_files and has_valid_inquiry and has_mode)

    def _clear_sub_rows(self, path: str):
        for sub in self._sub_rows.pop(path, []):
            sub.setParent(None)
            sub.deleteLater()

    def _build_sub_rows(self, path: str, vendors: list):
        """Insert sub-rows below the parent FileRow when a file produced multiple entries."""
        if len(vendors) <= 1:
            return
        parent_row = self._file_rows.get(path)
        if not parent_row:
            return
        insert_idx = self.list_layout.indexOf(parent_row) + 1
        sub_list = []
        for vd in vendors:
            if vd.shipping_line:
                label = f"{vd.vendor_name}  —  {vd.shipping_line}"
            elif vd.airline:
                label = f"{vd.vendor_name}  —  {vd.airline}"
            else:
                label = vd.vendor_name
            sub = SubEntryRow(vd.uid, label, vd.quote_type)
            sub.remove_requested.connect(self._remove_sub_entry)
            self.list_layout.insertWidget(insert_idx, sub)
            insert_idx += 1
            sub_list.append(sub)
        self._sub_rows[path] = sub_list

    def _remove_sub_entry(self, uid: str):
        vd = self.app.vendors.pop(uid, None)
        if not vd:
            return
        path = vd.source_file
        for sub in list(self._sub_rows.get(path, [])):
            if sub.uid == uid:
                self._sub_rows[path].remove(sub)
                sub.setParent(None)
                sub.deleteLater()
                break
        # Update parent badge to reflect remaining entries
        remaining = [v for v in self.app.vendors.values() if v.source_file == path]
        row = self._file_rows.get(path)
        if row and remaining:
            modes = {v.quote_type for v in remaining}
            row.set_mode("mixed" if len(modes) > 1 else modes.pop())

    # ------------------------------------------------------------------
    def _proceed(self):
        if not self._file_rows:
            return
        entered_inq = self._get_inquiry_number()
        if not entered_inq:
            QMessageBox.warning(
                self,
                "Inquiry Number Required",
                "Please enter a valid inquiry number before proceeding.\n\n"
                "Format: E followed by 6 digits (e.g. E250950).",
            )
            self._inquiry_input.setFocus()
            self._inquiry_input.selectAll()
            return
        selected_mode = self._get_selected_mode()
        if not selected_mode:
            QMessageBox.warning(
                self,
                "Quote Mode Required",
                "Please select whether these quotes are AIR, FCL, or LCL before proceeding.",
            )
            self._mode_combo.setFocus()
            return

        pending = []
        if self.app.gemini_service:
            pending = [p for p in self._file_rows if p not in self._extracted_paths]

        # --- Pre-check: validate files against the entered inquiry number ---
        if pending:
            from src.services.job_utils import find_job_in_file
            from src.services.quote_mode_utils import (
                guess_quote_mode_in_file,
                is_strong_mode_mismatch,
            )

            self.status_label.setVisible(True)
            self.status_label.setText("Scanning files for inquiry numbers…")
            self.repaint()

            path_to_job: dict[str, str | None] = {
                p: find_job_in_file(p) for p in pending
            }

            # Flag any file that has a different non-empty inquiry number.
            mismatches = [
                (p, job)
                for p, job in path_to_job.items()
                if job and job.upper() != entered_inq
            ]
            if mismatches:
                dlg = _InquiryMismatchDialog(entered_inq, mismatches, self)
                if dlg.exec() != QDialog.Accepted:
                    self.status_label.setVisible(False)
                    return
                for p in dlg.paths_to_remove():
                    if p in self._file_rows:
                        self._remove_file(p)
                pending = [p for p in self._file_rows if p not in self._extracted_paths]
                if not pending:
                    self.status_label.setVisible(False)
                    self._go_to_mapping()
                    return

            self.status_label.setVisible(False)

            self.status_label.setVisible(True)
            self.status_label.setText("Checking files against selected quote mode…")
            self.repaint()

            mode_mismatches = []
            for p in pending:
                guessed_mode, score = guess_quote_mode_in_file(p)
                if is_strong_mode_mismatch(selected_mode, guessed_mode, score):
                    mode_mismatches.append((p, guessed_mode, score))

            self.status_label.setVisible(False)
            if mode_mismatches:
                dlg = _QuoteModeMismatchDialog(selected_mode, mode_mismatches, self)
                if dlg.exec() != QDialog.Accepted:
                    return

        if pending:
            self.proceed_btn.setEnabled(False)
            self._mode_combo.setEnabled(False)
            self.progress.setMaximum(len(pending))
            self.progress.setValue(0)
            self.progress.setVisible(True)
            self.status_label.setText(f"Extracting charges from {len(pending)} file(s)...")
            self.status_label.setVisible(True)
            self._done_count = 0

            self._worker = ExtractionWorker(
                pending,
                self.app.gemini_service,
                selected_mode,
                self,
            )
            self._worker.file_started.connect(self._on_started)
            self._worker.file_done.connect(self._on_done)
            self._worker.file_error.connect(self._on_error)
            self._worker.all_done.connect(self._on_all_done)
            self._worker.start()
        else:
            self._go_to_mapping()

    def _on_started(self, path: str):
        row = self._file_rows.get(path)
        if row:
            row.set_status("processing")
        self.status_label.setText(
            f"Extracting {Path(path).name}...  "
            f"({self._done_count + 1} of {self.progress.maximum()})"
        )

    def _on_done(self, path: str, results: list):
        self._done_count += 1
        self.progress.setValue(self._done_count)
        self._extracted_paths.add(path)

        stale = [k for k, vd in self.app.vendors.items() if vd.source_file == path]
        for k in stale:
            del self.app.vendors[k]
        self._clear_sub_rows(path)

        if not results:
            results = [{"vendor_name": Path(path).stem, "quote_type": self._get_selected_mode() or "air",
                        "shipping_line": "", "container_type": "", "charges": []}]

        first_vendor_name = ""
        created: list[VendorData] = []
        for rd in results:
            vendor_name = rd.get("vendor_name") or Path(path).stem
            if not first_vendor_name:
                first_vendor_name = vendor_name
            vd = VendorData(vendor_name, path)
            vd.quote_type     = rd.get("quote_type", "air")
            vd.shipping_line  = rd.get("shipping_line", "")
            vd.airline        = rd.get("airline", "")
            vd.container_type = rd.get("container_type", "")
            vd.etd            = str(rd.get("etd") or "")
            vd.transit_days   = str(rd.get("transit_days") or "")
            try:
                vd.free_days_origin = int(rd.get("free_days_origin") or 0)
            except (ValueError, TypeError):
                vd.free_days_origin = 0
            try:
                vd.free_days_destination = int(rd.get("free_days_destination") or 0)
            except (ValueError, TypeError):
                vd.free_days_destination = 0
            from src.services.bucketing_rules import rebucket_charges
            vd.set_charges_from_dicts(
                rebucket_charges(vd.quote_type, rd.get("charges", []))
            )
            if self.app.chargeable_weight > 0:
                from src.services.slab_utils import auto_mark_slab_optional
                auto_mark_slab_optional(vd, self.app.chargeable_weight)
            vd.status = "done"
            self.app.vendors[vd.uid] = vd
            created.append(vd)

        row = self._file_rows.get(path)
        if row:
            row.set_status("done", first_vendor_name)
            modes = {vd.quote_type for vd in created}
            row.set_mode("mixed" if len(modes) > 1 else (modes.pop() if modes else "air"))

        self._build_sub_rows(path, created)

    def _on_error(self, path: str, msg: str):
        self._done_count += 1
        self.progress.setValue(self._done_count)
        self._extracted_paths.add(path)

        vd = VendorData(Path(path).stem, path)
        vd.status = "error"
        vd.error = msg
        self.app.vendors[vd.uid] = vd

        row = self._file_rows.get(path)
        if row:
            row.set_status("error")
            row.set_error_tip(msg)

    def _on_all_done(self):
        self._mode_combo.setEnabled(True)
        self.progress.setVisible(False)
        self.status_label.setVisible(False)
        self._go_to_mapping()

    def _go_to_mapping(self):
        self._mode_combo.setEnabled(True)
        for path in self._file_rows:
            if path not in self._extracted_paths:
                vd = VendorData(Path(path).stem, path)
                vd.quote_type = self._get_selected_mode() or "air"
                vd.status = "done"
                self.app.vendors[vd.uid] = vd
                self._extracted_paths.add(path)
        self.proceed_btn.setEnabled(True)
        self._refresh_buttons()
        from src.services import session_service
        session_service.save_session(self.app)
        self.app.go_to_mapping()

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _save_session_manual(self):
        """Explicit Save Session button handler."""
        inquiry = self._get_inquiry_number()
        mode = self._get_selected_mode()
        if not inquiry or not mode:
            QMessageBox.warning(self, "Cannot Save",
                                "Please enter a valid inquiry number and select a quote mode first.")
            return
        if not self._file_rows:
            QMessageBox.warning(self, "Cannot Save", "No files are loaded yet.")
            return
        from src.services import session_service
        path = session_service.save_session(self.app)
        if path:
            QMessageBox.information(self, "Session Saved",
                                    f"Session saved:\n{path}")
        else:
            QMessageBox.warning(self, "Save Failed",
                                "Session could not be saved. Check that inquiry number and mode are set.")

    def _show_session_picker(self):
        """Open a dialog listing all saved sessions so the user can pick one to load."""
        from src.services import session_service
        sessions = session_service.list_sessions()
        if not sessions:
            QMessageBox.information(self, "No Saved Sessions",
                                    "No saved sessions found yet.\n\n"
                                    "Sessions are saved automatically when you proceed to the mapping page.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Load Saved Session")
        dlg.setMinimumWidth(540)
        dlg.setStyleSheet("background:#F8FAFC;color:#1E2A3A;")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        hdr = QLabel("Select a session to load:")
        hdr.setStyleSheet("font-size:13px;font-weight:600;color:#1E2A3A;")
        lay.addWidget(hdr)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QDialogButtonBox
        lst = QListWidget()
        lst.setStyleSheet(
            "QListWidget{border:1px solid #B0BEC5;border-radius:5px;background:#FFFFFF;}"
            "QListWidget::item{padding:8px 10px;border-bottom:1px solid #E0E0E0;color:#1E2A3A;}"
            "QListWidget::item:selected{background:#E3F2FD;color:#1565C0;}"
        )
        lst.setAlternatingRowColors(False)
        session_list = []
        for s in sessions:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(s["saved_at"])
                date_str = dt.strftime("%d %b %Y  %H:%M")
            except Exception:
                date_str = s["saved_at"]
            label = (f"{s['inquiry']}  —  {s['mode']}  —  "
                     f"{s['vendor_count']} vendor(s)  —  saved {date_str}")
            item = QListWidgetItem(label)
            lst.addItem(item)
            session_list.append(s)
        lst.setCurrentRow(0)
        lay.addWidget(lst)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(
            "QPushButton{min-width:80px;min-height:28px;border-radius:4px;"
            "background:#FFFFFF;color:#1E2A3A;border:1px solid #B0BEC5;}"
            "QPushButton:hover{background:#E3F2FD;}"
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lst.doubleClicked.connect(dlg.accept)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return
        row = lst.currentRow()
        if row < 0:
            return
        chosen = session_list[row]
        sess = session_service.load_session(chosen["inquiry"], chosen["mode"])
        if sess is None:
            QMessageBox.warning(self, "Load Failed", "Could not read the session file.")
            return

        if self._file_rows:
            reply = QMessageBox.question(
                self, "Load Saved Session",
                "Loading a session will replace all currently loaded files and vendors.\nContinue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        # Set inquiry + mode fields to match the chosen session
        self._inquiry_input.blockSignals(True)
        self._inquiry_input.setText(chosen["inquiry"])
        self._inquiry_input.blockSignals(False)
        self.app.inquiry_number = chosen["inquiry"].upper()
        self._inquiry_input.setStyleSheet(_INQUIRY_VALID_STYLE)
        self._inquiry_hint.setText("Valid")
        self._inquiry_hint.setStyleSheet("font-size:11px;color:#43A047;margin-left:6px;")

        mode_idx = self._mode_combo.findData(chosen["mode"].lower())
        if mode_idx >= 0:
            self._mode_combo.blockSignals(True)
            self._mode_combo.setCurrentIndex(mode_idx)
            self._mode_combo.blockSignals(False)
            self.app.selected_quote_mode = chosen["mode"].lower()
            self._mode_hint.setText(chosen["mode"])
            self._mode_hint.setStyleSheet("font-size:11px;color:#43A047;margin-left:6px;")
            self._mode_combo.setStyleSheet(
                "QComboBox{border:1px solid #43A047;border-radius:5px;padding:0 10px;"
                "font-size:13px;color:#1E2A3A;background:#F1F8E9;}"
                "QComboBox:focus{border:1px solid #1976D2;}"
            )
            self._update_weight_state()

        self._apply_session(sess)

    def _check_session(self):
        inquiry = self._get_inquiry_number()
        mode = self._get_selected_mode()
        if not inquiry or not mode:
            self._session_banner.setVisible(False)
            self._current_session = None
            return
        from src.services import session_service
        sess = session_service.load_session(inquiry, mode)
        if sess is None:
            self._session_banner.setVisible(False)
            self._current_session = None
            return
        self._current_session = sess
        vendor_count = len(sess.get("vendors", []))
        saved_at = sess.get("saved_at", "")
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(saved_at)
            saved_at_display = dt.strftime("%d %b %Y %H:%M")
        except Exception:
            saved_at_display = saved_at
        self._session_info_lbl.setText(
            f"Saved session found — {vendor_count} vendor(s) — last saved {saved_at_display}"
        )
        self._session_banner.setVisible(True)

    def _load_session(self):
        if not self._current_session:
            return
        if self._file_rows:
            reply = QMessageBox.question(
                self,
                "Load Saved Session",
                "Loading the saved session will replace all currently loaded files and vendors.\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self._apply_session(self._current_session)
        self._dismiss_session()

    def _dismiss_session(self):
        self._current_session = None
        self._session_banner.setVisible(False)

    def _apply_session(self, session: dict):
        # Clear existing rows and vendor state
        for path in list(self._file_rows.keys()):
            self._clear_sub_rows(path)
            row = self._file_rows.pop(path)
            row.setParent(None)
            row.deleteLater()
        self.app.vendors.clear()
        self._extracted_paths.clear()

        # Restore chargeable weight
        try:
            cw = float(session.get("chargeable_weight") or 0.0)
        except (ValueError, TypeError):
            cw = 0.0
        self._weight_input.blockSignals(True)
        self._weight_input.setValue(cw)
        self._weight_input.blockSignals(False)
        self.app.chargeable_weight = cw

        # Restore inquiry number on app (already set in _on_inquiry_changed, but ensure consistency)
        self.app.inquiry_number = session.get("inquiry_number", self.app.inquiry_number)

        # Restore vendors — group by source_file to build FileRows correctly
        file_to_vendors: dict[str, list[VendorData]] = {}
        for vd_dict in session.get("vendors", []):
            vd = VendorData.from_dict(vd_dict)
            self.app.vendors[vd.uid] = vd
            file_to_vendors.setdefault(vd.source_file, []).append(vd)

        for src, vd_list in file_to_vendors.items():
            row = FileRow(src)
            row.remove_requested.connect(self._remove_file)
            first_name = vd_list[0].vendor_name if vd_list else ""
            modes = {vd.quote_type for vd in vd_list}
            row.set_status("done", first_name)
            row.set_mode("mixed" if len(modes) > 1 else (modes.pop() if modes else "air"))
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            self._file_rows[src] = row
            self._extracted_paths.add(src)
            self._build_sub_rows(src, vd_list)

        self._refresh_buttons()

    # ------------------------------------------------------------------
    @staticmethod
    def _pri_btn_style():
        return (
            "QPushButton{background:#1976D2;color:white;border:none;"
            "border-radius:6px;padding:0 18px;font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#1565C0;}"
            "QPushButton:disabled{background:#B0BEC5;color:#ECEFF1;}"
        )

    @staticmethod
    def _sec_btn_style():
        return (
            "QPushButton{background:#FFFFFF;color:#1E2A3A;border:1px solid #90A4AE;"
            "border-radius:6px;padding:0 16px;font-size:13px;}"
            "QPushButton:hover{background:#F0F4F8;}"
        )
