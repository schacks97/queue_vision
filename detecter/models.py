import uuid

from django.db import models


class ProcessingJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Input
    input_file = models.CharField(max_length=500, blank=True, default="")
    input_url = models.URLField(blank=True, default="")
    original_filename = models.CharField(max_length=255, blank=True, default="")

    # Output
    output_file = models.CharField(max_length=500, blank=True, default="")

    # ROI (list of rectangular regions drawn by user, pixel coords)
    roi_regions = models.JSONField(default=list, blank=True)

    # Progress
    progress = models.PositiveIntegerField(default=0)  # 0-100
    current_frame = models.PositiveIntegerField(default=0)
    total_frames = models.PositiveIntegerField(default=0)
    processing_fps = models.FloatField(default=0.0)

    # Results
    total_vehicles = models.PositiveIntegerField(default=0)
    avg_wait_time = models.FloatField(default=0.0)
    max_wait_time = models.FloatField(default=0.0)
    max_wait_vehicle_id = models.IntegerField(null=True, blank=True)
    vehicle_data = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Error
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        name = self.original_filename or self.input_url or str(self.id)[:8]
        return f"Job {name} [{self.status}]"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
