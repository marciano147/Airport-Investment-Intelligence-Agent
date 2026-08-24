from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_app_renders_core_chat_controls(monkeypatch, tmp_path):
    monkeypatch.setattr("chat_store.DB_PATH", tmp_path / "chat_history.db")

    app = AppTest.from_file(APP_PATH).run(timeout=5)

    assert not app.exception
    assert app.title[0].value == "Airport Investment Intelligence Agent"
    assert "Powered by Groq" in app.caption[0].value
    assert any(button.label == "New Conversation" for button in app.button)
    assert any("New England" in button.label for button in app.button)
    assert any("Voice Input" in subheader.value for subheader in app.subheader)
    assert app.chat_input[0].placeholder == "Ask about airport investment opportunities..."


def test_voice_transcript_path_does_not_force_immediate_rerun():
    source = APP_PATH.read_text(encoding="utf-8")

    risky_pattern = '_queue_user_message(transcript)\n                st.rerun()'

    assert risky_pattern not in source


def test_voice_input_uses_dedicated_recorder_and_button():
    source = APP_PATH.read_text(encoding="utf-8")

    # Native Streamlit recorder caused the browser-side completion error.
    assert "st.audio_input(" not in source

    # Dedicated recorder should be used instead.
    assert "from streamlit_mic_recorder import mic_recorder" in source
    assert "mic_recorder(" in source

    # WAV is sent directly to the existing Whisper pipeline.
    assert 'format="wav"' in source
    assert 'filename="question.wav"' in source

    # Recording and submission remain separate actions.
    assert 'st.button(' in source
    assert '"Send Voice"' in source

    # Existing voice diagnostics/reset lifecycle remain enabled.
    assert "_record_voice_event" in source
    assert "voice_reset_after_response" in source

    # Do not bring the old form implementation back.
    assert 'st.form("voice_input_form", clear_on_submit=True)' not in source
    assert "voice_slot.empty()" not in source


def test_chat_history_has_delete_control():
    source = APP_PATH.read_text(encoding="utf-8")

    assert "delete_conversation" in source
    assert "st.columns([0.84, 0.16]" in source
    assert '"🗑"' in source
    assert "st-key-delete-" in source
    assert "rgba(185, 28, 28, 0.62)" in source
    assert 'help=f"Delete: {title}"' not in source
    assert '"Delete saved chat"' not in source
    assert '"Delete Selected Chat"' not in source
