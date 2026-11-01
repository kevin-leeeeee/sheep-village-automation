"""Dry-run regression checks; never start listeners or click the desktop."""
import ast
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch


source = Path(__file__).with_name('friend_challenge.py')
tree = ast.parse(source.read_text(encoding='utf-8'))
namespace = {
    'time': time,
    'os': SimpleNamespace(path=SimpleNamespace(exists=lambda path: False)),
    'get_image_path': lambda name: name,
    'pyautogui': SimpleNamespace(leftClick=lambda x, y: None),
    'tk': SimpleNamespace(NORMAL='normal', DISABLED='disabled'),
}
nodes = [node for node in tree.body if isinstance(node, ast.ClassDef)
         and node.name in ('SkipCurrentFriend', 'FriendChallengeApp')
         or isinstance(node, ast.FunctionDef) and node.name == 'fit_window_geometry']
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
App = namespace['FriendChallengeApp']


class WindowGeometryTests(unittest.TestCase):
    def test_close_and_reopen_restores_saved_geometry(self):
        saved, restored = [], []
        app = App.__new__(App)
        app.config = {}
        app._normal_geometry = None
        app.hotkey_listener = app.mouse_listener = app.capture_listener = None
        app.root = SimpleNamespace(state=lambda: 'normal', winfo_width=lambda: 720,
                                   winfo_height=lambda: 820, winfo_x=lambda: -1700,
                                   winfo_y=lambda: 100, destroy=lambda: None)
        with patch.dict(namespace, save_config=lambda config: saved.append(dict(config))):
            app.on_close()
        app.config = saved[0]
        app.root = SimpleNamespace(minsize=lambda *args: None, geometry=restored.append)
        monitors = SimpleNamespace(EnumDisplayMonitors=lambda: [(1, None, None)],
                                   GetMonitorInfo=lambda monitor: {'Work': (-1920, 0, 0, 1080)})
        with patch.dict(namespace, win32api=monitors):
            app.restore_window_geometry()
        self.assertEqual(restored, ['720x820+-1700+100'])

    def test_existing_position_and_negative_monitor_are_preserved(self):
        fit = namespace['fit_window_geometry']
        for x in (120, -1800):
            saved = dict(x=x, y=100, width=600, height=800)
            self.assertEqual(fit(saved, [(-1920, 0, 0, 1080), (0, 0, 1920, 1080)]), saved)

    def test_disconnected_monitor_and_oversized_window_are_recovered(self):
        fit = namespace['fit_window_geometry']
        result = fit(dict(x=-1800, y=1200, width=2400, height=1600), [(0, 0, 1920, 1040)])
        self.assertGreaterEqual(result['x'], 0)
        self.assertGreaterEqual(result['y'], 0)
        self.assertLessEqual(result['x'] + result['width'], 1920)
        self.assertLessEqual(result['y'] + result['height'], 1040)

    def test_invalid_saved_size_is_rejected(self):
        with self.assertRaises(ValueError):
            namespace['fit_window_geometry'](dict(x=0, y=0, width=-1, height=800), [(0, 0, 1920, 1080)])


class FriendSkipTests(unittest.TestCase):
    def run_bot(self, mode, injection=None, targets=(1, 2), dispatch='auto', detect=False,
                tasks=None, selected_friends=None):
        app = App.__new__(App)
        app.running, app.skip_current = True, False
        app.tasks = tasks if tasks is not None else [(target, mode) for target in targets]
        app.config = {key: [100 + i, 200] for i, key in enumerate((
            'camp_coord', 'defense_coord', 'challenge_btn_coord',
            'start_battle_coord', 'confirm_btn_coord', 'next_page_coord',
            'auto_queue_coord', 'gohome_coord', 'territory_coord',
            'withdraw_coord', 'withdraw_confirm_coord'))}
        app.config.update(coordinates=[[i, 1] for i in range(6)],
                          prev_page_coord=[90, 200],
                          action_delay=0, load_delay=0, initial_delay=0,
                          wait_timeout=1, poll_interval=1,
                          dispatch_mode=dispatch, dispatch_wolves='1,2',
                          wolf_slots=[[50, 1], [51, 1]])
        app.root = SimpleNamespace(after=lambda delay, callback: callback())
        button = SimpleNamespace(config=lambda **kwargs: None)
        app.start_btn = app.stop_btn = app.skip_btn = button
        logs, events, checkpoints = [], [], []
        app.log = logs.append
        app.find_template_on_game_screen = lambda *a, **k: (False, 0, None)
        namespace['os'].path.exists = lambda path: detect

        def checkpoint(kind):
            checkpoints.append(kind)
            if injection == len(checkpoints):
                app.trigger_skip('test')
                events.append(('skip', None))

        actual_page = 1

        def click(coord, name='', allow_skip=False):
            nonlocal actual_page
            if not allow_skip:
                checkpoint('click')
            result = App.click_coord(app, coord, name, allow_skip=allow_skip)
            if result:
                if coord == app.config['next_page_coord']:
                    actual_page += 1
                elif coord == app.config['prev_page_coord']:
                    actual_page = max(1, actual_page - 1)
                elif coord in app.config['coordinates'] and selected_friends is not None:
                    slot = app.config['coordinates'].index(coord)
                    selected_friends.append((actual_page - 1) * 6 + slot + 1)
                # 遊戲按回家會保留好友列原頁，不改 actual_page。
            events.append(('recovery' if allow_skip else 'click', tuple(coord)))
            return result

        def sleep(duration, interrupt_on_skip=True):
            if interrupt_on_skip:
                checkpoint('wait')
            return App.interruptible_sleep(app, 0, interrupt_on_skip=interrupt_on_skip)

        app.click_coord, app.interruptible_sleep = click, sleep
        app.bot_loop()
        self.assertFalse(any('❌' in log for log in logs), logs)
        return events, checkpoints, app.config

    def test_mixed_mode_return_home_preserves_friend_page(self):
        tasks = [(1, 'wolf'), (3, 'defense'), (4, 'defense'),
                 (5, 'wolf'), (6, 'wolf'), (7, 'defense'),
                 (8, 'wolf'), (9, 'defense'), (10, 'defense'),
                 (11, 'wolf'), (13, 'defense')]
        selected = []
        events, _, config = self.run_bot('wolf', tasks=tasks, selected_friends=selected)
        self.assertEqual(selected, [target for target, _ in tasks])
        self.assertEqual(events.count(('click', tuple(config['next_page_coord']))), 2)

    def test_return_home_then_earlier_friend_uses_previous_page(self):
        selected = []
        events, _, config = self.run_bot(
            'defense', targets=(7, 1), selected_friends=selected)
        self.assertEqual(selected, [7, 1])
        self.assertEqual(events.count(('click', tuple(config['prev_page_coord']))), 1)

    def test_skip_at_every_click_and_wait(self):
        for mode, dispatch, detect in (
            ('wolf', 'auto', False), ('wolf', 'auto', True),
            ('defense', 'auto', False), ('defense', 'manual', True),
        ):
            baseline, checkpoints, config = self.run_bot(mode, dispatch=dispatch, detect=detect)
            # Count checkpoints belonging to the first friend only.
            second = baseline.index(('click', (1, 1)))
            first_clicks = sum(kind == 'click' for kind, _ in baseline[:second])
            count = 0
            for kind in checkpoints:
                if kind == 'click':
                    first_clicks -= 1
                    if first_clicks < 0:
                        break
                count += 1
            for position in range(1, count + 1):
                with self.subTest(mode=mode, dispatch=dispatch, detect=detect, position=position):
                    events, _, _ = self.run_bot(mode, position, dispatch=dispatch, detect=detect)
                    after = events[events.index(('skip', None)) + 1:]
                    normal = next(event for event in after if event[0] == 'click')
                    self.assertEqual(normal, ('click', (1, 1)))

    def test_skip_while_paging_keeps_page_position(self):
        events, _, config = self.run_bot('wolf', injection=2, targets=(7, 8))
        self.assertEqual(events.count(('click', tuple(config['next_page_coord']))), 1)
        self.assertIn(('click', (1, 1)), events)

    def test_skip_is_unconditional_without_return_home(self):
        # 無論 defense 還是 wolf，無論開戰前或開戰中跳過，皆無條件直接點下一位好友，不回家不撤防
        events, _, config = self.run_bot('defense', injection=12, targets=(7, 8))
        self.assertEqual(events.count(('click', tuple(config['next_page_coord']))), 1)
        self.assertIn(('click', (1, 1)), events)
        self.assertFalse(any(e[0] == 'recovery' and e[1] == tuple(config['gohome_coord']) for e in events))

    def test_page_backward_uses_left_arrow_and_auto_calc(self):
        # 目標頁小於當前頁 (例如 7 在第 2 頁，1 在第 1 頁)：按左箭頭 (上一頁) 翻回第 1 頁，完全不按回家
        app = App.__new__(App)
        app.running, app.skip_current = False, False
        app.tasks = [(7, 'wolf'), (1, 'wolf')]
        app.config = {key: [100 + i, 200] for i, key in enumerate((
            'camp_coord', 'defense_coord', 'challenge_btn_coord',
            'start_battle_coord', 'confirm_btn_coord', 'next_page_coord',
            'auto_queue_coord', 'gohome_coord', 'territory_coord',
            'withdraw_coord', 'withdraw_confirm_coord'))}
        app.config.update(coordinates=[[i * 100, 500] for i in range(6)],
                          action_delay=0, load_delay=0, initial_delay=0,
                          wait_timeout=1, poll_interval=1,
                          dispatch_mode='auto', dispatch_wolves='1',
                          wolf_slots=[[50, 1]])
        app.root = SimpleNamespace(after=lambda delay, callback: callback())
        button = SimpleNamespace(config=lambda **kwargs: None)
        app.start_btn = app.stop_btn = app.skip_btn = button
        events = []
        app.log = lambda msg: None
        app.find_template_on_game_screen = lambda *a, **k: (False, 0, None)
        app.click_coord = lambda coord, name='', allow_skip=False: events.append(('click', tuple(coord), name))
        app.interruptible_sleep = lambda *a, **k: True
        app.running = True
        app.bot_loop()
        # 應包含點擊上一頁(◀)，且絕無點擊回家
        self.assertTrue(any('上一頁(◀)' in name for _, _, name in events))
        self.assertFalse(any('回家' in name for _, _, name in events))

    def test_stop_prevents_recovery_clicks(self):
        app = App.__new__(App)
        app.running, app.skip_current = False, True
        self.assertFalse(app.click_coord([1, 2]))
        self.assertFalse(app.interruptible_sleep(1, interrupt_on_skip=False))


if __name__ == '__main__':
    unittest.main()
