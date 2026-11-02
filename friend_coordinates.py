"""好友挑戰的舊 DPI 座標轉換；不移動或點擊滑鼠。"""
import copy
import json
from pathlib import Path
import subprocess
import sys

SPACE = 'per_monitor_v1'
POINT_KEYS = ('camp_coord', 'defense_coord', 'challenge_btn_coord', 'start_battle_coord',
              'confirm_btn_coord', 'prev_page_coord', 'next_page_coord', 'auto_queue_coord',
              'gohome_coord', 'territory_coord', 'withdraw_coord', 'withdraw_confirm_coord')
LIST_KEYS = ('coordinates', 'wolf_slots')


def monitor_rects():
    import win32api
    return {win32api.GetMonitorInfo(handle)['Device']: list(rect)
            for handle, _, rect in win32api.EnumDisplayMonitors()}


def legacy_monitor_rects():
    # DPI 模式必須在獨立行程設定；不能暫時改動正在執行的介面。
    code = ('import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(1); '
            'from friend_coordinates import monitor_rects; import json; '
            'print(json.dumps(monitor_rects()))')
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
                            capture_output=True, text=True, check=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout)


def convert_point(point, old_monitors, new_monitors):
    if not point or list(point) == [0, 0]:
        return copy.deepcopy(point)
    x, y = point
    for device, (left, top, right, bottom) in old_monitors.items():
        if left <= x < right and top <= y < bottom and device in new_monitors:
            nl, nt, nr, nb = new_monitors[device]
            return [round(nl + (x - left) * (nr - nl) / (right - left)),
                    round(nt + (y - top) * (nb - nt) / (bottom - top))]
    raise ValueError(f'舊座標 {point} 不在已連接的螢幕內，請確認螢幕配置後再開啟好友挑戰。')


def convert_config(config, old_monitors, new_monitors):
    result = copy.deepcopy(config)
    if result.get('coordinate_space') == SPACE:
        return result
    if result.get('coordinate_space') is not None:
        raise ValueError('不支援的好友座標版本，已保留原設定。')
    for key in POINT_KEYS:
        if key in result:
            result[key] = convert_point(result[key], old_monitors, new_monitors)
    for key in LIST_KEYS:
        if key in result:
            result[key] = [convert_point(point, old_monitors, new_monitors) for point in result[key]]
    result['coordinate_space'] = SPACE
    return result


def migrate_config_file(path, config):
    if config.get('coordinate_space') == SPACE:
        return config
    converted = convert_config(config, legacy_monitor_rects(), monitor_rects())
    path = Path(path)
    # 保留轉換前的完整檔案，以便使用者還原；之後啟動不會重複轉換。
    backup = path.with_name(path.name + '.before-dpi.bak')
    if not backup.exists():
        with backup.open('xb') as stream:
            stream.write(path.read_bytes())
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(converted, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
    return converted
