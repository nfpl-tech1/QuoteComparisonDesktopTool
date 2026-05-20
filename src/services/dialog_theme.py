APP_DIALOG_STYLE = """
QMessageBox, QDialog, QInputDialog {
    background: #F8FAFC;
    color: #1E2A3A;
}
QMessageBox QLabel,
QDialog QLabel,
QInputDialog QLabel,
QMessageBox QWidget,
QDialog QWidget,
QInputDialog QWidget {
    color: #1E2A3A;
}
QMessageBox QLabel#qt_msgbox_label,
QMessageBox QLabel#qt_msgbox_informativelabel {
    color: #1E2A3A;
    font-size: 12px;
}
QMessageBox QPushButton,
QDialog QPushButton,
QInputDialog QPushButton {
    min-height: 30px;
    min-width: 84px;
    background: #FFFFFF;
    color: #1E2A3A;
    border: 1px solid #B0BEC5;
    border-radius: 6px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 600;
}
QMessageBox QPushButton:hover,
QDialog QPushButton:hover,
QInputDialog QPushButton:hover {
    background: #EEF2F7;
    border-color: #90A4AE;
}
QMessageBox QPushButton:pressed,
QDialog QPushButton:pressed,
QInputDialog QPushButton:pressed {
    background: #E3F2FD;
}
QMessageBox QPushButton:disabled,
QDialog QPushButton:disabled,
QInputDialog QPushButton:disabled {
    background: #E9EEF3;
    color: #90A4AE;
    border-color: #CFD8DC;
}
QMessageBox QLineEdit,
QDialog QLineEdit,
QInputDialog QLineEdit,
QMessageBox QComboBox,
QDialog QComboBox,
QInputDialog QComboBox,
QMessageBox QDoubleSpinBox,
QDialog QDoubleSpinBox,
QInputDialog QDoubleSpinBox,
QMessageBox QListWidget,
QDialog QListWidget,
QInputDialog QListWidget,
QMessageBox QPlainTextEdit,
QDialog QPlainTextEdit,
QInputDialog QPlainTextEdit,
QMessageBox QTextEdit,
QDialog QTextEdit,
QInputDialog QTextEdit {
    background: #FFFFFF;
    color: #1E2A3A;
    border: 1px solid #CFD8DC;
    border-radius: 6px;
    selection-background-color: #E3F2FD;
    selection-color: #1E2A3A;
}
QMessageBox QLineEdit,
QDialog QLineEdit,
QInputDialog QLineEdit,
QMessageBox QComboBox,
QDialog QComboBox,
QInputDialog QComboBox,
QMessageBox QDoubleSpinBox,
QDialog QDoubleSpinBox,
QInputDialog QDoubleSpinBox {
    min-height: 30px;
    padding: 0 10px;
    font-size: 12px;
}
QMessageBox QLineEdit:focus,
QDialog QLineEdit:focus,
QInputDialog QLineEdit:focus,
QMessageBox QComboBox:focus,
QDialog QComboBox:focus,
QInputDialog QComboBox:focus,
QMessageBox QDoubleSpinBox:focus,
QDialog QDoubleSpinBox:focus,
QInputDialog QDoubleSpinBox:focus {
    border: 1px solid #1976D2;
}
QMessageBox QComboBox::drop-down,
QDialog QComboBox::drop-down,
QInputDialog QComboBox::drop-down {
    border: none;
    width: 24px;
}
QMessageBox QMenu,
QDialog QMenu,
QInputDialog QMenu {
    background: #FFFFFF;
    color: #1E2A3A;
    border: 1px solid #CFD8DC;
}
QMessageBox QMenu::item:selected,
QDialog QMenu::item:selected,
QInputDialog QMenu::item:selected {
    background: #E3F2FD;
    color: #1E2A3A;
}
"""
