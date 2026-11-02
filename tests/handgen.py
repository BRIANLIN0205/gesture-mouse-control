"""產生假的手部關鍵點，用來測試手勢判斷（不需要鏡頭）。

手腕在下方、手指朝上。座標為正規化座標。
"""

FINGER_X = {"index": 0.44, "middle": 0.50, "ring": 0.56, "pinky": 0.62}
FINGER_BASE = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}

WRIST = (0.50, 0.80)
MCP_Y = 0.60


def make_hand(index=True, middle=False, ring=False, pinky=False, thumb_tip=None, offset=(0.0, 0.0), scale=1.0):
    """回傳 21 個 (x, y, z)。True = 伸直，False = 彎曲。

    thumb_tip：指定拇指指尖位置（用來做捏合），預設在手掌外側。
    offset / scale：整隻手平移與縮放（模擬手的位置與遠近）。
    """
    pts = [None] * 21
    pts[0] = WRIST
    # 拇指預設往左外側張開
    pts[1] = (0.44, 0.75)
    pts[2] = (0.39, 0.70)
    pts[3] = (0.35, 0.66)
    pts[4] = (0.32, 0.62)

    states = {"index": index, "middle": middle, "ring": ring, "pinky": pinky}
    for name, base in FINGER_BASE.items():
        x = FINGER_X[name]
        pts[base] = (x, MCP_Y)
        if states[name]:
            pts[base + 1] = (x, 0.50)
            pts[base + 2] = (x, 0.45)
            pts[base + 3] = (x, 0.40)
        else:
            # 彎曲：指尖折回靠近掌心
            pts[base + 1] = (x, 0.55)
            pts[base + 2] = (x, 0.60)
            pts[base + 3] = (x, 0.64)

    if thumb_tip is not None:
        pts[4] = thumb_tip

    ox, oy = offset
    cx, cy = WRIST
    return [((p[0] - cx) * scale + cx + ox, (p[1] - cy) * scale + cy + oy, 0.0) for p in pts]


def tip(hand, i):
    return hand[i][0], hand[i][1]
