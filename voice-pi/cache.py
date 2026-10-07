"""Local SQLite mirror of the datastore's container list, so a spoken
query can be answered without a live round-trip to the cluster — and can
still be answered at all if the shop network to the cluster is down.

Wholesale resync, not incremental: GET /containers has no since= filter
(checked against the real datastore/main.py before building this), and
this dataset is small-parts inventory, not big data — a full replace on
every sync is simple, correct, and plenty fast at this scale.
"""

import logging
import sqlite3
import threading
import time

import requests
from rapidfuzz import fuzz

import config

# Mirrors datastore/main.py's FUZZY_MIN_SCORE/FUZZY_MAX_RESULTS and
# token_set_ratio choice — kept in sync by hand since the cache is a
# separate deployable (a Pi script, not a shared package) from datastore.
_FUZZY_MIN_SCORE = 60
_FUZZY_MAX_RESULTS = 5


def _score(query_text: str, row: dict) -> float:
    # WRatio, not token_set_ratio — see datastore/main.py's _score for the
    # real-hardware STT-mishearing comparison that motivated this choice;
    # kept identical here on purpose.
    text = " ".join(
        v for v in (row.get("code"), row.get("domain"), row.get("locator"), row.get("ai_description")) if v
    )
    return fuzz.WRatio(query_text, text)

log = logging.getLogger("voice-pi.cache")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS containers (
    code TEXT PRIMARY KEY,
    type_prefix TEXT,
    parent_code TEXT,
    domain TEXT,
    locator TEXT,
    ai_description TEXT,
    display_name TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class ContainerCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _fetch(self, api_url: str, timeout: float = 5.0) -> list[dict] | None:
        """Goes through registration's /containers/search with an empty q
        (LIKE '%%' matches everything) rather than datastore's own bulk
        /containers — registration is the externally-exposed API layer
        that already proxies straight to datastore; datastore itself is
        ClusterIP-only by design, and stays that way on purpose. Returns
        None on any network/parse failure."""
        try:
            resp = requests.get(
                f"{api_url}/containers/search", params={"q": ""}, timeout=timeout
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.warning("Cache fetch failed, keeping existing cache: %s", exc)
            return None

    def resync(self, api_url: str, timeout: float = 5.0) -> bool:
        """Pull the full container list and replace the local table in one
        transaction. Returns True on success, False on any network/parse
        failure — callers should treat False as "kept the previous cache,
        network's down or the API's unreachable right now," not a fatal
        error."""
        rows = self._fetch(api_url, timeout)
        if rows is None:
            return False
        self._apply(rows)
        return True

    def _apply(self, rows: list[dict]) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM containers")
                conn.executemany(
                    """INSERT INTO containers
                       (code, type_prefix, parent_code, domain, locator,
                        ai_description, display_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            r.get("code"),
                            r.get("type_prefix"),
                            r.get("parent_code"),
                            r.get("domain"),
                            r.get("locator"),
                            r.get("ai_description"),
                            r.get("display_name"),
                        )
                        for r in rows
                    ],
                )
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_sync', ?)",
                    (str(time.time()),),
                )
                conn.commit()
            finally:
                conn.close()

        log.info("Cache resynced: %d containers", len(rows))

    def search(self, query_text: str, limit: int = 5) -> list[dict]:
        """Same field set the real /containers/search LIKE-matches against:
        code, domain, locator, ai_description — mirrored here so cache
        results and live results behave the same way to whatever calls
        this. Two tiers, mirroring datastore's fuzzy=true path: a literal
        substring hit first, scored/sorted by relevance rather than
        alphabetical; if nothing literally matches, widen to a scored
        fuzzy match over the whole cache instead of reporting nothing —
        spoken queries rarely match stored text word-for-word."""
        like = f"%{query_text}%"
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """SELECT code, type_prefix, parent_code, domain, locator,
                              ai_description, display_name
                       FROM containers
                       WHERE code LIKE ? OR domain LIKE ?
                          OR locator LIKE ? OR ai_description LIKE ?""",
                    (like, like, like, like),
                )
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

                if not rows:
                    cur = conn.execute(
                        """SELECT code, type_prefix, parent_code, domain, locator,
                                  ai_description, display_name
                           FROM containers"""
                    )
                    cols = [c[0] for c in cur.description]
                    all_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                    scored = [(r, _score(query_text, r)) for r in all_rows]
                    scored = [t for t in scored if t[1] >= _FUZZY_MIN_SCORE]
                    scored.sort(key=lambda t: t[1], reverse=True)
                    return [r for r, _s in scored[:_FUZZY_MAX_RESULTS]]

                rows.sort(key=lambda r: _score(query_text, r), reverse=True)
                return rows[:limit]
            finally:
                conn.close()

    def vocabulary_prompt(self) -> str:
        """Whisper's initial_prompt biases decoding toward whatever text
        it's given — feeding it our own container codes and type prefixes
        steers transcription away from mishearing domain jargon (part
        numbers, box codes) as ordinary words. Built fresh from the cache
        each call (cheap local SELECTs) rather than cached once, so it
        stays current as containers get added between resyncs."""
        with self._lock:
            conn = self._connect()
            try:
                prefixes = [
                    r[0] for r in conn.execute(
                        "SELECT DISTINCT type_prefix FROM containers WHERE type_prefix IS NOT NULL"
                    ).fetchall()
                ]
                codes = [r[0] for r in conn.execute("SELECT code FROM containers").fetchall()]
            finally:
                conn.close()
        vocab = ", ".join(sorted(set(prefixes) | set(codes)))
        return f"Small parts inventory. Container codes and types: {vocab}."

    def last_sync_age_seconds(self) -> float | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'last_sync'"
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return time.time() - float(row[0])


# How many newly-registered containers should force an early resync
# instead of waiting out interval_seconds — catches a registration burst
# (e.g. scanning a shelf's worth of new parts) without waiting up to 5
# minutes for the vocabulary/cache to catch up. Checked on every poll
# tick, so it's tuned to this inventory's current scale (~36 containers):
# high enough that a single new item doesn't trigger a resync every poll,
# low enough that a real batch gets picked up well before the timer would.
_GROWTH_RESYNC_THRESHOLD = 5

# How often to check for growth — cheap: it's the same request a full
# resync makes, just decided against before committing it to the DB.
_POLL_SECONDS = 20


def start_background_resync(cache: ContainerCache, datastore_url: str, interval_seconds: int):
    """Fire-and-forget daemon thread: resync now, then poll every
    _POLL_SECONDS for container-count growth, forcing an early full
    resync once it's grown by _GROWTH_RESYNC_THRESHOLD since the last
    one. interval_seconds remains a fallback ceiling on staleness even
    with no growth (e.g. a container's fields changed without the total
    count changing). A plain thread+sleep loop is the right amount of
    machinery for a single-process Pi service — no scheduler library
    needed."""

    def loop():
        last_synced_count = None
        last_sync_time = 0.0
        while True:
            rows = cache._fetch(datastore_url)
            if rows is not None:
                now = time.time()
                count = len(rows)
                grown = (
                    last_synced_count is not None
                    and count - last_synced_count >= _GROWTH_RESYNC_THRESHOLD
                )
                due = last_synced_count is None or now - last_sync_time >= interval_seconds
                if grown:
                    log.info(
                        "%d new containers since last sync (>= %d) — resyncing early",
                        count - last_synced_count, _GROWTH_RESYNC_THRESHOLD,
                    )
                if grown or due:
                    cache._apply(rows)
                    last_synced_count = count
                    last_sync_time = now
            time.sleep(_POLL_SECONDS)

    t = threading.Thread(target=loop, daemon=True, name="cache-resync")
    t.start()
    return t
