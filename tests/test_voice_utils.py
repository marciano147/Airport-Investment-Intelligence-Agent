import voice_utils


def test_transcribe_audio_rejects_empty_audio():
    assert "empty audio input" in voice_utils.transcribe_audio(b"")


def test_transcribe_audio_requires_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = voice_utils.transcribe_audio(b"not-really-audio")

    assert "GROQ_API_KEY" in result


def test_transcribe_audio_returns_mocked_transcript(monkeypatch):
    class Transcriptions:
        def create(self, **kwargs):
            assert kwargs["model"] == voice_utils.TRANSCRIPTION_MODEL
            assert kwargs["response_format"] == "text"
            return "rank California airports"

    class Audio:
        transcriptions = Transcriptions()

    class Client:
        audio = Audio()

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("voice_utils.Groq", lambda api_key: Client())

    result = voice_utils.transcribe_audio(b"audio-bytes")

    assert result == "rank California airports"


def test_transcribe_audio_returns_visible_error_on_groq_failure(monkeypatch):
    class Transcriptions:
        def create(self, **kwargs):
            raise RuntimeError("service unavailable")

    class Audio:
        transcriptions = Transcriptions()

    class Client:
        audio = Audio()

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("voice_utils.Groq", lambda api_key: Client())

    result = voice_utils.transcribe_audio(b"audio-bytes")

    assert result == "[Transcription error: service unavailable]"


def test_transcription_succeeded_distinguishes_text_from_error():
    assert voice_utils.transcription_succeeded("Hello, error error.")
    assert not voice_utils.transcription_succeeded("")
    assert not voice_utils.transcription_succeeded("[Transcription error: bad audio]")
