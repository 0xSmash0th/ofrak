"""Tests for SerializedError.to_dict carrying a `details` field across the GUI error boundary."""
from ofrak.service.error import SerializedError


def test_serialized_error_carries_chained_cause_as_details():
    try:
        try:
            raise ValueError("the real underlying cause")
        except ValueError as cause:
            raise RuntimeError("generic top-level message") from cause
    except RuntimeError as err:
        d = SerializedError.to_dict(err)
    assert d["type"] == "RuntimeError"
    assert d["message"] == "generic top-level message"
    assert "the real underlying cause" in d["details"]


def test_serialized_error_prefers_explicit_details_attribute():
    err = RuntimeError("top")
    err.details = "captured stderr tail"  # type: ignore[attr-defined]
    assert SerializedError.to_dict(err)["details"] == "captured stderr tail"


def test_serialized_error_backward_compatible_without_details():
    d = SerializedError.to_dict(ValueError("plain"))
    assert set(d.keys()) == {"type", "message"}
