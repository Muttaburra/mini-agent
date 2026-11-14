"""Offline safety net shared by old unittest and new pytest tests."""
import socket
from unittest.mock import Mock

import dotenv
import pytest

import tool_impl


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", Mock(side_effect=AssertionError("No .env in tests")))
    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, Mock(side_effect=AssertionError("Network forbidden")))
    monkeypatch.setattr(socket, "getaddrinfo", Mock(side_effect=AssertionError("DNS forbidden")))


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(tool_impl, "WORKSPACE", root.resolve())
    return root
