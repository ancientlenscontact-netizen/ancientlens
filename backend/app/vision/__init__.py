from typing import Protocol
from PIL import Image
from app.models import BoundingBox

class RegionDetector(Protocol):
    def detect(self, image: Image.Image) -> list[BoundingBox]: ...

class GlyphSegmenter(Protocol):
    def segment(self, image: Image.Image, region: BoundingBox) -> list[BoundingBox]: ...

class MockDetector:
    """Fixed geometry for UI integration; performs NO visual detection."""
    def detect(self, image: Image.Image) -> list[BoundingBox]:
        w, h = image.size
        return [BoundingBox(x=w//10, y=h//4, width=max(1,w*8//10), height=max(1,h//2))]

    def segment(self, image: Image.Image, region: BoundingBox) -> list[BoundingBox]:
        return [BoundingBox(x=region.x+i*region.width//3, y=region.y,
                width=max(1,region.width//4), height=region.height) for i in range(3)]


class ContrastRegionDetector:
    """Bounded local-contrast connected components, NOT a script classifier.

    Proposals can include non-text. Downsampling and filtering may miss small,
    low-contrast or connected signs. Parameters are engineering defaults only.
    """
    def detect(self, image: Image.Image) -> list[BoundingBox]:
        import math
        from PIL import ImageChops, ImageFilter
        gray = image.convert("L")
        gray.thumbnail((640, 640))
        w, h = gray.size
        if min(w, h) < 5:
            return []
        contrast = ImageChops.difference(gray, gray.filter(ImageFilter.GaussianBlur(3)))
        mask = contrast.point(lambda value: 255 if value >= 20 else 0).filter(ImageFilter.MaxFilter(3))
        pixels = bytearray(mask.tobytes())
        components = []
        minimum = max(8, w*h//20000)
        for start in range(w*h):
            if not pixels[start]:
                continue
            pixels[start] = 0
            pending = [start]
            x0, y0 = start % w, start // w
            x1, y1, count = x0, y0, 0
            while pending:
                pos = pending.pop()
                x, y = pos % w, pos // w
                count += 1
                x0, y0, x1, y1 = min(x0,x), min(y0,y), max(x1,x), max(y1,y)
                for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        n = ny*w+nx
                        if pixels[n]:
                            pixels[n] = 0
                            pending.append(n)
            area = (x1-x0+1)*(y1-y0+1)
            if count >= minimum and area <= w*h*0.8:
                components.append((count,x0,y0,x1,y1))
        # Bound response/crop costs; prioritization is size, not confidence.
        proposals = []
        for _,x0,y0,x1,y1 in sorted(components, reverse=True)[:100]:
            left, top = math.floor(x0*image.width/w), math.floor(y0*image.height/h)
            right = min(image.width, math.ceil((x1+1)*image.width/w))
            bottom = min(image.height, math.ceil((y1+1)*image.height/h))
            proposals.append(BoundingBox(x=left,y=top,width=right-left,height=bottom-top))
        return proposals


class RegionAsCandidate:
    """One crop per region; individual glyph segmentation is unavailable."""
    def segment(self, image: Image.Image, region: BoundingBox) -> list[BoundingBox]:
        return [region]
