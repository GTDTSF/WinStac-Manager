# auto_monitor.py
import ctypes
from ctypes import wintypes

import win32gui
from pynput import mouse, keyboard
from PySide6.QtCore import QObject, QThread, Signal, QTimer
import win_api
from logger import logger


# === 键盘监控 === #
class _KeyboardWatcher(QObject):
    """
    内部类：负责监听键盘事件 (用于捕获输入法上屏操作)
    """
    # 发送请求重排信号
    input_committed = Signal()

    def start_monitoring(self):
        # 监听释放事件即可
        self.listener = keyboard.Listener(on_release=self.on_release)
        self.listener.start()

    def stop_monitoring(self):
        if hasattr(self, 'listener'):
            self.listener.stop()

    def on_release(self, key):
        """
        核心逻辑：过滤按键。
        只有按下“确认类”按键（空格、回车、数字键）时，才触发检查。
        """
        try:
            should_trigger = False

            # 1. 检查特殊键 (空格, 回车)
            if key == keyboard.Key.space or key == keyboard.Key.enter:
                should_trigger = True

            # 2. 检查字符键 (1-9)
            elif hasattr(key, 'char') and key.char:
                if key.char in '123456789':
                    should_trigger = True

            if should_trigger:
                self.input_committed.emit()

        except Exception:
            pass


# === 鼠标监控 === #
class _MouseWatcher(QObject):
    """
    内部类：负责运行 pynput 监听器。
    """
    # 发送鼠标释放时的坐标
    left_released = Signal(int, int)
    right_released = Signal(int, int)
    any_clicked = Signal()
    def start_monitoring(self):
        self.listener = mouse.Listener(on_click=self.on_click)
        self.listener.start()

    def on_click(self, x, y, button, pressed):
        if button == mouse.Button.left and not pressed:
            self.left_released.emit(x, y)
        if button == mouse.Button.right and not pressed:
            self.left_released.emit(x, y)

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

        # 2. 键盘工作者
        self.keyboard_worker = _KeyboardWatcher()
        self.keyboard_worker.moveToThread(self.thread)

        # 连接线程生命周期
        self.thread.started.connect(self.mouse_worker.start_monitoring)
        self.thread.started.connect(self.keyboard_worker.start_monitoring)
        self.thread.finished.connect(self.mouse_worker.stop_monitoring)
        self.thread.finished.connect(self.keyboard_worker.stop_monitoring)

        # 绑定鼠标释放信号
        self.mouse_worker.left_released.connect(self._handle_mouse_release)
        self.mouse_worker.right_released.connect(self._handle_mouse_release)

        # 绑定键盘输入信号
        self.keyboard_worker.input_committed.connect(self._handle_input_action)
        self.mouse_worker.any_clicked.connect(self._handle_input_action)

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

    # === 处理鼠标释放/操作完成 === #
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

    # === 处理输入法/操作完成 === #
    def _handle_input_action(self):
        """
        当检测到 1-9, Space, Enter 或 鼠标点击 时触发。
        逻辑：
        1. 检查当前活动窗口是谁。
        2. 如果活动窗口在我们的管理列表中，且不是 Rank 1（即正在操作底层窗口）。
        3. 延迟一小会儿（等输入法窗口消失），然后执行重排。
        """
        if not self._targets:
            return

        # 获取前台窗口
        foreground_hwnd = win32gui.GetForegroundWindow()

        # 检查是否是受管窗口
        is_managed = False
        target_rank = 0

        for target in self._targets:
            if target.hwnd == foreground_hwnd:
                is_managed = True
                target_rank = target.rank
                break

        # 只有当：
        # 1. 活动窗口是我们管理的
        # 2. 活动窗口不是 Rank 1 (即我们在操作下面的窗口，导致它浮上来了)
        # 才触发重排
        if is_managed and target_rank > 1:
            # logger.debug(f"捕捉到输入操作 (Rank {target_rank}) -> 请求重排")
            self.request_rearrange.emit()
