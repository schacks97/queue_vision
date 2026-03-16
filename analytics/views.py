import csv
import io
import os

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from detecter.models import ProcessingJob


def _fmt(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _video_url(job):
    if job.output_file and os.path.isfile(job.output_file):
        rel = os.path.relpath(job.output_file, settings.MEDIA_ROOT)
        return settings.MEDIA_URL + rel.replace("\\", "/")
    return ""


class AnalyticsOverviewView(LoginRequiredMixin, View):
    """Page 1 — grid of cards for every completed video."""

    template_name = "analytics/overview.html"

    def get(self, request):
        jobs = ProcessingJob.objects.filter(status=ProcessingJob.Status.COMPLETED)

        cards = []
        for job in jobs:
            vdata = job.vehicle_data or {}
            # Peak congestion = total unique vehicles (simple proxy)
            peak = job.total_vehicles
            cards.append({
                "job": job,
                "video_name": job.original_filename or str(job.id)[:8],
                "total_vehicles": job.total_vehicles,
                "avg_wait_display": _fmt(job.avg_wait_time),
                "peak_congestion": peak,
                "output_url": _video_url(job),
            })

        return render(request, self.template_name, {"cards": cards})


class VideoDetailAnalyticsView(LoginRequiredMixin, View):
    """Page 2 — detailed analytics for one video."""

    template_name = "analytics/detail.html"

    def get(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)

        vdata = job.vehicle_data or {}

        # Per-vehicle list
        vehicles = []
        class_counts = {}
        for tid_str, info in vdata.items():
            cls = info.get("class_name", "vehicle")
            wt = info.get("wait_seconds", 0)
            vehicles.append({
                "track_id": int(tid_str),
                "class_name": cls,
                "wait_seconds": wt,
                "wait_display": _fmt(wt),
                "active": info.get("active", False),
            })
            class_counts[cls] = class_counts.get(cls, 0) + 1

        vehicles.sort(key=lambda v: v["wait_seconds"], reverse=True)

        # Congestion over time buckets (30-second intervals)
        bucket_size = 30
        time_buckets = {}
        for info in vdata.values():
            wt = info.get("wait_seconds", 0)
            bucket = int(wt // bucket_size) * bucket_size
            time_buckets[bucket] = time_buckets.get(bucket, 0) + 1

        if time_buckets:
            max_t = max(time_buckets.keys())
            timeline_labels = list(range(0, max_t + bucket_size, bucket_size))
            timeline_values = [time_buckets.get(t, 0) for t in timeline_labels]
            timeline_labels = [f"{t}s" for t in timeline_labels]
        else:
            timeline_labels = ["0s"]
            timeline_values = [0]

        # Class distribution for chart
        class_labels = list(class_counts.keys())
        class_values = list(class_counts.values())

        return render(request, self.template_name, {
            "job": job,
            "output_url": _video_url(job),
            "vehicles": vehicles,
            "total_vehicles": job.total_vehicles,
            "avg_wait_display": _fmt(job.avg_wait_time),
            "max_wait_display": _fmt(job.max_wait_time),
            "peak_congestion": job.total_vehicles,
            "class_labels": class_labels,
            "class_values": class_values,
            "timeline_labels": timeline_labels,
            "timeline_values": timeline_values,
        })


class DownloadCSVView(LoginRequiredMixin, View):
    """Stream a CSV file for a completed job's vehicle data."""

    def get(self, request, job_id):
        job = get_object_or_404(ProcessingJob, id=job_id)
        vdata = job.vehicle_data or {}

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["#", "Track ID", "Class", "Wait Time", "Seconds", "Status"])

        rows = []
        for tid_str, info in vdata.items():
            rows.append({
                "tid": int(tid_str),
                "cls": info.get("class_name", "vehicle"),
                "wt": info.get("wait_seconds", 0),
                "active": info.get("active", False),
            })
        rows.sort(key=lambda r: r["wt"], reverse=True)

        for i, r in enumerate(rows, 1):
            writer.writerow([
                i,
                r["tid"],
                r["cls"],
                _fmt(r["wt"]),
                f"{r['wt']:.1f}s",
                "In ROI" if r["active"] else "Exited",
            ])

        filename = (job.original_filename or str(job.id)[:8]).rsplit(".", 1)[0]
        response = HttpResponse(buf.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}_analytics.csv"'
        return response
