import time
from typing import Dict, List, Set

import cv2
import numpy as np

from .config import PipelineConfig
from .tracker import TrackedObject
from .logger import get_logger


class TimerManager:
    """Tracks per-vehicle dwell time inside the ROI using video timestamps."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger("TimerManager", config)

        # {track_id: entry_video_time_seconds}
        self._entry_times: Dict[int, float] = {}
        # {track_id: accumulated_seconds}  (for vehicles that left the ROI)
        self._completed: Dict[int, float] = {}
        # {track_id: class_name}
        self._class_names: Dict[int, str] = {}
        # Current video timestamp (updated each frame)
        self._current_time: float = 0.0

        self.logger.info("TimerManager initialised.")

    # ── public API ───────────────────────────────────────────

    def update(self, roi_tracks: List[TrackedObject], video_time: float) -> None:
        """Call once per frame with the tracks currently inside the ROI.

        Args:
            roi_tracks: tracks that are inside the ROI this frame.
            video_time: current video timestamp in seconds (frame_number / fps).
        """
        self._current_time = video_time
        active_ids: Set[int] = set()

        for t in roi_tracks:
            active_ids.add(t.track_id)
            if t.track_id not in self._class_names:
                self._class_names[t.track_id] = t.class_name

        # Start timers for newly entered vehicles
        for tid in active_ids:
            if tid not in self._entry_times:
                self._entry_times[tid] = video_time
                cls = self._class_names.get(tid, "vehicle")
                self.logger.info("ENTER  | ID %-4d | class: %-12s | entered ROI at %.2fs", tid, cls, video_time)

        # Finalize timers for vehicles that left
        exited = set(self._entry_times.keys()) - active_ids
        for tid in exited:
            elapsed = video_time - self._entry_times.pop(tid)
            self._completed[tid] = elapsed
            cls = self._class_names.get(tid, "vehicle")
            self.logger.info(
                "EXIT   | ID %-4d | class: %-12s | wait: %s (%.1fs)",
                tid, cls, self._format(elapsed), elapsed,
            )

    def get_wait_time(self, track_id: int) -> float:
        """Return current wait time in seconds (active or completed)."""
        if track_id in self._entry_times:
            return self._current_time - self._entry_times[track_id]
        return self._completed.get(track_id, 0.0)

    def get_all_wait_times(self) -> Dict[int, float]:
        """Return {track_id: seconds} for every known vehicle."""
        result: Dict[int, float] = {}
        for tid, start in self._entry_times.items():
            result[tid] = self._current_time - start
        result.update(self._completed)
        return result

    # ── drawing ──────────────────────────────────────────────

    def draw(self, frame: np.ndarray, roi_tracks: List[TrackedObject]) -> np.ndarray:
        """Draw MM:SS wait time label on each tracked vehicle inside the ROI."""
        for t in roi_tracks:
            seconds = self.get_wait_time(t.track_id)
            label = self._format(seconds)

            cx = (t.x1 + t.x2) // 2
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            lx = cx - tw // 2
            ly = t.y2 + th + 12

            cv2.rectangle(frame, (lx - 4, ly - th - 4), (lx + tw + 4, ly + 4), (0, 0, 0), -1)
            cv2.putText(frame, label, (lx, ly),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
        return frame

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _format(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
