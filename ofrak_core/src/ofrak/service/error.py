from typing import Dict, Any

import json
import sys

import ofrak_type.error


class SerializedError(RuntimeError):
    def to_json(self):
        return json.dumps(self.to_dict(self))

    @classmethod
    def to_dict(cls, error: Exception):
        # Always carry type + message (the backward-compatible contract every client relies on).
        # Additionally surface the REAL underlying cause so a GUI-only user can see past the
        # top-level message: an explicit structured `details` attribute if the raiser set one
        # (e.g. captured subprocess stderr), otherwise the chained `__cause__` (from
        # `raise ... from ...`), which is otherwise dropped at this serialization boundary.
        serialized: Dict[str, Any] = {"type": type(error).__name__, "message": str(error)}
        details = getattr(error, "details", None)
        if not details:
            cause = error.__cause__
            if cause is not None and cause is not error:
                details = f"{type(cause).__name__}: {cause}"
        if details:
            serialized["details"] = str(details)
        return serialized

    @classmethod
    def from_json(cls, serialized: str) -> "SerializedError":
        # Note: `details` (added by `to_dict`) is intentionally NOT reconstructed here. It is a
        # presentation-only field for GUI/JSON consumers (which read it straight off the parsed
        # payload); a rebuilt Python exception carries only type + message, as before.
        error_dict = json.loads(serialized)
        error_type = error_dict["type"]
        try:
            error = getattr(sys.modules[__name__], error_type)
        except AttributeError:
            try:
                error = getattr(ofrak_type.error, error_type)
            except:
                raise ValueError(error_dict)
        if issubclass(error, cls):
            return error.from_dict({"message": error_dict["message"]})
        else:
            return error(error_dict["message"])

    @classmethod
    def from_dict(cls, error_dict: Dict[str, Any]) -> "SerializedError":
        return cls(error_dict["message"])


class DataServiceError(SerializedError):
    pass


class ResourceServiceError(SerializedError):
    pass


class JobServiceError(SerializedError):
    pass


class OutOfBoundError(DataServiceError):
    pass


class PatchOverlapError(DataServiceError):
    pass


class MisalignedError(DataServiceError):
    pass


class AmbiguousOrderError(RuntimeError):
    pass


class NonContiguousError(DataServiceError):
    pass
