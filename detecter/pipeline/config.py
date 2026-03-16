from dataclasses import dataclass, field
import os

try:
    import torch
    _cuda_available = torch.cuda.is_available()
except ImportError:
    _cuda_available = False


@dataclass
class PipelineConfig:
    # Video I/O
    input_video: str = ""
    output_video: str = "output.mp4"
    codec: str = "mp4v"
    frame_skip: int = 1  # Process every Nth frame (1 = all frames)

    # Detection
    detecter_model: str = "yolov8n.pt"
    detecter_confidence: float = 0.3
    detecter_device: str = "cuda" if _cuda_available else "cpu"
    detection_classes: list = field(default_factory=lambda: [2, 3, 5, 7])

    # Tracking (ByteTrack)
    tracker_track_thresh: float = 0.25
    tracker_track_buffer: int = 30
    tracker_match_thresh: float = 0.8
    tracker_frame_rate: int = 30

    # ROI (Region of Interest) — list of region dicts. Two types supported:
    #   Rectangle: {"type":"rect", "x1":…,"y1":…,"x2":…,"y2":…}
    #   Polygon:   {"type":"polygon", "points":[[x,y],[x,y],…]}
    roi_enabled: bool = False
    roi_regions: list = field(default_factory=list)

    # Logging
    log_level: str = "INFO"
    log_file: str = ""  # Empty = console only

    def validate(self):
        if not self.input_video:
            raise ValueError("input_video path is required.")
        if not os.path.isfile(self.input_video):
            raise FileNotFoundError(f"Input video not found: {self.input_video}")
        if self.frame_skip < 1:
            raise ValueError("frame_skip must be >= 1.")
