# ui_widgets.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QListWidgetItem
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, Signal, QObject
import win_api


class ItemData(QObject):
    rank_updated = Signal(int)
    title_updated = Signal(str)

    def __init__(self, hwnd: int, title: str, rank: int = None, window_type: str = 'STANDARD'):
        super().__init__()
        self._hwnd = hwnd
        self._title = title
        self._rank = rank
        self._window_type = window_type

    @property
    def hwnd(self):
        return self._hwnd

    @property
    def title(self):
        return self._title

    @property
    def rank(self):
        return self._rank

    @rank.setter
    def rank(self, value: int):
        if self._rank != value:
            self._rank = value
            self.rank_updated.emit(value)

    @property
    def window_type(self):
        return self._window_type


class SourceItemWidget(QWidget):
    """左侧列表的自定义控件：[图标] [标题]"""

    def __init__(self, item_data: ItemData, parent=None):
        super().__init__(parent)

        self._item_data = item_data

        self._setup_ui()

    def _setup_ui(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(5)

        icon_lable = QLabel()
        pixmap = win_api.get_window_pixmap(self._item_data.hwnd)
        if not pixmap.isNull():
            icon_lable.setPixmap(pixmap)

        text_label = QLabel(self._item_data.title)
        text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        h_layout.addWidget(icon_lable)
        h_layout.addWidget(text_label)

    @property
    def item_data(self):
        return self._item_data


class TargetItemWidget(QWidget):
    """右侧列表的自定义控件：[序号] [图标] [标题]"""
    def __init__(self, item_data: ItemData,  parent=None):
        super().__init__(parent)

        self._item_data = item_data

        self._setup_ui()

    def _setup_ui(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(5)

        rank_edit = QLineEdit(str(self._item_data.rank))

        rank_edit.setReadOnly(True)
        rank_edit.setFocusPolicy(Qt.NoFocus)
        rank_edit.setAlignment(Qt.AlignCenter)
        fm = rank_edit.fontMetrics()
        char_width = fm.horizontalAdvanceChar("0")
        rank_edit.setFixedWidth(char_width + 20)

        icon_lable = QLabel()
        pixmap = win_api.get_window_pixmap(self._item_data.hwnd)
        if not pixmap.isNull():
            icon_lable.setPixmap(pixmap)

        text_label = QLabel(self._item_data.title)
        text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        h_layout.addWidget(rank_edit)
        h_layout.addWidget(icon_lable)
        h_layout.addWidget(text_label)

    @property
    def item_data(self):
        return self._item_data
