import io
import os
import shutil
import warnings
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from app.data import Repository
from app.api.contributions import contribution_router
from app.models import Inscription
from app.pipeline import Pipeline
from app.api.limits import BodyLimit
from urllib.parse import urlsplit

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000

def create_app(data_dir: Path = None, pipeline: Pipeline = None) -> FastAPI:
    directory = data_dir or Path(os.environ.get("ANCIENTLENS_DATA_DIR", ".local"))
    mode=os.environ.get('ANCIENTLENS_SERVICE_MODE','local')
    if mode not in ('local','community'): raise ValueError('Unknown service mode')
    inspector=mode=='local'
    if not inspector:
        origins=os.environ.get('ANCIENTLENS_ALLOWED_ORIGINS','').split(',')
        if os.environ.get('ANCIENTLENS_SECURE_COOKIES')!='1' or not all(
            urlsplit(origin).scheme=='https' and urlsplit(origin).netloc and not urlsplit(origin).path
            and not urlsplit(origin).query and not urlsplit(origin).fragment and not urlsplit(origin).username
            for origin in origins):
            raise ValueError('Community mode requires Secure cookies and explicit HTTPS origins')
    app = FastAPI(title="AncientLens", version="0.1.0")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # FastAPI validation otherwise echoes rejected input, including passwords.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
            for item in error.errors()]})

    catalog_path = (data_dir / 'language-catalog.sqlite3') if data_dir else Path(
        os.environ.get('ANCIENTLENS_CATALOG_PATH', str(Path(__file__).resolve().parents[3] / '.local/language-catalog.sqlite3')))
    app.include_router(contribution_router(catalog_path))
    app.add_middleware(BodyLimit,image_inspector=inspector)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "heuristic" if inspector else "community"}

    @app.get('/api/features')
    def features(): return {'image_inspector':inspector,'service_mode':mode}

    if not inspector:
        return app
    media=directory/'media'
    media.mkdir(parents=True,exist_ok=True)
    repository=Repository(directory)
    processor=pipeline or Pipeline()
    app.mount('/media',StaticFiles(directory=media),name='media')

    @app.get("/api/inscriptions/{id}", response_model=Inscription)
    def get_inscription(id: str):
        result = repository.get(id)
        if result is None:
            raise HTTPException(404, "Inscription not found")
        return result

    @app.post("/api/inscriptions", response_model=Inscription, status_code=201)
    def upload(file: UploadFile):
        try:
            raw = file.file.read(MAX_BYTES + 1)
        finally:
            file.file.close()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 10 MiB")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if source.format not in {"JPEG", "PNG", "WEBP"}:
                        raise HTTPException(415, "Use JPEG, PNG or WebP")
                    if source.width * source.height > MAX_PIXELS:
                        raise HTTPException(413, "Image exceeds 20 megapixels")
                    image = ImageOps.exif_transpose(source).convert("RGB")
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(413, "Image dimensions are too large")
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(415, "Invalid or damaged image")
        id = str(uuid4())
        target = media / id
        target.mkdir()
        try:
            image.save(target / "image.png")
            result = processor.run(image, id, target)
            repository.save(result)
            return result
        except Exception:
            shutil.rmtree(target)
            raise
    return app
