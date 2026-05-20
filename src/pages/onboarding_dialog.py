from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QWidget, QSizePolicy,
)


_MODEL_OPTIONS = [
    ("gemini-2.5-flash", "Flash 2.5  (faster, lower cost)"),
    ("gemini-2.5-pro",   "Pro 2.5  (heavier reasoning)"),
]

_FIELD_STYLE = (
    "QLineEdit{border:1px solid #CFD8DC;border-radius:8px;"
    "padding:0 14px;font-size:13px;color:#1E2A3A;background:#FAFBFC;min-height:40px;}"
    "QLineEdit:focus{border:1px solid #1976D2;background:#FFFFFF;}"
    "QLineEdit[error='true']{border:1px solid #E53935;background:#FFEBEE;}"
)
_COMBO_STYLE = (
    "QComboBox{border:1px solid #CFD8DC;border-radius:8px;"
    "padding:0 14px;font-size:13px;color:#1E2A3A;background:#FAFBFC;min-height:40px;}"
    "QComboBox:focus{border:1px solid #1976D2;}"
    "QComboBox::drop-down{border:none;width:28px;}"
    "QComboBox QAbstractItemView{border:1px solid #CFD8DC;background:#FFFFFF;"
    "color:#1E2A3A;selection-background-color:#E3F2FD;}"
)


class OnboardingDialog(QDialog):
    """
    First-run setup dialog — shown when required API keys are missing.
    Returns accepted() if the user saved keys; rejected() if they skipped.
    Call .collected_settings() after exec() to get the entered values.
    """

    def __init__(self, current_settings: dict, parent=None):
        super().__init__(parent)
        self._settings = dict(current_settings)
        self._result_settings: dict = {}

        self.setWindowTitle("Welcome — Quick Setup")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self.setFixedWidth(580)
        self.setStyleSheet("QDialog{background:#F4F6F9;}")
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            "QFrame{background:#1565C0;border:none;}"
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(32, 28, 32, 24)
        h_lay.setSpacing(6)

        app_lbl = QLabel("Nagarkot Quote Compare")
        app_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#90CAF9;border:none;")
        h_lay.addWidget(app_lbl)

        title = QLabel("Quick Setup")
        title.setStyleSheet("font-size:22px;font-weight:700;color:#FFFFFF;border:none;")
        h_lay.addWidget(title)

        desc = QLabel(
            "One or more API keys are not configured yet.\n"
            "Set them up below to enable AI-powered charge extraction and live exchange rates."
        )
        desc.setStyleSheet("font-size:13px;color:#BBDEFB;border:none;line-height:1.4;")
        desc.setWordWrap(True)
        h_lay.addWidget(desc)
        root.addWidget(header)

        # ── Body ──────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background:#F4F6F9;border:none;")
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(32, 24, 32, 8)
        b_lay.setSpacing(20)

        # AI Extraction section
        b_lay.addWidget(self._section_header(
            "AI Extraction API Key",
            "Required for auto-extracting charges from vendor quote emails.",
            required=True,
        ))

        ai_row = QHBoxLayout()
        ai_row.setSpacing(8)
        self._ai_key_edit = QLineEdit()
        self._ai_key_edit.setPlaceholderText("Paste your AI extraction API key here")
        self._ai_key_edit.setEchoMode(QLineEdit.Password)
        self._ai_key_edit.setStyleSheet(_FIELD_STYLE)
        self._ai_key_edit.setText(self._settings.get("gemini_api_key", ""))
        self._ai_key_edit.textChanged.connect(lambda: self._clear_error(self._ai_key_edit))
        ai_row.addWidget(self._ai_key_edit, 1)

        self._ai_toggle = QPushButton("Show")
        self._ai_toggle.setFixedHeight(40)
        self._ai_toggle.setFixedWidth(68)
        self._ai_toggle.setStyleSheet(self._ghost_btn())
        self._ai_toggle.clicked.connect(
            lambda: self._toggle(self._ai_key_edit, self._ai_toggle)
        )
        ai_row.addWidget(self._ai_toggle)
        b_lay.addLayout(ai_row)

        # AI Model selector
        model_wrap = QWidget()
        model_wrap.setStyleSheet("background:transparent;border:none;")
        m_lay = QVBoxLayout(model_wrap)
        m_lay.setContentsMargins(0, 0, 0, 0)
        m_lay.setSpacing(6)

        m_lbl = QLabel("AI Model")
        m_lbl.setStyleSheet("font-size:12px;font-weight:600;color:#1E2A3A;border:none;")
        m_lay.addWidget(m_lbl)

        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet(_COMBO_STYLE)
        self._model_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._model_combo.setMinimumWidth(280)
        for value, label in _MODEL_OPTIONS:
            self._model_combo.addItem(label, value)
        saved_model = self._settings.get("gemini_model", "gemini-2.5-flash")
        idx = next((i for i, (v, _) in enumerate(_MODEL_OPTIONS) if v == saved_model), 0)
        self._model_combo.setCurrentIndex(idx)
        m_lay.addWidget(self._model_combo)

        m_hint = QLabel("Flash is faster and cheaper · Pro handles complex quote layouts")
        m_hint.setStyleSheet("font-size:11px;color:#90A4AE;border:none;")
        m_lay.addWidget(m_hint)
        b_lay.addWidget(model_wrap)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color:#DCE3EA;background:#DCE3EA;max-height:1px;border:none;")
        b_lay.addWidget(div)

        # Currency section
        b_lay.addWidget(self._section_header(
            "Free Currency API Key",
            "Optional. Enables live exchange-rate fetching instead of built-in fallback rates.",
            required=False,
        ))

        cur_row = QHBoxLayout()
        cur_row.setSpacing(8)
        self._cur_key_edit = QLineEdit()
        self._cur_key_edit.setPlaceholderText("Paste your Free Currency API key here  (optional)")
        self._cur_key_edit.setEchoMode(QLineEdit.Password)
        self._cur_key_edit.setStyleSheet(_FIELD_STYLE)
        self._cur_key_edit.setText(self._settings.get("free_currency_api_key", ""))
        cur_row.addWidget(self._cur_key_edit, 1)

        self._cur_toggle = QPushButton("Show")
        self._cur_toggle.setFixedHeight(40)
        self._cur_toggle.setFixedWidth(68)
        self._cur_toggle.setStyleSheet(self._ghost_btn())
        self._cur_toggle.clicked.connect(
            lambda: self._toggle(self._cur_key_edit, self._cur_toggle)
        )
        cur_row.addWidget(self._cur_toggle)
        b_lay.addLayout(cur_row)

        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet(
            "font-size:12px;color:#C62828;border:none;background:transparent;"
        )
        self._error_lbl.setVisible(False)
        b_lay.addWidget(self._error_lbl)

        root.addWidget(body)

        # ── Footer ────────────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(
            "QFrame{background:#FFFFFF;border:none;border-top:1px solid #E6ECF2;}"
        )
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(32, 14, 32, 14)
        f_lay.setSpacing(12)

        skip_btn = QPushButton("Skip for now")
        skip_btn.setFlat(True)
        skip_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#607080;border:none;"
            "font-size:13px;padding:0;}"
            "QPushButton:hover{color:#1E2A3A;}"
        )
        skip_btn.clicked.connect(self.reject)
        f_lay.addWidget(skip_btn)
        f_lay.addStretch()

        save_btn = QPushButton("Save and Get Started")
        save_btn.setFixedHeight(42)
        save_btn.setStyleSheet(
            "QPushButton{background:#1565C0;color:#FFFFFF;border:none;"
            "border-radius:8px;font-size:13px;font-weight:600;padding:0 24px;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        save_btn.clicked.connect(self._save)
        f_lay.addWidget(save_btn)
        root.addWidget(footer)

    # ------------------------------------------------------------------
    def _section_header(self, title: str, desc: str, required: bool) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        row = QHBoxLayout()
        row.setSpacing(6)
        t = QLabel(title)
        t.setStyleSheet("font-size:13px;font-weight:700;color:#1E2A3A;border:none;")
        row.addWidget(t)
        if required:
            req = QLabel("Required")
            req.setStyleSheet(
                "font-size:10px;font-weight:700;color:#FFFFFF;"
                "background:#E53935;border-radius:4px;padding:1px 6px;border:none;"
            )
            row.addWidget(req)
        row.addStretch()
        lay.addLayout(row)

        d = QLabel(desc)
        d.setStyleSheet("font-size:12px;color:#607080;border:none;")
        d.setWordWrap(True)
        lay.addWidget(d)
        return w

    def _toggle(self, edit: QLineEdit, btn: QPushButton):
        showing = edit.echoMode() == QLineEdit.Normal
        edit.setEchoMode(QLineEdit.Password if showing else QLineEdit.Normal)
        btn.setText("Show" if showing else "Hide")

    def _clear_error(self, edit: QLineEdit):
        edit.setProperty("error", "false")
        edit.setStyle(edit.style())
        self._error_lbl.setVisible(False)

    def _ghost_btn(self) -> str:
        return (
            "QPushButton{background:#EEF2F7;color:#1E2A3A;"
            "border:1px solid #CFD8DC;border-radius:8px;"
            "font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#E3F2FD;border-color:#90CAF9;}"
        )

    # ------------------------------------------------------------------
    def _save(self):
        ai_key = self._ai_key_edit.text().strip()
        if not ai_key:
            self._ai_key_edit.setProperty("error", "true")
            self._ai_key_edit.setStyle(self._ai_key_edit.style())
            self._error_lbl.setText(
                "AI Extraction API Key is required. Enter a key or click 'Skip for now'."
            )
            self._error_lbl.setVisible(True)
            self._ai_key_edit.setFocus()
            return

        self._result_settings = {
            "gemini_api_key":        ai_key,
            "gemini_model":          self._model_combo.currentData() or "gemini-2.5-flash",
            "free_currency_api_key": self._cur_key_edit.text().strip(),
        }
        self.accept()

    def collected_settings(self) -> dict:
        """Return the settings entered by the user (only valid after accept())."""
        return dict(self._result_settings)
