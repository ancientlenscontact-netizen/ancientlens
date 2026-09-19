from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.community import create_community_app
from app.data.catalog import initialize


def configure(monkeypatch, tmp_path):
    catalog = tmp_path / 'catalog.sqlite3'; initialize(catalog)
    monkeypatch.setenv('ANCIENTLENS_SERVICE_MODE', 'community')
    monkeypatch.setenv('ANCIENTLENS_CATALOG_PATH', str(catalog))
    monkeypatch.setenv('ANCIENTLENS_ALLOWED_ORIGINS', 'https://ancientlens.example')
    monkeypatch.setenv('ANCIENTLENS_SECURE_COOKIES', '1')
    return catalog


def test_missing_catalog_refuses_start(monkeypatch, tmp_path):
    catalog = configure(monkeypatch, tmp_path); catalog.unlink()
    with pytest.raises(ValueError, match='existing absolute catalog'): create_community_app()


def test_production_routes_and_host_boundary(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    # Use the actual production build; no sensitive data is served from this directory.
    if not (Path(__file__).resolve().parents[2] / 'frontend/dist/index.html').exists():
        pytest.skip('Build frontend to run deployment integration check')
    with TestClient(create_community_app(), base_url='https://ancientlens.example') as client:
        assert client.get('/').status_code == 200
        assert 'text/html' in client.get('/').headers['content-type']
        assert client.get('/api/features').json()['image_inspector'] is False
        assert client.get('/api/health').json()['mode'] == 'community'
        for path in ['/api/unknown', '/api/inscriptions', '/media/image.png', '/.local/language-catalog.sqlite3']:
            assert client.get(path).status_code == 404
        assert client.get('/api/health', headers={'host': 'attacker.example'}).status_code == 400
