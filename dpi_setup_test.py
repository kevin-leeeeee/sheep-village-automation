"""DPI 模式只能在新行程驗證，避免套件載入順序掩蓋問題。"""
import json
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows DPI regression')
class DpiSetupTests(unittest.TestCase):
    def probe(self, setup):
        code = setup + '''
import ctypes, json, win32api
import tkinter as tk
from tkinter import font
mode = ctypes.c_int()
ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(mode))
root = tk.Tk()
root.withdraw()
print(json.dumps(dict(mode=mode.value, scaling=float(root.tk.call('tk', 'scaling')),
                     monitors=[rect for _, _, rect in win32api.EnumDisplayMonitors()],
                     line_height=font.Font(root, family='Microsoft JhengHei UI', size=21).metrics('linespace'))))
root.destroy()
'''
        output = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
                                capture_output=True, text=True, encoding='utf-8', check=True)
        return json.loads(output.stdout)

    def test_friend_challenge_is_crisp_and_matches_other_apps(self):
        # 舊版先匯入 PyAutoGUI，由它設定 system-aware；後續改成 2 的呼叫不會成功。
        legacy = self.probe('import tkinter, pyautogui, pynput, ctypes\n'
                            'ctypes.windll.shcore.SetProcessDpiAwareness(2)\n')
        current = self.probe('import friend_challenge\n')
        self.assertEqual(legacy['mode'], 1)
        self.assertEqual(current['mode'], 2)
        other = self.probe('import arena_challenge\n')
        self.assertEqual(current, other)

    def test_other_apps_keep_per_monitor_dpi_and_font_metrics(self):
        results = []
        for module in ('wolf_mine_speedup', 'arena_challenge'):
            result = self.probe(f'import {module}\n')
            self.assertEqual(result['mode'], 2, module)
            results.append(result)
        self.assertEqual(results[0], results[1])


if __name__ == '__main__':
    unittest.main()
