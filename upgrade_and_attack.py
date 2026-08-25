# -*- coding: utf-8 -*-
import sys
import os
import ctypes

# 啟用 Windows DPI 自適應，防止螢幕縮放時滑鼠點偏
# 注意：此宣告必須在 import pyautogui 之前，否則 pyautogui 載入時解析度會初始化錯誤！
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import cv2
import pyautogui
import numpy as np
import time
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import pynput
from datetime import datetime

# 取得圖片目錄路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, 'images')

def get_image_path(filename):
    return os.path.join(IMAGE_DIR, filename)

class TowerAutomation:
    """自动化功能"""
    def __init__(self, gui):
        self.gui = gui
        # 升塔需要的圖片
        self.tower_images = [
            get_image_path('shengji.png'),
            get_image_path('liliang.png'),
            get_image_path('jiahao.png'),
            get_image_path('queding.png'),
            get_image_path('tacha.png')
        ]
        self.tower_running = False
        self.monster_running = False
        self.match_threshold = 0.9
        self.default_delay = 2

        # 圖片友善中文名稱對照表
        self.friendly_names = {
            'shengji.png': '升級按鈕 (shengji.png)',
            'liliang.png': '空閒力量標誌 (liliang.png)',
            'liliang_gongzuo.png': '工作中力量標誌 (liliang_gongzuo.png)',
            'jiahao.png': '加號按鈕 (jiahao.png)',
            'queding.png': '確定按鈕 (queding.png)',
            'tacha.png': '關閉叉叉 (tacha.png)',
            'gongji.png': '攻擊按鈕 (gongji.png)',
            'bosscha.png': 'Boss叉叉 (bosscha.png)'
        }

    def log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        self.gui.log_text.insert('end', log_message + '\n')
        self.gui.log_text.see('end')

    def start_tower(self):
        if not self.gui.coordinates:
            self.log('错误: 未添加坐标，请先添加坐标')
            return
        if self.tower_running:
            return
        self.tower_running = True
        self.gui.start_tower_btn.config(state='disabled')
        self.gui.stop_tower_btn.config(state='normal')
        self.log('升塔已启动')
        threading.Thread(target=self.tower_loop, daemon=True).start()

    def stop_tower(self):
        self.tower_running = False
        self.gui.start_tower_btn.config(state='normal')
        self.gui.stop_tower_btn.config(state='disabled')
        self.log('升塔已停止')

    def tower_loop(self):
        try:
            click_interval = float(self.gui.interval_var.get())
            cycle_interval = float(self.gui.cycle_var.get())
            click_times = int(self.gui.click_times_var.get())
        except Exception:
            click_interval = 1.0
            cycle_interval = 60.0
            click_times = 20

        while True:
            time.sleep(0.2)
            if not self.tower_running:
                break
            
            for coord in self.gui.coordinates:
                if not self.tower_running:
                    break
                x, y = coord
                pyautogui.leftClick(x, y)
                self.log(f'点击防禦塔坐标: ({x}, {y})')
                time.sleep(click_interval)
                
                # 第一步：嘗試點擊升級按鈕
                if self.click_image(get_image_path('shengji.png'), silent_fail=True):
                    time.sleep(0.8)
                
                # 第二步：尋找所有空閒苦工、工作中苦工與排除標誌
                if not self.tower_running: break
                path_idle = get_image_path('liliang.png')
                path_work = get_image_path('liliang_gongzuo.png')
                path_exclude = get_image_path('liliang_exclude.png')
                
                try:
                    tpl_idle = cv2.imdecode(np.fromfile(path_idle, dtype=np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    tpl_idle = None
                    
                try:
                    tpl_work = cv2.imdecode(np.fromfile(path_work, dtype=np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    tpl_work = None
                    
                try:
                    tpl_exclude = cv2.imdecode(np.fromfile(path_exclude, dtype=np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    tpl_exclude = None
                    
                points_idle = []
                points_work = []
                points_exclude = []
                
                screenshot = self.gui.capture_screen()
                if screenshot is not None:
                    if tpl_idle is not None:
                        points_idle = self.find_all_images(tpl_idle, screenshot)
                    if tpl_work is not None:
                        points_work = self.find_all_images(tpl_work, screenshot)
                    if tpl_exclude is not None:
                        points_exclude = self.find_all_images(tpl_exclude, screenshot)
                
                # 進行 exclude 排除過濾
                filtered_idle = []
                for pt in points_idle:
                    is_excluded = False
                    for ex_pt in points_exclude:
                        if abs(pt[0] - ex_pt[0]) < 15 and abs(pt[1] - ex_pt[1]) < 15:
                            is_excluded = True
                            break
                    if not is_excluded:
                        filtered_idle.append(pt)
                        
                filtered_work = []
                for pt in points_work:
                    is_excluded = False
                    for ex_pt in points_exclude:
                        if abs(pt[0] - ex_pt[0]) < 15 and abs(pt[1] - ex_pt[1]) < 15:
                            is_excluded = True
                            break
                    if not is_excluded:
                        filtered_work.append(pt)
                
                # 輸出包含排除結果的辨識日誌
                exclude_count = len(points_idle) - len(filtered_idle) + len(points_work) - len(filtered_work)
                if exclude_count > 0:
                    self.log(f'辨識到空閒苦工: {len(filtered_idle)} 個，工作中苦工: {len(filtered_work)} 個 (已排除 {exclude_count} 個其它功能符號)')
                else:
                    self.log(f'辨識到空閒苦工: {len(filtered_idle)} 個，工作中苦工: {len(filtered_work)} 個')
                
                if filtered_idle:
                    self.log(f'由左至右嘗試點擊 {len(filtered_idle)} 個空閒苦工...')
                    success = False
                    for pt in filtered_idle:
                        if not self.tower_running: break
                        self.click_center(tpl_idle, pt)
                        self.log(f'點擊空閒苦工坐標: {pt}')
                        time.sleep(0.8) # 等待加號彈出
                        
                        # 檢查是否出現加號
                        if self.click_image(get_image_path('jiahao.png'), silent_fail=True):
                            self.log(f'發現空閒苦工！開始連點 {click_times} 次...')
                            self.click_current(click_times)
                            time.sleep(0.5)
                            
                            # 點擊確定
                            self.click_image(get_image_path('queding.png'), silent_fail=True)
                            success = True
                            break
                        else:
                            self.log('該苦工無加號(可能剛進入工作狀態)，嘗試下一個...')
                            
                    if not success:
                        self.log('所有空閒苦工皆嘗試完畢或辨識失敗。')
                else:
                    self.log('未偵測到任何空閒中的苦工標誌 (liliang.png)。')
                
                # 關閉面板 (若有叉叉)
                self.click_image(get_image_path('tacha.png'), silent_fail=True)
                
            if not self.tower_running:
                break
            self.log(f'等待 {cycle_interval} 秒...')
            self.wait_tower(cycle_interval)

    def wait_tower(self, seconds):
        # 細粒度循環睡眠，便於隨時響應停止按鈕
        for _ in range(int(seconds)):
            if not self.tower_running:
                return
            time.sleep(1)

    def start_monster(self):
        if self.monster_running:
            return
        self.monster_running = True
        self.gui.start_monster_btn.config(state='disabled')
        self.gui.stop_monster_btn.config(state='normal')
        self.log('打怪已启动')
        threading.Thread(target=self.monster_loop, daemon=True).start()

    def stop_monster(self):
        self.monster_running = False
        self.gui.start_monster_btn.config(state='normal')
        self.gui.stop_monster_btn.config(state='disabled')
        self.log('打怪已停止')

    def monster_loop(self):
        while self.monster_running:
            try:
                # 1. 優先處理彈窗（靜默處理，找不到不印日誌，找到了印日誌）
                if self.click_image(get_image_path('queding.png'), silent_fail=True):
                    time.sleep(self.default_delay)
                    continue
                
                if self.click_image(get_image_path('bosscha.png'), silent_fail=True):
                    time.sleep(self.default_delay)
                    continue
                
                # 2. 尋找怪物並點擊（若找不到輸出「未在螢幕上看到」並等待10分鐘）
                if self.click_image(get_image_path('gongji.png'), silent_fail=False):
                    time.sleep(0.1)
                    pyautogui.moveTo(1, 1) # 滑鼠移到角落，避免阻擋識別
                    
                    self.log('已發動攻擊，進入 60 秒戰鬥期...')
                    for _ in range(60):
                        if not self.monster_running:
                            return
                        time.sleep(1)
                        
                    screenshot2 = self.gui.capture_screen()
                    try:
                        monster_tpl = cv2.imdecode(np.fromfile(get_image_path('gongji.png'), dtype=np.uint8), cv2.IMREAD_COLOR)
                    except Exception:
                        monster_tpl = None
                    if self.find_image(monster_tpl, screenshot2):
                        self.log('60秒戰鬥結束: 怪物仍在')
                    else:
                        self.log('60秒戰鬥結束: 怪物已消失，等待10分鐘')
                        self.wait(600)
                else:
                    self.log('未發現怪物，等待10分鐘')
                    self.wait(600)
            except Exception as e:
                self.log(f'错误: {e}')
                time.sleep(5)

    def wait(self, seconds):
        for _ in range(seconds):
            if not self.monster_running:
                return
            time.sleep(1)

    def find_image(self, target, screenshot):
        if target is None or screenshot is None:
            return None
        if target.shape[0] > screenshot.shape[0] or target.shape[1] > screenshot.shape[1]:
            return None
        
        result = cv2.matchTemplate(screenshot, target, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        threshold = self.gui.threshold_var.get() / 100.0
        if max_val >= threshold:
            return max_loc
        return None

    def find_all_images(self, target, screenshot):
        if target is None or screenshot is None:
            return []
        if target.shape[0] > screenshot.shape[0] or target.shape[1] > screenshot.shape[1]:
            return []
        
        result = cv2.matchTemplate(screenshot, target, cv2.TM_CCOEFF_NORMED)
        threshold = self.gui.threshold_var.get() / 100.0
        
        locations = np.where(result >= threshold)
        points = []
        for pt in zip(*locations[::-1]):
            # 簡單過濾太接近的點，避免同一個按鈕回傳多個相近座標
            too_close = False
            for p in points:
                if abs(p[0] - pt[0]) < 10 and abs(p[1] - pt[1]) < 10:
                    too_close = True
                    break
            if not too_close:
                points.append(pt)
                
        # 依照 X 座標由小到大排序 (從左到右)
        points.sort(key=lambda p: p[0])
        return points

    def click_center(self, image, location):
        h, w = image.shape[:2]
        x = location[0] + w // 2
        y = location[1] + h // 2
        if self.gui.screenshot_area:
            x += self.gui.screenshot_area[0]
            y += self.gui.screenshot_area[1]
        pyautogui.leftClick(x, y)

    def click_image(self, path, silent_fail=False):
        filename = os.path.basename(path)
        friendly_name = self.friendly_names.get(filename, filename)
        
        if not os.path.exists(path):
            self.log(f'錯誤: 圖片檔案不存在 - {friendly_name}')
            return False
        
        # 支援 Windows 中文路徑的讀取方式
        try:
            template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            template = None
            
        if template is None:
            self.log(f'錯誤: 圖片載入失敗 - {friendly_name}')
            return False
        screenshot = self.gui.capture_screen()
        if screenshot is None:
            self.log('錯誤: 螢幕截圖失敗')
            return False
        location = self.find_image(template, screenshot)
        if location:
            self.click_center(template, location)
            self.log(f'找到並點擊: {friendly_name}')
            time.sleep(self.default_delay)
            return True
        if not silent_fail:
            self.log(f'未在螢幕上看到: {friendly_name}')
        return False

    def click_current(self, times):
        x, y = pyautogui.position()
        for _ in range(times):
            if not self.tower_running:
                break
            pyautogui.click(x, y)
            time.sleep(0.01)

class GUI:
    def __init__(self, root):
        self.root = root
        admin_status = "【管理员】" if is_admin() else "【普通用户】"
        self.root.title(f"该脚本由“鹏小白是我”分享-升塔&打怪 {admin_status}")
        self.root.geometry('350x640')
        self.coordinates = []
        self.screenshot_area = None
        self.capturing = False
        self.keyboard_listener = None
        self.auto = TowerAutomation(self)
        self.topmost = False
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.root, padx=8, pady=8)
        main.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(main)
        header_frame.pack(fill='x', pady=3)

        title_lbl = tk.Label(header_frame, text='1000分 自动升塔&打怪', font=('Arial', 14, 'bold'))
        title_lbl.pack(side='left')

        self.topmost_btn = tk.Button(header_frame, text='窗口置顶', command=self.toggle_topmost, bg='SystemButtonFace', width=10)
        self.topmost_btn.pack(side='right', padx=5)

        # 權限顯示區域
        admin_frame = tk.Frame(main)
        admin_frame.pack(pady=3, fill="x")
        if is_admin():
            admin_label = tk.Label(admin_frame, text="✓ 管理员权限", fg="green", font=('Arial', 9))
        else:
            admin_label = tk.Label(admin_frame, text="⚠ 非管理员权限运行", fg="orange", font=('Arial', 9))
        admin_label.pack(side=tk.LEFT)
        
        if not is_admin():
            elevate_btn = tk.Button(admin_frame,
              text="以管理员身份运行",
              command=self.request_admin,
              bg="#FF9800",
              fg="white",
              font=('Arial', 8),
              pady=1)
            elevate_btn.pack(side=tk.RIGHT)

        tower = tk.LabelFrame(main, text='升塔', padx=5, pady=3)
        tower.pack(fill='x', pady=3)

        tf = tk.Frame(tower)
        tf.pack(fill='x')

        self.start_tower_btn = tk.Button(tf, text='启动', command=self.auto.start_tower)
        self.start_tower_btn.pack(side='left', expand=True, fill='x', padx=1)

        self.stop_tower_btn = tk.Button(tf, text='停止', command=self.auto.stop_tower, state='disabled')
        self.stop_tower_btn.pack(side='left', expand=True, fill='x', padx=1)

        monster = tk.LabelFrame(main, text='打怪', padx=5, pady=3)
        monster.pack(fill='x', pady=3)

        mf = tk.Frame(monster)
        mf.pack(fill='x')

        self.start_monster_btn = tk.Button(mf, text='启动', command=self.auto.start_monster)
        self.start_monster_btn.pack(side='left', expand=True, fill='x', padx=1)

        self.stop_monster_btn = tk.Button(mf, text='停止', command=self.auto.stop_monster, state='disabled')
        self.stop_monster_btn.pack(side='left', expand=True, fill='x', padx=1)

        coord = tk.LabelFrame(main, text='坐标', padx=5, pady=3)
        coord.pack(fill='both', expand=True, pady=3)

        cf = tk.Frame(coord)
        cf.pack(fill='x')

        add_btn = tk.Button(cf, text='添加(K键)', command=self.start_capture, width=10)
        add_btn.pack(side='left', padx=1)

        cancel_btn = tk.Button(cf, text='取消(ESC)', command=self.stop_capture, width=10)
        cancel_btn.pack(side='left', padx=1)

        clear_btn = tk.Button(cf, text='清空', command=self.clear_coords, width=8)
        clear_btn.pack(side='left', padx=1)

        self.coord_list = tk.Listbox(coord, height=4, font=('Arial', 8))
        self.coord_list.pack(fill='both', expand=True, pady=3)

        sf = tk.Frame(main)
        sf.pack(fill='x', pady=3)

        tk.Label(sf, text='点击间隔:', font=('Arial', 8)).pack(side='left')
        self.interval_var = tk.StringVar(value='1')
        tk.Entry(sf, textvariable=self.interval_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)

        tk.Label(sf, text='循环间隔:', font=('Arial', 8)).pack(side='left', padx=(8, 0))
        self.cycle_var = tk.StringVar(value='60')
        tk.Entry(sf, textvariable=self.cycle_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)

        click_times_frame = tk.Frame(main)
        click_times_frame.pack(fill='x', pady=3)

        tk.Label(click_times_frame, text='连点次数:', font=('Arial', 8)).pack(side='left')
        self.click_times_var = tk.StringVar(value='20')
        tk.Entry(click_times_frame, textvariable=self.click_times_var, width=4, font=('Arial', 8)).pack(side='left', padx=2)
        tk.Label(click_times_frame, text='(升塔时加号连点)', font=('Arial', 7), fg='gray').pack(side='left', padx=5)

        threshold_frame = tk.LabelFrame(main, text='图像匹配阈值', padx=5, pady=3)
        threshold_frame.pack(fill='x', pady=3)

        threshold_control = tk.Frame(threshold_frame)
        threshold_control.pack(fill='x')

        tk.Label(threshold_control, text='阈值:', font=('Arial', 10)).pack(side='left')
        self.threshold_var = tk.IntVar(value=90)
        self.threshold_scale = tk.Scale(threshold_control, from_=50, to=100, orient=tk.HORIZONTAL, variable=self.threshold_var, length=200, command=self.on_threshold_change)
        self.threshold_scale.pack(side='left', padx=5)

        self.threshold_label = tk.Label(threshold_control, text='90%', font=('Arial', 8), width=5)
        self.threshold_label.pack(side='left')

        log_frame = tk.LabelFrame(main, text='日志', padx=3, pady=3)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=3)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, font=('Arial', 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def request_admin(self):
        result = messagebox.askyesno("提升权限", "程序将以管理员身份重新启动\n当前窗口将关闭\n是否继续？")
        if result:
            run_as_admin()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes('-topmost', self.topmost)
        if self.topmost:
            self.topmost_btn.config(bg='lightgreen', relief='sunken')
            self.auto.log('窗口置顶已开启')
        else:
            self.topmost_btn.config(bg='SystemButtonFace', relief='raised')
            self.auto.log('窗口置顶已关闭')

    def on_threshold_change(self, value):
        self.threshold_label.config(text=f'{value}%')

    def start_capture(self):
        if self.capturing:
            return
        self.capturing = True
        self.keyboard_listener = pynput.keyboard.Listener(on_press=self.on_key)
        self.keyboard_listener.start()
        self.auto.log('按K键添加坐标，ESC取消')

    def on_key(self, key):
        if not self.capturing:
            return False
        try:
            if key.char and key.char.lower() == 'k':
                x, y = pyautogui.position()
                self.coordinates.append((int(x), int(y)))
                self.root.after(0, self.update_coords)
                self.root.after(0, lambda: self.auto.log(f'已添加: ({x}, {y})'))
                return True
        except AttributeError:
            if key == pynput.keyboard.Key.esc:
                self.root.after(0, self.stop_capture)
                return False
        return True

    def stop_capture(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.capturing = False
        self.auto.log('取消添加')

    def clear_coords(self):
        self.coordinates.clear()
        self.update_coords()
        self.auto.log('已清空坐标')

    def update_coords(self):
        self.coord_list.delete(0, tk.END)
        for i, (x, y) in enumerate(self.coordinates):
            self.coord_list.insert(tk.END, f'{i+1}. ({x}, {y})')

    def capture_screen(self):
        try:
            if self.screenshot_area:
                screenshot = pyautogui.screenshot(region=self.screenshot_area)
            else:
                screenshot = pyautogui.screenshot()
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception:
            return None

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
            params = " ".join([script] + sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit(0)
    except Exception as e:
        messagebox.showerror("错误", f"无法以管理员身份运行: {str(e)}")
        sys.exit(1)

def main():
    if not is_admin():
        result = messagebox.askyesno("权限提示", "检测到程序未以管理员身份运行\n某些功能可能无法正常工作\n\n是否以管理员身份重新启动？\n（选择'否'将继续以普通用户身份运行）")
        if result:
            run_as_admin()
            return

    root = tk.Tk()
    app = GUI(root)
    
    def on_close():
        if app.keyboard_listener:
            app.keyboard_listener.stop()
        app.auto.tower_running = False
        app.auto.monster_running = False
        root.destroy()
        
    root.protocol('WM_DELETE_WINDOW', on_close)
    root.mainloop()

if __name__ == '__main__':
    main()
