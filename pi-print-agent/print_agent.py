"""Print Agent — Linux/Pi version. Same HTTP contract as
scripts/print_agent.py (the Windows one) on purpose: the registration
UI's JS (index.html, phone.html) talks to whatever PRINT_AGENT_URL
points at without caring which platform is on the other end. Swapping
from the Windows workstation to this Pi is a config change
(PRINT_AGENT_URL in the k8s deployment), not a UI code change.

Exists at all because the Windows path required an NSSM service tied to
a specific workstation staying powered on — this runs on the Pi that's
already always-on for voice-pi, so printing stops depending on whether
anyone's desktop happens to be awake. See print_label.py's docstring
for why the actual device write is simpler here than on Windows too
(no GDI driver fight — a genuine USB Printer Class device the kernel's
usblp driver already exposes as /dev/usb/lpN).

Two printers, one per label size, so there's no roll-swapping and no
"what's loaded" state: each label goes to the printer that holds its size
(see PRINTERS). Device names come from udev rules keyed on each model's
USB vendor:product (99-wheresdat-labels.rules) — /dev/usb/lp0 vs lp1
ordering isn't stable across reboots/replugs, and both report junk
serials, so port-agnostic model matching is the only stable handle.

Usage:
    python3 print_agent.py
    python3 print_agent.py --label-maker-url http://192.0.2.15:8103 --port 8104

Run under systemd (see wheresdat-print.service/install-service.sh) —
not a terminal tab, this one has no interactive workstation to leave
open in the first place.
"""

import argparse
import json
import os
import pathlib

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from print_label import (
    ROTATE_TIERS,
    ROW_CELLS,
    compose_row,
    fetch_label_image,
    orient_for_tier,
    print_image,
    print_label,
)

app = FastAPI(title="WheresDat Print Agent (Pi)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # same posture as the Windows agent — trusted home LAN only
    allow_methods=["POST", "GET", "PUT"],
    allow_headers=["*"],
)

_label_maker_url = "http://192.0.2.15:8103"

# One printer per label size. x_offset_mm shifts content right — measured
# with a mm-ruler test print (see print_label._shift_x): the M128's raster
# starts left of the label edge, the M110S lines up as-is. Overridable
# per-key from printers.json next to this file (e.g. after re-measuring
# when the M128's roll gets reloaded — its roll floats; it's shimmed).
PRINTERS = {
    "40x30": {"dev": "/dev/label-40x30", "model": "M128", "x_offset_mm": 2.0},
    "20x10": {"dev": "/dev/label-20x10", "model": "M110S", "x_offset_mm": 0.0},
}

_TIER_TO_SIZE = {
    "outer": "40x30",
    "inner_40x30": "40x30",
    "inner_20x10": "20x10",
}

_STATE_DIR = pathlib.Path(__file__).parent
_PRINTERS_PATH = _STATE_DIR / "printers.json"
_QUEUE_PATH = _STATE_DIR / "print_agent_queue.json"


def _load_printers() -> dict:
    printers = {size: dict(cfg) for size, cfg in PRINTERS.items()}
    if _PRINTERS_PATH.exists():
        for size, override in json.loads(_PRINTERS_PATH.read_text()).items():
            printers.setdefault(size, {}).update(override)
    return printers


def _printer_for(size: str) -> dict:
    """The printer config for a label size, or a 503 if it isn't plugged
    in. Checked before every write: a sleeping Phomemo drops off USB
    entirely, and writing to a stale path would otherwise "succeed" with
    nothing printed (seen live — the M128 slept mid-test and two jobs
    vanished without an error)."""
    printer = _printers.get(size)
    if printer is None:
        raise HTTPException(status_code=500, detail=f"no printer configured for {size}mm labels")
    if not os.path.exists(printer["dev"]):
        raise HTTPException(
            status_code=503,
            detail=f"{size}mm printer ({printer['model']}) not connected — is it switched on / asleep?",
        )
    return printer


def _load_queue() -> list:
    if _QUEUE_PATH.exists():
        try:
            return json.loads(_QUEUE_PATH.read_text())
        except Exception:
            pass
    return []


def _save_queue(queue: list) -> None:
    _QUEUE_PATH.write_text(json.dumps(queue))


_printers = _load_printers()
_row_queue: list = _load_queue()


@app.get("/health")
def health():
    return {
        "service": "print-agent-pi",
        "status": "ok",
        "printers": {
            size: {**cfg, "connected": os.path.exists(cfg["dev"])} for size, cfg in _printers.items()
        },
        "label_maker_url": _label_maker_url,
        "queued_cells": len(_row_queue),
    }


@app.get("/print-queue")
def get_print_queue():
    return {"queue": _row_queue, "cells_until_flush": ROW_CELLS - len(_row_queue)}


def _flush_row() -> dict:
    global _row_queue
    if not _row_queue:
        raise HTTPException(status_code=400, detail="print queue is empty, nothing to flush")
    printer = _printer_for("20x10")  # only inner_20x10 codes ever queue

    cells = []
    codes_printed = []
    for entry in _row_queue[:ROW_CELLS]:
        img, label_tier, _used_part = fetch_label_image(entry["code"], _label_maker_url, part=entry["part"],
                                                        tier=entry.get("tier"))
        cells.append(orient_for_tier(img, label_tier))
        codes_printed.append(entry["code"])
    blank_cells = ROW_CELLS - len(cells)
    cells.extend([None] * blank_cells)

    row = compose_row(cells)
    print_image(row, printer["dev"], x_offset_mm=printer["x_offset_mm"])

    _row_queue = []
    _save_queue(_row_queue)
    return {"printed_codes": codes_printed, "blank_cells": blank_cells}


@app.post("/print-queue/flush")
def flush_print_queue():
    return _flush_row()


def _parts(code: str, tier: str | None = None) -> dict:
    try:
        resp = requests.get(f"{_label_maker_url}/labels/{code}/parts",
                            params={"tier": tier} if tier else None, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"couldn't look up label size for '{code}': {e}")


@app.post("/print/{code}")
def do_print(code: str, part: str | None = None, size: str | None = None):
    """size = which stock to print on ("40x30" | "20x10"), chosen per
    print on the phone; omitted = the code's type default. Picking the
    other size re-renders the label at that size (label-maker ?tier=) and
    routes it to that size's printer."""
    global _row_queue
    if size is not None and size not in _printers:
        raise HTTPException(status_code=422, detail=f"size must be one of {sorted(_printers)}")
    parts_info = _parts(code)
    label_tier = parts_info["label_tier"]
    if label_tier == "none":
        raise HTTPException(status_code=400, detail=f"'{code}' has label_tier \"none\" — nothing to print")

    tier = None  # None = type default, passed through as "no override"
    if size is not None and size != _TIER_TO_SIZE.get(label_tier):
        tier = "inner_20x10" if size == "20x10" else "inner_40x30"
        parts_info = _parts(code, tier)
        label_tier = parts_info["label_tier"]
        part = None  # the default tier's part names don't apply to the override's
    needed_size = _TIER_TO_SIZE.get(label_tier)

    if label_tier in ROTATE_TIERS:
        use_part = part if part is not None else parts_info["parts"][0]
        _row_queue.append({"code": code, "part": use_part, "tier": tier})
        _save_queue(_row_queue)
        if len(_row_queue) >= ROW_CELLS:
            result = _flush_row()
            return {"printed": True, "row_flushed": True, **result}
        return {
            "printed": False,
            "queued": True,
            "queue_position": len(_row_queue),
            "cells_until_flush": ROW_CELLS - len(_row_queue),
        }

    printer = _printer_for(needed_size)
    try:
        print_label(code, _label_maker_url, part=part, printer_dev=printer["dev"],
                    x_offset_mm=printer["x_offset_mm"], tier=tier)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"print failed: {e}")
    return {"printed": code, "part": part or "all", "size": needed_size}


def main():
    global _label_maker_url
    parser = argparse.ArgumentParser(description="Run the WheresDat print agent (Linux/Pi)")
    parser.add_argument("--label-maker-url", default="http://192.0.2.15:8103")
    parser.add_argument("--port", type=int, default=8104)
    args = parser.parse_args()
    _label_maker_url = args.label_maker_url
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
