# gesture-mouse-control

用筆電前置鏡頭辨識手勢，控制 Windows 滑鼠（移動、點擊、拖曳、右鍵、捲動）。

流程：OpenCV 讀鏡頭 → MediaPipe 取 21 個手部關鍵點 → 規則式判斷手勢 → 平滑處理 → pynput 送出滑鼠指令。

## 手勢

| 手勢 | 動作 |
| --- | --- |
| 張開手掌 | 移動游標（相對移動，像觸控板） |
| 食指 + 拇指輕捏一下（其他手指張開或彎曲都可以） | 左鍵點擊（放開時觸發） |
| 食指 + 拇指捏住並移動 | 拖曳 |
| 食指 + 拇指捏住不動約 0.6 秒 | 右鍵點擊 |
| 中指 + 拇指捏住，往上 / 往下移 | 捲動，像搖桿：離捏住的起點越遠捲越快，移回起點就停（捏住時游標不動） |
| 中指 + 拇指捏住，往上 / 往下一點就放開（0.4 秒內） | 方向鍵上 / 下 |
| 中指 + 拇指捏住，往左 / 往右移再放開 | 上一頁 / 下一頁（Alt + ← / →），放開時才執行 |
| 食指 + 中指 + 無名指伸出，往上甩 | 顯示所有視窗（Win + Tab） |
| 三指往下甩 | 顯示桌面（Win + D） |
| 三指往左 / 往右甩 | 切換視窗（Alt + Tab） |
| 短握拳 | 抬起：游標停住，可以把手移回中間 |
| 握拳約 1.5 秒 | 暫停 / 恢復控制（暫停時只認握拳），會播提示音 |
| 手離開畫面 | 游標停住 |

### 雙手動作

| 手勢 | 動作 |
| --- | --- |
| 兩手都用食指 + 拇指捏住，拉開 / 靠近 | 放大 / 縮小（Ctrl + 滾輪，瀏覽器、圖片、PDF、地圖都能用） |
| 左手中指 + 拇指捏住，往上 / 往下移 | 音量變大 / 變小，像搖桿：離捏住的起點越遠調越快 |

縮放時兩手盡量同時捏；縮放中右手的捏合不會被當成點擊或拖曳，右手放開後才恢復。

**兩隻手同時入鏡**：游標、點擊只聽主控手（預設右手），另一隻手只用在上面的雙手動作，其他手勢都不影響。預覽視窗會在手腕旁標 `R` / `L`，主控手是綠色、另一隻是灰色。只有另一隻手在畫面上時，游標停住（但仍可調音量）。

捏合瞬間游標會鎖住約 0.15 秒，避免捏合時手抖把點擊點歪。所有對應都可以在 `config.yaml` 修改。

### 回饋

- **游標旁的小圓圈**：不開預覽視窗也知道系統怎麼解讀你的手。綠 = 移動、橘 = 捏合判斷中、紅橘 = 拖曳、藍 = 捲動、紫 = 視窗手勢（三指）、青 = 雙手縮放、粉紅 = 調音量、白 = 抬起（握拳）、紅 = 暫停、灰 = 看不到手、**黃色閃爍 = 手快離開鏡頭畫面**（預覽視窗也會出現黃框）。
- **聲音**：點擊有輕微「喀」聲（右鍵和甩動觸發的快捷鍵音較低，調音量不出聲），暫停 / 恢復有高低兩聲提示音。

### 第一次使用：手勢教學

第一次執行會先進入教學，畫面右邊依序列出每個手勢，做對就打勾；練習時不會真的操作滑鼠。按 `s` 可跳過。之後想再練習：`python -m gesture_mouse --tutorial`。

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
- 游標預設是相對移動：手移動多少，游標就跟著移動多少，移得快會走得更遠（加速度）。手移到鏡頭邊緣時，握拳把手移回中間（1.5 秒內），再張開手掌繼續。
- 手不用舉高：在鏡頭畫面下半部（靠近鍵盤）小幅移動就能走遍螢幕，比較不累。只要手還在鏡頭拍得到的範圍內就好。
- 想改回「手的位置直接對應螢幕位置」：`config.yaml` 設 `cursor.mode: absolute`，預覽視窗中的藍框就是有效範圍。
- 在預覽視窗按 `q` 或 `Esc` 結束。
- 不要預覽視窗：`python -m gesture_mouse --no-preview`（用 Ctrl+C 結束）。
- 指定其他設定檔：`python -m gesture_mouse --config my.yaml`。
- 第一次也不要教學：`python -m gesture_mouse --skip-tutorial`。

第一次執行時，如果安裝的 MediaPipe 是新版（沒有舊的 `solutions` API），程式會自動下載手部模型（約 8 MB）到 `models/`。

## 設定介面

程式執行時，Windows 右下角系統匣（工作列時鐘旁的 `^` 箭頭裡）會有綠色手掌圖示，暫停時變紅色。點一下圖示會出現選單：

- **開啟設定**：用滑桿和勾選框調整數值（游標、點擊與捏合、捲動與搖桿、雙手、聲音與顯示、鏡頭、進階）。改了會自動存進 `config.yaml`（原本的註解會保留），半秒內就套用，不用重開。標「需重開」的項目（鏡頭、辨識信心門檻、左右手對調）要重開程式才會生效。也可以雙擊圖示直接開設定。
- **暫停 / 恢復**：和長握拳一樣。
- **結束手勢滑鼠**。

設定視窗也可以單獨開：`python -m gesture_mouse.settings_gui`。手勢對應哪個動作目前還是要直接改 `config.yaml` 的 `gestures` 區塊。

## 調整手感（config.yaml）

用文字編輯器改 `config.yaml` 也可以，程式執行中存檔一樣會自動套用。

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
| 搖桿捲動太快 / 太慢 | 調整 `control.joystick_max_speed`；要偏更遠才到最快就調大 `control.joystick_full` |
| 手稍微動就開始捲 | 調大 `control.joystick_deadzone` |
| 方向鍵太難 / 太容易觸發 | 調大 / 調小 `control.joystick_tap_seconds` |
| 翻頁太容易 / 太難觸發 | 調大 / 調小 `control.joystick_nav_distance` |
| 想要手掌快速甩動捲動 / 翻頁 | `gestures.palm: move_flick_scroll`，門檻用 `control.palm_swipe_min_speed` 調 |
| 想要中指捏合變回右鍵 | `gestures.pinch_middle: click_right` |
| 三指甩動常誤觸 / 甩了沒反應 | 調大 / 調小 `control.swipe_min_speed`、`control.swipe_min_distance` |
| 想改回雙指慢慢移動就捲動（舊做法） | `gestures.two_finger: scroll`，速度用 `control.scroll_sensitivity` 調 |
| 捲動方向相反 | `control.scroll_invert: true` |
| 點擊時游標還是會偏 / 拖曳開始太慢 | 調大 / 調小 `control.click_lock_seconds` |
| 甩動後滑太久 / 太短 | 調大 / 調小 `control.scroll_inertia_friction`；不要慣性設 `control.scroll_inertia: false` |
| 游標跟著指尖而不是食指根部 | `cursor.pointer_landmark: 8` |
| 輕捏常被當成拖曳 / 拖曳很難開始 | 調大 / 調小 `control.drag_threshold_px` |
| 右鍵太容易 / 太難觸發 | 調大 / 調小 `control.right_hold_seconds` |
| 想要捏到就按下（舊行為） | `gestures.pinch_index: hold_left` |
| 雙手縮放太敏感 / 太遲鈍 | 調大 / 調小 `two_hands.zoom_step` |
| 音量調太快 / 太慢 | 調整 `two_hands.volume_max_speed` |
| 不要雙手縮放 / 左手調音量 | `two_hands.zoom: false` / `two_hands.volume: false` |
| 關掉點擊音 | `sound.click_enabled: false` |
| 關掉游標旁小圓圈 | `overlay.enabled: false` |
| 出畫面提示太敏感 | 調小 `detection.edge_margin` |
| 用左手操作 | `detection.control_hand: left`；不分左右設 `any` |
| 預覽視窗標的 L / R 和實際相反 | `detection.swap_hands: true` |
| 關掉暫停 / 恢復提示音 | `sound.enabled: false` |
| 換成自己的音效 | `sound.pause_file`、`sound.resume_file` 填 wav 檔路徑 |

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
  two_hands.py   雙手動作：縮放、另一隻手調音量
  smoothing.py   One Euro Filter 游標平滑
  sounds.py      點擊、暫停 / 恢復音效
  overlay.py     游標旁的狀態小圓圈
  tutorial.py    第一次使用的手勢教學
  live_config.py 執行中自動重新讀取設定檔
  yaml_update.py 改數值時保留 config.yaml 的註解
  settings_gui.py 設定視窗（PySide6）
  tray.py        系統匣圖示與選單
  mouse.py       pynput 送出滑鼠指令、Windows DPI 處理
  config.py      讀取 config.yaml
config.yaml      手勢對應與參數
tests/           單元測試
```
