"""Opt-in live smoke checks for the airport investment agent.

Run with:
    python scripts/live_smoke.py
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from groq import Groq
from langsmith import Client


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    os.chdir(ROOT)

    checks = [
        ("environment", check_environment),
        ("groq model access", check_groq_model_access),
        ("agent text query", check_agent_query),
        ("langsmith access", check_langsmith_access),
        ("groq whisper", check_whisper),
        ("streamlit boot", check_streamlit_boot),
    ]

    failed = False
    for label, check in checks:
        try:
            detail = check()
            print(f"PASS {label}: {detail}")
        except SkipCheck as exc:
            print(f"SKIP {label}: {exc}")
        except Exception as exc:
            failed = True
            print(f"FAIL {label}: {type(exc).__name__}: {exc}")

    return 1 if failed else 0


def check_environment() -> str:
    required = ["GROQ_API_KEY", "GROQ_MODEL", "GROQ_TRANSCRIPTION_MODEL"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"missing required env vars: {', '.join(missing)}")
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        langsmith_required = ["LANGSMITH_ENDPOINT", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"]
        missing_langsmith = [key for key in langsmith_required if not os.getenv(key)]
        if missing_langsmith:
            raise RuntimeError(
                f"missing LangSmith env vars: {', '.join(missing_langsmith)}"
            )
    return "required variables are set"


def check_groq_model_access() -> str:
    model = os.environ["GROQ_MODEL"]
    model_ids = {item.id for item in Groq().models.list().data}
    if model not in model_ids:
        raise RuntimeError(f"GROQ_MODEL '{model}' is not available to this key")
    return f"{model} is available"


def check_agent_query() -> str:
    from agent import run_agent

    try:
        answer = run_agent(
            "Compare LAX and SNA. Return one short table.",
            thread_id="live-smoke-agent-query",
        )
    except Exception as exc:
        error_text = str(exc).lower()
        if "tokens per day" in error_text or "tpd" in error_text:
            raise SkipCheck("Groq daily token quota is exhausted")
        raise
    required_fragments = ["LAX", "SNA", "Composite"]
    missing = [fragment for fragment in required_fragments if fragment not in answer]
    if missing:
        raise RuntimeError(f"agent answer missing expected fragments: {missing}")
    return "Groq-backed tool agent returned comparison"


def check_langsmith_access() -> str:
    if os.getenv("LANGSMITH_TRACING", "").lower() != "true":
        raise SkipCheck("LANGSMITH_TRACING is not true")
    projects = list(Client().list_projects(limit=1))
    return f"client can access LangSmith project list ({len(projects)} sample visible)"


def check_whisper() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SkipCheck("ffmpeg is unavailable for local audio generation")

    audio_path = Path(tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name)
    try:
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "flite=text='rank california airports':voice=slt",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-t",
            "3",
            str(audio_path),
        ]
        generated = subprocess.run(command, capture_output=True, text=True, timeout=15)
        if generated.returncode != 0:
            raise SkipCheck("ffmpeg flite audio generation is unavailable")
        if audio_path.stat().st_size == 0:
            raise SkipCheck("ffmpeg generated an empty audio file")

        from voice_utils import transcribe_audio

        transcript = transcribe_audio(audio_path.read_bytes(), filename=audio_path.name)
        if transcript.startswith("[Transcription error:"):
            raise RuntimeError(transcript)
        if "california" not in transcript.lower():
            raise RuntimeError(f"unexpected transcript: {transcript!r}")
        return f"transcribed sample as {transcript!r}"
    finally:
        audio_path.unlink(missing_ok=True)


def check_streamlit_boot() -> str:
    port = _free_port()
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        health_url = f"http://localhost:{port}/_stcore/health"
        root_url = f"http://localhost:{port}"
        deadline = time.time() + 20
        last_error = "not checked"
        while time.time() < deadline:
            try:
                health = requests.get(health_url, timeout=2)
                root = requests.get(root_url, timeout=2)
                if health.text == "ok" and root.status_code == 200:
                    return f"health ok on port {port}"
                last_error = f"health={health.status_code} root={root.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)
            time.sleep(0.5)
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        output = _read_process_output(process)
        raise RuntimeError(f"Streamlit did not become healthy: {last_error}\n{output}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_process_output(process: subprocess.Popen[str]) -> str:
    if not process.stdout:
        return ""
    try:
        return process.stdout.read(4000)
    except Exception:
        return ""


class SkipCheck(Exception):
    """Raised when a live smoke check is not applicable on this machine."""


if __name__ == "__main__":
    raise SystemExit(main())
