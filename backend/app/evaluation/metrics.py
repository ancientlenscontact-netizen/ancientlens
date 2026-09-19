from app.models import BoundingBox

def iou(a: BoundingBox, b: BoundingBox) -> float:
    width=max(0,min(a.x+a.width,b.x+b.width)-max(a.x,b.x))
    height=max(0,min(a.y+a.height,b.y+b.height)-max(a.y,b.y))
    intersection=width*height
    return intersection/(a.width*a.height+b.width*b.height-intersection)

def match_regions(predictions, references, threshold=0.5):
    """Maximum-cardinality one-to-one matching at an explicit IoU threshold.
    Not average precision: proposals have no calibrated ranked scores.
    """
    if not 0 < threshold <= 1:
        raise ValueError('IoU threshold must be in (0,1]')
    neighbors=[[j for j,b in enumerate(references) if iou(a,b)>=threshold] for a in predictions]
    matched={}
    def augment(i,seen):
        for j in neighbors[i]:
            if j in seen: continue
            seen.add(j)
            if j not in matched or augment(matched[j],seen):
                matched[j]=i
                return True
        return False
    for i in range(len(predictions)): augment(i,set())
    tp=len(matched)
    return {'true_positives':tp,'false_positives':len(predictions)-tp,
            'false_negatives':len(references)-tp}
