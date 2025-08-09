import io
import os
import pickle
import threading
from typing import Optional, List

import torch
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image

from process_json_images_improved import (
    train_classifier as _train_classifier,
    classify_image as _classify_image,
    model as _clip_model,
    preprocess as _clip_preprocess,
    device as _clip_device,
)


MODEL_PATH = "trained_classifier.pkl"

app = FastAPI(title="Zenyum AI POC API", version="1.0.0")

_classifier_lock = threading.Lock()
_classifier = None

_clip_text_lock = threading.Lock()
_clip_text_embs = None  # torch.Tensor [num_classes, dim]
_clip_labels: List[str] = ["Frontal", "Left", "Right", "Upper", "Lower"]


def _ensure_clip_text_embeddings() -> torch.Tensor:
    global _clip_text_embs
    if _clip_text_embs is not None:
        return _clip_text_embs

    import clip as _clip
    with _clip_text_lock:
        if _clip_text_embs is not None:
            return _clip_text_embs

        templates = [
            "a dental {label} view photo",
            "a clinical {label} intraoral image",
            "a {label} occlusal view",
            "a photo of {label} teeth view",
        ]

        with torch.no_grad():
            label_text_embs = []
            for label in _clip_labels:
                prompts = [t.format(label=label) for t in temp lates]
                tokens = _clip.tokenize(prompts).to(_clip_device)
                te = _clip_model.encode_text(tokens)
                te = te / te.norm(dim=-1, keepdim=True)
                label_text_embs.append(te.mean(dim=0))

            _clip_text_embs = torch.stack(label_text_embs)
            _clip_text_embs = _clip_text_embs / _clip_text_embs.norm(dim=-1, keepdim=True)

        return _clip_text_embs


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


@app.post("/classify_clip")
async def classify_clip(file: UploadFile = File(...)) -> JSONResponse:
    if file.content_type is None or not any(
        file.content_type.lower().endswith(ct) for ct in ["jpeg", "jpg", "png"]
    ):
        if not (file.filename and file.filename.lower().endswith((".jpg", ".jpeg", ".png"))):
            raise HTTPException(status_code=400, detail="Please upload a JPEG or PNG image")

    text_embs = _ensure_clip_text_embeddings()

    image_bytes = await file.read()
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    try:
        img = _clip_preprocess(image).unsqueeze(0).to(_clip_device)
        with torch.no_grad():
            im = _clip_model.encode_image(img)
            im = im / im.norm(dim=-1, keepdim=True)
            logits = (im @ text_embs.T).squeeze(0)
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
        pred_idx = int(probs.argmax())
        prediction = _clip_labels[pred_idx]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLIP classification failed: {e}")

    return JSONResponse({"prediction": prediction})

