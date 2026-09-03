# -*- coding: utf-8 -*-
"""
保衛羊村 - 競技場挑戰 (防守 & 進攻雙模式)
功能特色：
1. 雙模式自由切換：
   - 🛡️ 防守模式：切磋 -> 開始戰鬥 -> 戰鬥偵測 -> 抽獎 -> 確定 (預設 10 次)
   - ⚔️ 進攻模式：切磋 -> 出戰隊列派狼 (自動隊列 / 指定第 N 隻狼) -> 開始戰鬥 -> 戰鬥偵測 -> 抽獎 -> 確定 (預設 5 次)
2. 狼槽兩點生成：滑鼠移至第 1 隻與第 8 隻狼頭像按 K 鍵，自動生成 8 格精準座標！
3. 雙螢幕/多螢幕原生支援：自動判定遊戲所在螢幕，副螢幕亦能 100% 精準截圖辨識！
4. 智慧戰鬥偵測：點擊開始戰鬥後前置等待 10 秒，之後每 1 秒辨識一次「勝利/失敗/抽獎」畫面，打完立即結算！
5. 抽獎二段式操作：點擊觸發洗牌 -> 等待洗牌動畫 -> 再次點擊翻牌抽獎！
6. 自動保存配置至 arena_config.json
7. 視窗置頂與 F10 全域緊急停止
"""

import sys
import os
import ctypes
from ctypes import wintypes
import json
import time
import threading
from datetime import datetime

# 啟用 Windows DPI 自適應
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import cv2
import numpy as np
import pyautogui
pyautogui.FAILSAFE = False

import win32api
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import pynput

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, 'images')
CONFIG_FILE = os.path.join(BASE_DIR, 'arena_config.json')

def get_image_path(filename):
    return os.path.join(IMAGE_DIR, filename)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def run_as_admin():
    try:
        if sys.platform == "win32":
            script = os.path.abspath(sys.argv[0])
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
            sys.exit(0)
    except Exception as e:
        messagebox.showerror("錯誤", f"無法以管理員身分運行: {str(e)}")
        sys.exit(1)


class ArenaDefenseAutomation:
    def __init__(self, gui):
        self.gui = gui
        self.running = False
        self.detected_monitor_name = None

    def log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        self.gui.log_text.insert('end', log_message + '\n')
        self.gui.log_text.see('end')

    def capture_screen(self):
        """多螢幕智慧截圖：自動鎖定遊戲座標所在螢幕 (GDI 原生設備截圖)"""
        try:
            monitors = win32api.EnumDisplayMonitors()
            target_device = None
            target_w, target_h = 0, 0

            # 依據已設定的切磋或戰鬥座標判定螢幕
            pt = (self.gui.coords.get('spar_attack') if self.gui.mode_var.get() == 'attack' else None) or \
                 self.gui.coords.get('spar_defense') or \
                 self.gui.coords.get('spar') or \
                 self.gui.coords.get('start_battle')

            if pt and monitors:
                px, py = pt
                for hMonitor, hdcMonitor, rMonitor in monitors:
                    m_info = win32api.GetMonitorInfo(hMonitor)
                    m_rect = m_info['Monitor']
                    if m_rect[0] <= px <= m_rect[2] and m_rect[1] <= py <= m_rect[3]:
                        target_device = m_info['Device']
                        target_w = m_rect[2] - m_rect[0]
                        target_h = m_rect[3] - m_rect[1]
                        break

            if not target_device and monitors:
                m_info = win32api.GetMonitorInfo(monitors[0][0])
                target_device = m_info['Device']
                m_rect = m_info['Monitor']
                target_w = m_rect[2] - m_rect[0]
                target_h = m_rect[3] - m_rect[1]

            if not target_device or target_w <= 0 or target_h <= 0:
                shot = pyautogui.screenshot()
                return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

            if target_device != self.detected_monitor_name:
                self.detected_monitor_name = target_device
                self.log(f"🖥️ 自動鎖定遊戲螢幕: {target_device} ({target_w}x{target_h})")

            gdi32 = ctypes.windll.gdi32
            hdc_screen = gdi32.CreateDCW(target_device, None, None, None)
            if not hdc_screen:
                shot = pyautogui.screenshot()
                return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, target_w, target_h)
            gdi32.SelectObject(hdc_mem, hbmp)

            SRCCOPY = 0x00CC0020
            ret = gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, SRCCOPY)

            img_bgr = None
            if ret:
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", wintypes.DWORD),
                        ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD),
                    ]
                class BITMAPINFO(ctypes.Structure):
                    _fields_ = [
                        ("bmiHeader", BITMAPINFOHEADER),
                        ("bmiColors", wintypes.DWORD * 1)
                    ]

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

            return img_bgr

        except Exception as e:
            self.log(f"截圖異常 ({e})，使用通用截圖備援")
            try:
                shot = pyautogui.screenshot()
                return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
            except Exception:
                return None

    def find_image_multiscale(self, template_filenames, screenshot, scales=(0.6, 0.75, 0.85, 0.95, 1.0, 1.05, 1.15, 1.25, 1.4), use_gray=True):
        """跨解析度與 DPI 縮放圖像匹配"""
        if screenshot is None:
            return None, 0, (0, 0)

        threshold = 0.65
        best_val = -1
        best_loc = None
        best_size = (0, 0)

        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY) if use_gray else screenshot

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

    def start(self):
        mode = self.gui.mode_var.get()
        mode_title = "進攻模式" if mode == 'attack' else "防守模式"

        # 檢查切磋座標
        spar_pt = self.gui.get_current_spar_coord()
        if not spar_pt:
            self.log(f"❌ 錯誤: 請先設定【{mode_title}】的「切磋座標」！")
            messagebox.showwarning("提示", f"請先設定【{mode_title}】的「切磋座標」！")
            return

        if not self.gui.coords.get('start_battle'):
            self.log("❌ 錯誤: 請先設定「開始戰鬥」座標！")
            messagebox.showwarning("提示", "請先設定「開始戰鬥」座標！")
            return

        # 進攻模式專屬檢查
        if mode == 'attack':
            if not self.gui.coords.get('attack_challenge'):
                self.log("❌ 錯誤: 進攻模式尚未設定「挑戰按鈕座標」！")
                messagebox.showwarning("提示", "請先設定進攻專屬的「切磋後挑戰按鈕 (K鍵)」！")
                return

            disp_mode = self.gui.dispatch_mode_var.get()
            if disp_mode == 'auto' and not self.gui.coords.get('auto_queue'):
                self.log("❌ 錯誤: 進攻模式選擇「自動隊列」，但尚未設定「自動隊列座標」！")
                messagebox.showwarning("提示", "請點擊「自動隊列座標 (K鍵)」進行設定！")
                return
            elif disp_mode == 'manual':
                slots = self.gui.coords.get('wolf_slots', [])
                if not slots or len(slots) < 8:
                    self.log("❌ 錯誤: 進攻模式選擇「指定狼隻」，但尚未設定狼槽座標！請先點擊「兩點生成狼槽 1~8」")
                    messagebox.showwarning("提示", "請點擊「兩點生成狼槽(1~8)」設定狼隻位置！")
                    return

        if self.running:
            return

        self.gui.save_config()
        self.running = True
        self.gui.start_btn.config(state='disabled')
        self.gui.stop_btn.config(state='normal')
        self.detected_monitor_name = None
        self.log(f"🚀 競技場【{mode_title}】自動化已啟動")
        threading.Thread(target=self.run_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.gui.start_btn.config(state='normal')
        self.gui.stop_btn.config(state='disabled')
        self.log("🛑 競技場挑戰已停止 (可隨時重新啟動)")

    def sleep_interruptible(self, seconds):
        steps = int(seconds * 10)
        for _ in range(steps):
            if not self.running:
                return False
            time.sleep(0.1)
        rem = seconds - (steps * 0.1)
        if rem > 0 and self.running:
            time.sleep(rem)
        return self.running

    def click_point(self, name, coord):
        if not self.running:
            return False
        x, y = coord
        pyautogui.leftClick(x, y)
        self.log(f"👉 點擊 {name}: ({x}, {y})")
        return True

    def wait_for_battle_end(self, initial_delay, poll_interval, max_timeout):
        self.log(f"⏳ 戰鬥等待 {initial_delay} 秒...")
        if not self.sleep_interruptible(initial_delay):
            return False

        self.log(f"🔍 開始動態偵測戰鬥結束 (每 {poll_interval} 秒辨識一次畫面)...")
        start_poll_time = time.time()

        while self.running:
            elapsed = time.time() - start_poll_time
            if elapsed > max_timeout:
                self.log(f"⚠️ 已超過最大戰鬥等待時間 ({max_timeout} 秒)，強制進入結算！")
                return True

            shot = self.capture_screen()
            
            # 優先辨識勝利、失敗或抽獎特徵
            pos_win, val_win, _ = self.find_image_multiscale(['arena_shengli.png'], shot)
            if pos_win:
                self.log(f"🏆 戰鬥結束：【勝利】！(信心度: {val_win*100:.1f}%)")
                return True

            pos_fail, val_fail, _ = self.find_image_multiscale(['arena_shibai.png'], shot)
            if pos_fail:
                self.log(f"💀 戰鬥結束：【惜敗】！(信心度: {val_fail*100:.1f}%)，進入抽獎補償結算")
                return True

            pos_chou, val_chou, _ = self.find_image_multiscale(['arena_choujiang.png'], shot)
            if pos_chou:
                self.log(f"🎁 偵測到抽獎畫面！(信心度: {val_chou*100:.1f}%)")
                return True

            if not self.sleep_interruptible(poll_interval):
                return False

        return False

    def run_loop(self):
        try:
            mode = self.gui.mode_var.get()
            total_rounds = int(self.gui.rounds_var.get())
            after_spar = float(self.gui.spar_delay_var.get())
            initial_delay = float(self.gui.battle_initial_var.get())
            poll_interval = float(self.gui.battle_poll_var.get())
            max_timeout = float(self.gui.battle_timeout_var.get())
            shuffle_delay = float(self.gui.shuffle_delay_var.get())
            after_draw = float(self.gui.draw_delay_var.get())
            after_confirm = float(self.gui.confirm_delay_var.get())
            dispatch_mode = self.gui.dispatch_mode_var.get()
        except Exception as e:
            self.log(f"⚠️ 參數讀取異常，採用預設值: {e}")
            mode = 'defense'
            total_rounds = 10
            after_spar = 2.0
            initial_delay = 10.0
            poll_interval = 1.0
            max_timeout = 50.0
            shuffle_delay = 1.2
            after_draw = 2.5
            after_confirm = 2.0
            dispatch_mode = 'auto'

        spar_pt = self.gui.get_current_spar_coord()
        attack_challenge_pt = self.gui.coords.get('attack_challenge')
        start_pt = self.gui.coords.get('start_battle')
        auto_queue_pt = self.gui.coords.get('auto_queue')
        wolf_slots = self.gui.coords.get('wolf_slots', [])
        draw_pt = self.gui.coords.get('draw')
        confirm_pt = self.gui.coords.get('confirm')

        # 解析指定狼隻編號 (如: "1" 或 "1, 2, 3")
        target_wolf_indices = []
        if mode == 'attack' and dispatch_mode == 'manual':
            raw_wolves = str(self.gui.selected_wolves_var.get()).replace('，', ',').replace('、', ',')
            for part in raw_wolves.split(','):
                part = part.strip()
                if part.isdigit():
                    w_idx = int(part)
                    if 1 <= w_idx <= len(wolf_slots):
                        target_wolf_indices.append(w_idx)
            if not target_wolf_indices:
                target_wolf_indices = [1]

        mode_name = "⚔️ 進攻模式" if mode == 'attack' else "🛡️ 防守模式"
        self.log(f"📋 開始執行【{mode_name}】，計劃進行 {total_rounds} 次挑戰")
        if mode == 'attack':
            if dispatch_mode == 'auto':
                self.log("🐺 出戰派狼策略: 【自動隊列】全派")
            else:
                self.log(f"🐺 出戰派狼策略: 【指定狼隻】派出第 {target_wolf_indices} 隻")

        for r in range(1, total_rounds + 1):
            if not self.running:
                break

            self.log("--------------------------------------------")
            self.log(f"{mode_name} 【第 {r} / {total_rounds} 次挑戰開始】")

            # 1. 點擊切磋一下
            if not self.click_point("切磋按鈕", spar_pt):
                break
            if not self.sleep_interruptible(after_spar):
                break

            # 2. 進攻模式專屬：點擊切磋後的「挑戰」按鈕進入出戰隊列
            if mode == 'attack':
                if attack_challenge_pt:
                    self.log("⚔️ 點擊切磋後的「挑戰」按鈕...")
                    if not self.click_point("挑戰按鈕", attack_challenge_pt):
                        break
                    if not self.sleep_interruptible(after_spar):
                        break
                else:
                    self.log("⚠️ 未設定進攻挑戰按鈕座標，嘗試直接進入出戰隊列")

                # 3. 派狼處理 (出戰隊列)
                if dispatch_mode == 'auto':
                    self.log("🐺 點擊「自動隊列」填滿出戰狼隻...")
                    if auto_queue_pt and not self.click_point("自動隊列按鈕", auto_queue_pt):
                        break
                    time.sleep(0.5)
                else:
                    self.log(f"🐺 依序派出指定狼隻: {target_wolf_indices} ...")
                    for w_idx in target_wolf_indices:
                        if not self.running:
                            break
                        slot_pt = wolf_slots[w_idx - 1]
                        self.log(f"👉 點擊第 {w_idx} 號狼槽: {slot_pt}")
                        pyautogui.leftClick(slot_pt[0], slot_pt[1])
                        time.sleep(0.3)
                    time.sleep(0.3)

            # 4. 點擊開始戰鬥
            if not self.click_point("開始戰鬥", start_pt):
                break

            # 4. 動態等待戰鬥結束 (自動針對遊戲螢幕辨識 勝利/失敗/抽獎)
            if not self.wait_for_battle_end(initial_delay, poll_interval, max_timeout):
                break

            # 5. 抽獎二段式流程：點擊卡片觸發洗牌 -> 等待洗牌動畫 -> 再次點擊卡片正式抽獎
            if draw_pt:
                time.sleep(0.5)
                self.log("🎴 【抽獎步驟 1/2】點擊卡片觸發洗牌...")
                if not self.click_point("抽獎卡片 (觸發洗牌)", draw_pt):
                    break

                self.log(f"⏳ 等待卡片洗牌動畫 ({shuffle_delay} 秒)...")
                if not self.sleep_interruptible(shuffle_delay):
                    break

                self.log("🎴 【抽獎步驟 2/2】再次點擊卡片正式抽獎！")
                if not self.click_point("抽獎卡片 (正式抽獎)", draw_pt):
                    break
            else:
                self.log("ℹ️ 未設定抽獎卡片座標，跳過點擊")

            if not self.sleep_interruptible(after_draw):
                break

            # 6. 點擊確定按鈕
            if confirm_pt:
                if not self.click_point("確定按鈕", confirm_pt):
                    break
            else:
                self.log("ℹ️ 未設定確定座標，跳過點擊")

            if not self.sleep_interruptible(after_confirm):
                break

            self.log(f"✔ 第 {r} 次挑戰結算完成！")

        self.log("--------------------------------------------")
        if self.running:
            self.log(f"🎉 競技場【{mode_name}】所有挑戰執行完畢！")
        self.stop()


class ArenaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("保衛羊村 - 競技場挑戰 (防守 & 進攻)")
        self.root.geometry('440x800')

        self.topmost = True
        self.root.attributes('-topmost', True)

        # 模式控制：defense (防守) / attack (進攻)
        self.mode_var = tk.StringVar(value='defense')
        self.dispatch_mode_var = tk.StringVar(value='auto')  # auto / manual
        self.selected_wolves_var = tk.StringVar(value='1')

        self.coords = {
            'spar_defense': None,
            'spar_attack': None,
            'attack_challenge': None,
            'spar': None,  # 舊設定相容
            'start_battle': None,
            'auto_queue': None,
            'wolf_slots': [],  # 8 個狼槽座標
            'draw': None,
            'confirm': None
        }

        self.capturing = False
        self.capture_key = None
        self.temp_p1 = None
        self.keyboard_listener = None

        self.auto = ArenaDefenseAutomation(self)

        self.setup_ui()
        self.setup_global_hotkeys()
        self.load_config()

    def setup_ui(self):
        main = tk.Frame(self.root, padx=8, pady=6)
        main.pack(fill=tk.BOTH, expand=True)

        # 頂部標題與置頂按鈕
        header_frame = tk.Frame(main)
        header_frame.pack(fill='x', pady=2)

        title_lbl = tk.Label(header_frame, text='競技場挑戰 (防守 & 進攻)', font=('Arial', 12, 'bold'))
        title_lbl.pack(side='left')

        self.topmost_btn = tk.Button(header_frame, text='視窗置頂', command=self.toggle_topmost, bg='lightgreen', relief='sunken', width=8)
        self.topmost_btn.pack(side='right', padx=2)

        # 權限顯示
        admin_frame = tk.Frame(main)
        admin_frame.pack(pady=1, fill="x")
        if is_admin():
            admin_label = tk.Label(admin_frame, text="✓ 管理員權限運行", fg="green", font=('Arial', 9))
        else:
            admin_label = tk.Label(admin_frame, text="⚠ 非管理員權限運行", fg="orange", font=('Arial', 9))
        admin_label.pack(side=tk.LEFT)

        if not is_admin():
            elevate_btn = tk.Button(admin_frame, text="以管理員身份運行", command=self.request_admin, bg="#FF9800", fg="white", font=('Arial', 8), pady=1)
            elevate_btn.pack(side=tk.RIGHT)

        # 🎮 模式選擇區 (防守 vs 進攻)
        mode_box = tk.LabelFrame(main, text='🎮 模式選擇', padx=5, pady=3)
        mode_box.pack(fill='x', pady=2)

        m_frame = tk.Frame(mode_box)
        m_frame.pack(fill='x')

        self.rb_defense = tk.Radiobutton(m_frame, text='🛡️ 防守模式', variable=self.mode_var, value='defense', command=self.on_mode_change, font=('Arial', 9, 'bold'), fg='#0D47A1')
        self.rb_defense.pack(side='left', padx=10)

        self.rb_attack = tk.Radiobutton(m_frame, text='⚔️ 進攻模式', variable=self.mode_var, value='attack', command=self.on_mode_change, font=('Arial', 9, 'bold'), fg='#B71C1C')
        self.rb_attack.pack(side='left', padx=10)

        # 運行控制區
        control_frame = tk.LabelFrame(main, text='運行控制', padx=5, pady=3)
        control_frame.pack(fill='x', pady=2)

        cf = tk.Frame(control_frame)
        cf.pack(fill='x')

        self.start_btn = tk.Button(cf, text='啟動挑戰', command=self.auto.start, bg="#4CAF50", fg="white", font=('Arial', 10, 'bold'))
        self.start_btn.pack(side='left', expand=True, fill='x', padx=2)

        self.stop_btn = tk.Button(cf, text='停止 (F10)', command=self.auto.stop, bg="#f44336", fg="white", font=('Arial', 10, 'bold'), state='disabled')
        self.stop_btn.pack(side='left', expand=True, fill='x', padx=2)

        # 📍 點擊座標配置區
        coord_box = tk.LabelFrame(main, text='📍 基礎座標配置 (點擊按鈕 ➔ 移至位置按 K 鍵)', padx=5, pady=3)
        coord_box.pack(fill='x', pady=2)

        # ① 切磋座標 (依模式顯示)
        r1 = tk.Frame(coord_box)
        r1.pack(fill='x', pady=1)
        self.btn_spar = tk.Button(r1, text='① 切磋座標 (K鍵)', command=self.start_capture_current_spar, bg="#2196F3", fg="white", font=('Arial', 8, 'bold'), width=17)
        self.btn_spar.pack(side='left')
        self.lbl_spar = tk.Label(r1, text='未設定', font=('Arial', 9), fg='#B71C1C')
        self.lbl_spar.pack(side='left', padx=6)

        # ② 切磋後挑戰座標 (進攻專用)
        r_chal = tk.Frame(coord_box)
        r_chal.pack(fill='x', pady=1)
        tk.Button(r_chal, text='② 切磋後挑戰(K鍵)', command=lambda: self.start_capture('attack_challenge', '移至切磋後的彈窗【挑戰按鈕】按 K 鍵'), bg="#E91E63", fg="white", font=('Arial', 8, 'bold'), width=17).pack(side='left')
        self.lbl_challenge = tk.Label(r_chal, text='未設定 [進攻專用]', font=('Arial', 9), fg='#B71C1C')
        self.lbl_challenge.pack(side='left', padx=6)

        # ③ 開始戰鬥座標
        r2 = tk.Frame(coord_box)
        r2.pack(fill='x', pady=1)
        tk.Button(r2, text='③ 開始戰鬥 (K鍵)', command=lambda: self.start_capture('start_battle', '移至【開始戰鬥按鈕】按 K 鍵'), bg="#FF9800", fg="white", font=('Arial', 8, 'bold'), width=17).pack(side='left')
        self.lbl_start = tk.Label(r2, text='未設定', font=('Arial', 9), fg='#B71C1C')
        self.lbl_start.pack(side='left', padx=6)

        # ④ 抽獎卡片座標
        r3 = tk.Frame(coord_box)
        r3.pack(fill='x', pady=1)
        tk.Button(r3, text='④ 抽獎卡片 (K鍵)', command=lambda: self.start_capture('draw', '移至【中間抽獎卡片】按 K 鍵'), bg="#9C27B0", fg="white", font=('Arial', 8, 'bold'), width=17).pack(side='left')
        self.lbl_draw = tk.Label(r3, text='未設定', font=('Arial', 9), fg='#B71C1C')
        self.lbl_draw.pack(side='left', padx=6)

        # ⑤ 確定按鈕座標
        r4 = tk.Frame(coord_box)
        r4.pack(fill='x', pady=1)
        tk.Button(r4, text='⑤ 確定按鈕 (K鍵)', command=lambda: self.start_capture('confirm', '移至獲獎【確定按鈕】按 K 鍵'), bg="#009688", fg="white", font=('Arial', 8, 'bold'), width=17).pack(side='left')
        self.lbl_confirm = tk.Label(r4, text='未設定', font=('Arial', 9), fg='#B71C1C')
        self.lbl_confirm.pack(side='left', padx=6)

        # 🐺 進攻出戰派狼配置 (進攻專用)
        self.attack_box = tk.LabelFrame(main, text='🐺 進攻出戰派狼配置 (出戰隊列)', padx=5, pady=3)
        self.attack_box.pack(fill='x', pady=2)

        # 派狼選項列
        d_row1 = tk.Frame(self.attack_box)
        d_row1.pack(fill='x', pady=1)
        tk.Radiobutton(d_row1, text='全部自動派出 (自動隊列)', variable=self.dispatch_mode_var, value='auto', font=('Arial', 8, 'bold')).pack(side='left')
        tk.Radiobutton(d_row1, text='指定派出狼隻:', variable=self.dispatch_mode_var, value='manual', font=('Arial', 8, 'bold')).pack(side='left', padx=(8, 0))
        self.entry_wolves = tk.Entry(d_row1, textvariable=self.selected_wolves_var, width=6, font=('Arial', 8))
        self.entry_wolves.pack(side='left', padx=2)
        tk.Label(d_row1, text='(如: 1 或 1,2)', font=('Arial', 8), fg='gray').pack(side='left')

        # 狼槽座標設定行
        d_row2 = tk.Frame(self.attack_box)
        d_row2.pack(fill='x', pady=1)
        tk.Button(d_row2, text='自動隊列座標(K鍵)', command=lambda: self.start_capture('auto_queue', '移至【自動隊列按鈕】按 K 鍵'), bg="#E65100", fg="white", font=('Arial', 8, 'bold'), width=17).pack(side='left')
        self.lbl_auto_queue = tk.Label(d_row2, text='未設定', font=('Arial', 8), fg='#B71C1C')
        self.lbl_auto_queue.pack(side='left', padx=6)

        d_row3 = tk.Frame(self.attack_box)
        d_row3.pack(fill='x', pady=1)
        tk.Button(d_row3, text='兩點生成狼槽(1~8)', command=self.start_two_point_wolf_wizard, bg="#5C6BC0", fg="white", font=('Arial', 8, 'bold'), width=17).pack(side='left')
        self.lbl_wolf_slots = tk.Label(d_row3, text='(0/8 點)', font=('Arial', 8), fg='#B71C1C')
        self.lbl_wolf_slots.pack(side='left', padx=6)

        # 清空按鈕行
        r_clear = tk.Frame(main)
        r_clear.pack(fill='x', pady=1)
        tk.Button(r_clear, text='清空當前模式座標', command=self.clear_current_mode_coords, font=('Arial', 8)).pack(side='right')

        # ⚙️ 運行參數配置 (按時間執行順序排列)
        param_box = tk.LabelFrame(main, text='⚙️ 運行參數配置 (按執行順序排列)', padx=5, pady=3)
        param_box.pack(fill='x', pady=2)

        # 頂部順序導引列與說明按鈕
        pb_head = tk.Frame(param_box)
        pb_head.pack(fill='x', pady=(0, 2))
        tk.Label(pb_head, text='順序: ①切磋 ➔ ②戰鬥偵測 ➔ ③卡片洗牌 ➔ ④翻牌揭曉 ➔ ⑤確定結算', font=('Arial', 8, 'bold'), fg='#0D47A1').pack(side='left')
        tk.Button(pb_head, text='❓ 階段說明', command=self.show_stage_guide, bg="#009688", fg="white", font=('Arial', 8, 'bold')).pack(side='right')

        # 行 1: 挑戰次數 & ① 切磋後等待
        p_row1 = tk.Frame(param_box)
        p_row1.pack(fill='x', pady=1)
        tk.Label(p_row1, text='挑戰次數:', font=('Arial', 8)).pack(side='left')
        self.rounds_var = tk.StringVar(value='10')
        tk.Entry(p_row1, textvariable=self.rounds_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)

        tk.Label(p_row1, text='① 切磋後等待:', font=('Arial', 8, 'bold'), fg='#1565C0').pack(side='left', padx=(8, 0))
        self.spar_delay_var = tk.StringVar(value='2.0')
        tk.Entry(p_row1, textvariable=self.spar_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)
        tk.Label(p_row1, text='秒 (等彈窗出現)', font=('Arial', 8), fg='gray').pack(side='left')

        # 行 2: ② 戰鬥等待 & 動態輪詢
        p_battle = tk.Frame(param_box)
        p_battle.pack(fill='x', pady=1)
        tk.Label(p_battle, text='② 戰鬥等待:', font=('Arial', 8, 'bold'), fg='#0D47A1').pack(side='left')
        self.battle_initial_var = tk.StringVar(value='10.0')
        tk.Entry(p_battle, textvariable=self.battle_initial_var, width=4, font=('Arial', 8, 'bold')).pack(side='left', padx=2)
        tk.Label(p_battle, text='秒 ➔ 每隔:', font=('Arial', 8)).pack(side='left')
        self.battle_poll_var = tk.StringVar(value='1.0')
        tk.Entry(p_battle, textvariable=self.battle_poll_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)
        tk.Label(p_battle, text='秒辨識 (超時:', font=('Arial', 8)).pack(side='left')
        self.battle_timeout_var = tk.StringVar(value='50.0')
        tk.Entry(p_battle, textvariable=self.battle_timeout_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)
        tk.Label(p_battle, text='s)', font=('Arial', 8)).pack(side='left')

        # 行 3: ③ 洗牌等待 ➔ ④ 翻牌等待 ➔ ⑤ 確定等待
        p_row2 = tk.Frame(param_box)
        p_row2.pack(fill='x', pady=1)
        tk.Label(p_row2, text='③ 洗牌等待:', font=('Arial', 8, 'bold'), fg='#E65100').pack(side='left')
        self.shuffle_delay_var = tk.StringVar(value='1.2')
        tk.Entry(p_row2, textvariable=self.shuffle_delay_var, width=4, font=('Arial', 8, 'bold')).pack(side='left', padx=2)

        tk.Label(p_row2, text='④ 翻牌等待:', font=('Arial', 8, 'bold'), fg='#6A1B9A').pack(side='left', padx=(6, 0))
        self.draw_delay_var = tk.StringVar(value='2.5')
        tk.Entry(p_row2, textvariable=self.draw_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)

        tk.Label(p_row2, text='⑤ 確定等待:', font=('Arial', 8, 'bold'), fg='#00695C').pack(side='left', padx=(6, 0))
        self.confirm_delay_var = tk.StringVar(value='2.0')
        tk.Entry(p_row2, textvariable=self.confirm_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)

        # 即時日誌區
        log_frame = tk.LabelFrame(main, text='即時日誌', padx=3, pady=2)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=2)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, font=('Arial', 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 底部狀態列
        bottom_f = tk.Frame(main)
        bottom_f.pack(fill='x', pady=2)
        tk.Button(bottom_f, text='清空日誌', command=lambda: self.log_text.delete('1.0', tk.END), font=('Arial', 8)).pack(side='left')
        tk.Label(bottom_f, text='按 F10 鍵可全域緊急停止', font=('Arial', 8), fg='gray').pack(side='right')

    def get_current_spar_coord(self):
        if self.mode_var.get() == 'attack':
            return self.coords.get('spar_attack')
        else:
            return self.coords.get('spar_defense') or self.coords.get('spar')

    def on_mode_change(self):
        mode = self.mode_var.get()
        if mode == 'attack':
            self.btn_spar.config(text='① 進攻切磋 (K鍵)', bg="#D32F2F")
            self.auto.log("🔄 切換至【⚔️ 進攻模式】")
        else:
            self.btn_spar.config(text='① 防守切磋 (K鍵)', bg="#2196F3")
            self.auto.log("🔄 切換至【🛡️ 防守模式】")
        self.update_coord_labels()

    def start_capture_current_spar(self):
        mode = self.mode_var.get()
        if mode == 'attack':
            self.start_capture('spar_attack', '移至右側【進攻切磋按鈕】按 K 鍵')
        else:
            self.start_capture('spar_defense', '移至左側【防守切磋按鈕】按 K 鍵')

    def update_coord_labels(self):
        s = self.get_current_spar_coord()
        mode_str = "進攻" if self.mode_var.get() == 'attack' else "防守"
        self.lbl_spar.config(text=f"({s[0]}, {s[1]}) [{mode_str}]" if s else f"未設定 [{mode_str}]", fg="green" if s else "#B71C1C")

        b = self.coords.get('start_battle')
        self.lbl_start.config(text=f"({b[0]}, {b[1]})" if b else "未設定", fg="green" if b else "#B71C1C")

        d = self.coords.get('draw')
        self.lbl_draw.config(text=f"({d[0]}, {d[1]})" if d else "未設定", fg="green" if d else "#B71C1C")

        c = self.coords.get('confirm')
        self.lbl_confirm.config(text=f"({c[0]}, {c[1]})" if c else "未設定", fg="green" if c else "#B71C1C")

        ac = self.coords.get('attack_challenge')
        self.lbl_challenge.config(text=f"({ac[0]}, {ac[1]})" if ac else "未設定", fg="green" if ac else "#B71C1C")

        aq = self.coords.get('auto_queue')
        self.lbl_auto_queue.config(text=f"({aq[0]}, {aq[1]})" if aq else "未設定", fg="green" if aq else "#B71C1C")

        slots = self.coords.get('wolf_slots', [])
        self.lbl_wolf_slots.config(text=f"({len(slots)}/8 點)" if slots else "(0/8)", fg="green" if len(slots) == 8 else "#B71C1C")

    def clear_current_mode_coords(self):
        if self.mode_var.get() == 'attack':
            self.coords['spar_attack'] = None
            self.coords['attack_challenge'] = None
            self.coords['auto_queue'] = None
            self.coords['wolf_slots'] = []
            self.auto.log("已清空進攻專屬座標 (進攻切磋、挑戰、自動隊列、狼槽)")
        else:
            self.coords['spar_defense'] = None
            self.coords['spar'] = None
            self.auto.log("已清空防守切磋座標")
        self.update_coord_labels()
        self.save_config()

    def start_two_point_wolf_wizard(self):
        self.capture_mode = 'wolf_p1'
        self.temp_p1 = None
        self.start_capture('wolf_p1', '【兩點生成狼槽 1/2】滑鼠移至底部【第 1 隻狼】頭像中心，按 K 鍵確認')

    def start_capture(self, key_name, tip_text):
        if self.capturing:
            return
        self.capturing = True
        self.capture_key = key_name
        self.auto.log(f"🎯 【定位模式】{tip_text} (按 ESC 取消)")

        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass

        self.keyboard_listener = pynput.keyboard.Listener(on_press=self.on_key)
        self.keyboard_listener.daemon = True
        self.keyboard_listener.start()

    def on_key(self, key):
        if not self.capturing:
            return False

        if key == pynput.keyboard.Key.esc:
            self.capturing = False
            self.root.after(0, lambda: self.auto.log("已取消定位操作"))
            return False

        try:
            char = getattr(key, 'char', None)
            if char and char.lower() in ('k', 'w'):
                x, y = pyautogui.position()
                ix, iy = int(x), int(y)

                if self.capture_key == 'wolf_p1':
                    self.temp_p1 = (ix, iy)
                    self.capture_key = 'wolf_p2'
                    self.root.after(0, lambda: self.auto.log(f"✔ 獲取第 1 隻狼中心: ({ix}, {iy})"))
                    self.root.after(0, lambda: self.auto.log("【兩點生成狼槽 2/2】滑鼠移至底部【第 8 隻狼】頭像中心，按 K 鍵確認"))
                    return True
                elif self.capture_key == 'wolf_p2':
                    p2 = (ix, iy)
                    self.capturing = False
                    self.root.after(0, lambda: self.generate_wolf_slots_from_two_points(self.temp_p1, p2))
                    return False
                else:
                    self.coords[self.capture_key] = (ix, iy)
                    self.capturing = False
                    self.root.after(0, self.update_coord_labels)
                    self.root.after(0, lambda: self.auto.log(f"✔ 成功設定 {self.capture_key} 座標為: ({ix}, {iy})"))
                    self.root.after(0, self.save_config)
                    return False
        except Exception:
            pass
        return True

    def generate_wolf_slots_from_two_points(self, p1, p2):
        """由第 1 隻與第 8 隻狼中心點內插計算出 8 個狼槽座標"""
        x1, y1 = p1
        x2, y2 = p2
        self.coords['wolf_slots'] = []
        for i in range(8):
            ratio = i / 7.0
            cx = int(x1 + (x2 - x1) * ratio)
            cy = int(y1 + (y2 - y1) * ratio)
            self.coords['wolf_slots'].append((cx, cy))
        self.update_coord_labels()
        self.auto.log(f"✨ 成功由兩點生成 8 個狼槽座標！(首: {p1}, 末: {p2})")
        self.save_config()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes('-topmost', self.topmost)
        if self.topmost:
            self.topmost_btn.config(bg='lightgreen', relief='sunken')
            self.auto.log('視窗置頂已開啟')
        else:
            self.topmost_btn.config(bg='SystemButtonFace', relief='raised')
            self.auto.log('視窗置頂已關閉')

    def show_stage_guide(self):
        msg = (
            "【競技場參數時間順序說明】\n\n"
            "① 切磋後等待：\n"
            "   點擊列表切磋按鈕後，等待彈出「防線資訊」或「出戰隊列」彈窗的時間。\n\n"
            "② 戰鬥等待：\n"
            "   點擊「開始戰鬥」後，戰鬥初期的必經動畫時間。此期間暫不截圖，待時間結束後才開始每秒辨識一次副螢幕畫面（設有超時保護）。\n\n"
            "③ 洗牌等待：\n"
            "   畫面出現結算（勝利/惜敗/抽獎）後，第 1 次點擊卡片觸發洗牌，等待三張卡片背對翻轉並洗牌結束的時間。\n\n"
            "④ 翻牌等待：\n"
            "   第 2 次點擊卡片正式抽獎，等待獎勵翻開揭曉並彈出獲獎確定彈窗的時間。\n\n"
            "⑤ 確定等待：\n"
            "   點擊獲獎彈窗「確定」按鈕後，關閉彈窗並返回競技場主畫面，準備下一輪切磋。"
        )
        messagebox.showinfo("執行順序與階段說明", msg)

    def request_admin(self):
        result = messagebox.askyesno("提升權限", "程式將以管理員身份重新啟動\n當前視窗將關閉\n是否繼續？")
        if result:
            run_as_admin()

    def setup_global_hotkeys(self):
        def on_press(key):
            try:
                if key == pynput.keyboard.Key.f10:
                    if self.auto.running:
                        self.root.after(0, self.auto.stop)
            except Exception:
                pass

        self.hotkey_listener = pynput.keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def save_config(self):
        data = {
            'coords': self.coords,
            'mode': self.mode_var.get(),
            'dispatch_mode': self.dispatch_mode_var.get(),
            'selected_wolves': self.selected_wolves_var.get(),
            'rounds': self.rounds_var.get(),
            'spar_delay': self.spar_delay_var.get(),
            'battle_initial': self.battle_initial_var.get(),
            'battle_poll': self.battle_poll_var.get(),
            'battle_timeout': self.battle_timeout_var.get(),
            'shuffle_delay': self.shuffle_delay_var.get(),
            'draw_delay': self.draw_delay_var.get(),
            'confirm_delay': self.confirm_delay_var.get(),
            'topmost': self.topmost
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            raw_coords = data.get('coords', {})
            for k, v in raw_coords.items():
                if v:
                    if k == 'wolf_slots':
                        self.coords[k] = [tuple(pt) for pt in v]
                    else:
                        self.coords[k] = tuple(v)

            # 相容舊檔只有 'spar' 的情況 (預設為防守切磋)
            if not self.coords.get('spar_defense') and self.coords.get('spar'):
                self.coords['spar_defense'] = self.coords.get('spar')

            if 'mode' in data: self.mode_var.set(str(data['mode']))
            if 'dispatch_mode' in data: self.dispatch_mode_var.set(str(data['dispatch_mode']))
            if 'selected_wolves' in data: self.selected_wolves_var.set(str(data['selected_wolves']))
            if 'rounds' in data: self.rounds_var.set(str(data['rounds']))
            if 'spar_delay' in data: self.spar_delay_var.set(str(data['spar_delay']))
            if 'battle_initial' in data: self.battle_initial_var.set(str(data['battle_initial']))
            if 'battle_poll' in data: self.battle_poll_var.set(str(data['battle_poll']))
            if 'battle_timeout' in data: self.battle_timeout_var.set(str(data['battle_timeout']))
            if 'shuffle_delay' in data: self.shuffle_delay_var.set(str(data['shuffle_delay']))
            if 'draw_delay' in data: self.draw_delay_var.set(str(data['draw_delay']))
            if 'confirm_delay' in data: self.confirm_delay_var.set(str(data['confirm_delay']))
            if 'topmost' in data:
                self.topmost = bool(data['topmost'])
                self.root.attributes('-topmost', self.topmost)
                if self.topmost:
                    self.topmost_btn.config(bg='lightgreen', relief='sunken')
                else:
                    self.topmost_btn.config(bg='SystemButtonFace', relief='raised')

            self.on_mode_change()
            self.update_coord_labels()
            self.auto.log("📂 已成功載入上次保存的配置與座標")
        except Exception as e:
            self.auto.log(f"載入配置失敗: {e}")


def main():
    root = tk.Tk()
    app = ArenaGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
