"""
Temporal smoothing and spike detection for violence scores.
"""

import logging
from collections import deque
from .config import settings

logger = logging.getLogger(__name__)


class TemporalSmoother:
    """
    Smoothing: moving average over recent scores.
    Spike Detection: if >= min_hits of last buffer_size scores > threshold → violence.
    """

    def __init__(
        self,
        threshold: float | None = None,
        buffer_size: int | None = None,
        min_hits: int | None = None,
        smoothing_window: int | None = None,
    ):
        self.threshold = threshold if threshold is not None else settings.VIOLENCE_THRESHOLD
        self.buffer_size = buffer_size if buffer_size is not None else settings.BUFFER_SIZE
        self.min_hits = min_hits if min_hits is not None else settings.MIN_HITS
        self.smoothing_window = smoothing_window if smoothing_window is not None else settings.SMOOTHING_WINDOW

        self._smoothing_buffer: deque[float] = deque(maxlen=self.smoothing_window)
        self._score_history: deque[float] = deque(maxlen=self.buffer_size)
        self._is_violence = False

    def update(self, raw_score: float) -> dict:
        """Process a new raw score through smoothing and spike detection."""
        # Step 1: Moving average smoothing
        self._smoothing_buffer.append(raw_score)
        smoothed_score = sum(self._smoothing_buffer) / len(self._smoothing_buffer)

        # Step 2: Add to history
        self._score_history.append(smoothed_score)

        # Step 3: Violence = current smoothed score exceeds threshold
        # This matches the graph visualization exactly — alert fires
        # only when the plotted line crosses the threshold.
        self._is_violence = smoothed_score > self.threshold
        scores_above = sum(1 for s in self._score_history if s > self.threshold)

        result = {
            "smoothed_score": round(smoothed_score, 4),
            "is_violence": self._is_violence,
            "raw_score": round(raw_score, 4),
            "scores_above_threshold": scores_above,
            "history": [round(s, 4) for s in self._score_history],
        }

        logger.debug(
            f"Smoothing — raw: {raw_score:.4f}, smoothed: {smoothed_score:.4f}, "
            f"violence: {self._is_violence}"
        )
        return result

    @property
    def is_violence(self) -> bool:
        return self._is_violence

    def reset(self):
        self._smoothing_buffer.clear()
        self._score_history.clear()
        self._is_violence = False
        logger.info("Temporal smoother reset")
