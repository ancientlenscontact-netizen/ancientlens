import hashlib,json,sqlite3
from pathlib import Path
import pytest
from PIL import Image
from app.data.catalog import initialize,connect,ASSETS
from app.data.public_records import load_records

ROOT=Path(__file__).resolve().parents[2]

def fixture(tmp_path):
    data=json.loads((ROOT/'corpus/unas-pilot/records.json').read_text())
    root=tmp_path/'corpus'; (root/'originals').mkdir(parents=True); (root/'images').mkdir()
    a=root/'originals/unas-2017.jpg'; b=root/'images/unas-2017.png'
    Image.new('RGB',(40,30),'tan').save(a)
    with Image.open(a) as im: im.convert('RGB').save(b)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    media=data['tables']['media_records'][0]
    media.update(width=40,height=30,original_sha256=digest(a),normalized_sha256=digest(b))
    data['tables']['text_units'][0]['normalized_sha256']=digest(b)
    p=tmp_path/'records.json'; p.write_text(json.dumps(data))
    return tmp_path/'catalog.db',p,root,data

def test_import_idempotence_preserves_review_and_no_false_alignment(tmp_path):
    db,p,root,data=fixture(tmp_path)
    assert load_records(db,p,root)['status']=='imported'
    c=connect(db); assert c.execute("SELECT count(*) FROM passage_records WHERE id LIKE 'unas-%'").fetchone()[0]==7
    assert c.execute('SELECT count(*) FROM passage_image_links').fetchone()[0]==0
    c.execute("UPDATE classification_assertions SET evidence='Later review note'"); c.commit(); c.close()
    assert load_records(db,p,root)['status']=='already_imported'
    c=connect(db); assert c.execute('SELECT evidence FROM classification_assertions').fetchone()[0]=='Later review note'
    assert c.execute('PRAGMA foreign_key_check').fetchall()==[]; c.close()

@pytest.mark.parametrize('bad',['checksum','path','review','license'])
def test_rejects_untrusted_media_or_promoted_labels(tmp_path,bad):
    db,p,root,data=fixture(tmp_path); m=data['tables']['media_records'][0]
    if bad=='checksum': m['original_sha256']='0'*64
    if bad=='path': m['original_path']='../../outside.jpg'
    if bad=='review': data['tables']['classification_assertions'][0]['status']='reviewed'
    if bad=='license': m['license']='unknown'
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_records(db,p,root)
    assert not db.exists()

def test_import_failure_rolls_back_records(tmp_path):
    db,p,root,data=fixture(tmp_path); data['tables']['passage_records'][0]['monument_id']='missing'
    p.write_text(json.dumps(data))
    with pytest.raises(sqlite3.IntegrityError): load_records(db,p,root)
    c=connect(db); assert c.execute("SELECT count(*) FROM monuments WHERE id NOT LIKE 'cma-%'").fetchone()[0]==0
    assert c.execute('SELECT count(*) FROM public_record_imports').fetchone()[0]==0; c.close()

def test_migration_preserves_v1_data(tmp_path):
    p=tmp_path/'v1.db'; c=connect(p); c.executescript((ASSETS/'schema.sql').read_text())
    c.execute("INSERT INTO sources VALUES ('custom','Custom','https://example.org','2026-09-14','fixture')")
    c.execute("INSERT INTO languages VALUES ('custom','Custom','fixture','custom')"); c.commit(); c.close()
    initialize(p); initialize(p); c=connect(p)
    assert c.execute('SELECT version FROM catalog_version').fetchone()[0]==9
    assert c.execute('SELECT name FROM languages').fetchall()==[('Custom',)]; c.close()

def test_changed_batch_rejected_without_overwriting(tmp_path):
    db,p,root,data=fixture(tmp_path); load_records(db,p,root)
    data['tables']['monuments'][0]['name']='Changed'; p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='Batch changed'): load_records(db,p,root)
    c=connect(db); assert c.execute("SELECT name FROM monuments WHERE id NOT LIKE 'cma-%'").fetchone()[0]=='Pyramid of Unas'; c.close()
