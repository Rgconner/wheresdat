"""Turns transcribed query text into a spoken answer: search the local
cache first (fast, works offline), fall back to a live datastore query
only when the cache comes back empty and the network's actually up —
then walk the parent_code chain so the answer is a real location trail,
not just a bare container code.
"""

import logging

import requests

import config
from cache import ContainerCache

log = logging.getLogger("voice-pi.query")

# Literal, exact-phrase trigger for hearing the rest of the last search's
# matches — deliberately not fuzzy-matched like content queries are.
# Voice commands need to be predictable; spoken searches don't.
MORE_MATCHES_PHRASE = "more matches"

# Remaining (unspoken) matches from the last answer(), and how many there
# were in total — module-level since voice-pi is a single-process, single
# main-loop app with no concurrent queries to keep separate.
_pending_matches: list[dict] = []
_pending_total = 0


def _live_search(query_text: str, timeout: float = 3.0) -> list[dict]:
    try:
        resp = requests.get(
            f"{config.API_URL}/containers/search",
            params={"q": query_text, "fuzzy": "true"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.info("Live fallback search unavailable: %s", exc)
        return []


def _label(container: dict) -> str:
    # code, not locator/display_name: in this dataset locator is populated
    # from product-title text at scan time (barcode/vision lookup) — it
    # describes what's in the container, not where it is. code is the only
    # field guaranteed to be a physical location: it's what label-maker
    # actually prints on the sticker attached to the box (confirmed against
    # label-maker/main.py, which labels by code).
    return container.get("code") or "unlabeled container"


def _location_trail(cache: ContainerCache, container: dict, max_hops: int = 6) -> list[str]:
    """Walks parent_code upward using the local cache (already has the full
    container set from the last resync), building the chain from the found
    item up to its top-level container."""
    trail = [_label(container)]
    current = container
    seen = {current.get("code")}
    for _ in range(max_hops):
        parent_code = current.get("parent_code")
        if not parent_code or parent_code in seen:
            break
        matches = cache.search(parent_code, limit=1)
        parent = next((m for m in matches if m.get("code") == parent_code), None)
        if parent is None:
            break
        trail.append(_label(parent))
        seen.add(parent_code)
        current = parent
    return trail


MAX_DESCRIPTION_WORDS = 25


def _trim_description(text: str) -> str:
    # locator/ai_description are often scanned-in product titles (see
    # _label's comment) — some run 50+ words including piece counts and
    # warning labels, which is fine to read on a screen but painful to
    # sit through spoken aloud before ever hearing the actual box number.
    words = text.split()
    if len(words) <= MAX_DESCRIPTION_WORDS:
        return text
    return " ".join(words[:MAX_DESCRIPTION_WORDS])


def _format_match(cache: ContainerCache, container: dict) -> str:
    # What it is, for confirmation — separate from where it is (the code
    # trail below), since locator/ai_description describe contents, not
    # physical location.
    what = container.get("locator") or container.get("ai_description") or _label(container)
    what = _trim_description(what)
    trail = _location_trail(cache, container)
    return f"{what}. In box " + " inside box ".join(trail)


def answer(cache: ContainerCache, query_text: str) -> str:
    global _pending_matches, _pending_total

    if not query_text:
        return "I didn't catch that."

    if query_text.strip().lower() == MORE_MATCHES_PHRASE:
        if not _pending_matches:
            if _pending_total:
                return "That was all the matches."
            return "There's nothing more to hear — ask about something first."
        nxt = _pending_matches.pop(0)
        spoken = _format_match(cache, nxt)
        log.info("More matches: %s (%d left)", spoken, len(_pending_matches))
        if _pending_matches:
            return f"{spoken}. Say 'more matches' for {len(_pending_matches)} more."
        return f"{spoken}. That was the last one."

    results = cache.search(query_text)
    source = "cache"
    if not results:
        results = _live_search(query_text)
        source = "live"

    if not results:
        _pending_matches = []
        _pending_total = 0
        return f"I couldn't find anything matching {query_text}."

    best = results[0]
    spoken = _format_match(cache, best)
    _pending_matches = results[1:]
    _pending_total = len(results)

    log.info("Answered from %s: %s -> %s", source, query_text, spoken)

    if len(results) > 1:
        return f"{spoken}. There were {len(results)} matches — say 'more matches' to hear the rest."
    return spoken
