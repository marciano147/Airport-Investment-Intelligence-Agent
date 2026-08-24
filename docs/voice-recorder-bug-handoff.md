# Voice Recorder Bug Handoff

## Symptom

When the user records audio and stops recording, Streamlit shows:

> An error has occurred, please try again

The message appears at recorder completion time. In earlier tests, transcription and agent response could still succeed, which means this is not automatically a Groq Whisper failure.

## Current Implementation

Voice UI lives in `app.py` inside `_render_voice_input()`.

Current flow:

1. `streamlit_mic_recorder.mic_recorder(...)` records microphone audio.
2. User clicks `Send Voice`.
3. App reads WAV bytes from the recorder output dictionary.
4. `voice_utils.transcribe_audio()` sends bytes to Groq Whisper.
5. Transcript is queued as a normal chat prompt.
6. Agent response is traced in LangSmith.

The app no longer uses native `st.audio_input`. It uses `streamlit-mic-recorder==0.0.8` with `format="wav"`, `just_once=False`, and a separate `Send Voice` button.

The app marks `last_audio_hash` only after transcription succeeds. That allows a failed transcription to be retried with the same recording.

## Debugging Added

Server log:

```bash
tail -f logs/app.log
```

UI debug:

1. Enable `Show debug info` in the sidebar.
2. Check `Recent voice events`.

Voice events currently logged:

- `submit_without_audio`
- `duplicate_audio_ignored`
- `transcription_started`
- `transcription_succeeded`
- `transcription_failed`

Important interpretation:

- If the browser shows the recorder error and no `transcription_started` event appears, Python never received usable audio. That points to the recorder component, browser microphone state, or network/upload behavior.
- If `transcription_started` appears and then `transcription_failed`, inspect the Groq Whisper error.
- LangSmith starts at the agent call. It will not show recorder frontend failures unless a transcript reaches the agent.

## Most Likely Causes

1. Browser microphone/media permission state.
2. Custom recorder component upload/event issue.
3. Widget remount/rerun timing after recording completes.
4. Local browser cache holding an older Streamlit widget bundle.
5. Audio upload failure before Python receives WAV bytes.

## Reproduction Steps

1. Run the app:

```bash
streamlit run app.py
```

2. Open the local URL in a browser.
3. In the sidebar, record a short voice note.
4. Stop recording.
5. Observe whether the recorder shows an error before clicking `Send Voice`.
6. Enable `Show debug info` and check `Recent voice events`.
7. In another terminal, watch:

```bash
tail -f logs/app.log
```

## Browser Evidence To Capture

Open DevTools before recording:

1. Console tab: capture any Streamlit/media recorder error.
2. Network tab: filter failed requests around the recording stop event.
3. Confirm whether any upload request returns non-2xx.

Useful details:

- Browser name/version
- Local URL shown by Streamlit
- Whether the page is `localhost`, `127.0.0.1`, or a remote host
- Whether the issue reproduces in Chrome and Edge

## Fix Options

Recommended next attempts:

1. Hard refresh the app and restart Streamlit to ensure the latest code is loaded.
2. Test in Chrome with microphone permission reset.
3. Pin or upgrade Streamlit if the issue is version-specific.
4. Add an upload-audio fallback path using `st.file_uploader`.
5. Try an alternate recorder package such as `audio-recorder-streamlit` if the custom component fails in the target browser.

## Current Verification

Automated checks pass:

```bash
make check
make e2e
```

These verify the Python-side voice transcription path and Streamlit boot. They cannot fully verify the browser microphone widget stop-recording lifecycle without a real browser microphone session.
