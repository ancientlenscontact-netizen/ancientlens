from typing import Protocol
from app.models import Glyph

class ReadingOrderResolver(Protocol):
    def resolve(self, glyphs: list[Glyph]) -> list[Glyph]: ...

class UnknownReadingOrder:
    def resolve(self, glyphs: list[Glyph]) -> list[Glyph]:
        # List order is serialization order, never a claim about reading direction.
        return glyphs
