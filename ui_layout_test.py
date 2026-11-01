"""檢查設定區的實際 Tk 版面，不啟動遊戲操作。"""
import tkinter as tk
from tkinter import ttk
import unittest

from modern_ui import configure_scroll_area, scroll_settings_canvas


class ScrollAreaTests(unittest.TestCase):
    def test_scrollbar_tracks_content_height_and_resets_position(self):
        root = tk.Tk()
        try:
            root.geometry('320x240')
            scrollbar = ttk.Scrollbar(root, orient='vertical')
            scrollbar.pack(side='right', fill='y')
            canvas = tk.Canvas(root, highlightthickness=0, yscrollcommand=scrollbar.set)
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.configure(command=canvas.yview)
            content = tk.Frame(canvas, width=280, height=50)
            canvas.create_window((0, 0), window=content, anchor='nw')
            root.update()
            configure_scroll_area(canvas, scrollbar, content)
            root.update()
            self.assertFalse(scrollbar.winfo_manager())
            scroll_settings_canvas(canvas, -120)
            self.assertEqual(canvas.yview(), (0.0, 1.0))

            content.configure(height=600)
            root.update()
            configure_scroll_area(canvas, scrollbar, content)
            root.update()
            self.assertEqual(scrollbar.winfo_manager(), 'pack')
            scroll_settings_canvas(canvas, -120)
            self.assertGreater(canvas.yview()[0], 0)

            root.geometry('320x800')
            root.update()
            configure_scroll_area(canvas, scrollbar, content)
            root.update()
            self.assertFalse(scrollbar.winfo_manager())
            self.assertEqual(canvas.yview(), (0.0, 1.0))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
