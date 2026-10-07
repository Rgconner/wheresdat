"""Print dispatch for the Phomemo M110S over Linux -- companion to
scripts/print_label.py (the Windows version), NOT a replacement for it;
both encode the identical raw ESC/POS protocol (see that file's
docstring for the full reverse-engineering story), just against a
different transport.

On Windows, the M110S only exposes itself through the OS's GDI print
queue machinery, which is why that version has to fight win32print and
a RAW passthrough datatype. On Linux, it's dramatically simpler:
confirmed live (dmesg) that the M110S enumerates as a genuine USB
Printer Class device (proto 2, bidirectional), which the kernel's
built-in `usblp` driver picks up automatically and exposes as
/dev/usb/lp0 -- no custom driver, no pyusb, no pyserial. Printing is
just writing the same raw bytes straight to that device file.

One real gotcha, confirmed live: a plain `file.write(payload)` on that
device silently short-wrote (~1620 bytes intended, only the tail ~2
characters' worth actually reached the printer) -- character devices
don't give the same "the whole buffer went out" guarantee regular
files do, and Python's high-level file object doesn't necessarily loop
to complete it for a device file. write_all() below does that loop
explicitly, checking os.write()'s actual return value each call.

Usage:
    python3 print_label.py WH-001
    python3 print_label.py WH-001 --label-maker-url http://192.0.2.15:8103
"""

import argparse
import io
import os

import requests
from PIL import Image

LABEL_MAKER_URL = "http://192.0.2.15:8103"
PRINTER_DEV = "/dev/usb/lp0"

# Matches label_gen.py's fixed generation DPI — the PNG's pixel dimensions
# are always at this DPI; used here only to recover the label's true mm
# size, which then gets re-rendered at the printer's own native DPI below.
_SOURCE_DPI = 300

# M110S print head native resolution — same value confirmed on both the
# Windows (GetDeviceCaps) and Linux (this file's own encoding, validated
# against a real print) sides. Standard thermal print head DPI.
_PRINTER_DPI = 203

_ESC = b"\x1b"
_INITIALIZE = _ESC + b"\x40"
_JUSTIFY_CENTER = _ESC + b"\x61\x01"
_ARM_HEAD = b"\x1f\x11\x02\x04"  # Phomemo-proprietary; see scripts/print_label.py
_FLUSH_NO_SEEK = b"\x1b\x64\x00"  # ESC d 0
_GSV0 = b"\x1d\x76\x30\x00"  # GS v 0 — print raster image, normal mode

# Tiers whose physical precut roll is oriented differently than the
# generated image's own width/height, and whose roll is a shared 4-cell
# row rather than one label per gap-sensed unit — see
# scripts/print_label.py's ROTATE_TIERS/ROW_CELLS for the full story.
# Identical physical media, identical fix, just needs to exist on both
# platforms independently since the two scripts don't share code.
ROTATE_TIERS = {"inner_20x10"}
ROW_CELLS = 4


def fetch_label_image(code: str, label_maker_url: str, part: str | None = None,
                      tier: str | None = None) -> tuple["Image.Image", str, str]:
    """Fetch a label PNG and its tier without printing — mirrors
    scripts/print_label.py's function of the same name. tier forces a
    render at another stock size than the code's type default (see
    label-maker's _effective_tier); None = the type's own tier."""
    tier_param = {"tier": tier} if tier else {}
    parts_resp = requests.get(f"{label_maker_url}/labels/{code}/parts", params=tier_param, timeout=10)
    parts_resp.raise_for_status()
    parts_info = parts_resp.json()
    label_tier = parts_info["label_tier"]
    use_part = part if part is not None else parts_info["parts"][0]

    resp = requests.get(f"{label_maker_url}/labels/{code}", params={"part": use_part, **tier_param}, timeout=10)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    return img, label_tier, use_part


def orient_for_tier(img: "Image.Image", label_tier: str) -> "Image.Image":
    if label_tier in ROTATE_TIERS:
        return img.rotate(90, expand=True)
    return img


def compose_row(cell_images: list) -> "Image.Image":
    """Lay up to ROW_CELLS already-oriented single-cell images side by
    side into one physical row image — see scripts/print_label.py's
    version of this function for the full reasoning (the M110S's 20x10
    roll is a shared 4-cell row, not individual labels)."""
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


def _write_all(fd: int, payload: bytes, chunk_size: int = 64) -> int:
    """Explicit write loop, checking os.write()'s actual return value —
    see this module's docstring. A short write here is silent data loss,
    not an error the OS surfaces on its own."""
    total = 0
    while total < len(payload):
        chunk = payload[total:total + chunk_size]
        n = os.write(fd, chunk)
        if n <= 0:
            raise IOError(f"os.write returned {n} at offset {total}/{len(payload)}")
        total += n
    return total


def _shift_x(img: "Image.Image", x_offset_mm: float) -> "Image.Image":
    """Shift printed content right by padding the image's left side with
    white. Per-printer, not per-label. Measured on the M128 with a mm-ruler
    test print: its raster starts 4mm left of the label's left edge, and it
    ignores _JUSTIFY_CENTER (a 40mm and a 48mm-wide raster land at the same
    origin) — so it gets x_offset_mm=4 and the padding is exactly the
    offset, not double. The M110S lines up as-is (0)."""
    pad = round(x_offset_mm / 25.4 * _SOURCE_DPI)
    if pad <= 0:
        return img
    out = Image.new(img.mode, (img.width + pad, img.height), color=255)
    out.paste(img, (pad, 0))
    return out


def print_image(img: "Image.Image", printer_dev: str = PRINTER_DEV, x_offset_mm: float = 0.0) -> None:
    """Send an already-correctly-oriented/composed image straight to the
    printer device file. No rotation, no tier lookup — the caller
    (print_label, or the print agent's row-flush) has already decided
    orientation/composition. x_offset_mm: shift right, see _shift_x."""
    img = _shift_x(img, x_offset_mm)
    width_mm = img.width / _SOURCE_DPI * 25.4
    height_mm = img.height / _SOURCE_DPI * 25.4
    payload = _INITIALIZE + _JUSTIFY_CENTER + _ARM_HEAD + _encode_gsv0(img, width_mm, height_mm) + _FLUSH_NO_SEEK

    fd = os.open(printer_dev, os.O_WRONLY)
    try:
        _write_all(fd, payload)
    finally:
        os.close(fd)


def print_label(code: str, label_maker_url: str, part: str | None = None, printer_dev: str = PRINTER_DEV,
                x_offset_mm: float = 0.0, tier: str | None = None) -> None:
    img, label_tier, _used_part = fetch_label_image(code, label_maker_url, part=part, tier=tier)
    img = orient_for_tier(img, label_tier)
    print_image(img, printer_dev, x_offset_mm=x_offset_mm)


def main():
    parser = argparse.ArgumentParser(description="Print a WheresDat container label on the Phomemo M110S (Linux)")
    parser.add_argument("code", help="container code, e.g. WH-001")
    parser.add_argument("--label-maker-url", default=LABEL_MAKER_URL)
    parser.add_argument("--printer-dev", default=PRINTER_DEV)
    parser.add_argument("--part", default=None, help="print only this part instead of the code's default")
    parser.add_argument("--x-offset-mm", type=float, default=0.0, help="shift content right by this many mm (M128: 4)")
    args = parser.parse_args()
    print_label(args.code, args.label_maker_url, part=args.part, printer_dev=args.printer_dev,
                x_offset_mm=args.x_offset_mm)
    print(f"Sent '{args.code}' to {args.printer_dev}.")


if __name__ == "__main__":
    main()
