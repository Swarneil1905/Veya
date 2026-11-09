"""Opt-in crash metadata with a fixed allowlist and serialized consent changes.

Exception messages, stack locals, task text, paths and arbitrary labels are never
accepted. Upload is an injected host transport, not a model-accessible operation.
"""

import json
import re
import sqlite3
from uuid import uuid4


class CrashReports:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE IF NOT EXISTS consent(id INTEGER PRIMARY KEY, enabled INTEGER)')
            c.execute('INSERT OR IGNORE INTO consent VALUES (1,0)')
            c.execute(
                'CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, payload TEXT NOT NULL)'
            )

    def consent(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Explicit crash reporting consent required')
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('UPDATE consent SET enabled=? WHERE id=1', (int(enabled),))
            if not enabled:
                c.execute('DELETE FROM reports')

    def record(self, *, version, platform, fault, frames):
        if not re.fullmatch(r'\d+\.\d+\.\d+', version) or platform not in {
            'windows',
            'linux',
            'macos',
        }:
            raise ValueError('Bounded build identity required')
        if fault not in {'panic', 'unhandled_exception', 'worker_exit'}:
            raise ValueError('Unknown crash category')
        if not isinstance(frames, list) or len(frames) > 32:
            raise ValueError('At most 32 code-location identifiers are allowed')
        if any(
            not isinstance(f, str) or not re.fullmatch('[a-zA-Z0-9_.:]{1,120}', f) for f in frames
        ):
            raise ValueError('Stack frames must be code identifiers without paths or messages')
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT enabled FROM consent WHERE id=1').fetchone()[0]:
                return None
            if c.execute('SELECT count(*) FROM reports').fetchone()[0] >= 100:
                return None
            identity = uuid4().hex
            payload = dict(version=version, platform=platform, fault=fault, frames=frames)
            c.execute('INSERT INTO reports VALUES (?,?)', (identity, json.dumps(payload)))
        return identity

    def flush(self, send):
        # A consent revocation cannot race between the check and dispatch. The
        # configured sender must have a bounded deadline; no secrets enter reports.
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT enabled FROM consent WHERE id=1').fetchone()[0]:
                return 0
            rows = c.execute('SELECT id,payload FROM reports ORDER BY id LIMIT 100').fetchall()
            for identity, payload in rows:
                send(identity, json.loads(payload))
                c.execute('DELETE FROM reports WHERE id=?', (identity,))
            return len(rows)
