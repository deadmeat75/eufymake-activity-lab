"""Incremental SQLite persistence outside the integration's installed files."""
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3


class Journal:
    def __init__(self, hass, entry_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', entry_id):
            raise ValueError('Invalid entry identity')
        self.hass = hass
        self.path = Path(hass.config.path('eufymake_activity_lab', entry_id + '.sqlite3'))
        self.lock = asyncio.Lock()
        self.versions = {}

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)')
        conn.commit()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def load(self):
        with self.connect() as conn:
            row = conn.execute('SELECT data FROM metadata WHERE id=1').fetchone()
            saved = json.loads(row[0]) if row else {}
            events = [json.loads(row[0]) for row in conn.execute('SELECT data FROM events ORDER BY seq')]
            saved['events'] = events
            self.versions = {e['id']: e.get('revision', 1) for e in events}
            return saved

    def save(self, data):
        events = data['events']
        current = {e['id']: e.get('revision', 1) for e in events}
        changed = [e for e in events if self.versions.get(e['id']) != e.get('revision', 1)]
        removed = set(self.versions) - set(current)
        metadata = {k:v for k,v in data.items() if k != 'events'}
        with self.connect() as conn:
            conn.executemany('INSERT INTO events(id,data) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                             [(e['id'], json.dumps(e,allow_nan=False)) for e in changed])
            conn.executemany('DELETE FROM events WHERE id=?',[(eid,) for eid in removed])
            conn.execute('INSERT INTO metadata(id,data) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                         (json.dumps(metadata,allow_nan=False),))
        self.versions = current

    async def async_load(self):
        async with self.lock:
            return await self.hass.async_add_executor_job(self.load)

    async def async_save(self, data):
        async with self.lock:
            await self.hass.async_add_executor_job(self.save, data)

    async def async_remove(self):
        async with self.lock:
            await self.hass.async_add_executor_job(self.remove)

    def remove(self):
        for suffix in ('', '-wal', '-shm'):
            Path(str(self.path)+suffix).unlink(missing_ok=True)
        self.versions.clear()
