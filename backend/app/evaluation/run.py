import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from app.evaluation.models import Sample
from app.evaluation.metrics import match_regions
from app.vision import ContrastRegionDetector

def evaluate(manifest: Path):
    raw=json.loads(manifest.read_text())
    samples=[Sample.model_validate(s) for s in raw['samples']]
    seen_ids=set();splits={}
    for sample in samples:
        if sample.id in seen_ids: raise ValueError('Duplicate sample ID')
        seen_ids.add(sample.id)
        for key in (sample.object_id,sample.sha256):
            if key in splits and splits[key]!=sample.split:
                raise ValueError('Object or image leaks across splits')
            splits[key]=sample.split
    results=[];total={'true_positives':0,'false_positives':0,'false_negatives':0};scored=0
    for sample in samples:
        path=(manifest.parent/sample.image_path).resolve()
        if manifest.parent.resolve() not in path.parents: raise ValueError('Image path escapes dataset')
        payload=path.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=sample.sha256: raise ValueError('Image checksum changed')
        with Image.open(path) as image:
            if image.size!=(sample.width,sample.height): raise ValueError('Image dimensions changed')
            predictions=ContrastRegionDetector().detect(image)
        eligible=(sample.review.status=='expert_reviewed' and sample.review.complete_regions and sample.split=='test')
        counts=match_regions(predictions,sample.regions) if eligible else None
        if counts:
            scored+=1
            for key,value in counts.items():total[key]+=value
        results.append({'id':sample.id,'proposal_count':len(predictions),
            'proposals':[b.model_dump() for b in predictions],
            'metrics':counts,'status':'scored' if eligible else 'awaiting_complete_expert_test_labels'})
    tp,fp,fn=total.values()
    return {'detector':'local-contrast-v1','iou_threshold':0.5,'scored_images':scored,
        'precision':tp/(tp+fp) if scored and tp+fp else None,
        'recall':tp/(tp+fn) if scored and tp+fn else None,
        'counts':total if scored else None,'samples':results,
        'limitation':'Region localization only; no glyph recognition or translation metric. Review flags record supplied provenance, not independent verification of expertise.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=evaluate(args.manifest)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Evaluated {len(report['samples'])} images; {report['scored_images']} eligible for accuracy scoring")
