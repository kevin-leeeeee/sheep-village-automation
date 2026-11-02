"""在遊戲上顯示可拖曳座標；預覽操作不會送出遊戲點擊。"""
import copy
import tkinter as tk
from tkinter import ttk
import win32api

LABELS = {
    'camp_coord': '馴化營', 'defense_coord': '防線', 'challenge_btn_coord': '挑戰',
    'start_battle_coord': '開始戰鬥', 'confirm_btn_coord': '獎勵確定',
    'prev_page_coord': '上一頁', 'next_page_coord': '下一頁',
    'auto_queue_coord': '自動隊列', 'gohome_coord': '回家', 'territory_coord': '領地',
    'withdraw_coord': '撤防', 'withdraw_confirm_coord': '撤防確定',
}


def preview_points(config, group):
    if group == '全部座標':
        return [point for name in ('好友列', '戰鬥按鈕', '出戰狼隻', '回家與撤防')
                for point in preview_points(config, name)]
    if group == '好友列':
        return [('coordinates', i, f'好友 {i + 1}', pt)
                for i, pt in enumerate(config.get('coordinates', []))] + [
                    (key, None, LABELS[key], config[key])
                    for key in ('prev_page_coord', 'next_page_coord')
                    if config.get(key) and list(config[key]) != [0, 0]]
    if group == '出戰狼隻':
        return [('wolf_slots', i, f'狼 {i + 1}', pt)
                for i, pt in enumerate(config.get('wolf_slots', []))] + [
                    ('auto_queue_coord', None, '自動隊列', config['auto_queue_coord'])]
    keys = ('gohome_coord', 'territory_coord', 'withdraw_coord', 'withdraw_confirm_coord')
    if group == '戰鬥按鈕':
        keys = ('camp_coord', 'defense_coord', 'challenge_btn_coord',
                'start_battle_coord', 'confirm_btn_coord')
    return [(key, None, LABELS[key], config[key]) for key in keys
            if config.get(key) and list(config[key]) != [0, 0]]


class CoordinatePreview(tk.Toplevel):
    def __init__(self, parent, config, on_save):
        super().__init__(parent)
        self.original = copy.deepcopy(config)
        self.edited = copy.deepcopy(config)
        self.on_save = on_save
        self.drag = None
        rects = [rect for _, _, rect in win32api.EnumDisplayMonitors()]
        self.left, self.top = min(r[0] for r in rects), min(r[1] for r in rects)
        width = max(r[2] for r in rects) - self.left
        height = max(r[3] for r in rects) - self.top
        self.overrideredirect(True)
        self.geometry(f'{width}x{height}+{self.left}+{self.top}')
        self.attributes('-topmost', True)
        self.attributes('-transparentcolor', '#010203')
        self.canvas = tk.Canvas(self, bg='#010203', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        bar = tk.Frame(self, bg='#223344', padx=10, pady=8)
        # 控制列跟著遊戲座標所在的螢幕，避免分組選單留在另一個螢幕。
        points = [pt for _, _, _, pt in preview_points(config, '全部座標')]
        target = max(win32api.EnumDisplayMonitors(), key=lambda monitor: sum(
            monitor[2][0] <= pt[0] < monitor[2][2] and
            monitor[2][1] <= pt[1] < monitor[2][3] for pt in points))
        work = win32api.GetMonitorInfo(target[0])['Work']
        bar.place(x=work[0] - self.left + 20, y=work[1] - self.top + 20)
        tk.Label(bar, text='顯示：', bg='#223344', fg='white',
                 font=('Microsoft JhengHei UI', 10)).pack(side='left')
        self.group = tk.StringVar(value='全部座標')
        selector = ttk.Combobox(bar, textvariable=self.group, state='readonly', width=12,
                               values=('全部座標', '好友列', '戰鬥按鈕', '出戰狼隻', '回家與撤防'))
        selector.pack(side='left', padx=5)
        selector.bind('<<ComboboxSelected>>', lambda event: self.draw())
        for title, command in (('儲存並套用', self.save), ('還原', self.reset), ('關閉', self.destroy)):
            tk.Button(bar, text=title, command=command, font=('Microsoft JhengHei UI', 10)).pack(
                side='left', padx=4)
        self.status = tk.Label(bar, text='拖曳圓點或標籤微調；Esc 關閉', bg='#223344', fg='white',
                               font=('Microsoft JhengHei UI', 10))
        self.status.pack(side='left', padx=8)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.motion)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.bind('<Escape>', lambda event: self.destroy())
        self.bind('<Button-3>', lambda event: self.destroy())
        self.draw()
        self.focus_force()

    def draw(self):
        self.canvas.delete('all')
        self.targets = {}
        for index, (key, slot, label, point) in enumerate(preview_points(self.edited, self.group.get())):
            x, y = point[0] - self.left, point[1] - self.top
            tag = f'point{index}'
            self.targets[tag] = (key, slot, label)
            self.canvas.create_oval(x-12, y-12, x+12, y+12, outline='#FFB300', width=3, tags=tag)
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill='#FF3030', outline='white', tags=tag)
            # 狼與好友的名稱放在點位上方，避免橫向排列時互相遮蔽。
            text = self.canvas.create_text(x, y-29, text=f'{label}\n({point[0]}, {point[1]})',
                                           anchor='s', fill='white', justify='center',
                                           font=('Microsoft JhengHei UI', 9, 'bold'), tags=tag)
            bounds = self.canvas.bbox(text)
            if bounds:
                bg = self.canvas.create_rectangle(bounds[0]-4, bounds[1]-3, bounds[2]+4, bounds[3]+3,
                                                   fill='#223344', outline='#FFB300', tags=tag)
                self.canvas.tag_lower(bg, text)

    def press(self, event):
        self.drag = None
        for item in reversed(self.canvas.find_overlapping(event.x-2, event.y-2, event.x+2, event.y+2)):
            for tag in self.canvas.gettags(item):
                if tag in self.targets:
                    key, slot, label = self.targets[tag]
                    point = self.edited[key] if slot is None else self.edited[key][slot]
                    self.drag = (key, slot, label, list(point), event.x_root, event.y_root)
                    return

    def motion(self, event):
        if not self.drag:
            return
        key, slot, label, point, sx, sy = self.drag
        moved = [point[0] + event.x_root - sx, point[1] + event.y_root - sy]
        if slot is None:
            self.edited[key] = moved
        else:
            self.edited[key][slot] = moved
        self.status.config(text=f'{label}：({moved[0]}, {moved[1]})，按儲存套用')
        self.draw()

    def release(self, event):
        self.drag = None

    def save(self):
        self.on_save(copy.deepcopy(self.edited))
        self.status.config(text='已儲存並套用；Esc 關閉')

    def reset(self):
        self.edited = copy.deepcopy(self.original)
        self.draw()
        self.status.config(text='已還原預覽；按儲存才會套用')
