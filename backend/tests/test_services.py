import asyncio

import pytest

from app.core import issue_liff_token, read_liff_token
from app.tools import call_tool, register_tool, tool_definitions


def test_liff_token_is_signed_and_rejects_tampering():
    token = issue_liff_token("U123")
    assert read_liff_token(token) == "U123"
    assert read_liff_token(token + "x") is None


def test_tool_registry_only_calls_registered_tools():
    async def handler(arguments): return {"employee": arguments["employee"]}
    register_tool("directory_lookup", handler)
    assert any(item["name"] == "directory_lookup" for item in tool_definitions())
    assert asyncio.run(call_tool("directory_lookup", {"employee": "E001"})) == {"employee": "E001"}
    with pytest.raises(ValueError): asyncio.run(call_tool("unknown", {}))
