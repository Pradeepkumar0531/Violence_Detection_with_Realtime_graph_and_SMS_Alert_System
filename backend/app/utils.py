"""
Utility functions for frame preprocessing and formatting.
"""

import cv2
import numpy as np
from datetime import datetime, timezone


def preprocess_frame(frame: np.ndarray, target_size: tuple[int, int] = (224, 224)) -> np.ndarray:
    """
    Preprocess a single BGR frame for VideoMAE input.

    Steps:
        1. Resize to target_size (224x224)
        2. Convert BGR → RGB
        3. Normalize pixel values to [0, 1]
        4. Apply ImageNet-style normalization

    Args:
        frame: Raw BGR frame from OpenCV (H, W, 3)
        target_size: Target spatial dimensions (H, W)

    Returns:
        Preprocessed frame as float32 array (3, H, W) in CHW format
    """
    # Resize
    resized = cv2.resize(frame, (target_size[1], target_size[0]), interpolation=cv2.INTER_LINEAR)

    # BGR → RGB
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    # Normalize to [0, 1]
    normalized = rgb.astype(np.float32) / 255.0

    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    normalized = (normalized - mean) / std

    # HWC → CHW
    chw = np.transpose(normalized, (2, 0, 1))

    return chw


def build_input_tensor(frames: list[np.ndarray]) -> np.ndarray:
    """
    Build the model input tensor from a list of preprocessed frames.

    Args:
        frames: List of 16 preprocessed frames, each (3, 224, 224)

    Returns:
        Input tensor of shape (1, 16, 3, 224, 224) as float32
    """
    # Stack frames: (16, 3, 224, 224)
    stacked = np.stack(frames, axis=0)

    # Add batch dimension: (1, 16, 3, 224, 224)
    batched = np.expand_dims(stacked, axis=0)

    return batched.astype(np.float32)


def get_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def get_readable_timestamp() -> str:
    """Return a human-readable local timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def softmax(logits: np.ndarray) -> np.ndarray:
    """
    Compute softmax probabilities from raw logits.

    Args:
        logits: Raw model output logits (1D or 2D array)

    Returns:
        Softmax probabilities with same shape as input
    """
    # Numerical stability: subtract max
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp_vals = np.exp(shifted)
    return exp_vals / np.sum(exp_vals, axis=-1, keepdims=True)
