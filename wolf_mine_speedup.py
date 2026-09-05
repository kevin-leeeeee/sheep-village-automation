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
from ctypes import wintypes
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

import win32api
from PIL import Image, ImageTk, ImageDraw, ImageFont
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
        self.detected_monitor_name = None
        self.monitor_offset_x = 0
        self.monitor_offset_y = 0
        
        # 圖片友善中文名稱對照表
        self.friendly_names = {
            'jiasu_shalou.png': '挖礦加速沙漏 (jiasu_shalou.png)',
            'jiasu_shalou_hd.png': '高清沙漏 (jiasu_shalou_hd.png)',
            'haoyou_next.png': '好友欄下一頁 (haoyou_next.png)',
            'jiayuan.png': '家園領地圖示 (jiayuan.png)',
            'queding.png': '確定按鈕 (queding.png)',
            'queding_orange.png': '橘色確定按鈕 (queding_orange.png)',
            'shangxian_short.png': '挖礦上限提示 (shangxian_short.png)',
            'shangxian_text.png': '挖礦上限文字 (shangxian_text.png)',
            'cha.png': '關閉叉叉 (cha.png)',
            'bosscha.png': 'Boss叉叉 (bosscha.png)',
            'tacha.png': '防禦塔叉叉 (tacha.png)'
        }

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
            m_left, m_top = 0, 0

            # 依據已設定的好友座標、敲狼座標、礦山座標或翻頁座標判定螢幕
            pt = None
            if self.gui.coordinates:
                pt = self.gui.coordinates[0]
            elif self.gui.wolf_coords:
                pt = self.gui.wolf_coords[0]
            elif self.gui.mine_coord:
                pt = self.gui.mine_coord
            elif self.gui.next_page_coord:
                pt = self.gui.next_page_coord

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

            if not target_device or target_w <= 0 or target_h <= 0:
                self.monitor_offset_x = 0
                self.monitor_offset_y = 0
                shot = pyautogui.screenshot()
                return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

            self.monitor_offset_x = m_left
            self.monitor_offset_y = m_top

            if target_device != self.detected_monitor_name:
                self.detected_monitor_name = target_device
                self.log(f"🖥️ 自動鎖定遊戲螢幕: {target_device} ({target_w}x{target_h}) 偏移=({m_left},{m_top})")

            gdi32 = ctypes.windll.gdi32
            hdc_screen = gdi32.CreateDCW(target_device, None, None, None)
            if not hdc_screen:
                shot = pyautogui.screenshot()
                self.monitor_offset_x = 0
                self.monitor_offset_y = 0
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
            self.monitor_offset_x = 0
            self.monitor_offset_y = 0
            try:
                shot = pyautogui.screenshot()
                return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
            except Exception:
                return None

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
            screenshot = self.capture_screen()
        if screenshot is None:
            return False

        pos, val, _ = self.find_image_multiscale([filename], screenshot)
        if pos:
            click_x = pos[0] + self.monitor_offset_x
            click_y = pos[1] + self.monitor_offset_y
            pyautogui.leftClick(click_x, click_y)
            self.log(f'點擊: {friendly_name} [匹配度: {val*100:.1f}%] 座標: ({click_x}, {click_y})')
            time.sleep(self.default_delay)
            return True

        if not silent_fail:
            self.log(f'未看到: {friendly_name} (最高匹配度: {val*100:.1f}%)')
        return False

    def check_mine_limit_popup(self, screenshot=None):
        """專門檢查是否出現『你今天已經幫助很多好友了』上限彈窗"""
        if screenshot is None:
            screenshot = self.capture_screen()
        if screenshot is None:
            return None

        # 1. 檢查上限文字標籤 (如：幫助很多好友了)
        pos_txt, val_txt, _ = self.find_image_multiscale(['shangxian_short.png', 'shangxian_text.png'], screenshot)
        # 2. 檢查橘黃色確定按鈕
        pos_btn, val_btn, _ = self.find_image_multiscale(['queding_orange.png'], screenshot)

        if pos_txt or pos_btn:
            if pos_btn:
                cx = pos_btn[0] + self.monitor_offset_x
                cy = pos_btn[1] + self.monitor_offset_y
            else:
                cx = pos_txt[0] + self.monitor_offset_x
                cy = pos_txt[1] + self.monitor_offset_y + 135
            return (cx, cy)
        return None

    def handle_confirm_popup(self, stage_name=""):
        """處理確定彈窗：優先檢查加速礦上限彈窗，再點擊手動指定座標，並以視覺辨識補刀"""
        try:
            c_delay = float(self.gui.confirm_delay_var.get())
        except Exception:
            c_delay = 0.2

        # 1. 優先專項檢測：是否出現「今日已幫助很多好友了」上限彈窗 (特別是在點擊礦山後)
        shot = self.capture_screen()
        limit_pos = self.check_mine_limit_popup(shot)
        if limit_pos:
            lx, ly = limit_pos
            pyautogui.leftClick(lx, ly)
            time.sleep(c_delay + 0.2)
            if self.gui.mining_var.get():
                self.gui.mining_var.set(False)
                self.log('🛑 [上限觸發] 偵測到「你今天已經幫助很多好友了」上限彈窗！已點擊確定關閉，並自動關閉【⚡ 挖礦加速】。後續將專心敲狼。')
            else:
                self.log(f'🛑 偵測到上限特殊彈窗！已點擊確定關閉: ({lx}, {ly})')
            return True

        # 2. 點擊手動指定確定座標
        clicked_fixed = False
        if getattr(self.gui, 'confirm_coord', None):
            cx, cy = self.gui.confirm_coord
            pyautogui.leftClick(cx, cy)
            self.log(f'✔ [{stage_name}] 點擊指定確定座標: ({cx}, {cy}) (等待 {c_delay}s)')
            time.sleep(c_delay)
            clicked_fixed = True

        # 3. 二次檢查/補刀：檢測畫面上是否仍殘留確定彈窗 (包含橘黃色與灰藍色確定按鈕)
        shot2 = self.capture_screen()
        if shot2 is not None:
            limit_pos2 = self.check_mine_limit_popup(shot2)
            if limit_pos2:
                lx, ly = limit_pos2
                pyautogui.leftClick(lx, ly)
                time.sleep(c_delay)
                if self.gui.mining_var.get():
                    self.gui.mining_var.set(False)
                    self.log('🛑 [上限觸發] 偵測到「你今天已經幫助很多好友了」上限彈窗！已點擊確定關閉，並自動關閉【⚡ 挖礦加速】。後續將專心敲狼。')
                return True

            pos, val, _ = self.find_image_multiscale(['queding_orange.png', 'queding.png'], shot2)
            if pos:
                click_x = pos[0] + self.monitor_offset_x
                click_y = pos[1] + self.monitor_offset_y
                pyautogui.leftClick(click_x, click_y)
                time.sleep(c_delay)
                self.log(f'✔ [{stage_name}] 影像辨識補點確定彈窗: ({click_x}, {click_y})')
                return True

        return clicked_fixed

    def detect_and_click_confirm(self):
        """偵測並點擊確定或關閉按鈕"""
        for popup_img in ['queding_orange.png', 'queding.png', 'cha.png', 'bosscha.png', 'tacha.png', 'yaoqing_queding.png']:
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
        採用 Win32 API 原生視窗句柄偵測 (0.001s 100% 精準，支援 CefFlashBrowser 與所有系統對話框)
        """
        if not self.gui.stop_on_invite_var.get():
            return False

        user32 = ctypes.windll.user32

        # 1. 舊版獨立播放器偵測: flashplayerdesktop
        hwnd_old = user32.FindWindowW(None, 'flashplayerdesktop')
        if hwnd_old and user32.IsWindowVisible(hwnd_old):
            self.log('🛑 [Win32 原生偵測] 瞬間捕捉「flashplayerdesktop」系統彈窗！自動關閉並停止巡邏。')
            user32.PostMessageW(hwnd_old, 0x0010, 0, 0)
            time.sleep(0.3)
            return True

        # 2. CefFlashBrowser (WPF 彈窗) 與標準對話框全域精準枚舉
        try:
            target_info = [None]
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    c_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, c_buf, 256)
                    cname = c_buf.value

                    t_len = user32.GetWindowTextLengthW(hwnd)
                    t_buf = ctypes.create_unicode_buffer(t_len + 1)
                    user32.GetWindowTextW(hwnd, t_buf, t_len + 1)
                    title = t_buf.value

                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top

                    # (A) CefFlashBrowser WPF 彈出對話框 (如尺寸約 420x200，排除 1200x900 的主視窗)
                    if 'CefFlashBrowser' in cname:
                        if 150 <= w <= 650 and 80 <= h <= 450:
                            target_info[0] = (hwnd, title, (rect.left, rect.top, w, h))
                            return False

                    # (B) 標準 Windows 對話框 (#32770)
                    elif cname == '#32770':
                        if any(k in title for k in ['保卫', '保衛', '提示', '警告', 'Flash', '不支持']):
                            target_info[0] = (hwnd, title, (rect.left, rect.top, w, h))
                            return False

                    # (C) 標題包含明確字樣之彈窗
                    elif any(k in title for k in ['暂不支持', '暫不支持', '邀请好友', '邀請好友']):
                        target_info[0] = (hwnd, title, (rect.left, rect.top, w, h))
                        return False

                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            if target_info[0]:
                h, title, (rx, ry, rw, rh) = target_info[0]
                self.log(f'🛑 [Win32 原生偵測] 成功捕捉到「暫時不支持邀請好友」彈窗 (HWND={hex(h)}, 尺寸={rw}x{rh})！已達好友末端，自動關閉並停止巡邏。')
                user32.PostMessageW(h, 0x0010, 0, 0)
                pyautogui.press('enter')
                time.sleep(0.3)
                return True

        except Exception:
            pass

        # 3. 視覺圖像辨識兜底 (若非原生系統對話框或在其他瀏覽器執行時)
        try:
            for text_img in ['yaoqing_text.png', 'yaoqing_title.png']:
                pos = self.find_image(text_img, confidence=0.75)
                if pos:
                    self.log(f'🛑 [視覺辨識兜底] 捕捉到「暫時不支持邀請好友」畫面標識 ({text_img})！已達好友末端。')
                    if not self.click_image('yaoqing_queding.png', silent_fail=True):
                        pyautogui.press('enter')
                    time.sleep(0.3)
                    return True
        except Exception:
            pass

        return False

    def patrol_loop(self):
        try:
            load_delay = float(self.gui.load_delay_var.get())
            click_interval = float(self.gui.interval_var.get())
            wolf_after_delay = float(self.gui.wolf_delay_var.get())
            try:
                wolf_click_count = max(1, int(self.gui.wolf_click_count_var.get()))
            except Exception:
                wolf_click_count = len(self.gui.wolf_coords)
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
            wolf_click_count = 6
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
                target_coords = self.gui.wolf_coords[:wolf_click_count]
                self.log(f'🐺 啟用範圍覆蓋敲狼: 點擊前 {len(target_coords)} 個熱點 (敲後等待 {wolf_after_delay}s)')
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
                        target_coords = self.gui.wolf_coords[:wolf_click_count]
                        self.log(f'🐺 執行草地範圍覆蓋敲狼 ({len(target_coords)} 個熱點)...')
                        for wx, wy in target_coords:
                            if not self.running:
                                break
                            pyautogui.leftClick(wx, wy)
                            time.sleep(click_interval)

                        # 敲狼後等待設定的時間（③ 敲完等待）
                        if wolf_after_delay > 0:
                            time.sleep(wolf_after_delay)

                        # 敲完狼自動檢查並點擊「確定」彈窗
                        self.handle_confirm_popup('敲狼完畢')

                    if not self.running:
                        break

                    # 2. 加速挖礦 (點擊指定礦山座標)
                    if self.gui.mining_var.get():
                        if self.gui.mine_coord:
                            mx, my = self.gui.mine_coord
                            pyautogui.leftClick(mx, my)
                            self.log(f'⚡ 點擊指定礦山座標: ({mx}, {my})')
                            total_mining += 1
                            time.sleep(mine_delay)
                            # 點擊礦山後自動檢查並點擊「確定」彈窗
                            self.handle_confirm_popup('礦山點擊完畢')
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
        self.confirm_coord = None
        self.capturing = False
        self.capture_mode = 'friend'
        self.temp_p1 = None
        self.keyboard_listener = None
        self.screen_overlay = None
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
        tk.Label(row_wolf, text='網格:', font=('Arial', 8)).pack(side='left', padx=(2, 0))
        self.wolf_cols_var = tk.StringVar(value='3')
        tk.Entry(row_wolf, textvariable=self.wolf_cols_var, width=2, font=('Arial', 8)).pack(side='left')
        tk.Label(row_wolf, text='x', font=('Arial', 8)).pack(side='left')
        self.wolf_rows_var = tk.StringVar(value='2')
        tk.Entry(row_wolf, textvariable=self.wolf_rows_var, width=2, font=('Arial', 8)).pack(side='left')

        def on_grid_change(*args):
            if not getattr(self, '_loading_config', False):
                self.update_grid_from_existing_bounds()

        self.wolf_cols_var.trace_add('write', on_grid_change)
        self.wolf_rows_var.trace_add('write', on_grid_change)

        tk.Button(row_wolf, text='清空', command=self.clear_wolf_coords, font=('Arial', 8)).pack(side='left', padx=2)
        self.wolf_info_lbl = tk.Label(row_wolf, text='(熱點: 5點)', font=('Arial', 8), fg='#B71C1C')
        self.wolf_info_lbl.pack(side='left', padx=2)

        # 行 2: 好友生成
        row_friend = tk.Frame(coord_box)
        row_friend.pack(fill='x', pady=1)
        tk.Button(row_friend, text='兩點生成好友', command=self.start_two_point_wizard, bg="#2196F3", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_friend, text='清空', command=self.clear_friend_coords, font=('Arial', 8)).pack(side='left', padx=1)

        # 行 3: 翻頁、礦山與確定座標
        row_aux = tk.Frame(coord_box)
        row_aux.pack(fill='x', pady=1)
        tk.Button(row_aux, text='翻頁(K鍵)', command=self.start_capture_next_page, bg="#00897B", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_aux, text='礦山(K鍵)', command=self.start_capture_mine, bg="#F57C00", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_aux, text='確定按鈕(K鍵)', command=self.start_capture_confirm, bg="#009688", fg="white", font=('Arial', 8, 'bold')).pack(side='left', padx=1)
        tk.Button(row_aux, text='清空', command=self.clear_aux_coords, font=('Arial', 8)).pack(side='left', padx=1)

        # 行 4: 標記預覽
        row_crop = tk.Frame(coord_box)
        row_crop.pack(fill='x', pady=1)
        tk.Button(row_crop, text='🖥️ 標記預覽 (即時視覺化微調)', command=self.open_screen_overlay, bg="#673AB7", fg="white", font=('Arial', 8, 'bold')).pack(side='left', expand=True, fill='x', padx=1)

        # 狀態列
        self.coord_info_lbl = tk.Label(coord_box, text='好友: 0 | 翻頁: 自動 | 礦山: 未設定 | 確定: 自動辨識', font=('Arial', 8), fg='navy')
        self.coord_info_lbl.pack(fill='x', pady=1)

        # ⚙️ 運行參數配置 (按時間執行順序排列)
        param_box = tk.LabelFrame(main, text='⚙️ 運行參數配置 (按時間執行順序排列)', padx=5, pady=2)
        param_box.pack(fill='x', pady=2)

        # 順序提示標籤
        tk.Label(param_box, text='順序: ①進家 ➔ ②敲狼 ➔ ③敲完等待 ➔ ④礦山 ➔ 確定等待 ➔ ⑤翻頁', font=('Arial', 8, 'bold'), fg='#0D47A1').pack(anchor='w', pady=(0, 2))

        sf1 = tk.Frame(param_box)
        sf1.pack(fill='x', pady=1)

        tk.Label(sf1, text='①進家延遲:', font=('Arial', 8)).pack(side='left')
        self.load_delay_var = tk.StringVar(value='1.8')
        tk.Entry(sf1, textvariable=self.load_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf1, text='②敲熱點數:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.wolf_click_count_var = tk.StringVar(value='6')
        tk.Entry(sf1, textvariable=self.wolf_click_count_var, width=3, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf1, text='點擊間隔:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.interval_var = tk.StringVar(value='0.12')
        tk.Entry(sf1, textvariable=self.interval_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        sf2 = tk.Frame(param_box)
        sf2.pack(fill='x', pady=1)

        tk.Label(sf2, text='③敲完等待:', font=('Arial', 8)).pack(side='left')
        self.wolf_delay_var = tk.StringVar(value='0.6')
        tk.Entry(sf2, textvariable=self.wolf_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf2, text='④礦山等待:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.mine_delay_var = tk.StringVar(value='0.4')
        tk.Entry(sf2, textvariable=self.mine_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf2, text='確定等待:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.confirm_delay_var = tk.StringVar(value='0.2')
        tk.Entry(sf2, textvariable=self.confirm_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        sf3 = tk.Frame(param_box)
        sf3.pack(fill='x', pady=1)

        tk.Label(sf3, text='⑤翻頁延遲:', font=('Arial', 8)).pack(side='left')
        self.page_delay_var = tk.StringVar(value='1.0')
        tk.Entry(sf3, textvariable=self.page_delay_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf3, text='巡邏頁數:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.max_pages_var = tk.StringVar(value='10')
        tk.Entry(sf3, textvariable=self.max_pages_var, width=3, font=('Arial', 8)).pack(side='left', padx=1)

        tk.Label(sf3, text='跳過好友:', font=('Arial', 8)).pack(side='left', padx=(4, 0))
        self.skip_friend_idx_var = tk.StringVar(value='')
        tk.Entry(sf3, textvariable=self.skip_friend_idx_var, width=4, font=('Arial', 8)).pack(side='left', padx=1)
        tk.Label(sf3, text='(如: 1,2)', font=('Arial', 8), fg='gray').pack(side='left', padx=(1, 2))

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
            'confirm_coord': self.confirm_coord,
            'load_delay': self.load_delay_var.get(),
            'wolf_cols': self.wolf_cols_var.get(),
            'wolf_rows': self.wolf_rows_var.get(),
            'wolf_click_count': self.wolf_click_count_var.get(),
            'wolf_delay': self.wolf_delay_var.get(),
            'interval': self.interval_var.get(),
            'page_delay': self.page_delay_var.get(),
            'max_pages': self.max_pages_var.get(),
            'mine_delay': self.mine_delay_var.get(),
            'confirm_delay': self.confirm_delay_var.get(),
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
            if data.get('confirm_coord'):
                self.confirm_coord = tuple(data['confirm_coord'])
            elif os.path.exists(os.path.join(BASE_DIR, 'arena_config.json')):
                # 若 arena_config.json 中已有確認座標，自動載入作為預設值
                try:
                    with open(os.path.join(BASE_DIR, 'arena_config.json'), 'r', encoding='utf-8') as af:
                        adata = json.load(af)
                        if adata.get('coords', {}).get('confirm'):
                            self.confirm_coord = tuple(adata['coords']['confirm'])
                except Exception:
                    pass

            if 'load_delay' in data: self.load_delay_var.set(str(data['load_delay']))
            if 'wolf_cols' in data: self.wolf_cols_var.set(str(data['wolf_cols']))
            if 'wolf_rows' in data: self.wolf_rows_var.set(str(data['wolf_rows']))
            if 'wolf_click_count' in data: self.wolf_click_count_var.set(str(data['wolf_click_count']))
            if 'wolf_delay' in data: self.wolf_delay_var.set(str(data['wolf_delay']))
            if 'interval' in data: self.interval_var.set(str(data['interval']))
            if 'page_delay' in data: self.page_delay_var.set(str(data['page_delay']))
            if 'max_pages' in data: self.max_pages_var.set(str(data['max_pages']))
            if 'mine_delay' in data: self.mine_delay_var.set(str(data['mine_delay']))
            if 'confirm_delay' in data: self.confirm_delay_var.set(str(data['confirm_delay']))
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
        cnt = len(self.wolf_coords)
        if hasattr(self, 'wolf_click_count_var'):
            self.wolf_click_count_var.set(str(cnt))
        self.wolf_info_lbl.config(text=f'(熱點: {cnt}點)')

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
        self.confirm_coord = None
        self.update_coords()
        self.auto.log('已清空翻頁、礦山與確定座標')
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

    def start_capture_confirm(self):
        self.capture_mode = 'confirm'
        self.start_capture('滑鼠移至獲獎/彈窗【確定按鈕】中心，按 K 鍵設定座標，ESC 取消')

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
                elif self.capture_mode == 'confirm':
                    self.confirm_coord = (ix, iy)
                    self.root.after(0, self.update_coords)
                    self.root.after(0, lambda: self.auto.log(f'✔ 成功設定確定按鈕座標為: ({ix}, {iy})'))
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
                    self.root.after(0, lambda: self.generate_wolf_grid(self.temp_p1, p2))
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

    def update_grid_from_existing_bounds(self):
        """根據現有草地範圍自動依新欄x列重新計算網格點"""
        if not self.wolf_coords or len(self.wolf_coords) < 2:
            return
        try:
            min_x = min(pt[0] for pt in self.wolf_coords)
            max_x = max(pt[0] for pt in self.wolf_coords)
            min_y = min(pt[1] for pt in self.wolf_coords)
            max_y = max(pt[1] for pt in self.wolf_coords)
            if max_x - min_x < 10 or max_y - min_y < 10:
                return
            self.generate_wolf_grid((min_x, min_y), (max_x, max_y))
        except Exception:
            pass

    def generate_wolf_grid(self, p1, p2, cols=None, rows=None):
        """由兩點產生覆蓋草地區域的網格敲擊點"""
        if cols is None or rows is None:
            try:
                cols = max(1, int(self.wolf_cols_var.get()))
                rows = max(1, int(self.wolf_rows_var.get()))
            except Exception:
                cols, rows = 3, 2

        self.wolf_coords.clear()
        min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
        min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])

        for r in range(rows):
            for c in range(cols):
                rx = min_x + int((max_x - min_x) * (c + 0.5) / cols)
                ry = min_y + int((max_y - min_y) * (r + 0.5) / rows)
                self.wolf_coords.append((rx, ry))

        self.wolf_click_count_var.set(str(len(self.wolf_coords)))
        self.update_wolf_info()
        self.auto.log(f'✨ 成功生成 {len(self.wolf_coords)} 個 ({cols}x{rows}) 覆蓋草地的敲狼熱點！')
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
        confirm_str = f"({self.confirm_coord[0]}, {self.confirm_coord[1]})" if getattr(self, 'confirm_coord', None) else "自動辨識"
        self.coord_info_lbl.config(text=f'好友: {len(self.coordinates)} | 翻頁: {next_str} | 礦山: {mine_str} | 確定: {confirm_str}')

    def capture_screen(self):
        if hasattr(self, 'auto') and self.auto:
            return self.auto.capture_screen()
        try:
            screenshot = pyautogui.screenshot()
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def open_screen_overlay(self):
        """開啟或關閉 1:1 直接覆蓋於當前螢幕畫面的透明標記層 (重複點擊則切換關閉)"""
        if hasattr(self, 'screen_overlay') and self.screen_overlay:
            try:
                if self.screen_overlay.winfo_exists():
                    self.screen_overlay.destroy()
                    self.screen_overlay = None
                    return
            except Exception:
                self.screen_overlay = None

        self.screen_overlay = ScreenOverlayDialog(self.root, self)

    def open_preview_dialog(self):
        """開啟畫面座標預覽比對彈窗"""
        PreviewDialog(self.root, self)

    def get_target_monitor_rect(self):
        """獲取遊戲座標所在螢幕的 (left, top, width, height)"""
        try:
            monitors = win32api.EnumDisplayMonitors()
            pt = None
            if self.coordinates: pt = self.coordinates[0]
            elif self.wolf_coords: pt = self.wolf_coords[0]
            elif self.mine_coord: pt = self.mine_coord
            elif self.next_page_coord: pt = self.next_page_coord
            elif getattr(self, 'confirm_coord', None): pt = self.confirm_coord

            if pt and monitors:
                px, py = pt
                for hMonitor, hdcMonitor, rMonitor in monitors:
                    m_info = win32api.GetMonitorInfo(hMonitor)
                    m_rect = m_info['Monitor']
                    if m_rect[0] <= px <= m_rect[2] and m_rect[1] <= py <= m_rect[3]:
                        return m_rect[0], m_rect[1], m_rect[2] - m_rect[0], m_rect[3] - m_rect[1]

            if monitors:
                m_info = win32api.GetMonitorInfo(monitors[0][0])
                m_rect = m_info['Monitor']
                return m_rect[0], m_rect[1], m_rect[2] - m_rect[0], m_rect[3] - m_rect[1]
        except Exception:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def generate_preview_image(self):
        """
        截取當前螢幕畫面並將目前設定的座標 (好友、敲狼、翻頁、礦山、確定)
        以視覺化 Overlay 標籤繪製於圖片上，供使用者比對。
        """
        shot = self.capture_screen()
        if shot is None:
            return None, "無法截取當前螢幕畫面，請確認遊戲視窗未最小化"

        # 轉換成 PIL Image (RGB)
        img_rgb = cv2.cvtColor(shot, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        draw = ImageDraw.Draw(pil_img)

        # 載入 Windows 繁體中文字型
        font_main = None
        font_small = None
        for font_path in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\mingliu.ttc']:
            if os.path.exists(font_path):
                try:
                    font_main = ImageFont.truetype(font_path, 15)
                    font_small = ImageFont.truetype(font_path, 12)
                    break
                except Exception:
                    pass
        if not font_main:
            font_main = ImageFont.load_default()
            font_small = ImageFont.load_default()

        ox = self.auto.monitor_offset_x
        oy = self.auto.monitor_offset_y

        def draw_marker(cx, cy, label_text, color_hex, radius=13, shape='circle'):
            rx = cx - ox
            ry = cy - oy

            # 繪製標記符號
            if shape == 'circle':
                draw.ellipse((rx - radius, ry - radius, rx + radius, ry + radius), outline=color_hex, width=3)
                draw.ellipse((rx - 3, ry - 3, rx + 3, ry + 3), fill='red', outline='white', width=1)
            elif shape == 'rect':
                draw.rectangle((rx - radius, ry - radius, rx + radius, ry + radius), outline=color_hex, width=3)
                draw.ellipse((rx - 3, ry - 3, rx + 3, ry + 3), fill='red', outline='white', width=1)

            # 繪製文字底框與文字
            bbox = font_small.getbbox(label_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            bx = rx + radius + 4
            by = ry - text_h // 2 - 2

            # 邊界防溢出
            if bx + text_w + 6 > pil_img.width:
                bx = rx - radius - text_w - 8
            if by < 2:
                by = 2

            draw.rectangle((bx, by, bx + text_w + 6, by + text_h + 6), fill=color_hex, outline='white', width=1)
            draw.text((bx + 3, by + 1), label_text, fill='white', font=font_small)

        # 1. 繪製好友點位 (藍色 #1976D2)
        for idx, pt in enumerate(self.coordinates, start=1):
            draw_marker(pt[0], pt[1], f"好友 #{idx}", '#1976D2', radius=14, shape='circle')

        # 2. 繪製敲狼草地區域與熱點 (橘色 #E65100)
        if self.wolf_coords:
            xs = [pt[0] - ox for pt in self.wolf_coords]
            ys = [pt[1] - oy for pt in self.wolf_coords]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            pad = 16
            draw.rectangle((min_x - pad, min_y - pad, max_x + pad, max_y + pad), outline='#E65100', width=2)
            draw.text((min_x - pad + 4, max_y + pad + 2), "🌾 敲狼熱點覆蓋範圍", fill='#E65100', font=font_small)

            for w_idx, pt in enumerate(self.wolf_coords, start=1):
                rx, ry = pt[0] - ox, pt[1] - oy
                draw.ellipse((rx - 6, ry - 6, rx + 6, ry + 6), fill='#FF5722', outline='white', width=1)
                draw.text((rx + 8, ry - 8), f"W{w_idx}", fill='#FF5722', font=font_small)

        # 3. 繪製翻頁座標 (青綠色 #00897B)
        if self.next_page_coord:
            draw_marker(self.next_page_coord[0], self.next_page_coord[1], "⏩ 翻頁按鈕", '#00897B', radius=14, shape='circle')

        # 4. 繪製礦山座標 (琥珀金黃 #F57C00)
        if self.mine_coord:
            draw_marker(self.mine_coord[0], self.mine_coord[1], "⛏️ 礦山加速", '#F57C00', radius=14, shape='rect')

        # 5. 繪製確定按鈕座標 (洋紅玫瑰紅 #D81B60)
        if getattr(self, 'confirm_coord', None):
            draw_marker(self.confirm_coord[0], self.confirm_coord[1], "🎯 確定按鈕", '#D81B60', radius=16, shape='rect')

        # 頂部狀態資訊條
        dev_name = self.auto.detected_monitor_name or "主螢幕"
        info_banner = f"🖥️ 當前鎖定螢幕: {dev_name} ({pil_img.width}x{pil_img.height}) | 螢幕原點偏移: ({ox}, {oy})"
        draw.rectangle((10, 10, 420, 36), fill='#212121', outline='white', width=1)
        draw.text((16, 15), info_banner, fill='#FFEB3B', font=font_small)

        return pil_img, None


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
            "3. ⚡ 翻頁、礦山與確定座標：滑鼠移至按鈕上方按下 K 鍵即可設定。\n\n"
            "4. 🖥️ 標記預覽：點擊「標記預覽」可在螢幕上直接拖曳微調所有點位。"
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


class ScreenOverlayDialog(tk.Toplevel):
    """直接覆蓋於當前螢幕之透明座標標記層 (所見即所得：支援滑鼠自由拖曳與區域縮放)"""
    def __init__(self, parent, gui):
        super().__init__(parent)
        self.gui = gui

        left, top, width, height = self.gui.get_target_monitor_rect()
        self.left = left
        self.top = top
        self.width = width
        self.height = height

        # 備份原始座標 (供還原)
        self.orig_coordinates = [list(pt) for pt in self.gui.coordinates]
        self.orig_wolf_coords = [list(pt) for pt in self.gui.wolf_coords]
        self.orig_mine_coord = list(self.gui.mine_coord) if self.gui.mine_coord else None
        self.orig_next_page_coord = list(self.gui.next_page_coord) if self.gui.next_page_coord else None
        self.orig_confirm_coord = list(self.gui.confirm_coord) if getattr(self.gui, 'confirm_coord', None) else None

        # 當前編輯中的全域座標
        self.edit_coordinates = [list(pt) for pt in self.gui.coordinates]
        self.edit_wolf_coords = [list(pt) for pt in self.gui.wolf_coords]
        self.edit_mine_coord = list(self.gui.mine_coord) if self.gui.mine_coord else None
        self.edit_next_page_coord = list(self.gui.next_page_coord) if self.gui.next_page_coord else None
        self.edit_confirm_coord = list(self.gui.confirm_coord) if getattr(self.gui, 'confirm_coord', None) else None

        self.wolf_box = None
        self.update_wolf_box_from_coords()

        # 拖曳狀態管理
        self.drag_info = None

        # 無邊框全螢幕覆蓋與置頂
        self.overrideredirect(True)
        self.geometry(f"{width}x{height}+{left}+{top}")
        self.attributes('-topmost', True)

        # 設定 Windows 專屬完全透明背景通道
        self.TRANS_COLOR = '#010203'
        try:
            self.attributes('-transparentcolor', self.TRANS_COLOR)
        except Exception:
            pass

        self.canvas = tk.Canvas(self, bg=self.TRANS_COLOR, highlightthickness=0, width=width, height=height)
        self.canvas.pack(fill='both', expand=True)

        # 頂部浮動控制工具列
        self.setup_control_bar()

        # 繪製畫面標記
        self.draw_overlay()

        # 滑鼠與鍵盤事件綁定
        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_motion)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.canvas.bind('<Motion>', self.on_hover)

        # 綁定右鍵任意處立即關閉 (最直觀最快)
        self.canvas.bind('<Button-3>', lambda e: self.destroy())
        self.bind('<Button-3>', lambda e: self.destroy())

        # 綁定 ESC 鍵關閉
        self.bind('<Escape>', lambda e: self.destroy())

        # 強制奪取焦點，確保按 ESC 鍵 100% 響應
        self.focus_force()
        self.canvas.focus_set()

    def update_wolf_box_from_coords(self):
        """根據當前敲狼點位精準計算草地外框矩形 (min_x, min_y, max_x, max_y)，忠實還原草地真實邊界"""
        if self.edit_wolf_coords and len(self.edit_wolf_coords) >= 1:
            xs = [pt[0] for pt in self.edit_wolf_coords]
            ys = [pt[1] for pt in self.edit_wolf_coords]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            try:
                cols = max(1, int(self.gui.wolf_cols_var.get()))
                rows = max(1, int(self.gui.wolf_rows_var.get()))
            except Exception:
                cols, rows = 3, 2

            # 計算單元格寬高 (中心點間距代表單元格大小)
            if cols > 1 and max_x > min_x:
                cell_w = (max_x - min_x) / (cols - 1)
            else:
                cell_w = 60

            if rows > 1 and max_y > min_y:
                cell_h = (max_y - min_y) / (rows - 1)
            else:
                cell_h = 50

            # 草地邊界為邊界格中心點往外延伸半個單元格，100% 吻合原始框選範圍
            bx1 = int(min_x - cell_w * 0.5)
            by1 = int(min_y - cell_h * 0.5)
            bx2 = int(max_x + cell_w * 0.5)
            by2 = int(max_y + cell_h * 0.5)

            self.wolf_box = [bx1, by1, bx2, by2]
            # 注意：嚴禁在此呼叫 self.regenerate_wolf_coords_from_box()！
            # 必須保持 edit_wolf_coords 100% 等同於實際點擊的 wolf_coords！
        else:
            self.wolf_box = None

    def regenerate_wolf_coords_from_box(self):
        """依據草地外框，上下平分 (rows)、左右平分 (cols)，將熱點精確設定於各子格子正中心"""
        if not self.wolf_box:
            return
        try:
            cols = max(1, int(self.gui.wolf_cols_var.get()))
            rows = max(1, int(self.gui.wolf_rows_var.get()))
        except Exception:
            cols, rows = 3, 2

        bx1, by1, bx2, by2 = self.wolf_box
        bw = max(40, bx2 - bx1)
        bh = max(40, by2 - by1)
        cell_w = bw / cols
        cell_h = bh / rows

        new_pts = []
        for r in range(rows):
            for c in range(cols):
                # 精確計算各子格子幾何正中心
                cx = int(bx1 + (c + 0.5) * cell_w)
                cy = int(by1 + (r + 0.5) * cell_h)
                new_pts.append([cx, cy])
        self.edit_wolf_coords = new_pts

    def setup_control_bar(self):
        """建立置頂中央浮動控制面板"""
        self.ctrl_frame = tk.Frame(self, bg='#212121', padx=14, pady=8, highlightbackground='#FFFFFF', highlightthickness=1)
        self.ctrl_frame.place(relx=0.5, y=18, anchor='n')

        self.status_lbl = tk.Label(self.ctrl_frame, text="💡 提示：按住標籤或圖示即可拖曳移動；拖曳四角縮放草地 | 【右鍵】或【ESC】關閉", font=('Microsoft JhengHei', 9, 'bold'), bg='#212121', fg='#FFEB3B')
        self.status_lbl.pack(side='left', padx=(0, 16))

        save_btn = tk.Button(self.ctrl_frame, text="💾 儲存並套用", command=self.save_and_apply, bg="#4CAF50", fg="white", font=('Microsoft JhengHei', 9, 'bold'), padx=8)
        save_btn.pack(side='left', padx=4)

        reset_btn = tk.Button(self.ctrl_frame, text="🔄 還原", command=self.reset_coords, bg="#FF9800", fg="white", font=('Microsoft JhengHei', 9, 'bold'), padx=6)
        reset_btn.pack(side='left', padx=4)

        close_btn = tk.Button(self.ctrl_frame, text="❌ 關閉 (右鍵/ESC)", command=self.destroy, bg="#E53935", fg="white", font=('Microsoft JhengHei', 9, 'bold'), padx=8)
        close_btn.pack(side='left', padx=4)

    def draw_overlay(self):
        """重繪畫布所有標記與互動把手"""
        c = self.canvas
        c.delete('overlay_item')
        ox = self.left
        oy = self.top
        self.label_hit_boxes = []

        # 輔助標記繪製函式
        def draw_pin(px, py, text, color, target_info, shape='circle', radius=14):
            rx = px - ox
            ry = py - oy

            if shape == 'circle':
                c.create_oval(rx - radius, ry - radius, rx + radius, ry + radius, outline=color, width=3, tags='overlay_item')
                c.create_oval(rx - 3, ry - 3, rx + 3, ry + 3, fill='red', outline='white', width=1, tags='overlay_item')
            elif shape == 'rect':
                c.create_rectangle(rx - radius, ry - radius, rx + radius, ry + radius, outline=color, width=3, tags='overlay_item')
                c.create_oval(rx - 3, ry - 3, rx + 3, ry + 3, fill='red', outline='white', width=1, tags='overlay_item')

            # 純文字標籤 (不顯示座標與括號，避免畫面繁雜)
            tx = rx + radius + 8
            ty = ry
            t_item = c.create_text(tx, ty, text=text, anchor='w', fill='white', font=('Microsoft JhengHei', 9, 'bold'), tags='overlay_item')
            bbox = c.bbox(t_item)
            if bbox:
                bx1, by1, bx2, by2 = bbox[0] - 6, bbox[1] - 3, bbox[2] + 6, bbox[3] + 3
                bg_item = c.create_rectangle(bx1, by1, bx2, by2, fill=color, outline='white', width=1, tags='overlay_item')
                c.tag_lower(bg_item, t_item)
                # 記錄標籤熱區，支援直接點擊標籤進行拖曳
                self.label_hit_boxes.append({
                    'rect': (bx1 + ox, by1 + oy, bx2 + ox, by2 + oy),
                    'target_info': target_info
                })

        # 1. 好友標記 (亮藍色)
        for idx, pt in enumerate(self.edit_coordinates, start=1):
            draw_pin(pt[0], pt[1], f"好友 #{idx}", '#1976D2', {'type': 'friend', 'idx': idx - 1}, shape='circle', radius=14)

        # 2. 敲狼草地範圍 (真正上下垂直平分、左右水平平分之子格子)
        if self.wolf_box:
            bx1, by1 = self.wolf_box[0] - ox, self.wolf_box[1] - oy
            bx2, by2 = self.wolf_box[2] - ox, self.wolf_box[3] - oy

            try:
                cols = max(1, int(self.gui.wolf_cols_var.get()))
                rows = max(1, int(self.gui.wolf_rows_var.get()))
            except Exception:
                cols, rows = 3, 2

            bw = bx2 - bx1
            bh = by2 - by1
            cell_w = bw / cols
            cell_h = bh / rows

            # (1) 繪製最外圍大框
            c.create_rectangle(bx1, by1, bx2, by2, outline='#E65100', width=2, tags='overlay_item')
            c.create_text(bx1 + 55, by1 - 12, text="🌾 敲狼草地", fill='#E65100', font=('Microsoft JhengHei', 9, 'bold'), tags='overlay_item')

            # (2) 繪製內部平分線 (垂直平分與水平平分線)
            for i in range(1, cols):
                lx = bx1 + i * cell_w
                c.create_line(lx, by1, lx, by2, fill='#FF9800', dash=(4, 4), width=1, tags='overlay_item')
            for j in range(1, rows):
                ly = by1 + j * cell_h
                c.create_line(bx1, ly, bx2, ly, fill='#FF9800', dash=(4, 4), width=1, tags='overlay_item')

            # (3) 繪製各子格子的正中心敲狼熱點 (精準居中，絕不重疊)
            for w_idx, pt in enumerate(self.edit_wolf_coords, start=1):
                rx, ry = pt[0] - ox, pt[1] - oy
                c.create_oval(rx - 8, ry - 8, rx + 8, ry + 8, outline='#FF5722', width=2, tags='overlay_item')
                c.create_oval(rx - 3, ry - 3, rx + 3, ry + 3, fill='#FF5722', outline='white', width=1, tags='overlay_item')
                w_item = c.create_text(rx, ry - 14, text=f"W{w_idx}", fill='#FFD54F', font=('Microsoft JhengHei', 9, 'bold'), tags='overlay_item')
                w_bbox = c.bbox(w_item)
                if w_bbox:
                    self.label_hit_boxes.append({
                        'rect': (w_bbox[0] + ox - 4, w_bbox[1] + oy - 2, w_bbox[2] + ox + 4, w_bbox[3] + oy + 2),
                        'target_info': {'type': 'wolf_pt', 'idx': w_idx - 1}
                    })

            # (4) 四角縮放把手 (Handle)
            hw = 7
            handles = [
                (bx1, by1, 'nw'),
                (bx2, by1, 'ne'),
                (bx1, by2, 'sw'),
                (bx2, by2, 'se')
            ]
            for hx, hy, tag in handles:
                c.create_rectangle(hx - hw, hy - hw, hx + hw, hy + hw, fill='#FFEB3B', outline='#E65100', width=2, tags='overlay_item')

        # 3. 翻頁按鈕 (青綠色)
        if self.edit_next_page_coord:
            draw_pin(self.edit_next_page_coord[0], self.edit_next_page_coord[1], "⏩ 翻頁", '#00897B', {'type': 'next_page'}, shape='circle', radius=14)

        # 4. 礦山座標 (琥珀金)
        if self.edit_mine_coord:
            draw_pin(self.edit_mine_coord[0], self.edit_mine_coord[1], "⛏️ 礦山", '#F57C00', {'type': 'mine'}, shape='rect', radius=16)

        # 5. 確定按鈕 (洋紅玫瑰紅)
        if self.edit_confirm_coord:
            draw_pin(self.edit_confirm_coord[0], self.edit_confirm_coord[1], "🎯 確定", '#D81B60', {'type': 'confirm'}, shape='rect', radius=18)

    def on_hover(self, event):
        """滑鼠懸停時動態切換游標樣式"""
        mx, my = event.x, event.y
        gx = mx + self.left
        gy = my + self.top

        # 1. 檢測是否在草地四角縮放把手上
        if self.wolf_box:
            bx1, by1 = self.wolf_box[0] - self.left, self.wolf_box[1] - self.top
            bx2, by2 = self.wolf_box[2] - self.left, self.wolf_box[3] - self.top
            hw = 8
            if abs(mx - bx1) <= hw and abs(my - by1) <= hw:
                self.canvas.config(cursor='size_nw_se')
                return
            if abs(mx - bx2) <= hw and abs(my - by1) <= hw:
                self.canvas.config(cursor='size_ne_sw')
                return
            if abs(mx - bx1) <= hw and abs(my - by2) <= hw:
                self.canvas.config(cursor='size_ne_sw')
                return
            if abs(mx - bx2) <= hw and abs(my - by2) <= hw:
                self.canvas.config(cursor='size_nw_se')
                return

        # 2. 檢測是否在標籤文字框上 (懸停游標提示)
        for item in getattr(self, 'label_hit_boxes', []):
            lx1, ly1, lx2, ly2 = item['rect']
            if lx1 <= gx <= lx2 and ly1 <= gy <= ly2:
                self.canvas.config(cursor='fleur')
                return

        # 3. 檢測是否在單點圖示上
        targets = []
        if self.edit_confirm_coord: targets.append((self.edit_confirm_coord, 22))
        if self.edit_mine_coord: targets.append((self.edit_mine_coord, 20))
        if self.edit_next_page_coord: targets.append((self.edit_next_page_coord, 20))
        for pt in self.edit_coordinates: targets.append((pt, 20))
        for pt in self.edit_wolf_coords: targets.append((pt, 12))

        for pt, r in targets:
            if (gx - pt[0]) ** 2 + (gy - pt[1]) ** 2 <= r ** 2:
                self.canvas.config(cursor='fleur')
                return

        # 4. 檢測是否在草地區域內
        if self.wolf_box:
            if self.wolf_box[0] <= gx <= self.wolf_box[2] and self.wolf_box[1] <= gy <= self.wolf_box[3]:
                self.canvas.config(cursor='hand2')
                return

        self.canvas.config(cursor='')

    def on_press(self, event):
        """滑鼠按下：命中檢測 (Hit-test)，支援標籤文字框與圖示拖曳"""
        mx, my = event.x, event.y
        gx = mx + self.left
        gy = my + self.top

        self.press_mx = mx
        self.press_my = my

        # 1. 優先檢測草地四角縮放把手
        if self.wolf_box:
            bx1, by1 = self.wolf_box[0] - self.left, self.wolf_box[1] - self.top
            bx2, by2 = self.wolf_box[2] - self.left, self.wolf_box[3] - self.top
            hw = 12
            for hx, hy, hname in [(bx1, by1, 'nw'), (bx2, by1, 'ne'), (bx1, by2, 'sw'), (bx2, by2, 'se')]:
                if abs(mx - hx) <= hw and abs(my - hy) <= hw:
                    self.drag_info = {
                        'type': 'wolf_handle',
                        'handle': hname,
                        'start_box': list(self.wolf_box)
                    }
                    self.status_lbl.config(text=f"📐 正在縮放草地覆蓋範圍 ({hname})...", fg="#FFD54F")
                    return

        # 2. 檢測是否點擊拖曳「標籤文字底框」
        for item in getattr(self, 'label_hit_boxes', []):
            lx1, ly1, lx2, ly2 = item['rect']
            if lx1 <= gx <= lx2 and ly1 <= gy <= ly2:
                info = item['target_info']
                ttype = info['type']
                if ttype == 'confirm':
                    self.drag_info = {'type': 'confirm', 'start_pt': list(self.edit_confirm_coord)}
                    self.status_lbl.config(text="🎯 正在移動【確定按鈕】座標...", fg="#FF4081")
                    return
                elif ttype == 'mine':
                    self.drag_info = {'type': 'mine', 'start_pt': list(self.edit_mine_coord)}
                    self.status_lbl.config(text="⛏️ 正在移動【礦山座標】...", fg="#FFB300")
                    return
                elif ttype == 'next_page':
                    self.drag_info = {'type': 'next_page', 'start_pt': list(self.edit_next_page_coord)}
                    self.status_lbl.config(text="⏩ 正在移動【翻頁按鈕】座標...", fg="#00E676")
                    return
                elif ttype == 'friend':
                    idx = info['idx']
                    self.drag_info = {'type': 'friend', 'idx': idx, 'start_pt': list(self.edit_coordinates[idx])}
                    self.status_lbl.config(text=f"👥 正在移動【好友 #{idx+1}】座標...", fg="#40C4FF")
                    return
                elif ttype == 'wolf_pt':
                    w_idx = info['idx']
                    self.drag_info = {'type': 'wolf_pt', 'idx': w_idx, 'start_pt': list(self.edit_wolf_coords[w_idx])}
                    self.status_lbl.config(text=f"🐺 正在微調【敲狼點 W{w_idx+1}】座標...", fg="#FF7043")
                    return

        # 3. 檢測單點圖示本體 (確定 > 礦山 > 翻頁 > 好友 > 敲狼熱點)
        if self.edit_confirm_coord and (gx - self.edit_confirm_coord[0]) ** 2 + (gy - self.edit_confirm_coord[1]) ** 2 <= 24 ** 2:
            self.drag_info = {'type': 'confirm', 'start_pt': list(self.edit_confirm_coord)}
            self.status_lbl.config(text="🎯 正在移動【確定按鈕】座標...", fg="#FF4081")
            return

        if self.edit_mine_coord and (gx - self.edit_mine_coord[0]) ** 2 + (gy - self.edit_mine_coord[1]) ** 2 <= 22 ** 2:
            self.drag_info = {'type': 'mine', 'start_pt': list(self.edit_mine_coord)}
            self.status_lbl.config(text="⛏️ 正在移動【礦山座標】...", fg="#FFB300")
            return

        if self.edit_next_page_coord and (gx - self.edit_next_page_coord[0]) ** 2 + (gy - self.edit_next_page_coord[1]) ** 2 <= 22 ** 2:
            self.drag_info = {'type': 'next_page', 'start_pt': list(self.edit_next_page_coord)}
            self.status_lbl.config(text="⏩ 正在移動【翻頁按鈕】座標...", fg="#00E676")
            return

        for idx, pt in enumerate(self.edit_coordinates):
            if (gx - pt[0]) ** 2 + (gy - pt[1]) ** 2 <= 20 ** 2:
                self.drag_info = {'type': 'friend', 'idx': idx, 'start_pt': list(pt)}
                self.status_lbl.config(text=f"👥 正在移動【好友 #{idx+1}】座標...", fg="#40C4FF")
                return

        for w_idx, pt in enumerate(self.edit_wolf_coords):
            if (gx - pt[0]) ** 2 + (gy - pt[1]) ** 2 <= 14 ** 2:
                self.drag_info = {'type': 'wolf_pt', 'idx': w_idx, 'start_pt': list(pt)}
                self.status_lbl.config(text=f"🐺 正在微調【敲狼點 W{w_idx+1}】座標...", fg="#FF7043")
                return

        # 4. 檢測點擊草地內部 (整塊平移草地)
        if self.wolf_box:
            if self.wolf_box[0] <= gx <= self.wolf_box[2] and self.wolf_box[1] <= gy <= self.wolf_box[3]:
                self.drag_info = {
                    'type': 'wolf_box_move',
                    'start_box': list(self.wolf_box),
                    'start_pts': [list(pt) for pt in self.edit_wolf_coords]
                }
                self.status_lbl.config(text="🌾 正在平移整塊【草地敲狼覆蓋範圍】...", fg="#FFB74D")
                return

        self.drag_info = None

    def on_motion(self, event):
        """滑鼠拖曳：即時計算位移並重繪"""
        if not self.drag_info:
            return

        dx = event.x - self.press_mx
        dy = event.y - self.press_my
        dtype = self.drag_info['type']

        if dtype == 'confirm':
            sp = self.drag_info['start_pt']
            self.edit_confirm_coord = [sp[0] + dx, sp[1] + dy]
            self.status_lbl.config(text=f"🎯 確定按鈕新座標: ({self.edit_confirm_coord[0]}, {self.edit_confirm_coord[1]})")

        elif dtype == 'mine':
            sp = self.drag_info['start_pt']
            self.edit_mine_coord = [sp[0] + dx, sp[1] + dy]
            self.status_lbl.config(text=f"⛏️ 礦山新座標: ({self.edit_mine_coord[0]}, {self.edit_mine_coord[1]})")

        elif dtype == 'next_page':
            sp = self.drag_info['start_pt']
            self.edit_next_page_coord = [sp[0] + dx, sp[1] + dy]
            self.status_lbl.config(text=f"⏩ 翻頁新座標: ({self.edit_next_page_coord[0]}, {self.edit_next_page_coord[1]})")

        elif dtype == 'friend':
            idx = self.drag_info['idx']
            sp = self.drag_info['start_pt']
            self.edit_coordinates[idx] = [sp[0] + dx, sp[1] + dy]
            self.status_lbl.config(text=f"👥 好友 #{idx+1} 新座標: ({self.edit_coordinates[idx][0]}, {self.edit_coordinates[idx][1]})")

        elif dtype == 'wolf_pt':
            idx = self.drag_info['idx']
            sp = self.drag_info['start_pt']
            self.edit_wolf_coords[idx] = [sp[0] + dx, sp[1] + dy]
            self.status_lbl.config(text=f"🐺 敲狼點 W{idx+1} 新座標: ({self.edit_wolf_coords[idx][0]}, {self.edit_wolf_coords[idx][1]})")

        elif dtype == 'wolf_handle':
            sb = self.drag_info['start_box']
            handle = self.drag_info['handle']
            bx1, by1, bx2, by2 = sb[0], sb[1], sb[2], sb[3]

            if handle == 'se':
                bx2 = max(bx1 + 40, sb[2] + dx)
                by2 = max(by1 + 40, sb[3] + dy)
            elif handle == 'nw':
                bx1 = min(bx2 - 40, sb[0] + dx)
                by1 = min(by2 - 40, sb[1] + dy)
            elif handle == 'ne':
                bx2 = max(bx1 + 40, sb[2] + dx)
                by1 = min(by2 - 40, sb[1] + dy)
            elif handle == 'sw':
                bx1 = min(bx2 - 40, sb[0] + dx)
                by2 = max(by1 + 40, sb[3] + dy)

            self.wolf_box = [bx1, by1, bx2, by2]
            self.regenerate_wolf_coords_from_box()
            self.status_lbl.config(text=f"📐 草地新範圍尺寸: {bx2 - bx1} x {by2 - by1} px")

        elif dtype == 'wolf_box_move':
            sb = self.drag_info['start_box']
            self.wolf_box = [sb[0] + dx, sb[1] + dy, sb[2] + dx, sb[3] + dy]
            spts = self.drag_info['start_pts']
            self.edit_wolf_coords = [[pt[0] + dx, pt[1] + dy] for pt in spts]
            self.status_lbl.config(text=f"🌾 草地已平移: dx={dx}, dy={dy}")

        self.draw_overlay()

    def on_release(self, event):
        """滑鼠放開：完成單次拖曳"""
        if self.drag_info:
            self.drag_info = None
            self.status_lbl.config(text="✔ 座標已即時調整！確認滿意後請點擊【💾 儲存並套用】", fg="#76FF03")

    def save_and_apply(self):
        """將目前調整後的座標寫回 GUI 並持久化至 config.json"""
        self.gui.coordinates = [tuple(pt) for pt in self.edit_coordinates]
        self.gui.wolf_coords = [tuple(pt) for pt in self.edit_wolf_coords]
        if self.edit_mine_coord:
            self.gui.mine_coord = tuple(self.edit_mine_coord)
        if self.edit_next_page_coord:
            self.gui.next_page_coord = tuple(self.edit_next_page_coord)
        if self.edit_confirm_coord:
            self.gui.confirm_coord = tuple(self.edit_confirm_coord)

        self.gui.update_coords()
        self.gui.update_wolf_info()
        self.gui.save_config()
        self.gui.auto.log("✔ [視覺化校正] 座標已透過螢幕拖曳成功更新並保存至 config.json！")
        self.status_lbl.config(text="✅ 成功儲存！所有座標已更新並保存至 config.json！", fg="#76FF03")

    def reset_coords(self):
        """還原為開啟時的原始座標"""
        self.edit_coordinates = [list(pt) for pt in self.orig_coordinates]
        self.edit_wolf_coords = [list(pt) for pt in self.orig_wolf_coords]
        self.edit_mine_coord = list(self.orig_mine_coord) if self.orig_mine_coord else None
        self.edit_next_page_coord = list(self.orig_next_page_coord) if self.orig_next_page_coord else None
        self.edit_confirm_coord = list(self.orig_confirm_coord) if self.orig_confirm_coord else None

        self.update_wolf_box_from_coords()
        self.draw_overlay()
        self.status_lbl.config(text="🔄 已還原至開啟時的原始座標", fg="#FFEB3B")

    def destroy(self):
        if hasattr(self.gui, 'screen_overlay') and self.gui.screen_overlay is self:
            self.gui.screen_overlay = None
        super().destroy()


class PreviewDialog(tk.Toplevel):
    """畫面座標預覽比對視窗"""
    def __init__(self, parent, gui):
        super().__init__(parent)
        self.gui = gui
        self.title("👁️ 畫面座標預覽比對 (Overlay Preview)")
        self.attributes('-topmost', True)
        self.geometry("980x720")

        self.img_cache = None
        self.photo_cache = None

        self.setup_ui()
        self.refresh_preview()

    def setup_ui(self):
        # 頂部控制列
        top_bar = tk.Frame(self, padx=10, pady=8, bg='#263238')
        top_bar.pack(fill='x')

        self.info_lbl = tk.Label(top_bar, text="正在獲取遊戲畫面...", font=('Arial', 10, 'bold'), bg='#263238', fg='#ECEFF1')
        self.info_lbl.pack(side='left', padx=4)

        refresh_btn = tk.Button(top_bar, text="🔄 刷新當前畫面", command=self.refresh_preview, bg="#4CAF50", fg="white", font=('Arial', 9, 'bold'))
        refresh_btn.pack(side='left', padx=10)

        close_btn = tk.Button(top_bar, text="關閉", command=self.destroy, font=('Arial', 9), width=8)
        close_btn.pack(side='right', padx=4)

        # 底部圖例標籤列
        legend_bar = tk.Frame(self, padx=10, pady=5, bg='#ECEFF1')
        legend_bar.pack(fill='x', side='bottom')
        legend_text = "● 藍圈: 好友點位 (#1~#6)  |  🌾 橘框: 敲狼草地與熱點 (W1~Wn)  |  ⏩ 綠色: 翻頁  |  ⛏️ 金色: 礦山  |  🎯 紅框: 確定按鈕"
        tk.Label(legend_bar, text=legend_text, font=('Arial', 9, 'bold'), bg='#ECEFF1', fg='#37474F').pack(side='left')

        # 中間預覽圖片展示區
        self.preview_container = tk.Frame(self, bg='#1E1E1E')
        self.preview_container.pack(fill='both', expand=True)

        self.preview_lbl = tk.Label(self.preview_container, bg='#1E1E1E')
        self.preview_lbl.pack(fill='both', expand=True, padx=6, pady=6)

    def refresh_preview(self):
        self.info_lbl.config(text="正在截取當前螢幕畫面並疊加座標標籤...")
        self.update_idletasks()

        img, err = self.gui.generate_preview_image()
        if err or img is None:
            self.info_lbl.config(text=f"❌ {err or '截圖失敗'}")
            return

        # 自適應縮放至視窗合適尺寸 (最大寬 960, 最大高 620)
        max_w, max_h = 960, 620
        orig_w, orig_h = img.size
        scale = min(max_w / orig_w, max_h / orig_h, 1.0)
        disp_w = max(1, int(orig_w * scale))
        disp_h = max(1, int(orig_h * scale))

        resized_img = img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        self.photo_cache = ImageTk.PhotoImage(resized_img)
        self.preview_lbl.config(image=self.photo_cache)

        pct = int(scale * 100)
        self.info_lbl.config(text=f"✔ 原始解析度: {orig_w}x{orig_h} | 縮放顯示: {pct}% | 請比對圖示紅點是否對齊按鈕！")


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
