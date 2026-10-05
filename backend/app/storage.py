import json
import sqlite3
import threading
from datetime import datetime, timezone
from .schemas import Scan, TireFields


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.db:
            self.db.executescript(
                """PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS corrections(id INTEGER PRIMARY KEY, scan_id TEXT REFERENCES scans(id) ON DELETE CASCADE, created_at TEXT, fields TEXT, latest_message_id INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, scan_id TEXT REFERENCES scans(id) ON DELETE CASCADE, role TEXT, content TEXT);
            CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, document TEXT, page INTEGER, text TEXT, source_url TEXT);
            """
            )
            columns = {r[1] for r in self.db.execute("PRAGMA table_info(corrections)")}
            if "latest_message_id" not in columns:
                self.db.execute(
                    "ALTER TABLE corrections ADD COLUMN latest_message_id INTEGER DEFAULT 0"
                )
                self.db.execute(
                    "UPDATE corrections SET latest_message_id=COALESCE((SELECT MAX(id) FROM messages WHERE messages.scan_id=corrections.scan_id),0)"
                )

    def save(self, scan):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO scans VALUES (?,?)", (scan.id, scan.model_dump_json())
            )

    def get(self, id):
        with self.lock:
            row = self.db.execute(
                "SELECT payload FROM scans WHERE id=?", (id,)
            ).fetchone()
            if not row:
                return None
            scan = Scan.model_validate_json(row[0])
            scan.messages = [
                dict(r)
                for r in self.db.execute(
                    "SELECT role,content FROM messages WHERE scan_id=? ORDER BY id",
                    (id,),
                )
            ]
            return scan

    def page(self, page, size):
        with self.lock:
            total = self.db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
            rows = self.db.execute(
                "SELECT id FROM scans ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (size, (page - 1) * size),
            ).fetchall()
            return [self.get(r[0]) for r in rows], total

    def correct(self, id, fields):
        with self.lock, self.db:
            scan = self.get(id)
            if scan is None:
                return None
            scan.fields = fields
            scan.correction_count += 1
            # Evidence is re-retrieved by the API, never reused after correction.
            scan.references = []
            self.db.execute(
                "UPDATE scans SET payload=? WHERE id=?", (scan.model_dump_json(), id)
            )
            latest = self.db.execute(
                "SELECT COALESCE(MAX(id),0) FROM messages WHERE scan_id=?", (id,)
            ).fetchone()[0]
            self.db.execute(
                "INSERT INTO corrections(scan_id,created_at,fields,latest_message_id) VALUES (?,?,?,?)",
                (
                    id,
                    datetime.now(timezone.utc).isoformat(),
                    fields.model_dump_json(),
                    latest,
                ),
            )
            # Old chat used superseded fields; retain it in DB but exclude it from generation context.
            return scan

    def context(self, id):
        """Recent conversation for this scan's current corrected-field revision."""
        with self.lock:
            floor = self.db.execute(
                "SELECT COALESCE(MAX(latest_message_id),0) FROM corrections WHERE scan_id=?",
                (id,),
            ).fetchone()[0]
            return [
                dict(r)
                for r in self.db.execute(
                    "SELECT role,content FROM (SELECT id,role,content FROM messages WHERE scan_id=? AND id>? ORDER BY id DESC LIMIT 8) ORDER BY id",
                    (id, floor),
                )
            ]

    def message(self, id, role, content):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO messages(scan_id,role,content) VALUES (?,?,?)",
                (id, role, content),
            )

    def delete(self, id):
        with self.lock, self.db:
            return self.db.execute("DELETE FROM scans WHERE id=?", (id,)).rowcount > 0

    def chunks(self):
        with self.lock:
            return [
                dict(r) for r in self.db.execute("SELECT * FROM chunks ORDER BY id")
            ]

    def add_chunks(self, chunks):
        with self.lock, self.db:
            self.db.executemany(
                "INSERT OR IGNORE INTO chunks VALUES (:id,:document,:page,:text,:source_url)",
                chunks,
            )
