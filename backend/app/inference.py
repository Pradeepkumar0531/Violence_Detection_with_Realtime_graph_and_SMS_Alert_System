"""
Transformers-based violence detection inference engine.
Loads the VideoMAE model from safetensors and runs prediction using PyTorch.
"""

import logging
import torch
import numpy as np
from transformers import VideoMAEForVideoClassification, AutoImageProcessor

from .config import settings

logger = logging.getLogger(__name__)


class ViolenceDetector:
    """
    Transformers inference wrapper for the VideoMAE violence detection model.

    Expected input: List of 16 frames or preprocessed tensor.
    Output: violence_score (probability of violence class)
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or settings.MODEL_PATH
        self.model = None
        self.processor = None
        self._loaded = False
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def load(self) -> bool:
        """
        Load the VideoMAE model and processor.

        Returns:
            True if the model loaded successfully, False otherwise.
        """
        try:
            logger.info(f"Loading model from: {self.model_path} on {self.device}")
            
            self.processor = AutoImageProcessor.from_pretrained(self.model_path)
            self.model = VideoMAEForVideoClassification.from_pretrained(self.model_path)
            
            self.model.to(self.device)
            self.model.eval()

            logger.info("Model and processor loaded successfully")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._loaded = False
            return False

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded and ready for inference."""
        return self._loaded and self.model is not None

    def predict(self, frames: list[np.ndarray]) -> dict:
        """
        Run inference on a list of frames.

        Args:
            frames: List of 16 BGR frames from OpenCV (H, W, 3)

        Returns:
            Dictionary with:
                - violence_score: float (0-1 probability of violence)
                - raw_logits: list of raw model logits
                - probabilities: list of softmax probabilities
        """
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call load() first.")

        if len(frames) != 16:
            raise ValueError(f"Expected 16 frames, got {len(frames)}")

        # Preprocess frames
        # VideoMAE processor expects frames in (T, C, H, W) or (T, H, W, C)
        # OpenCV frames are BGR, processor usually expects RGB
        rgb_frames = [np.ascontiguousarray(f[:, :, ::-1]) for f in frames]
        
        inputs = self.processor(rgb_frames, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probabilities = torch.nn.functional.softmax(logits, dim=-1)

        # Extract violence score (class 1)
        # Based on config.json: "0": "non_violence", "1": "violence"
        violence_score = float(probabilities[0, 1])
        
        logits_list = logits[0].cpu().tolist()
        probs_list = probabilities[0].cpu().tolist()

        logger.debug(
            f"Inference complete — violence_score: {violence_score:.4f}, "
            f"logits: {logits_list}"
        )

        return {
            "violence_score": violence_score,
            "raw_logits": logits_list,
            "probabilities": probs_list,
        }
