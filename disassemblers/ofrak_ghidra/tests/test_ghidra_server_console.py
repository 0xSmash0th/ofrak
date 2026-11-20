"""Unit tests (no live Ghidra needed) for the no-root console server management in
`ofrak_ghidra.server`: the pgrep-based finder, console-status, and console-stop."""
import pytest

import ofrak_ghidra.server.__main__ as server_main


def test_pgrep_user_parses_pids(monkeypatch):
    class _Result:
        stdout = b"111\n222\n"

    monkeypatch.setattr(server_main.subprocess, "run", lambda *a, **k: _Result())
    assert server_main._pgrep_user("GhidraServer") == {111, 222}


def test_pgrep_user_without_pgrep(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(server_main.subprocess, "run", _raise)
    assert server_main._pgrep_user("x") == set()


def test_find_console_server_excludes_analysis_jvms_and_self(monkeypatch):
    # The analysis JVMs (analyzeHeadless) share the GhidraServer classpath, so they match the server
    # pattern too and MUST be subtracted, or console-stop would kill the live analysis backend.
    def _fake_pgrep(pattern):
        return {
            server_main._SERVER_PGREP_PATTERN: {111, 222, 999},
            server_main._ANALYSIS_PGREP_PATTERN: {222},
        }[pattern]

    monkeypatch.setattr(server_main, "_pgrep_user", _fake_pgrep)
    monkeypatch.setattr(server_main.os, "getpid", lambda: 999)
    assert server_main._find_console_server_pids() == [111]


def test_console_status_running(monkeypatch, capsys):
    monkeypatch.setattr(server_main, "_find_console_server_pids", lambda: [111, 222])
    server_main._console_status.__wrapped__()
    assert "running" in capsys.readouterr().out


def test_console_status_not_running(monkeypatch, capsys):
    monkeypatch.setattr(server_main, "_find_console_server_pids", lambda: [])
    server_main._console_status.__wrapped__()
    assert "No OFRAK Ghidra console server" in capsys.readouterr().out


def test_console_stop_nothing_running(monkeypatch, capsys):
    monkeypatch.setattr(server_main, "_find_console_server_pids", lambda: [])
    server_main._console_stop.__wrapped__()
    assert "nothing to stop" in capsys.readouterr().out


def test_console_stop_sigterm_success(monkeypatch, capsys):
    # First lookup finds [111]; after SIGTERM the process is gone, so later lookups return [].
    lookups = [[111], []]
    monkeypatch.setattr(
        server_main,
        "_find_console_server_pids",
        lambda: lookups.pop(0) if lookups else [],
    )
    killed = []
    monkeypatch.setattr(server_main.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(server_main.time, "sleep", lambda s: None)
    server_main._console_stop.__wrapped__()
    assert (111, server_main.signal.SIGTERM) in killed
    assert "Stopped" in capsys.readouterr().out


def test_console_stop_escalates_to_sigkill(monkeypatch, capsys):
    # The process never dies: SIGTERM, wait out the deadline, SIGKILL, then "Failed to stop".
    monkeypatch.setattr(server_main, "_find_console_server_pids", lambda: [111])
    killed = []
    monkeypatch.setattr(server_main.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(server_main.time, "sleep", lambda s: None)
    clock = iter(float(i) for i in range(100))
    monkeypatch.setattr(server_main.time, "time", lambda: next(clock))
    server_main._console_stop.__wrapped__()
    signals = {sig for _, sig in killed}
    assert server_main.signal.SIGTERM in signals and server_main.signal.SIGKILL in signals
    assert "Failed to stop" in capsys.readouterr().out


def test_posix_only_rejects_non_posix(monkeypatch):
    monkeypatch.setattr(server_main.sys, "platform", "win32")
    with pytest.raises(NotImplementedError):
        server_main._console_status()
