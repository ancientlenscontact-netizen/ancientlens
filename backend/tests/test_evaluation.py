import hashlib,json
import pytest
from PIL import Image
from app.models import BoundingBox
from app.evaluation.metrics import iou,match_regions
from app.evaluation.models import Review
from app.evaluation.run import evaluate

def box(x=0):return BoundingBox(x=x,y=0,width=10,height=10)

def test_matching_does_not_double_count():
    assert iou(box(),box())==1
    assert iou(box(),box(20))==0
    assert match_regions([box(),box()],[box()])=={'true_positives':1,'false_positives':1,'false_negatives':0}

def test_missing_detection():
    assert match_regions([],[box()])['false_negatives']==1

def test_review_needs_provenance():
    with pytest.raises(ValueError):Review(status='expert_reviewed')

def fixture_manifest(tmp_path):
    path=tmp_path/'blank.png';Image.new('RGB',(40,40),'white').save(path)
    sample=dict(id='one',object_id='object-one',image_path='blank.png',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width=40,height=40,source_url='https://example.org',rights='test fixture',rights_url='https://example.org',split='test')
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'samples':[sample]}))
    return manifest,sample

def test_unreviewed_is_not_zero_accuracy(tmp_path):
    manifest,_=fixture_manifest(tmp_path)
    result=evaluate(manifest)
    assert result['scored_images']==0 and result['precision'] is None and result['counts'] is None

def test_checksum_and_leakage(tmp_path):
    manifest,sample=fixture_manifest(tmp_path)
    other={**sample,'id':'two','split':'train'}
    manifest.write_text(json.dumps({'samples':[sample,other]}))
    with pytest.raises(ValueError,match='leaks'):evaluate(manifest)
    sample['sha256']='0'*64
    manifest.write_text(json.dumps({'samples':[sample]}))
    with pytest.raises(ValueError,match='checksum'):evaluate(manifest)

def test_reviewed_negative(tmp_path):
    manifest,sample=fixture_manifest(tmp_path)
    sample['review']={'status':'expert_reviewed','reviewer':'Synthetic test fixture','evidence':'Unit test only, not a real expert','complete_regions':True}
    manifest.write_text(json.dumps({'samples':[sample]}))
    result=evaluate(manifest)
    assert result['scored_images']==1
    assert result['counts']['false_positives']==0
    assert result['recall'] is None
