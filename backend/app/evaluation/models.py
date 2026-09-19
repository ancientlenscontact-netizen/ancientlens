from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
from app.models import BoundingBox

class Review(BaseModel):
    status: Literal['unreviewed','expert_reviewed'] = 'unreviewed'
    reviewer: Optional[str] = None
    evidence: Optional[str] = None
    complete_regions: bool = False
    @model_validator(mode='after')
    def verified(self):
        if self.status == 'expert_reviewed' and (not self.reviewer or not self.evidence):
            raise ValueError('Expert review requires reviewer and evidence reference')
        return self

class Sample(BaseModel):
    id: str
    object_id: str
    image_path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source_url: str
    rights: str
    rights_url: str
    split: Literal['review','train','validation','test'] = 'review'
    regions: list[BoundingBox] = Field(default_factory=list)
    review: Review = Field(default_factory=Review)
    @model_validator(mode='after')
    def bounds(self):
        if any(b.x+b.width > self.width or b.y+b.height > self.height for b in self.regions):
            raise ValueError('Reference region exceeds image bounds')
        return self
