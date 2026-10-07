"""Registration Service — FastAPI application.

PoC punch list item #7: a way to enter a new container into the system.
Owns the business logic (talks to the datastore service over HTTP); the
datastore itself stays a dumb record-keeper.

Two real, working paths:
  - register a brand new container *type* (human names it, picks a prefix)
  - register a new *instance* of an existing type (auto-numbered, and
    nestable under a parent container's code)

Two paths that are explicitly NOT implemented yet, on purpose (they
depend on the AI call engine, punch list item #2, which doesn't exist
yet — returning 501 here rather than faking a result):
  - identify container type from a photo
  - look up container specs from a part number

Also serves a minimal static UI (no framework/build step — plain HTML +
fetch) at GET / for staging registrations from a browser, since the raw
JSON endpoints aren't browser-friendly on their own.

Endpoints
---------
GET   /health
GET   /container-types        (proxy to datastore, for the UI)
PATCH /container-types/{prefix}  (proxy to datastore — fix a type's own
                                   settings, e.g. label_tier, without a new
                                   prefix; doesn't retroactively touch
                                   existing instances)
POST  /register-type
POST  /register
POST  /register-batch
POST  /register-with-children
PATCH /containers/{code}/move    (proxy to datastore)
PATCH /containers/{code}/locator (proxy to datastore)
DELETE /containers/{code}        (proxy to datastore; 409 if it still has
                                   children parented under it, no cascade)
POST  /containers/{code}/photo   (proxy to datastore, then best-effort
                                   calls vision-identify and stores its
                                   result as ai_description — search
                                   fodder, not verified fact)
GET   /containers/{code}/photo   (proxy to datastore)
GET   /containers/search         (proxy to datastore)
POST  /containers/find-by-photo  (text search first using vision-identify's
                                   own output; only on multiple ambiguous
                                   matches does it fall back to jepa-embed
                                   visual similarity, scored against that
                                   already-narrowed small set — never the
                                   whole database)
POST  /items/find-by-photo       (matching/decision engine, punch list #6,
                                   V1: same pattern as find-by-photo above,
                                   scoped to ITM/ITMN records, resolves the
                                   match to its current parent_code location.
                                   No free-bin allocation for a genuinely new
                                   item — that stays a human call, see
                                   SPEC.md's Parking Lot)
GET   /                        (static UI — desktop admin page)
GET   /phone                   (static UI — light phone app, camera-first)
"""

import base64
import math
import os
import pathlib

import httpx
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

DATASTORE_URL = os.getenv("DATASTORE_URL", "http://localhost:8101")
LABEL_MAKER_URL = os.getenv("LABEL_MAKER_URL", "http://label-maker:8103")
VISION_IDENTIFY_URL = os.getenv("VISION_IDENTIFY_URL")  # optional — no ai_description gets set if unset
JEPA_EMBED_URL = os.getenv("JEPA_EMBED_URL")  # optional — visual-similarity tier skipped if unset
KANBAN_URL = os.getenv("KANBAN_URL")  # optional — no card gets created if unset
KANBAN_PUBLIC_URL = os.getenv("KANBAN_PUBLIC_URL", "http://localhost:8300")  # browser-facing, differs per environment (live vs QA)
PRINT_AGENT_URL = os.getenv("PRINT_AGENT_URL", "")  # browser-facing, see scripts/print_agent.py — empty hides the Print buttons
KANBAN_BOARD = "wheresdat"
_STATIC_DIR = pathlib.Path(__file__).parent / "static"

app = FastAPI(
    title="Tote Vision Registration",
    description="Registers new container types and container instances.",
    version="0.1.0",
)


class RegisterTypeIn(BaseModel):
    prefix: str
    name: str
    default_child_count: int | None = None
    label_tier: str = "outer"
    numbering_scope: str = "parent"


class UpdateTypeIn(BaseModel):
    name: str | None = None
    default_child_count: int | None = None
    label_tier: str | None = None
    numbering_scope: str | None = None


class ContainerMoveIn(BaseModel):
    parent_code: str | None = None


class ContainerLocatorIn(BaseModel):
    locator: str | None = None


class RegisterIn(BaseModel):
    type_prefix: str | None = None
    parent_code: str | None = None
    domain: str = "general"
    photo: bool = False          # placeholder flag, no upload handling yet — see note below
    part_number: str | None = None


class RegisterBatchIn(BaseModel):
    type_prefix: str
    count: int
    parent_code: str | None = None
    domain: str = "general"


class RegisterWithChildrenIn(BaseModel):
    type_prefix: str
    domain: str = "general"


@app.get("/health")
def health():
    return {"service": "registration", "status": "ok"}


@app.get("/")
def ui():
    # No templating engine — one placeholder, one substitution. The
    # widget's own base URL is the one thing in this page that's
    # genuinely per-environment (browser-facing host port differs
    # between the live and QA stacks; everything else is either a
    # relative fetch or an internal docker-network URL already handled
    # via env vars).
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("__KANBAN_PUBLIC_URL__", KANBAN_PUBLIC_URL)
    html = html.replace("__PRINT_AGENT_URL__", PRINT_AGENT_URL)
    # This page is server-rendered on every request (env substitution) and
    # actively under development — a stale cached copy silently running
    # old JS has already caused real confusion (PSP-006's phone
    # registration ran with pre-identify-preview code despite the server
    # having redeployed). Never worth a browser caching this response.
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/phone")
def phone_ui():
    """The other of SPEC.md's "two interface modules" — light, physical-
    capture-oriented, camera-first. Not a shrunk copy of the admin page:
    no Kanban board, no menu, just the two entry points SPEC.md calls
    out explicitly ("container and item are separate, explicit UI
    paths, not inferred from one ambiguous photo") — recognize (calls
    find-by-photo) and register (calls register + photo + locator)."""
    html = (_STATIC_DIR / "phone.html").read_text(encoding="utf-8")
    html = html.replace("__PRINT_AGENT_URL__", PRINT_AGENT_URL)
    # See ui()'s matching comment — same reasoning, same fix.
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/container-types")
def list_container_types():
    with httpx.Client() as client:
        resp = client.get(f"{DATASTORE_URL}/container-types")
    resp.raise_for_status()
    return resp.json()


@app.get("/labels/{code}/parts")
def label_parts_proxy(code: str, tier: str | None = None):
    """Proxy to label-maker — lets the browser (phone/desktop UI) ask
    which physical label(s) a just-registered code needs (marker+text
    for outer tier, one combined label otherwise) without needing its
    own browser-facing label-maker URL, same reasoning as the other
    proxy endpoints here. Optional tier = "what if I print it on the
    other stock size" (see label-maker's _effective_tier)."""
    with httpx.Client() as client:
        resp = client.get(f"{LABEL_MAKER_URL}/labels/{code}/parts", params={"tier": tier} if tier else None)
    if resp.status_code in (404, 422):
        raise HTTPException(status_code=404, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return resp.json()


@app.post("/register-type", status_code=201)
def register_type(payload: RegisterTypeIn):
    with httpx.Client() as client:
        resp = client.post(
            f"{DATASTORE_URL}/container-types",
            json={
                "prefix": payload.prefix,
                "name": payload.name,
                "default_child_count": payload.default_child_count,
                "label_tier": payload.label_tier,
                "numbering_scope": payload.numbering_scope,
            },
        )
    if resp.status_code in (409, 422):
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return resp.json()


@app.patch("/container-types/{prefix}")
def update_container_type(prefix: str, payload: UpdateTypeIn):
    """Fix a type's own settings (label_tier especially — e.g. a type
    registered as "outer" that turns out too small for the marker+strip
    format, see SCB) without needing a whole new prefix. Only touches
    the type; existing instances' already-assigned aruco_id etc. aren't
    retroactively changed — see the datastore's update_container_type."""
    body = {k: v for k, v in payload.model_dump().items() if v is not None}
    with httpx.Client() as client:
        resp = client.patch(f"{DATASTORE_URL}/container-types/{prefix}", json=body)
    if resp.status_code in (404, 422):
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return resp.json()


def _notify_register_card(code: str):
    """Drop a 'Label and register {code}' task card on the Register column
    — SPEC.md's Kanban task board is the intended landing page for exactly
    this. Best-effort: a missing/unreachable KanBanMan instance should
    never block a registration, same graceful-degradation posture as the
    rest of this ecosystem."""
    if not KANBAN_URL:
        return
    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(
                f"{KANBAN_URL}/boards/{KANBAN_BOARD}/cards",
                json={
                    "column": "Register",
                    "title": f"Label and register {code}",
                    "card_type": "task",
                },
            )
    except httpx.HTTPError:
        pass


def _register_one(client: httpx.Client, type_prefix: str, parent_code: str | None, domain: str):
    resp = client.post(
        f"{DATASTORE_URL}/containers",
        json={"type_prefix": type_prefix, "parent_code": parent_code, "domain": domain},
    )
    if resp.status_code in (404, 507):
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    resp.raise_for_status()
    container = resp.json()
    _notify_register_card(container["code"])
    return container


@app.post("/register", status_code=201)
def register(payload: RegisterIn):
    if payload.photo or payload.part_number:
        raise HTTPException(
            status_code=501,
            detail=(
                "Identifying a container type from a photo or part number "
                "isn't implemented yet — that needs the AI call engine "
                "(PoC punch list item #2). Pass type_prefix explicitly for now."
            ),
        )

    if not payload.type_prefix:
        raise HTTPException(
            status_code=422,
            detail="type_prefix is required until photo/part-number lookup exists",
        )

    with httpx.Client() as client:
        return _register_one(client, payload.type_prefix, payload.parent_code, payload.domain)


@app.post("/register-batch", status_code=201)
def register_batch(payload: RegisterBatchIn):
    """Stage several containers of the same type ahead of time, e.g. to
    print a sheet of labels before the physical containers are even
    unpacked."""
    if payload.count < 1:
        raise HTTPException(status_code=422, detail="count must be at least 1")
    if payload.count > 50:
        raise HTTPException(status_code=422, detail="count capped at 50 per batch")

    with httpx.Client() as client:
        return [
            _register_one(client, payload.type_prefix, payload.parent_code, payload.domain)
            for _ in range(payload.count)
        ]


@app.post("/register-with-children", status_code=201)
def register_with_children(payload: RegisterWithChildrenIn):
    """Register a new container instance and, if its type declares a
    default_child_count (e.g. a Harbor Freight 20-bin case), auto-stage
    that many numbered sub-bins nested under it in the same call — so the
    label BOM for a known product is known the moment it's registered,
    not assembled manually one batch call at a time."""
    with httpx.Client() as client:
        type_resp = client.get(f"{DATASTORE_URL}/container-types/{payload.type_prefix}")
        if type_resp.status_code == 404:
            raise HTTPException(status_code=404, detail=type_resp.json().get("detail"))
        type_resp.raise_for_status()
        container_type = type_resp.json()

        parent = _register_one(client, payload.type_prefix, None, payload.domain)

        child_count = container_type.get("default_child_count") or 0
        children = [
            _register_one(client, payload.type_prefix, parent["code"], payload.domain)
            for _ in range(child_count)
        ]

    return {"parent": parent, "children": children}


@app.patch("/containers/{code}/move")
def move_container(code: str, payload: ContainerMoveIn):
    """Reassign a container's current location without touching its own
    code/identity — see the datastore's move_container for the real
    logic. Pass parent_code: null to pull it out to the top level (e.g.
    into a spare-parts pool with no home yet)."""
    with httpx.Client() as client:
        resp = client.patch(
            f"{DATASTORE_URL}/containers/{code}/move",
            json={"parent_code": payload.parent_code},
        )
    if resp.status_code in (404, 422):
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return resp.json()


@app.delete("/containers/{code}", status_code=204)
def delete_container(code: str):
    """Permanent removal — see the datastore's delete_container for the
    real logic (refuses to delete anything with children still parented
    under it, no cascade). For items (ITM/ITMN) specifically: a tool
    breaks and gets thrown out, a bulk-contents record turns out wrong —
    this is that."""
    with httpx.Client() as client:
        resp = client.delete(f"{DATASTORE_URL}/containers/{code}")
    if resp.status_code in (404, 409):
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return Response(status_code=204)


@app.patch("/containers/{code}/locator")
def set_container_locator(code: str, payload: ContainerLocatorIn):
    """Free-text, instance-only note, e.g. 'Mounted above reloading
    workbench' or 'Halloween crafts' — see the datastore's
    set_container_locator for the real logic. Pass locator: null to
    clear it."""
    with httpx.Client() as client:
        resp = client.patch(
            f"{DATASTORE_URL}/containers/{code}/locator",
            json={"locator": payload.locator},
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return resp.json()


def _identify_description(body: bytes, content_type: str, filename: str | None) -> str | None:
    """Call vision-identify and build the same "name — text_on_package"
    description string stored as ai_description — the one shared place
    that shapes what "the AI description" actually is, used both for the
    auto-populate-on-photo-upload path and the phone app's identify-
    before-you-commit preview (see /identify-preview). Returns None on
    any failure — not treated as verified fact regardless (a vision-LLM
    can fabricate plausible-looking text, confirmed directly: it invented
    "Happy Days" on a tape roll that actually said "Heavy Duty Tape")."""
    if not VISION_IDENTIFY_URL:
        return None
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{VISION_IDENTIFY_URL}/identify",
                files={"file": (filename or "photo.jpg", body, content_type)},
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPError:
        return None
    parts = [result.get("name", "")]
    if result.get("text_on_package"):
        parts.append(result["text_on_package"])
    return " — ".join(p for p in parts if p) or None


NAME_LLM_BASE_URL = os.getenv("NAME_LLM_BASE_URL", "").rstrip("/")
NAME_LLM_MODEL = os.getenv("NAME_LLM_MODEL", "")
NAME_LLM_KEY = os.getenv("NAME_LLM_KEY", "")
SHORT_NAME_MAX_WORDS = 6

_SHORT_NAME_PROMPT = (
    "You name things for a home workshop parts inventory. Below is raw text "
    "read off a product label (it may be messy, repeated, or run together). "
    f"Return a short name, AT MOST {SHORT_NAME_MAX_WORDS} words, that a person "
    "would use to find it on a shelf: what the thing is, plus the one or two "
    "specs that set it apart from similar items (size, material, color, or "
    "brand only if it distinguishes). No marketing words, no piece counts, no "
    "temperatures or batch codes. Return only the name, nothing else.\n\n"
    "Label text:\n"
)


def _fix_mojibake(s: str) -> str:
    """Undo UTF-8-decoded-as-cp1252 damage ("â€”" -> "—", "Â°" -> "°")
    seen in stored descriptions. No-op on clean text."""
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _chat_text(client: httpx.Client, messages: list) -> str:
    resp = client.post(
        f"{NAME_LLM_BASE_URL}/chat/completions",
        json={"model": NAME_LLM_MODEL, "messages": messages, "max_tokens": 1024, "temperature": 0.2},
        headers={"Authorization": f"Bearer {NAME_LLM_KEY}"},
    )
    resp.raise_for_status()
    data = resp.json()
    data = data.get("data", data) if "choices" not in data else data  # ClinePass envelope
    content = (data["choices"][0]["message"].get("content") or "").strip()
    if "</think>" in content:
        content = content.split("</think>")[-1]
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    return lines[-1].strip('"').strip() if lines else ""


def _short_name(text: str) -> str | None:
    """<=6-word shelf name from long label text. The full text stays in
    ai_description as search fodder — this is only what gets shown.
    Plain truncation was tested on the 12 longest real names and produced
    junk ("Terminal Set 520 Piece — ELECTRIC"); the LLM reads like a
    hand-written bin label but sometimes overshoots the limit, so: one
    stricter retry, then a hard truncate. None only if there's no text."""
    text = _fix_mojibake(text or "").strip()
    if not text:
        return None
    n = SHORT_NAME_MAX_WORDS
    if len(text.split()) <= n and "—" not in text:
        return text
    name = ""
    if NAME_LLM_BASE_URL and NAME_LLM_KEY:
        messages = [{"role": "user", "content": _SHORT_NAME_PROMPT + text}]
        try:
            with httpx.Client(timeout=60.0) as client:
                name = _chat_text(client, messages)
                if len(name.split()) > n:
                    messages += [
                        {"role": "assistant", "content": name},
                        {"role": "user", "content": f"That was {len(name.split())} words. Give the same name in AT MOST {n} words. Return only the name."},
                    ]
                    name = _chat_text(client, messages) or name
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            name = ""
    return " ".join((name or text).split()[:n])


class ShortNameIn(BaseModel):
    text: str


@app.post("/short-name")
def short_name(payload: ShortNameIn):
    """<=6-word name for arbitrary label text — used by the one-off
    backfill of existing long names, and handy for testing the prompt."""
    name = _short_name(payload.text)
    if name is None:
        raise HTTPException(status_code=422, detail="text is empty")
    return {"short_name": name}


def _notify_ai_description(code: str, body: bytes, content_type: str, filename: str | None, override: str | None = None):
    """Best-effort: store ai_description — search fodder, not verified
    fact, see _identify_description. `override` is the phone app's
    already-reviewed preview result (see /identify-preview): when given,
    this stores it as-is instead of calling vision-identify a second
    time — the point of the preview flow is the human sees this exact
    text before committing, so re-deriving a fresh (possibly different)
    one here would defeat that. A missing/unreachable vision-identify
    should never block a photo upload, same graceful-degradation posture
    as the rest of this ecosystem."""
    description = override if override is not None else _identify_description(body, content_type, filename)
    if not description:
        return
    try:
        with httpx.Client(timeout=10.0) as client:
            client.patch(
                f"{DATASTORE_URL}/containers/{code}/ai-description",
                json={"ai_description": description},
            )
            # Desktop flow (no phone preview): without a locator, the
            # display name falls back to this whole description blob — give
            # it a short name instead. Never overwrites a locator the human
            # already set (the phone flow sets its own, pre-filled from
            # /identify-preview's short_name).
            if override is None:
                existing = client.get(f"{DATASTORE_URL}/containers/{code}")
                if existing.status_code == 200 and not existing.json().get("locator"):
                    name = _short_name(description)
                    if name:
                        client.patch(f"{DATASTORE_URL}/containers/{code}/locator", json={"locator": name})
    except httpx.HTTPError:
        pass


@app.post("/identify-preview")
async def identify_preview(file: UploadFile):
    """Run identification on a photo BEFORE any container exists —
    lets the phone app's register flow show the AI-generated
    description for review/editing before the human commits by hitting
    Register, rather than only finding out afterward. Purely a
    vision-identify passthrough; no datastore writes happen here."""
    body = await file.read()
    description = _identify_description(body, file.content_type, file.filename)
    if description is None:
        raise HTTPException(status_code=503, detail="identification unavailable — vision-identify unreachable or found nothing")
    # short_name pre-fills the phone's Note (= locator = display name);
    # the full description still goes to ai_description for search.
    return {"description": description, "short_name": _short_name(description)}


@app.post("/containers/{code}/photo", status_code=201)
async def upload_container_photo(code: str, file: UploadFile, ai_description: str | None = Form(None)):
    """Proxy the registration-time reference photo upload — see the
    datastore's upload_container_photo for the real logic (10MB cap,
    jpeg/png/webp only, one photo per container). Also populates
    ai_description (see _notify_ai_description) — either the given
    override (phone app's already-reviewed preview text) or a fresh
    best-effort vision-identify call when none is given (desktop flow)."""
    body = await file.read()
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{DATASTORE_URL}/containers/{code}/photo",
            files={"file": (file.filename, body, file.content_type)},
        )
    if resp.status_code in (404, 413, 422):
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    resp.raise_for_status()
    _notify_ai_description(code, body, file.content_type, file.filename, override=ai_description)
    return resp.json()


@app.get("/containers/{code}/photo")
def get_container_photo(code: str):
    with httpx.Client() as client:
        resp = client.get(f"{DATASTORE_URL}/containers/{code}/photo")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail"))
    resp.raise_for_status()
    return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))


@app.get("/containers/search")
def search_containers(q: str, domain: str | None = None, fuzzy: bool = False):
    with httpx.Client() as client:
        params = {"q": q, "fuzzy": fuzzy}
        if domain is not None:
            params["domain"] = domain
        resp = client.get(f"{DATASTORE_URL}/containers/search", params=params)
    resp.raise_for_status()
    return resp.json()


def _jepa_embed(client: httpx.Client, image_bytes: bytes) -> list[float] | None:
    if not JEPA_EMBED_URL:
        return None
    b64 = base64.b64encode(image_bytes).decode()
    resp = client.post(
        f"{JEPA_EMBED_URL}/v1/embeddings",
        json={"model": "ijepa_vith14_1k-q8_0", "input": [{"b64": b64}]},
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@app.post("/containers/find-by-photo")
async def find_by_photo(file: UploadFile):
    """"Here's a photo of a mystery item, which registered container is
    this?" — text search first (fast, free, using the same identify
    call the reference-photo flow already makes), visual similarity only
    as a tie-breaker when text search comes back ambiguous, and only
    ever scored against that already-narrowed small set. See SPEC.md's
    "Text search across AI description + locator" section for why this
    order, not the reverse."""
    if not VISION_IDENTIFY_URL:
        raise HTTPException(status_code=503, detail="VISION_IDENTIFY_URL not configured")

    image_bytes = await file.read()

    with httpx.Client(timeout=60.0) as client:
        identify_resp = client.post(
            f"{VISION_IDENTIFY_URL}/identify",
            files={"file": (file.filename or "photo.jpg", image_bytes, file.content_type)},
        )
        if identify_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="vision-identify could not identify the photo")
        identification = identify_resp.json()

        search_term = identification.get("name", "")
        candidates = []
        if search_term:
            search_resp = client.get(f"{DATASTORE_URL}/containers/search", params={"q": search_term})
            search_resp.raise_for_status()
            candidates = search_resp.json()

        if len(candidates) <= 1:
            return {
                "method": "text",
                "identification": identification,
                "resolved": candidates[0] if candidates else None,
                "candidates": candidates,
            }

        # Ambiguous — narrow with visual similarity, scored only against
        # these candidates, never the whole database.
        if not JEPA_EMBED_URL:
            return {
                "method": "text",
                "identification": identification,
                "resolved": None,
                "candidates": candidates,
                "note": "multiple text matches and JEPA_EMBED_URL is not configured — cannot disambiguate visually",
            }

        query_embedding = _jepa_embed(client, image_bytes)
        scored = []
        for c in candidates:
            if not c.get("has_photo"):
                continue
            photo_resp = client.get(f"{DATASTORE_URL}/containers/{c['code']}/photo")
            if photo_resp.status_code != 200:
                continue
            candidate_embedding = _jepa_embed(client, photo_resp.content)
            similarity = _cosine_similarity(query_embedding, candidate_embedding)
            scored.append({**c, "similarity": round(similarity, 4)})

        scored.sort(key=lambda c: c["similarity"], reverse=True)
        return {
            "method": "visual",
            "identification": identification,
            "resolved": scored[0] if scored else None,
            "candidates": scored,
        }


ITEM_TYPE_PREFIXES = ("ITM", "ITMN")


@app.post("/items/find-by-photo")
async def find_item_by_photo(file: UploadFile):
    """"Here's a photo of something in hand, which registered item is
    this, and where does it currently live?" Same text-first, visual-
    tiebreak-on-ambiguity pattern as /containers/find-by-photo, but
    scoped to ITM/ITMN records only (not every container) and resolving
    the winning match through parent_code to its current physical
    location -- e.g. "ITM-005 -> BIN-005", not just the bare item
    record.

    Deliberately does NOT try to pick a bin for a genuinely new
    (unmatched) item -- see SPEC.md's Parking Lot: designing a general
    "where does this belong" fit algorithm doesn't hold together (it
    depends on categories that live in the human's head, not in any
    data the system has). A miss just says so; the human decides and
    registers it manually.

    confidence: "high" (one unambiguous text match), "medium" (multiple
    text matches, resolved by visual similarity), "low" (multiple
    matches, couldn't disambiguate), "none" (no registered item matched
    at all)."""
    if not VISION_IDENTIFY_URL:
        raise HTTPException(status_code=503, detail="VISION_IDENTIFY_URL not configured")

    image_bytes = await file.read()

    with httpx.Client(timeout=60.0) as client:
        identify_resp = client.post(
            f"{VISION_IDENTIFY_URL}/identify",
            files={"file": (file.filename or "photo.jpg", image_bytes, file.content_type)},
        )
        if identify_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="vision-identify could not identify the photo")
        identification = identify_resp.json()

        search_term = identification.get("name", "")
        candidates = []
        if search_term:
            search_resp = client.get(f"{DATASTORE_URL}/containers/search", params={"q": search_term, "fuzzy": True})
            search_resp.raise_for_status()
            candidates = [c for c in search_resp.json() if c["type_prefix"] in ITEM_TYPE_PREFIXES]

        def _resolve(match: dict) -> dict:
            location = None
            if match.get("parent_code"):
                loc_resp = client.get(f"{DATASTORE_URL}/containers/{match['parent_code']}")
                if loc_resp.status_code == 200:
                    location = loc_resp.json()
            return {**match, "location": location}

        if not candidates:
            return {
                "confidence": "none",
                "identification": identification,
                "resolved": None,
                "candidates": [],
                "note": "no registered item matched — register this one manually",
            }

        if len(candidates) == 1:
            return {
                "confidence": "high",
                "method": "text",
                "identification": identification,
                "resolved": _resolve(candidates[0]),
                "candidates": candidates,
            }

        # Ambiguous — narrow with visual similarity, same pattern as
        # /containers/find-by-photo: scored only against these candidates,
        # never the whole database.
        if not JEPA_EMBED_URL:
            return {
                "confidence": "low",
                "method": "text",
                "identification": identification,
                "resolved": None,
                "candidates": candidates,
                "note": "multiple item matches and JEPA_EMBED_URL is not configured — cannot disambiguate visually",
            }

        query_embedding = _jepa_embed(client, image_bytes)
        scored = []
        for c in candidates:
            if not c.get("has_photo"):
                continue
            photo_resp = client.get(f"{DATASTORE_URL}/containers/{c['code']}/photo")
            if photo_resp.status_code != 200:
                continue
            candidate_embedding = _jepa_embed(client, photo_resp.content)
            similarity = _cosine_similarity(query_embedding, candidate_embedding)
            scored.append({**c, "similarity": round(similarity, 4)})

        scored.sort(key=lambda c: c["similarity"], reverse=True)
        return {
            "confidence": "medium" if scored else "low",
            "method": "visual",
            "identification": identification,
            "resolved": _resolve(scored[0]) if scored else None,
            "candidates": scored,
        }
