import pytest
from app.data.corpus import select_asset,MAX_IMAGE_BYTES

def record():
    return {'share_license_status':'CC0','culture':['Egypt, Middle Kingdom'],'images':{'print':{'url':'https://openaccess-cdn.clevelandart.org/example.jpg','filesize':'100'}}}

def test_only_explicit_cc0():
    r=record();assert select_asset(r).startswith('https://')
    r['share_license_status']='Copyrighted'
    with pytest.raises(ValueError,match='CC0'):select_asset(r)

def test_forgery_and_host():
    r=record();r['culture']=['Egypt or modern forgery']
    with pytest.raises(ValueError,match='forgery'):select_asset(r)
    r=record();r['images']['print']['url']='https://example.org/a.jpg'
    with pytest.raises(ValueError,match='host'):select_asset(r)

def test_acquisition_limit():
    r=record();r['images']['print']['filesize']=MAX_IMAGE_BYTES+1
    with pytest.raises(ValueError,match='cap'):select_asset(r)
