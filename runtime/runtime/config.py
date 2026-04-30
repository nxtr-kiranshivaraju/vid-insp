"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val else default


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val else default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    # Database
    database_url: str = field(default_factory=lambda: _env_str(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vlm_runtime"
    ))
    db_pool_min_size: int = field(default_factory=lambda: _env_int("DB_POOL_MIN_SIZE", 2))
    db_pool_max_size: int = field(default_factory=lambda: _env_int("DB_POOL_MAX_SIZE", 10))

    # VLM
    vlm_concurrency: int = field(default_factory=lambda: _env_int("VLM_CONCURRENCY", 10))
    jpeg_quality: int = field(default_factory=lambda: _env_int("JPEG_QUALITY", 85))
    image_max_dimension: int = field(default_factory=lambda: _env_int("IMAGE_MAX_DIMENSION", 1024))

    # Snapshot cache
    snapshot_diff_threshold: float = field(
        default_factory=lambda: _env_float("SNAPSHOT_DIFF_THRESHOLD", 15.0)
    )

    # Camera failure
    camera_starved_threshold: int = field(
        default_factory=lambda: _env_int("CAMERA_STARVED_THRESHOLD", 5)
    )
    camera_max_retries: int = field(default_factory=lambda: _env_int("CAMERA_MAX_RETRIES", 10))
    camera_base_delay: float = field(default_factory=lambda: _env_float("CAMERA_BASE_DELAY", 2.0))
    camera_max_delay: float = field(default_factory=lambda: _env_float("CAMERA_MAX_DELAY", 60.0))
    camera_heartbeat_interval: float = field(
        default_factory=lambda: _env_float("CAMERA_HEARTBEAT_INTERVAL", 30.0)
    )

    # Retention
    observation_retention_days: int = field(
        default_factory=lambda: _env_int("OBSERVATION_RETENTION_DAYS", 90)
    )

    # API
    api_host: str = field(default_factory=lambda: _env_str("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8080))

    # Cost (USD per million tokens — defaults are advisory, override per-deployment)
    vlm_cost_per_mtok_input: float = field(
        default_factory=lambda: _env_float("VLM_COST_PER_MTOK_INPUT", 3.0)
    )
    vlm_cost_per_mtok_output: float = field(
        default_factory=lambda: _env_float("VLM_COST_PER_MTOK_OUTPUT", 15.0)
    )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
