from typing import Optional, Literal
from pydantic import BaseModel, Field

class ConfidenceScore(BaseModel):
    value: Optional[float] = Field(default=None, ge=0, le=1)
    calibrated: bool = False
    basis: str = "Not evaluated"

class SourceReference(BaseModel):
    title: str
    uri: str
    license: Optional[str] = None

class BoundingBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

class GardinerSign(BaseModel):
    code: str
    meanings: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)

class GlyphCandidate(BaseModel):
    sign: GardinerSign
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)

class Glyph(BaseModel):
    id: str
    bbox: BoundingBox
    crop_url: str
    candidates: list[GlyphCandidate] = Field(default_factory=list)
    orientation: Optional[str] = None
    reading_order_index: Optional[int] = None
    status: Literal["high_confidence", "uncertain", "missing", "unidentified"] = "unidentified"
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)

class TextRegion(BaseModel):
    id: str
    bbox: BoundingBox
    glyph_ids: list[str]
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)

class Transliteration(BaseModel):
    text: Optional[str] = None
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    uncertain_segments: list[str] = Field(default_factory=list)

class TranslationAlternative(BaseModel):
    text: str
    confidence: ConfidenceScore
    sources: list[SourceReference] = Field(default_factory=list)

class Translation(BaseModel):
    text: Optional[str] = None
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    alternatives: list[TranslationAlternative] = Field(default_factory=list)
    uncertain_segments: list[str] = Field(default_factory=list)
    missing_segments: list[str] = Field(default_factory=list)
    reasoning_metadata: list[str] = Field(default_factory=list)

class Inscription(BaseModel):
    id: str
    schema_version: str = "1.0"
    script: str = "egyptian_hieroglyphs"
    image_url: str
    width: int
    height: int
    mode: Literal["mock", "heuristic"] = "heuristic"
    regions: list[TextRegion]
    glyphs: list[Glyph]
    transliteration: Transliteration
    translation: Translation
    warnings: list[str]
