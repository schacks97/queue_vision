"""
Model export service — converts YOLO .pt files to ONNX or TensorRT format.

Uses Ultralytics' built-in `model.export()` API, which handles:
  - ONNX: opset 12+, dynamic axes, simplification
  - TensorRT (engine): FP16, workspace build via TensorRT C++ runtime
"""
import logging
import os
import threading

from .models import OptimizedModel

logger = logging.getLogger(__name__)


def start_conversion(optimized_model_id: int) -> None:
    """Launch the export in a daemon thread (same pattern as detecter tasks)."""
    t = threading.Thread(
        target=_run_conversion,
        args=(optimized_model_id,),
        daemon=True,
    )
    t.start()


def _run_conversion(optimized_model_id: int) -> None:
    try:
        obj = OptimizedModel.objects.get(pk=optimized_model_id)
    except OptimizedModel.DoesNotExist:
        logger.error("OptimizedModel %s not found", optimized_model_id)
        return

    obj.status = OptimizedModel.Status.PROCESSING
    obj.error_message = ""
    obj.save(update_fields=["status", "error_message"])

    # Validate source file exists
    source = os.path.abspath(obj.source_path)
    if not os.path.isfile(source):
        obj.status = OptimizedModel.Status.FAILED
        obj.error_message = f"Source model not found: {source}"
        obj.save(update_fields=["status", "error_message"])
        logger.error("Source not found: %s", source)
        return

    try:
        from ultralytics import YOLO

        model = YOLO(source)
        fmt = "onnx" if obj.target_format == OptimizedModel.Format.ONNX else "engine"

        logger.info("Exporting %s → %s ...", source, fmt)

        export_kwargs = {"format": fmt}
        if fmt == "engine":
            export_kwargs["half"] = True  # FP16 for TensorRT

        exported_path = model.export(**export_kwargs)

        # Ultralytics returns the path (may be str or pathlib.Path)
        exported_path = str(exported_path) if exported_path else ""

        # Verify the artifact file was actually created
        if not exported_path or not os.path.isfile(exported_path):
            # Fall back to the derived path
            derived = obj.derive_artifact_path()
            if os.path.isfile(derived):
                exported_path = derived
            else:
                raise FileNotFoundError(
                    f"Export returned '{exported_path}' but file does not exist. "
                    f"Derived path '{derived}' also missing."
                )

        obj.artifact_path = os.path.abspath(exported_path)
        obj.status = OptimizedModel.Status.READY
        obj.save(update_fields=["artifact_path", "status"])
        logger.info("Export complete: %s", obj.artifact_path)

    except ImportError as exc:
        msg = f"Missing dependency: {exc}. Install with: pip install ultralytics"
        logger.error(msg)
        obj.status = OptimizedModel.Status.FAILED
        obj.error_message = msg[:2000]
        obj.save(update_fields=["status", "error_message"])
    except Exception as exc:
        logger.exception("Export failed for %s: %s", obj.source_model, exc)
        obj.status = OptimizedModel.Status.FAILED
        obj.error_message = str(exc)[:2000]
        obj.save(update_fields=["status", "error_message"])
