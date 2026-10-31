"""
Drop-in live audio router for iraqi_listener.py.

After your existing `app = FastAPI(...)` and model globals/functions are defined,
add:

    from live_router import build_live_router
    app.include_router(build_live_router(
        whisper_getter=lambda: whisper_model,
        summarize_fn=summarize_transcript,
    ))

Assumptions matching the existing project:
- `whisper_model` is a faster_whisper.WhisperModel instance or None.
- `summarize_transcript(text)` returns a summary string.
- The router transcribes 16-bit mono PCM WAV audio through faster-whisper.
"""
from __future__ import annotations
import asyncio
import io
import json
import wave
from typing import Callable, Optional

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


def _resample_int16(pcm: np.ndarray, source_rate: int, target_rate: int = 16000) -> np.ndarray:
    if source_rate == target_rate or pcm.size == 0:
        return pcm.astype(np.int16, copy=False)
    new_len = max(1, round(len(pcm) * target_rate / source_rate))
    old_x = np.arange(len(pcm), dtype=np.float64)
    new_x = np.linspace(0, len(pcm) - 1, new_len)
    return np.clip(np.interp(new_x, old_x, pcm.astype(np.float32)), -32768, 32767).astype(np.int16)


def _wav_bytes(pcm16: np.ndarray, sample_rate: int = 16000) -> bytes:
    buff = io.BytesIO()
    with wave.open(buff, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.astype("<i2", copy=False).tobytes())
    return buff.getvalue()


def build_live_router(whisper_getter: Callable, summarize_fn: Callable):
    router = APIRouter()
    @router.websocket("/ws/live")
    async def live_audio(websocket: WebSocket):
        await websocket.accept()
        model = whisper_getter()
        if model is None:
            await websocket.send_json({"type": "error", "message": "Whisper model is not loaded."})
            await websocket.close()
            return
        language = "ar"
        sample_rate = 48000
        source = "microphone"
        pcm_parts = []
        total_samples = 0
        session_transcript = []
        last_summary_at = 0
        chunk_seconds = 15
        summary_interval_seconds = 60
        processed_seconds = 0
        stopped = False

        async def transcribe_buffer(final=False):
            nonlocal pcm_parts, total_samples, processed_seconds, last_summary_at
            if not pcm_parts:
                return
            joined = np.concatenate(pcm_parts)
            pcm_parts = []
            total_samples = 0
            pcm16 = _resample_int16(joined, sample_rate)
            if len(pcm16) < 1600:
                return
            processed_seconds += len(pcm16) / 16000
            wav_data = _wav_bytes(pcm16)
            def run_whisper():
                segments, info = model.transcribe(
                    io.BytesIO(wav_data),
                    language=None if language == "auto" else language,
                    vad_filter=True,
                    beam_size=1,
                )
                return [seg.text.strip() for seg in segments if seg.text.strip()]
            try:
                texts = await asyncio.to_thread(run_whisper)
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": f"Whisper: {type(exc).__name__}: {exc}"})
                return
            text = " ".join(texts).strip()
            if text:
                session_transcript.append(text)
                await websocket.send_json({"type": "transcript", "text": text, "source": source})
            joined_text = "\n".join(session_transcript).strip()
            if joined_text and (final or processed_seconds - last_summary_at >= summary_interval_seconds):
                await websocket.send_json({"type": "status", "message": "Updating rolling summary…"})
                try:
                    summary = await asyncio.to_thread(summarize_fn, joined_text)
                    if summary:
                        await websocket.send_json({"type": "summary", "summary": summary})
                    last_summary_at = processed_seconds
                except Exception as exc:
                    await websocket.send_json({"type": "error", "message": f"Summary: {type(exc).__name__}: {exc}"})

        try:
            first = await websocket.receive_text()
            config = json.loads(first)
            if config.get("type") != "start":
                await websocket.send_json({"type": "error", "message": "Send start configuration first."})
                await websocket.close()
                return
            sample_rate = int(config.get("sample_rate", 48000))
            if not 8000 <= sample_rate <= 192000:
                raise ValueError("Unsupported browser sample rate.")
            language = config.get("language", "ar")
            if language not in ("ar", "en", "auto"):
                language = "ar"
            source = config.get("source", "microphone")
            await websocket.send_json({"type": "status", "message": "Live audio connected."})
            while True:
                message = await websocket.receive()
                if message.get("bytes") is not None:
                    raw = message["bytes"]
                    # Browser sends signed 16-bit little-endian mono PCM.
                    chunk = np.frombuffer(raw, dtype="<i2").copy()
                    if chunk.size:
                        pcm_parts.append(chunk)
                        total_samples += len(chunk)
                    if total_samples >= sample_rate * chunk_seconds:
                        await transcribe_buffer()
                elif message.get("text") is not None:
                    control = json.loads(message["text"])
                    if control.get("type") == "stop":
                        await transcribe_buffer(final=True)
                        final_text = "\n".join(session_transcript).strip()
                        await websocket.send_json({
                            "type": "finished",
                            "transcript": final_text,
                        })
                        stopped = True
                        break
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                await websocket.send_json({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass
        finally:
            if not stopped:
                try:
                    await websocket.close()
                except Exception:
                    pass
    return router
