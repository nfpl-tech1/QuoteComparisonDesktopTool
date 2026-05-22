from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QSizePolicy,
)

from src.constants import APP_COLORS


class _StepButton(QPushButton):
    """Sidebar navigation button with number badge + label."""

    def __init__(self, number: int, label: str, parent=None):
        super().__init__(parent)
        self._number = number
        self._label = label
        self.setCheckable(False)
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._set_state("locked")

    def _set_state(self, state: str):
        self._state = state
        colors = {
            "locked": ("#354A5E", "#607080", "#607080"),
            "active": ("#1976D2", "#FFFFFF", "#FFFFFF"),
            "done": ("#1B3A2E", "#27AE60", "#A5D6A7"),
        }
        bg, num_col, txt_col = colors[state]
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: 0;
                text-align: left;
                padding-left: 16px;
            }}
            QPushButton:hover {{
                background: {'#1565C0' if state == 'active' else '#2C3E50'};
            }}
        """)
        self._num_color = num_col
        self._txt_color = txt_col
        self.update()

    def set_active(self):
        self._set_state("active")

    def set_done(self):
        self._set_state("done")

    def set_locked(self):
        self._set_state("locked")

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor

        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()

        cx, cy, rad = 28, r.height() // 2, 12
        if self._state == "done":
            p.setBrush(QColor("#27AE60"))
        elif self._state == "active":
            p.setBrush(QColor("#FFFFFF"))
        else:
            p.setBrush(QColor("#354A5E"))
        p.setPen(QColor(self._num_color))
        p.drawEllipse(cx - rad, cy - rad, rad * 2, rad * 2)

        if self._state == "done":
            badge_color = "#FFFFFF"
        elif self._state == "active":
            badge_color = "#1E2A3A"
        else:
            badge_color = self._num_color
        p.setPen(QColor(badge_color))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)
        badge_text = "✓" if self._state == "done" else str(self._number)
        p.drawText(cx - rad, cy - rad, rad * 2, rad * 2, Qt.AlignCenter, badge_text)

        p.setPen(QColor(self._txt_color))
        label_font = QFont()
        label_font.setPointSize(10)
        label_font.setBold(self._state == "active")
        p.setFont(label_font)
        p.drawText(
            cx + rad + 10,
            0,
            r.width() - cx - rad - 16,
            r.height(),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._label,
        )
        p.end()


class _HealthCheckWorker(QThread):
    result = Signal(bool)  # True = reachable

    def __init__(self, cloud_url: str, parent=None):
        super().__init__(parent)
        self._url = cloud_url.rstrip("/") + "/api/health" if cloud_url else ""

    def run(self):
        if not self._url:
            self.result.emit(False)
            return
        try:
            import requests
            resp = requests.get(self._url, timeout=5)
            self.result.emit(resp.status_code == 200)
        except Exception:
            self.result.emit(False)


class App(QMainWindow):
    def __init__(self, currency_service, gemini_service, settings: dict):
        super().__init__()
        self.currency_service = currency_service
        self.gemini_service = gemini_service
        self.settings = dict(settings)

        self.vendors: dict = {}
        self.chargeable_weight: float = 0.0
        self.selected_quote_mode: str = ""
        self.selected_lane: str = ""
        self.inquiry_number: str = ""
        self._previous_stack_idx = 0

        self._health_worker: _HealthCheckWorker | None = None

        self.setWindowTitle("Vendor Quote Comparison Tool")
        self.setMinimumSize(1100, 680)
        self.resize(1280, 800)
        self._build_ui()
        self._run_health_check()

    def _run_health_check(self):
        cloud_url = self.settings.get("cloud_service_url", "").strip()
        self._health_worker = _HealthCheckWorker(cloud_url, self)
        self._health_worker.result.connect(self._on_health_result)
        self._health_worker.start()

    def _on_health_result(self, ok: bool):
        if ok:
            self._cloud_lbl.setText("● Cloud OK")
            self._cloud_lbl.setStyleSheet("color:#27AE60; font-size:10px; padding:4px 8px;")
        else:
            self._cloud_lbl.setText("● Cloud offline")
            self._cloud_lbl.setStyleSheet("color:#E65100; font-size:10px; padding:4px 8px;")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet(f"background:{APP_COLORS['sidebar_bg']};")
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0, 0, 0, 0)
        sb_lay.setSpacing(0)

        logo = QLabel("Nagarkot\nQuote Compare")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedHeight(72)
        logo.setStyleSheet(
            "color:#FFFFFF; font-size:14px; font-weight:700;"
            f"background:{APP_COLORS['sidebar_bg']}; "
            "border-bottom:1px solid #2C3E50; padding:12px;"
        )
        sb_lay.addWidget(logo)

        self._step_btns: list[_StepButton] = []
        labels = ["Import Files", "Map Vendors", "Compare"]
        for i, lbl in enumerate(labels):
            btn = _StepButton(i + 1, lbl)
            btn.clicked.connect(lambda _checked, idx=i: self._on_step_clicked(idx))
            sb_lay.addWidget(btn)
            self._step_btns.append(btn)

        sb_lay.addStretch()

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setFixedHeight(42)
        self._settings_btn.clicked.connect(self.go_to_settings)
        sb_lay.addWidget(self._settings_btn)

        self._cloud_lbl = QLabel("● Cloud checking…")
        self._cloud_lbl.setAlignment(Qt.AlignCenter)
        self._cloud_lbl.setStyleSheet(
            "color:#607080; font-size:10px; padding:4px 8px;"
        )
        sb_lay.addWidget(self._cloud_lbl)

        footer = QLabel("Made with ❤ at Nagarkot Forwarders Pvt Ltd by Freight Team")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        footer.setStyleSheet(
            f"color:{APP_COLORS['sidebar_text']}; font-size:12px; padding:6px;"
        )
        sb_lay.addWidget(footer)

        ver = QLabel("v1.0")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color:#354A5E; font-size:10px; padding:8px;")
        sb_lay.addWidget(ver)

        root.addWidget(sidebar)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#2C3E50;")
        root.addWidget(sep)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{APP_COLORS['bg']};")
        root.addWidget(self.stack, 1)

        from src.pages.import_page import ImportPage
        from src.pages.mapping_page import MappingPage
        from src.pages.comparison_page import ComparisonPage
        from src.pages.settings_page import SettingsPage

        self.import_page = ImportPage(self)
        self.mapping_page = MappingPage(self)
        self.comparison_page = ComparisonPage(self)
        self.settings_page = SettingsPage(self)

        self.stack.addWidget(self.import_page)
        self.stack.addWidget(self.mapping_page)
        self.stack.addWidget(self.comparison_page)
        self.stack.addWidget(self.settings_page)

        self._show(0)

    def _show(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self._sync_nav(idx, settings_active=False)

    def _sync_nav(self, idx: int, settings_active: bool):
        for i, btn in enumerate(self._step_btns):
            if i < idx:
                btn.set_done()
            elif i == idx:
                btn.set_active()
            else:
                btn.set_locked()
        if settings_active:
            self._settings_btn.setStyleSheet(
                "QPushButton{background:#1976D2;color:#FFFFFF;border:none;"
                "padding:0 16px;text-align:left;font-size:12px;font-weight:600;}"
                "QPushButton:hover{background:#1565C0;}"
            )
        else:
            self._settings_btn.setStyleSheet(
                "QPushButton{background:#2C3E50;color:#B0BEC5;border:none;"
                "padding:0 16px;text-align:left;font-size:12px;font-weight:600;}"
                "QPushButton:hover{background:#354A5E;color:#FFFFFF;}"
            )

    def _on_step_clicked(self, idx: int):
        current = self.stack.currentIndex()
        if current == self.stack.indexOf(self.settings_page):
            current = self._previous_stack_idx
        if idx < current:
            if idx == 1:
                self.mapping_page.populate()
            self._show(idx)
        elif idx == current + 1:
            pass

    def go_to_import(self):
        self._show(0)

    def go_to_mapping(self):
        self.mapping_page.populate()
        self._show(1)

    def go_to_comparison(self):
        from src.services import session_service

        session_service.save_session(self)
        self.comparison_page.load()
        self._show(2)

    def go_to_settings(self):
        current = self.stack.currentIndex()
        settings_idx = self.stack.indexOf(self.settings_page)
        if current != settings_idx:
            self._previous_stack_idx = current if current in (0, 1, 2) else 0
        self.settings_page.load_settings()
        self.stack.setCurrentWidget(self.settings_page)
        self._sync_nav(min(self._previous_stack_idx, 2), settings_active=True)

    def return_from_settings(self):
        idx = self._previous_stack_idx if self._previous_stack_idx in (0, 1, 2) else 0
        if idx == 1:
            self.mapping_page.populate()
        elif idx == 2:
            self.comparison_page.load()
        self._show(idx)

    def apply_settings(self, new_settings: dict) -> str:
        from src.services.currency_service import CurrencyService
        from src.services.gemini_service import GeminiService
        from src.services.settings_service import DEFAULT_GEMINI_MODEL, save_settings

        save_settings(new_settings)
        self.settings = dict(new_settings)
        self.currency_service = CurrencyService(
            self.settings.get("cloud_service_url", ""),
            self.settings.get("cloud_api_key", ""),
        )

        warning = ""
        self.gemini_service = None
        api_key = self.settings.get("gemini_api_key", "").strip()
        model_name = self.settings.get("gemini_model", "").strip() or DEFAULT_GEMINI_MODEL
        if api_key:
            try:
                self.gemini_service = GeminiService(api_key, model_name=model_name)
            except Exception as exc:
                warning = str(exc)

        self.import_page.refresh_service_state()
        self.comparison_page.refresh_service_state()
        self.settings_page.refresh_runtime_state(warning)
        return warning
