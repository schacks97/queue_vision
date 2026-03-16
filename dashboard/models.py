import os

from django.db import models


class SiteConfig(models.Model):
    """Singleton model storing dashboard configuration."""
    detecter_model = models.CharField(max_length=100, default="yolov8s")
    detecter_confidence = models.FloatField(default=0.3)
    detection_classes = models.JSONField(default=list, blank=True,
                                         help_text="COCO class IDs to detect, e.g. [2,3,5,7]")

    class Meta:
        verbose_name = "Site Configuration"

    def __str__(self):
        return f"SiteConfig (model={self.detecter_model})"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"detection_classes": [2, 3, 5, 7]},
        )
        return obj


class OptimizedModel(models.Model):
    """Tracks ONNX / TensorRT exports of YOLO .pt models."""

    class Format(models.TextChoices):
        ONNX = "onnx", "ONNX"
        TENSORRT = "tensorrt", "TensorRT"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    source_model = models.CharField(
        max_length=200,
        help_text="Name of the base .pt model, e.g. yolov8s",
    )
    source_path = models.CharField(
        max_length=500,
        help_text="Absolute path to the source .pt file",
    )
    target_format = models.CharField(
        max_length=20, choices=Format.choices,
    )
    artifact_path = models.CharField(
        max_length=500, blank=True, default="",
        help_text="Derived automatically from source path",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING,
    )
    error_message = models.TextField(blank=True, default="")
    is_active = models.BooleanField(
        default=False,
        help_text="If True, the pipeline uses this artifact instead of the .pt file",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Optimized Model"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_model", "target_format"],
                name="unique_model_format",
            ),
        ]

    def __str__(self):
        return f"{self.source_model}.{self.get_extension()} ({self.get_status_display()})"

    def get_extension(self):
        return "onnx" if self.target_format == self.Format.ONNX else "engine"

    def derive_artifact_path(self):
        """Build the output path by replacing the .pt extension."""
        base, _ = os.path.splitext(self.source_path)
        return f"{base}.{self.get_extension()}"

    def artifact_exists(self):
        return bool(self.artifact_path) and os.path.isfile(self.artifact_path)

    def save(self, *args, **kwargs):
        if not self.artifact_path and self.source_path:
            self.artifact_path = self.derive_artifact_path()
        # Only one active artifact per model allowed
        if self.is_active:
            OptimizedModel.objects.filter(
                source_model=self.source_model, is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
