from typing import Protocol
from app.models import Glyph, Transliteration

class Transliterator(Protocol):
    def transliterate(self, glyphs: list[Glyph]) -> Transliteration: ...

class AbstainingTransliterator:
    def transliterate(self, glyphs: list[Glyph]) -> Transliteration:
        return Transliteration(uncertain_segments=[g.id for g in glyphs])
