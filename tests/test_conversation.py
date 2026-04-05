# tests/test_conversation.py
from __future__ import annotations
from x_agent_kit.conversation import ConversationManager

class TestConversationManager:
    def test_add_and_get_context(self):
        cm = ConversationManager(max_turns=5)
        cm.add_message("user", "hello", "chat-1")
        cm.add_message("assistant", "hi there", "chat-1")
        ctx = cm.get_context("chat-1")
        assert len(ctx) == 2
        assert ctx[0] == {"role": "user", "content": "hello"}
        assert ctx[1] == {"role": "assistant", "content": "hi there"}

    def test_max_turns(self):
        cm = ConversationManager(max_turns=3)
        for i in range(5):
            cm.add_message("user", f"msg-{i}", "chat-1")
        ctx = cm.get_context("chat-1")
        assert len(ctx) == 3
        assert ctx[0]["content"] == "msg-2"

    def test_separate_chats(self):
        cm = ConversationManager()
        cm.add_message("user", "a", "chat-1")
        cm.add_message("user", "b", "chat-2")
        assert len(cm.get_context("chat-1")) == 1
        assert len(cm.get_context("chat-2")) == 1

    def test_empty_context(self):
        cm = ConversationManager()
        assert cm.get_context("nonexistent") == []

    def test_clear(self):
        cm = ConversationManager()
        cm.add_message("user", "hello", "chat-1")
        cm.clear("chat-1")
        assert cm.get_context("chat-1") == []
