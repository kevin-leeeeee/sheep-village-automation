"""驗證舊座標轉換與預覽；不送出任何桌面滑鼠點擊。"""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dpi_setup import configure_dpi
configure_dpi()
import friend_coordinates as coordinates
from coordinate_preview import CoordinatePreview, preview_points
import tkinter as tk


OLD = {'primary': [0, 0, 1920, 1200], 'game': [2400, -173, 3900, 2227]}
NEW = {'primary': [0, 0, 1920, 1200], 'game': [1920, -138, 3120, 1782]}


class CoordinateMigrationTests(unittest.TestCase):
    def test_game_coordinates_and_settings_are_preserved(self):
        original = {'challenge_btn_coord': [3612, 953], 'prev_page_coord': [0, 0],
                    'coordinates': [[2683, 907], [2820, 905]],
                    'wolf_slots': [[2727, 900], [2845, 901]],
                    'wolf_friends': '1,5,6', 'dispatch_wolves': '1,3', 'initial_delay': '40',
                    'window_geometry': {'x': 2352, 'y': 823, 'width': 560, 'height': 833}}
        saved = copy.deepcopy(original)
        result = coordinates.convert_config(original, OLD, NEW)
        self.assertEqual(original, saved)
        self.assertEqual(result['challenge_btn_coord'], [2890, 763])
        self.assertEqual(result['coordinates'][0], [2146, 726])
        self.assertEqual(result['wolf_slots'][0], [2182, 720])
        self.assertEqual(result['prev_page_coord'], [0, 0])
        for key in ('wolf_friends', 'dispatch_wolves', 'initial_delay', 'window_geometry'):
            self.assertEqual(result[key], original[key])
        self.assertEqual(coordinates.convert_config(result, OLD, NEW), result)

    def test_primary_and_negative_monitor_coordinates(self):
        self.assertEqual(coordinates.convert_point([100, 400], OLD, NEW), [100, 400])
        self.assertEqual(coordinates.convert_point([-1600, -100],
                         {'left': [-2000, -200, 0, 1800]},
                         {'left': [-1600, -160, 0, 1440]}), [-1280, -80])

    def test_backup_is_exact_and_second_load_does_not_convert(self):
        original = {'challenge_btn_coord': [3612, 953]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'friend.json')
            before = json.dumps(original, indent=3).encode('utf-8')
            path.write_bytes(before)
            with patch.object(coordinates, 'legacy_monitor_rects', return_value=OLD) as old_probe, \
                 patch.object(coordinates, 'monitor_rects', return_value=NEW):
                first = coordinates.migrate_config_file(path, original)
                second = coordinates.migrate_config_file(path, json.loads(path.read_text()))
            self.assertEqual(first, second)
            self.assertEqual(old_probe.call_count, 1)
            self.assertEqual(Path(str(path) + '.before-dpi.bak').read_bytes(), before)

    def test_disconnected_monitor_leaves_config_untouched(self):
        original = {'camp_coord': [9000, 9000]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'friend.json')
            path.write_text(json.dumps(original))
            before = path.read_bytes()
            with patch.object(coordinates, 'legacy_monitor_rects', return_value=OLD), \
                 patch.object(coordinates, 'monitor_rects', return_value=NEW):
                with self.assertRaises(ValueError):
                    coordinates.migrate_config_file(path, original)
            self.assertEqual(path.read_bytes(), before)


class CoordinatePreviewTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.config = {key: [200 + i * 30, 400] for i, key in enumerate(coordinates.POINT_KEYS)}
        self.config.update(coordinates=[[200 + i * 100, 700] for i in range(6)],
                           wolf_slots=[[200 + i * 100, 800] for i in range(8)])
        self.saved = []
        self.preview = CoordinatePreview(self.root, self.config, self.saved.append)
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_all_groups_and_virtual_desktop_origin(self):
        self.assertEqual(self.preview.group.get(), '全部座標')
        all_points = preview_points(self.config, '全部座標')
        self.assertEqual(len(all_points), 26)
        self.assertEqual(len({(key, slot) for key, slot, _, _ in all_points}), 26)
        self.assertEqual(len(self.preview.targets), 26)
        self.assertEqual(len(preview_points(self.config, '好友列')), 8)
        self.assertEqual(len(preview_points(self.config, '出戰狼隻')), 9)
        self.assertEqual(len(preview_points(self.config, '戰鬥按鈕')), 5)
        self.assertEqual(len(preview_points(self.config, '回家與撤防')), 4)
        self.assertEqual(self.preview.winfo_rootx(), self.preview.left)
        self.assertEqual(self.preview.winfo_rooty(), self.preview.top)

    def test_drag_save_reset_and_close_without_saving(self):
        p = self.preview
        x, y = self.config['coordinates'][0]
        p.press(SimpleNamespace(x=x-p.left, y=y-p.top, x_root=x, y_root=y))
        p.motion(SimpleNamespace(x_root=x+17, y_root=y-9))
        p.release(None)
        self.assertEqual(p.edited['coordinates'][0], [x+17, y-9])
        self.assertEqual(self.config['coordinates'][0], [x, y])
        self.assertEqual(self.saved, [])
        p.save()
        self.assertEqual(self.saved[0]['coordinates'][0], [x+17, y-9])
        p.reset()
        self.assertEqual(p.edited['coordinates'][0], [x, y])
        self.assertEqual(self.saved[0]['coordinates'][0], [x+17, y-9])
        p.destroy()
        self.assertEqual(len(self.saved), 1)


if __name__ == '__main__':
    unittest.main()
