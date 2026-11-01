"""各工具共用的視窗位置記憶；由原有設定儲存流程寫入檔案。"""
import json
import tkinter as tk

import win32api


def fit_geometry(saved, work_areas, minimum=(380, 450)):
    x, y, width, height = (saved[key] for key in ('x', 'y', 'width', 'height'))
    if any(type(value) is not int for value in (x, y, width, height)) or width <= 0 or height <= 0:
        raise ValueError('Invalid window geometry')
    if not work_areas:
        raise ValueError('No monitor work areas')

    def rank(area):
        left, top, right, bottom = area
        overlap = max(0, min(x + width, right) - max(x, left)) * max(0, min(y + height, bottom) - max(y, top))
        distance = (x + width / 2 - (left + right) / 2) ** 2 + (y + height / 2 - (top + bottom) / 2) ** 2
        return overlap, -distance

    left, top, right, bottom = max(work_areas, key=rank)
    width = min(max(minimum[0], width), max(1, right - left - 24))
    height = min(max(minimum[1], height), max(1, bottom - top - 48))
    return dict(x=max(left + 12, min(x, right - width - 12)),
                y=max(top + 12, min(y, bottom - height - 36)),
                width=width, height=height)


class WindowState:
    def __init__(self, root, config_path, minimum=(380, 450)):
        self.root = root
        self.normal_geometry = None
        try:
            with open(config_path, encoding='utf-8') as stream:
                saved = json.load(stream).get('window_geometry')
            if isinstance(saved, dict):
                areas = [win32api.GetMonitorInfo(monitor)['Work']
                         for monitor, _, _ in win32api.EnumDisplayMonitors()]
                geometry = fit_geometry(saved, areas, minimum)
                root.minsize(min(minimum[0], geometry['width']), min(minimum[1], geometry['height']))
                root.geometry('{width}x{height}+{x}+{y}'.format(**geometry))
                self.normal_geometry = geometry
                if saved.get('maximized') is True:
                    root.after_idle(lambda: root.state('zoomed'))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, tk.TclError):
            # 無舊設定時沿用程式預設位置。
            pass
        root.bind('<Configure>', self.remember, add='+')

    def remember(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        if self.root.state() == 'normal':
            width, height = self.root.winfo_width(), self.root.winfo_height()
            if width > 1 and height > 1:
                self.normal_geometry = dict(x=self.root.winfo_x(), y=self.root.winfo_y(),
                                            width=width, height=height)

    def snapshot(self):
        self.remember()
        if self.normal_geometry:
            return dict(self.normal_geometry, maximized=self.root.state() == 'zoomed')
        return None
