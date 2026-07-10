"""
Video capture and frame buffering pipeline.
Handles webcam and video file sources with frame sampling and sliding window.
"""

import logging
import threading
import time
from collections import deque

import cv2
import numpy as np

from .config import settings
from .utils import preprocess_frame

logger = logging.getLogger(__name__)


class VideoStream:
    """
    Thread-safe video capture with frame sampling and sliding window buffering.

    Architecture:
        - Capture thread continuously reads frames from the video source
        - Frames are sampled (every Nth frame) and preprocessed
        - A rolling buffer maintains the last WINDOW_SIZE preprocessed frames
        - Consumers can request the current buffer for inference
    """

    def __init__(
        self,
        source=None,
        sample_rate: int | None = None,
        window_size: int | None = None,
        stride: int | None = None,
    ):
        self.source = source if source is not None else settings.video_source_parsed
        self.sample_rate = sample_rate or settings.FRAME_SAMPLE_RATE
        self.window_size = window_size or settings.WINDOW_SIZE
        self.stride = stride or settings.STRIDE

        self._cap: cv2.VideoCapture | None = None
        self._frame_buffer: deque[np.ndarray] = deque(maxlen=self.window_size)
        self._raw_frame: np.ndarray | None = None  # Latest raw frame (for display)
        self._lock = threading.Lock()
        self._running = False
        self._capture_thread: threading.Thread | None = None
        self._frame_count = 0
        self._frames_since_last_inference = 0
        self._buffer_ready_event = threading.Event()
        self._fps = 30.0  # Default fallback

    def start(self) -> bool:
        """
        Open the video source and start the capture thread.

        Returns:
            True if capture started successfully.
        """
        # On Windows, CAP_DSHOW often works better for webcams than the default MSMF
        if isinstance(self.source, int):
            self._cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                logger.warning(f"Failed to open webcam {self.source} with CAP_DSHOW, trying default...")
                self._cap = cv2.VideoCapture(self.source)
        else:
            self._cap = cv2.VideoCapture(self.source)

        if not self._cap.isOpened():
            logger.error(f"Failed to open video source: {self.source}")
            return False

        # Log video properties
        self._fps = self._cap.get(cv2.CAP_PROP_FPS)
        if self._fps <= 0:
            self._fps = 30.0
            
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(
            f"Video source opened: {self.source} "
            f"({width}x{height} @ {self._fps:.1f} FPS)"
        )

        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="VideoCapture"
        )
        self._capture_thread.start()
        logger.info("Capture thread started")
        return True

    def stop(self):
        """Stop the capture thread and release the video source."""
        self._running = False
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=5.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        self._frame_buffer.clear()
        self._buffer_ready_event.clear()
        logger.info("Video stream stopped")

    def _capture_loop(self):
        """
        Main capture loop running in a dedicated thread.
        Reads frames, applies sampling, preprocesses, and fills the buffer.
        """
        logger.info(f"Starting capture loop for source: {self.source}")
        consecutive_failures = 0
        
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                logger.warning("Video source disconnected, stopping capture")
                break

            ret, frame = self._cap.read()

            if not ret:
                consecutive_failures += 1
                # End of video file — stop instead of looping
                if isinstance(self.source, str) and not str(self.source).isdigit():
                    logger.info("Video file ended")
                    self._running = False
                    break
                else:
                    if consecutive_failures % 30 == 0:
                        logger.warning(f"Failed to read frame from webcam (failures: {consecutive_failures})")
                    time.sleep(0.01)
                    continue

            consecutive_failures = 0
            self._frame_count += 1

            # Store raw frame for potential display use
            with self._lock:
                self._raw_frame = frame.copy()

            # Sample every Nth frame
            if self._frame_count % self.sample_rate != 0:
                continue

            # Add raw frame and its exact timestamp to buffer
            with self._lock:
                frame_timestamp = self._frame_count / self._fps if self._fps > 0 else 0.0
                self._frame_buffer.append((frame.copy(), frame_timestamp))
                self._frames_since_last_inference += 1

                # Signal buffer ready when we have enough frames
                if len(self._frame_buffer) >= self.window_size:
                    self._buffer_ready_event.set()

            # Small sleep to prevent CPU spinning
            time.sleep(0.001)

        self._running = False

    def get_inference_buffer(self) -> list[np.ndarray] | None:
        """
        Get the current frame buffer for inference if stride condition is met.

        The buffer is returned only when:
            1. Buffer has at least WINDOW_SIZE frames
            2. At least STRIDE new frames have been added since last inference

        Returns:
            Tuple of (List of WINDOW_SIZE preprocessed frames, timestamp of the latest frame), or (None, None) if not ready.
        """
        with self._lock:
            # Stride check: only return if enough new frames added, OR if video has ended
            # (to ensure we process the final frames even if they don't reach a full stride)
            stride_met = self._frames_since_last_inference >= self.stride
            if not self._running:
                stride_met = True # Process final bits anyway

            if len(self._frame_buffer) < self.window_size or not stride_met:
                return None, None

            self._frames_since_last_inference = 0
            frames = [item[0] for item in self._frame_buffer]
            timestamp = self._frame_buffer[-1][1]
            return frames, timestamp

    def generate_mjpeg(self):
        """Generator for MJPEG video streaming."""
        while self._running:
            with self._lock:
                if self._raw_frame is None:
                    time.sleep(0.01)
                    continue
                # Copy the frame to avoid mutation issues during encoding
                frame = self._raw_frame.copy() 
            
            # Encode as JPEG
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.04) # ~25 FPS

    def wait_for_buffer(self, timeout: float = 5.0) -> bool:
        """
        Block until the frame buffer has enough frames for inference.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if buffer is ready, False if timed out.
        """
        return self._buffer_ready_event.wait(timeout=timeout)

    def get_latest_raw_frame(self) -> np.ndarray | None:
        """Get the most recent raw BGR frame (thread-safe)."""
        with self._lock:
            return self._raw_frame.copy() if self._raw_frame is not None else None

    @property
    def is_running(self) -> bool:
        """Check if the capture thread is active."""
        return self._running

    @property
    def buffer_size(self) -> int:
        """Current number of frames in the buffer."""
        with self._lock:
            return len(self._frame_buffer)

    @property
    def current_timestamp(self) -> float:
        """Current video timestamp in seconds based on frame count."""
        with self._lock:
            return self._frame_count / self._fps if self._fps > 0 else 0.0
