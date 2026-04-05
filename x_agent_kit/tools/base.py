from __future__ import annotations
import inspect
from dataclasses import dataclass
from typing import Any, Callable

_PYTHON_TYPE_TO_JSON = {
    str: "string", int: "integer", float: "number", bool: "boolean", dict: "object", list: "array",
}

@dataclass
class ToolMeta:
    name: str
    description: str
    func: Callable
    parameters: dict

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }

def _extract_parameters(func: Callable) -> dict:
    sig = inspect.signature(func)
    hints = func.__annotations__
    properties = {}
    required = []
    for param_name, param in sig.parameters.items():
        if param_name == "return":
            continue
        param_type = hints.get(param_name, str)
        json_type = _PYTHON_TYPE_TO_JSON.get(param_type, "string")
        properties[param_name] = {"type": json_type}
        if func.__doc__:
            for line in func.__doc__.split("\n"):
                stripped = line.strip()
                if stripped.startswith(f"{param_name}:"):
                    desc = stripped.split(":", 1)[1].strip()
                    properties[param_name]["description"] = desc
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            properties[param_name]["default"] = param.default
    return {"type": "object", "properties": properties, "required": required}

def tool(description: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        meta = ToolMeta(name=func.__name__, description=description, func=func, parameters=_extract_parameters(func))
        func._tool_meta = meta
        return func
    return decorator
