# gesture-mouse-control

用筆電前置鏡頭辨識手勢，控制 Windows 滑鼠（移動、點擊、拖曳、右鍵、捲動）。

流程：OpenCV 讀鏡頭 → MediaPipe 取 21 個手部關鍵點 → 規則式判斷手勢 → 平滑處理 → pynput 送出滑鼠指令。

## 手勢

| 手勢 | 動作 |
| --- | --- |
| 只伸出食指 | 移動游標（相對移動，像觸控板） |
| 食指 + 拇指捏合 | 左鍵點擊；捏住不放移動 = 拖曳 |
| 中指 + 拇指捏合 | 右鍵點擊 |
| 食指 + 中指伸出，上下移動 | 捲動 |
| 握拳約 0.8 秒 | 暫停 / 恢復控制（暫停時只認握拳） |
| 張開手掌、或手離開畫面 | 游標停住（像把滑鼠拿起來，可以趁這時把手移回中間） |

所有對應都可以在 `config.yaml` 修改。

## 在 Windows 安裝

需要：Windows 10/11、可用的鏡頭、Python 3.10 ~ 3.12（建議 3.12，MediaPipe 對最新版 Python 的支援有時會晚一點）。

```powershell
# 1. 下載程式
git clone https://github.com/BRIANLIN0205/gesture-mouse-control.git
cd gesture-mouse-control

# 2. 建立虛擬環境
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
#   如果 PowerShell 不允許執行腳本，先執行：
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. 安裝套件
pip install -r requirements.txt
```

## 執行

```powershell
python -m gesture_mouse
```

- 會跳出鏡頭預覽視窗，顯示手部骨架、目前手勢和 FPS。
- 游標預設是相對移動：手移動多少，游標就跟著移動多少，移得快會走得更遠（加速度）。手移到鏡頭邊緣時，張開手掌把手移回中間，再伸食指繼續。
- 想改回「手的位置直接對應螢幕位置」：`config.yaml` 設 `cursor.mode: absolute`，預覽視窗中的藍框就是有效範圍。
- 在預覽視窗按 `q` 或 `Esc` 結束。
- 不要預覽視窗：`python -m gesture_mouse --no-preview`（用 Ctrl+C 結束）。
- 指定其他設定檔：`python -m gesture_mouse --config my.yaml`。

第一次執行時，如果安裝的 MediaPipe 是新版（沒有舊的 `solutions` API），程式會自動下載手部模型（約 8 MB）到 `models/`。

## 調整手感（config.yaml）

| 想要 | 改這個 |
| --- | --- |
| 游標太抖 | 調小 `cursor.smoothing_min_cutoff`（例如 0.5） |
| 游標跟不上、有延遲 | 調大 `cursor.smoothing_beta`（例如 0.05） |
| 游標整體太慢 / 太快 | 調整 `cursor.relative_gain` |
| 快速移動時游標飛太遠 | 調小 `cursor.relative_accel` 或 `cursor.relative_max_gain` |
| 手靜止時游標還在飄 | 調大 `cursor.relative_deadzone` |
| （絕對模式）手要移很大才能碰到螢幕邊 | 調大 `cursor.frame_margin`（例如 0.2） |
| 捏合太容易誤觸 | 調小 `detection.pinch_enter` |
| 捏合很難觸發 | 調大 `detection.pinch_enter`（`pinch_exit` 要一起調大） |
| 捲動太快 / 太慢 | 調整 `control.scroll_sensitivity` |
| 捲動方向相反 | `control.scroll_invert: true` |
| 游標跟著指尖而不是食指根部 | `cursor.pointer_landmark: 8` |

## 常見問題

- **打不開鏡頭**：確認沒有其他程式（Teams、Zoom、相機 App）在用鏡頭；外接鏡頭可以試 `camera.index: 1`。
- **游標位置跟手對不上**：程式已處理 Windows 顯示縮放，但若有多螢幕，目前只對應主螢幕。
- **在某些視窗點不到**：以系統管理員身分執行的程式，一般權限的 Python 無法控制它，請用同樣權限執行本程式。

## 開發與測試

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

手勢判斷、指令狀態機、平滑和設定檔都有單元測試，用假的手部關鍵點資料，不需要鏡頭。

## 專案結構

```
gesture_mouse/
  app.py         主迴圈：鏡頭、預覽視窗
  detector.py    MediaPipe 手部偵測（新舊 API 都支援）
  hand.py        關鍵點編號與幾何計算
  gestures.py    規則式手勢判斷
  controller.py  手勢 → 滑鼠指令（防抖、拖曳、捲動、暫停）
  smoothing.py   One Euro Filter 游標平滑
  mouse.py       pynput 送出滑鼠指令、Windows DPI 處理
  config.py      讀取 config.yaml
config.yaml      手勢對應與參數
tests/           單元測試
```
