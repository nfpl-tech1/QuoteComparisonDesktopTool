"""
Standalone dialog classes and the rate-fetch worker for the comparison page.
"""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QHeaderView,
    QComboBox, QDialogButtonBox, QFormLayout, QLineEdit, QDoubleSpinBox,
)

from src.constants import AIR_IMPORT_BUCKETS, FCL_BUCKETS, LCL_BUCKETS

# ---------------------------------------------------------------------------
# Shared style strings (also imported by comparison_page.py)
# ---------------------------------------------------------------------------
_POPUP_STYLE = """
    QDialog {
        background: #F8FAFC;
        color: #1E2A3A;
    }
    QDialog QLabel {
        color: #1E2A3A;
        font-size: 12px;
    }
    QDialog QLineEdit,
    QDialog QComboBox,
    QDialog QDoubleSpinBox {
        min-height: 28px;
        padding: 0 8px;
        color: #1E2A3A;
        background: #FFFFFF;
        border: 1px solid #B0BEC5;
        border-radius: 4px;
        selection-background-color: #BBDEFB;
        selection-color: #1E2A3A;
    }
    QDialog QLineEdit:focus,
    QDialog QComboBox:focus,
    QDialog QDoubleSpinBox:focus {
        border: 1px solid #1976D2;
    }
    QDialog QComboBox::drop-down,
    QDialog QDoubleSpinBox::up-button,
    QDialog QDoubleSpinBox::down-button {
        border: none;
        width: 18px;
    }
    QDialog QComboBox QAbstractItemView {
        color: #1E2A3A;
        background: #FFFFFF;
        border: 1px solid #CFD8DC;
        selection-background-color: #E3F2FD;
        selection-color: #1E2A3A;
    }
    QDialog QPushButton {
        background: #FFFFFF;
        color: #1E2A3A;
        border: 1px solid #B0BEC5;
        border-radius: 5px;
        padding: 6px 14px;
        font-size: 12px;
    }
    QDialog QPushButton:hover {
        background: #EEF2F7;
    }
    QDialog QPushButton:disabled {
        background: #E9EEF3;
        color: #90A4AE;
        border-color: #CFD8DC;
    }
    QMenu {
        background: #FFFFFF;
        color: #1E2A3A;
        border: 1px solid #CFD8DC;
        padding: 4px;
    }
    QMenu::item {
        padding: 6px 18px;
    }
    QMenu::item:selected {
        background: #E3F2FD;
        color: #1E2A3A;
    }
"""

_SPIN_STYLE = (
    "QDoubleSpinBox{border:1px solid #B0BEC5;border-radius:4px;"
    "padding:0 4px;font-size:12px;color:#1E2A3A;background:#FFFFFF;}"
)


# ---------------------------------------------------------------------------
# Worker: fetch exchange rates in background
# ---------------------------------------------------------------------------
class RateFetchWorker(QThread):
    done = Signal(bool)

    def __init__(self, currency_service, parent=None):
        super().__init__(parent)
        self._svc = currency_service

    def run(self):
        ok = self._svc.fetch_rates()
        self.done.emit(ok)


# ---------------------------------------------------------------------------
# Add-charge dialog
# ---------------------------------------------------------------------------
class _AddChargeDialog(QDialog):
    def __init__(self, mode: str = "air", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Charge Row")
        self.setMinimumWidth(340)
        self.setStyleSheet(_POPUP_STYLE)
        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 12)

        self._bucket = QComboBox()
        buckets = {"fcl": FCL_BUCKETS, "lcl": LCL_BUCKETS}.get(mode, AIR_IMPORT_BUCKETS)
        self._bucket.addItems(buckets)
        layout.addRow("Bucket:", self._bucket)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Fuel Surcharge")
        layout.addRow("Charge Name:", self._name)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_values(self) -> tuple[str, str]:
        return self._bucket.currentText(), self._name.text().strip()


# ---------------------------------------------------------------------------
# Custom Exchange Rate dialog
# ---------------------------------------------------------------------------
class CustomRateDialog(QDialog):
    """Let the user override live exchange rates per currency."""

    def __init__(self, live_rates: dict, currencies: list,
                 current_custom: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Exchange Rates")
        self.setMinimumWidth(480)
        self.setModal(True)
        self.setStyleSheet(_POPUP_STYLE)

        self._inputs: dict[str, QDoubleSpinBox] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        title = QLabel("Custom Exchange Rates")
        title.setStyleSheet("font-size:14px;font-weight:700;color:#1E2A3A;")
        layout.addWidget(title)

        desc = QLabel(
            "Enter how many units of each currency equal 1 USD. "
            "Leave a field at 0 (shown as 'use live') to fall back to the fetched rate."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:12px;color:#607080;")
        layout.addWidget(desc)

        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["Currency", "Live  (1 USD = …)", "Custom  (1 USD = …)"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionMode(QTableWidget.NoSelection)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        tbl.setStyleSheet("""
            QTableWidget{border:1px solid #DCE3EA;border-radius:4px;font-size:12px;color:#1E2A3A;}
            QTableWidget::item{padding:4px 10px;color:#1E2A3A;}
            QHeaderView::section{background:#EEF2F7;color:#607080;font-size:11px;
                font-weight:700;padding:5px 10px;border:none;border-bottom:1px solid #DCE3EA;}
        """)

        tbl.setRowCount(len(currencies))
        for r, curr in enumerate(currencies):
            tbl.setRowHeight(r, 36)

            curr_item = QTableWidgetItem(curr)
            f = curr_item.font(); f.setBold(True); curr_item.setFont(f)
            tbl.setItem(r, 0, curr_item)

            live_rate = live_rates.get(curr, 1.0)
            live_str = f"{live_rate:,.4f}".rstrip("0").rstrip(".")
            live_item = QTableWidgetItem(live_str)
            live_item.setForeground(QBrush(QColor("#607080")))
            live_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tbl.setItem(r, 1, live_item)

            spin = QDoubleSpinBox()
            spin.setRange(0, 9_999_999)
            spin.setDecimals(4)
            spin.setSpecialValueText("  use live")
            spin.setValue(current_custom.get(curr, 0.0))
            spin.setStyleSheet(_SPIN_STYLE)
            spin.setFrame(False)
            tbl.setCellWidget(r, 2, spin)
            self._inputs[curr] = spin

        tbl.setFixedHeight(min(len(currencies) * 36 + 38, 320))
        layout.addWidget(tbl)

        btn_row = QHBoxLayout()

        reset_btn = QPushButton("Reset All to Live")
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Rates")
        apply_btn.setStyleSheet(
            "QPushButton{background:#1976D2;color:white;border:none;"
            "border-radius:5px;padding:6px 18px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#1565C0;}"
        )
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

    def _reset_all(self):
        for spin in self._inputs.values():
            spin.setValue(0.0)

    def get_custom_rates(self) -> dict:
        """Return {currency: rate} for every currency where user entered a non-zero value."""
        return {
            curr: spin.value()
            for curr, spin in self._inputs.items()
            if spin.value() > 0
        }
