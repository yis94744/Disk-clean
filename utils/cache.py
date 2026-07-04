# -*- coding: utf-8 -*-
"""SQLite cache for flat scan results."""
import os, sqlite3, json, time, zlib

class ScanCache:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "scan_cache.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS scans ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "root_path TEXT NOT NULL,"
                "scan_time REAL NOT NULL,"
                "data_json TEXT NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_root ON scans(root_path)")
            conn.commit()

    def save(self, file_list, root_path):
        data = [{"p": f.path, "n": f.name, "s": f.size, "mt": f.mtime, "e": f.ext} for f in file_list]
        json_str = json.dumps(data, separators=(",", ":"))
        if len(json_str) > 1024:
            compressed = zlib.compress(json_str.encode("utf-8"), level=1)
            json_str = "Z:" + compressed.hex()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("DELETE FROM scans WHERE root_path = ?", (root_path,))
            conn.execute(
                "INSERT INTO scans (root_path, scan_time, data_json) VALUES (?,?,?)",
                (root_path, time.time(), json_str)
            )
            conn.commit()

    def load(self, root_path, max_age=3600):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute(
                "SELECT scan_time, data_json FROM scans WHERE root_path = ? ORDER BY scan_time DESC LIMIT 1",
                (root_path,)
            ).fetchone()
            if row and (time.time() - row[0]) < max_age:
                json_str = row[1]
                if json_str.startswith("Z:"):
                    try:
                        json_str = zlib.decompress(bytes.fromhex(json_str[2:])).decode("utf-8")
                    except Exception:
                        return None
                data = json.loads(json_str)
                from core.scanner import ScanNode
                return [ScanNode(d["p"], d["n"], d["s"], d["mt"], d.get("e", "")) for d in data]
        return None

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM scans")
            conn.execute("VACUUM")
            conn.commit()
