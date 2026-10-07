"""Print Agent — small always-on HTTP wrapper around print_label.py's
win32print logic, so the WheresDat browser UI can trigger a real print
directly instead of only a "python print_label.py CODE" terminal
command. Has to run on THIS machine specifically — same reason
print_label.py does: the Phomemo M110S is USB-attached here, showing up
as a Windows print queue only this host can see (see print_label.py's
own docstring for the full explanation).

The registration service's page is served from the k8s cluster, but the
browser viewing it is on the same LAN as this machine — so the page's
JS calls this agent directly (cross-origin), not through the cluster.

Usage:
    python print_agent.py
    python print_agent.py --printer "M110S Printer" --label-maker-url http://192.0.2.15:8103 --port 8104

Run this once, leave it running (a terminal tab, or a Scheduled Task at
logon if you want it surviving reboots without manual restart).
"""

import argparse
import json
import pathlib

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from print_label import (
    ROW_CELLS,
    ROTATE_TIERS,
    compose_row,
    fetch_label_image,
    orient_for_tier,
    print_image,
    print_label,
)

app = FastAPI(title="WheresDat Print Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # the registration page's origin varies (LB IP can change) — this agent only runs on the trusted home LAN
    allow_methods=["POST", "GET", "PUT"],
    allow_headers=["*"],
)

_printer_name = "M110S Printer"
_label_maker_url = "http://192.0.2.15:8103"

# Which physical label stock a code needs — NOT the same axis as
# label_tier: "outer" and "inner_40x30" both physically need 40x30mm
# precut stock (outer just prints as two labels instead of one strip),
# only "inner_20x10" needs the smaller size. See label_gen.py's module
# docstring for the three tiers.
_TIER_TO_SIZE = {
    "outer": "40x30",
    "inner_40x30": "40x30",
    "inner_20x10": "20x10",
}

# Persisted to local files, not just in-memory — an agent restart
# shouldn't silently forget what's loaded (or what's mid-row queued) and
# let a mismatched/wasted print through with no warning.
_STATE_PATH = pathlib.Path(__file__).parent / "print_agent_state.json"
_QUEUE_PATH = pathlib.Path(__file__).parent / "print_agent_queue.json"


def _load_loaded_size() -> str:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text())["loaded_size"]
        except Exception:
            pass
    return "40x30"  # matches what's actually been on hand since this printer was set up


def _save_loaded_size(size: str) -> None:
    _STATE_PATH.write_text(json.dumps({"loaded_size": size}))


def _load_queue() -> list[dict]:
    if _QUEUE_PATH.exists():
        try:
            return json.loads(_QUEUE_PATH.read_text())
        except Exception:
            pass
    return []


def _save_queue(queue: list[dict]) -> None:
    _QUEUE_PATH.write_text(json.dumps(queue))


_loaded_size = _load_loaded_size()

# Codes waiting for a shared physical row — see print_label.py's
# ROW_CELLS/compose_row docstrings for why: the M110S's 20x10 die-cut
# roll is actually a 4-cell-wide row per gap-sensed unit, so printing
# one code per job wastes the other 3 cells every time. Each entry:
# {"code": str, "part": str}. Only rotate-tier codes (inner_20x10 today)
# ever go through this queue; everything else still prints immediately,
# one physical unit per job, same as always.
_row_queue: list[dict] = _load_queue()


class LoadedSizeIn(BaseModel):
    size: str  # "40x30" or "20x10"


@app.get("/health")
def health():
    return {
        "service": "print-agent",
        "status": "ok",
        "printer": _printer_name,
        "label_maker_url": _label_maker_url,
        "loaded_size": _loaded_size,
        "queued_cells": len(_row_queue),
    }


@app.get("/loaded-size")
def get_loaded_size():
    return {"loaded_size": _loaded_size}


@app.put("/loaded-size")
def set_loaded_size(body: LoadedSizeIn):
    global _loaded_size
    if body.size not in ("40x30", "20x10"):
        raise HTTPException(status_code=422, detail="size must be '40x30' or '20x10'")
    _loaded_size = body.size
    _save_loaded_size(_loaded_size)
    return {"loaded_size": _loaded_size}


@app.get("/print-queue")
def get_print_queue():
    return {"queue": _row_queue, "cells_until_flush": ROW_CELLS - len(_row_queue)}


def _flush_row() -> dict:
    """Print whatever's in _row_queue as one physical row (padding any
    unused cells blank), then clear it. Images are re-fetched fresh from
    label-maker here rather than held from queue-time — cheap, and
    avoids ever printing a stale image if a label's content changed
    between queuing and flushing."""
    global _row_queue
    if not _row_queue:
        raise HTTPException(status_code=400, detail="print queue is empty, nothing to flush")

    cells: list = []
    codes_printed = []
    for entry in _row_queue[:ROW_CELLS]:
        img, label_tier, _used_part = fetch_label_image(entry["code"], _label_maker_url, part=entry["part"])
        cells.append(orient_for_tier(img, label_tier))
        codes_printed.append(entry["code"])
    blank_cells = ROW_CELLS - len(cells)
    cells.extend([None] * blank_cells)

    row = compose_row(cells)
    print_image(row, _printer_name, "WheresDat row: " + ", ".join(codes_printed))

    _row_queue = []
    _save_queue(_row_queue)
    return {"printed_codes": codes_printed, "blank_cells": blank_cells}


@app.post("/print-queue/flush")
def flush_print_queue():
    return _flush_row()


@app.post("/print/{code}")
def do_print(code: str, part: str | None = None, override: bool = False):
    # part=None prints every part label_gen.label_parts says this code
    # needs (both marker+text for outer tier); a specific part reprints
    # just that one — e.g. only the text label smudged in the printer,
    # or the registration UI's separate per-part print controls.
    global _row_queue
    try:
        parts_resp = httpx.get(f"{_label_maker_url}/labels/{code}/parts", timeout=10.0)
        parts_resp.raise_for_status()
        parts_info = parts_resp.json()
        label_tier = parts_info["label_tier"]
        needed_size = _TIER_TO_SIZE.get(label_tier)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"couldn't look up label size for '{code}': {e}")

    if label_tier == "none":
        # ITM/ITMN and anything else registered with no printable format
        # — a lookup record, never printed (see the matching/decision
        # engine's SPEC.md section). Short-circuit with a clear message
        # here, before ever reaching label-maker's image endpoint, which
        # 400s for exactly this case (confirmed live: this used to crash
        # through to a raw 502 with no useful detail).
        raise HTTPException(status_code=400, detail=f"'{code}' has label_tier \"none\" — nothing to print")

    if needed_size and needed_size != _loaded_size and not override:
        raise HTTPException(
            status_code=409,
            detail=f"'{code}' needs {needed_size}mm stock, but {_loaded_size}mm is set as loaded — "
                    f"swap the roll and update the dropdown, or resend with ?override=true to print anyway",
        )

    if label_tier in ROTATE_TIERS:
        # Shared-row tier (inner_20x10 today) — queue instead of
        # printing immediately, auto-flushing once a full row's worth
        # (ROW_CELLS) is pending. See _flush_row/print-queue/flush for
        # the manual "print what's queued now, pad the rest blank" path.
        use_part = part if part is not None else parts_info["parts"][0]
        _row_queue.append({"code": code, "part": use_part})
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

    try:
        print_label(code, _printer_name, _label_maker_url, part=part)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"print failed: {e}")
    return {"printed": code, "part": part or "all", "printer": _printer_name}


def main():
    global _printer_name, _label_maker_url
    parser = argparse.ArgumentParser(description="Run the WheresDat print agent")
    parser.add_argument("--printer", default="M110S Printer", help="Windows printer name (exact, see Get-Printer)")
    parser.add_argument("--label-maker-url", default="http://192.0.2.15:8103")
    parser.add_argument("--port", type=int, default=8104)
    args = parser.parse_args()
    _printer_name = args.printer
    _label_maker_url = args.label_maker_url
    # 0.0.0.0, not 127.0.0.1 — needs to accept connections from other
    # devices on the LAN (the browser might be on a phone, not this machine).
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
