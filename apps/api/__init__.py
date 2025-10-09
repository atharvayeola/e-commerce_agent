"""API package initialization with compatibility patches."""

from __future__ import annotations

import inspect
from typing import ForwardRef

# Python 3.12 made ForwardRef._evaluate require a keyword-only argument.
# Pydantic <2 still calls it positionally, so we adapt the call here to keep
# FastAPI working under the newer runtime.
if hasattr(ForwardRef, "_evaluate"):
    signature = inspect.signature(ForwardRef._evaluate)
    param = signature.parameters.get("recursive_guard")
    if param and param.kind is inspect.Parameter.KEYWORD_ONLY:
        _orig_forward_evaluate = ForwardRef._evaluate

        def _patched_forward_evaluate(self, globalns, localns, *args, **kwargs):  # type: ignore[override]
            if args:
                recursive_guard = args[0]
            else:
                recursive_guard = kwargs.get("recursive_guard")
            if recursive_guard is None:
                recursive_guard = set()
            return _orig_forward_evaluate(self, globalns, localns, recursive_guard=recursive_guard)

        ForwardRef._evaluate = _patched_forward_evaluate  # type: ignore[assignment]

__all__ = ["ForwardRef"]