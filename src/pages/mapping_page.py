from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QComboBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox,
)

from src.constants import CURRENCIES, UNITS_OF_MEASUREMENT, AIR_IMPORT_BUCKETS, FCL_BUCKETS, LCL_BUCKETS

_COMBO_STYLE = (
    "QComboBox{"
    "border:1px solid #CFD8DC;padding:2px 8px;font-size:12px;"
    "color:#1E2A3A;background:#FFFFFF;min-height:28px;}"
    "QComboBox:hover{border:1px solid #90CAF9;}"
    "QComboBox:focus{border:1px solid #1976D2;}"
    "QComboBox QAbstractItemView{"
    "color:#1E2A3A;background:#FFFFFF;border:1px solid #CFD8DC;"
    "selection-background-color:#E3F2FD;selection-color:#1E2A3A;font-size:12px;}"
)
_LINE_STYLE = (
    "QLineEdit{border:none;padding:3px 6px;font-size:12px;"
    "color:#1E2A3A;background:transparent;}"
    "QLineEdit:focus{border-bottom:2px solid #1976D2;}"
)
_TABLE_STYLE = """
    QTableWidget {
        border: 1px solid #DCE3EA;
        border-radius: 6px;
        gridline-color: #E8EDF2;
        background: #FFFFFF;
    }
    QTableWidget::item { padding: 0px; background: transparent; }
    QHeaderView::section {
        background: #EEF2F7;
        color: #607080;
        font-size: 11px;
        font-weight: 700;
        padding: 6px 10px;
        border: none;
        border-right: 1px solid #DCE3EA;
        border-bottom: 2px solid #B0BEC5;
    }
    QScrollBar:vertical {
        width: 8px; background: #F5F7FA; border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #B0BEC5; border-radius: 4px; min-height: 20px;
    }
"""


# ---------------------------------------------------------------------------
# Vendor charge table — no charge master, 4 hard-coded buckets
# ---------------------------------------------------------------------------
class VendorMappingTable(QWidget):
    HEADERS = ["Category (Bucket)", "Name of Charge", "Currency",
               "Rate", "Unit of Measurement", "Remarks", "Optional?", ""]

    def __init__(self, buckets: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._buckets = buckets if buckets is not None else AIR_IMPORT_BUCKETS
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setStyleSheet(_TABLE_STYLE)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.Stretch)
        hh.setSectionResizeMode(6, QHeaderView.Fixed)
        hh.setSectionResizeMode(7, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 75)
        self.table.setColumnWidth(3, 75)
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 36)

        root.addWidget(self.table, 1)

        add_btn = QPushButton("+ Add Row")
        add_btn.setFixedHeight(32)
        add_btn.setStyleSheet(
            "QPushButton{background:#F0F4F8;color:#1976D2;border:1px dashed #90A4AE;"
            "border-radius:5px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#E3F2FD;}"
        )
        add_btn.clicked.connect(self.add_empty_row)
        root.addWidget(add_btn)

    # ------------------------------------------------------------------
    def _make_combo(self, items: list[str], editable: bool = True) -> QComboBox:
        cb = QComboBox()
        cb.setEditable(editable)
        cb.setInsertPolicy(QComboBox.InsertPolicy.InsertAtTop)
        cb.setFrame(True)
        cb.addItems(items)
        if editable:
            cb.setCurrentIndex(-1)
            cb.lineEdit().setPlaceholderText("Select or type…")
        else:
            # show no initial selection
            cb.setCurrentIndex(-1)
        cb.setStyleSheet(_COMBO_STYLE)
        return cb

    def _make_opt_widget(self, checked: bool = False) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        cb = QCheckBox()
        cb.setChecked(checked)
        cb.setStyleSheet("QCheckBox::indicator{width:15px;height:15px;}")
        lay.addWidget(cb)
        return w

    def _make_line(self, placeholder: str = "") -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        le.setFrame(False)
        le.setStyleSheet(_LINE_STYLE)
        return le

    def add_row(self, data: dict | None = None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 38)

        cat_cb  = self._make_combo(self._buckets)
        name_le = self._make_line("Charge name…")
        cur_cb  = self._make_combo(CURRENCIES)
        cur_cb.setCurrentText("USD")
        rate_le = self._make_line("0.00")
        unit_cb = self._make_combo(UNITS_OF_MEASUREMENT, editable=False)
        rem_le  = self._make_line()

        if_applicable = bool(data.get("if_applicable", False)) if data else False
        opt_widget = self._make_opt_widget(if_applicable)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(30, 30)
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#90A4AE;"
            "border:none;font-size:13px;}"
            "QPushButton:hover{color:#E53935;}"
        )
        del_btn.clicked.connect(lambda _checked, b=del_btn: self._delete_row(b))

        if data:
            self._fill(cat_cb, name_le, cur_cb, unit_cb, rate_le, rem_le, data)

        self.table.setCellWidget(r, 0, cat_cb)
        self.table.setCellWidget(r, 1, name_le)
        self.table.setCellWidget(r, 2, cur_cb)
        self.table.setCellWidget(r, 3, rate_le)
        self.table.setCellWidget(r, 4, unit_cb)
        self.table.setCellWidget(r, 5, rem_le)
        self.table.setCellWidget(r, 6, opt_widget)
        self.table.setCellWidget(r, 7, del_btn)

    def add_empty_row(self):
        self.add_row(None)

    def load_data(self, charges: list[dict]):
        self.table.setRowCount(0)
        for charge in charges:
            self.add_row(charge)

    def get_all_data(self) -> list[dict]:
        result = []
        for r in range(self.table.rowCount()):
            cat_w  = self.table.cellWidget(r, 0)
            name_w = self.table.cellWidget(r, 1)
            cur_w  = self.table.cellWidget(r, 2)
            rate_w = self.table.cellWidget(r, 3)
            unit_w = self.table.cellWidget(r, 4)
            rem_w  = self.table.cellWidget(r, 5)
            opt_w  = self.table.cellWidget(r, 6)
            if not cat_w:
                continue
            cb = opt_w.findChild(QCheckBox) if opt_w else None
            if_applicable = cb.isChecked() if cb else False
            try:
                rate = float(rate_w.text()) if rate_w.text().strip() else 0.0
            except ValueError:
                rate = 0.0
            result.append({
                "category":            cat_w.currentText().strip(),
                "name_of_charge":      name_w.text().strip(),
                "currency":            cur_w.currentText().strip(),
                "unit_of_measurement": unit_w.currentText().strip(),
                "rate":                rate,
                "remarks":             rem_w.text().strip(),
                "if_applicable":       if_applicable,
            })
        return result

    # ------------------------------------------------------------------
    def _fill(self, cat_cb, name_le, cur_cb, unit_cb, rate_le, rem_le, data: dict):
        cat = data.get("category", "")
        if cat:
            cat_cb.setCurrentText(cat)

        name_le.setText(data.get("name_of_charge", ""))
        cur_cb.setCurrentText(data.get("currency") or "USD")

        unit = data.get("unit_of_measurement", "")
        if unit:
            unit_cb.setCurrentText(unit)

        rate = data.get("rate", 0)
        if rate:
            rate_le.setText(str(rate))

        remarks = data.get("remarks", "")
        if remarks:
            rem_le.setText(remarks)

    def _delete_row(self, del_btn: QPushButton):
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, 7) == del_btn:
                self.table.removeRow(r)
                break


# ---------------------------------------------------------------------------
# Mapping Page
# ---------------------------------------------------------------------------
class MappingPage(QWidget):
    def __init__(self, app_window, parent=None):
        super().__init__(parent)
        self.app = app_window
        self._tables: dict[str, VendorMappingTable] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 20)
        root.setSpacing(14)

        title = QLabel("Map Vendor Charges")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#1E2A3A;")
        root.addWidget(title)

        sub = QLabel(
            "Review and edit the auto-extracted charges for each vendor. "
            "Rates will be normalised to USD in the comparison table."
        )
        sub.setStyleSheet("font-size:13px; color:#607080;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane{border:1px solid #DCE3EA;border-radius:6px;background:#FFFFFF;}
            QTabBar::tab{padding:7px 18px;font-size:12px;color:#607080;
                         border:1px solid transparent;border-bottom:none;
                         background:#EEF2F7;margin-right:3px;border-radius:5px 5px 0 0;}
            QTabBar::tab:selected{color:#1976D2;font-weight:700;
                                   background:#FFFFFF;border-color:#DCE3EA;}
            QTabBar::tab:hover{background:#E3F2FD;}
        """)
        root.addWidget(self.tabs, 1)

        self._placeholder = QLabel(
            "No vendor files imported yet.\nGo back to Import Files to add quotes."
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size:14px; color:#90A4AE;")
        root.addWidget(self._placeholder)
        self._placeholder.setVisible(False)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#DCE3EA;")
        root.addWidget(sep)

        nav = QHBoxLayout()
        back_btn = QPushButton("← Back to Import")
        back_btn.setFixedHeight(36)
        back_btn.setStyleSheet(self._sec_btn())
        back_btn.clicked.connect(lambda: self.app.go_to_import())
        nav.addWidget(back_btn)
        # Preview imported mails
        preview_btn = QPushButton("Preview Imported Mails")
        preview_btn.setFixedHeight(36)
        preview_btn.setStyleSheet(self._sec_btn())
        preview_btn.clicked.connect(self._preview_imported)
        nav.addWidget(preview_btn)
        nav.addStretch()

        self.compare_btn = QPushButton("Build Comparison Table  →")
        self.compare_btn.setFixedHeight(36)
        self.compare_btn.setStyleSheet(self._pri_btn())
        self.compare_btn.clicked.connect(self._proceed)
        nav.addWidget(self.compare_btn)
        root.addLayout(nav)

    # ------------------------------------------------------------------
    def populate(self):
        self.tabs.clear()
        self._tables.clear()

        vendor_list = list(self.app.vendors.values())
        if not vendor_list:
            self._placeholder.setVisible(True)
            self.tabs.setVisible(False)
            return

        self._placeholder.setVisible(False)
        self.tabs.setVisible(True)

        for vd in vendor_list:
            if vd.quote_type == "fcl":
                buckets = FCL_BUCKETS
            elif vd.quote_type == "lcl":
                buckets = LCL_BUCKETS
            else:
                buckets = AIR_IMPORT_BUCKETS

            table = VendorMappingTable(buckets)
            table.load_data(vd.to_charge_dicts())
            self._tables[vd.uid] = table

            if vd.quote_type == "fcl" and vd.shipping_line:
                tab_label = f"{vd.vendor_name} [FCL · {vd.shipping_line}]"
            elif vd.quote_type == "fcl":
                tab_label = f"{vd.vendor_name} [FCL]"
            elif vd.quote_type == "lcl":
                tab_label = f"{vd.vendor_name} [LCL]"
            elif vd.airline:
                tab_label = f"{vd.vendor_name} [Air · {vd.airline}]"
            else:
                tab_label = f"{vd.vendor_name} [Air]"

            container = QWidget()
            container.setStyleSheet("background:#FFFFFF;")
            cl = QVBoxLayout(container)
            cl.setContentsMargins(12, 12, 12, 12)
            cl.addWidget(table)
            self.tabs.addTab(container, tab_label)

            tab_idx = self.tabs.count() - 1
            _mode_colors = {
                "fcl": QColor("#00796B"),
                "lcl": QColor("#2E7D32"),
                "air": QColor("#1565C0"),
            }
            self.tabs.tabBar().setTabTextColor(
                tab_idx, _mode_colors.get(vd.quote_type, QColor("#1E2A3A"))
            )

    def save_all(self):
        for vd in self.app.vendors.values():
            table = self._tables.get(vd.uid)
            if table:
                vd.set_charges_from_dicts(table.get_all_data())

    def _proceed(self):
        self.save_all()
        self.app.go_to_comparison()

    def _preview_imported(self):
        try:
            from src.pages.preview_mails import PreviewMailsDialog
        except Exception:
            QMessageBox.warning(self, "Unable to preview", "Preview component unavailable.")
            return
        dlg = PreviewMailsDialog(self.app, self)
        dlg.exec()

    @staticmethod
    def _pri_btn():
        return (
            "QPushButton{background:#1976D2;color:white;border:none;"
            "border-radius:6px;padding:0 18px;font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#1565C0;}"
        )

    @staticmethod
    def _sec_btn():
        return (
            "QPushButton{background:#FFFFFF;color:#1E2A3A;border:1px solid #90A4AE;"
            "border-radius:6px;padding:0 16px;font-size:13px;}"
            "QPushButton:hover{background:#F0F4F8;}"
        )
