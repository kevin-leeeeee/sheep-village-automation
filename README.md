# 保衛羊村 - 自動化輔助工具 (Sheep Village Automation)

本專案提供網頁遊戲《保衛羊村》的 Python 自動化輔助工具，整合 OpenCV 圖像辨識與 PyAutoGUI 模擬操作。

> 📖 **完整圖文取點與操作教學**：請參閱 [詳細操作與使用手冊 (USAGE.md)](./USAGE.md)。

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

### 4. 競技場挑戰 (`arena_challenge.py`)
- **雙模式自由切換**：
  - **🛡️ 防守模式**：切磋 ➔ 開始戰鬥 ➔ 動態偵測 ➔ 洗牌翻牌抽獎 ➔ 確定。
  - **⚔️ 進攻模式**：切磋 ➔ 挑戰 ➔ 出戰隊列派狼（全部自動派出 / 指定第 N 隻狼）➔ 開始戰鬥 ➔ 動態偵測 ➔ 洗牌翻牌抽獎 ➔ 確定。
- **狼槽兩點極速生成**：滑鼠移至第 1 隻與第 8 隻狼頭像按 `K` 鍵，自動等分算出 8 格精準座標。
- **雙螢幕 / 多螢幕原生支援**：智慧分析點擊座標，自動鎖定副螢幕設備進行 Windows GDI 硬體截圖辨識。
- **動態戰鬥與二段式洗牌抽獎**：支援勝利（WIN）與惜敗（LOST）自動辨識，並依序執行「點擊卡片觸發洗牌 ➔ 等待洗牌動畫 ➔ 再次點擊翻牌抽獎 ➔ 確定」全自動結算。

---

## 目錄結構

```text
sheep-village-automation/
│
├── images/                      # 圖像辨識比對範本資源 (含勝利、失敗、抽獎等)
├── config.json                  # 敲狼與巡邏腳本參數與座標設定檔
├── friend_links.txt             # 好友清單
├── requirements.txt             # Python 相依套件清單
│
├── wolf_mine_speedup.py         # 【功能 1】敲狼與挖礦加速核心
├── boss_auto_clicker.py         # 【功能 2】BOSS 自動連點
├── upgrade_and_attack.py        # 【功能 3】升級與自動攻擊
├── arena_challenge.py           # 【功能 4】競技場防守與進攻挑戰
│
├── start_wolf_mine.bat          # 雙擊啟動：敲狼與挖礦加速
├── start_boss_clicker.bat       # 雙擊啟動：BOSS 自動點擊
├── start_upgrade_attack.bat     # 雙擊啟動：升級與自動攻擊
├── start_arena_challenge.bat    # 雙擊啟動：競技場防守與進攻挑戰
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
- **競技場防守與進攻**：雙擊 `start_arena_challenge.bat`

或透過指令執行：

```bash
python arena_challenge.py
```

---

## 操作注意事項

1. **螢幕縮放與解析度**：
   - 建議解析度設為 **1920x1080 (1080P)**，Windows 系統縮放建議設為 **100%**。
2. **緊急停止快捷鍵**：
   - 程式執行期間可隨時按下鍵盤 **`F10`** 鍵立即中斷自動化動作。
3. **圖像辨識閾值**：
   - 預設比對閾值為 `0.9`，若遇辨識不良可於介面微調為 `0.8`。
