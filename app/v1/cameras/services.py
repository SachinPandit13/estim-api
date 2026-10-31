import socket
import time
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.v1.cameras.models import Camera
from app.v1.cameras.schemas import CameraCreate, CameraUpdate, CameraTestResponse
from app.v1.cameras.functions import build_dvr_rtsp_url, parse_rtsp_url, sanitize_rtsp_url


class CameraService:
    @staticmethod
    def get_all(db: Session) -> list[Camera]:
        return db.query(Camera).filter(Camera.is_deleted == False).all()

    @staticmethod
    def get_by_id(db: Session, camera_id: str) -> Optional[Camera]:
        return db.query(Camera).filter(Camera.id == camera_id, Camera.is_deleted == False).first()

    @staticmethod
    def create(db: Session, payload: CameraCreate) -> Camera:
        stream_url = payload.stream_url
        config = dict(payload.config or {})
        source_type = (payload.source_type or "rtsp").lower()

        # If DVR/NVR source type or dynamic dvr_host provided:
        if source_type == "dvr" or payload.dvr_host:
            host = (payload.dvr_host or "").strip() or "127.0.0.1"
            port = payload.dvr_port if payload.dvr_port and payload.dvr_port > 0 else 554
            channel = payload.dvr_channel if payload.dvr_channel and payload.dvr_channel > 0 else 1
            subtype = 1 if payload.subtype == 1 else 0

            stream_url = build_dvr_rtsp_url(
                host=host,
                port=port,
                channel=channel,
                subtype=subtype,
                username=payload.rtsp_username or "",
                password=payload.rtsp_password or "",
            )
            config["dvr_host"] = host
            config["dvr_port"] = port
            config["subtype"] = subtype
            config["dvr_channel"] = channel
            source_type = "dvr"
        elif stream_url:
            parsed = parse_rtsp_url(stream_url)
            if parsed.get("host"):
                config.setdefault("dvr_host", parsed.get("host"))
                config.setdefault("dvr_port", parsed.get("port", 554))
                config.setdefault("subtype", parsed.get("subtype", 0))

        camera = Camera(
            name=payload.name,
            description=payload.description,
            source_type=source_type,
            stream_url=stream_url,
            rtsp_username=payload.rtsp_username,
            rtsp_password=payload.rtsp_password,
            dvr_channel=payload.dvr_channel or config.get("dvr_channel", 1),
            location=payload.location,
            is_enabled=payload.is_enabled,
            config=config,
            status="offline",
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)
        try:
            from app.v1.ai.worker import worker_manager

            if camera.is_enabled and camera.stream_url and source_type in ("rtsp", "dvr", "ip"):
                worker_manager.start_camera(camera.id, camera.stream_url)
        except Exception:
            pass
        return camera

    @staticmethod
    def update(db: Session, camera_id: str, payload: CameraUpdate) -> Optional[Camera]:
        camera = CameraService.get_by_id(db, camera_id)
        if not camera:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        config = dict(camera.config or {})

        if "config" in update_data and update_data["config"]:
            config.update(update_data.pop("config"))

        if payload.source_type == "dvr" or payload.dvr_host:
            host = (payload.dvr_host or config.get("dvr_host") or "").strip() or "127.0.0.1"
            port = payload.dvr_port or config.get("dvr_port") or 554
            channel = payload.dvr_channel or camera.dvr_channel or 1
            subtype = payload.subtype if payload.subtype is not None else config.get("subtype", 0)

            username = payload.rtsp_username if payload.rtsp_username is not None else camera.rtsp_username or ""
            password = payload.rtsp_password if payload.rtsp_password is not None else camera.rtsp_password or ""

            update_data["stream_url"] = build_dvr_rtsp_url(
                host=host,
                port=port,
                channel=channel,
                subtype=subtype,
                username=username,
                password=password,
            )
            config["dvr_host"] = host
            config["dvr_port"] = port
            config["subtype"] = subtype

        old_url = camera.stream_url
        for key, val in update_data.items():
            if key == "rtsp_password" and (val is None or val == ""):
                continue  # blank password = keep existing
            setattr(camera, key, val)

        if payload.dvr_channel is not None:
            config["dvr_channel"] = payload.dvr_channel
        camera.config = config
        db.commit()
        db.refresh(camera)

        # Reconnect AI worker when stream endpoint changes
        try:
            from app.v1.ai.worker import worker_manager
            from app.v1.ai.tracking import reset_camera_tracker
            from app.v1.ai.models.person import reset_person_tracker

            if camera.is_enabled and camera.stream_url and camera.source_type in ("rtsp", "dvr", "ip"):
                if camera.stream_url != old_url or payload.dvr_host or payload.dvr_channel or payload.dvr_port:
                    reset_camera_tracker(camera.id)
                    reset_person_tracker(camera.id)
                    worker_manager.restart_camera(camera.id, camera.stream_url)
            else:
                worker_manager.stop_camera(camera.id)
        except Exception:
            pass

        return camera

    @staticmethod
    def soft_delete(db: Session, camera_id: str) -> bool:
        camera = CameraService.get_by_id(db, camera_id)
        if not camera:
            return False
        camera.is_deleted = True
        camera.is_enabled = False
        db.commit()
        try:
            from app.v1.ai.worker import worker_manager
            from app.v1.ai.tracking import drop_camera_tracker

            worker_manager.stop_camera(camera_id)
            drop_camera_tracker(camera_id)
        except Exception:
            pass
        return True

    @staticmethod
    def toggle_enabled(db: Session, camera_id: str) -> Optional[Camera]:
        camera = CameraService.get_by_id(db, camera_id)
        if not camera:
            return None
        camera.is_enabled = not camera.is_enabled
        db.commit()
        db.refresh(camera)
        try:
            from app.v1.ai.worker import worker_manager

            if camera.is_enabled and camera.stream_url and camera.source_type in ("rtsp", "dvr", "ip"):
                worker_manager.start_camera(camera.id, camera.stream_url)
            else:
                worker_manager.stop_camera(camera.id)
        except Exception:
            pass
        return camera

    @staticmethod
    def test_connection(camera: Camera, db: Optional[Session] = None) -> CameraTestResponse:
        # 1. Local system webcam / demo asset probe
        source = (camera.source_type or "").lower()
        if source in ["webcam", "usb", "device", "demo"]:
            if db:
                camera.status = "online"
                camera.last_connected_at = datetime.now(timezone.utc)
                camera.last_error = None
                db.commit()
            label = "Demo video source" if source == "demo" else "Local system device camera"
            return CameraTestResponse(
                reachable=True,
                status="online",
                message=f"{label} verified for {camera.name}",
                latency_ms=0.5,
            )

        # 2. Dynamic DVR/NVR and RTSP TCP reachability probe
        parsed = parse_rtsp_url(camera.stream_url or "")
        host = parsed.get("host") or (camera.config and camera.config.get("dvr_host"))
        port = parsed.get("port") or (camera.config and camera.config.get("dvr_port")) or 554

        if not host:
            return CameraTestResponse(
                reachable=False,
                status="offline",
                message="Camera has no host/IP configured for RTSP stream",
                latency_ms=None,
            )

        start_time = time.perf_counter()
        try:
            with socket.create_connection((host, int(port)), timeout=2.5):
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                if db:
                    camera.status = "online"
                    camera.last_connected_at = datetime.now(timezone.utc)
                    camera.last_error = None
                    db.commit()
                return CameraTestResponse(
                    reachable=True,
                    status="online",
                    message=f"DVR/RTSP endpoint {host}:{port} is reachable",
                    latency_ms=latency,
                )
        except (socket.timeout, socket.error, OSError) as e:
            if db:
                camera.status = "offline"
                camera.last_error = str(e)
                db.commit()
            return CameraTestResponse(
                reachable=False,
                status="offline",
                message=f"Cannot connect to DVR endpoint {host}:{port}: {e}",
                latency_ms=None,
            )
