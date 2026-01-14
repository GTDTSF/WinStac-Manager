# rank_engine.py
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Set

import win32con
import win32gui
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

        rank = 1
        if self._targets:
            last_target = self._targets[-1]
            rank = last_target.rank + 1
        item_data.rank = rank

        self._targets.append(item_data)
        return True

    def insert_derived_window(self, child_hwnd, child_title, parent_hwnd):
        if any(target.hwnd == child_hwnd for target in self._targets):
            return False

        parent_idx = -1
        parent_rank = 1
        for i, target in enumerate(self._targets):
            if target.hwnd == parent_hwnd:
                parent_idx = i
                parent_rank = target.rank
                break

        new_item = ItemData(child_hwnd, child_title, rank=parent_rank, window_type='TOOL')
        self._targets.insert(parent_idx, new_item)
        logger.info(f"挂载工具窗口: [{child_title}] -> [{self._targets[parent_idx].title}]")
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
        if not self._targets:
            return False

        pre_hwnd = None

        for target in self._targets:
            title = target.title
            # 1. 基础存活检查
            if not win32gui.IsWindow(target.hwnd):
                continue

            # 2. 获取当前可见性
            is_visible = win32gui.IsWindowVisible(target.hwnd)
            # === 核心逻辑：工具窗口休眠管理 === #
            if target.window_type == 'TOOL':
                # 如果工具窗口隐藏了：跳过。
                if not is_visible:
                    continue

                # 如果是可见的：参与排序，但不强制发送 Show 指令
                force_show = False

            # === 普通窗口逻辑 === #
            else:
                # 如果主窗口最小化或隐藏，跳过排序
                if win_api.is_minimized(target.hwnd) or not is_visible:
                    continue
                force_show = True

            # === 执行线性排序 === #
            if pre_hwnd is None:
                logger.info(f"  -> 置顶: {title}")
                win_api.set_z_order(target.hwnd, win32con.HWND_TOPMOST, force_show=force_show)
                win_api.set_z_order(target.hwnd, win32con.HWND_NOTOPMOST, force_show=force_show)
            else:
                logger.info(f"  -> 跟随：{title}")
                win_api.set_z_order(target.hwnd, pre_hwnd, force_show=force_show)

            pre_hwnd = target.hwnd
        logger.info(f"  - 结束")
        return True

    # === 检测窗口存活情况 ===#
    def clean_invalid_windows(self):
        cleaned = False
        for target in list(self._targets):
            if not win32gui.IsWindow(target.hwnd):
                self.remove_window(target)
                cleaned = True
        return cleaned

