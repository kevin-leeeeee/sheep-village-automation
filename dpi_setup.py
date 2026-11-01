"""在 Tk、PyAutoGUI 等套件載入前，統一設定 Windows DPI 模式。"""
import ctypes
import sys


def configure_dpi():
    if sys.platform != 'win32':
        return
    try:
        # 延用敲狼與競技場的每螢幕 DPI 模式，保留原有實體座標系統。
        result = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if result == 0:
            return
        # 已由宿主或 manifest 設定時無法再改；不強制覆寫執行緒模式。
        current = ctypes.c_int()
        if ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(current)) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass
