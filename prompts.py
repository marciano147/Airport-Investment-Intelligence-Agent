"""Hermes-style markdown context loader."""

from pathlib import Path


CONTEXT_FILES = ["SOUL.md", "TOOLS.md", "SCORING.md", "ASSUMPTIONS.md", "WRITING.md"]


def load_context(context_dir: str | Path = "context") -> str:
    """Load context markdown files into one system prompt."""
    base = Path(context_dir)
    parts: list[str] = []

    for name in CONTEXT_FILES:
        path = base / name
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            parts.append(f"### {name.replace('.md', '').upper()}\n{content}")

    return "\n\n----------------\n\n".join(parts)
