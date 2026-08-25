# -*- coding: utf-8 -*-
# 原始檔案名: 漏普通狼打boss.py
# 編譯環境: Python 3.8

import sys, os, ctypes

# 取得圖片目錄路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, 'images')

def get_image_path(filename):
    return os.path.join(IMAGE_DIR, filename)

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

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import pyautogui, time, threading
from datetime import datetime

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


class BossAutoClicker:

    def __init__(self, root):
        self.root = root
        admin_status = "【管理员】" if is_admin() else "【普通用户】"
        self.root.title(f"该脚本由“鹏小白是我”分享-打BOSS {admin_status}")
        self.root.geometry("300x520")
        self.topmost = True
        self.root.attributes("-topmost", self.topmost)
        self.running = False
        self.thread = None
        self.create_widgets()

    def create_widgets(self):
        title_label = tk.Label(self.root, text="漏小怪 打BOSS", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # 權限顯示區域
        admin_frame = tk.Frame(self.root)
        admin_frame.pack(padx=10, pady=5, fill="x")
        if is_admin():
            admin_label = tk.Label(admin_frame, text="✓ 管理员权限", fg="green", font=('Arial', 10))
        else:
            admin_label = tk.Label(admin_frame, text="⚠ 非管理员权限运行", fg="orange", font=('Arial', 10))
        admin_label.pack(side=tk.LEFT)
        
        if not is_admin():
            elevate_btn = tk.Button(admin_frame,
              text="以管理员身份运行",
              command=self.request_admin,
              bg="#FF9800",
              fg="white",
              font=('Arial', 9))
            elevate_btn.pack(side=tk.RIGHT)
        
        # 運行狀態顯示
        status_frame = tk.LabelFrame(self.root, text="运行状态", padx=10, pady=10)
        status_frame.pack(padx=10, pady=5, fill="x")
        self.status_label = tk.Label(status_frame, text="状态: 未运行", font=('Arial', 12), fg="red")
        self.status_label.pack(side=tk.LEFT)
        
        self.topmost_var = tk.BooleanVar(value=self.topmost)
        topmost_check = tk.Checkbutton(status_frame,
          text="窗口置顶",
          variable=self.topmost_var,
          command=self.toggle_topmost)
        topmost_check.pack(side=tk.RIGHT)
        
        # 控制按鈕
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10)
        self.start_button = tk.Button(control_frame, text="开始运行", command=self.start_automation,
          bg="#4CAF50",
          fg="white",
          font=('Arial', 12, 'bold'),
          width=12,
          height=2)
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = tk.Button(control_frame, text="停止运行", command=self.stop_automation,
          bg="#f44336",
          fg="white",
          font=('Arial', 12, 'bold'),
          width=12,
          height=2,
          state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        # 參數設置
        settings_frame = tk.LabelFrame(self.root, text="设置参数", padx=10, pady=10)
        settings_frame.pack(padx=10, pady=5, fill="x")
        
        interval_frame = tk.Frame(settings_frame)
        interval_frame.pack(fill="x", pady=5)
        tk.Label(interval_frame, text="循环间隔(分钟):").pack(side="left")
        self.interval_var = tk.StringVar(value="10")
        interval_entry = tk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        interval_entry.pack(side="left", padx=5)
        
        confidence_frame = tk.Frame(settings_frame)
        confidence_frame.pack(fill="x", pady=10)
        tk.Label(confidence_frame, text="匹配阈值:").pack(side="left")
        self.confidence_var = tk.DoubleVar(value=0.9)
        confidence_slider = ttk.Scale(confidence_frame,
          from_=0.5,
          to=1.0,
          variable=self.confidence_var,
          orient="horizontal",
          length=120,
          command=lambda v: self.update_confidence_label(v))
        confidence_slider.pack(side="left", padx=5)
        self.confidence_label = tk.Label(confidence_frame, text="0.90", width=6)
        self.confidence_label.pack(side="left")
        
        # 運行日誌
        log_frame = tk.LabelFrame(self.root, text="运行日志", padx=10, pady=10)
        log_frame.pack(padx=10, pady=5, fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=55)
        self.log_text.pack(fill="both", expand=True)
        
        clear_log_button = tk.Button(self.root, text="清空日志", command=self.clear_log)
        clear_log_button.pack(pady=5)

    def request_admin(self):
        """请求管理员权限"""
        result = messagebox.askyesno("提升权限", "程序将以管理员身份重新启动\n当前窗口将关闭\n是否继续？")
        if result:
            run_as_admin()

    def update_confidence_label(self, value):
        """更新置信度顯示標籤"""
        self.confidence_label.config(text=f"{float(value):.2f}")

    def toggle_topmost(self):
        """切换窗口置顶状态"""
        self.topmost = self.topmost_var.get()
        self.root.attributes("-topmost", self.topmost)
        status = "开启" if self.topmost else "关闭"
        self.log(f"窗口置顶已{status}")

    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        print(log_message, end="", flush=True)

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)

    def find_and_click(self, image_path, confidence):
        """在螢幕上尋找圖片並點擊，成功點擊回傳 True，否則回傳 False"""
        friendly_names = {
            "bosscha.png": "Boss視窗關閉鈕 (bosscha.png)",
            "cha.png": "關閉叉叉鈕 (cha.png)",
            "queding.png": "確定按鈕 (queding.png)",
            "boss.png": "普通Boss (boss.png)",
            "4boss.png": "4階Boss (4boss.png)",
            "gongji.png": "攻擊按鈕 (gongji.png)",
            "yiban.png": "一般小怪 (yiban.png)",
            "putong.png": "普通小怪 (putong.png)",
            "kunnan.png": "困難小怪 (kunnan.png)",
            "qugan.png": "驅趕按鈕 (qugan.png)"
        }
        friendly_name = friendly_names.get(image_path, image_path)

        try:
            pos = pyautogui.locateCenterOnScreen(get_image_path(image_path), confidence=confidence)
            if pos is not None:
                pyautogui.moveTo(pos)
                time.sleep(0.05)
                pyautogui.mouseDown()
                time.sleep(0.1)
                pyautogui.mouseUp()
                self.log(f"找到並點擊: {friendly_name}")
                return True
            self.log(f"未在螢幕上看到: {friendly_name}")
            return False
        except Exception as e:
            err_msg = str(e)
            if not err_msg or "ImageNotFoundException" in type(e).__name__ or "NoneType" in err_msg:
                self.log(f"未在螢幕上看到: {friendly_name}")
            else:
                self.log(f"圖像辨識出錯 - {friendly_name}: {err_msg}")
            return False

    def find_and_click_with_retry(self, image_path, confidence, retries=6, delay=0.3):
        """嘗試在一段時間內反覆尋找並點擊（應對遊戲視窗彈出動畫延遲）"""
        for i in range(retries):
            try:
                pos = pyautogui.locateCenterOnScreen(get_image_path(image_path), confidence=confidence)
                if pos is not None:
                    pyautogui.moveTo(pos)
                    time.sleep(0.05)
                    pyautogui.mouseDown()
                    time.sleep(0.1)
                    pyautogui.mouseUp()
                    friendly_names = {
                        "bosscha.png": "Boss視窗關閉鈕 (bosscha.png)",
                        "cha.png": "關閉叉叉鈕 (cha.png)",
                        "queding.png": "確定按鈕 (queding.png)",
                        "boss.png": "普通Boss (boss.png)",
                        "4boss.png": "4階Boss (4boss.png)",
                        "gongji.png": "攻擊按鈕 (gongji.png)",
                        "yiban.png": "一般小怪 (yiban.png)",
                        "putong.png": "普通小怪 (putong.png)",
                        "kunnan.png": "困難小怪 (kunnan.png)",
                        "qugan.png": "驅趕按鈕 (qugan.png)"
                    }
                    friendly_name = friendly_names.get(image_path, image_path)
                    self.log(f"找到並點擊: {friendly_name}")
                    return True
            except Exception:
                # 靜默忽略重試期間的「找不到圖片」異常
                pass
            time.sleep(delay)
        return self.find_and_click(image_path, confidence)

    def image_exists(self, image_path, confidence):
        """僅僅檢查圖片是否存在，不進行點擊，且不會因為找不到圖片而拋出異常崩潰"""
        try:
            pos = pyautogui.locateOnScreen(get_image_path(image_path), confidence=confidence)
            return pos is not None
        except Exception:
            return False

    def automation_cycle(self):
        """自動化點擊循環邏輯"""
        confidence = self.confidence_var.get()
        try:
            self.log("--- 开始新循环 ---")
            self.log("点击关闭和确定按钮...")
            time.sleep(0.1)
            pyautogui.moveTo(1, 1) # 滑鼠移到角落，避免阻擋識別
            time.sleep(0.5)
            
            # 1. 優先關閉無關彈窗或點擊確定
            self.find_and_click("bosscha.png", confidence)
            time.sleep(0.5)
            self.find_and_click("cha.png", confidence)
            time.sleep(0.5)
            self.find_and_click("queding.png", confidence)
            time.sleep(1)
            
            # 2. 開始搜尋 BOSS 並攻擊
            self.log("开始扫描Boss状态...")
            if self.find_and_click("boss.png", confidence):
                # 點擊 Boss 後，因為視窗彈出有動畫，使用帶重試的點擊
                self.find_and_click_with_retry("gongji.png", confidence, retries=6, delay=0.3)
                time.sleep(1)
            elif self.find_and_click("4boss.png", confidence):
                # 點擊 Boss 後，使用帶重試的點擊
                self.find_and_click_with_retry("gongji.png", confidence, retries=6, delay=0.3)
                time.sleep(1)
            else:
                # 3. 如果沒有 Boss，則處理小怪驅趕
                self.log("未發現Boss，開始檢查地圖中是否有小怪...")
                
                # 使用安全的檢測方法，防止找不到小怪時拋出 ImageNotFoundException 崩潰
                has_yiban = self.image_exists("yiban.png", confidence)
                has_putong = self.image_exists("putong.png", confidence)
                has_kunnan = self.image_exists("kunnan.png", confidence)
                
                if has_yiban or has_putong or has_kunnan:
                    detected_types = []
                    if has_yiban: detected_types.append("一般小怪")
                    if has_putong: detected_types.append("普通小怪")
                    if has_kunnan: detected_types.append("困難小怪")
                    self.log(f"地圖中偵測到小怪: {', '.join(detected_types)}，準備執行驅趕...")
                    
                    # 直接點擊常駐在螢幕上的驅趕按鈕
                    if self.find_and_click("qugan.png", confidence):
                        self.find_and_click_with_retry("queding.png", confidence, retries=6, delay=0.3)
                        time.sleep(1)
                else:
                    self.log("地圖中無小怪 (一般/普通/困難已全部打完)，無需執行驅趕")
        except Exception as e:
            import traceback
            err_details = traceback.format_exc()
            self.log(f"循環錯誤！詳細錯誤資訊如下：\n{err_details}")

    def automation_thread(self):
        """自動化執行緒"""
        try:
            interval_minutes = int(self.interval_var.get())
            interval_seconds = interval_minutes * 60
            self.log(f"自动化程序已启动，每{interval_minutes}分钟循环一次")
            while self.running:
                self.automation_cycle()
                if self.running:
                    self.log(f"等待{interval_minutes}分钟后进行下一次循环...")
                    # 用 1 秒的細粒度循環睡眠，以便隨時響應「停止運行」按鈕
                    for i in range(interval_seconds):
                        if not self.running:
                            break
                        time.sleep(1)
            self.log("自动化程序已停止")
        except ValueError:
            self.log("错误：循环间隔必须是整数")
            self.stop_automation()

    def start_automation(self):
        """开始自动化"""
        if not self.running:
            self.running = True
            self.status_label.config(text="状态: 运行中", fg="green")
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.thread = threading.Thread(target=self.automation_thread, daemon=True)
            self.thread.start()

    def stop_automation(self):
        """停止自动化"""
        if self.running:
            self.running = False
            self.status_label.config(text="状态: 已停止", fg="red")
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.log("正在停止程序...")


def main():
    if not is_admin():
        result = messagebox.askyesno("权限提示", "检测到程序未以管理员身份运行\n某些功能可能无法正常工作\n\n是否以管理员身份重新启动？\n（选择'否'将继续以普通用户身份运行）")
        if result:
            run_as_admin()
            return
    root = tk.Tk()
    app = BossAutoClicker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
