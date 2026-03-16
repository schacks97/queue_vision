import json
import os
import re
import time
import uuid
from urllib.parse import urlparse, parse_qs

import requests
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from .models import ProcessingJob
from .tasks import run_job
from . import frame_buffer


ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB


class UploadView(View):
    template_name = "detecter/upload.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        video_file = request.FILES.get("video_file")
        video_url = request.POST.get("video_url", "").strip()

        if video_file:
            return self._handle_file_upload(request, video_file)
        elif video_url:
            return self._handle_url(request, video_url)
        else:
            messages.error(request, "Please upload a video file or provide a video URL.")
            return redirect("detecter:upload")

    # ── file upload ──────────────────────────────────────────

    def _handle_file_upload(self, request, video_file):
        ext = os.path.splitext(video_file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(request, f"Unsupported format ({ext}). Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
            return redirect("detecter:upload")

        if video_file.size > MAX_UPLOAD_SIZE:
            messages.error(request, "File exceeds the 500 MB limit.")
            return redirect("detecter:upload")

        upload_dir = os.path.join(settings.MEDIA_ROOT, "detecter", "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        safe_name = self._safe_filename(video_file.name)
        dest = os.path.join(upload_dir, safe_name)
        with open(dest, "wb+") as f:
            for chunk in video_file.chunks():
                f.write(chunk)

        job = ProcessingJob.objects.create(
            input_file=dest,
            original_filename=video_file.name,
        )
        # Don't start processing yet — redirect to ROI selection
        return redirect("detecter:select_roi", job_id=job.id)

    # ── URL input ────────────────────────────────────────────

    def _handle_url(self, request, video_url):
        parsed = urlparse(video_url)
        if parsed.scheme not in ("http", "https"):
            messages.error(request, "Only http and https URLs are allowed.")
            return redirect("detecter:upload")

        # Convert Google Drive share links to direct download URLs
        download_url = self._resolve_download_url(video_url, parsed)
        if not download_url:
            messages.error(request, "Could not resolve a downloadable URL. Check the link and sharing settings.")
            return redirect("detecter:upload")

        # Download the video to disk
        upload_dir = os.path.join(settings.MEDIA_ROOT, "detecter", "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        # Derive a filename
        basename = os.path.basename(parsed.path) or "video"
        if not os.path.splitext(basename)[1]:
            basename += ".mp4"
        safe_name = self._safe_filename(f"{uuid.uuid4().hex[:8]}_{basename}")
        dest = os.path.join(upload_dir, safe_name)

        try:
            with requests.get(download_url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                # Check content-length if available
                cl = resp.headers.get("Content-Length")
                if cl and int(cl) > MAX_UPLOAD_SIZE:
                    messages.error(request, "Remote file exceeds the 500 MB limit.")
                    return redirect("detecter:upload")

                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        downloaded += len(chunk)
                        if downloaded > MAX_UPLOAD_SIZE:
                            f.close()
                            os.remove(dest)
                            messages.error(request, "Remote file exceeds the 500 MB limit.")
                            return redirect("detecter:upload")
                        f.write(chunk)
        except requests.RequestException as exc:
            messages.error(request, f"Failed to download video: {exc}")
            if os.path.exists(dest):
                os.remove(dest)
            return redirect("detecter:upload")

        job = ProcessingJob.objects.create(
            input_file=dest,
            input_url=video_url,
            original_filename=basename,
        )
        return redirect("detecter:select_roi", job_id=job.id)

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _resolve_download_url(url, parsed):
        """Convert cloud share links to direct download URLs."""
        host = parsed.hostname or ""

        # Google Drive: /file/d/<FILE_ID>/...
        if "drive.google.com" in host:
            m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", parsed.path)
            if m:
                file_id = m.group(1)
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            # Also handle ?id=<FILE_ID> format
            qs = parse_qs(parsed.query)
            if "id" in qs:
                return f"https://drive.google.com/uc?export=download&id={qs['id'][0]}"
            return None

        # Direct link — return as-is
        return url

    @staticmethod
    def _safe_filename(name: str) -> str:
        name = os.path.basename(name)
        name = re.sub(r"[^\w.\-]", "_", name)
        return name


class SelectROIView(View):
    """Step 2: show the uploaded video and let the user draw a ROI rectangle."""
    template_name = "detecter/select_roi.html"

    def get(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)
        video_url = ""
        if job.input_file and os.path.isfile(job.input_file):
            rel = os.path.relpath(job.input_file, settings.MEDIA_ROOT)
            video_url = settings.MEDIA_URL + rel.replace("\\", "/")
        return render(request, self.template_name, {
            "job": job,
            "video_url": video_url,
        })


class StartProcessingView(View):
    """Step 3: receive ROI coords from JS, save them, and launch the pipeline."""

    def post(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)

        # ROI regions arrive as JSON: [{"x1":...,"y1":...,"x2":...,"y2":...}, ...]
        raw = request.POST.get("roi_regions", "[]")
        try:
            regions = json.loads(raw)
            if not isinstance(regions, list):
                regions = []
        except (json.JSONDecodeError, TypeError):
            regions = []

        job.roi_regions = regions
        job.save(update_fields=["roi_regions"])
        run_job(str(job.id))
        return redirect("detecter:status", job_id=job.id)


class StatusView(View):
    template_name = "detecter/status.html"

    def get(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)
        if job.status == ProcessingJob.Status.COMPLETED:
            return redirect("detecter:results", job_id=job.id)

        input_url = ""
        if job.input_file and os.path.isfile(job.input_file):
            rel = os.path.relpath(job.input_file, settings.MEDIA_ROOT)
            input_url = settings.MEDIA_URL + rel.replace("\\", "/")

        return render(request, self.template_name, {
            "job": job,
            "input_video_url": input_url,
        })


class JobStatusAPIView(View):
    """Lightweight JSON endpoint polled by the status page."""

    def get(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)

        return JsonResponse({
            "status": job.status,
            "progress": job.progress,
            "current_frame": job.current_frame,
            "total_frames": job.total_frames,
            "processing_fps": job.processing_fps,
            "total_vehicles": job.total_vehicles,
        })


class ResultsView(View):
    template_name = "detecter/results.html"

    def get(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)

        # Build output video URL
        output_url = ""
        if job.output_file:
            rel_path = os.path.relpath(job.output_file, settings.MEDIA_ROOT)
            output_url = settings.MEDIA_URL + rel_path.replace("\\", "/")

        # Format helper
        def fmt(seconds):
            m, s = divmod(int(seconds), 60)
            return f"{m:02d}:{s:02d}"

        # Build per-vehicle list from stored JSON
        vehicles = []
        vdata = job.vehicle_data or {}
        for tid_str, info in vdata.items():
            vehicles.append({
                "track_id": int(tid_str),
                "class_name": info.get("class_name", "vehicle"),
                "wait_seconds": info.get("wait_seconds", 0),
                "wait_display": fmt(info.get("wait_seconds", 0)),
                "active": info.get("active", False),
            })
        vehicles.sort(key=lambda v: v["wait_seconds"], reverse=True)

        # Duration display
        dur = job.duration_seconds
        duration_display = fmt(dur) if dur else None

        return render(request, self.template_name, {
            "job": job,
            "output_url": output_url,
            "vehicles": vehicles,
            "avg_wait_display": fmt(job.avg_wait_time),
            "max_wait_display": fmt(job.max_wait_time),
            "duration_display": duration_display,
        })


def stream_inference(request, job_id):
    """MJPEG stream — serves live annotated frames from the pipeline thread."""
    job = get_object_or_404(ProcessingJob, id=job_id)
    job_key = str(job.id)

    def generate():
        while True:
            jpeg_bytes = frame_buffer.get_frame(job_key)
            if jpeg_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg_bytes
                    + b"\r\n"
                )
            # Check if job is done
            try:
                current = ProcessingJob.objects.values_list("status", flat=True).get(id=job_id)
                if current in (ProcessingJob.Status.COMPLETED, ProcessingJob.Status.FAILED):
                    break
            except ProcessingJob.DoesNotExist:
                break
            time.sleep(0.1)  # ~10 FPS refresh rate

    response = StreamingHttpResponse(
        generate(),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )
    response["Cache-Control"] = "no-cache"
    return response
