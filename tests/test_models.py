class TestMessage:
    def test_create_user_message(self):
        from x_agent_kit.models import Message
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_call_id is None

    def test_create_tool_result(self):
        from x_agent_kit.models import Message
        msg = Message(role="tool_result", content="result", tool_call_id="call_1")
        assert msg.tool_call_id == "call_1"

class TestToolCall:
    def test_create_tool_call(self):
        from x_agent_kit.models import ToolCall
        tc = ToolCall(id="call_1", name="search", arguments={"q": "test"})
        assert tc.name == "search"
        assert tc.arguments == {"q": "test"}

class TestBrainResponse:
    def test_text_only(self):
        from x_agent_kit.models import BrainResponse
        resp = BrainResponse(text="done")
        assert resp.text == "done"
        assert resp.tool_calls is None
        assert resp.done is False

    def test_tool_calls(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        tc = ToolCall(id="1", name="fn", arguments={})
        resp = BrainResponse(tool_calls=[tc])
        assert len(resp.tool_calls) == 1

    def test_done_flag(self):
        from x_agent_kit.models import BrainResponse
        resp = BrainResponse(text="final", done=True)
        assert resp.done is True
