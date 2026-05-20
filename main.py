import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def main():
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QMessageBox

    from src.services.dialog_theme import APP_DIALOG_STYLE
    from src.services.settings_service import load_settings

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_DIALOG_STYLE)

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

    currency_service = CurrencyService(settings.get("free_currency_api_key", ""))

    api_key = settings.get("gemini_api_key", "").strip()
    model_name = settings.get("gemini_model", "").strip() or "gemini-2.5-flash"
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
