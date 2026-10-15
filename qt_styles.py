from typing import Final

STYLE: Final = """
QWidget { color: #ECEEF2; background: transparent; font-size: 12px; }
QLabel#title { font-size: 15px; font-weight: 700; }
QLabel#muted { color: #B0B3BC; font-size: 10px; }
QLineEdit { background: rgba(160,189,219,20); border: 1px solid rgba(160,189,219,35);
    border-radius: 12px; padding: 9px 12px; selection-background-color: #293D53; }
QLineEdit:focus { border-color: rgba(160,189,219,110); }
QPushButton { border: none; border-radius: 8px; padding: 4px 7px; }
QPushButton:hover { background: rgba(160,189,219,30); }
QPushButton:pressed { background: rgba(160,189,219,50); }
QPushButton:disabled { color: #555966; }
QPushButton#star { color: #E6A16A; font-size: 17px; }
QFrame#row { background: rgba(160,189,219,12); border-radius: 10px; }
QFrame#selected { background: rgba(160,189,219,35); border-radius: 10px; }
QComboBox { background: rgba(160,189,219,20); border: none; border-radius: 9px;
    padding: 6px 10px; font-weight: 700; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView, QMenu { background: #192334; color: #ECEEF2;
    border: 1px solid #293D53; selection-background-color: #293D53; padding: 5px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: #293D53; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 4px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: #465267; border-radius: 2px; min-height: 18px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QDialog, QMessageBox { background: #10131E; }
"""
