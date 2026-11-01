"""游標平滑：One Euro Filter。

手慢慢移動時強力平滑（消除抖動），快速移動時降低平滑（減少延遲）。
參考：Casiez et al., "1€ Filter", CHI 2012.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple


class _LowPass:
    def __init__(self) -> None:
        self.value: Optional[float] = None

    def apply(self, x: float, alpha: float) -> float:
        self.value = x if self.value is None else alpha * x + (1 - alpha) * self.value
        return self.value


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    """單一數值的 One Euro Filter。

    min_cutoff：越小越平滑（但越黏）。
    beta：越大，快速移動時延遲越小。
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.01, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._x = _LowPass()
        self._dx = _LowPass()
        self._last_t: Optional[float] = None
        self._last_raw: Optional[float] = None

    def __call__(self, x: float, t: float) -> float:
        if self._last_t is None or self._last_raw is None:
            self._last_t, self._last_raw = t, x
            self._dx.apply(0.0, 1.0)
            return self._x.apply(x, 1.0)

        dt = t - self._last_t
        if dt <= 0:
            dt = 1e-3
        dx = (x - self._last_raw) / dt
        edx = self._dx.apply(dx, _alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        self._last_t, self._last_raw = t, x
        return self._x.apply(x, _alpha(cutoff, dt))


class PointFilter:
    """2D 點的平滑（x、y 各一個 One Euro Filter）。"""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.01) -> None:
        self.fx = OneEuroFilter(min_cutoff, beta)
        self.fy = OneEuroFilter(min_cutoff, beta)

    def reset(self) -> None:
        self.fx.reset()
        self.fy.reset()

    def __call__(self, x: float, y: float, t: float) -> Tuple[float, float]:
        return self.fx(x, t), self.fy(y, t)
