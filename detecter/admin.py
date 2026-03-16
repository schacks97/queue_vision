from django.contrib import admin

from .models import ProcessingJob


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "status", "total_vehicles", "avg_wait_time", "max_wait_time", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("original_filename", "input_url", "id")
    readonly_fields = (
        "id", "created_at", "started_at", "completed_at",
        "progress", "current_frame", "total_frames", "processing_fps",
        "total_vehicles", "avg_wait_time", "max_wait_time", "max_wait_vehicle_id",
        "vehicle_data", "roi_regions",
    )
    fieldsets = (
        ("Job", {
            "fields": ("id", "status", "error_message"),
        }),
        ("Input", {
            "fields": ("original_filename", "input_file", "input_url"),
        }),
        ("Output", {
            "fields": ("output_file", "roi_regions"),
        }),
        ("Progress", {
            "fields": ("progress", "current_frame", "total_frames", "processing_fps"),
        }),
        ("Results", {
            "fields": ("total_vehicles", "avg_wait_time", "max_wait_time", "max_wait_vehicle_id", "vehicle_data"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "started_at", "completed_at"),
            "classes": ("collapse",),
        }),
    )
    ordering = ("-created_at",)
