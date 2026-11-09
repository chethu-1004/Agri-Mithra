from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from agrinetra.auth.dependencies import get_current_user
from agrinetra.config import settings
from agrinetra.database.connection import get_db
from agrinetra.database.models import DiseaseScan, User, new_id
from agrinetra.species_detection.predictor import predictor
from agrinetra.disease_detection.model_loader import ModelUnavailable, predictor as disease_predictor
from agrinetra.services.plant_analysis import build_species_analysis
from agrinetra.storage.service import save_image
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/species", tags=["species detection"])


@router.post("/predict")
async def predict_species(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid image type. Use JPG, PNG or WEBP.")

    image_path, storage_key = await save_image(file)
    scan_id = new_id()
    try:
        result = predictor.predict(image_path)
        human_detected = result.get("human_detected") is True or result.get("analysis_type") == "human"
        predicted_class = str(result.get("predicted_class") or result.get("species") or "Not identified")
        confidence = result.get("confidence")
        status = "NON_CROP" if human_detected else (
            "SUCCESS" if confidence is not None and confidence >= settings.prediction_threshold else "UNCERTAIN"
        )

        disease_result = None
        disease_status = "not_configured"
        if not human_detected:
            try:
                disease_label, disease_confidence = disease_predictor.predict(image_path)
                disease_status = "available"
                disease_result = {
                    "name": str(disease_label).replace("___", " — ").replace("_", " "),
                    "confidence": disease_confidence,
                    "status": "SUCCESS" if disease_confidence >= settings.prediction_threshold else "UNCERTAIN",
                }
            except ModelUnavailable:
                disease_status = "not_configured"
            except Exception:
                logger.exception("Optional disease model failed during species analysis")
                disease_status = "analysis_unavailable"

        analysis = build_species_analysis(
            result,
            disease_result=disease_result,
            disease_status=disease_status,
            prediction_status=status,
        )
        scan = DiseaseScan(
            id=scan_id,
            user_id=user.id,
            image_url=f"/api/disease/history/{scan_id}/image",
            image_storage_key=storage_key,
            predicted_disease="Human detected" if human_detected else str(result.get("species") or predicted_class),
            predicted_class=predicted_class,
            confidence=float(confidence) if confidence is not None else 0.0,
            model_version=settings.model_version,
            status=status,
        )
        db.add(scan)
        db.commit()
        result["scan_id"] = scan_id
        result.setdefault("model", "Agri Mitra species classifier")
        # Report the server's threshold decision so every frontend stays in sync
        # even if its locally configured threshold differs from the API setting.
        result.setdefault("status", status)
        result.setdefault("is_confident", status == "SUCCESS")
        result["analysis"] = analysis
        return {"status": "success", "scan_id": scan_id, "prediction": result}
    except Exception as exc:
        db.rollback()
        Path(image_path).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc))
