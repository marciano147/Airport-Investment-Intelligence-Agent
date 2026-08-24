"""Modular agent system-prompt loader."""

from pathlib import Path


CONTEXT_FILES = ["SOUL.md", "TOOLS.md", "SCORING.md", "ASSUMPTIONS.md", "WRITING.md"]


def load_context(context_dir: str | Path = "context") -> str:
    """Load context markdown files into one system prompt."""
    base = Path(context_dir)
    parts: list[str] = []

    # File order matters: identity and tool-use rules should appear before
    # scoring and answer-style guidance.
    for name in CONTEXT_FILES:
        path = base / name
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            parts.append(f"### {name.replace('.md', '').upper()}\n{content}")
        else:
            print(f"Warning: {name} not found")

    return "\n\n----------------\n\n".join(parts)
