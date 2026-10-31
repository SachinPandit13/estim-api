import os
import re
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database components
    DB_HOST: str = "localhost"
    DB_USER_NAME: str = "postgres"
    DB_PASSWORD: str = ""
    DB_NAME: str = "estim_local_db"
    DB_PORT: str = "5432"

    # Database config
    DB_URL: str = Field(
        default="postgresql+psycopg2://{DB_USER_NAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Project Settings
    PROJECT_NAME: str = "ESTIM"
    APP_NAME: str = "ESTIM"
    ENVIRONMENT: str = "development"
    AUDIT_ONLY_LOGS: bool = False

    # Comma-separated browser origins allowed for cross-origin API requests (see app/main.py).
    CORS_ORIGINS: str | list[str] = "http://localhost:3000"

    # AI & Processing Engine
    AI_DEVICE: str = "auto"  # auto | cpu | cuda
    FRAME_SAMPLE_RATE: float = 2.0
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.50
    INCIDENT_COOLDOWN_SECONDS: int = 60
    TEMPORAL_CONFIRMATION_FRAMES: int = 3
    TRACK_MISS_TTL: int = 8
    SNAPSHOTS_DIR: str = "uploads/snapshots"
    PERSON_MODEL_PATH: str = "yolov8n.pt"
    PPE_MODEL_PATH: str = ""
    FIRE_SMOKE_MODEL_PATH: str = ""
    POSE_MODEL_PATH: str = ""
    ENABLE_PPE_MODEL: bool = False
    ENABLE_FIRE_SMOKE_MODEL: bool = False
    ENABLE_POSE_FALL_MODEL: bool = False
    ENABLE_RTSP_WORKERS: bool = True
    AI_MAX_WORKERS: int = 2
    AI_FRAME_QUEUE_SIZE: int = 2
    PPE_CADENCE: int = 2
    FIRE_SMOKE_CADENCE: int = 4
    POSE_CADENCE: int = 3

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    @model_validator(mode="after")
    def resolve_db_url(self) -> "Settings":
        if "{" in self.DB_URL:
            context = {
                "DB_HOST": self.DB_HOST,
                "DB_USER_NAME": self.DB_USER_NAME,
                "DB_PASSWORD": self.DB_PASSWORD,
                "DB_NAME": self.DB_NAME,
                "DB_PORT": str(self.DB_PORT),
            }
            self.DB_URL = re.sub(
                r"\{(\w+)\}",
                lambda m: str(context.get(m.group(1), os.getenv(m.group(1), m.group(0)))),
                self.DB_URL,
            )
        return self


settings = Settings()