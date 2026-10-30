"""Per-camera RTSP capture workers with reconnect/backoff and health updates."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.db.config import settings
from app.v1.ai.health import clear_camera_health, update_camera_health
from app.v1.ai.models.person import reset_person_tracker
from app.v1.ai.scheduler import frame_cadence
from app.v1.ai.tracking import drop_camera_tracker, reset_camera_tracker

logger = logging.getLogger("estim.ai.worker")


class CameraWorker:
    def __init__(self, camera_id: str, stream_url: str):
        self.camera_id = camera_id
        self.stream_url = stream_url
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.reconnect_count = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"rtsp-{self.camera_id[:8]}",
            daemon=True,
        )
        self._thread.start()
        update_camera_health(
            self.camera_id,
            worker_alive=True,
            processing=True,
            reconnect_count=self.reconnect_count,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        clear_camera_health(self.camera_id)
        drop_camera_tracker(self.camera_id)
        frame_cadence.reset(self.camera_id)

    def restart(self, stream_url: Optional[str] = None) -> None:
        self.stop()
        if stream_url:
            self.stream_url = stream_url
        reset_camera_tracker(self.camera_id)
        reset_person_tracker(self.camera_id)
        self.start()

    def _run(self) -> None:
        try:
            import cv2
        except Exception as exc:
            logger.error("OpenCV unavailable for RTSP worker: %s", exc)
            update_camera_health(self.camera_id, worker_alive=False, last_error=str(exc))
            return

        backoff = 2.0
        sample_interval = 1.0 / max(0.2, settings.FRAME_SAMPLE_RATE)

        while not self._stop.is_set():
            cap = None
            try:
                cap = cv2.VideoCapture(self.stream_url)
                if not cap.isOpened():
                    raise RuntimeError(f"Unable to open RTSP: {self.stream_url[:48]}...")

                update_camera_health(
                    self.camera_id,
                    worker_alive=True,
                    processing=True,
                    last_error=None,
                    reconnect_count=self.reconnect_count,
                )
                backoff = 2.0
                last_sample = 0.0
                last_health_broadcast = 0.0

                while not self._stop.is_set():
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        raise RuntimeError("RTSP frame read failed")

                    now = time.monotonic()
                    if now - last_sample < sample_interval:
                        continue
                    last_sample = now

                    update_camera_health(
                        self.camera_id,
                        worker_alive=True,
                        processing=True,
                        last_frame_at=datetime.now(timezone.utc).isoformat(),
                        fps_actual=settings.FRAME_SAMPLE_RATE,
                    )

                    try:
                        from app.v1.ai.pipeline import process_bgr_frame

                        process_bgr_frame(self.camera_id, frame)
                        if now - last_health_broadcast >= 5.0:
                            last_health_broadcast = now
                            try:
                                from app.v1.ai.health import get_camera_ai_health
                                from app.v1.ws.manager import ws_manager

                                ws_manager.broadcast_sync({
                                    "type": "AI_HEALTH",
                                    **get_camera_ai_health(self.camera_id),
                                })
                            except Exception:
                                pass
                    except Exception as infer_exc:
                        logger.debug("Frame infer skipped/failed: %s", infer_exc)

            except Exception as exc:
                self.reconnect_count += 1
                update_camera_health(
                    self.camera_id,
                    worker_alive=True,
                    processing=False,
                    last_error=str(exc),
                    reconnect_count=self.reconnect_count,
                    ai_hint="DEGRADED",
                )
                logger.warning(
                    "RTSP worker camera=%s reconnecting in %.1fs: %s",
                    self.camera_id,
                    backoff,
                    exc,
                )
                reset_camera_tracker(self.camera_id)
                reset_person_tracker(self.camera_id)
                self._stop.wait(backoff)
                backoff = min(60.0, backoff * 1.8)
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass

        update_camera_health(self.camera_id, worker_alive=False, processing=False)


class WorkerManager:
    def __init__(self) -> None:
        self._workers: dict[str, CameraWorker] = {}
        self._lock = threading.Lock()

    def start_all_enabled(self) -> None:
        if not settings.ENABLE_RTSP_WORKERS:
            logger.info("RTSP workers disabled via ENABLE_RTSP_WORKERS")
            return
        try:
            from app.db.session import SessionLocal
            from app.v1.cameras.models import Camera

            db = SessionLocal()
            try:
                cameras = (
                    db.query(Camera)
                    .filter(
                        Camera.is_deleted == False,
                        Camera.is_enabled == True,
                        Camera.source_type.in_(["rtsp", "dvr", "ip"]),
                    )
                    .all()
                )
                for cam in cameras:
                    if cam.stream_url:
                        self.start_camera(cam.id, cam.stream_url)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Failed to start RTSP workers: %s", exc)

    def start_camera(self, camera_id: str, stream_url: str) -> None:
        if not settings.ENABLE_RTSP_WORKERS:
            return
        with self._lock:
            existing = self._workers.get(camera_id)
            if existing:
                existing.restart(stream_url)
                return
            worker = CameraWorker(camera_id, stream_url)
            self._workers[camera_id] = worker
            worker.start()

    def stop_camera(self, camera_id: str) -> None:
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker:
            worker.stop()

    def restart_camera(self, camera_id: str, stream_url: str) -> None:
        self.stop_camera(camera_id)
        self.start_camera(camera_id, stream_url)

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self._workers.keys())
        for cid in ids:
            self.stop_camera(cid)


worker_manager = WorkerManager()
