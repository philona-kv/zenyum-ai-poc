import io
import os
import pickle
import threading
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image

from process_json_images_improved import (
    train_classifier as _train_classifier,
    classify_image as _classify_image,
)


MODEL_PATH = "trained_classifier.pkl"

app = FastAPI(title="Zenyum AI POC API", version="1.0.0")

_classifier_lock = threading.Lock()
_classifier = None


def _load_classifier_from_disk() -> Optional[object]:
    global _classifier
    if _classifier is not None:
        return _classifier
    if not os.path.exists(MODEL_PATH):
        return None
    with open(MODEL_PATH, "rb") as f:
        _classifier = pickle.load(f)
    return _classifier


def _save_classifier_to_disk(classifier: object) -> None:
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(classifier, f)


@app.get("/health")
def health() -> JSONResponse:
    has_model = os.path.exists(MODEL_PATH)
    return JSONResponse({"status": "ok", "model_present": has_model})


@app.post("/train")
def train() -> JSONResponse:
    with _classifier_lock:
        classifier = _train_classifier()
        if classifier is None:
            raise HTTPException(status_code=400, detail="Failed to train classifier (no training data found)")
        _save_classifier_to_disk(classifier)
        global _classifier
        _classifier = classifier
    classes = [str(c) for c in getattr(classifier, "classes_", [])]
    return JSONResponse({"status": "trained", "num_classes": len(classes), "classes": classes})


@app.post("/classify")
async def classify(file: UploadFile = File(...)) -> JSONResponse:
    if file.content_type is None or not any(
        file.content_type.lower().endswith(ct) for ct in ["jpeg", "jpg", "png"]
    ):
        if not (file.filename and file.filename.lower().endswith((".jpg", ".jpeg", ".png"))):
            raise HTTPException(status_code=400, detail="Please upload a JPEG or PNG image")

    with _classifier_lock:
        classifier = _load_classifier_from_disk()

    if classifier is None:
        raise HTTPException(status_code=400, detail="Model not trained yet. Call /train first.")

    image_bytes = await file.read()
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    try:
        predicted_label = _classify_image(classifier, image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")

    label_str = str(predicted_label).strip()
    lower = label_str.lower()
    if lower == "left":
        final_label = "Right"
    elif lower == "right":
        final_label = "Left"
    else:
        final_label = label_str

    return JSONResponse({"prediction": final_label})

