import io
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from app.api import create_app
from app.models import ConfidenceScore
from pydantic import ValidationError

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path))

def image_bytes(size=(120,90)):
    buffer=io.BytesIO()
    image=Image.new("RGB",size,"white")
    if min(size)>30:
        ImageDraw.Draw(image).rectangle((20,20,35,50),fill="black")
    image.save(buffer,format="PNG")
    return buffer.getvalue()

def test_upload_round_trip(client):
    response=client.post("/api/inscriptions",files={"file":("../../bad.png",image_bytes(),"image/png")})
    assert response.status_code==201
    data=response.json()
    assert data["mode"]=="heuristic"
    assert len(data["glyphs"])>=1
    assert data["translation"]["text"] is None
    assert data["translation"]["confidence"]["value"] is None
    assert client.get('/api/inscriptions/'+data['id']).json()==data
    assert client.get(data['image_url']).status_code==200
    for glyph in data['glyphs']:
        assert glyph['candidates']==[]
        assert glyph['reading_order_index'] is None
        b=glyph['bbox']
        assert b['x']+b['width']<=data['width']
        assert b['y']+b['height']<=data['height']
        crop=Image.open(io.BytesIO(client.get(glyph['crop_url']).content))
        assert crop.size==(b['width'],b['height'])

@pytest.mark.parametrize('payload',[b'',b'not an image',b'<svg></svg>'])
def test_invalid_image(client,payload):
    assert client.post('/api/inscriptions',files={'file':('x.png',payload,'image/png')}).status_code==415

def test_oversize(client):
    assert client.post('/api/inscriptions',files={'file':('x.png',b'x'*(10*1024*1024+1))}).status_code==413

def test_missing(client):
    assert client.get('/api/inscriptions/missing').status_code==404
    assert client.post('/api/inscriptions').status_code==422

def test_tiny_image(client):
    data=client.post('/api/inscriptions',files={'file':('x.png',image_bytes((1,1)))}).json()
    assert data['glyphs']==[]

def test_confidence_validation():
    with pytest.raises(ValidationError):
        ConfidenceScore(value=1.1)


def test_uniform_has_no_proposals(client):
    buffer=io.BytesIO()
    Image.new('RGB',(300,200),'gray').save(buffer,format='PNG')
    data=client.post('/api/inscriptions',files={'file':('blank.png',buffer.getvalue())}).json()
    assert data['regions']==[]
    assert data['translation']['text'] is None


def test_proposals_follow_pixels():
    from app.vision import ContrastRegionDetector
    detector=ContrastRegionDetector()
    image=Image.new('RGB',(300,200),'white')
    ImageDraw.Draw(image).rectangle((40,50,60,90),fill='black')
    first=detector.detect(image)
    assert len(first)==1
    box=first[0]
    assert box.x<=40 and box.x+box.width>=60
    shifted=Image.new('RGB',(300,200),'white')
    ImageDraw.Draw(shifted).rectangle((140,50,160,90),fill='black')
    assert detector.detect(shifted)[0].x-box.x==100


def test_large_image_bounds():
    from app.vision import ContrastRegionDetector
    image=Image.new('RGB',(2000,1000),'white')
    ImageDraw.Draw(image).rectangle((1800,800,1900,950),fill='black')
    boxes=ContrastRegionDetector().detect(image)
    assert boxes
    assert all(b.x+b.width<=2000 and b.y+b.height<=1000 for b in boxes)
