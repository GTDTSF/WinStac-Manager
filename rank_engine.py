# rank_engine.py
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Set

import win32con
from PySide6.QtCore import QTimer

import win_api
from ui_widgets import ItemData
from logger import logger


class WindowRankEngine:
    def __init__(self):
        self._targets = []

    @property
    def targets(self):
        return self._targets

    # === 添加窗口 === #
    def add_window(self, item_data: ItemData):
        """添加窗口，如果已存在则返回 False"""
        if any(target.hwnd == item_data.hwnd for target in self._targets):
            return False

        self._targets.append(item_data)
        return True

    # === 移除窗口 === #
    def remove_window(self, item_data: ItemData):
        remove_hwnd = item_data.hwnd
        self._targets = [t for t in self._targets if t.hwnd != remove_hwnd]
        return True

    # === 移动窗口 === #
    def move_item(self, item_data: ItemData, direction: str):
        if direction not in ('up', 'down'):
            return False

        target_idx = -1
        for idx, target in enumerate(self._targets):
            if target.hwnd == item_data.hwnd:
                target_idx = idx
                break

        if direction == 'up':
            if target_idx > 0:
                new_idx = target_idx - 1
            else:
                return False
        elif direction == 'down':
            if target_idx < len(self._targets) - 1:
                new_idx = target_idx + 1
            else:
                return False

        self._targets[target_idx], self._targets[new_idx] = self._targets[new_idx], self._targets[target_idx]
        return True

    # === 执行重排 === #
    def execute_reorder(self):
        logger.info("=== 开始执行窗口重排序列 ===")
        if len(self._targets) == 0:
            return False

        pre_hwnd = None
        found_top = None

        for target in self._targets:
            hwnd = target.hwnd
            title = target.title

            if win_api.is_minimized(hwnd):
                logger.info(f"  X 跳过：{title}处于最小化状态， ")
                continue

            if not found_top:
                logger.info(f"  -> 置顶: {title}")

                # 强行置顶
                win_api.set_z_order(hwnd, win32con.HWND_TOPMOST)
                win_api.set_z_order(hwnd, win32con.HWND_NOTOPMOST)

                found_top = True
                pre_hwnd = hwnd
            else:
                logger.info(f"  -> 跟随：{title}")
                win_api.set_z_order(hwnd, pre_hwnd)
                pre_hwnd = hwnd

        logger.info(f"  - 结束")
        return True

    # === 检测窗口存活情况 ===#
    def clean_invalid_windows(self):

        cleaned = False

        for target in self._targets:
            hwnd = target.hwnd
            if not win_api.is_window_valid(hwnd):
                self.remove_window(target)
                cleaned = True
        return cleaned
