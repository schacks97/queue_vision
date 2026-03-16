"""
Background task runner for video processing jobs.
Uses a plain daemon thread — no Celery required.
"""
import logging
import os
import threading

from django.conf import settings
from django.utils import timezone

from . import frame_buffer

logger = logging.getLogger(__name__)


def run_job(job_id: str) -> None:
    """Start processing a job in a background thread."""
    t = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    t.start()


def _process_job(job_id: str) -> None:
    # Deferred imports to avoid circular dependencies at module load time
    try:
        from .models import ProcessingJob
        from .pipeline.config import PipelineConfig
        from .pipeline.video_processor import VideoProcessor
    except Exception as exc:
        logger.exception("IMPORT FAILED in background thread: %s", exc)
        print(f"\n*** IMPORT ERROR IN PIPELINE THREAD: {exc}\n")
        return

    try:
        job = ProcessingJob.objects.get(id=job_id)
    except ProcessingJob.DoesNotExist:
        logger.error("Job %s not found", job_id)
        return
    except Exception as exc:
        logger.exception("DB ERROR looking up job %s: %s", job_id, exc)
        print(f"\n*** DB ERROR (job lookup): {exc}\n")
        return

    # ── resolve input path ────────────────────────────────────────
    input_path = job.input_file
    print(f"\n>>> [PIPELINE] Job {job_id} starting. Input: {input_path}")
    if not input_path or not os.path.isfile(input_path):
        msg = f"Input file not found: {input_path}"
        print(f">>> [PIPELINE] FAILED: {msg}")
        job.status = ProcessingJob.Status.FAILED
        job.error_message = msg
        job.save(update_fields=["status", "error_message"])
        return

    # ── prepare output paths ──────────────────────────────────────
    output_dir = os.path.join(settings.MEDIA_ROOT, "detecter", "outputs")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{job_id}.mp4")

    # ── mark job as processing ────────────────────────────────────
    job.status = ProcessingJob.Status.PROCESSING
    job.started_at = timezone.now()
    job.output_file = output_path
    try:
        job.save(update_fields=["status", "started_at", "output_file"])
        print(f">>> [PIPELINE] Job marked processing. Output: {output_path}")
    except Exception as exc:
        print(f">>> [PIPELINE] DB SAVE FAILED (missing migration?): {exc}")
        logger.exception("DB save failed: %s", exc)
        return

    regions = job.roi_regions or []

    # Read saved model from dashboard config
    try:
        from dashboard.models import SiteConfig
        site_cfg = SiteConfig.load()
        detecter_model = site_cfg.detecter_model
        detecter_confidence = site_cfg.detecter_confidence
        detection_classes = site_cfg.detection_classes or [2, 3, 5, 7]
    except Exception:
        detecter_model = "yolov8s"
        detecter_confidence = 0.3
        detection_classes = [2, 3, 5, 7]

    # Resolve model path from media/models/<family>/<model_file>
    from django.conf import settings as django_settings
    models_dir = os.path.join(django_settings.MEDIA_ROOT, "models")
    # detecter_model now stores the full filename (e.g. "yolov8n.pt" or "yolov8n.onnx")
    model_file = detecter_model
    if not os.path.splitext(model_file)[1]:
        model_file = model_file + ".pt"  # legacy fallback for old configs without extension
    model_path = model_file  # fallback: bare filename (Ultralytics will download)
    if os.path.isdir(models_dir):
        for family_folder in os.listdir(models_dir):
            candidate = os.path.join(models_dir, family_folder, model_file)
            if os.path.isfile(candidate):
                model_path = candidate
                break

    # No automatic override — the user's dashboard selection is used directly.
    # If they want ONNX/TensorRT, they select it from the dashboard dropdown.

    config = PipelineConfig(
        input_video=input_path,
        output_video=output_path,
        log_level="DEBUG",
        roi_enabled=bool(regions),
        roi_regions=regions,
        detecter_model=model_path,
        detecter_confidence=detecter_confidence,
        detection_classes=detection_classes,
    )

    # ── progress callback (called every 5 processed frames) ───────
    def on_progress(current_frame, total_frames, processing_fps, total_vehicles):
        progress = int(current_frame / total_frames * 100) if total_frames else 0
        ProcessingJob.objects.filter(id=job_id).update(
            current_frame=current_frame,
            total_frames=total_frames,
            processing_fps=round(processing_fps, 2),
            total_vehicles=total_vehicles,
            progress=progress,
        )

    # ── run pipeline ──────────────────────────────────────────────
    try:
        print(">>> [PIPELINE] Creating VideoProcessor...")
        processor = VideoProcessor(config)
        processor._frame_callback = lambda frame: frame_buffer.push_frame(str(job_id), frame)
        print(">>> [PIPELINE] Starting process()...")
        processor.process(on_progress=on_progress)

        # Collect final results from timer manager
        wait_times = processor.timer_manager.get_all_wait_times()
        class_names = processor.timer_manager._class_names
        active_ids = set(processor.timer_manager._entry_times.keys())
        vehicle_data = {
            str(tid): {
                "class_name": class_names.get(tid, "vehicle"),
                "wait_seconds": round(wt, 2),
                "active": tid in active_ids,
            }
            for tid, wt in wait_times.items()
        }
        avg_wait = sum(wait_times.values()) / len(wait_times) if wait_times else 0.0
        max_wait = max(wait_times.values()) if wait_times else 0.0
        max_id = max(wait_times, key=wait_times.get) if wait_times else None

        job.refresh_from_db()
        job.status = ProcessingJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.total_vehicles = len(wait_times)
        job.avg_wait_time = round(avg_wait, 2)
        job.max_wait_time = round(max_wait, 2)
        job.max_wait_vehicle_id = max_id
        job.vehicle_data = vehicle_data
        job.progress = 100
        job.save()

        logger.info("Job %s completed. Vehicles: %d", job_id, len(wait_times))
        print(f">>> [PIPELINE] Job {job_id} completed. Vehicles: {len(wait_times)}")

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        print(f"\n>>> [PIPELINE] JOB FAILED: {exc}\n")
        ProcessingJob.objects.filter(id=job_id).update(
            status=ProcessingJob.Status.FAILED,
            error_message=str(exc),
        )
    finally:
        frame_buffer.clear(str(job_id))
