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
