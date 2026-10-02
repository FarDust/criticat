"""Tests for the ``criticat-mcp`` entry point."""

import logging
import subprocess
import sys
from collections.abc import Iterator

import pytest

from criticat.interfaces import server


@pytest.fixture
def restore_logging() -> Iterator[logging.Logger]:
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield root
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture
def run_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda transport: calls.append(transport))
    monkeypatch.setattr(server.mcp.settings, "host", server.mcp.settings.host)
    monkeypatch.setattr(server.mcp.settings, "port", server.mcp.settings.port)
    monkeypatch.setattr(server, "configure_logging", lambda level: None)
    return calls


def test_parse_args_defaults() -> None:
    args = server.parse_args([])
    assert args.transport == "stdio"
    assert args.host is None
    assert args.port is None
    assert args.log_level == "INFO"


def test_parse_args_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRITICAT_MCP_TRANSPORT", "sse")
    monkeypatch.setenv("CRITICAT_LOG_LEVEL", "debug")
    args = server.parse_args([])
    assert args.transport == "sse"
    assert args.log_level == "DEBUG"


def test_parse_args_rejects_unknown_transport() -> None:
    with pytest.raises(SystemExit):
        server.parse_args(["--transport", "carrier-pigeon"])


def test_main_runs_stdio_by_default(run_calls: list[str]) -> None:
    server.main([])
    assert run_calls == ["stdio"]


def test_main_configures_sse_host_and_port(run_calls: list[str]) -> None:
    server.main(["--transport", "sse", "--host", "127.0.0.1", "--port", "9123"])
    assert run_calls == ["sse"]
    assert server.mcp.settings.host == "127.0.0.1"
    assert server.mcp.settings.port == 9123


def test_main_handles_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, run_calls: list[str]
) -> None:
    def interrupt(transport: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(server.mcp, "run", interrupt)
    server.main([])


def test_configure_logging_moves_handlers_to_stderr(
    restore_logging: logging.Logger,
) -> None:
    restore_logging.addHandler(logging.StreamHandler(sys.stdout))
    server.configure_logging("WARNING")

    streams = [getattr(h, "stream", None) for h in restore_logging.handlers]
    assert sys.stdout not in streams
    assert sys.stderr in streams
    assert restore_logging.level == logging.WARNING


def test_import_writes_nothing_to_stdout() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import logging, criticat.interfaces.server as s; "
                "logging.getLogger('criticat').warning('probe')"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert result.stdout == ""
