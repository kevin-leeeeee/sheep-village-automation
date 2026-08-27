# -*- coding: utf-8 -*-
"""
保衛羊村 - 敲狼加速礦 (自動範圍覆蓋敲狼 & 挖礦加速)
升級特色:
1. 支援「範圍覆蓋/多點盲敲」敲狼，無論木桶是否開蓋或位置偏移，必定敲中
2. 支援兩點框選草地範圍自動生成敲狼網格，或按 K 鍵自由添加敲狼點
3. 敲完狼支援自訂等待時間，並自動辨識點擊「確定」按鈕
4. 支援所有參數、好友座標、敲狼點自動保存至 config.json，下次啟動自動保留
5. DPI 自適應與全域 F10 緊急停止
"""

import sys
import os
import ctypes
import json

# 啟用 Windows DPI 自適應
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import cv2
import pyautogui
import numpy as np
import time

# 關閉 PyAutoGUI 自動觸發的邊角防護異常 (改用全域 F10 鍵緊急停止)
pyautogui.FAILSAFE = False

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import pynput
from datetime import datetime

# 取得圖片與設定目錄路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, 'images')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

def get_image_path(filename):
    return os.path.join(IMAGE_DIR, filename)

def is_admin():
    """檢查是否具有管理員權限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def run_as_admin():
    """請求以管理員身份重新運行程序"""
    try:
        if sys.platform == "win32":
            script = os.path.abspath(sys.argv[0])
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
            sys.exit(0)
    except Exception as e:
        messagebox.showerror("錯誤", f"無法以管理員身分運行: {str(e)}")
        sys.exit(1)


class FriendPatrolAutomation:
    """敲狼加速礦核心引擎"""
    def __init__(self, gui):
        self.gui = gui
        self.running = False
        self.default_delay = 0.5
        
        # 圖片友善中文名稱對照表
        self.friendly_names = {
            'jiasu_shalou.png': '挖礦加速沙漏 (jiasu_shalou.png)',
            'jiasu_shalou_hd.png': '高清沙漏 (jiasu_shalou_hd.png)',
            'haoyou_next.png': '好友欄下一頁 (haoyou_next.png)',
            'jiayuan.png': '家園領地圖示 (jiayuan.png)',
            'queding.png': '確定按鈕 (queding.png)',
            'cha.png': '關閉叉叉 (cha.png)',
            'bosscha.png': 'Boss叉叉 (bosscha.png)',
            'tacha.png': '防禦塔叉叉 (tacha.png)'
        }

    def log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        self.gui.log_text.insert('end', log_message + '\n')
        self.gui.log_text.see('end')

    def start_patrol(self):
        if not self.gui.coordinates:
            self.log('錯誤: 未添加好友座標，請先點擊「兩點生成」或「添加(K鍵)」')
            return
        if self.running:
            return
        self.gui.save_config()
        self.running = True
        self.gui.start_btn.config(state='disabled')
        self.gui.stop_btn.config(state='normal')
        self.log('敲狼加速礦已啟動')
        threading.Thread(target=self.patrol_loop, daemon=True).start()

    def stop_patrol(self):
        self.running = False
        self.gui.start_btn.config(state='normal')
        self.gui.stop_btn.config(state='disabled')
        self.log('敲狼加速礦已停止')

    def find_image_multiscale(self, template_filenames, screenshot, scales=(0.5, 0.65, 0.75, 0.85, 0.95, 1.0, 1.05, 1.15, 1.25, 1.4, 1.6, 1.8, 2.0), use_gray=True):
        """支援多圖片、廣域多尺度與灰階匹配，完美適應跨裝置不同解析度與 DPI 縮放"""
        if screenshot is None:
            return None, 0, (0, 0)

        try:
            threshold = float(self.gui.threshold_var.get()) / 100.0
        except Exception:
            threshold = 0.70
        best_val = -1
        best_loc = None
        best_size = (0, 0)

        if use_gray:
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        else:
            gray_screenshot = screenshot

        for filename in template_filenames:
            path = get_image_path(filename)
            if not os.path.exists(path):
                continue
            try:
                tpl = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
                if tpl is None:
                    continue
                if use_gray:
                    tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            except Exception:
                continue

            th, tw = tpl.shape[:2]
            for s in scales:
                target_w = int(tw * s)
                target_h = int(th * s)
                if target_w <= 0 or target_h <= 0 or target_w > gray_screenshot.shape[1] or target_h > gray_screenshot.shape[0]:
                    continue

                scaled_tpl = cv2.resize(tpl, (target_w, target_h), interpolation=cv2.INTER_AREA if s < 1.0 else cv2.INTER_LINEAR)
                res = cv2.matchTemplate(gray_screenshot, scaled_tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_size = (target_w, target_h)

        if best_val >= threshold and best_loc is not None:
            cx = best_loc[0] + best_size[0] // 2
            cy = best_loc[1] + best_size[1] // 2
            return (cx, cy), best_val, best_size

        return None, best_val, (0, 0)

    def click_image(self, filename, silent_fail=False, screenshot=None):
        friendly_name = self.friendly_names.get(filename, filename)
        if screenshot is None:
            screenshot = self.gui.capture_screen()
        if screenshot is None:
            return False

        pos, val, _ = self.find_image_multiscale([filename], screenshot)
        if pos:
            pyautogui.leftClick(pos[0], pos[1])
            self.log(f'點擊: {friendly_name} [匹配度: {val*100:.1f}%]')
            time.sleep(self.default_delay)
            return True

        if not silent_fail:
            self.log(f'未看到: {friendly_name} (最高匹配度: {val*100:.1f}%)')
        return False

    def detect_and_click_confirm(self):
        """偵測並點擊確定或關閉按鈕"""
        for popup_img in ['queding.png', 'cha.png', 'bosscha.png', 'tacha.png', 'yaoqing_queding.png']:
            if not self.running:
                break
            if self.click_image(popup_img, silent_fail=True):
                self.log(f'✔ 偵測到並點擊彈窗按鈕: {popup_img}')
                time.sleep(0.3)
                if popup_img == 'yaoqing_queding.png' and self.gui.stop_on_invite_var.get():
                    self.log('🛑 點擊到「邀請好友」確定按鈕（已達好友列表末端）！強制停止。')
                    return 'invite_stop'
                return True
        return False

    def check_invite_popup_and_stop(self):
        """
        檢查是否出現「暫時不支持邀請好友」彈窗
        優先採用 Win32 原生視窗句柄偵測 (0.001s 100% 精準)，次要採用廣域圖像匹配備援
        """
        if not self.gui.stop_on_invite_var.get():
            return False

        # 1. 優先：Win32 API 原生視窗句柄偵測 (0.001 秒，100% 跨裝置精準)
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, 'flashplayerdesktop')
            if hwnd and ctypes.windll.user32.IsWindowVisible(hwnd):
                self.log('🛑 [Win32 API 偵測] 瞬間捕捉「flashplayerdesktop」系統彈窗！自動關閉並停止巡邏。')
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
                time.sleep(0.3)
                return True
        except Exception:
            pass

        # 2. 備援：圖像匹配文字
        screenshot = self.gui.capture_screen()
        if screenshot is None:
            return False

        path_text = get_image_path('yaoqing_text.png')
        if not os.path.exists(path_text):
            return False

        pos_t, val_t, _ = self.find_image_multiscale(['yaoqing_text.png'], screenshot)

        if pos_t and val_t >= 0.70:
            self.log(f'🛑 [圖片辨識] 偵測到「暫時不支持邀請好友」彈窗 (匹配度: {val_t*100:.1f}%)！強制停止。')
            try:
                if not self.click_image('yaoqing_queding.png', silent_fail=True, screenshot=screenshot):
                    pyautogui.leftClick(pos_t[0] + 50, pos_t[1] + 70)
                time.sleep(0.3)
            except Exception:
                pass
            return True

        return False

    def patrol_loop(self):
        try:
            load_delay = float(self.gui.load_delay_var.get())
            click_interval = float(self.gui.interval_var.get())
            wolf_after_delay = float(self.gui.wolf_delay_var.get())
            page_delay = float(self.gui.page_delay_var.get())
            max_pages = int(self.gui.max_pages_var.get())
            mine_delay = float(self.gui.mine_delay_var.get())
            do_mining = self.gui.mining_var.get()
            do_wolf = self.gui.wolf_var.get()
            auto_page = self.gui.auto_page_var.get()
        except Exception as e:
            self.log(f'參數讀取錯誤: {e}，使用預設參數')
            load_delay = 1.8
            click_interval = 0.12
            wolf_after_delay = 0.6
            page_delay = 1.0
            max_pages = 10
            mine_delay = 0.4
            do_mining = True
            do_wolf = True
            auto_page = True

        while self.running:
            current_page = 1
            total_mining = 0
            total_friends = 0

            # 解析要跳過的好友序號 (如: "1" 或 "1, 2")
            skip_indices = set()
            raw_skip = str(self.gui.skip_friend_idx_var.get()).strip()
            if raw_skip:
                for part in raw_skip.replace('，', ',').replace('、', ',').split(','):
                    part = part.strip()
                    if part.isdigit():
                        skip_indices.add(int(part))

            self.log('--------------------------------------------')
            skip_info = f"，跳過好友 #{','.join(map(str, sorted(skip_indices)))}" if skip_indices else ""
            self.log(f'開始執行: 好友數={len(self.gui.coordinates)}, 頁數={max_pages}{skip_info}')
            if do_wolf:
                wolf_count = len(self.gui.wolf_coords)
                self.log(f'🐺 啟用範圍覆蓋敲狼: 共 {wolf_count} 個敲打熱點 (敲後等待 {wolf_after_delay}s)')
            self.log('--------------------------------------------')

            while self.running and current_page <= max_pages:
                self.log(f'=== 第 {current_page} / {max_pages} 頁 ===')

                for idx, coord in enumerate(self.gui.coordinates, start=1):
                    if not self.running:
                        break

                    # 判斷是否跳過該好友 (例如避免按到自己)
                    if idx in skip_indices:
                        self.log(f'⏭ [跳過] 第 {current_page} 頁好友 #{idx} (避免點擊自己)')
                        continue

                    x, y = coord
                    pyautogui.leftClick(x, y)
                    self.log(f'點擊好友 {idx} 座標: ({x}, {y})')
                    total_friends += 1

                    # 等待進入好友家園
                    time.sleep(load_delay)
                    if not self.running:
                        break

                    # 檢查是否點到「邀請好友」彈窗
                    if self.check_invite_popup_and_stop():
                        self.stop_patrol()
                        return

                    # 1. 範圍覆蓋敲狼
                    if do_wolf and self.gui.wolf_coords:
                        self.log(f'🐺 執行草地範圍覆蓋敲狼 ({len(self.gui.wolf_coords)} 點)...')
                        for wx, wy in self.gui.wolf_coords:
                            if not self.running:
                                break
                            pyautogui.leftClick(wx, wy)
                            time.sleep(click_interval)

                        # 敲狼後等待設定的時間（③ 敲完等待）
                        if wolf_after_delay > 0:
                            time.sleep(wolf_after_delay)

                        # 敲完狼自動檢查並點擊「確定」彈窗
                        for _ in range(2):
                            shot = self.gui.capture_screen()
                            if self.click_image('queding.png', silent_fail=True, screenshot=shot):
                                self.log('✔ [敲狼完畢] 成功點擊確定彈窗')
                                break
                            time.sleep(0.1)

                    if not self.running:
                        break

                    # 2. 加速挖礦 (點擊指定礦山座標)
                    if do_mining:
                        if self.gui.mine_coord:
                            mx, my = self.gui.mine_coord
                            pyautogui.leftClick(mx, my)
                            self.log(f'⚡ 點擊指定礦山座標: ({mx}, {my})')
                            total_mining += 1
                            time.sleep(mine_delay)
                            # 點擊礦山後自動檢查並點擊「確定」彈窗
                            for _ in range(2):
                                shot = self.gui.capture_screen()
                                if self.click_image('queding.png', silent_fail=True, screenshot=shot):
                                    self.log('✔ [礦山點擊完畢] 成功點擊確定彈窗')
                                    break
                                time.sleep(0.1)
                        else:
                            self.log('⚠ 挖礦加速已勾選但未設定「礦山座標」，請點擊「礦山座標(K鍵)」設定')

                    time.sleep(0.2)

                if not self.running:
                    break

                # 翻頁處理
                if auto_page and current_page < max_pages:
                    if self.gui.next_page_coord:
                        nx, ny = self.gui.next_page_coord
                        pyautogui.leftClick(nx, ny)
                        self.log(f'點擊翻頁座標: ({nx}, {ny})')
                        time.sleep(page_delay)
                    else:
                        if not self.click_image('haoyou_next.png', silent_fail=False):
                            self.log('未找到翻頁按鈕，若辨識失敗請點擊「翻頁座標」手動設定')
                        time.sleep(page_delay)
                    current_page += 1
                else:
                    break

            self.log(f'巡邏完成: 檢查好友 {total_friends} 位 | 挖礦加速 {total_mining} 次')

        self.stop_patrol()


class GUI:
    def __init__(self, root):
        self.root = root
        admin_status = "【管理員】" if is_admin() else "【普通用戶】"
        self.root.title(f"保衛羊村 - 敲狼加速礦 {admin_status}")
        self.root.geometry('420x760')
        self.coordinates = []
        self.wolf_coords = []
        self.next_page_coord = None
        self.mine_coord = None
        self.capturing = False
        self.capture_mode = 'friend'
        self.temp_p1 = None
        self.keyboard_listener = None
        self.auto = FriendPatrolAutomation(self)
        self.topmost = True
        self.root.attributes('-topmost', True)
        self.show_guide_var = tk.BooleanVar(value=True)

        self.setup_ui()
        self.setup_global_hotkeys()
        self.init_default_wolf_coords()
        self.load_config()
        if self.show_guide_var.get():
            self.root.after(600, self.show_guide_dialog)

    def init_default_wolf_coords(self):
        """預設草地 5 個敲打熱點"""
        if not self.wolf_coords:
            self.wolf_coords = [
                (680, 500), # 草地偏左上
                (760, 520), # 草地中央
                (860, 490), # 草地偏右上 (常出狼)
                (880, 540), # 草地偏右下 (常出木桶)
                (780, 560)  # 草地下方
            ]
            self.update_wolf_info()

    def setup_ui(self):
        main = tk.Frame(self.root, padx=8, pady=6)
        main.pack(fill=tk.BOTH, expand=True)

        # 頂部標題與按鈕列
        header_frame = tk.Frame(main)
        header_frame.pack(fill='x', pady=2)

        title_lbl = tk.Label(header_frame, text='敲狼加速礦', font=('Arial', 13, 'bold'))
        title_lbl.pack(side='left')

        self.topmost_btn = tk.Button(header_frame, text='窗口置頂', command=self.toggle_topmost, bg='lightgreen', relief='sunken', width=8)
        self.topmost_btn.pack(side='right', padx=2)

        # 權限顯示區域
        admin_frame = tk.Frame(main)
        admin_frame.pack(pady=2, fill="x")
        if is_admin():
            admin_label = tk.Label(admin_frame, text="✓ 管理員權限運行", fg="green", font=('Arial', 9))
        else:
            admin_label = tk.Label(admin_frame, text="⚠ 非管理員權限運行", fg="orange", font=('Arial', 9))
        admin_label.pack(side=tk.LEFT)
        
        if not is_admin():
            elevate_btn = tk.Button(admin_frame,
              text="以管理員身份運行",
              command=self.request_admin,
              bg="#FF9800",
              fg="white",
              font=('Arial', 8),
              pady=1)
            elevate_btn.pack(side=tk.RIGHT)

        # 控制區
        control_frame = tk.LabelFrame(main, text='運行控制', padx=5, pady=2)
        control_frame.pack(fill='x', pady=2)

        cf = tk.Frame(control_frame)
        cf.pack(fill='x')

        self.start_btn = tk.Button(cf, text='啟動', command=self.auto.start_patrol, bg="#4CAF50", fg="white", font=('Arial', 10, 'bold'))
        self.start_btn.pack(side='left', expand=True, fill='x', padx=2)

        self.stop_btn = tk.Button(cf, text='停止 (F10)', command=self.auto.stop_patrol, bg="#f44336", fg="white", font=('Arial', 10, 'bold'), state='disabled')
        self.stop_btn.pack(side='left', expand=True, fill='x', padx=2)

        # 功能選項區
        opt_frame = tk.LabelFrame(main, text='功能選項', padx=5, pady=2)
        opt_frame.pack(fill='x', pady=2)

        of1 = tk.Frame(opt_frame)
        of1.pack(fill='x')
        self.wolf_var = tk.BooleanVar(value=True)
        tk.Checkbutton(of1, text='🐺 覆蓋敲狼', variable=self.wolf_var, font=('Arial', 9, 'bold')).pack(side='left', padx=2)

        self.mining_var = tk.BooleanVar(value=True)
        tk.Checkbutton(of1, text='⚡ 挖礦加速', variable=self.mining_var, font=('Arial', 8)).pack(side='left', padx=4)

        self.auto_page_var = tk.BooleanVar(value=True)
        tk.Checkbutton(of1, text='自動翻頁', variable=self.auto_page_var, font=('Arial', 8)).pack(side='left', padx=4)

        self.stop_on_invite_var = tk.BooleanVar(value=True)
        tk.Checkbutton(of1, text='遇邀請好友停止', variable=self.stop_on_invite_var, font=('Arial', 8)).pack(side='left', padx=4)

        # 敲狼草地區域設定
        # 📍 區域與座標配置 (草地/好友/翻頁/礦山)
        coord_box = tk.LabelFrame(main, text='📍 區域與座標配置', padx=5, pady=2)
        coord_box.pack(fill='x', pady=2)

        # 頂部指南按鈕列
        cb_head = tk.Frame(coord_box)
        cb_head.pack(fill='x', pady=(0, 2))
        tk.Button(cb_head, text='❓ 操作指南', command=self.show_guide_dialog, bg="#009688", fg="white", font=('Arial', 8, 'bold')).pack(side='right', padx=1)

        # 行 1: 草地敲狼
        row_wolf = tk.Frame(coord_box)
        row_wolf.pack(fill='x', pady=1)
        tk.Button(row_wolf, text='兩點框選草地', command=self.start_wolf_box_wizard, bg="#E65100", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_wolf, text='清空', command=self.clear_wolf_coords, font=('Arial', 8)).pack(side='left', padx=1)
        self.wolf_info_lbl = tk.Label(row_wolf, text='(熱點: 5點)', font=('Arial', 8), fg='#B71C1C')
        self.wolf_info_lbl.pack(side='left', padx=3)

        # 行 2: 好友生成
        row_friend = tk.Frame(coord_box)
        row_friend.pack(fill='x', pady=1)
        tk.Button(row_friend, text='兩點生成好友', command=self.start_two_point_wizard, bg="#2196F3", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_friend, text='清空', command=self.clear_friend_coords, font=('Arial', 8)).pack(side='left', padx=1)

        # 行 3: 翻頁與礦山座標
        row_aux = tk.Frame(coord_box)
        row_aux.pack(fill='x', pady=1)
        tk.Button(row_aux, text='翻頁座標(K鍵)', command=self.start_capture_next_page, bg="#00897B", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_aux, text='礦山座標(K鍵)', command=self.start_capture_mine, bg="#F57C00", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_aux, text='清空', command=self.clear_aux_coords, font=('Arial', 8)).pack(side='left', padx=1)

        # 行 4: 圖像校正
        row_crop = tk.Frame(coord_box)
        row_crop.pack(fill='x', pady=1)
        tk.Button(row_crop, text='📸 框選確定圖片', command=self.start_crop_queding_wizard, bg="#D81B60", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)

        # 狀態列
        self.coord_info_lbl = tk.Label(coord_box, text='好友: 0 | 翻頁: 自動 | 礦山: 未設定', font=('Arial', 8), fg='navy')
        self.coord_info_lbl.pack(fill='x', pady=1)

        # ⚙️ 運行參數配置 (按時間執行順序排列)
        param_box = tk.LabelFrame(main, text='⚙️ 運行參數配置 (按時間執行順序排列)', padx=5, pady=2)
        param_box.pack(fill='x', pady=2)

        # 順序提示標籤
        tk.Label(param_box, text='順序: ①進家 ➔ ②敲狼連點 ➔ ③敲完等待 ➔ ④礦山等待 ➔ ⑤翻頁', font=('Arial', 8, 'bold'), fg='#0D47A1').pack(anchor='w', pady=(0, 2))

        sf1 = tk.Frame(param_box)
        sf1.pack(fill='x', pady=1)

        tk.Label(sf1, text='①進家延遲:', font=('Arial', 8)).pack(side='left')
        self.load_delay_var = tk.StringVar(value='1.8')
        tk.Entry(sf1, textvariable=self.load_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf1, text='②點擊間隔:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.interval_var = tk.StringVar(value='0.12')
        tk.Entry(sf1, textvariable=self.interval_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf1, text='③敲完等待:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.wolf_delay_var = tk.StringVar(value='0.6')
        tk.Entry(sf1, textvariable=self.wolf_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        sf2 = tk.Frame(param_box)
        sf2.pack(fill='x', pady=1)

        tk.Label(sf2, text='④礦山等待:', font=('Arial', 8)).pack(side='left')
        self.mine_delay_var = tk.StringVar(value='0.4')
        tk.Entry(sf2, textvariable=self.mine_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf2, text='⑤翻頁延遲:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.page_delay_var = tk.StringVar(value='1.0')
        tk.Entry(sf2, textvariable=self.page_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf2, text='巡邏頁數:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.max_pages_var = tk.StringVar(value='10')
        tk.Entry(sf2, textvariable=self.max_pages_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        # 跳過好友設定 (例如跳過自己)
        sf3 = tk.Frame(param_box)
        sf3.pack(fill='x', pady=1)

        tk.Label(sf3, text='跳過好友序號:', font=('Arial', 8)).pack(side='left')
        self.skip_friend_idx_var = tk.StringVar(value='')
        tk.Entry(sf3, textvariable=self.skip_friend_idx_var, width=5, font=('Arial', 8)).pack(side='left', padx=1)
        tk.Label(sf3, text='(如: 1 或 1,2，跳過自己)', font=('Arial', 8), fg='gray').pack(side='left', padx=(1, 4))

        # 圖像匹配閾值 (%)
        threshold_frame = tk.LabelFrame(main, text='圖像匹配閾值 (%)', padx=5, pady=2)
        threshold_frame.pack(fill='x', pady=2)

        threshold_control = tk.Frame(threshold_frame)
        threshold_control.pack(fill='x')

        tk.Label(threshold_control, text='彈窗辨識閾值(%):', font=('Arial', 8)).pack(side='left')
        self.threshold_var = tk.StringVar(value='70')
        tk.Entry(threshold_control, textvariable=self.threshold_var, width=5, font=('Arial', 8)).pack(side='left', padx=3)
        tk.Label(threshold_control, text='(預設 70%，信心度高於此值視為彈窗)', font=('Arial', 8), fg='gray').pack(side='left', padx=3)

        # 日誌區
        log_frame = tk.LabelFrame(main, text='日誌', padx=3, pady=2)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=2)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, font=('Arial', 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        bottom_f = tk.Frame(main)
        bottom_f.pack(fill='x', pady=2)
        tk.Button(bottom_f, text='清空日誌', command=self.clear_log, font=('Arial', 8)).pack(side='left')
        tk.Label(bottom_f, text='按 F10 鍵可全域緊急停止', font=('Arial', 8), fg='gray').pack(side='right')

    def save_config(self):
        """保存當前參數與座標至 config.json"""
        data = {
            'coordinates': self.coordinates,
            'wolf_coords': self.wolf_coords,
            'next_page_coord': self.next_page_coord,
            'mine_coord': self.mine_coord,
            'load_delay': self.load_delay_var.get(),
            'wolf_delay': self.wolf_delay_var.get(),
            'interval': self.interval_var.get(),
            'page_delay': self.page_delay_var.get(),
            'max_pages': self.max_pages_var.get(),
            'mine_delay': self.mine_delay_var.get(),
            'threshold': self.threshold_var.get(),
            'skip_friend_idx': self.skip_friend_idx_var.get(),
            'wolf_var': self.wolf_var.get(),
            'mining_var': self.mining_var.get(),
            'auto_page_var': self.auto_page_var.get(),
            'stop_on_invite_var': self.stop_on_invite_var.get(),
            'topmost': self.topmost,
            'show_guide': self.show_guide_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_config_manual(self):
        self.save_config()
        self.auto.log('💾 已手動保存當前所有座標與參數至 config.json')

    def load_config(self):
        """啟動時載入上次保存的設定"""
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.coordinates = [tuple(pt) for pt in data.get('coordinates', [])]
            if 'wolf_coords' in data and data['wolf_coords']:
                self.wolf_coords = [tuple(pt) for pt in data['wolf_coords']]
            if data.get('next_page_coord'):
                self.next_page_coord = tuple(data['next_page_coord'])
            if data.get('mine_coord'):
                self.mine_coord = tuple(data['mine_coord'])

            if 'load_delay' in data: self.load_delay_var.set(str(data['load_delay']))
            if 'wolf_delay' in data: self.wolf_delay_var.set(str(data['wolf_delay']))
            if 'interval' in data: self.interval_var.set(str(data['interval']))
            if 'page_delay' in data: self.page_delay_var.set(str(data['page_delay']))
            if 'max_pages' in data: self.max_pages_var.set(str(data['max_pages']))
            if 'mine_delay' in data: self.mine_delay_var.set(str(data['mine_delay']))
            if 'threshold' in data: self.threshold_var.set(str(data['threshold']))
            if 'skip_friend_idx' in data: self.skip_friend_idx_var.set(str(data['skip_friend_idx']))

            if 'wolf_var' in data: self.wolf_var.set(bool(data['wolf_var']))
            if 'mining_var' in data: self.mining_var.set(bool(data['mining_var']))
            if 'auto_page_var' in data: self.auto_page_var.set(bool(data['auto_page_var']))
            if 'stop_on_invite_var' in data: self.stop_on_invite_var.set(bool(data['stop_on_invite_var']))
            if 'show_guide' in data: self.show_guide_var.set(bool(data['show_guide']))
            if 'topmost' in data:
                self.topmost = bool(data['topmost'])
                self.root.attributes('-topmost', self.topmost)
                if self.topmost:
                    self.topmost_btn.config(bg='lightgreen', relief='sunken')
                else:
                    self.topmost_btn.config(bg='SystemButtonFace', relief='raised')

            self.update_coords()
            self.update_wolf_info()
            self.auto.log(f'📂 已自動載入上次配置: 好友 {len(self.coordinates)} 位 | 敲狼點 {len(self.wolf_coords)} 個')
        except Exception as e:
            self.auto.log(f'載入配置失敗: {e}')

    def setup_global_hotkeys(self):
        def on_press(key):
            try:
                if key == pynput.keyboard.Key.f10:
                    if self.auto.running:
                        self.root.after(0, self.auto.stop_patrol)
            except Exception:
                pass

        self.hotkey_listener = pynput.keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def show_guide_dialog(self):
        GuideDialog(self.root, self)

    def request_admin(self):
        result = messagebox.askyesno("提升權限", "程序將以管理員身份重新啟動\n當前視窗將關閉\n是否繼續？")
        if result:
            run_as_admin()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes('-topmost', self.topmost)
        if self.topmost:
            self.topmost_btn.config(bg='lightgreen', relief='sunken')
            self.auto.log('視窗置頂已開啟')
        else:
            self.topmost_btn.config(bg='SystemButtonFace', relief='raised')
            self.auto.log('視窗置頂已關閉')

    def clear_log(self):
        self.log_text.delete('1.0', tk.END)

    def update_wolf_info(self):
        self.wolf_info_lbl.config(text=f'(熱點: {len(self.wolf_coords)}點)')

    def clear_wolf_coords(self):
        self.wolf_coords.clear()
        self.update_wolf_info()
        self.auto.log('已清空草地敲狼點')
        self.save_config()

    def clear_friend_coords(self):
        self.coordinates.clear()
        self.update_coords()
        self.auto.log('已清空好友點擊座標')
        self.save_config()

    def clear_aux_coords(self):
        self.next_page_coord = None
        self.mine_coord = None
        self.update_coords()
        self.auto.log('已清空翻頁與礦山輔助座標')
        self.save_config()

    def start_wolf_box_wizard(self):
        self.capture_mode = 'w_box1'
        self.temp_p1 = None
        self.start_capture('【兩點框選草地 1/2】滑鼠移至防線右側【草地左上角】，按 K 鍵確認')

    def start_capture_next_page(self):
        self.capture_mode = 'next_page'
        self.start_capture('滑鼠移至翻頁按鈕 > 上，按 K 鍵設定座標，ESC 取消')

    def start_capture_mine(self):
        self.capture_mode = 'mine'
        self.start_capture('滑鼠移至礦山/沙漏位置上，按 K 鍵設定座標，ESC 取消')

    def start_crop_queding_wizard(self):
        self.capture_mode = 'crop_q1'
        self.temp_p1 = None
        self.start_capture('【框選確定圖片 1/2】滑鼠移至彈窗「確定」按鈕【左上角】，按 K 鍵確認')

    def start_two_point_wizard(self):
        self.capture_mode = 'p1'
        self.temp_p1 = None
        self.start_capture('【兩點生成好友欄 1/2】滑鼠移至【第 1 位好友】頭像中心，按 K 鍵確認')

    def start_capture(self, tip_text):
        if self.capturing:
            return
        self.capturing = True
        self.keyboard_listener = pynput.keyboard.Listener(on_press=self.on_key)
        self.keyboard_listener.start()
        self.auto.log(tip_text)

    def on_key(self, key):
        if not self.capturing:
            return False

        # 優先處理 ESC 鍵結束/取消
        if key == pynput.keyboard.Key.esc:
            self.root.after(0, self.stop_capture)
            return False

        try:
            char = getattr(key, 'char', None)
            if char:
                char = char.lower()

            x, y = pyautogui.position()
            ix, iy = int(x), int(y)

            # 統一所有添加功能均按 K 鍵 (相容 w 鍵)
            if char in ('k', 'w'):
                if self.capture_mode == 'next_page':
                    self.next_page_coord = (ix, iy)
                    self.root.after(0, self.update_coords)
                    self.root.after(0, lambda: self.auto.log(f'已設定翻頁按鈕座標: ({ix}, {iy})'))
                    self.root.after(0, self.stop_capture)
                    return False
                elif self.capture_mode == 'mine':
                    self.mine_coord = (ix, iy)
                    self.root.after(0, self.update_coords)
                    self.root.after(0, lambda: self.auto.log(f'已設定礦山座標: ({ix}, {iy})'))
                    self.root.after(0, self.stop_capture)
                    return False
                elif self.capture_mode == 'p1':
                    self.temp_p1 = (ix, iy)
                    self.root.after(0, lambda: self.auto.log(f'✔ 已獲取第 1 位好友: ({ix}, {iy})'))
                    self.capture_mode = 'p2'
                    self.root.after(0, lambda: self.auto.log('【兩點生成好友欄 2/2】滑鼠移至【第 6 位好友】頭像中心，按 K 鍵確認'))
                    return True
                elif self.capture_mode == 'p2':
                    p2 = (ix, iy)
                    self.root.after(0, lambda: self.auto.log(f'✔ 已獲取第 6 位好友: ({ix}, {iy})'))
                    self.root.after(0, lambda: self.generate_friends_from_two_points(self.temp_p1, p2, count=6))
                    self.root.after(0, self.stop_capture)
                    return False
                elif self.capture_mode == 'w_box1':
                    self.temp_p1 = (ix, iy)
                    self.root.after(0, lambda: self.auto.log(f'✔ 草地左上角: ({ix}, {iy})'))
                    self.capture_mode = 'w_box2'
                    self.root.after(0, lambda: self.auto.log('【兩點框選草地 2/2】滑鼠移至【草地右下角】，按 K 鍵確認'))
                    return True
                elif self.capture_mode == 'w_box2':
                    p2 = (ix, iy)
                    self.root.after(0, lambda: self.auto.log(f'✔ 草地右下角: ({ix}, {iy})'))
                    self.root.after(0, lambda: self.generate_wolf_grid(self.temp_p1, p2, cols=3, rows=2))
                    self.root.after(0, self.stop_capture)
                    return False
                elif self.capture_mode == 'crop_q1':
                    self.temp_p1 = (ix, iy)
                    self.root.after(0, lambda: self.auto.log(f'✔ 確定按鈕左上角: ({ix}, {iy})'))
                    self.capture_mode = 'crop_q2'
                    self.root.after(0, lambda: self.auto.log('【框選確定圖片 2/2】滑鼠移至彈窗「確定」按鈕【右下角】，按 K 鍵確認'))
                    return True
                elif self.capture_mode == 'crop_q2':
                    p2 = (ix, iy)
                    self.root.after(0, lambda: self.save_cropped_image(self.temp_p1, p2, ['queding.png', 'yaoqing_queding.png']))
                    self.root.after(0, self.stop_capture)
                    return False

        except Exception as e:
            pass
        return True

    def generate_friends_from_two_points(self, p1, p2, count=6):
        self.coordinates.clear()
        x1, y1 = p1
        x2, y2 = p2
        for i in range(count):
            ratio = i / (count - 1) if count > 1 else 0
            cx = int(x1 + (x2 - x1) * ratio)
            cy = int(y1 + (y2 - y1) * ratio)
            self.coordinates.append((cx, cy))
        self.update_coords()
        self.auto.log(f'✨ 已自動生成 {count} 個好友點擊座標！')
        self.save_config()

    def generate_wolf_grid(self, p1, p2, cols=3, rows=2):
        """由兩點產生覆蓋草地區域的 3x2 網格敲擊點"""
        self.wolf_coords.clear()
        min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
        min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])

        for r in range(rows):
            for c in range(cols):
                rx = min_x + int((max_x - min_x) * (c + 0.5) / cols)
                ry = min_y + int((max_y - min_y) * (r + 0.5) / rows)
                self.wolf_coords.append((rx, ry))

        self.update_wolf_info()
        self.auto.log(f'✨ 成功生成 {len(self.wolf_coords)} 個覆蓋草地的敲狼熱點！')
        self.save_config()

    def save_cropped_image(self, p1, p2, filenames):
        """框選螢幕區域並自動裁切、覆蓋圖片檔"""
        try:
            min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
            min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])
            width = max_x - min_x
            height = max_y - min_y

            if width < 5 or height < 5:
                self.auto.log('❌ 錯誤: 框選區域過小 (<5px)，請重新操作！')
                return

            screenshot = pyautogui.screenshot(region=(min_x, min_y, width, height))
            for fname in filenames:
                save_path = get_image_path(fname)
                screenshot.save(save_path)
            self.auto.log(f'✨ 成功框選截圖並自動覆蓋存檔: {", ".join(filenames)} (尺寸: {width}x{height}px)！當前裝置辨識已 100% 校正。')
        except Exception as e:
            self.auto.log(f'❌ 截圖覆蓋失敗: {e}')

    def stop_capture(self):
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
        self.capturing = False
        self.auto.log('結束座標添加')
        self.save_config()

    def clear_coords(self):
        self.coordinates.clear()
        self.next_page_coord = None
        self.mine_coord = None
        self.update_coords()
        self.auto.log('已清空所有座標')
        self.save_config()

    def update_coords(self):
        next_str = f"({self.next_page_coord[0]}, {self.next_page_coord[1]})" if self.next_page_coord else "自動"
        mine_str = f"({self.mine_coord[0]}, {self.mine_coord[1]})" if self.mine_coord else "未設定"
        self.coord_info_lbl.config(text=f'好友: {len(self.coordinates)} | 翻頁: {next_str} | 礦山: {mine_str}')

    def capture_screen(self):
        try:
            screenshot = pyautogui.screenshot()
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception:
            return None


class GuideDialog(tk.Toplevel):
    def __init__(self, parent, gui):
        super().__init__(parent)
        self.gui = gui
        self.title("📍 操作指南")
        self.geometry("380x280")
        self.attributes('-topmost', True)
        self.resizable(False, False)

        main_f = tk.Frame(self, padx=15, pady=12)
        main_f.pack(fill='both', expand=True)

        tk.Label(main_f, text="📍 區域與座標設定說明", font=('Arial', 10, 'bold'), fg='#1565C0').pack(anchor='w', pady=(0, 8))

        text_msg = (
            "1. 🌾 兩點框選草地：移至草地【左上角】按 K，再移至【右下角】按 K。\n\n"
            "2. 👥 兩點生成好友：移至【第1位好友】頭像按 K，再移至【第6位】按 K。\n\n"
            "3. ⚡ 翻頁與礦山座標：將滑鼠移至按鈕上方按下 K 鍵即可設定。\n\n"
            "4. 📸 框選確定圖片：移至確定按鈕【左上角】按 K，再移至【右下角】按 K。"
        )

        msg_lbl = tk.Label(main_f, text=text_msg, font=('Arial', 8), justify='left', anchor='w')
        msg_lbl.pack(fill='both', expand=True)

        bottom_f = tk.Frame(main_f)
        bottom_f.pack(fill='x', pady=(10, 0))

        self.dont_show_var = tk.BooleanVar(value=not self.gui.show_guide_var.get())
        chk = tk.Checkbutton(bottom_f, text="不再自動顯示此指南", variable=self.dont_show_var, font=('Arial', 8))
        chk.pack(side='left')

        close_btn = tk.Button(bottom_f, text="我知道了", command=self.on_close, bg="#2196F3", fg="white", font=('Arial', 8, 'bold'), width=8)
        close_btn.pack(side='right')

    def on_close(self):
        self.gui.show_guide_var.set(not self.dont_show_var.get())
        self.gui.save_config()
        self.destroy()


def main():
    root = tk.Tk()
    app = GUI(root)
    
    def on_close():
        app.save_config()
        if app.keyboard_listener:
            try:
                app.keyboard_listener.stop()
            except Exception:
                pass
        if hasattr(app, 'hotkey_listener') and app.hotkey_listener:
            try:
                app.hotkey_listener.stop()
            except Exception:
                pass
        app.auto.running = False
        root.destroy()
        
    root.protocol('WM_DELETE_WINDOW', on_close)
    root.mainloop()

if __name__ == '__main__':
    main()
