"""DPI 模式只能在新行程驗證，避免套件載入順序掩蓋問題。"""
import json
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows DPI regression')
class DpiSetupTests(unittest.TestCase):
    def test_all_three_apps_use_same_dpi_and_font_metrics(self):
        results = []
        for module in ('friend_challenge', 'wolf_mine_speedup', 'arena_challenge'):
            code = f'''
import {module}
import ctypes, json
import tkinter as tk
from tkinter import font
mode = ctypes.c_int()
ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(mode))
root = tk.Tk()
root.withdraw()
print(json.dumps(dict(mode=mode.value, scaling=float(root.tk.call('tk', 'scaling')),
                     line_height=font.Font(root, family='Microsoft JhengHei UI', size=21).metrics('linespace'))))
root.destroy()
'''
            output = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
                                    capture_output=True, text=True, encoding='utf-8', check=True)
            result = json.loads(output.stdout)
            self.assertEqual(result['mode'], 2, module)
            results.append(result)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])


if __name__ == '__main__':
    unittest.main()
