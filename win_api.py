import win32gui, win32con, win32process
import ctypes
from ctypes import wintypes
from logger import logger

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

dwmapi = ctypes.WinDLL('dwmapi')
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]

_icon_cache = {}

# === 获取句柄、窗口名称 === #
def is_window_cloaked(hwnd: int):
    cloaked = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return hr == 0 and cloaked.value != 0


# 暂时废弃
def is_real_window(hwnd: int, filter):
    # 过滤没有标题的窗口
    if win32gui.GetWindowTextLength(hwnd) == 0:
        return False
    # 过滤隐藏的窗口
    if not win32gui.IsWindowVisible(hwnd):
        return False
    # 过滤附属窗口
    if win32gui.GetWindow(hwnd, win32con.GW_OWNER) != 0:
        return False
    # 过滤被DWM遮蔽的窗口（如UWP挂起、其他虚拟桌面窗口）
    if is_window_cloaked(hwnd):
        return False

    if filter:
        # 过滤工具窗口 (ToolWindow)
        # 这种窗口通常用于浮动工具栏，不会出现在 Alt+Tab 或任务栏中、案例：微信表情框
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return False

    return True


def get_all_windows(filter=True):
    """获取所有真实可见窗口的 (hwnd, title)"""
    windows = []

    def callback(hwnd, extra):
        title = win32gui.GetWindowText(hwnd)
        if is_real_window(hwnd, filter):
            if title not in ["Program Manager", "窗口重排器"]:
                windows.append((hwnd, title))

        return True

    win32gui.EnumWindows(callback, None)
    return windows


# === 获取窗口图标 === #
def clear_icon_cache(hwnd):
    if hwnd in _icon_cache:
        del _icon_cache[hwnd]

def get_window_hicon(hwnd: int):
    """获取窗口图标句柄（依次尝试窗口小图标、大图标、类小图标、类大图标）"""
    hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
    if hicon != 0:
        return hicon

    hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
    if hicon != 0:
        return hicon

    # 3. 尝试窗口类的小图标
    hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICONSM)
    if hicon != 0:
        return hicon

    # 4. 尝试窗口类的大图标
    hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
    if hicon != 0:
        return hicon

    return None


def get_window_pixmap(hwnd: int, size: int = 24):
    """获取窗口图标并转换为QPixmap"""
    if hwnd in _icon_cache:
        return _icon_cache[hwnd]

    hicon = get_window_hicon(hwnd)
    if not hicon:
        return QPixmap()
    image = QImage.fromHICON(hicon)

    pixmap = QPixmap.fromImage(image)
    icon = pixmap.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    if not pixmap.isNull():
        _icon_cache[hwnd] = icon
    return icon


# === 排序窗口 === #
def is_minimized(hwnd: int):
    """检查窗口是否最小化。"""
    return win32gui.IsIconic(hwnd) != 0


# === 排序窗口 === #
def set_z_order(hwnd, insert_after_hwnd, force_show=True):
    """
    设置窗口的 Z 轴顺序 (Z-Order)。
    """
    # 组合标志位
    # SWP_NOMOVE: 不改变当前位置 (x, y)
    # SWP_NOSIZE: 不改变当前大小 (cx, cy)
    # SWP_NOACTIVATE: 不激活窗口
    # SWP_SHOWWINDOW: 显示窗口
    flags = (
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
    )
    if force_show:
        flags |= win32con.SWP_SHOWWINDOW
    else:
        pass

    win32gui.SetWindowPos(
        hwnd,  # 目标窗口句柄
        insert_after_hwnd,  # 在哪个窗口句柄之后
        0, 0, 0, 0,
        flags
    )


# === 获取指定坐标的窗口句柄 === #
def get_root_window_at(x, y):
    hwnd = win32gui.WindowFromPoint((x, y))
    if hwnd == 0:
        return None

    root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
    return root_hwnd


# === 判断有没有按下叉 === #
def get_window_rect(hwnd):
    """获取窗口的坐标 (left, top, right, bottom)"""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        return rect
    except Exception:
        return None


def is_click_on_close_button(hwnd: int, x: int, y: int):
    """
    通过坐标判断是否点击了右上角区域 (针对自绘标题栏软件)
    """
    rect = get_window_rect(hwnd)
    if not rect:
        return False

    left, top, right, bottom = rect
    width = right - left
    height = bottom - top

    # 计算相对坐标
    rel_x = x - left
    rel_y = y - top

    # === 判定区域设置 === #
    # 标题栏高度通常在 30~40 像素
    # 关闭按钮宽度通常在 45~50 像素
    # 我们设置一个稍微宽松的范围：右上角 60x40 的区域

    # 1. 必须在窗口顶部 40 像素内
    if rel_y < 0 or rel_y > 40:
        return False

    # 2. 必须在窗口最右侧 60 像素内
    if rel_x > (width - 60) and rel_x < width:
        return True

    return False


# === 获取窗口pid === #
def get_window_pid(hwnd: int):
    """获取窗口对应的进程ID"""
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid


# === 检查附属关系 === #
def is_son_window(parent_hwnd: int, target_hwnd: int):
    # --- 1. 检查 Win32 Owner 关系 (显式父子关系) ---
    try:
        owner = win32gui.GetWindow(target_hwnd, win32con.GW_OWNER)
        if owner == parent_hwnd:
            return True
    except Exception:
        # 窗口可能已关闭
        return False

    try:
        _, parent_pid = win32process.GetWindowThreadProcessId(parent_hwnd)
        _, target_pid = win32process.GetWindowThreadProcessId(target_hwnd)
    except Exception:
        return False

    if parent_pid != target_pid:
        return False

    try:
        # 获取样式
        style = win32gui.GetWindowLong(target_hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(target_hwnd, win32con.GWL_EXSTYLE)
        debug_title = win32gui.GetWindowText(target_hwnd)

        # [日志优化] 将标题和样式信息合并为一条日志，减少刷屏
        logger.info(f"[检测窗口] HWND: {target_hwnd} | 标题: '{debug_title}' | Style={hex(style)} | ExStyle={hex(ex_style)}")

    except Exception as e:
        # [日志优化] 使用 logger 记录异常
        logger.error(f"[检测窗口] HWND: {target_hwnd} 获取窗口样式失败: {e}")
        return False

    # 判定 A: 工具窗口 (ToolWindow)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        logger.info(f"  -> [结果: True] HWND: {target_hwnd} 判定为子窗口 (命中规则: WS_EX_TOOLWINDOW 工具窗口)")
        return True

    # 判定 B: 任务栏可见窗口 (AppWindow)
    if ex_style & win32con.WS_EX_APPWINDOW:
        logger.info(f"  -> [结果: False] HWND: {target_hwnd} 判定为独立窗口 (命中规则: WS_EX_APPWINDOW 强制任务栏显示)")
        return False

    # 判定 C: Popup 窗口 vs Overlapped 窗口
    if style & win32con.WS_POPUP:
        logger.info(f"  -> [结果: False] HWND: {target_hwnd} 判定为独立窗口 (命中规则: WS_POPUP 弹出式样式)")
        return False

    # 默认情况
    logger.info(f"  -> [结果: False] HWND: {target_hwnd} 判定为独立窗口 (未命中子窗口特征，推测为 WS_OVERLAPPED 标准窗口)")
    return False

if __name__ == '__main__':
    windows = get_all_windows()
    for window in windows:
        print(window)
