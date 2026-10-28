"""Transactional append-only facts; derived status files are replaceable views."""
import hashlib
import json
import sqlite3
from pathlib import Path

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def atomic(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(canonical(value))
    tmp.replace(path)

class Store:
    def __init__(self, output):
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.output / 'supervisor.sqlite', timeout=20)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS facts (kind TEXT, id TEXT, hash TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
        for operation in ('UPDATE', 'DELETE'):
            self.db.execute(f"CREATE TRIGGER IF NOT EXISTS deny_{operation.lower()} BEFORE {operation} ON facts BEGIN SELECT RAISE(ABORT, 'Facts are immutable'); END")
        self.db.commit()

    def put(self, kind, identity, value):
        raw = canonical(value).decode(); h = hashlib.sha256(raw.encode()).hexdigest()
        old = self.db.execute('SELECT hash FROM facts WHERE kind=? AND id=?', (kind, str(identity))).fetchone()
        if old:
            if old[0] != h:
                raise ValueError(f'Immutable fact changed: {kind}/{identity}')
            return False
        self.db.execute('INSERT INTO facts VALUES (?,?,?,?)', (kind, str(identity), h, raw))
        return True

    def get(self, kind, identity):
        r = self.db.execute('SELECT body,hash FROM facts WHERE kind=? AND id=?', (kind, str(identity))).fetchone()
        if r is None:
            return None
        if hashlib.sha256(r[0].encode()).hexdigest() != r[1]:
            raise ValueError('Database fact checksum differs')
        return json.loads(r[0])

    def all(self, kind):
        ids = [r[0] for r in self.db.execute('SELECT id FROM facts WHERE kind=? ORDER BY id', (kind,))]
        return [self.get(kind, i) for i in ids]

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.close()
