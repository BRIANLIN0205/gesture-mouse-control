"""暫停 / 恢復時播放提示音。

內建提示音是程式產生的短音：暫停 = 由高到低，恢復 = 由低到高。
也可以在 config.yaml 指定自己的 wav 檔。播放在背景執行，不會卡住鏡頭畫面。
"""

from __future__ import annotations

import io
import math
import struct
import sys
import threading
import wave
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .config import SoundConfig
from .controller import PauseChanged

SAMPLE_RATE = 22050


def make_tone_wav(freqs: Sequence[float], note_ms: int = 90, volume: float = 0.5) -> bytes:
    """依序播放幾個音高的短音，回傳 wav 檔內容。每個音頭尾淡入淡出，避免爆音。"""
    volume = min(max(volume, 0.0), 1.0)
    n = int(SAMPLE_RATE * note_ms / 1000)
    fade = max(1, int(n * 0.15))
    frames = bytearray()
    for f in freqs:
        for i in range(n):
            env = min(1.0, i / fade, (n - 1 - i) / fade)
            sample = volume * env * math.sin(2 * math.pi * f * i / SAMPLE_RATE)
            frames += struct.pack("<h", int(sample * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def _load(path: str, fallback: bytes) -> bytes:
    if not path:
        return fallback
    p = Path(path)
    if not p.exists():
        print(f"找不到音效檔 {p}，改用內建提示音")
        return fallback
    return p.read_bytes()


class SoundPlayer:
    def __init__(self, cfg: SoundConfig) -> None:
        self.enabled = cfg.enabled and sys.platform == "win32"
        if cfg.enabled and not self.enabled:
            print("音效目前只支援 Windows，已略過")
        self.pause_wav = _load(cfg.pause_file, make_tone_wav([880, 587], volume=cfg.volume))
        self.resume_wav = _load(cfg.resume_file, make_tone_wav([587, 880], volume=cfg.volume))

    def sound_for(self, commands: Iterable[object]) -> Optional[bytes]:
        """從這一幀的指令找出要播的音效（沒有就回傳 None）。"""
        wav = None
        for cmd in commands:
            if isinstance(cmd, PauseChanged):
                wav = self.pause_wav if cmd.paused else self.resume_wav
        return wav

    def execute(self, commands: Iterable[object]) -> None:
        wav = self.sound_for(commands)
        if wav is None or not self.enabled:
            return
        threading.Thread(target=_play, args=(wav,), daemon=True).start()


def _play(wav: bytes) -> None:
    try:
        import winsound

        winsound.PlaySound(wav, winsound.SND_MEMORY)
    except Exception as e:  # 音效失敗不影響控制
        print(f"播放音效失敗：{e}")
