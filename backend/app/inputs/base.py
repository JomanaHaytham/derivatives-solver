"""Input adapters: every input modality is converted to plain problem text.

Today only text is supported. To add image input later, implement an
``ImageInputAdapter`` (e.g. calling an OCR / vision model that returns the
math as text), register it in ``ADAPTERS``, and have the frontend send
``input_type="image"``. Nothing downstream needs to change, because the
math and AI layers only ever see text.
"""

from __future__ import annotations

from typing import Protocol


class UnsupportedInput(Exception):
    pass


class InputAdapter(Protocol):
    input_type: str

    async def to_text(self, payload: str) -> str: ...


class TextInputAdapter:
    input_type = "text"

    async def to_text(self, payload: str) -> str:
        return payload.strip()


ADAPTERS: dict[str, InputAdapter] = {"text": TextInputAdapter()}


def get_adapter(input_type: str) -> InputAdapter:
    try:
        return ADAPTERS[input_type]
    except KeyError:
        raise UnsupportedInput(f"Input type '{input_type}' is not supported yet. Please type the problem as text.")
