"""Isolated configuration and local MCP server fixtures."""

import importlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def toolbox(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("MCP_CONFIG_FILE", raising=False)
    module = importlib.import_module("quantalogic_toolbox_mcp.tools")
    monkeypatch.setattr(module, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(module, "CONFIG_FILE", None)
    monkeypatch.setattr(module, "_tools_cache", None)
    module.servers.clear()
    module.tools_cache.clear()
    return module


@pytest.fixture
def http_server():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = dict(os.environ, NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("fixture_server.py")), str(port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server(process, port)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        process.wait(timeout=10)


def wait_for_server(process, port):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        assert process.poll() is None, "Local MCP server failed to start"
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail("Local MCP server did not start")
