import argparse
import functools
import os
import signal
import stat
import subprocess
import sys
import time

from ofrak_ghidra.constants import (
    GHIDRA_START_SERVER_SCRIPT,
    GHIDRA_CONSOLE_SERVER_SCRIPT,
    GHIDRA_PATH,
    CORE_OFRAK_GHIDRA_SCRIPTS,
    GHIDRA_USER,
    GHIDRA_PASS,
    GHIDRA_REPOSITORY_HOST,
    GHIDRA_REPOSITORY_PORT,
)


def _posix_only(func):
    """These server operations shell out to Ghidra's POSIX launcher scripts / POSIX process
    signalling, and are only supported on Linux and macOS."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if sys.platform not in ("linux", "darwin"):
            raise NotImplementedError(
                f"Native OFRAK Ghidra server not supported for {sys.platform}!"
            )
        return func(*args, **kwargs)

    return wrapper


@_posix_only
def _run_ghidra_server(*args):
    os.chmod(GHIDRA_START_SERVER_SCRIPT, os.stat(GHIDRA_START_SERVER_SCRIPT).st_mode | stat.S_IEXEC)
    subprocess.call(
        [
            GHIDRA_START_SERVER_SCRIPT,
            GHIDRA_PATH,
            CORE_OFRAK_GHIDRA_SCRIPTS,
            GHIDRA_USER,
            GHIDRA_PASS,
            GHIDRA_REPOSITORY_HOST,
            str(GHIDRA_REPOSITORY_PORT),
        ]
    )


@_posix_only
def _run_ghidra_server_console(*args):
    os.chmod(
        GHIDRA_CONSOLE_SERVER_SCRIPT, os.stat(GHIDRA_CONSOLE_SERVER_SCRIPT).st_mode | stat.S_IEXEC
    )
    subprocess.call(
        [
            GHIDRA_CONSOLE_SERVER_SCRIPT,
            GHIDRA_PATH,
            CORE_OFRAK_GHIDRA_SCRIPTS,
            GHIDRA_USER,
            GHIDRA_PASS,
            GHIDRA_REPOSITORY_HOST,
            str(GHIDRA_REPOSITORY_PORT),
        ]
    )


@_posix_only
def _stop_ghidra_server(*args):
    # `ghidraSvr stop` stops the systemd service installed by `start`; it does NOT stop a
    # foreground `console` server. Use `console-stop` for that.
    subprocess.call([os.path.join(GHIDRA_PATH, "server", "ghidraSvr"), "stop"])


# The Ghidra repository-server JVM carries "GhidraServer" in its launcher/classpath - but so do
# OFRAK's own analysis JVMs, because `analyzeHeadless` keeps `GhidraServer.jar` on its classpath.
# Those analysis JVMs MUST be subtracted out, or `console-stop` would SIGKILL the analysis backend a
# live GUI session depends on. (Verified on a running host: the analyzeHeadless JVMs matched
# `pgrep -f GhidraServer`.)
_SERVER_PGREP_PATTERN = "GhidraServer"
_ANALYSIS_PGREP_PATTERN = "analyzeHeadless"


def _pgrep_user(pattern):
    """The set of the current user's PIDs whose full command line matches `pattern`; empty if pgrep
    is unavailable."""
    try:
        result = subprocess.run(
            ["pgrep", "-u", str(os.getuid()), "-f", pattern],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        return set()
    return {int(t) for t in result.stdout.decode("utf-8", "replace").split() if t.isdigit()}


def _find_console_server_pids():
    """Return the PIDs of the current user's Ghidra repository-server JVM(s) - i.e. a server started
    with `console`. Scoped to the current uid (another user's server on a shared host is never
    touched); the analysis JVMs (`analyzeHeadless`, which share the GhidraServer classpath) and this
    process are excluded so `console-stop` never kills the analysis backend."""
    return sorted(
        _pgrep_user(_SERVER_PGREP_PATTERN) - _pgrep_user(_ANALYSIS_PGREP_PATTERN) - {os.getpid()}
    )


@_posix_only
def _console_status(*args):
    pids = _find_console_server_pids()
    if pids:
        print(
            "OFRAK Ghidra console server is running (PID "
            + ", ".join(str(p) for p in pids)
            + ")."
        )
    else:
        print("No OFRAK Ghidra console server is running for this user.")


@_posix_only
def _console_stop(*args):
    pids = _find_console_server_pids()
    if not pids:
        print("No OFRAK Ghidra console server is running for this user; nothing to stop.")
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as err:
            print(f"Could not signal PID {pid}: {err}")
    deadline = time.time() + 5.0
    while time.time() < deadline and _find_console_server_pids():
        time.sleep(0.2)
    for pid in _find_console_server_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    remaining = _find_console_server_pids()
    if remaining:
        print("Failed to stop console server PID(s): " + ", ".join(str(p) for p in remaining))
    else:
        print("Stopped the OFRAK Ghidra console server (no sudo required).")


parser = argparse.ArgumentParser(description="Manage OFRAK Ghidra server")
command_parser = parser.add_subparsers()

start_parser = command_parser.add_parser(
    "start",
    description="Start the OFRAK Ghidra server as a background system service (requires root)",
)
start_parser.set_defaults(func=_run_ghidra_server)
console_parser = command_parser.add_parser(
    "console",
    description="Run the OFRAK Ghidra server in the foreground (console mode), without root",
)
console_parser.set_defaults(func=_run_ghidra_server_console)
stop_parser = command_parser.add_parser(
    "stop",
    description="Stop the Ghidra system service started by `start` (requires root; for a `console` "
    "server use `console-stop`)",
)
stop_parser.set_defaults(func=_stop_ghidra_server)
console_stop_parser = command_parser.add_parser(
    "console-stop",
    description="Stop a `console` (no-root) Ghidra server owned by the current user",
)
console_stop_parser.set_defaults(func=_console_stop)
console_status_parser = command_parser.add_parser(
    "console-status",
    description="Report whether a `console` (no-root) Ghidra server is running for the current user",
)
console_status_parser.set_defaults(func=_console_status)


if __name__ == "__main__":
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_usage()
