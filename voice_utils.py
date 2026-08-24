"""Voice transcription helpers."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

TRANSCRIPTION_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
TRANSCRIPTION_ERROR_PREFIX = "[Transcription error:"


def transcription_succeeded(transcript: str) -> bool:
    """Return true when Groq returned usable transcript text."""
    return bool(transcript and not transcript.startswith(TRANSCRIPTION_ERROR_PREFIX))


def transcribe_audio(audio_bytes: bytes, filename: str = "question.wav") -> str:
    """Transcribe a recorded question with Groq Whisper."""
    if not audio_bytes:
        return "[Transcription error: empty audio input]"
    if not os.getenv("GROQ_API_KEY"):
        return "[Transcription error: set GROQ_API_KEY in .env]"

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=TRANSCRIPTION_MODEL,
            response_format="text",
        )
        return str(transcription).strip()
    except Exception as exc:
        return f"[Transcription error: {exc}]"
