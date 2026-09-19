"""Extensible language catalog, separate from immutable inference snapshots."""
import argparse
import json
import sqlite3
from pathlib import Path

ASSETS = Path(__file__).parent / 'catalog'

def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    return db

def upgrade(db):
    version = db.execute('SELECT version FROM catalog_version').fetchall()
    if version not in ([(1,)], [(2,)], [(3,)], [(4,)], [(5,)], [(6,)], [(7,)], [(8,)], [(9,)]):
        raise ValueError('Unsupported catalog version')
    for target in range(version[0][0] + 1, 10):
        db.executescript('BEGIN IMMEDIATE;\n' + (ASSETS / f'migration-{target:03d}.sql').read_text())
        db.commit()
    from app.data.curated import seed
    seed(db)

def initialize(path, assets=ASSETS):
    """Create once atomically; preserve all existing catalog and review records."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='catalog_version'").fetchone()
        if exists:
            upgrade(db)
            return
        if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
            raise ValueError('Refusing to initialize a nonempty unrelated database')
        seed = json.loads((assets / 'seed.json').read_text())
        db.executescript('BEGIN IMMEDIATE;\n' + (assets / 'schema.sql').read_text())
        for table, columns in [
            ('sources', ['id','title','url','accessed_on','note']),
            ('languages', ['id','name','description','source_id']),
            ('varieties', ['id','language_id','name','kind','parent_id','source_id','note']),
            ('scripts', ['id','name','source_id','note']),
            ('writing_systems', ['id','language_id','variety_id','script_id','source_id','note']),
            ('research_priorities', ['writing_system_id','priority','reason']),
        ]:
            sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
            db.executemany(sql, [[row[c] for c in columns] for row in seed[table]])
        tasks = ('localization','recognition','reading_order','transliteration','translation','known_inscription_retrieval')
        db.executemany('INSERT INTO capabilities(writing_system_id,task) VALUES (?,?)',
                       [(r['id'], task) for r in seed['writing_systems'] for task in tasks])
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Invalid catalog relationships')
        db.commit()
        upgrade(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def summary(path):
    db = connect(path)
    try:
        return {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in
                ('languages','varieties','scripts','writing_systems','classification_assertions')}
    finally:
        db.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    initialize(args.database)
    print(json.dumps(summary(args.database), indent=2))
