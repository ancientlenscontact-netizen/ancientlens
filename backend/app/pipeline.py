from pathlib import Path
from PIL import Image
from app.models import Glyph, TextRegion, Inscription
from app.vision import ContrastRegionDetector, RegionAsCandidate, RegionDetector, GlyphSegmenter
from app.glyph_recognition import UnavailableRecognizer, GlyphRecognizer
from app.reading_order import UnknownReadingOrder, ReadingOrderResolver
from app.transliteration import AbstainingTransliterator, Transliterator
from app.translation import AbstainingTranslator, Translator

class Pipeline:
    def __init__(self, detector: RegionDetector = None, segmenter: GlyphSegmenter = None,
                 recognizer: GlyphRecognizer = None, order: ReadingOrderResolver = None,
                 transliterator: Transliterator = None, translator: Translator = None):
        self.detector = detector or ContrastRegionDetector()
        self.segmenter = segmenter or RegionAsCandidate()
        self.recognizer = recognizer or UnavailableRecognizer()
        self.order = order or UnknownReadingOrder()
        self.transliterator = transliterator or AbstainingTransliterator()
        self.translator = translator or AbstainingTranslator()

    def run(self, image: Image.Image, id: str, directory: Path) -> Inscription:
        regions, glyphs = [], []
        for ri, box in enumerate(self.detector.detect(image)):
            ids = []
            for gi, b in enumerate(self.segmenter.segment(image, box)):
                gid = f"r{ri}-g{gi}"
                crop = image.crop((b.x,b.y,b.x+b.width,b.y+b.height))
                crop.save(directory / f"{gid}.png")
                glyphs.append(Glyph(id=gid, bbox=b, crop_url=f"/media/{id}/{gid}.png", candidates=self.recognizer.recognize(crop)))
                ids.append(gid)
            regions.append(TextRegion(id=f"r{ri}", bbox=box, glyph_ids=ids))
        glyphs = self.order.resolve(glyphs)
        transliteration = self.transliterator.transliterate(glyphs)
        return Inscription(id=id, image_url=f"/media/{id}/image.png", width=image.width,
            height=image.height, regions=regions, glyphs=glyphs, transliteration=transliteration,
            translation=self.translator.translate(transliteration),
            warnings=["HEURISTIC: local-contrast region proposals, not confirmed hieroglyphs. Up to 100 regions, ranked by component size.",
                      "Each crop is an entire proposed region; individual glyph segmentation is unavailable. Non-text may be included and faint signs missed.",
                      "No glyph identification, reading order, transliteration or translation is available."])
