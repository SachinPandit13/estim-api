import base64
import io
import importlib
import logging
from typing import Any, Optional

logger = logging.getLogger("estim.yolo")

# Dynamic runtime loading of deep-learning libraries
_YOLO_AVAILABLE = False
YOLO: Optional[Any] = None
Image: Optional[Any] = None
np: Optional[Any] = None

try:
    _ultralytics = importlib.import_module("ultralytics")
    YOLO = getattr(_ultralytics, "YOLO", None)
    _pil_image = importlib.import_module("PIL.Image")
    Image = _pil_image
    np = importlib.import_module("numpy")
    if YOLO is not None and Image is not None and np is not None:
        _YOLO_AVAILABLE = True
except Exception as err:
    logger.info("YOLO deep learning libraries pending installation in environment (%s). Operating in standby mode.", err)


class YoloInferenceService:
    _instance: Optional["YoloInferenceService"] = None

    def __new__(cls) -> "YoloInferenceService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._model: Optional[Any] = None
        self._model_name = "yolov8n.pt"
        self._is_ready = False
        self._load_model()
        self._initialized = True

    def _load_model(self):
        if not _YOLO_AVAILABLE or YOLO is None:
            logger.info("YOLO inference service initialized in standby mode.")
            return

        try:
            logger.info("Loading YOLO deep learning tracking model: %s", self._model_name)
            self._model = YOLO(self._model_name)
            self._is_ready = True
            logger.info("YOLO tracking model loaded successfully.")
        except Exception as e:
            logger.error("Failed to load YOLO model %s: %s", self._model_name, e)
            self._is_ready = False

    @property
    def is_available(self) -> bool:
        return self._is_ready and self._model is not None

    def decode_image_base64(self, b64_str: str) -> Optional[Any]:
        """Decode base64 image string to PIL Image."""
        if not b64_str or Image is None:
            return None
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return img
        except Exception as e:
            logger.warning("Failed to decode base64 frame: %s", e)
            return None

    def infer_and_track(
        self,
        image_base64: str,
        camera_id: str = "default",
        conf_threshold: float = 0.35,
    ) -> list[dict[str, Any]]:
        """
        Run YOLOv8 object detection and ByteTrack multi-object tracking.
        Returns normalized bounding boxes [x1, y1, x2, y2] for detected persons
        along with PPE compliance (hardhat/helmet, safety vest) and fall posture.
        """
        img = self.decode_image_base64(image_base64)
        if img is None:
            return []

        if not self.is_available or np is None or self._model is None:
            return []

        try:
            w, h = img.size
            img_np = np.array(img)

            # Run YOLO tracking with ByteTrack (Class 0: person in COCO)
            results = self._model.track(
                source=img_np,
                persist=True,
                tracker="bytetrack.yaml",
                classes=[0],
                conf=conf_threshold,
                verbose=False,
            )

            candidates: list[dict[str, Any]] = []

            if not results or len(results) == 0:
                return []

            res = results[0]
            boxes = getattr(res, "boxes", None)

            if boxes is None or len(boxes) == 0:
                return []

            for i, box in enumerate(boxes):
                xyxy = box.xyxy[0].tolist()
                x1_px, y1_px, x2_px, y2_px = xyxy

                norm_x1 = max(0.01, min(0.98, x1_px / w))
                norm_y1 = max(0.01, min(0.98, y1_px / h))
                norm_x2 = max(0.02, min(0.99, x2_px / w))
                norm_y2 = max(0.02, min(0.99, y2_px / h))

                confidence = float(box.conf[0]) if box.conf is not None else 0.88
                track_id = int(box.id[0]) if box.id is not None else (i + 1)

                bw = norm_x2 - norm_x1
                bh = norm_y2 - norm_y1
                aspect_ratio = bw / (bh if bh > 0.01 else 0.01)

                # 1. Fall detection: prone horizontal orientation grounded at floor level
                is_fallen = aspect_ratio > 1.65 and norm_y2 > 0.80 and bh < 0.30

                # 2. Inspect PPE in localized regions from pixel array
                has_helmet, has_vest = self._inspect_ppe(
                    img_np,
                    int(max(0, x1_px)),
                    int(max(0, y1_px)),
                    int(min(w, x2_px)),
                    int(min(h, y2_px)),
                )

                candidates.append({
                    "bbox": [round(norm_x1, 4), round(norm_y1, 4), round(norm_x2, 4), round(norm_y2, 4)],
                    "confidence": round(confidence, 2),
                    "has_helmet": has_helmet,
                    "has_vest": has_vest,
                    "is_fallen": is_fallen,
                    "assigned_track_id": track_id,
                })

            return candidates

        except Exception as e:
            logger.error("YOLO tracking inference exception: %s", e)
            return []

    def _inspect_ppe(
        self,
        img_np: Any,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> tuple[bool, bool]:
        """Inspect localized crown (helmet) and torso (vest) ROIs for safety gear."""
        try:
            bw = x2 - x1
            bh = y2 - y1
            if bw < 8 or bh < 16:
                return (True, True)

            crown_y2 = y1 + int(bh * 0.28)
            crown = img_np[y1:crown_y2, x1:x2]

            torso_y1 = y1 + int(bh * 0.25)
            torso_y2 = y1 + int(bh * 0.75)
            torso = img_np[torso_y1:torso_y2, x1:x2]

            has_helmet = self._check_hardhat_colors(crown)
            has_vest = self._check_vest_colors(torso)
            return (has_helmet, has_vest)
        except Exception:
            return (True, True)

    def _check_hardhat_colors(self, roi: Any) -> bool:
        """Detect industrial safety hardhat colors (Yellow, Orange, White, Blue)."""
        if roi is None or getattr(roi, "size", 0) == 0 or np is None:
            return True

        r = roi[:, :, 0].astype(float)
        g = roi[:, :, 1].astype(float)
        b = roi[:, :, 2].astype(float)

        yellow = (r > 130) & (g > 130) & (b < 105) & ((r + g) / (2 * (b + 1)) > 1.35)
        orange = (r > 165) & (g >= 55) & (g <= 145) & (b < 75) & (r - g > 35)
        white = (r > 190) & (g > 190) & (b > 190) & (np.abs(r - g) < 20) & (np.abs(g - b) < 20)
        blue = (b > 135) & (b > r + 30) & (b > g + 18)

        helmet_pixels = np.sum(yellow | orange | white | blue)
        total_pixels = roi.shape[0] * roi.shape[1]
        return bool((helmet_pixels / max(1, total_pixels)) >= 0.12)

    def _check_vest_colors(self, roi: Any) -> bool:
        """Detect industrial safety vest colors (Fluorescent Neon Yellow/Green, Hi-Vis Orange, Reflective)."""
        if roi is None or getattr(roi, "size", 0) == 0 or np is None:
            return True

        r = roi[:, :, 0].astype(float)
        g = roi[:, :, 1].astype(float)
        b = roi[:, :, 2].astype(float)

        hi_vis_yellow = (r > 120) & (g > 140) & (g > b + 30) & (b < 130)
        hi_vis_orange = (r > 165) & (g >= 55) & (g <= 140) & (b < 75) & (r - g > 38)
        reflective = (r > 210) & (g > 210) & (b > 210) & (np.abs(r - g) < 15) & (np.abs(g - b) < 15)

        vest_pixels = np.sum(hi_vis_yellow | hi_vis_orange | reflective)
        total_pixels = roi.shape[0] * roi.shape[1]
        return bool((vest_pixels / max(1, total_pixels)) >= 0.10)


# Global singleton instance
yolo_service = YoloInferenceService()
