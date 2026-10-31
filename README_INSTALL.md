# Voice Intelligence Web Application

This is a browser UI plus a drop-in FastAPI WebSocket router for your existing
`voice_summrizer` project. It supports:

1. Audio file upload through your existing `POST /transcribe`.
2. Live microphone capture.
3. Browser-tab audio capture (Google Meet / browser Discord) using the browser's
   screen/tab sharing dialog and the **Share tab audio** option.
4. Rolling summary refreshes approximately once per minute, plus a final refresh
   when the user stops.

## Important compatibility note

The existing GitHub server file was not available to inspect from this build
environment. The integration below is based on the project structure previously
shared: `app`, `whisper_model`, and `summarize_transcript`. Check those exact
names in `iraqi_listener.py` before adding the router.

## 1. Copy the files

Copy the `web` directory into the same directory as `iraqi_listener.py`.
Copy `live_router.py` beside `iraqi_listener.py`.

## 2. Install the additional dependency

In the same Python environment as your API:

```powershell
pip install numpy
```

FastAPI, faster-whisper and Uvicorn are already required by your server.

## 3. Add the router to iraqi_listener.py

After `app` is created and after the existing `whisper_model` global and
`summarize_transcript` function are defined, add:

```python
from fastapi.staticfiles import StaticFiles
from live_router import build_live_router

app.include_router(
    build_live_router(
        whisper_getter=lambda: whisper_model,
        summarize_fn=summarize_transcript,
    )
)

app.mount("/web", StaticFiles(directory="web"), name="web")
```

If your app already mounts `/web`, do not mount it twice. The router must be
included after the existing model globals/functions are available.

The router assumes `whisper_model.transcribe(...)` accepts a WAV file-like
object. If your faster-whisper version requires a filesystem path, tell me the
error and I can adapt it to your installed version.

## 4. Serve the page at /

Add this route to `iraqi_listener.py`:

```python
from fastapi.responses import FileResponse

@app.get("/", include_in_schema=False)
def voice_intelligence_home():
    return FileResponse("web/index.html")
```

If you already have a `/` route, update that route instead.

## 5. Run

From the project directory:

```powershell
uvicorn iraqi_listener:app --host 0.0.0.0 --port 8000
```

Open on the server computer:
`http://127.0.0.1:8000/`

From another computer on your LAN:
`http://SERVER-IP:8000/`

For microphone and tab capture, browsers require a secure context. `localhost`
works over HTTP. For another computer, use HTTPS (for example, a local
reverse proxy with a trusted certificate); plain HTTP LAN access may block
`getUserMedia()` and `getDisplayMedia()`.

## 6. How live processing works

The browser captures audio with Web Audio, converts it to 16-bit mono PCM, and
sends five-second packets over `/ws/live`. The server buffers approximately
15 seconds, then asks faster-whisper to transcribe the buffer. Every ~60 seconds
of processed audio, it calls your existing `summarize_transcript()` on the
session transcript. Stopping sends the remaining audio and requests a final
summary.

## 7. Meeting capture limitations

- The user must select the meeting tab and explicitly enable tab audio sharing.
- The capture is audio only; it does not join meetings, bypass permissions, or
  capture audio from tabs that the browser does not share.
- Desktop Discord is not captured by browser tab sharing. Use Discord in a
  browser or a separate desktop audio-capture helper.
- Browser audio capture is subject to browser support and OS/browser policies.
- Notify participants and obtain any required consent before recording.

## 8. CPU and accuracy notes

This is near-live, chunked transcription, not word-by-word streaming. A 15-second
buffer reduces very short utterance fragmentation. On CPU, large-v3 may take
longer than the audio duration, so transcript updates can lag. Qwen3-32B
summarization every minute can be expensive; increase `summary_interval_seconds`
to 120 or 180 in `live_router.py` if needed.

The app is experimental. Review the transcript and summary against the original
audio, especially names, numbers, medical information, and decisions.

## 9. Security before exposing outside your LAN

Do not expose this development server directly to the public internet. Add
authentication, TLS, upload limits, rate limiting, session isolation, and a
retention/deletion policy first. This initial version is intended for a trusted
local network.
