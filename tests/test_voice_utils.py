import voice_utils


def test_transcribe_audio_rejects_empty_audio():
    assert "empty audio input" in voice_utils.transcribe_audio(b"")


def test_transcribe_audio_requires_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = voice_utils.transcribe_audio(b"not-really-audio")

    assert "GROQ_API_KEY" in result
