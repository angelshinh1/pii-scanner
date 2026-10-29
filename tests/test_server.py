import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from pii_scanner.server import mcp


@pytest.fixture(autouse=True)
def allow_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_ALLOWED_ROOT", str(tmp_path))


@pytest.mark.asyncio
async def test_lists_exactly_two_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert sorted(t.name for t in tools) == ["scan_file", "scan_folder"]
    assert all(t.description for t in tools)


@pytest.mark.asyncio
async def test_scan_folder_tool(tmp_path):
    (tmp_path / "x.txt").write_text("card 4111 1111 1111 1111", encoding="utf-8")
    (tmp_path / "clean.md").write_text("nothing here", encoding="utf-8")
    async with Client(mcp) as client:
        result = await client.call_tool("scan_folder", {"path": str(tmp_path)})

    data = result.data
    assert data["files_scanned"] == 2
    assert data["files_flagged"] == 1
    assert data["totals"] == {"CREDIT_CARD": 1}
    assert data["reports"][0]["path"] == "x.txt"
    assert data["reports"][0]["findings"][0]["masked"] == "XXXX XXXX XXXX 1111"

    everything = json.dumps(data) + "".join(c.text for c in result.content)
    assert "4111111111111111" not in everything
    assert "4111 1111 1111 1111" not in everything


@pytest.mark.asyncio
async def test_scan_file_tool(tmp_path):
    (tmp_path / "hr").mkdir()
    (tmp_path / "hr" / "people.csv").write_text("A,130 692 544\nB,123-456-782", encoding="utf-8")
    async with Client(mcp) as client:
        result = await client.call_tool("scan_file", {"path": str(tmp_path / "hr" / "people.csv")})

    data = result.data
    assert data["path"] == "hr/people.csv"
    assert data["counts"] == {"SIN": 2}
    assert [f["line"] for f in data["findings"]] == [1, 2]
    assert "130 692 544" not in json.dumps(data)


@pytest.mark.asyncio
async def test_path_outside_allowed_root_is_friendly_error(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("SCANNER_ALLOWED_ROOT", str(allowed))
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="outside the allowed scan root"):
            await client.call_tool("scan_folder", {"path": str(tmp_path)})
        with pytest.raises(ToolError, match="outside the allowed scan root"):
            await client.call_tool("scan_file", {"path": str(tmp_path / "x.txt")})


@pytest.mark.asyncio
async def test_missing_folder_is_friendly_error(tmp_path):
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Folder not found"):
            await client.call_tool("scan_folder", {"path": str(tmp_path / "nope")})


@pytest.mark.asyncio
async def test_unsupported_file_type_is_friendly_error(tmp_path):
    (tmp_path / "x.py").write_text("SIN 130 692 544", encoding="utf-8")
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Unsupported file type"):
            await client.call_tool("scan_file", {"path": str(tmp_path / "x.py")})
