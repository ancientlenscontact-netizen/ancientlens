from typing import Protocol
from app.models import Inscription, ConfidenceScore

class ConfidenceEstimator(Protocol):
    def estimate(self, inscription: Inscription) -> ConfidenceScore: ...

class UncalibratedConfidence:
    def estimate(self, inscription: Inscription) -> ConfidenceScore:
        return ConfidenceScore(basis="Mock geometry; no statistical inference or calibration")
