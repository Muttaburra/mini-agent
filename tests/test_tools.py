from unittest.mock import Mock

import pytest

import tool_impl as impl
import tool_dispatcher as dispatcher
from tool_schema import tools


@pytest.mark.parametrize("operation,expected", [("add", 13), ("subtract", 7), ("multiply", 30), ("divide", 10 / 3)])
def test_calculate(operation, expected):
    assert impl.calculate(10, 3, operation) == pytest.approx(expected)


@pytest.mark.parametrize("args", [(1, 0, "divide"), (1, 2, "power")])
def test_calculate_invalid_operation(args):
    with pytest.raises(ValueError):
        impl.calculate(*args)


@pytest.mark.parametrize("args", [("1", "2", "add"), (True, 1, "add"), (1, None, "multiply"), (1, 2, 3)])
def test_calculate_rejects_types(args):
    with pytest.raises((TypeError, ValueError)):
        impl.calculate(*args)


@pytest.mark.parametrize("name,args", [
    ("missing", {}), ("calculate", {}), ("calculate", []),
    ("calculate", {"a": 1, "b": 2, "operation": "add", "extra": 1}),
    ("calculate", {"a": True, "b": 2, "operation": "add"}),
    ("read_file", {"path": 1}), ("write_file", {"path": "a.txt", "content": 1}),
    ("search_files", {"keyword": None}),
])
def test_dispatch_rejects_invalid(name, args):
    with pytest.raises(ValueError):
        dispatcher.dispatch_tool(name, args)


@pytest.mark.parametrize("name,args", [
    ("calculate", {"a": 1, "b": 2, "operation": "add"}),
    ("read_file", {"path": "a.txt"}),
    ("write_file", {"path": "a.txt", "content": "hello"}),
    ("search_files", {"keyword": "hello"}),
])
def test_dispatch_forwards(monkeypatch, name, args):
    handler = Mock(return_value="result")
    monkeypatch.setitem(dispatcher.tool_handlers, name, handler)
    assert dispatcher.dispatch_tool(name, args) == "result"
    handler.assert_called_once_with(**args)


def test_dispatch_propagates_tool_exception(monkeypatch):
    handler = Mock(side_effect=RuntimeError("injected"))
    monkeypatch.setitem(dispatcher.tool_handlers, "read_file", handler)
    with pytest.raises(RuntimeError, match="injected"):
        dispatcher.dispatch_tool("read_file", {"path": "a.txt"})


def test_schema_matches_dispatcher():
    assert {t["name"] for t in tools} == set(dispatcher.tool_handlers)
    for tool in tools:
        assert set(tool["parameters"]["required"]) == dispatcher.required_args[tool["name"]]
        assert tool["parameters"]["additionalProperties"] is False


def test_read_write_and_no_overwrite(workspace):
    assert impl.write_file("report.txt", "支出 350") == "Created file: report.txt"
    assert impl.read_file("report.txt") == "支出 350"
    with pytest.raises(FileExistsError):
        impl.write_file("report.txt", "changed")
    assert (workspace / "report.txt").read_text(encoding="utf-8") == "支出 350"


def test_missing_files():
    with pytest.raises(FileNotFoundError):
        impl.read_file("missing.txt")
    with pytest.raises(FileNotFoundError):
        impl.write_file("missing/output.txt", "x")


@pytest.mark.parametrize("path", ["../.env", "../outside.txt", "sub/../../outside.txt", "secret.json"])
@pytest.mark.parametrize("write", [False, True])
def test_unsafe_paths(path, write):
    with pytest.raises(ValueError):
        impl.write_file(path, "x") if write else impl.read_file(path)


def test_absolute_paths(workspace):
    with pytest.raises(ValueError):
        impl.read_file(str(workspace / "a.txt"))
    with pytest.raises(ValueError):
        impl.write_file(str(workspace / "a.txt"), "x")


def test_write_byte_limit(workspace):
    impl.write_file("limit.txt", "x" * impl.MAX_WRITE_BYTES)
    with pytest.raises(ValueError, match="too large"):
        impl.write_file("large.txt", "中" * (impl.MAX_WRITE_BYTES // 3 + 1))
    assert not (workspace / "large.txt").exists()


def test_search_casefold_and_miss(workspace):
    (workspace / "a.txt").write_text("Hello\nStraße\nhello", encoding="utf-8")
    assert impl.search_files("HELLO") == [
        {"file": "a.txt", "line": 1, "text": "Hello"},
        {"file": "a.txt", "line": 3, "text": "hello"},
    ]
    assert impl.search_files("STRASSE")[0]["line"] == 2
    assert impl.search_files("absent") == []


@pytest.mark.parametrize("keyword", ["", "  ", None, 1])
def test_search_invalid(keyword):
    with pytest.raises(ValueError):
        impl.search_files(keyword)


def test_search_limits(workspace):
    (workspace / "large.txt").write_text("match" * 4000, encoding="utf-8")
    assert impl.search_files("match") == []
    (workspace / "a.txt").write_text(("match" * 50 + "\n") * 30, encoding="utf-8")
    hits = impl.search_files("match")
    assert len(hits) == 20
    assert all(len(hit["text"]) == 200 for hit in hits)


def test_symlink_escape(workspace, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "secret.txt"
    source.write_text("outside secret", encoding="utf-8")
    try:
        (workspace / "link.txt").symlink_to(source)
        (workspace / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows requires symlink privilege or Developer Mode")
        raise
    with pytest.raises(ValueError):
        impl.read_file("link.txt")
    with pytest.raises(ValueError):
        impl.write_file("linked/new.txt", "x")
    assert impl.search_files("outside") == []
    assert not (outside / "new.txt").exists()
    assert source.read_text(encoding="utf-8") == "outside secret"
