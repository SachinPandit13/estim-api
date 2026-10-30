"""Geometric association helpers for person <-> PPE boxes."""

from __future__ import annotations


def iou(a: list[int] | list[float], b: list[int] | list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def head_roi(x1: int, y1: int, x2: int, y2: int) -> list[int]:
    bh = y2 - y1
    return [x1, y1, x2, y1 + int(bh * 0.30)]


def torso_roi(x1: int, y1: int, x2: int, y2: int) -> list[int]:
    bh = y2 - y1
    return [x1, y1 + int(bh * 0.25), x2, y1 + int(bh * 0.75)]
