"""Print dispatch for the Phomemo M110S — native Windows script, NOT
containerized. label-maker's Docker container can't reach the printer
either way it's connected: Bluetooth LE isn't accessible from inside a
Linux container under Docker Desktop/WSL2, and the M110S is actually
wired over USB anyway, showing up as a plain Windows print queue
("M110S Printer", port USB001) that only the host can see. So this runs
directly on the host, but NOT through that print queue's GDI driver —
see below.

Raw ESC/POS over the print queue's RAW datatype, not GDI drawing. The
GDI path (win32ui StartDoc/StartPage/dib.draw through the installed
driver) was the original approach and worked when this was first set
up, but after a from-scratch driver reinstall it proved impossible to
get right again: oversized output, then fragmented across ~11 labels,
reproduced identically across three different DEVMODE strategies
(custom size, the driver's own named paper-size list, even the
system-wide Printing Defaults set correctly via the vendor's own
Labelife app) — while Labelife's own prints came out perfect. That
strongly pointed at a bug in this cheap driver's StretchBlt/BitBlt
handling of a scaled DIB, not a configuration problem, so this instead
sends a hand-built ESC/POS `GS v 0` raster block directly to the print
queue's RAW passthrough (bypasses the driver's GDI rendering entirely;
still goes through the same "M110S Printer" queue object, so it
doesn't disturb Labelife's own ability to print).

Reverse-engineered against real hardware (see phomemo_printer on PyPI,
targeting a different Phomemo model, for the starting point): plain
`ESC d n` (feed n lines) is a real, standard command and moved the
paper on its own, but the image alone printed nothing until preceded
by `\\x1f\\x11\\x02\\x04` (Phomemo-proprietary, undocumented — arms the
thermal head; without it the raster data just buffers silently). A
trailing feed is also required to flush that buffer — `ESC d` with any
nonzero n triggers the gap sensor to seek all the way to the start of
the NEXT label (wasting one blank label per print, confirmed
independent of the actual n value tried); `ESC d 0` is the sweet spot
that flushes the print without triggering that seek.

Usage:
    python print_label.py WH-001
    python print_label.py WH-001 --printer "M110S Printer" --label-maker-url http://localhost:8103
"""

import argparse
import io

import httpx
import win32print
from PIL import Image

# Matches label_gen.py's fixed generation DPI — the PNG's pixel dimensions
# are always at this DPI; used here only to recover the label's true mm
# size, which then gets re-rendered at the printer's own native DPI below.
_SOURCE_DPI = 300

# M110S print head native resolution, confirmed via GetDeviceCaps
# (LOGPIXELSX/Y) across every earlier GDI experiment: always 203, a
# standard thermal print head DPI (8 dots/mm).
_PRINTER_DPI = 203

_ESC = b"\x1b"
_INITIALIZE = _ESC + b"\x40"
_JUSTIFY_CENTER = _ESC + b"\x61\x01"
_ARM_HEAD = b"\x1f\x11\x02\x04"  # Phomemo-proprietary; see module docstring
_FLUSH_NO_SEEK = b"\x1b\x64\x00"  # ESC d 0
_GSV0 = b"\x1d\x76\x30\x00"  # GS v 0 — print raster image, normal mode

# Tiers whose physical precut roll is oriented differently than the
# generated image's own width/height — confirmed live for inner_20x10:
# label_gen.py generates it 20mm-wide x 10mm-tall, but the physical roll
# is actually a 4-across ROW (40mm cross-web x 20mm feed-direction,
# containing four 10mm x 20mm peel-off cells) — the gap sensor only
# detects boundaries between rows, not between the 4 cells within one.
# Rotating 90 degrees turns label_gen.py's 20x10mm image into the
# correctly-oriented 10mm x 20mm single-cell shape; see ROW_CELLS below
# for filling all 4 cells of a row instead of wasting 3 of them.
ROTATE_TIERS = {"inner_20x10"}

# How many cells make up one physical gap-sensed row for a rotate-tier
# roll. Only inner_20x10 is a multi-cell row today; anything not in
# ROTATE_TIERS implicitly means 1 (its own full physical unit, no
# sharing) and never goes through compose_row.
ROW_CELLS = 4


def fetch_label_image(code: str, label_maker_url: str, part: str | None = None) -> tuple["Image.Image", str, str]:
    """Fetch a label PNG and its tier without printing anything —
    separated from print_label() so callers (the print agent's row-
    batching queue) can hold onto fetched images across multiple HTTP
    requests before ever touching the printer. Returns (image,
    label_tier, part_used) — part_used matters for the caller's doc_name
    when part=None let the server pick."""
    parts_resp = httpx.get(f"{label_maker_url}/labels/{code}/parts", timeout=10.0)
    parts_resp.raise_for_status()
    parts_info = parts_resp.json()
    label_tier = parts_info["label_tier"]
    use_part = part if part is not None else parts_info["parts"][0]

    resp = httpx.get(f"{label_maker_url}/labels/{code}", params={"part": use_part}, timeout=10.0)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    return img, label_tier, use_part


def orient_for_tier(img: "Image.Image", label_tier: str) -> "Image.Image":
    """Apply whatever rotation this tier's physical roll needs. Safe to
    call on an already-composed multi-cell row image too, as long as
    label_tier is passed as None/something not in ROTATE_TIERS (a
    composed row is already in final physical orientation)."""
    if label_tier in ROTATE_TIERS:
        return img.rotate(90, expand=True)
    return img


def compose_row(cell_images: list["Image.Image | None"]) -> "Image.Image":
    """Lay up to ROW_CELLS already-oriented single-cell images side by
    side (left to right) into one physical row image. A None entry
    prints as a blank (unused) cell -- e.g. flushing a partial queue of
    2 pending codes still uses the full row, cells 3-4 just come out
    blank rather than being left for a future, now-misaligned print.
    All cells are assumed the same pixel size (label_gen.py generates a
    fixed nominal size per tier, content differs, dimensions don't)."""
    real = next((img for img in cell_images if img is not None), None)
    if real is None:
        raise ValueError("compose_row: at least one cell must be non-None")
    cell_w, cell_h = real.size
    row = Image.new("L", (cell_w * len(cell_images), cell_h), color=255)
    for i, img in enumerate(cell_images):
        if img is not None:
            row.paste(img, (cell_w * i, 0))
    return row


def _encode_gsv0(img: "Image.Image", width_mm: float, height_mm: float) -> bytes:
    width_dots = round(width_mm / 25.4 * _PRINTER_DPI)
    width_bytes = -(-width_dots // 8)  # round up to a whole byte
    width_dots = width_bytes * 8
    height_dots = round(height_mm / 25.4 * _PRINTER_DPI)

    bitmap = img.resize((width_dots, height_dots)).convert("1")
    px = bitmap.load()

    header = _GSV0 + bytes([
        width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
        height_dots & 0xFF, (height_dots >> 8) & 0xFF,
    ])
    data = bytearray(width_bytes * height_dots)
    i = 0
    for y in range(height_dots):
        for bx in range(width_bytes):
            byte = 0
            for bit in range(8):
                if px[bx * 8 + bit, y] == 0:  # black pixel
                    byte |= 1 << (7 - bit)
            data[i] = byte
            i += 1
    return header + bytes(data)


def print_image(img: "Image.Image", printer_name: str, doc_name: str) -> None:
    """Send an already-correctly-oriented image straight to the printer.
    No rotation, no tier lookup -- the caller (print_label, or the print
    agent's row-flush) has already decided orientation/composition."""
    width_mm = img.width / _SOURCE_DPI * 25.4
    height_mm = img.height / _SOURCE_DPI * 25.4
    payload = _INITIALIZE + _JUSTIFY_CENTER + _ARM_HEAD + _encode_gsv0(img, width_mm, height_mm) + _FLUSH_NO_SEEK

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, (doc_name, None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, payload)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def print_label(code: str, printer_name: str, label_maker_url: str, part: str | None = None) -> None:
    # Outer-tier containers need two physical labels (marker, then text) —
    # only fixed 40x30mm precut stock is on hand, not the continuous roll
    # a one-piece landscape strip needs. See label-maker's label_gen.py
    # (label_parts) for which tiers need how many parts; this just follows
    # whatever it says rather than knowing tier rules itself. Pass an
    # explicit `part` to print just that one instead of every part this
    # code has — e.g. a reprint of only the text label, or the
    # registration UI's separate per-part print controls.
    #
    # inner_20x10 specifically prints immediately here too (one code =
    # one physical row, 3 of its 4 cells left blank) -- this function is
    # the direct/CLI path with no batching state. The print agent's
    # queued row-batching (fill all 4 cells before printing) is what
    # actually avoids that waste for the normal registration-UI flow;
    # see print_agent.py.
    parts_resp = httpx.get(f"{label_maker_url}/labels/{code}/parts", timeout=10.0)
    parts_resp.raise_for_status()
    parts_info = parts_resp.json()
    label_tier = parts_info["label_tier"]
    parts = [part] if part is not None else parts_info["parts"]

    for p in parts:
        resp = httpx.get(f"{label_maker_url}/labels/{code}", params={"part": p}, timeout=10.0)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = orient_for_tier(img, label_tier)
        print_image(img, printer_name, f"WheresDat label {code} ({p})")


def main():
    parser = argparse.ArgumentParser(description="Print a WheresDat container label on the Phomemo M110S")
    parser.add_argument("code", help="container code, e.g. WH-001")
    parser.add_argument("--printer", default="M110S Printer", help="Windows printer name (exact, see Get-Printer)")
    parser.add_argument("--label-maker-url", default="http://localhost:8103")
    parser.add_argument("--part", default=None, help="print only this part (e.g. marker, text) instead of every part this code has")
    args = parser.parse_args()
    print_label(args.code, args.printer, args.label_maker_url, part=args.part)
    print(f"Sent '{args.code}' to '{args.printer}'.")


if __name__ == "__main__":
    main()
