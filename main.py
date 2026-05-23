import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from src.services.app_paths import app_log_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.FileHandler(app_log_file(), encoding="utf-8")],
    force=True,
)
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def main():
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox

    from src.services.dialog_theme import APP_DIALOG_STYLE
    from src.services.settings_service import DEFAULT_GEMINI_MODEL, load_settings

    class _NoScrollFilter(QObject):
        def eventFilter(self, obj, event):
            if isinstance(obj, QComboBox) and event.type() == QEvent.Type.Wheel:
                if not obj.hasFocus():
                    return True  # swallow the event
            return False

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_DIALOG_STYLE)

    _scroll_guard = _NoScrollFilter(app)
    app.installEventFilter(_scroll_guard)

    settings = load_settings()

    # ── Onboarding: show setup dialog if the AI key is missing ────────
    if not settings.get("gemini_api_key", "").strip():
        from src.pages.onboarding_dialog import OnboardingDialog
        from src.services.settings_service import save_settings as _save

        dlg = OnboardingDialog(settings)
        if dlg.exec():
            entered = dlg.collected_settings()
            settings.update(entered)
            _save(settings)

    from src.services.currency_service import CurrencyService

    currency_service = CurrencyService(
        settings.get("cloud_service_url", ""),
        settings.get("cloud_api_key", ""),
    )

    api_key = settings.get("gemini_api_key", "").strip()
    model_name = settings.get("gemini_model", "").strip() or DEFAULT_GEMINI_MODEL
    gemini_service = None
    if api_key:
        try:
            from src.services.gemini_service import GeminiService

            gemini_service = GeminiService(api_key, model_name=model_name)
        except Exception as exc:
            QMessageBox.warning(
                None,
                "AI Extraction Init Failed",
                f"Could not initialise AI extraction:\n{exc}\n\n"
                "You can still map charges manually.",
            )

    from src.app import App

    window = App(currency_service, gemini_service, settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
