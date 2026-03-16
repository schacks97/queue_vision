from typing import List, Tuple

import cv2
import numpy as np

from .config import PipelineConfig
from .tracker import TrackedObject
from .logger import get_logger


# Colours for up to 8 ROI regions (BGR)
_ROI_COLORS = [
    (0, 255, 255),  # yellow
    (0, 230, 118),  # green
    (255, 165, 0),  # orange-ish
    (255, 105, 180),# pink
    (0, 191, 255),  # deep-sky blue
    (147, 112, 219),# purple
    (64, 224, 208), # turquoise
    (255, 99, 71),  # tomato
]


class ROIManager:
    """Manages multiple ROI regions (rectangles and polygons) and filters tracked objects."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger("ROIManager", config)

        self.enabled = config.roi_enabled
        self.regions: List[dict] = list(config.roi_regions) if config.roi_regions else []

        # Pre-compute numpy polygon contours for fast point-in-polygon tests
        self._poly_contours: List[np.ndarray] = []
        for r in self.regions:
            if r.get("type") == "polygon" and r.get("points"):
                pts = np.array(r["points"], dtype=np.int32)
                self._poly_contours.append(pts)
            else:
                self._poly_contours.append(None)

        if self.enabled and self.regions:
            for i, r in enumerate(self.regions):
                rtype = r.get("type", "rect")
                if rtype == "polygon":
                    n = len(r.get("points", []))
                    self.logger.info("ROI #%d: polygon with %d vertices", i + 1, n)
                else:
                    self.logger.info(
                        "ROI #%d: rect (%d, %d) -> (%d, %d)",
                        i + 1, r["x1"], r["y1"], r["x2"], r["y2"],
                    )
        else:
            self.logger.info("ROI disabled — all tracks will be kept.")

    def center_of(self, track: TrackedObject) -> Tuple[int, int]:
        cx = (track.x1 + track.x2) // 2
        cy = (track.y1 + track.y2) // 2
        return cx, cy

    def _inside_region(self, cx: int, cy: int, idx: int) -> bool:
        r = self.regions[idx]
        if r.get("type") == "polygon":
            contour = self._poly_contours[idx]
            if contour is None:
                return False
            return cv2.pointPolygonTest(contour, (float(cx), float(cy)), False) >= 0
        # Default: rectangle
        return r["x1"] <= cx <= r["x2"] and r["y1"] <= cy <= r["y2"]

    def is_inside(self, track: TrackedObject) -> bool:
        if not self.enabled or not self.regions:
            return True
        cx, cy = self.center_of(track)
        return any(self._inside_region(cx, cy, i) for i in range(len(self.regions)))

    def filter_tracks(self, tracks: List[TrackedObject]) -> List[TrackedObject]:
        if not self.enabled or not self.regions:
            return tracks
        return [t for t in tracks if self.is_inside(t)]

    def _draw_rect(self, frame: np.ndarray, r: dict, color, label: str) -> None:
        x1, y1, x2, y2 = r["x1"], r["y1"], r["x2"], r["y2"]
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        self._draw_label(frame, label, x1, y1, color)

    def _draw_polygon(self, frame: np.ndarray, r: dict, color, label: str) -> None:
        pts = np.array(r["points"], dtype=np.int32)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)
        # Draw vertex dots
        for p in pts:
            cv2.circle(frame, tuple(p), 4, color, -1)
        # Label at first vertex
        lx, ly = int(pts[0][0]), int(pts[0][1])
        self._draw_label(frame, label, lx, ly, color)

    @staticmethod
    def _draw_label(frame, label, x, y, color):
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x, y - th - 8), (x + tw + 6, y), color, -1)
        cv2.putText(frame, label, (x + 3, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)

    def draw(self, frame: np.ndarray) -> np.ndarray:
        if not self.enabled or not self.regions:
            return frame

        for i, r in enumerate(self.regions):
            color = _ROI_COLORS[i % len(_ROI_COLORS)]
            label = f"ROI {i + 1}"
            if r.get("type") == "polygon":
                self._draw_polygon(frame, r, color, label)
            else:
                self._draw_rect(frame, r, color, label)
        return frame
