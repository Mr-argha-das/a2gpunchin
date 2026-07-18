from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(".env", override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "rMatrix"
    environment: str = "development"
    debug: bool = True
    secret_key: str = Field(default="change-me-in-production", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    mongodb_uri: str = "mongodb+srv://infozodex_db_user:absolutions@data.yycywiw.mongodb.net/testing3_db_new"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["*"]
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "attendance"
    minio_secure: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@example.com"
    whatsapp_provider_url: str = ""
    whatsapp_token: str = ""
    auto_punch_out_after_minutes: int = 30
    face_punch_cooldown_seconds: int = 10
    face_index_dir: str = "./data/face_index"
    similarity_threshold: float = 0.45
    gpu_id: int = -1
    face_det_size: int = 320
    face_liveness_min_frame_delta: float = 3.5
    voice_data_dir: str = "./data/voice"
    voice_speaker_threshold: float = 0.35
    voice_device: str = "cpu"
    default_timezone: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
