"""Label image generation — pure functions, no FastAPI/network dependency
so this can be tested standalone.

Three tiers (see SPEC.md, "Three label formats now, not two"):
  - outer: landscape strip, variable length (auto-sized to the code),
    ArUco marker + code text, thin border.
  - inner_40x30: fixed 40x30mm, text-only (HF-style physical sub-bins).
  - inner_20x10: fixed 20x10mm, text-only (3D-printed Sortimo boxes).

ArUco marker: DICT_5X5_250 (250 unique IDs, comfortably more than
realistic container counts). One ID per outer-tier container, assigned by
the datastore at creation time (see services/datastore/models.py).
Deliberately not attempting to replicate Bosch/Sortimo's own hardware —
this is just the print label, unrelated to the tray design.
"""

import cv2
from PIL import Image, ImageDraw, ImageFont

DPI = 300
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_250)

# Tried in order; falls back to PIL's built-in bitmap font (small, but
# never fails) if none of these are present. The Docker image installs
# fonts-dejavu-core specifically so the first path resolves in practice.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size_px: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def mm_to_px(mm: float, dpi: int = DPI) -> int:
    return round(mm / 25.4 * dpi)


def _aruco_marker_image(marker_id: int, size_px: int) -> Image.Image:
    marker = cv2.aruco.generateImageMarker(ARUCO_DICT, marker_id, size_px)
    return Image.fromarray(marker).convert("L")


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int, tuple]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox


def generate_outer_label(code: str, aruco_id: int, tape_height_mm: float = 40, dpi: int = DPI) -> Image.Image:
    """Landscape strip: ArUco marker on the left (own quiet-zone margin,
    can't touch text or border), code as one line of text on the right,
    length auto-sized to the code so a short code doesn't waste tape."""
    height_px = mm_to_px(tape_height_mm, dpi)
    margin = round(height_px * 0.08)
    marker_size = height_px - 2 * margin

    font = _font(round(height_px * 0.45))
    tmp_draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    text_w, text_h, bbox = _text_size(tmp_draw, code, font)

    gap = margin
    width_px = margin + marker_size + gap + text_w + margin

    img = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(img)

    img.paste(_aruco_marker_image(aruco_id, marker_size), (margin, margin))

    text_x = margin + marker_size + gap
    text_y = (height_px - text_h) // 2 - bbox[1]
    draw.text((text_x, text_y), code, font=font, fill=0)

    border_w = max(1, round(height_px * 0.015))
    draw.rectangle([0, 0, width_px - 1, height_px - 1], outline=0, width=border_w)
    return img


def _generate_text_only_label(code: str, width_mm: float, height_mm: float, dpi: int = DPI) -> Image.Image:
    width_px = mm_to_px(width_mm, dpi)
    height_px = mm_to_px(height_mm, dpi)
    img = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(img)

    # The M110S's label feed drifts a bit (confirmed on a real test
    # print, off-center) — cheap thermal printers just don't feed precut
    # stock with much precision. Rather than chase that in hardware,
    # leave a blank buffer around the border/text so drift eats into
    # margin instead of clipping content. Fixed 2mm, not proportional —
    # Russ's call, plenty for the drift actually observed.
    margin_px = mm_to_px(2, dpi)
    content_x0, content_y0 = margin_px, margin_px
    content_x1, content_y1 = width_px - margin_px, height_px - margin_px
    content_w = content_x1 - content_x0
    content_h = content_y1 - content_y0

    max_w = content_w * 0.88
    font_size = round(content_h * 0.55)
    font = _font(font_size)
    text_w, text_h, bbox = _text_size(draw, code, font)
    while text_w > max_w and font_size > 6:
        font_size -= 1
        font = _font(font_size)
        text_w, text_h, bbox = _text_size(draw, code, font)

    text_x = content_x0 + (content_w - text_w) // 2 - bbox[0]
    text_y = content_y0 + (content_h - text_h) // 2 - bbox[1]
    draw.text((text_x, text_y), code, font=font, fill=0)

    border_w = max(1, round(content_h * 0.03))
    draw.rectangle([content_x0, content_y0, content_x1 - 1, content_y1 - 1], outline=0, width=border_w)
    return img


def generate_inner_40x30_label(code: str, dpi: int = DPI) -> Image.Image:
    return _generate_text_only_label(code, 40, 30, dpi)


def generate_inner_20x10_label(code: str, dpi: int = DPI) -> Image.Image:
    return _generate_text_only_label(code, 20, 10, dpi)


def generate_label(code: str, label_tier: str, aruco_id: int | None, dpi: int = DPI) -> Image.Image:
    if label_tier == "outer":
        if aruco_id is None:
            raise ValueError(f"outer-tier label for '{code}' requires an aruco_id")
        return generate_outer_label(code, aruco_id, dpi=dpi)
    if label_tier == "inner_40x30":
        return generate_inner_40x30_label(code, dpi=dpi)
    if label_tier == "inner_20x10":
        return generate_inner_20x10_label(code, dpi=dpi)
    raise ValueError(f"unknown label_tier: {label_tier}")


def generate_marker_only_label(aruco_id: int, width_mm: float = 40, height_mm: float = 30, dpi: int = DPI) -> Image.Image:
    """Marker centered on its own fixed-size label, paired with a
    separate text-only label (see label_parts/generate_label_part) for
    outer-tier containers — the one-piece landscape strip from
    generate_outer_label needs continuous roll stock; this pair prints
    on the 40x30mm precut labels actually on hand instead. Same
    bordered/2mm-margin styling as _generate_text_only_label so the two
    look like a matched pair."""
    width_px = mm_to_px(width_mm, dpi)
    height_px = mm_to_px(height_mm, dpi)
    margin_px = mm_to_px(2, dpi)

    img = Image.new("L", (width_px, height_px), color=255)
    marker_size = min(width_px, height_px) - 2 * margin_px
    marker = _aruco_marker_image(aruco_id, marker_size)
    img.paste(marker, ((width_px - marker_size) // 2, (height_px - marker_size) // 2))

    draw = ImageDraw.Draw(img)
    border_w = max(1, round(height_px * 0.03))
    draw.rectangle([margin_px, margin_px, width_px - margin_px - 1, height_px - margin_px - 1], outline=0, width=border_w)
    return img


def label_parts(label_tier: str) -> list[str]:
    """Which physical labels a code needs printed, given only fixed
    40x30mm precut stock is on hand (not the continuous roll
    generate_outer_label's single landscape strip was designed for).
    Two parts for outer (marker + text), one for the text-only tiers."""
    if label_tier == "outer":
        return ["marker", "text"]
    return ["combined"]


def generate_label_part(code: str, label_tier: str, aruco_id: int | None, part: str, dpi: int = DPI) -> Image.Image:
    if part == "combined":
        return generate_label(code, label_tier, aruco_id, dpi=dpi)
    if part == "marker":
        if aruco_id is None:
            raise ValueError(f"marker part for '{code}' requires an aruco_id")
        return generate_marker_only_label(aruco_id, dpi=dpi)
    if part == "text":
        # Fixed 40x30 — the precut stock actually on hand, not necessarily
        # this container's own tier size (only reached for "outer" today).
        return _generate_text_only_label(code, 40, 30, dpi=dpi)
    raise ValueError(f"unknown label part: {part}")
