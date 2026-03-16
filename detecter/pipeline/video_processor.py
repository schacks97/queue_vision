import os
import shutil
import subprocess
import time

import cv2

from .config import PipelineConfig
from .detector import Vehicledetecter
from .tracker import VehicleTracker
from .roi_manager import ROIManager
from .timer_manager import TimerManager
from .logger import get_logger


class VideoProcessor:
    def __init__(self, config: PipelineConfig):
        config.validate()
        self.config = config
        self.logger = get_logger("VideoProcessor", config)
        self.detecter = Vehicledetecter(config)
        self.tracker = VehicleTracker(config)
        self.roi_manager = ROIManager(config)
        self.timer_manager = TimerManager(config)
        self._frame_callback = None  # set externally: fn(frame_ndarray)

    def process(self, on_progress=None) -> None:
        """
        Run the full pipeline.

        on_progress(current_frame, total_frames, processing_fps, total_vehicles)
            Optional callable invoked every 5 processed frames for live DB updates.
        """
        cap = cv2.VideoCapture(self.config.input_video)
        if not cap.isOpened():
            self.logger.error("Failed to open video: %s", self.config.input_video)
            raise RuntimeError(f"Cannot open video: {self.config.input_video}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.logger.info(
            "Input video: %s | %dx%d @ %.2f FPS | %d total frames",
            self.config.input_video, width, height, video_fps, total_frames,
        )

        fourcc = cv2.VideoWriter_fourcc(*self.config.codec)
        writer = cv2.VideoWriter(self.config.output_video, fourcc, video_fps, (width, height))

        if not writer.isOpened():
            cap.release()
            self.logger.error("Failed to create output video: %s", self.config.output_video)
            raise RuntimeError(f"Cannot create output video: {self.config.output_video}")

        frame_number = 0
        written = 0

        # FPS tracking
        processing_start = time.monotonic()
        fps_interval_start = processing_start
        fps_interval_frames = 0
        current_fps = 0.0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_number += 1

                if frame_number % self.config.frame_skip != 0:
                    continue

                frame = self.process_frame(frame, frame_number, current_fps, video_fps)
                writer.write(frame)
                written += 1
                fps_interval_frames += 1

                # Push every frame to the live stream callback
                if self._frame_callback:
                    try:
                        self._frame_callback(frame)
                    except Exception:
                        pass

                # Notify progress callback every 5 processed frames
                if on_progress and written % 5 == 0:
                    on_progress(
                        current_frame=frame_number,
                        total_frames=total_frames,
                        processing_fps=current_fps,
                        total_vehicles=len(self.timer_manager.get_all_wait_times()),
                    )

                # Update FPS every 30 processed frames
                now = time.monotonic()
                elapsed = now - fps_interval_start
                if fps_interval_frames >= 30 and elapsed > 0:
                    current_fps = fps_interval_frames / elapsed
                    fps_interval_start = now
                    fps_interval_frames = 0

                # Progress log every 200 frames
                if frame_number % 200 == 0:
                    pct = (frame_number / total_frames * 100) if total_frames else 0
                    self.logger.info(
                        "Progress: frame %d / %d (%.1f%%) | processing FPS: %.1f",
                        frame_number, total_frames, pct, current_fps,
                    )
        finally:
            cap.release()
            writer.release()

        # Re-encode to H.264 so browsers can play the output
        self._reencode_h264(self.config.output_video, video_fps)

        total_time = time.monotonic() - processing_start
        avg_fps = written / total_time if total_time > 0 else 0.0

        # Final summary with timer stats
        wait_times = self.timer_manager.get_all_wait_times()
        active_count = len(self.timer_manager._entry_times)
        completed_count = len(self.timer_manager._completed)

        self.logger.info("=" * 60)
        self.logger.info("PIPELINE SUMMARY")
        self.logger.info("-" * 60)
        self.logger.info("Frames read:       %d", frame_number)
        self.logger.info("Frames written:    %d", written)
        self.logger.info("Total time:        %.2fs", total_time)
        self.logger.info("Avg FPS:           %.1f", avg_fps)
        self.logger.info("Vehicles tracked:  %d (active: %d, exited: %d)",
                         len(wait_times), active_count, completed_count)
        if wait_times:
            max_wait = max(wait_times.values())
            max_id = max(wait_times, key=wait_times.get)
            self.logger.info("Longest wait:      ID %d — %.1fs", max_id, max_wait)
        self.logger.info("Output:            %s", self.config.output_video)
        self.logger.info("=" * 60)

    def process_frame(self, frame, frame_number: int, current_fps: float, video_fps: float):
        """Detect, track, filter by ROI, update timers, and draw results."""
        detections = self.detecter.detect(frame)
        tracks = self.tracker.update(detections)
        roi_tracks = self.roi_manager.filter_tracks(tracks)

        video_time = frame_number / video_fps
        self.timer_manager.update(roi_tracks, video_time)

        # Log every frame for the first 5, then every 50 frames at INFO level
        if frame_number <= 5 or frame_number % 50 == 0:
            self.logger.info(
                "Frame %d: shape=%s  detections=%d  tracks=%d  roi_tracks=%d",
                frame_number, frame.shape, len(detections), len(tracks), len(roi_tracks),
            )
        elif tracks:
            self.logger.debug(
                "Frame %d: %d detection(s), %d track(s), %d in ROI",
                frame_number, len(detections), len(tracks), len(roi_tracks),
            )

        frame = self.roi_manager.draw(frame)
        frame = self.tracker.draw(frame, roi_tracks)
        frame = self.timer_manager.draw(frame, roi_tracks)
        self._draw_fps(frame, current_fps)
        return frame

    @staticmethod
    def _draw_fps(frame, fps: float) -> None:
        """Draw FPS counter in the top-right corner."""
        if fps <= 0:
            return
        label = f"FPS: {fps:.1f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        h, w = frame.shape[:2]
        x = w - tw - 12
        y = th + 12
        cv2.rectangle(frame, (x - 4, y - th - 4), (x + tw + 4, y + 4), (0, 0, 0), -1)
        cv2.putText(frame, label, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

    def _reencode_h264(self, video_path: str, fps: float) -> None:
        """Re-encode output video to H.264/AAC so browsers can play it."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            # Try imageio-ffmpeg bundled binary
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except (ImportError, FileNotFoundError):
                pass
        if not ffmpeg:
            self.logger.warning("ffmpeg not found — output video may not play in browser")
            return

        tmp_path = video_path + ".tmp.mp4"
        cmd = [
            ffmpeg, "-y",
            "-i", video_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            tmp_path,
        ]
        self.logger.info("Re-encoding to H.264: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            os.replace(tmp_path, video_path)
            self.logger.info("H.264 re-encode complete: %s", video_path)
        except subprocess.CalledProcessError as exc:
            self.logger.error("ffmpeg failed: %s", exc.stderr.decode(errors="replace"))
            # Keep the original mp4v file as fallback
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except FileNotFoundError:
            self.logger.warning("ffmpeg binary disappeared during re-encode")
        except subprocess.TimeoutExpired:
            self.logger.error("ffmpeg re-encode timed out")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
