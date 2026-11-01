"""視窗記憶測試：使用暫存設定，不啟動監聽器或操作遊戲。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from window_state import WindowState, fit_geometry


class WindowStateTests(unittest.TestCase):
    def test_negative_monitor_position_preserved(self):
        saved = dict(x=-1800, y=100, width=450, height=760)
        self.assertEqual(fit_geometry(saved, [(-1920, 0, 0, 1040)]), saved)

    def test_missing_monitor_moves_window_into_visible_area(self):
        result = fit_geometry(dict(x=-1800, y=1800, width=2400, height=1600), [(0, 0, 1920, 1040)])
        self.assertGreaterEqual(result['x'], 0)
        self.assertGreaterEqual(result['y'], 0)
        self.assertLessEqual(result['x'] + result['width'], 1920)
        self.assertLessEqual(result['y'] + result['height'], 1040)

    def test_maximized_window_keeps_normal_size(self):
        state = WindowState.__new__(WindowState)
        state.normal_geometry = dict(x=120, y=100, width=450, height=760)
        state.root = SimpleNamespace(state=lambda: 'zoomed')
        self.assertEqual(state.snapshot(), dict(state.normal_geometry, maximized=True))

    def test_both_apps_save_and_restore_geometry(self):
        import tkinter as tk
        import wolf_mine_speedup as wolf
        import arena_challenge as arena

        saved = dict(x=120, y=100, width=680, height=820, maximized=False)
        for module, cls in ((wolf, wolf.GUI), (arena, arena.ArenaGUI)):
            with self.subTest(app=module.__name__), TemporaryDirectory() as directory:
                config = Path(directory) / 'settings.json'
                config.write_text(json.dumps(dict(window_geometry=saved, show_guide=False)), encoding='utf-8')
                root = tk.Tk()
                root.withdraw()
                try:
                    with patch.object(module, 'CONFIG_FILE', str(config)), \
                         patch.object(cls, 'setup_global_hotkeys'), \
                         patch('window_state.win32api.EnumDisplayMonitors', return_value=[(1, None, None)]), \
                         patch('window_state.win32api.GetMonitorInfo', return_value={'Work': (0, 0, 1920, 1080)}):
                        app = cls(root)
                        if module is wolf:
                            app.coordinates = [(1, 1), (2, 2)]
                            app.next_page_coord = (2774, 763)
                            app.update_coords()
                            self.assertEqual(app.coord_status_labels['friends'].cget('text'), '2 位好友')
                            self.assertEqual(app.coord_status_labels['next'].cget('text'), '(2774, 763)')
                            self.assertEqual(app.coord_status_labels['mine'].cget('text'), '未設定')
                        root.update_idletasks()
                        self.assertEqual(len(app.settings_tabs.tabs()), 3)
                        self.assertEqual(app.start_btn.cget('bg'), '#277653')
                        self.assertEqual(app.save_btn.cget('bg'), 'white')
                        def check_buttons(parent):
                            for child in parent.winfo_children():
                                if isinstance(child, tk.Button):
                                    self.assertEqual(child.cget('relief'), 'solid', child.cget('text'))
                                    self.assertGreaterEqual(int(child.cget('borderwidth')), 1)
                                check_buttons(child)
                        check_buttons(root)
                        # 新開的設定對話框，也必須繼承可見邊框。
                        dialog = tk.Toplevel(root)
                        dialog.withdraw()
                        button = tk.Button(dialog, text='Dialog action')
                        self.assertEqual(button.cget('relief'), 'solid')
                        self.assertGreaterEqual(int(button.cget('borderwidth')), 1)
                        dialog.destroy()
                        for canvas in app._settings_scrolls.values():
                            content = canvas.nametowidget(canvas.itemcget(canvas.find_all()[0], 'window'))
                            self.assertLessEqual(content.winfo_reqwidth(), 520)
                        # 尚未映射的視窗使用已還原的正常尺寸，不把 1x1 寫回設定。
                        app.save_config()
                        self.assertEqual(json.loads(config.read_text(encoding='utf-8'))['window_geometry'], saved)
                        self.assertEqual(root.geometry().split('+')[1:], ['120', '100'])
                finally:
                    for timer in root.tk.call('after', 'info'):
                        root.after_cancel(timer)
                    root.destroy()


if __name__ == '__main__':
    unittest.main()
