# 保衛羊村 - 自動化輔助工具 (Sheep Village Automation)

本專案提供網頁遊戲《保衛羊村》的 Python 自動化輔助工具，整合 OpenCV 圖像辨識與 PyAutoGUI 模擬操作。

---

## 核心功能

### 1. 敲狼與加速礦 (`wolf_mine_speedup.py`)
- **草地網格覆蓋敲狼**：支援兩點框選草地範圍自動生成網格熱點（或按 `K` 鍵標記），100% 盲敲命中隱藏在木桶內的間諜狼。
- **好友循序巡邏**：自動進入好友家園進行驅趕敲狼與沙漏加速。
- **邀請彈窗防護**：到達好友列表末端觸發「暫時不支持邀請好友」彈窗時，自動安全終止並返回自己家園。
- **參數與點位記憶**：所有設定與自訂座標自動保存在 `config.json`。

### 2. BOSS 自動點擊 (`boss_auto_clicker.py`)
- 針對世界 BOSS 與活動 BOSS 進行高速自動連點與驅趕。

### 3. 升級與自動攻擊 (`upgrade_and_attack.py`)
- 自動辨識可升級之防禦塔並執行升級與攻擊操作。

---

## 目錄結構

```text
sheep-village-automation/
│
├── images/                      # 圖像辨識比對範本資源
├── config.json                  # 腳本參數與座標記憶設定檔
├── friend_links.txt             # 好友清單
├── requirements.txt             # Python 相依套件清單
│
├── wolf_mine_speedup.py         # 【功能 1】敲狼與挖礦加速核心
├── boss_auto_clicker.py         # 【功能 2】BOSS 自動連點
├── upgrade_and_attack.py        # 【功能 3】升級與自動攻擊
│
├── start_wolf_mine.bat          # 雙擊啟動：敲狼與挖礦加速
├── start_boss_clicker.bat       # 雙擊啟動：BOSS 自動點擊
├── start_upgrade_attack.bat     # 雙擊啟動：升級與自動攻擊
│
├── .gitignore                   # Git 忽略清單
└── README.md                    # 專案說明文件
```

---

## 安裝與環境準備

### 1. 安裝 Python
建議使用 **Python 3.8 ~ 3.11** (64-bit)。

### 2. 安裝相依套件
在專案根目錄下開啟終端機執行：

```bash
pip install -r requirements.txt
```

---

## 快速啟動方式

在 Windows 環境下，直接雙擊對應的 `.bat` 批次檔即可啟動：

- **敲狼與挖礦加速**：雙擊 `start_wolf_mine.bat`
- **BOSS 自動點擊**：雙擊 `start_boss_clicker.bat`
- **防禦塔升級與攻擊**：雙擊 `start_upgrade_attack.bat`

或透過指令執行：

```bash
python wolf_mine_speedup.py
```

---

## 操作注意事項

1. **螢幕縮放與解析度**：
   - 建議解析度設為 **1920x1080 (1080P)**，Windows 系統縮放建議設為 **100%**。
2. **緊急停止快捷鍵**：
   - 程式執行期間可隨時按下鍵盤 **`F10`** 鍵立即中斷自動化動作。
3. **圖像辨識閾值**：
   - 預設比對閾值為 `0.9`，若遇辨識不良可於介面微調為 `0.8`。
