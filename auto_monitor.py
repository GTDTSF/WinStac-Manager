# auto_monitor.py
import ctypes
from ctypes import wintypes
from pynput import mouse
from PySide6.QtCore import QObject, QThread, Signal, QTimer
import win_api
from logger import logger


# === 鼠标监控 === #
class _MouseWatcher(QObject):
    """
    内部类：负责运行 pynput 监听器。
    """
    # 发送鼠标释放时的坐标
    released = Signal(int, int)

    def start_monitoring(self):
        self.listener = mouse.Listener(on_click=self.on_click)
        self.listener.start()

    def on_click(self, x, y, button, pressed):
        if button == mouse.Button.left and not pressed:
            self.released.emit(x, y)

    def stop_monitoring(self):
        if hasattr(self, 'listener'):
            self.listener.stop()


class WindowWatcher(QObject):
    """
    主控制器：
    1. 接收鼠标释放信号。
    2. 判断是否点击了“目标窗口”。
    3. 如果是，立即请求重排。
    """

    # 核心信号：请求执行重排
    request_rearrange = Signal()
    # 状态信号：(文本, 样式)
    status_changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        self._targets = []
        self.known_hwnds = set()
        # 配置后台线程
        self.thread = QThread()
        self.mouse_worker = _MouseWatcher()
        self.mouse_worker.moveToThread(self.thread)

        # 连接线程生命周期
        self.thread.started.connect(self.mouse_worker.start_monitoring)
        self.thread.finished.connect(self.mouse_worker.stop_monitoring)

        #
        self.mouse_worker.released.connect(self._handle_mouse_release)

    def start(self):
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self):
        """停止监控线程"""
        self.mouse_worker.stop_monitoring()
        self.thread.quit()
        self.thread.wait()

    def update_monitored_hwnds(self, item_data_list):
        self._targets = item_data_list

    def _handle_mouse_release(self, x, y):
        """
        处理鼠标释放事件（在主线程运行）
        """
        if not self._targets:
            return

        hwnd_clicked = win_api.get_root_window_at(x, y)
        if win_api.is_click_on_close_button(hwnd_clicked, x, y):
            self.status_changed.emit(f"检测到右上角点击 -> 忽略重排", "color: orange;")
            return

        hwnd_clicked = win_api.get_root_window_at(x, y)
        for target in self._targets:
            if hwnd_clicked == target.hwnd:
                self.status_changed.emit(f"捕捉操作：{hwnd_clicked} -> 立即重排", "color: green; font-weight: bold;")
                self.request_rearrange.emit()