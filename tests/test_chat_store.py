import json

import chat_store

from chat_store import (
    delete_conversation,
    export_messages_json,
    list_conversations,
    load_messages,
    save_message,
)


def test_chat_store_saves_and_loads_messages(tmp_path):
    db_path = tmp_path / "chat_history.db"

    save_message("thread-1", "user", "Rank California airports", db_path)
    save_message("thread-1", "assistant", "SAN ranks first.", db_path)

    conversations = list_conversations(db_path)
    messages = load_messages("thread-1", db_path)

    assert conversations[0]["thread_id"] == "thread-1"
    assert conversations[0]["title"] == "Rank California airports"
    assert messages == [
        {"role": "user", "content": "Rank California airports"},
        {"role": "assistant", "content": "SAN ranks first."},
    ]


def test_chat_store_exports_messages_as_json(tmp_path):
    db_path = tmp_path / "chat_history.db"

    save_message("thread-2", "user", "Compare LAX and SNA", db_path)

    exported = json.loads(export_messages_json("thread-2", db_path))

    assert exported == [{"role": "user", "content": "Compare LAX and SNA"}]


def test_chat_store_deletes_one_conversation(tmp_path):
    db_path = tmp_path / "chat_history.db"

    save_message("thread-1", "user", "Rank California airports", db_path)
    save_message("thread-2", "user", "Compare LAX and SNA", db_path)

    delete_conversation("thread-1", db_path)

    conversations = list_conversations(db_path)
    assert [row["thread_id"] for row in conversations] == ["thread-2"]
    assert load_messages("thread-1", db_path) == []
    assert load_messages("thread-2", db_path) == [
        {"role": "user", "content": "Compare LAX and SNA"}
    ]


def test_chat_store_uses_current_default_path(monkeypatch, tmp_path):
    db_path = tmp_path / "patched_history.db"
    monkeypatch.setattr(chat_store, "DB_PATH", db_path)

    save_message("thread-3", "user", "Rank US airports")

    assert db_path.exists()
    assert load_messages("thread-3") == [
        {"role": "user", "content": "Rank US airports"}
    ]
