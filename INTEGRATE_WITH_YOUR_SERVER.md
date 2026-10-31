# Integration with `hussein1-1almos/voice_summrizer`

I reviewed the public `iraqi_listener.py`. Its relevant globals/functions are:
- `app`
- `whisper_model`
- `whisper_lock`
- `summarize_transcript`
- `/transcribe` and `/health` already exist

Do not create another FastAPI app or another model instance.

## 1. Copy these files

Copy `live_router.py` into the same directory as `iraqi_listener.py`, and copy the `web/` directory beside it.

## 2. Append this at the VERY END of `iraqi_listener.py`

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from live_router import build_live_router

app.include_router(
    build_live_router(
        whisper_getter=lambda: whisper_model,
        summarize_fn=summarize_transcript,
        whisper_lock=whisper_lock,
    )
)

app.mount("/web", StaticFiles(directory="web"), name="web")

@app.get("/", include_in_schema=False)
def web_home():
    return FileResponse("web/index.html")
```

This is an addition to the existing `app`; do not replace its `FastAPI(...)` creation or lifespan.

## 3. Dependencies

Your GitHub `requirements.txt` lists FastAPI, Uvicorn, faster-whisper, python-multipart, and onnxruntime. The live router also needs NumPy (normally installed transitively, but ensure it is present):

```bash
pip install numpy
```

Keep your working torch/transformers installation for Qwen. Do not create a second model process.

## 4. Run a syntax/import check

From the server project directory and with its existing venv activated:

```bash
python -m py_compile iraqi_listener.py live_router.py
```

Then start using the normal command you already use. Check:
- `GET /health` still reports both models loaded
- `GET /` serves the web page
- `GET /docs` still works
- Upload still uses the original `/transcribe`
- Live recording connects to `/ws/live`

The live router uses a NumPy float32 waveform for faster-whisper and your existing `whisper_lock`. Your `summarize_transcript()` already serializes Qwen inference with `summary_lock`, so it is called directly without acquiring that lock a second time.

## Note on deployment service

The deployment systemd unit in `deploy/voice-summrizer.service` creates a new `.venv` path. Your current repo already has `~/whisper/venv`. Either:
- change `ExecStart` to `/opt/voice_summrizer/venv/bin/uvicorn ...` and copy the existing venv only if its absolute paths remain valid (usually they do not after moving); or
- preferably create `/opt/voice_summrizer/.venv` and install the same pinned packages into it, including the existing compatible torch/transformers versions and model dependencies.

Do not run two Uvicorn services against the same CPU models.
