import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import threading
import time
import pyautogui
import os
import sys
import pynput
import ctypes
from ctypes import wintypes
import win32api
from PIL import Image, ImageTk
import cv2
import numpy as np

# 關閉 PyAutoGUI 自動觸發的邊角防護異常 (改用全域 F10 鍵緊急停止)
pyautogui.FAILSAFE = False

# 解決 Windows 縮放導致 pyautogui 座標偏移與截圖全黑的問題
try:
    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# 確保在正確的目錄執行
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
IMAGE_DIR = os.path.join(BASE_DIR, 'images')

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

CONFIG_FILE = 'friend_challenge_config.json'

DEFAULT_CONFIG = {
    "wolf_friends": "1,2,3",
    "defense_friends": "4,5,6",
    "camp_coord": [1000, 500],
    "defense_coord": [1100, 500],
    "challenge_btn_coord": [1200, 600],
    "start_battle_coord": [1300, 700],
    "confirm_btn_coord": [1400, 800],
    "coordinates": [
        [2143, 720], [2253, 719], [2364, 718],
        [2475, 717], [2586, 716], [2697, 715]
    ],
    "next_page_coord": [2774, 763],
    "dispatch_mode": "auto",
    "auto_queue_coord": [1150, 650],
    "wolf_slots": [],
    "dispatch_wolves": "1,2,3",
    "action_delay": "1.5",
    "load_delay": "3",
    "initial_delay": "10",
    "poll_interval": "1",
    "wait_timeout": "30",
    "threshold": "0.9",
    "topmost": True,
    "gohome_coord": [1500, 900],
    "territory_coord": [1600, 900],
    "withdraw_coord": [1700, 900],
    "withdraw_confirm_coord": [1800, 900]
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            print(f"讀取設定檔失敗: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"儲存設定檔失敗: {e}")

def center_window_on_cursor(root, width, height):
    try:
        monitors = win32api.EnumDisplayMonitors()
        pt = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            px, py = pt.x, pt.y
        else:
            px, py = 0, 0
        for hMonitor, _, _ in monitors:
            m_info = win32api.GetMonitorInfo(hMonitor)
            m_rect = m_info['Monitor']
            if m_rect[0] <= px <= m_rect[2] and m_rect[1] <= py <= m_rect[3]:
                work = m_info.get('Work', m_rect)
                avail_w = work[2] - work[0]
                avail_h = work[3] - work[1]
                target_w = min(width, max(380, avail_w - 20))
                target_h = min(height, max(450, avail_h - 40))
                spawn_x = work[0] + max(0, (avail_w - target_w) // 2)
                spawn_y = work[1] + max(0, (avail_h - target_h) // 2)
                root.geometry(f"{target_w}x{target_h}+{spawn_x}+{spawn_y}")
                return
    except Exception:
        pass
    root.geometry(f"{width}x{height}")


class FriendChallengeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("保衛羊村 - 挑戰好友")
        center_window_on_cursor(self.root, 435, 690)
        
        self.config = load_config()
        self.running = False
        self.thread = None
        
        self.topmost = self.config.get("topmost", True)
        self.root.attributes("-topmost", self.topmost)
        
        self.capturing = False
        self.capture_mode = None
        self.temp_p1 = None
        self.capture_listener = None

        self.setup_ui()
        self.setup_global_hotkeys()

    def setup_global_hotkeys(self):
        def on_press(key):
            try:
                if key == pynput.keyboard.Key.f10:
                    if self.running:
                        self.root.after(0, self.stop_bot)
            except Exception:
                pass
        self.hotkey_listener = pynput.keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def setup_ui(self):
        # 建立外層滾動容器，確保小螢幕按鈕不被截斷
        self.canvas_container = tk.Frame(self.root)
        self.canvas_container.pack(fill=tk.BOTH, expand=True)

        self.main_canvas = tk.Canvas(self.canvas_container, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(self.canvas_container, orient="vertical", command=self.main_canvas.yview)
        
        main = tk.Frame(self.main_canvas, padx=6, pady=4)
        self.canvas_window_id = self.main_canvas.create_window((0, 0), window=main, anchor="nw")
        
        def _on_main_configure(e):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        main.bind("<Configure>", _on_main_configure)

        def _on_canvas_configure(e):
            self.main_canvas.itemconfig(self.canvas_window_id, width=e.width)
        self.main_canvas.bind('<Configure>', _on_canvas_configure)

        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_scrollbar.pack(side="right", fill="y")
        
        # 滾輪智慧滾動
        def _on_mousewheel(event):
            try:
                if self.main_canvas.winfo_height() < main.winfo_reqheight():
                    widget = self.root.winfo_containing(event.x_root, event.y_root)
                    if widget is not getattr(self, 'log_text', None):
                        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
        self.root.bind_all("<MouseWheel>", _on_mousewheel)

        # 頂部按鈕列
        top_btn_frame = tk.Frame(main)
        top_btn_frame.pack(fill='x', pady=2)
        
        bg_color = 'lightgreen' if self.topmost else 'SystemButtonFace'
        relief_style = 'sunken' if self.topmost else 'raised'
        self.topmost_btn = tk.Button(top_btn_frame, text="📌 視窗置頂", command=self.toggle_topmost, font=('Arial', 9), bg=bg_color, relief=relief_style, padx=5)
        self.topmost_btn.pack(side=tk.RIGHT, padx=2)
        
        # -- 好友編號設定 --
        target_lf = tk.LabelFrame(main, text="好友編號設定 (逗號分隔)", font=('Arial', 9, 'bold'), padx=5, pady=5)
        target_lf.pack(fill='x', pady=5)

        tk.Label(target_lf, text="挑戰狼:", font=('Arial', 9)).grid(row=0, column=0, sticky='w', pady=2)
        self.wolf_friends_var = tk.StringVar(value=self.config.get("wolf_friends", ""))
        tk.Entry(target_lf, textvariable=self.wolf_friends_var, width=32, font=('Arial', 9)).grid(row=0, column=1, sticky='w', pady=2, padx=5)

        tk.Label(target_lf, text="挑戰防線:", font=('Arial', 9)).grid(row=1, column=0, sticky='w', pady=2)
        self.defense_friends_var = tk.StringVar(value=self.config.get("defense_friends", ""))
        tk.Entry(target_lf, textvariable=self.defense_friends_var, width=32, font=('Arial', 9)).grid(row=1, column=1, sticky='w', pady=2, padx=5)

        # -- 派狼設定 --
        wolf_lf = tk.LabelFrame(main, text="出戰派狼設定 (僅挑戰防線有效)", font=('Arial', 9, 'bold'), padx=5, pady=5)
        wolf_lf.pack(fill='x', pady=5)

        self.dispatch_mode_var = tk.StringVar(value=self.config.get("dispatch_mode", "auto"))
        tk.Radiobutton(wolf_lf, text="自動隊列", variable=self.dispatch_mode_var, value="auto", font=('Arial', 9)).grid(row=0, column=0, sticky='w')
        tk.Radiobutton(wolf_lf, text="指定狼隻", variable=self.dispatch_mode_var, value="manual", font=('Arial', 9)).grid(row=0, column=1, sticky='w')

        tk.Label(wolf_lf, text="自動隊列:", font=('Arial', 9)).grid(row=1, column=0, sticky='w', pady=2)
        aq_val = self.config.get("auto_queue_coord", [0, 0])
        self.aq_x = tk.StringVar(value=str(aq_val[0]))
        self.aq_y = tk.StringVar(value=str(aq_val[1]))
        aq_frame = tk.Frame(wolf_lf)
        aq_frame.grid(row=1, column=1, sticky='w', pady=2, columnspan=2)
        tk.Entry(aq_frame, textvariable=self.aq_x, width=4, font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Label(aq_frame, text=",", font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Entry(aq_frame, textvariable=self.aq_y, width=4, font=('Arial', 9)).pack(side=tk.LEFT, padx=(0,5))
        tk.Button(aq_frame, text="設定(K)", font=('Arial', 8), command=lambda: self.start_capture('auto_queue_coord', '自動隊列按鈕')).pack(side=tk.LEFT)

        tk.Label(wolf_lf, text="狼槽(兩點):", font=('Arial', 9)).grid(row=2, column=0, sticky='w', pady=2)
        slots = self.config.get("wolf_slots", [])
        self.lbl_wolf_slots = tk.Label(wolf_lf, text=f"({len(slots)}/8 點)", font=('Arial', 9), fg="green" if len(slots)==8 else "red")
        self.lbl_wolf_slots.grid(row=2, column=1, sticky='w', pady=2)
        tk.Button(wolf_lf, text="擷取 (第1及第8隻)", font=('Arial', 8), command=self.start_capture_wolf).grid(row=2, column=2, sticky='w', padx=5)

        tk.Label(wolf_lf, text="出戰順序:", font=('Arial', 9)).grid(row=3, column=0, sticky='w', pady=2)
        self.dispatch_wolves_var = tk.StringVar(value=self.config.get("dispatch_wolves", "1,2,3"))
        tk.Entry(wolf_lf, textvariable=self.dispatch_wolves_var, width=15, font=('Arial', 9)).grid(row=3, column=1, sticky='w', pady=2, columnspan=2)

        # -- 戰鬥主流程座標設定 --
        main_coord_lf = tk.LabelFrame(main, text="戰鬥主流程座標", font=('Arial', 9, 'bold'), padx=5, pady=5)
        main_coord_lf.pack(fill='x', pady=5)

        self.coord_vars = {}
        main_fields = [
            ("camp_coord", "馴化營:"),
            ("defense_coord", "防線:"),
            ("challenge_btn_coord", "挑戰:"),
            ("start_battle_coord", "開始戰鬥:"),
            ("confirm_btn_coord", "確定(獎勵):"),
            ("next_page_coord", "下一頁:")
        ]

        for i, (key, label) in enumerate(main_fields):
            row = i // 2
            col_offset = (i % 2) * 2
            tk.Label(main_coord_lf, text=label, font=('Arial', 9)).grid(row=row, column=col_offset, sticky='e', pady=2)
            
            val = self.config.get(key, [0, 0])
            var_x = tk.StringVar(value=str(val[0]))
            var_y = tk.StringVar(value=str(val[1]))
            self.coord_vars[key] = (var_x, var_y)
            
            f_ = tk.Frame(main_coord_lf)
            f_.grid(row=row, column=col_offset+1, sticky='w', pady=2, padx=2)
            tk.Entry(f_, textvariable=var_x, width=4, font=('Arial', 9)).pack(side=tk.LEFT)
            tk.Entry(f_, textvariable=var_y, width=4, font=('Arial', 9)).pack(side=tk.LEFT, padx=(1,2))
            tk.Button(f_, text="(K)", font=('Arial', 8), command=lambda k=key, n=label: self.start_capture(k, n)).pack(side=tk.LEFT)

        # 好友列表座標(兩點生成)
        tk.Label(main_coord_lf, text="好友列表:", font=('Arial', 9)).grid(row=3, column=0, sticky='e', pady=2)
        f_coords = self.config.get("coordinates", [])
        self.lbl_friend_coords = tk.Label(main_coord_lf, text=f"({len(f_coords)}/6 點)", font=('Arial', 9), fg="green" if len(f_coords)==6 else "red")
        self.lbl_friend_coords.grid(row=3, column=1, sticky='w', pady=2, padx=2)
        tk.Button(main_coord_lf, text="擷取 (第1及第6位)", font=('Arial', 8), command=self.start_capture_friend).grid(row=3, column=2, sticky='w', columnspan=2)

        # 新增: 截圖校正按鈕與瀏覽按鈕
        tk.Label(main_coord_lf, text="獎勵截圖:", font=('Arial', 9)).grid(row=4, column=0, sticky='e', pady=2)
        capture_btn_frame = tk.Frame(main_coord_lf)
        capture_btn_frame.grid(row=4, column=1, sticky='w', columnspan=3, pady=2, padx=2)
        tk.Button(capture_btn_frame, text="📸 框選截圖", font=('Arial', 8), command=self.start_capture_image).pack(side=tk.LEFT)
        tk.Button(capture_btn_frame, text="📁 瀏覽圖檔", font=('Arial', 8), command=self.browse_reward_image).pack(side=tk.LEFT, padx=(5, 0))

        # -- 防線撤退專用座標 --
        retreat_lf = tk.LabelFrame(main, text="防線撤退專用座標", font=('Arial', 9, 'bold'), padx=5, pady=5)
        retreat_lf.pack(fill='x', pady=5)
        
        retreat_fields = [
            ("gohome_coord", "回家:"),
            ("territory_coord", "領地:"),
            ("withdraw_coord", "撤防:"),
            ("withdraw_confirm_coord", "撤防確定:")
        ]
        
        for i, (key, label) in enumerate(retreat_fields):
            row = i // 2
            col_offset = (i % 2) * 2
            tk.Label(retreat_lf, text=label, font=('Arial', 9)).grid(row=row, column=col_offset, sticky='e', pady=2)
            
            val = self.config.get(key, [0, 0])
            var_x = tk.StringVar(value=str(val[0]))
            var_y = tk.StringVar(value=str(val[1]))
            self.coord_vars[key] = (var_x, var_y)
            
            f_ = tk.Frame(retreat_lf)
            f_.grid(row=row, column=col_offset+1, sticky='w', pady=2, padx=2)
            tk.Entry(f_, textvariable=var_x, width=4, font=('Arial', 9)).pack(side=tk.LEFT)
            tk.Entry(f_, textvariable=var_y, width=4, font=('Arial', 9)).pack(side=tk.LEFT, padx=(1,2))
            tk.Button(f_, text="(K)", font=('Arial', 8), command=lambda k=key, n=label: self.start_capture(k, n)).pack(side=tk.LEFT)

        # -- 其他時間設定 --
        time_lf = tk.LabelFrame(main, text="各項時間間隔與超時設定", font=('Arial', 9, 'bold'), padx=5, pady=5)
        time_lf.pack(fill='x', pady=5)

        r1 = tk.Frame(time_lf)
        r1.pack(fill='x', pady=2)
        tk.Label(r1, text="進好友家(s):", font=('Arial', 9)).pack(side=tk.LEFT)
        self.load_delay_var = tk.StringVar(value=str(self.config.get("load_delay", "3")))
        tk.Entry(r1, textvariable=self.load_delay_var, width=5, font=('Arial', 9)).pack(side=tk.LEFT, padx=3)
        
        tk.Label(r1, text="一般動作間隔(s):", font=('Arial', 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.action_delay_var = tk.StringVar(value=str(self.config.get("action_delay", "1.5")))
        tk.Entry(r1, textvariable=self.action_delay_var, width=5, font=('Arial', 9)).pack(side=tk.LEFT, padx=3)

        r2 = tk.Frame(time_lf)
        r2.pack(fill='x', pady=2)
        tk.Label(r2, text="幾秒後截圖:", font=('Arial', 9)).pack(side=tk.LEFT)
        self.initial_delay_var = tk.StringVar(value=str(self.config.get("initial_delay", "10")))
        tk.Entry(r2, textvariable=self.initial_delay_var, width=5, font=('Arial', 9)).pack(side=tk.LEFT, padx=3)
        
        tk.Label(r2, text="截圖間隔:", font=('Arial', 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.poll_interval_var = tk.StringVar(value=str(self.config.get("poll_interval", "1")))
        tk.Entry(r2, textvariable=self.poll_interval_var, width=4, font=('Arial', 9)).pack(side=tk.LEFT, padx=3)
        
        tk.Label(r2, text="戰鬥超時:", font=('Arial', 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.timeout_var = tk.StringVar(value=str(self.config.get("wait_timeout", "30")))
        tk.Entry(r2, textvariable=self.timeout_var, width=4, font=('Arial', 9)).pack(side=tk.LEFT, padx=3)

        tk.Label(r2, text="相似度:", font=('Arial', 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.threshold_var = tk.StringVar(value=str(self.config.get("threshold", "0.9")))
        tk.Entry(r2, textvariable=self.threshold_var, width=4, font=('Arial', 9)).pack(side=tk.LEFT, padx=3)

        btn_frame = tk.Frame(main)
        btn_frame.pack(fill='x', pady=5)
        self.save_btn = tk.Button(btn_frame, text="💾 儲存", command=self.save_current_config, width=8)
        self.save_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.start_btn = tk.Button(btn_frame, text="▶ 開始", command=self.start_bot, width=8, bg='lightgreen')
        self.start_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.stop_btn = tk.Button(btn_frame, text="⏹ 停止(F10)", command=self.stop_bot, state=tk.DISABLED, width=10, bg='salmon')
        self.stop_btn.pack(side=tk.LEFT, padx=5, expand=True)

        # -- 日誌 --
        log_lf = tk.LabelFrame(main, text="日誌", font=('Arial', 9, 'bold'), padx=3, pady=2)
        log_lf.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_lf, height=8, font=('Arial', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes('-topmost', self.topmost)
        if self.topmost:
            self.topmost_btn.config(bg='lightgreen', relief='sunken')
            self.log('視窗置頂已開啟')
        else:
            self.topmost_btn.config(bg='SystemButtonFace', relief='raised')
            self.log('視窗置頂已關閉')
        self.config["topmost"] = self.topmost
        save_config(self.config)

    def log(self, message):
        def append():
            timestamp = time.strftime('%H:%M:%S')
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
        self.root.after(0, append)

    def start_capture_image(self):
        """先嘗試全螢幕截圖 overlay；如果環境不支援則改用瀏覽圖檔方式"""
        self.root.withdraw()
        self.root.update()
        self.root.after(180, self._open_crop_overlay)

    def _open_crop_overlay(self):
        try:
            FriendCropOverlay(self.root, self, self._on_crop_complete)
        except Exception as e:
            self.root.deiconify()
            self.log(f"⚠️ 展開截圖視窗失敗: {e}，請改用「瀏覽圖檔」功能")
            self.browse_reward_image()

    def _on_crop_complete(self, success, msg):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if success:
            self.log("✨ 獎勵截圖已更新！")

    def browse_reward_image(self):
        """開啟檔案瀏覽對話框，讓使用者手動選取已截的獎勵圖檔"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="選取「獲得獎勵」彈窗截圖",
            filetypes=[("PNG 圖片", "*.png"), ("所有圖片", "*.png;*.jpg;*.bmp")]
        )
        if path:
            import shutil
            save_path = os.path.join(IMAGE_DIR, "friend_challenge_reward.png")
            if not os.path.exists(IMAGE_DIR):
                os.makedirs(IMAGE_DIR)
            # 如果選的不是 PNG 就轉換
            try:
                from PIL import Image as PILImg
                img = PILImg.open(path).convert('RGB')
                img.save(save_path, 'PNG')
                self.log(f"✨ 已將選取的圖檔複製為獎勵截圖！({img.width}x{img.height}px)")
            except Exception as e:
                self.log(f"❌ 圖檔處理失敗: {e}")

    def start_capture_wolf(self):
        if self.capturing: return
        self.root.focus_set() # 移除輸入框焦點
        self.capturing = True
        self.capture_mode = 'wolf_p1'
        self.temp_p1 = None
        self.log("【定位】請將滑鼠移至底部【第 1 隻狼】頭像中心，按 K 鍵確認 (ESC取消)")
        self.capture_listener = pynput.keyboard.Listener(on_press=self.on_capture_key)
        self.capture_listener.start()

    def start_capture_friend(self):
        if self.capturing: return
        self.root.focus_set() # 移除輸入框焦點
        self.capturing = True
        self.capture_mode = 'friend_p1'
        self.temp_p1 = None
        self.log("【定位】請將滑鼠移至好友列表【第 1 位好友】頭像中心，按 K 鍵確認 (ESC取消)")
        self.capture_listener = pynput.keyboard.Listener(on_press=self.on_capture_key)
        self.capture_listener.start()

    def start_capture(self, key_name, display_name):
        if self.capturing: return
        self.root.focus_set() # 移除輸入框焦點
        self.capturing = True
        self.capture_mode = key_name
        self.log(f"【定位】滑鼠移至「{display_name}」並按 K 鍵確認 (ESC取消)")
        self.capture_listener = pynput.keyboard.Listener(on_press=self.on_capture_key)
        self.capture_listener.start()

    def on_capture_key(self, key):
        if not self.capturing: return False
        
        if key == pynput.keyboard.Key.esc:
            self.root.after(0, self.stop_capture)
            return False
            
        try:
            char = getattr(key, 'char', None)
            if char and char.lower() == 'k':
                x, y = pyautogui.position()
                ix, iy = int(x), int(y)
                
                if self.capture_mode == 'wolf_p1':
                    self.temp_p1 = (ix, iy)
                    self.capture_mode = 'wolf_p2'
                    self.root.after(0, lambda: self.log(f"✔ 獲取第 1 隻狼中心: ({ix}, {iy})"))
                    self.root.after(0, lambda: self.log("請將滑鼠移至底部【第 8 隻狼】頭像中心，按 K 鍵確認"))
                    return True
                elif self.capture_mode == 'wolf_p2':
                    p2 = (ix, iy)
                    self.root.after(0, lambda: self.generate_wolf_slots(self.temp_p1, p2))
                    self.root.after(0, self.stop_capture)
                    return False
                elif self.capture_mode == 'friend_p1':
                    self.temp_p1 = (ix, iy)
                    self.capture_mode = 'friend_p2'
                    self.root.after(0, lambda: self.log(f"✔ 獲取第 1 位好友中心: ({ix}, {iy})"))
                    self.root.after(0, lambda: self.log("請將滑鼠移至好友列表【第 6 位好友】頭像中心，按 K 鍵確認"))
                    return True
                elif self.capture_mode == 'friend_p2':
                    p2 = (ix, iy)
                    self.root.after(0, lambda: self.generate_friend_slots(self.temp_p1, p2))
                    self.root.after(0, self.stop_capture)
                    return False
                elif self.capture_mode == 'auto_queue_coord':
                    self.aq_x.set(str(ix))
                    self.aq_y.set(str(iy))
                else:
                    vx, vy = self.coord_vars[self.capture_mode]
                    vx.set(str(ix))
                    vy.set(str(iy))
                    
                self.root.after(0, lambda: self.log(f"✔ 成功獲取座標: ({ix}, {iy})"))
                self.root.after(0, self.stop_capture)
                return False
        except Exception:
            pass
        return True

    def capture_full_screen_gdi(self):
        """使用 GDI 截取遊戲座標所在螢幕的完整畫面（移植自 wolf_mine_speedup.py）"""
        try:
            monitors = win32api.EnumDisplayMonitors()
            target_device = None
            target_w, target_h = 0, 0
            m_left, m_top = 0, 0

            # 依據任何已設定的座標判定螢幕
            pt = None
            coords = self.config.get("coordinates", [])
            if coords: pt = coords[0]
            if not pt:
                cur_pt = wintypes.POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(cur_pt)):
                    pt = (cur_pt.x, cur_pt.y)

            if pt and monitors:
                px, py = pt
                for hMonitor, hdcMonitor, rMonitor in monitors:
                    m_info = win32api.GetMonitorInfo(hMonitor)
                    m_rect = m_info['Monitor']
                    if m_rect[0] <= px <= m_rect[2] and m_rect[1] <= py <= m_rect[3]:
                        target_device = m_info['Device']
                        m_left = m_rect[0]
                        m_top = m_rect[1]
                        target_w = m_rect[2] - m_rect[0]
                        target_h = m_rect[3] - m_rect[1]
                        break

            if not target_device and monitors:
                m_info = win32api.GetMonitorInfo(monitors[0][0])
                target_device = m_info['Device']
                m_rect = m_info['Monitor']
                m_left = m_rect[0]
                m_top = m_rect[1]
                target_w = m_rect[2] - m_rect[0]
                target_h = m_rect[3] - m_rect[1]

            gdi32 = ctypes.windll.gdi32
            hdc_screen = gdi32.CreateDCW(target_device, None, None, None)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, target_w, target_h)
            gdi32.SelectObject(hdc_mem, hbmp)
            SRCCOPY = 0x00CC0020
            gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, SRCCOPY)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                            ("biClrImportant", wintypes.DWORD)]
            class BITMAPINFO(ctypes.Structure):
                _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 1)]

            bi = BITMAPINFO()
            bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bi.bmiHeader.biWidth = target_w
            bi.bmiHeader.biHeight = -target_h
            bi.bmiHeader.biPlanes = 1
            bi.bmiHeader.biBitCount = 32
            bi.bmiHeader.biCompression = 0

            buf = ctypes.create_string_buffer(target_w * target_h * 4)
            gdi32.GetDIBits(hdc_mem, hbmp, 0, target_h, buf, ctypes.byref(bi), 0)
            img = np.frombuffer(buf, dtype=np.uint8).reshape((target_h, target_w, 4))
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            gdi32.DeleteDC(hdc_screen)

            return img_bgr, m_left, m_top, target_w, target_h
        except Exception as e:
            self.log(f"GDI全螢幕截圖失敗: {e}")
            return None, 0, 0, 0, 0

    def generate_wolf_slots(self, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        slots = []
        for i in range(8):
            ratio = i / 7.0
            cx = int(x1 + (x2 - x1) * ratio)
            cy = int(y1 + (y2 - y1) * ratio)
            slots.append((cx, cy))
        self.config["wolf_slots"] = slots
        self.lbl_wolf_slots.config(text="(8/8 點)", fg="green")
        self.log("✨ 成功由兩點生成 8 個狼槽座標！")
        self.save_current_config()

    def generate_friend_slots(self, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        slots = []
        for i in range(6):
            ratio = i / 5.0
            cx = int(x1 + (x2 - x1) * ratio)
            cy = int(y1 + (y2 - y1) * ratio)
            slots.append((cx, cy))
        self.config["coordinates"] = slots
        self.lbl_friend_coords.config(text="(6/6 點)", fg="green")
        self.log("✨ 成功由兩點生成 6 個好友座標！")
        self.save_current_config()

    def stop_capture(self):
        if self.capture_listener:
            try: self.capture_listener.stop()
            except: pass
        self.capturing = False
        self.capture_mode = None
        self.log("結束座標擷取")

    def save_current_config(self):
        try:
            self.config["wolf_friends"] = self.wolf_friends_var.get().strip()
            self.config["defense_friends"] = self.defense_friends_var.get().strip()
            self.config["dispatch_mode"] = self.dispatch_mode_var.get()
            self.config["dispatch_wolves"] = self.dispatch_wolves_var.get().strip()
            
            for key, (var_x, var_y) in self.coord_vars.items():
                self.config[key] = [int(var_x.get()), int(var_y.get())]
                
            self.config["auto_queue_coord"] = [int(self.aq_x.get()), int(self.aq_y.get())]
            self.config["load_delay"] = self.load_delay_var.get().strip()
            self.config["action_delay"] = self.action_delay_var.get().strip()
            self.config["initial_delay"] = self.initial_delay_var.get().strip()
            self.config["poll_interval"] = self.poll_interval_var.get().strip()
            self.config["wait_timeout"] = self.timeout_var.get().strip()
            self.config["threshold"] = self.threshold_var.get().strip()
            self.config["topmost"] = self.topmost
            
            save_config(self.config)
            self.log("設定已儲存。")
        except ValueError:
            messagebox.showerror("錯誤", "座標必須是整數！")

    def parse_friends(self):
        wolf_list = []
        defense_list = []
        try:
            if self.config["wolf_friends"]:
                wolf_list = [int(x.strip()) for x in self.config["wolf_friends"].split(',')]
        except: self.log("警告: 挑戰狼編號解析失敗")
            
        try:
            if self.config["defense_friends"]:
                defense_list = [int(x.strip()) for x in self.config["defense_friends"].split(',')]
        except: self.log("警告: 挑戰防線編號解析失敗")
            
        tasks = []
        for w in wolf_list: tasks.append((w, 'wolf'))
        for d in defense_list: tasks.append((d, 'defense'))
        tasks.sort(key=lambda x: x[0])
        return tasks

    def start_bot(self):
        if self.running: return
        self.save_current_config()
        self.tasks = self.parse_friends()
        if not self.tasks:
            messagebox.showwarning("警告", "未設定任何有效的好友編號！")
            return
            
        # 啟動前進行截圖檔案健康檢查
        reward_img = os.path.join(IMAGE_DIR, "friend_challenge_reward.png")
        if os.path.exists(reward_img):
            try:
                from PIL import Image
                with Image.open(reward_img) as img:
                    img.verify()
                if os.path.getsize(reward_img) < 200:
                    self.log("⚠️ 警告：獎勵截圖檔案異常過小，可能會導致辨識失敗，建議重新擷取！")
            except Exception:
                self.log("⚠️ 警告：偵測到獎勵截圖檔案已損壞，將改為盲等模式。強烈建議點擊【📸 兩點框選截圖】重新設定！")
        else:
            self.log("⚠️ 提示：未設定獎勵截圖，將改為盲等模式。建議點擊【📸 兩點框選截圖】設定！")
            
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("▶ 開始自動挑戰...")
        
        self.thread = threading.Thread(target=self.bot_loop, daemon=True)
        self.thread.start()

    def stop_bot(self):
        if not self.running: return
        self.running = False
        self.log("⏹ 正在停止...")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def click_coord(self, coord, name=""):
        if not self.running: return False
        x, y = coord
        pyautogui.leftClick(x, y)
        self.log(f"點擊: {name} ({x}, {y})")
        return True

    def bot_loop(self):
        try:
            load_delay = float(self.config.get("load_delay", 3))
            delay = float(self.config.get("action_delay", 1.5))
            initial_delay = float(self.config.get("initial_delay", 10))
            poll_interval = float(self.config.get("poll_interval", 1))
            timeout = int(self.config.get("wait_timeout", 30))
            threshold = float(self.config.get("threshold", 0.9))
            friend_coords = self.config["coordinates"]
            
            if not friend_coords or len(friend_coords) < 6:
                self.log("❌ 錯誤: 好友座標數量不足，請重新擷取 (第1位及第6位)！")
                return

            per_page = len(friend_coords)
            current_page = 1
            
            for target_idx, task_type in self.tasks:
                if not self.running: break
                    
                target_page = ((target_idx - 1) // per_page) + 1
                pos_in_page = (target_idx - 1) % per_page
                
                while current_page < target_page and self.running:
                    self.click_coord(self.config["next_page_coord"], f"下一頁 (前往第{target_page}頁)")
                    time.sleep(delay)
                    current_page += 1
                
                if not self.running: break
                    
                type_name = '挑戰狼' if task_type == 'wolf' else '挑戰防線'
                self.log(f"--- 處理好友 #{target_idx} [{type_name}] ---")
                
                self.click_coord(friend_coords[pos_in_page], f"好友 #{target_idx}")
                self.log(f"等待好友家園載入 ({load_delay} 秒)...")
                time.sleep(load_delay)
                
                if task_type == 'wolf':
                    self.click_coord(self.config["camp_coord"], "馴化營")
                else:
                    self.click_coord(self.config["defense_coord"], "防線")
                time.sleep(delay)
                
                self.click_coord(self.config["challenge_btn_coord"], "挑戰")
                time.sleep(delay)
                
                if task_type == 'defense':
                    dispatch_mode = self.config.get("dispatch_mode", "auto")
                    if dispatch_mode == "auto":
                        aq = self.config.get("auto_queue_coord")
                        if aq:
                            self.click_coord(aq, "自動隊列")
                        time.sleep(delay)
                    else:
                        wolf_slots = self.config.get("wolf_slots", [])
                        if not wolf_slots:
                            self.log("⚠️ 警告: 未設定狼槽座標，無法派狼！")
                        else:
                            w_str = self.config.get("dispatch_wolves", "1").replace('，', ',')
                            try:
                                w_idx_list = [int(x.strip()) for x in w_str.split(',') if x.strip().isdigit()]
                            except:
                                w_idx_list = [1]
                            self.log(f"🐺 依序派出指定出戰對象: {w_idx_list}")
                            for w_idx in w_idx_list:
                                if not self.running: break
                                if 1 <= w_idx <= len(wolf_slots):
                                    self.click_coord(wolf_slots[w_idx - 1], f"第 {w_idx} 槽位")
                                    time.sleep(0.3)
                            time.sleep(delay)
                
                if not self.running: break
                
                self.click_coord(self.config["start_battle_coord"], "開始戰鬥")
                
                self.log(f"⏳ 戰鬥開始，前置等待 {initial_delay} 秒後才開始截圖...")
                time.sleep(initial_delay)
                
                self.log("🔍 開始偵測戰鬥結束(尋找獲得獎勵截圖)...")
                reward_img = os.path.join(IMAGE_DIR, "friend_challenge_reward.png")
                
                if not os.path.exists(reward_img):
                    self.log(f"⚠️ 找不到 {reward_img}，將直接等待 {timeout} 秒")
                    time.sleep(timeout)
                else:
                    elapsed = 0
                    found = False
                    
                    try:
                        from PIL import Image
                        target_img = Image.open(reward_img).convert('RGB')
                    except Exception as e:
                        self.log(f"⚠️ 圖片讀取失敗 (PIL): {e}")
                        target_img = None
                        
                    while elapsed < timeout and self.running and target_img:
                        try:
                            pos = pyautogui.locateCenterOnScreen(target_img, grayscale=False, confidence=threshold)
                            if pos:
                                self.log(f"✔ 辨識到戰鬥結算彈窗！(命中座標: {pos.x}, {pos.y})")
                                found = True
                                break
                        except pyautogui.ImageNotFoundException: pass
                        except Exception as e:
                            err_str = str(e)
                            if "Failed to read" in err_str:
                                self.log(f"⚠️ 獎勵截圖已損壞或失效，請點擊【📸 兩點框選截圖】重新設定！(將改為直接等待 {timeout} 秒)")
                            else:
                                self.log(f"圖像辨識錯誤: {err_str}")
                            time.sleep(timeout)
                            break
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                        
                    if not found and self.running:
                        self.log("等待超時，未找到獎勵截圖。")
                
                time.sleep(1)
                self.click_coord(self.config["confirm_btn_coord"], "確定(關閉彈窗)")
                time.sleep(delay)
                
                # --- 防線挑戰專屬：撤退流程 ---
                if task_type == 'defense':
                    if not self.running: break
                    self.log("🛡️ 防線挑戰結束，開始執行撤退...")
                    time.sleep(delay)
                    
                    self.click_coord(self.config.get("gohome_coord", [0,0]), "回家")
                    self.log(f"等待回城載入 ({load_delay} 秒)...")
                    time.sleep(load_delay)
                    
                    if not self.running: break
                    self.click_coord(self.config.get("territory_coord", [0,0]), "領地")
                    time.sleep(delay)
                    
                    if not self.running: break
                    self.click_coord(self.config.get("withdraw_coord", [0,0]), "撤防")
                    time.sleep(delay)
                    
                    if not self.running: break
                    self.click_coord(self.config.get("withdraw_confirm_coord", [0,0]), "撤防確定")
                    time.sleep(delay)
                
            if self.running:
                self.log("✨ === 所有挑戰任務完成 ===")
            
        except Exception as e:
            self.log(f"❌ 發生錯誤: {e}")
        finally:
            self.running = False
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))


class FriendCropOverlay(tk.Toplevel):
    """全螢幕拖曳框選截圖 overlay（完全移植自 arena_challenge.py 的 CropSelectorOverlay）"""
    def __init__(self, parent, app, callback):
        super().__init__(parent)
        self.app = app
        self.callback = callback

        img_bgr, m_left, m_top, width, height = app.capture_full_screen_gdi()
        if img_bgr is None:
            app.log("❌ 全螢幕截圖失敗，無法開啟框選視窗")
            callback(False, "截圖失敗")
            self.destroy()
            return

        self.full_screenshot = img_bgr
        self.m_left = m_left
        self.m_top = m_top
        self.width = width
        self.height = height

        self.overrideredirect(True)
        self.geometry(f"{width}x{height}+{m_left}+{m_top}")
        self.attributes('-topmost', True)

        self.canvas = tk.Canvas(self, highlightthickness=0, width=width, height=height, cursor='cross')
        self.canvas.pack(fill='both', expand=True)

        shot_h, shot_w = img_bgr.shape[:2]
        self.scale_x = shot_w / max(1, width)
        self.scale_y = shot_h / max(1, height)

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        if pil_img.size != (width, height):
            pil_img = pil_img.resize((width, height), Image.Resampling.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(pil_img)
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw')

        tip_text = "📸 拖曳滑鼠左鍵框選「獲得獎勵」彈窗 | 右鍵或 ESC 取消"
        cx = width // 2
        self.canvas.create_rectangle(cx - 280, 10, cx + 280, 42, fill='#1B5E20', outline='white', width=1)
        self.canvas.create_text(cx, 26, text=tip_text, fill="white", font=('Microsoft JhengHei', 10, 'bold'))

        self.start_x = self.start_y = None
        self.rect_id = self.tip_id = self.tip_bg_id = None

        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_motion)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.bind('<Button-3>', lambda e: self.cancel())
        self.canvas.bind('<Button-3>', lambda e: self.cancel())
        self.bind('<Escape>', lambda e: self.cancel())
        self.focus_force()

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        for rid in [self.rect_id, self.tip_bg_id, self.tip_id]:
            if rid: self.canvas.delete(rid)
        self.rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='#00E676', width=2)
        self.tip_bg_id = self.canvas.create_rectangle(event.x+8, event.y+12, event.x+85, event.y+30, fill='#212121', outline='white')
        self.tip_id = self.canvas.create_text(event.x+12, event.y+14, text="0 × 0 px", fill="#00E676", font=('Arial', 9, 'bold'), anchor='nw')

    def on_motion(self, event):
        if self.start_x is None: return
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)
        w, h = abs(event.x - self.start_x), abs(event.y - self.start_y)
        tx = max(event.x, self.start_x) + 8
        ty = max(event.y, self.start_y) + 12
        self.canvas.coords(self.tip_bg_id, tx, ty, tx + 85, ty + 18)
        self.canvas.coords(self.tip_id, tx + 4, ty + 2)
        self.canvas.itemconfig(self.tip_id, text=f"{w} × {h} px")

    def on_release(self, event):
        if self.start_x is None:
            self.cancel()
            return
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        rx1 = max(0, min(x1, x2))
        rx2 = min(self.width, max(x1, x2))
        ry1 = max(0, min(y1, y2))
        ry2 = min(self.height, max(y1, y2))
        cw, ch = rx2 - rx1, ry2 - ry1
        if cw < 6 or ch < 6:
            self.app.log("⚠️ 框選區域過小，已取消")
            self.cancel()
            return
        try:
            crop_x1 = max(0, int(round(rx1 * self.scale_x)))
            crop_x2 = min(self.full_screenshot.shape[1], int(round(rx2 * self.scale_x)))
            crop_y1 = max(0, int(round(ry1 * self.scale_y)))
            crop_y2 = min(self.full_screenshot.shape[0], int(round(ry2 * self.scale_y)))
            cropped = self.full_screenshot[crop_y1:crop_y2, crop_x1:crop_x2]
            if cropped.size == 0:
                self.app.log("❌ 裁切結果為空")
                self.cancel()
                return
            save_path = os.path.join(IMAGE_DIR, "friend_challenge_reward.png")
            success, enc = cv2.imencode('.png', cropped)
            if success:
                with open(save_path, 'wb') as f:
                    f.write(enc)
                self.app.log(f"✨ 成功截圖並儲存獎勵截圖 (尺寸: {cw}x{ch}px)")
                self.destroy()
                self.callback(True, "成功")
            else:
                raise Exception("cv2 編碼失敗")
        except Exception as e:
            self.app.log(f"❌ 截圖儲存失敗: {e}")
            self.destroy()
            self.callback(False, str(e))

    def cancel(self):
        self.destroy()
        self.callback(False, "已取消")


if __name__ == "__main__":
    root = tk.Tk()
    app = FriendChallengeApp(root)
    root.mainloop()
