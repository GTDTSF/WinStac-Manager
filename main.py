# main.py
import sys
import qdarktheme
import win32gui

import win_api
import ui_widgets
from logger import logger
from PySide6.QtCore import QSize, QTimer
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QListWidget, QPushButton, QLabel, QListWidgetItem,
                               QApplication)

from rank_engine import WindowRankEngine
from auto_monitor import WindowWatcher


class WindowManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("窗口重排器")
        self.resize(800, 500)

        # 初始化界面
        self._init_ui()

        # 鼠标监控
        self.watcher = WindowWatcher()
        self.watcher.start()

        # 连接操作信号
        self._init_connections()

        # 数据管理
        self.engine = WindowRankEngine()

        # 第一次加载数据
        self.refresh_window_list()

        # 定时刷新左侧列表
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh_window_list)
        self.refresh_timer.start()

        # 定时刷新左侧列表
        self.maintenance_timer = QTimer(self)
        self.maintenance_timer.setInterval(1000)
        self.maintenance_timer.timeout.connect(self.auto_clean_targets)
        self.maintenance_timer.start()

    # === 初始化界面 === #
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 左侧加载列表
        left_layout = QVBoxLayout()
        self.source_list_widget = QListWidget()  # 重命名
        self.source_list_widget.setIconSize(QSize(24, 24))
        self.btn_refresh = QPushButton("刷新列表")

        left_layout.addWidget(QLabel("当前活动窗口"))
        left_layout.addWidget(self.source_list_widget)
        left_layout.addWidget(self.btn_refresh)

        # 右侧重排列表
        right_layout = QVBoxLayout()
        self.target_list_widget = QListWidget()
        self.target_list_widget.setIconSize(QSize(24, 24))
        # self.target_list_widget.setDragEnabled(True)
        # self.target_list_widget.setAcceptDrops(True)
        # self.target_list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        # self.target_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)

        sort_btn_layout = QHBoxLayout()
        self.btn_up = QPushButton("▲ 上移")
        self.btn_down = QPushButton("▼ 下移")
        sort_btn_layout.addWidget(self.btn_up)
        sort_btn_layout.addWidget(self.btn_down)

        self.btn_apply = QPushButton("立即执行重排")
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")

        right_layout.addWidget(QLabel("排序层级"))
        right_layout.addWidget(self.target_list_widget)
        right_layout.addLayout(sort_btn_layout)
        right_layout.addWidget(self.btn_apply)
        right_layout.addWidget(self.status_label)

        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=1)

    # === 绑定信号 === #
    def _init_connections(self):
        # 双击
        self.source_list_widget.itemDoubleClicked.connect(self.add_target)
        self.target_list_widget.itemDoubleClicked.connect(self.remove_target)
        # 移动按钮
        self.btn_up.clicked.connect(self.move_item_up)
        self.btn_down.clicked.connect(self.move_item_down)
        # 重排
        self.btn_refresh.clicked.connect(self.refresh_window_list)
        self.btn_apply.clicked.connect(self.execute_reorder)

        # 鼠标监控重排
        self.watcher.request_rearrange.connect(self._scan_and_reorder_delay)
        self.watcher.status_changed.connect(self.update_status)

    # === 刷新源窗口列表 === #
    def refresh_window_list(self):
        current_windows = win_api.get_all_windows()

        current_hwnds = {hwnd for hwnd, title in current_windows if int(self.winId()) != hwnd}

        for i in range(self.source_list_widget.count() - 1, -1, -1):
            item = self.source_list_widget.item(i)
            widget = self.source_list_widget.itemWidget(item)
            if widget.item_data.hwnd not in current_hwnds:
                self.source_list_widget.takeItem(i)

                win_api.clear_icon_cache(widget.item_data.hwnd)

                hwnd = widget.item_data.hwnd
                title = widget.item_data.title

                logger.info(f"[列表同步] 移除已关闭窗口: [{title}] (HWND: {hwnd})")

        existing_hwnds = set()
        for i in range(self.source_list_widget.count()):
            item = self.source_list_widget.item(i)
            widget = self.source_list_widget.itemWidget(item)
            existing_hwnds.add(widget.item_data.hwnd)

        # logger.debug("=== 开始刷新窗口列表 ===")
        # self.source_list_widget.clear()
        # windows = win_api.get_all_windows()
        # logger.info(f"成功获取到 {len(windows)} 个窗口")
        for hwnd, title in current_windows:
            if hwnd == int(self.winId()): continue

            if hwnd not in existing_hwnds:
                logger.info(f"[列表同步] 发现新窗口: [{title}] (HWND: {hwnd})")
                item_data = ui_widgets.ItemData(hwnd=hwnd, title=title)

                list_item = QListWidgetItem()
                widget = ui_widgets.SourceItemWidget(item_data=item_data)

                list_item.setSizeHint(widget.sizeHint())

                self.source_list_widget.addItem(list_item)
                self.source_list_widget.setItemWidget(list_item, widget)

                logger.debug(f"成功添加窗口：句柄={hwnd}, 标题={title}")

    # === 增加、移除管理窗口 === #
    def add_target(self, item):

        widget = self.source_list_widget.itemWidget(item)
        item_data = widget.item_data
        if self.engine.add_window(item_data=item_data):
            logger.info(f"成功添加窗口：句柄={item_data.hwnd}, 标题={item_data.title}")
            self.refresh_target_ui()

    def remove_target(self, item):
        widget = self.target_list_widget.itemWidget(item)
        item_data = widget.item_data
        if self.engine.remove_window(item_data=item_data):
            logger.info(f"成功移除管理窗口：句柄={item_data.hwnd}, 标题={item_data.title}")
            self.refresh_target_ui()

    def _scan_and_reorder_delay(self):
        QTimer.singleShot(10, self._scan_and_reorder)

    def _scan_and_reorder(self):
        self._scan_for_child_windows()
        self.execute_reorder()

    def _scan_for_child_windows(self):
        current_windows = win_api.get_all_windows(filter=False)
        current_hwnds_set = {hwnd for hwnd, title in current_windows}

        if hasattr(self, "known_hwnds"):
            new_hwnds = current_hwnds_set - self.known_hwnds
        else:
            new_hwnds = current_hwnds_set

        self.known_hwnds = current_hwnds_set

        if not new_hwnds:
            return

        targets = self.engine.targets
        if not targets:
            return

        # 封装函数检测
        for new_hwnd, new_title in current_windows:
            if new_hwnd not in new_hwnds:
                continue

            for target in targets:
                if win_api.is_son_window(target.hwnd, new_hwnd):
                    self.engine.insert_derived_window(new_hwnd, new_title, target.hwnd)
                    break

        # 普通pid检测
        # managed_pids = {}
        # for target in targets:
        #     pid = win_api.get_window_pid(target.hwnd)
        #     if pid:
        #         managed_pids[pid] = target.hwnd

        # for hwnd, title in current_windows:
        #     if hwnd in new_hwnds:
        #         new_pid = win_api.get_window_pid(hwnd)
        #
        #         if new_pid in managed_pids:
        #             parent_hwnd = managed_pids[new_pid]
        #             self.engine.insert_derived_window(hwnd, title, parent_hwnd)

        # self.execute_reorder()

    # === 上移、下移管理窗口 === #
    def move_item_up(self):
        selected_item = self.target_list_widget.selectedItems()
        if not selected_item:  # 无选中项直接返回
            return

        current_row = self.target_list_widget.row(selected_item[0])

        widget = self.target_list_widget.itemWidget(selected_item[0])
        item_data = widget.item_data
        if self.engine.move_item(item_data=item_data, direction='up'):
            logger.info(f"成功上移管理窗口：句柄={item_data.hwnd}, 标题={item_data.title}")
            self.refresh_target_ui()

            new_row = max(current_row - 1, 0)
            self.target_list_widget.setCurrentRow(new_row)

    def move_item_down(self):
        selected_item = self.target_list_widget.selectedItems()
        if not selected_item:  # 无选中项直接返回
            return

        current_row = self.target_list_widget.row(selected_item[0])

        widget = self.target_list_widget.itemWidget(selected_item[0])
        item_data = widget.item_data
        if self.engine.move_item(item_data=item_data, direction='down'):
            logger.info(f"成功下移管理窗口：句柄={item_data.hwnd}, 标题={item_data.title}")
            self.refresh_target_ui()

            new_row = min(current_row + 1, self.target_list_widget.count() - 1)
            self.target_list_widget.setCurrentRow(new_row)

    # === 管理窗口界面 === #
    def auto_clean_targets(self):
        if self.engine.clean_invalid_windows():
            self.refresh_target_ui()

    def refresh_target_ui(self):
        self.target_list_widget.clear()

        self.watcher.update_monitored_hwnds(self.engine.targets)

        item_data_list = self.engine.targets
        for item_data in item_data_list:

            if int(self.winId()) == item_data.hwnd:
                continue

            if item_data.window_type == 'TOOL':
                continue

            list_item = QListWidgetItem()
            widget = ui_widgets.TargetItemWidget(item_data=item_data)

            list_item.setSizeHint(widget.sizeHint())

            self.target_list_widget.addItem(list_item)
            self.target_list_widget.setItemWidget(list_item, widget)

    # === 执行重排 === #
    def execute_reorder(self):
        self.engine.execute_reorder()
        self.refresh_target_ui()

    # === 状态栏 === #
    def update_status(self, text, style):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(style)

    # === 窗口关闭事件 === #
    def closeEvent(self, event):
        self.watcher.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    try:
        win32gui.SetProcessDPIAware()
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("auto")

    window = WindowManager()
    window.show()

    sys.exit(app.exec())
