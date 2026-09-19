from typing import Protocol
from app.models import Transliteration, Translation

class Translator(Protocol):
    def translate(self, text: Transliteration) -> Translation: ...

class AbstainingTranslator:
    def translate(self, text: Transliteration) -> Translation:
        return Translation(uncertain_segments=text.uncertain_segments,
            reasoning_metadata=["No recognition or linguistic model installed; translation withheld.",
                                "Damage and missing text have not been evaluated."])
