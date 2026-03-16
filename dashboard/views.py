
import json
import os

from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Avg, Max
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from detecter.models import ProcessingJob
from .models import SiteConfig, OptimizedModel
from .services import start_conversion

MODELS_DIR = os.path.join(settings.MEDIA_ROOT, "models")

MODEL_EXTENSIONS = (".pt", ".onnx", ".engine")


def scan_available_models():
    """Scan media/models/ — each sub-folder is a family, model files inside are variants."""
    families = []
    if not os.path.isdir(MODELS_DIR):
        return families
    for folder in sorted(os.listdir(MODELS_DIR)):
        folder_path = os.path.join(MODELS_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        variants = []
        for fname in sorted(os.listdir(folder_path)):
            lower = fname.lower()
            if any(lower.endswith(ext) for ext in MODEL_EXTENSIONS):
                variants.append({"id": fname, "name": fname})
        families.append({"id": folder, "name": folder, "variants": variants})
    return families

# COCO vehicle classes — id, name, enabled by default
DETECTION_OBJECTS = [
    {"id": 2, "name": "Car", "enabled": True},
    {"id": 3, "name": "Motorcycle", "enabled": True},
    {"id": 5, "name": "Bus", "enabled": True},
    {"id": 7, "name": "Truck", "enabled": True},
]


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard view showing system analytics and configuration."""
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        completed = ProcessingJob.objects.filter(status=ProcessingJob.Status.COMPLETED)
        agg = completed.aggregate(
            total_vehicles=Sum("total_vehicles"),
            avg_wait=Avg("avg_wait_time"),
            max_wait=Max("max_wait_time"),
        )

        total_videos = completed.count()
        total_vehicles = agg["total_vehicles"] or 0
        avg_wait_raw = agg["avg_wait"] or 0.0

        # Highest congestion = job with the most vehicles
        top_job = completed.order_by("-total_vehicles").first()
        highest_congestion = top_job.original_filename if top_job else "—"

        def fmt(seconds):
            m, s = divmod(int(seconds), 60)
            return f"{m:02d}:{s:02d}"

        # ── Block 1: Analytics summary
        context["analytics"] = {
            "total_videos": total_videos,
            "total_vehicles": total_vehicles,
            "avg_wait_display": fmt(avg_wait_raw),
            "highest_congestion": highest_congestion,
        }

        # ── Block 2: Model configuration
        site_cfg = SiteConfig.load()
        available_models = scan_available_models()
        context["model_config"] = {
            "current_model": site_cfg.detecter_model,
            "available_models": available_models,
        }

        # ── Block 3: Input configuration
        context["input_config"] = {
            "input_size": "1280×720",
            "output_size": "1280×720",
            "confidence": site_cfg.detecter_confidence,
        }

        # ── Block 4: Object selection
        saved_classes = set(site_cfg.detection_classes or [2, 3, 5, 7])
        detection_objects = [
            {**obj, "enabled": obj["id"] in saved_classes}
            for obj in DETECTION_OBJECTS
        ]
        context["detection_objects"] = detection_objects

        return context


@method_decorator(csrf_protect, name="dispatch")
class SaveConfigView(LoginRequiredMixin, View):
    """AJAX endpoint to persist dashboard configuration."""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        site_cfg = SiteConfig.load()

        if "detecter_model" in data:
            site_cfg.detecter_model = str(data["detecter_model"])[:100]
        if "detecter_confidence" in data:
            try:
                conf = float(data["detecter_confidence"])
                if 0.0 < conf <= 1.0:
                    site_cfg.detecter_confidence = round(conf, 2)
            except (ValueError, TypeError):
                pass

        if "detection_classes" in data:
            raw_classes = data["detection_classes"]
            if isinstance(raw_classes, list):
                valid = [int(c) for c in raw_classes if isinstance(c, (int, float))]
                site_cfg.detection_classes = valid

        site_cfg.save()
        return JsonResponse({"ok": True, "model": site_cfg.detecter_model})


# ═══════════════════════════════════════════════════════════════
#  Model Optimization Page
# ═══════════════════════════════════════════════════════════════


class ModelOptimizationView(LoginRequiredMixin, TemplateView):
    """Page for selecting a model and converting to ONNX / TensorRT."""
    template_name = "dashboard/model_optimization.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["available_models"] = scan_available_models()
        context["artifacts"] = OptimizedModel.objects.all()
        context["current_model"] = SiteConfig.load().detecter_model
        return context


@method_decorator(csrf_protect, name="dispatch")
class StartConversionView(LoginRequiredMixin, View):
    """AJAX: create an OptimizedModel record and kick off conversion."""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        source_model = str(data.get("source_model", "")).strip()
        target_format = str(data.get("target_format", "")).strip()

        if not source_model:
            return JsonResponse({"error": "source_model is required"}, status=400)
        if target_format not in ("onnx", "tensorrt"):
            return JsonResponse({"error": "target_format must be onnx or tensorrt"}, status=400)

        # Strip known extensions so the DB key is always the base name (e.g. "yolov8n")
        base_name = source_model
        for ext in (".pt", ".onnx", ".engine"):
            if base_name.lower().endswith(ext):
                base_name = base_name[: -len(ext)]
                break

        # Resolve .pt file path (conversion always starts from the .pt source)
        model_file = base_name + ".pt"
        source_path = ""
        if os.path.isdir(MODELS_DIR):
            for family_folder in sorted(os.listdir(MODELS_DIR)):
                candidate = os.path.join(MODELS_DIR, family_folder, model_file)
                if os.path.isfile(candidate):
                    source_path = os.path.abspath(candidate)
                    break

        if not source_path:
            return JsonResponse({"error": f"Model file not found: {model_file}"}, status=404)

        # Upsert: one record per (model, format)
        obj, created = OptimizedModel.objects.update_or_create(
            source_model=base_name,
            target_format=target_format,
            defaults={
                "source_path": source_path,
                "status": OptimizedModel.Status.PENDING,
                "error_message": "",
            },
        )
        # Derive artifact path fresh
        obj.artifact_path = obj.derive_artifact_path()
        obj.save(update_fields=["artifact_path"])

        start_conversion(obj.pk)

        return JsonResponse({
            "ok": True,
            "id": obj.pk,
            "artifact_path": obj.artifact_path,
            "created": created,
        })


class ArtifactStatusView(LoginRequiredMixin, View):
    """AJAX: poll conversion status."""

    def get(self, request, pk):
        try:
            obj = OptimizedModel.objects.get(pk=pk)
        except OptimizedModel.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        return JsonResponse({
            "id": obj.pk,
            "status": obj.status,
            "error_message": obj.error_message,
            "artifact_path": obj.artifact_path,
            "artifact_exists": obj.artifact_exists(),
            "is_active": obj.is_active,
            "source_model": obj.source_model,
            "format": obj.target_format,
        })

