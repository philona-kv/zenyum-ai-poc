## Zenyum AI POC — Image Classification Service

This repository exposes a FastAPI service to:

- Train a classifier from existing labeled images on disk
- Classify uploaded images without retraining each time

Under the hood it uses CLIP embeddings + Logistic Regression. Training pulls data from the `output/` directory (same structure your script generates). The trained model is saved to `trained_classifier.pkl` and reused by the classify API.

### Prerequisites

- Python 3.12
- (Optional) CUDA-capable GPU and drivers for faster inference/training

### Setup

```bash
# 1) Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3) Start the API server
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open the interactive API docs at `http://localhost:8000/docs`.

### Directory Layout Expectations

- Training reads from the `output/` directory with the following structure (created by your processing scripts):

```
output/
  {CASE_NAME}/
    preTreatment/
      Frontal/
      Left/
      Lower/
      Right/
      Upper/
    postTreatment/
      Frontal/
      Left/
      Lower/
      Right/
      Upper/
```

- If `output/` is missing or empty, the code falls back to `labeled_samples/` with subfolders per class.

### API Reference

- GET `/health`
  - Returns service status and whether a trained model file is present.

- POST `/train`
  - No body. Trains from the current `output/` directory (or falls back to `labeled_samples/`), saves model to `trained_classifier.pkl`, and caches it in memory.

- POST `/classify`
  - Multipart form upload with one file under the `file` field (JPEG/PNG).
  - Uses the saved model; does NOT retrain. If no model exists, returns an error asking to call `/train` first.
  - Note: As requested, API output complements mislabels for side views — if the model predicts "Left", the API responds with "Right", and vice versa.

### curl Examples

```bash
# Train (reads from ./output)
curl -X POST http://localhost:8000/train

# Classify an image
curl -X POST http://localhost:8000/classify \
  -F "file=@/home/philona/Documents/zenyum-ai-poc/fileInput/your_image.jpg"

# Health check
curl http://localhost:8000/health
```

### Postman Instructions

1. Start the server: `uvicorn server:app --host 0.0.0.0 --port 8000`
2. (Optional) POST `http://localhost:8000/train` — trains from `output/`
3. POST `http://localhost:8000/classify`
   - Body → form-data
   - Key: `file` (type = File)
   - Choose a .jpg/.jpeg/.png
   - Send

### Model Lifecycle

- Trained model: `trained_classifier.pkl`
- Metadata: `model_metadata.json`
- Both are ignored by git (see `.gitignore`).
- Classification does not retrain; call `/train` whenever you update/add training data under `output/`.

### GPU vs CPU

- If CUDA is available, CLIP runs on GPU automatically; otherwise falls back to CPU.
- First CLIP model load will download weights (~300MB+), so the initial run can take longer.

### Troubleshooting

- `Form data requires "python-multipart" to be installed`
  - Run: `pip install python-multipart` (already in `requirements.txt`).

- `Model not trained yet. Call /train first.` on `/classify`
  - Call `POST /train` once. Ensure `output/` has the expected folder structure or provide `labeled_samples/` fallback.

- Port already in use
  - Use another port: `uvicorn server:app --host 0.0.0.0 --port 8080`

- Slow training
  - Training runs through all images and augmentations; expect minutes on CPU. Use GPU for speed-ups.

### Dev Notes

- Core logic lives in `process_json_images_improved.py`.
- The API lives in `server.py` and imports the training/classification utilities.

