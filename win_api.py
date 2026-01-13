import win32gui, win32con, win32process
import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

dwmapi = ctypes.WinDLL('dwmapi')
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]


# === 获取句柄、窗口名称 === #
def is_window_cloaked(hwnd: int):
    cloaked = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return hr == 0 and cloaked.value != 0


def is_real_window(hwnd: int):
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

    # 过滤工具窗口 (ToolWindow)
    # 这种窗口通常用于浮动工具栏，不会出现在 Alt+Tab 或任务栏中、案例：微信表情框
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False

    return True


def get_all_windows():
    """获取所有真实可见窗口的 (hwnd, title)"""
    windows = []

    def callback(hwnd, extra):
        if is_real_window(hwnd):
            title = win32gui.GetWindowText(hwnd)

            if title and title not in ["Program Manager", "窗口重排器"]:
                windows.append((hwnd, title))
        return True

    win32gui.EnumWindows(callback, None)
    return windows


# === 获取窗口图标 === #
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
    hicon = get_window_hicon(hwnd)
    if not hicon:
        return QPixmap()
    image = QImage.fromHICON(hicon)

    pixmap = QPixmap.fromImage(image)
    icon = pixmap.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return icon


# === 排序窗口 === #
def is_minimized(hwnd: int):
    """检查窗口是否最小化。"""
    return win32gui.IsIconic(hwnd) != 0


# === 排序窗口 === #
def set_z_order(hwnd, insert_after_hwnd):
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
            | win32con.SWP_SHOWWINDOW
    )

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


# === 检查窗口是否存活 === #
def is_window_valid(hwnd: int):
    return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)


if __name__ == '__main__':
    windows = get_all_windows()
    for window in windows:
        print(window)
