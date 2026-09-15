from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, Protocol, cast
from unittest.mock import AsyncMock, Mock


class AwaitCall(Protocol):
    """Typed view of the arguments recorded by an awaited mock."""

    @property
    def args(self) -> tuple[Any, ...]: ...

    @property
    def kwargs(self) -> Mapping[str, Any]: ...


def replace_attr[ReplacementT](
    target: object, attribute: str, replacement: ReplacementT
) -> ReplacementT:
    """Install a test replacement while rejecting misspelled or stale fixture seams."""
    if not hasattr(target, attribute):
        raise AssertionError(f"{type(target).__name__} has no attribute {attribute!r}")
    setattr(target, attribute, replacement)
    return replacement


def loose_fixture(**attributes: object) -> Any:
    """Create a lightweight attribute fixture at an intentional dynamic boundary."""
    return SimpleNamespace(**attributes)


def as_mock(value: object) -> Mock:
    """Narrow a configured mock and fail when the fixture seam is not a mock."""
    if not isinstance(value, Mock):
        raise AssertionError(f"Expected Mock, got {type(value).__name__}")
    return value


def as_async_mock(value: object) -> AsyncMock:
    """Narrow a patched attribute and fail if the fixture installed the wrong mock type."""
    if not isinstance(value, AsyncMock):
        raise AssertionError(f"Expected AsyncMock, got {type(value).__name__}")
    return value


def require_await(value: object) -> AwaitCall:
    """Return the recorded await call after validating that it exists."""
    call = as_async_mock(value).await_args
    if call is None:
        raise AssertionError("Expected mock to have been awaited")
    return cast(AwaitCall, call)
