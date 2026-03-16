"""Query engine that aggregates ProcessingJob data for the AI assistant."""

from collections import Counter

from django.db.models import Avg, Max, Sum, Count
from django.utils import timezone

from detecter.models import ProcessingJob


def get_analytics_summary() -> dict:
    """Return a structured summary of all completed processing jobs."""
    completed = ProcessingJob.objects.filter(status=ProcessingJob.Status.COMPLETED)

    if not completed.exists():
        return {"message": "No completed processing jobs found."}

    agg = completed.aggregate(
        total_jobs=Count("id"),
        total_vehicles=Sum("total_vehicles"),
        avg_wait=Avg("avg_wait_time"),
        max_wait=Max("max_wait_time"),
    )

    # Vehicle type breakdown across all jobs
    type_counter = Counter()
    for job in completed.only("vehicle_data"):
        if job.vehicle_data:
            for info in job.vehicle_data.values():
                cls_name = info.get("class_name", "unknown")
                type_counter[cls_name] += 1

    return {
        "total_jobs": agg["total_jobs"],
        "total_vehicles_detected": agg["total_vehicles"] or 0,
        "average_wait_time_sec": round(agg["avg_wait"] or 0, 2),
        "max_wait_time_sec": round(agg["max_wait"] or 0, 2),
        "vehicle_type_counts": dict(type_counter),
    }


def get_job_detail(job_id: str) -> dict | None:
    """Return detailed analytics for a specific job."""
    try:
        job = ProcessingJob.objects.get(pk=job_id, status=ProcessingJob.Status.COMPLETED)
    except ProcessingJob.DoesNotExist:
        return None

    type_counter = Counter()
    wait_times = []
    if job.vehicle_data:
        for info in job.vehicle_data.values():
            type_counter[info.get("class_name", "unknown")] += 1
            wait_times.append(info.get("wait_seconds", 0))

    return {
        "job_id": str(job.id),
        "filename": job.original_filename or str(job.id)[:8],
        "total_vehicles": job.total_vehicles,
        "avg_wait_time_sec": round(job.avg_wait_time, 2),
        "max_wait_time_sec": round(job.max_wait_time, 2),
        "vehicle_type_counts": dict(type_counter),
        "processing_duration_sec": job.duration_seconds,
        "created_at": job.created_at.isoformat(),
    }


def get_recent_jobs_summary(limit: int = 10) -> list[dict]:
    """Return a short summary list of the most recent completed jobs."""
    jobs = ProcessingJob.objects.filter(
        status=ProcessingJob.Status.COMPLETED
    ).order_by("-completed_at")[:limit]

    return [
        {
            "job_id": str(j.id),
            "filename": j.original_filename or str(j.id)[:8],
            "total_vehicles": j.total_vehicles,
            "avg_wait_time_sec": round(j.avg_wait_time, 2),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]
