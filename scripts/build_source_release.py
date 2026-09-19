"""Stage an allowlisted public source snapshot, without private operator Git history."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='2026-09-19.1'
FILES=['corpus/unas-pilot/records.json','README.md','LICENSE','LICENSING.md','CONTRIBUTING.md','SECURITY.md','.gitignore','backend/requirements.txt','backend/requirements.lock.txt','frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/tsconfig.json','frontend/vite.config.ts','frontend/public/map-land.svg','scripts/build_collection.py','scripts/check_collection.py','scripts/collection_selection.json','scripts/build_dataset_release.py','scripts/build_source_release.py','docs/DATASET.md','docs/PUBLIC_RELEASE.md','docs/SELF_HOSTING.md']
DIRS=['backend/app','backend/tests','frontend/src','frontend/public/curated','frontend/public/maps']

def stage(target):
    if target.exists():raise ValueError('Choose a new empty staging path')
    target.mkdir(parents=True)
    files=[ROOT/name for name in FILES]
    for directory in DIRS:
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc'))
    files.extend(p for p in (ROOT/'frontend/public').glob('*.html'))
    for src in files:
        if src.is_symlink():raise ValueError('Symlink refused')
        rel=src.relative_to(ROOT)
        if any(x in rel.parts for x in ['.local','.git','node_modules','.venv']):raise ValueError('Private path refused')
        dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    # The public sample must not inherit the maintainer's private bucket name.
    config=target/'backend/app/data/configure_offdevice.py'
    text=config.read_text();start=text.index("REPOSITORY=");end=text.index('\n',start)
    config.write_text(text[:start]+"REPOSITORY='s3:https://s3.example.invalid/your-private-bucket/restic'"+text[end:])
    return target

def build(target):
    stage(target)
    out=ROOT/'frontend/public/releases';out.mkdir(exist_ok=True)
    archive=out/f'ancientlens-source-{VERSION}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file():
                info=zipfile.ZipInfo('ancientlens/'+p.relative_to(target).as_posix(),(2026,9,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
                z.writestr(info,p.read_bytes())
    (out/f'{archive.stem}.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(f'Staged public source at {target}; {archive.stat().st_size} archive bytes')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);build(p.parse_args().stage.resolve())
