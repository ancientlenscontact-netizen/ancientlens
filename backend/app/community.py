"""Explicit deployment entry point for the community application."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api import create_app


def create_community_app():
    if os.environ.get('ANCIENTLENS_SERVICE_MODE') != 'community':
        raise ValueError('Deployment requires explicit community mode')
    catalog = Path(os.environ.get('ANCIENTLENS_CATALOG_PATH', ''))
    if not catalog.is_absolute() or not catalog.is_file() or catalog.is_symlink():
        raise ValueError('Deployment requires an existing absolute catalog path on persistent storage')
    frontend = Path(__file__).resolve().parents[2] / 'frontend/dist'
    if not (frontend / 'index.html').is_file():
        raise ValueError('Build the frontend before starting the community application')
    app = create_app()
    hosts = [urlsplit(origin).hostname for origin in os.environ['ANCIENTLENS_ALLOWED_ORIGINS'].split(',')]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts, www_redirect=False)
    # API routes precede this mount. There is no fallback returning HTML for unknown API paths.
    app.mount('/', StaticFiles(directory=frontend, html=True, follow_symlink=False), name='frontend')
    return app
