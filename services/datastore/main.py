"""Datastore Service — FastAPI application.

Owns container-type and container records (the "free container specs"
catalog from the tote-vision spec's PoC punch list, item #1/#7) AND, as
of the matching/decision engine (punch list item #6), items too —
turned out not to need a separate table at all. An item is just a
Container row with type_prefix "ITM" (a genuinely unique thing, e.g. a
specific tool) or "ITMN" (bulk/loose contents — quantity is One vs Many,
not counted precisely), parented under whatever container currently
holds it. Reuses parent_code, domain, and the existing one-photo-per-
container mechanism exactly as they already work for any other
container — no schema change, no capacity/stock tracking, no free-bin
allocation logic. "Where does this go" for a genuinely new (unregistered)
item is still a human call, not automated — see SPEC.md's Parking Lot.

Each ContainerType declares a `label_tier` ("outer", "inner_40x30",
"inner_20x10", or "none" — see SPEC.md's three label formats; "none" is
for types that are never physically labeled, like ITM/ITMN — a lookup
record isn't a separately-labeled object). Only "outer" containers get
an `aruco_id` assigned at creation (sequential, within DICT_5X5_250's
0-249 range) — the label-maker service uses this for the marker on
outer labels; inner-tier and "none" labels don't need one.

Each ContainerType also declares a `numbering_scope`: "parent" (default —
code is `parent_code-NN`, permanently tied to whichever parent it was
created under, e.g. HF sub-bins that never leave their case) or "global"
(code is `type_prefix-NNN`, independent of current parent — for
reshuffleable containers like printed small-parts boxes, where
`parent_code` is just a mutable "current location" pointer that can
change via /containers/{code}/move without ever touching the container's
own permanent code/label).

Endpoints
---------
GET   /health
POST  /container-types
GET   /container-types
GET   /container-types/{prefix}
POST  /containers
GET   /containers            (optional ?domain= filter)
GET   /containers/{code}
PATCH /containers/{code}/move
PATCH /containers/{code}/locator
POST  /containers/{code}/photo   (multipart upload — the registration-time
                                   reference photo, label visible as the
                                   touchpoint; one per container, re-upload
                                   replaces it)
GET   /containers/{code}/photo
PATCH /containers/{code}/ai-description  (set by registration after calling
                                   vision-identify on a newly-attached photo)
GET   /containers/search?q=      (plain text search across code, domain,
                                   locator, ai_description)
"""

import os
import pathlib
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy import create_engine, func, or_
from sqlalchemy.orm import sessionmaker

from models import Base, Container, ContainerType

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./totevision.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
_engine = create_engine(DATABASE_URL, connect_args=_connect_args)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=_engine)

# Photos live as plain files next to the sqlite db, in the same shared
# volume — one canonical reference photo per container code, named
# {code}.{ext}. Not a DB column: existence is just "does a file with
# this code exist," checked at request time, so no migration was needed
# to add this (same volume already mounted at /data, see docker-compose.yml).
_PHOTOS_DIR = pathlib.Path("/data/photos") if pathlib.Path("/data").exists() else pathlib.Path("./photos")
_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10MB — generous for a phone photo, not unlimited
_ALLOWED_PHOTO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _photo_path(code: str) -> pathlib.Path | None:
    for ext in _ALLOWED_PHOTO_TYPES.values():
        candidate = _PHOTOS_DIR / f"{code}{ext}"
        if candidate.exists():
            return candidate
    return None

_STARTED_AT = datetime.now(timezone.utc).isoformat()
_START_MONO = time.monotonic()

app = FastAPI(
    title="Tote Vision Datastore",
    description="Container-type and container records for tote-vision.",
    version="0.1.0",
)


LABEL_TIERS = ("outer", "inner_40x30", "inner_20x10", "none")
NUMBERING_SCOPES = ("parent", "global")
ARUCO_DICT_SIZE = 250  # DICT_5X5_250


class ContainerTypeIn(BaseModel):
    prefix: str
    name: str
    default_child_count: int | None = None
    label_tier: str = "outer"
    numbering_scope: str = "parent"


class ContainerTypeUpdateIn(BaseModel):
    # Partial update -- only fields actually given get changed. Existing
    # instances aren't touched (label_tier/aruco_id assignment only ever
    # happens at creation time, see create_container) -- a type edit only
    # changes what NEW instances get, and what label-maker generates the
    # next time an existing instance's label is (re)printed. Already-
    # assigned aruco_ids on existing instances become vestigial if
    # label_tier moves off "outer", not reclaimed -- harmless, same as
    # any other gap in the sequence.
    name: str | None = None
    default_child_count: int | None = None
    label_tier: str | None = None
    numbering_scope: str | None = None


class ContainerIn(BaseModel):
    type_prefix: str
    parent_code: str | None = None
    domain: str = "general"
    locator: str | None = None


class ContainerMoveIn(BaseModel):
    parent_code: str | None = None  # None = pull out to the top level / a spare-parts pool, no home yet


class ContainerLocatorIn(BaseModel):
    locator: str | None = None  # None clears it


class ContainerAiDescriptionIn(BaseModel):
    ai_description: str | None = None  # None clears it


def _container_dict(c: Container) -> dict:
    return {
        "code": c.code,
        "type_prefix": c.type_prefix,
        "parent_code": c.parent_code,
        "sequence": c.sequence,
        "domain": c.domain,
        "aruco_id": c.aruco_id,
        "locator": c.locator,
        "ai_description": c.ai_description,
        "display_name": c.locator or c.ai_description,
        "has_photo": _photo_path(c.code) is not None,
        "created_at": c.created_at.isoformat(),
    }


def _type_dict(t: ContainerType) -> dict:
    return {
        "prefix": t.prefix,
        "name": t.name,
        "default_child_count": t.default_child_count,
        "label_tier": t.label_tier,
        "numbering_scope": t.numbering_scope,
        "created_at": t.created_at.isoformat(),
    }


@app.get("/health")
def health():
    return {
        "service": "datastore",
        "status": "ok",
        "started_at": _STARTED_AT,
        "uptime_seconds": round(time.monotonic() - _START_MONO, 1),
    }


@app.post("/container-types", status_code=201)
def create_container_type(payload: ContainerTypeIn):
    if payload.label_tier not in LABEL_TIERS:
        raise HTTPException(status_code=422, detail=f"label_tier must be one of {LABEL_TIERS}")
    if payload.numbering_scope not in NUMBERING_SCOPES:
        raise HTTPException(status_code=422, detail=f"numbering_scope must be one of {NUMBERING_SCOPES}")
    session = _SessionLocal()
    try:
        if session.get(ContainerType, payload.prefix):
            raise HTTPException(status_code=409, detail=f"prefix '{payload.prefix}' already exists")
        ct = ContainerType(
            prefix=payload.prefix,
            name=payload.name,
            default_child_count=payload.default_child_count,
            label_tier=payload.label_tier,
            numbering_scope=payload.numbering_scope,
        )
        session.add(ct)
        session.commit()
        return _type_dict(ct)
    finally:
        session.close()


@app.patch("/container-types/{prefix}")
def update_container_type(prefix: str, payload: ContainerTypeUpdateIn):
    session = _SessionLocal()
    try:
        ct = session.get(ContainerType, prefix)
        if not ct:
            raise HTTPException(status_code=404, detail=f"no container type with prefix '{prefix}'")

        if payload.label_tier is not None:
            if payload.label_tier not in LABEL_TIERS:
                raise HTTPException(status_code=422, detail=f"label_tier must be one of {LABEL_TIERS}")
            ct.label_tier = payload.label_tier
        if payload.numbering_scope is not None:
            if payload.numbering_scope not in NUMBERING_SCOPES:
                raise HTTPException(status_code=422, detail=f"numbering_scope must be one of {NUMBERING_SCOPES}")
            ct.numbering_scope = payload.numbering_scope
        if payload.name is not None:
            ct.name = payload.name
        if payload.default_child_count is not None:
            ct.default_child_count = payload.default_child_count

        session.commit()
        return _type_dict(ct)
    finally:
        session.close()


@app.get("/container-types")
def list_container_types():
    session = _SessionLocal()
    try:
        rows = session.query(ContainerType).order_by(ContainerType.prefix).all()
        return [_type_dict(r) for r in rows]
    finally:
        session.close()


@app.get("/container-types/{prefix}")
def get_container_type(prefix: str):
    session = _SessionLocal()
    try:
        ct = session.get(ContainerType, prefix)
        if not ct:
            raise HTTPException(status_code=404, detail=f"no container type with prefix '{prefix}'")
        return _type_dict(ct)
    finally:
        session.close()


@app.post("/containers", status_code=201)
def create_container(payload: ContainerIn):
    session = _SessionLocal()
    try:
        ct = session.get(ContainerType, payload.type_prefix)
        if not ct:
            raise HTTPException(status_code=404, detail=f"no container type with prefix '{payload.type_prefix}'")

        if payload.parent_code:
            parent = session.get(Container, payload.parent_code)
            if not parent:
                raise HTTPException(status_code=404, detail=f"no container with code '{payload.parent_code}'")

        if ct.numbering_scope == "global":
            # Independent of parent — same type_prefix counts together
            # regardless of which container (or none) it's currently
            # under. Code never needs to change if the container is later
            # moved via /containers/{code}/move.
            max_seq = (
                session.query(func.max(Container.sequence))
                .filter(Container.type_prefix == payload.type_prefix)
                .scalar()
            )
            sequence = (max_seq or 0) + 1
            code = f"{payload.type_prefix}-{sequence:03d}"
        else:
            max_seq = (
                session.query(func.max(Container.sequence))
                .filter(
                    Container.type_prefix == payload.type_prefix,
                    Container.parent_code == payload.parent_code,
                )
                .scalar()
            )
            sequence = (max_seq or 0) + 1
            code_root = payload.parent_code if payload.parent_code else payload.type_prefix
            code = f"{code_root}-{sequence:02d}"

        aruco_id = None
        if ct.label_tier == "outer":
            max_aruco = session.query(func.max(Container.aruco_id)).scalar()
            aruco_id = 0 if max_aruco is None else max_aruco + 1
            if aruco_id >= ARUCO_DICT_SIZE:
                raise HTTPException(
                    status_code=507,
                    detail=f"out of ArUco marker IDs (DICT_5X5_250 caps at {ARUCO_DICT_SIZE})",
                )

        container = Container(
            code=code,
            type_prefix=payload.type_prefix,
            parent_code=payload.parent_code,
            sequence=sequence,
            domain=payload.domain,
            aruco_id=aruco_id,
            locator=payload.locator,
        )
        session.add(container)
        session.commit()
        return _container_dict(container)
    finally:
        session.close()


@app.get("/containers")
def list_containers(domain: str | None = None):
    session = _SessionLocal()
    try:
        query = session.query(Container)
        if domain is not None:
            query = query.filter(Container.domain == domain)
        rows = query.order_by(Container.code).all()
        return [_container_dict(r) for r in rows]
    finally:
        session.close()


def _search_text(c: Container) -> str:
    return " ".join(f for f in (c.code, c.domain, c.locator, c.ai_description) if f)


def _score(q: str, c: Container) -> float:
    # WRatio, not token_set_ratio: verified against a real STT mishearing
    # ("these heat screws" for "PC screws") that token_set_ratio scored
    # only 52 vs. 27 for the wrong candidate — too weak a margin at a
    # sane threshold. WRatio (rapidfuzz's general-purpose blended ratio,
    # length-aware) scored the same pair 85.5 vs. 34.2 — a real margin
    # between "a short noisy query naming one real word" and "unrelated."
    return fuzz.WRatio(q, _search_text(c))


FUZZY_MIN_SCORE = 60
FUZZY_MAX_RESULTS = 5


@app.get("/containers/search")
def search_containers(q: str, domain: str | None = None, fuzzy: bool = False):
    """Plain text search across code/domain/locator/ai_description.

    Two tiers:
    - Literal substring match (LIKE), same as always — this is what
      /containers/find-by-photo's auto-resolve relies on (a single hit
      here means "confident match," see registration/main.py), so its
      behavior is untouched regardless of `fuzzy`.
    - If `fuzzy=true` and the literal match comes back empty, widen to a
      scored fuzzy match over the full table instead of returning
      nothing — for callers like voice-pi, where a spoken query rarely
      matches a stored description word-for-word. Opt-in only: a caller
      that doesn't ask for it (find-by-photo, by default) keeps getting
      either a real substring hit or nothing, never a guess.

    Either way, results are ordered by relevance score, not alphabetical
    by code — multiple literal hits are just as unordered by "closeness"
    as no hits at all would be otherwise.
    """
    session = _SessionLocal()
    try:
        like = f"%{q}%"
        query = session.query(Container).filter(
            or_(
                Container.code.ilike(like),
                Container.domain.ilike(like),
                Container.locator.ilike(like),
                Container.ai_description.ilike(like),
            )
        )
        if domain is not None:
            query = query.filter(Container.domain == domain)
        rows = query.all()

        if rows:
            rows.sort(key=lambda r: _score(q, r), reverse=True)
        elif fuzzy:
            all_rows = session.query(Container)
            if domain is not None:
                all_rows = all_rows.filter(Container.domain == domain)
            scored = [(r, _score(q, r)) for r in all_rows.all()]
            scored = [t for t in scored if t[1] >= FUZZY_MIN_SCORE]
            scored.sort(key=lambda t: t[1], reverse=True)
            rows = [r for r, _s in scored[:FUZZY_MAX_RESULTS]]

        return [_container_dict(r) for r in rows]
    finally:
        session.close()


@app.get("/containers/{code}")
def get_container(code: str):
    session = _SessionLocal()
    try:
        c = session.get(Container, code)
        if not c:
            raise HTTPException(status_code=404, detail=f"no container with code '{code}'")
        return _container_dict(c)
    finally:
        session.close()


@app.delete("/containers/{code}", status_code=204)
def delete_container(code: str):
    """Permanent removal — a container (or item: ITM/ITMN are ordinary
    Container rows, see the module docstring) can genuinely cease to
    exist, not just move (a tool breaks and gets thrown out, a bin
    cracks). Refuses to delete anything with children still parented
    under it (409) rather than silently orphaning them — move or delete
    the children first. Does not cascade on purpose: a bin holding real
    stock is exactly the case where an accidental recursive delete would
    be the most damaging."""
    session = _SessionLocal()
    try:
        c = session.get(Container, code)
        if not c:
            raise HTTPException(status_code=404, detail=f"no container with code '{code}'")

        child_count = session.query(Container).filter(Container.parent_code == code).count()
        if child_count:
            raise HTTPException(
                status_code=409,
                detail=f"'{code}' still has {child_count} container(s) parented under it — move or delete them first",
            )

        photo = _photo_path(code)
        if photo is not None:
            photo.unlink()

        session.delete(c)
        session.commit()
    finally:
        session.close()


@app.patch("/containers/{code}/move")
def move_container(code: str, payload: ContainerMoveIn):
    """Reassign a container's current location (parent_code) without
    touching its own code/sequence/aruco_id — identity stays fixed,
    only where it's currently sitting changes. Only meaningful for
    "global" numbering_scope types in practice (a "parent"-scoped
    container's code is derived from its parent, so moving one would
    make its own code a lie about where it lives — not blocked here,
    but the caller should know that's what they're doing)."""
    session = _SessionLocal()
    try:
        c = session.get(Container, code)
        if not c:
            raise HTTPException(status_code=404, detail=f"no container with code '{code}'")

        if payload.parent_code:
            parent = session.get(Container, payload.parent_code)
            if not parent:
                raise HTTPException(status_code=404, detail=f"no container with code '{payload.parent_code}'")
            if payload.parent_code == code:
                raise HTTPException(status_code=422, detail="a container cannot be its own parent")

        c.parent_code = payload.parent_code
        session.commit()
        return _container_dict(c)
    finally:
        session.close()


@app.patch("/containers/{code}/locator")
def set_container_locator(code: str, payload: ContainerLocatorIn):
    """Free-text, instance-only note — distinguishes one container from
    same-type siblings ("Mounted above reloading workbench", "Halloween
    crafts"). Not a printed label; purely a human-readable descriptor."""
    session = _SessionLocal()
    try:
        c = session.get(Container, code)
        if not c:
            raise HTTPException(status_code=404, detail=f"no container with code '{code}'")
        c.locator = payload.locator
        session.commit()
        return _container_dict(c)
    finally:
        session.close()


@app.patch("/containers/{code}/ai-description")
def set_container_ai_description(code: str, payload: ContainerAiDescriptionIn):
    """Vision-identify's raw output (name + text_on_package) for this
    container's reference photo, stored verbatim as search fodder — NOT
    treated as verified fact (a vision-LLM can fabricate plausible-
    looking text, confirmed earlier this same evening). `locator` wins
    for display whenever both exist; this exists so a container is still
    findable by search even if nobody ever bothered to set a locator."""
    session = _SessionLocal()
    try:
        c = session.get(Container, code)
        if not c:
            raise HTTPException(status_code=404, detail=f"no container with code '{code}'")
        c.ai_description = payload.ai_description
        session.commit()
        return _container_dict(c)
    finally:
        session.close()


@app.post("/containers/{code}/photo", status_code=201)
async def upload_container_photo(code: str, file: UploadFile):
    """The registration-time reference photo — label visible as the
    touchpoint. Every instance of a uniform type (HF) looks the same, so
    this matters most for visually-variable types (GB could be
    anything), but it's stored the same way regardless of type. One per
    container: re-uploading replaces whatever was there, including
    across formats (uploading a .png over an existing .jpg removes the
    old .jpg so there's never more than one file for a given code)."""
    session = _SessionLocal()
    try:
        c = session.get(Container, code)
        if not c:
            raise HTTPException(status_code=404, detail=f"no container with code '{code}'")
    finally:
        session.close()

    ext = _ALLOWED_PHOTO_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported content-type '{file.content_type}', must be one of {sorted(_ALLOWED_PHOTO_TYPES)}",
        )

    body = await file.read(_MAX_PHOTO_BYTES + 1)
    if len(body) > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail=f"photo exceeds {_MAX_PHOTO_BYTES} byte cap")

    existing = _photo_path(code)
    if existing is not None:
        existing.unlink()
    (_PHOTOS_DIR / f"{code}{ext}").write_bytes(body)

    return {"code": code, "has_photo": True}


@app.get("/containers/{code}/photo")
def get_container_photo(code: str):
    path = _photo_path(code)
    if path is None:
        raise HTTPException(status_code=404, detail=f"no photo for container '{code}'")
    return FileResponse(path)
