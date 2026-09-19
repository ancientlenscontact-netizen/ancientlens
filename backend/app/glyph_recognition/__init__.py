from typing import Protocol
from PIL import Image
from app.models import GlyphCandidate

class GlyphRecognizer(Protocol):
    def recognize(self, crop: Image.Image) -> list[GlyphCandidate]: ...

class UnavailableRecognizer:
    def recognize(self, crop: Image.Image) -> list[GlyphCandidate]:
        return []
