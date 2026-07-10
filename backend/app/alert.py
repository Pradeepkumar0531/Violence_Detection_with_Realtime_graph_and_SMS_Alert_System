"""
Twilio SMS alert system with cooldown to prevent spam.
"""

import logging
import time
from .config import settings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Sends SMS alerts via Twilio when violence is detected.
    Enforces a cooldown period between alerts to prevent spam.
    Gracefully skips if Twilio is not configured.
    """

    def __init__(self, cooldown: int | None = None):
        self.cooldown = cooldown if cooldown is not None else settings.SMS_COOLDOWN
        self._last_alert_time: float = 0.0
        self._client = None
        self._enabled = False

        if settings.twilio_configured:
            try:
                from twilio.rest import Client
                self._client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                )
                self._enabled = True
                logger.info("Twilio alert system initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Twilio client: {e}")
        else:
            logger.warning(
                "Twilio not configured — SMS alerts disabled. "
                "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE, TARGET_PHONE in .env"
            )

    def should_alert(self) -> bool:
        """Check if enough time has passed since the last alert."""
        return (time.time() - self._last_alert_time) >= self.cooldown

    def send_alert(self, timestamp: str) -> bool:
        """
        Send an SMS alert if cooldown has elapsed.

        Args:
            timestamp: Human-readable timestamp of the detection.

        Returns:
            True if SMS was sent, False otherwise.
        """
        if not self.should_alert():
            logger.debug(
                f"Alert cooldown active — {self.cooldown - (time.time() - self._last_alert_time):.0f}s remaining"
            )
            return False

        message_body = f"⚠️ Violence detected at {timestamp}"

        if not self._enabled:
            logger.info(f"[MOCK ALERT] {message_body}")
            self._last_alert_time = time.time()
            return False

        try:
            msg = self._client.messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE,
                to=settings.TARGET_PHONE,
            )
            self._last_alert_time = time.time()
            logger.info(f"SMS alert sent — SID: {msg.sid}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
            return False

    @property
    def is_enabled(self) -> bool:
        return self._enabled
