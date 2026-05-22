from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QComboBox, QScrollArea, QApplication,
    QSizePolicy,
)

from src.services.app_paths import app_data_dir, app_log_file, sessions_dir, settings_file
from src.services.settings_service import DEFAULT_GEMINI_MODEL


class SettingsPage(QWidget):
    _MODEL_OPTIONS = [
        ("gemini-3.1-flash-lite", "3.1 Flash Lite  (recommended)"),
        ("gemini-2.5-flash",      "2.5 Flash"),
    ]

    def __init__(self, app_window, parent=None):
        super().__init__(parent)
        self.app = app_window
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sticky page header ─────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            "QFrame{background:#FFFFFF;border:none;border-bottom:1px solid #E6ECF2;}"
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(40, 24, 40, 20)
        h_lay.setSpacing(4)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:22px;font-weight:700;color:#1E2A3A;border:none;")
        h_lay.addWidget(title)

        sub = QLabel(
            "Configure API keys and runtime options for this desktop app. "
            "Settings are saved per Windows user profile and reused by the packaged .exe."
        )
        sub.setStyleSheet("font-size:13px;color:#607080;border:none;")
        sub.setWordWrap(True)
        h_lay.addWidget(sub)
        root.addWidget(header)

        # ── Scrollable body ────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#F4F6F9;}")

        body = QWidget()
        body.setStyleSheet("background:#F4F6F9;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(40, 28, 40, 28)
        body_lay.setSpacing(18)

        # Status banner
        self._status = QFrame()
        self._status.setVisible(False)
        self._status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._status_icon = QLabel("●")
        self._status_icon.setFixedSize(20, 20)
        self._status_icon.setAlignment(Qt.AlignCenter)
        self._status_title = QLabel("")
        self._status_title.setStyleSheet("font-size:13px;font-weight:700;")
        self._status_body  = QLabel("")
        self._status_body.setStyleSheet("font-size:12px;")
        self._status_body.setWordWrap(True)
        s_lay = QHBoxLayout(self._status)
        s_lay.setContentsMargins(16, 12, 16, 12)
        s_lay.setSpacing(12)
        s_lay.addWidget(self._status_icon, 0, Qt.AlignTop)
        s_txt = QVBoxLayout()
        s_txt.setSpacing(2)
        s_txt.addWidget(self._status_title)
        s_txt.addWidget(self._status_body)
        s_lay.addLayout(s_txt, 1)
        body_lay.addWidget(self._status)

        body_lay.addWidget(self._build_ai_card())
        body_lay.addWidget(self._build_cloud_card())
        body_lay.addWidget(self._build_storage_card())

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── Sticky footer ──────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(
            "QFrame{background:#FFFFFF;border:none;border-top:1px solid #E6ECF2;}"
        )
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(40, 12, 40, 12)
        f_lay.setSpacing(10)

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(42)
        back_btn.setStyleSheet(self._sec_btn_style())
        back_btn.clicked.connect(self.app.return_from_settings)
        f_lay.addWidget(back_btn)
        f_lay.addStretch()

        save_btn = QPushButton("  Save Settings  ")
        save_btn.setFixedHeight(42)
        save_btn.setStyleSheet(self._pri_btn_style())
        save_btn.clicked.connect(self._save)
        f_lay.addWidget(save_btn)
        root.addWidget(footer)

    # ------------------------------------------------------------------
    def _build_ai_card(self) -> QFrame:
        card, lay = self._card("#1976D2")
        lay.addWidget(self._card_header(
            "AI Extraction",
            "Charges are auto-extracted from vendor quote emails (PDF or MSG) using an AI API key.",
        ))
        lay.addWidget(self._hline())

        # API key — full width
        self._gemini_key = self._secret_field(
            "AI Extraction API Key",
            "Paste your AI extraction API key here",
            "Stored only for this Windows user profile.",
        )
        lay.addWidget(self._gemini_key["wrap"])

        # Model selector — below, 50% width
        self._gemini_model = self._model_field()
        model_wrap = QHBoxLayout()
        model_wrap.setContentsMargins(0, 0, 0, 0)
        model_wrap.addWidget(self._gemini_model["wrap"], 0)
        model_wrap.addStretch(1)
        lay.addLayout(model_wrap)
        return card

    def _build_cloud_card(self) -> QFrame:
        card, lay = self._card("#2E7D32")
        lay.addWidget(self._card_header(
            "Cloud Service",
            "Exchange rates and inquiry logging go through the Nagarkot cloud service on Vercel.",
        ))
        lay.addWidget(self._hline())

        self._user_name = self._text_field(
            "Your Name",
            "e.g. Sarthak",
            "Shown in the dashboard to identify who processed each inquiry.",
        )
        lay.addWidget(self._user_name["wrap"])

        self._cloud_url = self._text_field(
            "Cloud Service URL",
            "https://your-app.vercel.app",
            "The base URL of your Vercel deployment.",
        )
        lay.addWidget(self._cloud_url["wrap"])

        self._cloud_key = self._secret_field(
            "Cloud API Key",
            "Paste the CLOUD_API_KEY value here",
            "Must match the CLOUD_API_KEY environment variable set on Vercel.",
        )
        lay.addWidget(self._cloud_key["wrap"])
        return card

    def _build_storage_card(self) -> QFrame:
        card, lay = self._card("#546E7A")
        lay.addWidget(self._card_header(
            "Storage Paths",
            "Useful for support, backups, and session-file troubleshooting.",
        ))
        lay.addWidget(self._hline())

        for label, value in (
            ("Settings File",        str(settings_file())),
            ("User Data Folder",     str(app_data_dir())),
            ("Desktop Log File",     str(app_log_file())),
            ("Saved Sessions",       str(sessions_dir())),
        ):
            lay.addWidget(self._path_row(label, value))
        return card

    # ------------------------------------------------------------------
    # Component builders
    # ------------------------------------------------------------------
    def _card(self, accent: str) -> tuple:
        """Return (outer QFrame, inner QVBoxLayout).  accent = top-border color."""
        outer = QFrame()
        outer.setStyleSheet(
            f"QFrame#settingsCard{{background:#FFFFFF;"
            f"border:1px solid #DCE3EA;"
            f"border-top:4px solid {accent};"
            f"border-radius:12px;}}"
        )
        outer.setObjectName("settingsCard")
        lay = QVBoxLayout(outer)
        lay.setContentsMargins(24, 20, 24, 22)
        lay.setSpacing(14)
        return outer, lay

    def _card_header(self, title: str, desc: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet("font-size:15px;font-weight:700;color:#1E2A3A;border:none;")
        lay.addWidget(t)
        d = QLabel(desc)
        d.setStyleSheet("font-size:12px;color:#607080;border:none;")
        d.setWordWrap(True)
        lay.addWidget(d)
        return w

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#E6ECF2;border:none;background:#E6ECF2;max-height:1px;")
        return line

    def _text_field(self, label_text: str, placeholder: str, hint: str) -> dict:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size:12px;font-weight:600;color:#1E2A3A;border:none;")
        lay.addWidget(lbl)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(40)
        edit.setStyleSheet(
            "QLineEdit{border:1px solid #CFD8DC;border-radius:8px;"
            "padding:0 14px;font-size:13px;color:#1E2A3A;background:#FAFBFC;}"
            "QLineEdit:focus{border:1px solid #1976D2;background:#FFFFFF;}"
        )
        lay.addWidget(edit)

        h = QLabel(hint)
        h.setStyleSheet("font-size:11px;color:#90A4AE;border:none;")
        lay.addWidget(h)
        return {"wrap": wrap, "edit": edit}

    def _secret_field(self, label_text: str, placeholder: str, hint: str) -> dict:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size:12px;font-weight:600;color:#1E2A3A;border:none;")
        lay.addWidget(lbl)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setEchoMode(QLineEdit.Password)
        edit.setFixedHeight(40)
        edit.setStyleSheet(
            "QLineEdit{border:1px solid #CFD8DC;border-radius:8px;"
            "padding:0 14px;font-size:13px;color:#1E2A3A;background:#FAFBFC;}"
            "QLineEdit:focus{border:1px solid #1976D2;background:#FFFFFF;}"
        )
        row.addWidget(edit, 1)

        toggle = QPushButton("Show")
        toggle.setFixedHeight(40)
        toggle.setFixedWidth(72)
        toggle.setStyleSheet(
            "QPushButton{background:#EEF2F7;color:#1E2A3A;border:1px solid #CFD8DC;"
            "border-radius:8px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#E3F2FD;border-color:#90CAF9;}"
        )
        toggle.clicked.connect(lambda _=False, e=edit, b=toggle: self._toggle_secret(e, b))
        row.addWidget(toggle)
        lay.addLayout(row)

        h = QLabel(hint)
        h.setStyleSheet("font-size:11px;color:#90A4AE;border:none;")
        lay.addWidget(h)
        return {"wrap": wrap, "edit": edit, "toggle": toggle}

    def _model_field(self) -> dict:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        lbl = QLabel("AI Model")
        lbl.setStyleSheet("font-size:12px;font-weight:600;color:#1E2A3A;border:none;")
        lay.addWidget(lbl)

        combo = QComboBox()
        combo.setFixedHeight(40)
        combo.setMinimumWidth(220)
        combo.setStyleSheet(
            "QComboBox{border:1px solid #CFD8DC;border-radius:8px;"
            "padding:0 14px;font-size:13px;color:#1E2A3A;background:#FAFBFC;}"
            "QComboBox:focus{border:1px solid #1976D2;}"
            "QComboBox::drop-down{border:none;width:28px;}"
            "QComboBox QAbstractItemView{border:1px solid #CFD8DC;background:#FFFFFF;"
            "color:#1E2A3A;selection-background-color:#E3F2FD;selection-color:#1E2A3A;}"
        )
        for value, label_text in self._MODEL_OPTIONS:
            combo.addItem(label_text, value)
        lay.addWidget(combo)

        h = QLabel("Choose between 3.1 Flash Lite and 2.5 Flash for extraction.")
        h.setStyleSheet("font-size:11px;color:#90A4AE;border:none;")
        lay.addWidget(h)
        return {"wrap": wrap, "combo": combo}

    def _path_row(self, label_text: str, value: str) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame{background:#F8FAFC;border:1px solid #E6ECF2;"
            "border-radius:8px;}"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            "font-size:11px;font-weight:700;color:#546E7A;"
            "text-transform:uppercase;letter-spacing:0.5px;border:none;"
        )
        info.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet("font-size:12px;color:#1E2A3A;border:none;")
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setWordWrap(True)
        info.addWidget(val)

        lay.addLayout(info, 1)

        copy_btn = QPushButton("Copy")
        copy_btn.setFixedHeight(30)
        copy_btn.setFixedWidth(58)
        copy_btn.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#1E2A3A;"
            "border:1px solid #CFD8DC;border-radius:6px;"
            "font-size:11px;font-weight:600;}"
            "QPushButton:hover{background:#E3F2FD;border-color:#90CAF9;color:#1565C0;}"
        )
        copy_btn.clicked.connect(lambda _=False, v=value: self._copy_to_clipboard(v, copy_btn))
        lay.addWidget(copy_btn, 0, Qt.AlignVCenter)
        return row

    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, text: str, btn: QPushButton):
        QApplication.clipboard().setText(text)
        btn.setText("Copied")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: btn.setText("Copy"))

    def _toggle_secret(self, edit: QLineEdit, btn: QPushButton):
        showing = edit.echoMode() == QLineEdit.Normal
        edit.setEchoMode(QLineEdit.Password if showing else QLineEdit.Normal)
        btn.setText("Show" if showing else "Hide")

    # ------------------------------------------------------------------
    def load_settings(self):
        settings = self.app.settings
        self._gemini_key["edit"].setText(settings.get("gemini_api_key", ""))
        model_value = settings.get("gemini_model", DEFAULT_GEMINI_MODEL)
        idx = self._gemini_model["combo"].findData(model_value)
        self._gemini_model["combo"].setCurrentIndex(idx if idx >= 0 else 0)
        self._user_name["edit"].setText(settings.get("user_display_name", ""))
        self._cloud_url["edit"].setText(settings.get("cloud_service_url", ""))
        self._cloud_key["edit"].setText(settings.get("cloud_api_key", ""))
        self.refresh_runtime_state("")

    def refresh_runtime_state(self, warning: str):
        if warning:
            self._apply_status(
                "#FFF3E0", "#E65100", "#FFB74D",
                "!", "AI extraction could not be initialised", warning,
            )
            return

        gemini_ready = self.app.gemini_service is not None
        cloud_ready  = bool(self.app.settings.get("cloud_service_url", "").strip())

        if gemini_ready:
            detail = "Vendor quote extraction is active."
            if cloud_ready:
                detail += "  Cloud service is configured for live exchange rates and inquiry logging."
            self._apply_status("#E8F5E9", "#1B5E20", "#A5D6A7",
                               "OK", "Everything is configured", detail)
        else:
            detail = "AI extraction is not configured yet — manual mapping will still work."
            if cloud_ready:
                detail += "  Cloud service is configured."
            self._apply_status("#FFF8E1", "#7B5800", "#FFE082",
                               "!", "AI extraction API key not set", detail)

    def _apply_status(self, bg, fg, border, icon, title, body):
        self._status.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {border};"
            f"border-radius:10px;}}"
        )
        self._status_icon.setText(icon)
        self._status_icon.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{fg};border:none;"
        )
        self._status_title.setText(title)
        self._status_title.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{fg};border:none;"
        )
        self._status_body.setText(body)
        self._status_body.setStyleSheet(
            f"font-size:12px;color:{fg};border:none;"
        )
        self._status.setVisible(True)

    def _save(self):
        settings = {
            "gemini_api_key":    self._gemini_key["edit"].text().strip(),
            "gemini_model":      self._gemini_model["combo"].currentData() or DEFAULT_GEMINI_MODEL,
            "user_display_name": self._user_name["edit"].text().strip(),
            "cloud_service_url": self._cloud_url["edit"].text().strip(),
            "cloud_api_key":     self._cloud_key["edit"].text().strip(),
        }
        warning = self.app.apply_settings(settings)
        if warning:
            QMessageBox.warning(
                self, "Settings Saved With Warning",
                "The settings were saved, but AI extraction could not be initialised.\n\n"
                f"{warning}\n\nYou can still use manual mapping.",
            )
        else:
            QMessageBox.information(self, "Settings Saved", "Your settings were saved successfully.")

    # ------------------------------------------------------------------
    def _pri_btn_style(self) -> str:
        return (
            "QPushButton{background:#1976D2;color:white;border:none;border-radius:8px;"
            "padding:0 20px;font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#1565C0;}"
            "QPushButton:disabled{background:#B0BEC5;color:#ECEFF1;}"
        )

    def _sec_btn_style(self) -> str:
        return (
            "QPushButton{background:#FFFFFF;color:#1E2A3A;border:1px solid #B0BEC5;"
            "border-radius:8px;padding:0 20px;font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#EEF2F7;}"
        )
