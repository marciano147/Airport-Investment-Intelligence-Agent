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


def test_voice_input_uses_explicit_submit_form():
    source = APP_PATH.read_text(encoding="utf-8")

    assert 'st.form("voice_input_form", clear_on_submit=True)' in source
    assert 'st.form_submit_button("Send Voice"' in source
    assert "voice_slot.empty()" not in source
    assert "voice_reset_after_response" in source
