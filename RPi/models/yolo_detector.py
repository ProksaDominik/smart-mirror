from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from .base import InferenceResult


class YoloDroneModel:
    def __init__(self, model_path: Path) -> None:
        self._model = YOLO(str(model_path))

    def run(self, frame_rgb: np.ndarray, conf: float, iou: float) -> InferenceResult:
        # TODO: run inference
        payload = {
            "model": "best.pt",
            "detection_count": len(cls_ids),
            "counts": counts,
            "conf": float(conf),
            "iou": float(iou),
        }
        return InferenceResult(
            annotated_rgb=annotated_rgb,
            payload=payload,
            status_text=f"YOLO done. detections={len(cls_ids)}",
        )
