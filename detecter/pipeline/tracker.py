from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from .config import PipelineConfig
from .detector import Detection
from .logger import get_logger


@dataclass
class TrackedObject:
    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_name: str


class VehicleTracker:
    # Color palette for track IDs (BGR)
    ID_COLORS = [
        (230, 100, 50), (50, 200, 50), (50, 100, 230),
        (200, 50, 200), (50, 200, 200), (200, 200, 50),
        (150, 80, 200), (100, 200, 150), (200, 150, 100),
        (80, 150, 230),
    ]

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger("VehicleTracker", config)
        self.logger.info(
            "Tracker ready — using ultralytics built-in ByteTrack (no supervision)"
        )

    def update(self, detections: List[Detection]) -> List[TrackedObject]:
        """Convert detections (already tracked by model.track) into TrackedObject list."""
        tracks: List[TrackedObject] = []
        for det in detections:
            if det.track_id < 0:
                continue
            tracks.append(TrackedObject(
                track_id=det.track_id,
                x1=det.x1, y1=det.y1,
                x2=det.x2, y2=det.y2,
                confidence=det.confidence,
                class_name=det.class_name,
            ))
        return tracks

    def draw(self, frame: np.ndarray, tracks: List[TrackedObject]) -> np.ndarray:
        for t in tracks:
            color = self.ID_COLORS[t.track_id % len(self.ID_COLORS)]
            cv2.rectangle(frame, (t.x1, t.y1), (t.x2, t.y2), color, 2)

            label = f"ID {t.track_id}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (t.x1, t.y1 - th - 8), (t.x1 + tw + 4, t.y1), color, -1)
            cv2.putText(frame, label, (t.x1 + 2, t.y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

            sub_label = f"{t.class_name} {t.confidence:.2f}"
            cv2.putText(frame, sub_label, (t.x1 + 2, t.y2 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
        return frame
