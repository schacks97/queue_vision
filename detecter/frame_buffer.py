"""
Thread-safe frame buffer for sharing live inference frames
between the background processing thread and the MJPEG streaming view.
"""
import threading
from typing import Dict, Optional

import cv2
import numpy as np

_lock = threading.Lock()
_buffers: Dict[str, bytes] = {}  # job_id → JPEG bytes


def push_frame(job_id: str, frame: np.ndarray) -> None:
    """Encode frame as JPEG and store it (called from pipeline thread)."""
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    with _lock:
        _buffers[job_id] = jpeg.tobytes()


def get_frame(job_id: str) -> Optional[bytes]:
    """Get the latest JPEG bytes (called from Django view)."""
    with _lock:
        return _buffers.get(job_id)


def clear(job_id: str) -> None:
    """Remove buffer when job finishes."""
    with _lock:
        _buffers.pop(job_id, None)
