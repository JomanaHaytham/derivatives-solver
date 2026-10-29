"""Tiny stand-in for pydantic's BaseModel, used only when pydantic is unavailable.

The static (GitHub Pages) build runs this backend code inside the browser with
Pyodide, where we ship only SymPy and mpmath. The models in ``schemas.py`` need
nothing more than keyword construction, defaults and ``model_dump()``.
"""

from __future__ import annotations

import copy
from typing import Any


def Field(default: Any = None, **_constraints: Any) -> Any:  # noqa: N802 - mirrors pydantic
    return default


class BaseModel:
    def __init__(self, **data: Any) -> None:
        for klass in reversed(type(self).__mro__):
            for name in getattr(klass, "__annotations__", {}):
                if name in data:
                    value = data[name]
                elif hasattr(klass, name):
                    value = copy.copy(getattr(klass, name))  # don't share mutable defaults
                else:
                    raise TypeError(f"{type(self).__name__} missing required field '{name}'")
                setattr(self, name, value)

    def model_dump(self) -> dict:
        return {name: _dump(getattr(self, name)) for klass in reversed(type(self).__mro__)
                for name in getattr(klass, "__annotations__", {})}


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    return value
