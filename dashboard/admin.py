from django.contrib import admin

from .models import SiteConfig, OptimizedModel


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ("detecter_model", "detecter_confidence")
    fieldsets = (
        ("Model", {
            "fields": ("detecter_model", "detecter_confidence"),
        }),
        ("Detection", {
            "fields": ("detection_classes",),
            "description": "COCO class IDs to detect (e.g. [2, 3, 5, 7])",
        }),
    )


@admin.register(OptimizedModel)
class OptimizedModelAdmin(admin.ModelAdmin):
    list_display = ("source_model", "target_format", "status", "is_active", "created_at")
    list_filter = ("target_format", "status", "is_active")
    readonly_fields = ("artifact_path", "created_at", "updated_at")

