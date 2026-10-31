"""PPE detection slot + strict color-heuristic bridge (low false positives)."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from app.db.config import settings
from app.v1.ai.device import resolve_device
from app.v1.ai.models.registry import model_registry

logger = logging.getLogger("estim.ai.ppe")

Status = str  # compliant | violation | unknown

# Compliant needs strong fluorescent / saturated industrial colors.
# Missing those on a clearly visible ROI → VIOLATION (not OK).
_HELMET_COMPLIANT_RATIO = 0.22
_VEST_COMPLIANT_RATIO = 0.18
_MIN_ROI_PIXELS = 80


def inspect_ppe_for_person(
    img_rgb: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    ppe_detections: Optional[list[dict[str, Any]]] = None,
) -> tuple[Status, Status, float, float]:
    """Return (helmet_status, vest_status, helmet_conf, vest_conf)."""
    if ppe_detections:
        return _associate_ppe_boxes(x1, y1, x2, y2, img_rgb.shape[1], img_rgb.shape[0], ppe_detections)
    return _color_heuristic(img_rgb, x1, y1, x2, y2)


def run_ppe_model(img_rgb: np.ndarray) -> list[dict[str, Any]]:
    """Full-frame PPE YOLO when enabled; else empty (caller uses heuristic)."""
    model = model_registry.ensure_ppe()
    if model is None:
        return []
    h, w = img_rgb.shape[:2]
    try:
        results = model.predict(
            source=img_rgb,
            conf=settings.DETECTION_CONFIDENCE_THRESHOLD,
            device=resolve_device(),
            verbose=False,
        )
    except Exception as exc:
        logger.error("PPE predict failed: %s", exc)
        return []
    if not results:
        return []
    names = dict(getattr(model, "names", {}) or {})
    out: list[dict[str, Any]] = []
    boxes = getattr(results[0], "boxes", None)
    if boxes is None:
        return out
    for box in boxes:
        cls_id = int(box.cls[0]) if box.cls is not None else -1
        label = str(names.get(cls_id, cls_id)).lower()
        xyxy = box.xyxy[0].tolist()
        out.append({
            "label": label,
            "confidence": float(box.conf[0]) if box.conf is not None else 0.0,
            "bbox_px": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
            "bbox": [xyxy[0] / w, xyxy[1] / h, xyxy[2] / w, xyxy[3] / h],
        })
    return out


def _associate_ppe_boxes(
    x1: int, y1: int, x2: int, y2: int, w: int, h: int, dets: list[dict[str, Any]]
) -> tuple[Status, Status, float, float]:
    from app.v1.ai.association import head_roi, torso_roi, iou

    head = head_roi(x1, y1, x2, y2)
    torso = torso_roi(x1, y1, x2, y2)
    helmet_status: Status = "unknown"
    vest_status: Status = "unknown"
    helmet_conf = 0.0
    vest_conf = 0.0

    for d in dets:
        bx = d["bbox_px"]
        label = d["label"]
        conf = float(d["confidence"])
        if any(k in label for k in ("helmet", "hardhat")) and "no" not in label and "head" not in label:
            if iou(head, bx) > 0.08:
                if conf >= settings.DETECTION_CONFIDENCE_THRESHOLD and conf > helmet_conf:
                    helmet_status = "compliant"
                    helmet_conf = conf
        elif any(k in label for k in ("no-helmet", "no_helmet", "without helmet")) or label == "head":
            if iou(head, bx) > 0.08:
                if conf >= settings.DETECTION_CONFIDENCE_THRESHOLD and conf > helmet_conf:
                    helmet_status = "violation"
                    helmet_conf = conf
        elif any(k in label for k in ("vest", "safety vest", "hi-vis")) and "no" not in label:
            if iou(torso, bx) > 0.08:
                if conf >= settings.DETECTION_CONFIDENCE_THRESHOLD and conf > vest_conf:
                    vest_status = "compliant"
                    vest_conf = conf
        elif any(k in label for k in ("no-vest", "no_vest", "without vest")):
            if iou(torso, bx) > 0.08:
                if conf >= settings.DETECTION_CONFIDENCE_THRESHOLD and conf > vest_conf:
                    vest_status = "violation"
                    vest_conf = conf

    # No positive PPE match with visible person box → violation (not compliant)
    if helmet_status == "unknown":
        helmet_status = "violation"
        helmet_conf = max(helmet_conf, 0.55)
    if vest_status == "unknown":
        vest_status = "violation"
        vest_conf = max(vest_conf, 0.55)
    return helmet_status, vest_status, helmet_conf, vest_conf


def _color_heuristic(
    img_rgb: np.ndarray, x1: int, y1: int, x2: int, y2: int
) -> tuple[Status, Status, float, float]:
    """
    Bridge heuristic biased toward low false COMPLIANT.
    Bare head / normal clothing → VIOLATION when ROI is large enough.
    """
    bw, bh = x2 - x1, y2 - y1
    if bw < 24 or bh < 40:
        return "unknown", "unknown", 0.0, 0.0

    # Crown: top ~22% of person box (avoid face/skin dominating)
    crown_y2 = y1 + max(8, int(bh * 0.22))
    crown = img_rgb[y1:crown_y2, x1:x2]

    # Torso: mid band; skip face-heavy upper portion on close-ups
    torso_y1 = y1 + int(bh * 0.35)
    torso_y2 = y1 + int(bh * 0.85)
    if torso_y2 <= torso_y1 + 4:
        torso_y1 = y1 + int(bh * 0.30)
        torso_y2 = y2
    torso = img_rgb[torso_y1:torso_y2, x1:x2]

    helmet_ratio = _hardhat_ratio(crown)
    vest_ratio = _vest_ratio(torso)

    if helmet_ratio >= _HELMET_COMPLIANT_RATIO:
        helmet_status: Status = "compliant"
        helmet_conf = min(0.9, 0.5 + helmet_ratio)
    elif crown.size >= _MIN_ROI_PIXELS:
        helmet_status = "violation"
        helmet_conf = 0.7
    else:
        helmet_status = "unknown"
        helmet_conf = 0.2

    if vest_ratio >= _VEST_COMPLIANT_RATIO:
        vest_status: Status = "compliant"
        vest_conf = min(0.9, 0.5 + vest_ratio)
    elif torso.size >= _MIN_ROI_PIXELS:
        vest_status = "violation"
        vest_conf = 0.7
    else:
        vest_status = "unknown"
        vest_conf = 0.2

    return helmet_status, vest_status, round(helmet_conf, 2), round(vest_conf, 2)


def _rgb_to_hsv_arrays(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized RGB(0-255) → H(0-179), S(0-255), V(0-255) like OpenCV."""
    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0
    cmax = np.maximum(np.maximum(rf, gf), bf)
    cmin = np.minimum(np.minimum(rf, gf), bf)
    delta = cmax - cmin

    h = np.zeros_like(cmax)
    mask = delta > 1e-6
    rmax = mask & (cmax == rf)
    gmax = mask & (cmax == gf)
    bmax = mask & (cmax == bf)
    h[rmax] = ((gf[rmax] - bf[rmax]) / delta[rmax]) % 6
    h[gmax] = (bf[gmax] - rf[gmax]) / delta[gmax] + 2
    h[bmax] = (rf[bmax] - gf[bmax]) / delta[bmax] + 4
    h = (h * 30.0)  # 0-179
    s = np.zeros_like(cmax)
    np.divide(delta, cmax, out=s, where=cmax > 1e-6)
    s = s * 255.0
    v = cmax * 255.0
    return h, s, v


def _is_skin(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Exclude skin from helmet crown counts (not saturated hardhat yellow/orange)."""
    rf, gf, bf = r.astype(float), g.astype(float), b.astype(float)
    # Skin is moderately saturated; neon hardhats have very high chroma
    chroma = np.maximum(rf, np.maximum(gf, bf)) - np.minimum(rf, np.minimum(gf, bf))
    return (
        (rf > 60)
        & (gf > 30)
        & (bf > 15)
        & (rf > gf)
        & (rf > bf)
        & ((rf - gf) > 10)
        & ((rf - gf) < 70)
        & (chroma < 110)  # neon hardhats exceed this
        & (bf > rf * 0.35)  # hardhat yellow/orange usually has lower B relative to R
    )


def _hardhat_ratio(roi: np.ndarray) -> float:
    """Saturated industrial hardhat colors only — no plain white (walls/ceilings FP)."""
    if roi is None or getattr(roi, "size", 0) == 0:
        return 0.0
    r = roi[:, :, 0].astype(float)
    g = roi[:, :, 1].astype(float)
    b = roi[:, :, 2].astype(float)
    h, s, v = _rgb_to_hsv_arrays(r, g, b)
    skin = _is_skin(r, g, b)

    # Neon / safety yellow-lime hardhat
    yellow = ((h >= 20) & (h <= 45) & (s >= 90) & (v >= 120)) & ~skin
    # Safety orange hardhat
    orange = ((h <= 18) | (h >= 170)) & (s >= 100) & (v >= 110) & (r > g + 25) & ~skin
    # Industrial blue hardhat (saturated, not navy clothing glimpses in crown)
    blue = (h >= 90) & (h <= 130) & (s >= 80) & (v >= 80) & (b > r + 25) & (b > g + 15) & ~skin

    hit = np.sum(yellow | orange | blue)
    return float(hit / max(1, roi.shape[0] * roi.shape[1]))


def _vest_ratio(roi: np.ndarray) -> float:
    """Fluorescent hi-vis vest only — brown/tan shirts must not match."""
    if roi is None or getattr(roi, "size", 0) == 0:
        return 0.0
    r = roi[:, :, 0].astype(float)
    g = roi[:, :, 1].astype(float)
    b = roi[:, :, 2].astype(float)
    h, s, v = _rgb_to_hsv_arrays(r, g, b)

    # Fluorescent yellow-green (neon): green channel strong, very saturated
    hi_vis_yellow = (
        (h >= 28) & (h <= 75) & (s >= 130) & (v >= 130) & (g >= 150) & (g >= r) & (g > b + 35)
    )
    # Fluorescent safety orange: bright + very saturated (muted brown shirts fail)
    # Typical brown ~ S 140 V 140; true hi-vis orange is hotter (R high, G low-mid, B low)
    hi_vis_orange = (
        ((h <= 12) | (h >= 172))
        & (s >= 170)
        & (v >= 160)
        & (r >= 190)
        & (g <= 120)
        & (b <= 80)
        & (r > g + 60)
    )

    hit = np.sum(hi_vis_yellow | hi_vis_orange)
    return float(hit / max(1, roi.shape[0] * roi.shape[1]))
