from prompts import CONTEXT_FILES, load_context


def test_load_context_includes_files_in_expected_order(tmp_path):
    for name in CONTEXT_FILES:
        (tmp_path / name).write_text(f"content for {name}", encoding="utf-8")

    context = load_context(tmp_path)

    sections = [part.strip().splitlines()[0] for part in context.split("----------------")]
    assert sections == [
        "### SOUL",
        "### TOOLS",
        "### SCORING",
        "### ASSUMPTIONS",
        "### WRITING",
    ]
    assert "content for SOUL.md" in context


def test_load_context_warns_for_missing_files(tmp_path, capsys):
    (tmp_path / "SOUL.md").write_text("mission", encoding="utf-8")

    context = load_context(tmp_path)
    captured = capsys.readouterr()

    assert "### SOUL" in context
    assert "Warning: TOOLS.md not found" in captured.out
