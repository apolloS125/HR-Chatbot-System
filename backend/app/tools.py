"""Allowlisted tool registry. Add external sources here; never execute user-supplied URLs."""
from collections.abc import Awaitable, Callable
from typing import Any

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
_handlers: dict[str, ToolHandler] = {}


def register_tool(name: str, handler: ToolHandler) -> None:
    _handlers[name] = handler


def tool_definitions() -> list[dict[str, Any]]:
    return [{"type": "function", "name": name, "description": "Registered external HR data source", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}} for name in _handlers]


async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in _handlers: raise ValueError(f"tool not registered: {name}")
    return await _handlers[name](arguments)
