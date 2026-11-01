"""Patrol navigation regression tests without desktop clicks or listeners."""
import ast
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from contextlib import contextmanager


source = Path(__file__).with_name('wolf_mine_speedup.py')
tree = ast.parse(source.read_text(encoding='utf-8'))
namespace = {'time': time, 'contextmanager': contextmanager}
nodes = [node for node in tree.body if isinstance(node, ast.ClassDef)
         and node.name in ('PatrolNavigationInterrupted', 'PatrolStepInterrupted', 'FriendPatrolAutomation')]
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
Engine = namespace['FriendPatrolAutomation']


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class PatrolTests(unittest.TestCase):
    def run_patrol(self, inject=None, previous=False, pages=1, image_page=False,
                   image_confirm=False, limit=False, inject_step=None):
        gui = SimpleNamespace(
            root=SimpleNamespace(after=lambda delay, callback: callback()),
            coordinates=[(1, 1), (2, 2), (3, 3)],
            wolf_coords=[(10, 10), (11, 11)], mine_coord=(20, 20),
            confirm_coord=None if image_confirm else (30, 30),
            next_page_coord=None if image_page else (40, 40),
        )
        for name, value in dict(load_delay=0, interval=0, wolf_delay=1,
                                page_delay=0, max_pages=pages, mine_delay=0,
                                confirm_delay=0, mining=True, wolf=True,
                                auto_page=pages > 1, skip_friend_idx='').items():
            setattr(gui, name + '_var', Value(value))
        button = SimpleNamespace(config=lambda **kwargs: None)
        gui.start_btn = gui.stop_btn = button
        engine = Engine(gui)
        engine.running = True
        events, checkpoints, logs = [], [], []
        injected = False

        def checkpoint(kind):
            nonlocal injected
            checkpoints.append(kind)
            if not injected and inject_step and engine.active_step == inject_step:
                injected = True
                engine.request_next_step()
                events.append(('request-step', inject_step))
            if not injected and inject == len(checkpoints):
                injected = True
                engine.request_navigation(previous)
                events.append(('request', None))

        def desktop_click(x, y):
            events.append(('click', (x, y)))

        namespace['pyautogui'] = SimpleNamespace(leftClick=desktop_click)

        def click(x, y):
            checkpoint('page-click' if engine.paging else 'click')
            Engine.patrol_click(engine, x, y)

        def sleep(duration):
            checkpoint('page-wait' if engine.paging else 'wait')
            return Engine.interruptible_sleep(engine, 0)

        def capture():
            checkpoint('capture')
            return object()

        def match(*args, **kwargs):
            checkpoint('match')
            return (30, 30), 1, (1, 1)

        def log(message):
            logs.append(message)
            if message.startswith('巡邏完成'):
                engine.running = False

        engine.log = log
        engine.patrol_click, engine.interruptible_sleep = click, sleep
        engine.capture_screen, engine.find_image_multiscale = capture, match
        engine.check_mine_limit_popup = lambda shot: (31, 31) if limit else None
        engine.check_invite_popup_and_stop = lambda: False
        engine.patrol_loop()
        return events, checkpoints, logs

    def test_right_at_every_stage_skips_remaining_actions(self):
        for image_confirm, limit in ((False, False), (True, False), (False, True)):
            baseline, checkpoints, _ = self.run_patrol(image_confirm=image_confirm, limit=limit)
            # Find the checkpoint for the first action of friend 2.
            first_friend_clicks = baseline.index(('click', (2, 2)))
            clicks = 0
            for position, kind in enumerate(checkpoints, 1):
                if kind == 'click':
                    clicks += 1
                if clicks > first_friend_clicks:
                    break
                with self.subTest(image_confirm=image_confirm, limit=limit, position=position):
                    events, _, _ = self.run_patrol(position, image_confirm=image_confirm, limit=limit)
                    after = events[events.index(('request', None)) + 1:]
                    self.assertEqual(next(event for event in after if event[0] == 'click'),
                                     ('click', (2, 2)))

    def test_page_command_is_preserved_for_new_page(self):
        for image_page in (False, True):
            _, checkpoints, _ = self.run_patrol(pages=2, image_page=image_page)
            for position, kind in enumerate(checkpoints, 1):
                if kind not in ('page-click', 'page-wait'):
                    continue
                with self.subTest(image_page=image_page, position=position):
                    events, _, logs = self.run_patrol(position, pages=2, image_page=image_page)
                    after = events[events.index(('request', None)) + 1:]
                    friend_clicks = [event for event in after if event[1] in ((1, 1), (2, 2), (3, 3))]
                    self.assertEqual(friend_clicks[0], ('click', (2, 2)))
                    self.assertTrue(any('#4' in log and '中斷' in log for log in logs))

    def test_left_returns_to_previous_friend(self):
        _, checkpoints, _ = self.run_patrol()
        second_friend = [i for i, kind in enumerate(checkpoints, 1) if kind == 'click'][7]
        events, _, _ = self.run_patrol(second_friend, previous=True)
        after = events[events.index(('request', None)) + 1:]
        self.assertEqual(next(event for event in after if event[0] == 'click'), ('click', (1, 1)))

    def test_zero_wait_still_checks_navigation_and_stop(self):
        engine = Engine(SimpleNamespace())
        engine.running = True
        engine.skip_current_friend = True
        self.assertFalse(engine.interruptible_sleep(0))
        engine.running = False
        with self.assertRaises(namespace['PatrolNavigationInterrupted']):
            engine.patrol_click(1, 2)

    def test_down_advances_only_current_step(self):
        for step, expected in (
            ('等待好友家園載入', (10, 10)),
            ('敲狼', (30, 30)),
            ('敲狼後等待', (30, 30)),
            ('敲狼確定彈窗', (20, 20)),
            ('礦山點擊後等待', (30, 30)),
            ('礦山確定與上限檢查', (2, 2)),
            ('好友結束等待', (2, 2)),
            ('換頁後等待', (1, 1)),
        ):
            with self.subTest(step=step):
                events, _, _ = self.run_patrol(inject_step=step, pages=2)
                after = events[events.index(('request-step', step)) + 1:]
                self.assertEqual(next(event for event in after if event[0] == 'click'),
                                 ('click', expected))

    def test_friend_navigation_takes_priority_over_next_step(self):
        engine = Engine(SimpleNamespace(root=SimpleNamespace(after=lambda *args: None)))
        engine.running = True
        with self.assertRaises(namespace['PatrolNavigationInterrupted']):
            with engine.patrol_step('test'):
                engine.request_next_step()
                engine.request_navigation()
                engine.wait_for_friend(0)
        self.assertFalse(engine.next_step)


if __name__ == '__main__':
    unittest.main()
