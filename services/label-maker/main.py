"""Label Maker Service — FastAPI application.

PoC punch list item #4. Generates label images for containers (see
SPEC.md's three label formats). This service only produces images;
actual printing happens in scripts/print_label.py and
scripts/print_agent.py, which run on the machine the Phomemo M110S is
USB-attached to (see those scripts' docstrings for why it can't happen
in this container).

Only fixed 40x30mm precut label stock is on hand right now, not
continuous roll — outer-tier's one-piece landscape strip
(generate_outer_label) needs the latter, so outer-tier containers print
as a PAIR of 40x30mm labels instead (marker, then text) until/unless
continuous stock shows up. See label_gen.label_parts.

Endpoints
---------
GET  /health
GET  /labels/{code}/parts        -> {"parts": [...]}, which part(s) to print
GET  /labels/{code}?part=...     -> PNG image (part defaults to "combined")
"""

import io
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from label_gen import generate_label_part, label_parts

DATASTORE_URL = os.getenv("DATASTORE_URL", "http://localhost:8101")

app = FastAPI(
    title="Tote Vision Label Maker",
    description="Generates label images for containers.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"service": "label-maker", "status": "ok"}


def _get_container_and_type(client: httpx.Client, code: str) -> tuple[dict, dict]:
    container_resp = client.get(f"{DATASTORE_URL}/containers/{code}")
    if container_resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"no container with code '{code}'")
    container_resp.raise_for_status()
    container = container_resp.json()

    type_resp = client.get(f"{DATASTORE_URL}/container-types/{container['type_prefix']}")
    type_resp.raise_for_status()
    return container, type_resp.json()


# Tiers a caller may force via ?tier= — printing a code on the other
# stock size than its type's default (e.g. an ITM on 40x30). "outer" only
# works for codes with an aruco_id; "none" is never a print target.
_OVERRIDE_TIERS = {"outer", "inner_40x30", "inner_20x10"}


def _effective_tier(container: dict, container_type: dict, tier: str | None) -> str:
    if tier is None:
        return container_type["label_tier"]
    if tier not in _OVERRIDE_TIERS:
        raise HTTPException(status_code=422, detail=f"tier must be one of {sorted(_OVERRIDE_TIERS)}")
    if tier == "outer" and container.get("aruco_id") is None:
        raise HTTPException(status_code=422, detail=f"'{container['code']}' has no ArUco marker — can't print an outer label")
    return tier


@app.get("/labels/{code}/parts")
def get_label_parts(code: str, tier: str | None = None):
    with httpx.Client() as client:
        container, container_type = _get_container_and_type(client, code)
    label_tier = _effective_tier(container, container_type, tier)
    # label_tier included alongside parts so callers (print_agent.py's
    # size routing) don't need a second round-trip just to learn which
    # physical size a code needs. default_tier = the type's own tier, so
    # a UI can preselect it even when asking about an override.
    return {"parts": label_parts(label_tier), "label_tier": label_tier,
            "default_tier": container_type["label_tier"]}


@app.get("/labels/{code}")
def get_label(code: str, part: str = "combined", tier: str | None = None):
    with httpx.Client() as client:
        container, container_type = _get_container_and_type(client, code)
    label_tier = _effective_tier(container, container_type, tier)

    if label_tier == "none":
        # ITM/ITMN and any other type registered with no printable
        # format at all -- a lookup record, not a physically labeled
        # object (see the matching/decision engine's SPEC.md section).
        # Fail cleanly here rather than falling into generate_label_part
        # -> label_gen.generate_label's bare ValueError for an unknown
        # tier, which surfaced as an ugly 500/502 through print_agent.py
        # instead of a clear "there's nothing to print" message.
        raise HTTPException(status_code=400, detail=f"'{code}' has label_tier \"none\" — nothing to print")

    img = generate_label_part(
        code=container["code"],
        label_tier=label_tier,
        aruco_id=container["aruco_id"],
        part=part,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
