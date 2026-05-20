"""
Dialog classes for the import page: job-number selector and inquiry mismatch resolver.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QDialog, QDialogButtonBox, QComboBox, QCheckBox,
)


class _JobNumberDialog(QDialog):
    """Dialog shown when multiple job numbers are detected.

    Accepts a mapping of job -> list[file_paths] where job may be None for unknowns.
    Returns selected_job (str) via `selected_job()` and whether to keep unknowns via `keep_unknowns()`.
    """
    def __init__(self, groups: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multiple enquiry numbers detected")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        desc = QLabel(
            "Multiple enquiry numbers were found in the selected files. "
            "Select the enquiry number you want to keep — other files will be removed."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:12px;color:#607080;")
        layout.addWidget(desc)

        summary_lines = []
        for job, files in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0])):
            label = job if job else "Unknown"
            summary_lines.append(f"{label}: {len(files)} file(s)")
        summary = QLabel("\n".join(summary_lines))
        summary.setStyleSheet("font-size:12px;color:#1E2A3A;")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        layout.addWidget(QLabel("Select enquiry number to keep:"))
        self._combo = QComboBox()
        job_items = [j for j in groups.keys() if j]
        self._combo.addItems(job_items)
        layout.addWidget(self._combo)

        self._keep_unknowns = QCheckBox("Keep files without detected job number")
        self._keep_unknowns.setChecked(False)
        layout.addWidget(self._keep_unknowns)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_job(self) -> str:
        return self._combo.currentText()

    def keep_unknowns(self) -> bool:
        return bool(self._keep_unknowns.isChecked())


class _InquiryMismatchDialog(QDialog):
    """Shown when files contain a job number different from the user-entered inquiry.

    Each mismatched file is listed with a checkbox (default unchecked = will be removed).
    The user checks any file they want to KEEP despite the mismatch.
    """

    _STYLE = (
        "QDialog{background:#F8FAFC;color:#1E2A3A;}"
        "QLabel{color:#1E2A3A;font-size:12px;}"
        "QPushButton{background:#FFFFFF;color:#1E2A3A;border:1px solid #B0BEC5;"
        "border-radius:5px;padding:5px 14px;font-size:12px;}"
        "QPushButton:hover{background:#EEF2F7;}"
        "QCheckBox{color:#1E2A3A;font-size:12px;spacing:8px;}"
        "QCheckBox::indicator{width:16px;height:16px;}"
    )

    def __init__(self, entered_job: str, mismatches: list, parent=None):
        # mismatches: list of (file_path, found_job_number)
        super().__init__(parent)
        self.setWindowTitle("Inquiry Number Mismatch")
        self.setMinimumWidth(540)
        self.setModal(True)
        self.setStyleSheet(self._STYLE)

        self._checks: dict[str, QCheckBox] = {}   # path → checkbox (checked = KEEP)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        title = QLabel("Inquiry Number Mismatch")
        title.setStyleSheet("font-size:14px;font-weight:700;color:#1E2A3A;")
        layout.addWidget(title)

        desc = QLabel(
            f"The files below contain an inquiry number other than "
            f"<b>{entered_job}</b>.<br>"
            f"Check any file you want to <b>keep</b> — unchecked files will be "
            f"removed before extraction."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:12px;color:#607080;")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{border:1px solid #DCE3EA;border-radius:4px;background:#FFFFFF;}"
        )
        content = QWidget()
        content.setStyleSheet("background:#FFFFFF;")
        cl = QVBoxLayout(content)
        cl.setSpacing(0)
        cl.setContentsMargins(8, 8, 8, 8)

        for path, found_job in mismatches:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{border:none;border-bottom:1px solid #F0F4F8;}"
                "QFrame:hover{background:#F8FAFC;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 6, 6, 6)
            rl.setSpacing(10)

            cb = QCheckBox()
            cb.setChecked(False)   # default = remove
            rl.addWidget(cb)
            self._checks[path] = cb

            name_lbl = QLabel(Path(path).name)
            name_lbl.setStyleSheet("font-size:12px;color:#1E2A3A;font-weight:600;")
            rl.addWidget(name_lbl, 1)

            tag = QLabel(f"contains  {found_job}")
            tag.setStyleSheet(
                "font-size:11px;font-weight:700;color:#E65100;"
                "background:#FFF3E0;border:1px solid #FFB74D;"
                "border-radius:3px;padding:1px 8px;"
            )
            rl.addWidget(tag)

            cl.addWidget(row)

        cl.addStretch()
        scroll.setWidget(content)
        scroll.setFixedHeight(min(len(mismatches) * 48 + 20, 280))
        layout.addWidget(scroll)

        sel_row = QHBoxLayout()
        keep_all_btn = QPushButton("Keep All")
        keep_all_btn.clicked.connect(lambda: self._set_all(True))
        sel_row.addWidget(keep_all_btn)
        remove_all_btn = QPushButton("Remove All")
        remove_all_btn.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(remove_all_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        proceed_btn = QPushButton("Proceed")
        proceed_btn.setStyleSheet(
            "QPushButton{background:#1976D2;color:white;border:none;"
            "border-radius:5px;padding:6px 18px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#1565C0;}"
        )
        proceed_btn.clicked.connect(self.accept)
        btn_row.addWidget(proceed_btn)
        layout.addLayout(btn_row)

    def _set_all(self, keep: bool):
        for cb in self._checks.values():
            cb.setChecked(keep)

    def paths_to_remove(self) -> set:
        """Return paths of files the user did NOT check (i.e. did not keep)."""
        return {path for path, cb in self._checks.items() if not cb.isChecked()}


class _QuoteModeMismatchDialog(QDialog):
    """Shown when lightweight heuristics suggest files may belong to another mode."""

    _STYLE = (
        "QDialog{background:#F8FAFC;color:#1E2A3A;}"
        "QLabel{color:#1E2A3A;font-size:12px;}"
        "QPushButton{background:#FFFFFF;color:#1E2A3A;border:1px solid #B0BEC5;"
        "border-radius:5px;padding:5px 14px;font-size:12px;}"
        "QPushButton:hover{background:#EEF2F7;}"
    )

    def __init__(self, selected_mode: str, mismatches: list[tuple[str, str, int]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Possible Quote Mode Mismatch")
        self.setMinimumWidth(560)
        self.setModal(True)
        self.setStyleSheet(self._STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        title = QLabel("Possible Quote Mode Mismatch")
        title.setStyleSheet("font-size:14px;font-weight:700;color:#1E2A3A;")
        layout.addWidget(title)

        desc = QLabel(
            f"You selected <b>{selected_mode.upper()}</b>, but one or more files strongly look like "
            f"a different quote mode based on a lightweight keyword check.<br>"
            f"This is only a warning. Your selected mode will still be used if you continue."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:12px;color:#607080;")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{border:1px solid #DCE3EA;border-radius:4px;background:#FFFFFF;}"
        )
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(0)
        cl.setContentsMargins(8, 8, 8, 8)

        for path, guessed_mode, score in mismatches:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{border:none;border-bottom:1px solid #F0F4F8;}"
                "QFrame:hover{background:#F8FAFC;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 6, 6, 6)
            rl.setSpacing(10)

            name_lbl = QLabel(Path(path).name)
            name_lbl.setStyleSheet("font-size:12px;color:#1E2A3A;font-weight:600;")
            rl.addWidget(name_lbl, 1)

            tag = QLabel(f"looks like {guessed_mode.upper()}  |  score {score}")
            tag.setStyleSheet(
                "font-size:11px;font-weight:700;color:#8E24AA;"
                "background:#F3E5F5;border:1px solid #CE93D8;"
                "border-radius:3px;padding:1px 8px;"
            )
            rl.addWidget(tag)
            cl.addWidget(row)

        cl.addStretch()
        scroll.setWidget(content)
        scroll.setFixedHeight(min(len(mismatches) * 48 + 20, 260))
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Go Back")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        proceed_btn = QPushButton("Continue Anyway")
        proceed_btn.setStyleSheet(
            "QPushButton{background:#1976D2;color:white;border:none;"
            "border-radius:5px;padding:6px 18px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#1565C0;}"
        )
        proceed_btn.clicked.connect(self.accept)
        btn_row.addWidget(proceed_btn)
        layout.addLayout(btn_row)
