from dataclasses import dataclass
from typing import List

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from .config import PipelineConfig
from .logger import get_logger


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_name: str
    track_id: int = -1


class Vehicledetecter:
    # COCO class IDs for vehicles
    VEHICLE_CLASS_IDS = {2, 3, 5, 7}  # car, motorcycle, bus, truck

    # Map COCO class name → display name
    CLASS_NAME_MAP = {
        "car": "car",
        "motorcycle": "motorcycle",
        "bus": "bus",
        "truck": "truck",
    }

    # Distinct color per class for drawing (BGR)
    CLASS_COLORS = {
        "car": (0, 200, 0),
        "truck": (0, 140, 255),
        "bus": (255, 100, 0),
        "motorcycle": (180, 0, 255),
    }

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger("Vehicledetecter", config)

        # Use classes from config (dashboard selection) or default
        if config.detection_classes:
            self.VEHICLE_CLASS_IDS = set(config.detection_classes)
        else:
            self.VEHICLE_CLASS_IDS = {2, 3, 5, 7}

        device = config.detecter_device
        self.logger.info(
            "Loading YOLOv8 model: %s  |  device: %s  |  CUDA available: %s",
            config.detecter_model, device, torch.cuda.is_available(),
        )
        if torch.cuda.is_available():
            self.logger.info("GPU: %s", torch.cuda.get_device_name(0))

        self.model = YOLO(config.detecter_model)
        self.model.to(device)
        self.logger.info(
            "Model loaded. Filtering COCO IDs %s | Confidence threshold: %.2f",
            self.VEHICLE_CLASS_IDS, config.detecter_confidence,
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Detect and track vehicles in a single model.track() call."""
        try:
            results = self.model.track(
                frame,
                conf=self.config.detecter_confidence,
                classes=list(self.VEHICLE_CLASS_IDS),
                device=self.config.detecter_device,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
            )
        except Exception as exc:
            self.logger.error("YOLO track() raised an exception: %s", exc, exc_info=True)
            return []

        detections: List[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id not in self.VEHICLE_CLASS_IDS:
                    continue
                cls_name = self.model.names[cls_id]
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0])
                track_id = int(box.id[0]) if box.id is not None else -1

                detections.append(Detection(
                    x1=int(x1), y1=int(y1),
                    x2=int(x2), y2=int(y2),
                    confidence=conf,
                    class_name=cls_name,
                    track_id=track_id,
                ))

        self.logger.debug(
            "track(): frame shape=%s  vehicles=%d  with_ids=%d",
            frame.shape, len(detections), sum(1 for d in detections if d.track_id >= 0),
        )
        return detections

    def draw(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        for det in detections:
            color = self.CLASS_COLORS.get(det.class_name, (255, 255, 255))
            cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), color, 2)

            label = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (det.x1, det.y1 - th - 6), (det.x1 + tw, det.y1), color, -1)
            cv2.putText(frame, label, (det.x1, det.y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        return frame
