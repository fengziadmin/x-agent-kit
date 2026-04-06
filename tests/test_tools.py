import pytest

class TestToolDecorator:
    def test_decorated_function_still_callable(self):
        from x_agent_kit.tools.base import tool
        @tool("adds two numbers")
        def add(a: int, b: int) -> int:
            return a + b
        assert add(1, 2) == 3

    def test_decorated_function_has_tool_meta(self):
        from x_agent_kit.tools.base import tool
        @tool("adds two numbers")
        def add(a: int, b: int) -> int:
            return a + b
        assert hasattr(add, "_tool_meta")
        assert add._tool_meta.description == "adds two numbers"

    def test_tool_meta_has_name(self):
        from x_agent_kit.tools.base import tool
        @tool("my tool")
        def my_func(x: str) -> str:
            return x
        assert my_func._tool_meta.name == "my_func"

    def test_tool_meta_generates_json_schema(self):
        from x_agent_kit.tools.base import tool
        @tool("greet user")
        def greet(name: str, loud: bool = False) -> str:
            return name
        schema = greet._tool_meta.schema()
        assert schema["type"] == "function"
        assert "name" in schema["function"]["parameters"]["properties"]

class TestToolRegistry:
    def test_register_and_list(self):
        from x_agent_kit.tools.base import tool
        from x_agent_kit.tools.registry import ToolRegistry
        @tool("adds")
        def add(a: int, b: int) -> int:
            return a + b
        reg = ToolRegistry()
        reg.register(add)
        assert "add" in [t.name for t in reg.list()]

    def test_execute_tool(self):
        from x_agent_kit.tools.base import tool
        from x_agent_kit.tools.registry import ToolRegistry
        @tool("adds")
        def add(a: int, b: int) -> int:
            return a + b
        reg = ToolRegistry()
        reg.register(add)
        result = reg.execute("add", {"a": 3, "b": 4})
        assert result == 7

    def test_execute_unknown_tool_raises(self):
        from x_agent_kit.tools.registry import ToolRegistry
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.execute("nonexistent", {})

    def test_schemas_returns_list_of_dicts(self):
        from x_agent_kit.tools.base import tool
        from x_agent_kit.tools.registry import ToolRegistry
        @tool("adds")
        def add(a: int, b: int) -> int:
            return a + b
        reg = ToolRegistry()
        reg.register(add)
        schemas = reg.schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"

    def test_tool_error_returns_error_string(self):
        from x_agent_kit.tools.base import tool
        from x_agent_kit.tools.registry import ToolRegistry
        @tool("fails")
        def bad_tool() -> str:
            raise ValueError("broken")
        reg = ToolRegistry()
        reg.register(bad_tool)
        result = reg.execute("bad_tool", {})
        assert "ValueError" in result
        assert "broken" in result


class TestToolLabel:
    def test_tool_with_label(self):
        from x_agent_kit.tools.base import tool
        @tool("does stuff", label="📊 My Tool")
        def my_tool() -> str:
            return "ok"
        assert my_tool._tool_meta.label == "📊 My Tool"

    def test_tool_without_label_defaults_empty(self):
        from x_agent_kit.tools.base import tool
        @tool("does stuff")
        def my_tool() -> str:
            return "ok"
        assert my_tool._tool_meta.label == ""

    def test_label_not_in_schema(self):
        from x_agent_kit.tools.base import tool
        @tool("does stuff", label="📊 My Tool")
        def my_tool() -> str:
            return "ok"
        schema = my_tool._tool_meta.schema()
        assert "label" not in schema["function"]


class TestToolRegistryGetMeta:
    def test_get_meta_returns_tool_meta(self):
        from x_agent_kit.tools.base import tool
        from x_agent_kit.tools.registry import ToolRegistry
        @tool("adds", label="➕ Add")
        def add(a: int, b: int) -> int:
            return a + b
        reg = ToolRegistry()
        reg.register(add)
        meta = reg.get_meta("add")
        assert meta is not None
        assert meta.label == "➕ Add"
        assert meta.name == "add"

    def test_get_meta_returns_none_for_unknown(self):
        from x_agent_kit.tools.registry import ToolRegistry
        reg = ToolRegistry()
        assert reg.get_meta("nonexistent") is None
