"""Unit tests (no live Ghidra needed) for the Ghidra headless error-surfacing helpers, the
analyze-and-serve EOF guard, and the custom-load empty/invalid-memory fast-fail guard."""
import asyncio
import os
import tempfile

import pytest

from ofrak_ghidra.components.ghidra_analyzer import (
    GhidraCustomLoadAnalyzer,
    GhidraProjectAnalyzer,
)
from ofrak_ghidra.ghidra_model import GhidraComponentException


# ------------------------------------------------------------------ headless error helpers (#7B)


def test_read_text_tail_returns_tail():
    tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
    try:
        tf.write("prelude\nERROR java.lang.NullPointerException at Foo.bar\n")
        tf.close()
        assert "NullPointerException" in GhidraProjectAnalyzer._read_text_tail(tf.name)
    finally:
        os.unlink(tf.name)


def test_read_text_tail_truncates_to_limit():
    tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
    try:
        tf.write("A" * 100 + "TAILMARKER")
        tf.close()
        out = GhidraProjectAnalyzer._read_text_tail(tf.name, limit=10)
        assert out == "TAILMARKER"
    finally:
        os.unlink(tf.name)


def test_read_text_tail_missing_file():
    assert GhidraProjectAnalyzer._read_text_tail("/no/such/file") == ""


def test_headless_error_surfaces_stderr():
    tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
    try:
        tf.write("java.lang.NullPointerException\n\tat ghidra.MemoryMapDB.getInt\n")
        tf.close()
        exc = GhidraProjectAnalyzer._ghidra_headless_error(
            GhidraProjectAnalyzer, "Ghidra headless analysis failed", tf.name
        )
    finally:
        os.unlink(tf.name)
    assert isinstance(exc, GhidraComponentException)
    assert "NullPointerException" in str(exc)
    assert exc.details is not None and "NullPointerException" in exc.details


def test_headless_error_without_stderr_falls_back():
    exc = GhidraProjectAnalyzer._ghidra_headless_error(
        GhidraProjectAnalyzer, "Ghidra headless analysis failed", "/no/such/file"
    )
    assert "no stderr captured" in str(exc)
    assert exc.details is None


# ------------------------------------------------- analyze-and-serve EOF guard (#6) + stderr (#7B)


async def test_serve_eof_guard_raises_without_busy_looping(monkeypatch):
    class _FakeStdout:
        async def readline(self):
            return b""  # immediate EOF: no success marker was ever printed

        def at_eof(self):
            return True

    class _FakeProc:
        pid = 4321
        returncode = 1
        stdout = _FakeStdout()
        stdin = None

        async def wait(self):
            return 1

    async def _fake_shell(*a, **k):
        return _FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_shell", _fake_shell)
    analyzer = GhidraProjectAnalyzer.__new__(GhidraProjectAnalyzer)
    analyzer._script_directories = ["/tmp"]
    analyzer._scripts = []

    # Regression sentinel: WITHOUT the at_eof() guard this loop spins on b"" forever and wait_for
    # raises TimeoutError instead; with the guard it raises promptly.
    with pytest.raises(GhidraComponentException) as exc_info:
        await asyncio.wait_for(
            analyzer._do_ghidra_analyze_and_serve("proj", "prog", skip_analysis=True),
            timeout=5,
        )
    assert "exited before it started serving" in str(exc_info.value)


# ------------------------------------------------------------- custom-load memory-map guard (#7A)


class _FakeProgramResource:
    async def analyze(self, _attr_type):
        return object()

    async def view_as(self, _view_type):
        return object()


async def test_custom_load_rejects_empty_memory(monkeypatch):
    analyzer = GhidraCustomLoadAnalyzer.__new__(GhidraCustomLoadAnalyzer)

    async def _no_blocks(_program):
        return []

    monkeypatch.setattr(analyzer, "_get_memory_blocks", _no_blocks)
    with pytest.raises(GhidraComponentException) as exc_info:
        await analyzer.analyze(_FakeProgramResource())
    assert "no usable MemoryRegions" in str(exc_info.value)


async def test_custom_load_rejects_invalid_region(monkeypatch):
    analyzer = GhidraCustomLoadAnalyzer.__new__(GhidraCustomLoadAnalyzer)

    class _BadBlock:
        virtual_address = None  # never set in the GUI -> would serialize as "None" for Ghidra
        size = 0

    async def _bad_blocks(_program):
        return [_BadBlock()]

    monkeypatch.setattr(analyzer, "_get_memory_blocks", _bad_blocks)
    with pytest.raises(GhidraComponentException) as exc_info:
        await analyzer.analyze(_FakeProgramResource())
    assert "no usable MemoryRegions" in str(exc_info.value)
