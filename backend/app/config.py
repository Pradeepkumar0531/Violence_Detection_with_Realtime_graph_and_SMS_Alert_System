"""
Configuration module for the Violence Detection System.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend root
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    # ── Twilio Configuration ──────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE: str = os.getenv("TWILIO_PHONE", "")
    TARGET_PHONE: str = os.getenv("TARGET_PHONE", "")

    # ── Detection Thresholds ──────────────────────────────────────────
    VIOLENCE_THRESHOLD: float = float(os.getenv("VIOLENCE_THRESHOLD", "0.7"))
    BUFFER_SIZE: int = int(os.getenv("BUFFER_SIZE", "5"))
    MIN_HITS: int = int(os.getenv("MIN_HITS", "3"))

    # ── Alert Settings ────────────────────────────────────────────────
    SMS_COOLDOWN: int = int(os.getenv("SMS_COOLDOWN", "30"))

    # ── Video Pipeline Settings ───────────────────────────────────────
    FRAME_SAMPLE_RATE: int = int(os.getenv("FRAME_SAMPLE_RATE", "3"))
    WINDOW_SIZE: int = int(os.getenv("WINDOW_SIZE", "16"))
    STRIDE: int = int(os.getenv("STRIDE", "8"))

    # ── Video Source ──────────────────────────────────────────────────
    # "0" for webcam, or a file path for video file
    VIDEO_SOURCE: str = os.getenv("VIDEO_SOURCE", "0")

    # ── Model Path ────────────────────────────────────────────────────
    MODEL_PATH: str = str(_backend_dir / "model")

    # ── Smoothing ─────────────────────────────────────────────────────
    SMOOTHING_WINDOW: int = 3

    @property
    def twilio_configured(self) -> bool:
        """Check if all Twilio credentials are provided."""
        return all([
            self.TWILIO_ACCOUNT_SID,
            self.TWILIO_AUTH_TOKEN,
            self.TWILIO_PHONE,
            self.TARGET_PHONE,
        ])

    @property
    def video_source_parsed(self):
        """Return int for webcam index, or string path for video file."""
        try:
            return int(self.VIDEO_SOURCE)
        except ValueError:
            return self.VIDEO_SOURCE


settings = Settings()
