"""Render NARC puzzle JSON files as PNG images (title, narrative, and grid sequence).

Masked positions are drawn as "?" placeholders; answer grids are never read.

Usage:
  python render_puzzles.py                                   # colour images -> images/
  python render_puzzles.py --mapping patterns_default ...    # pattern images -> greyscale_images/<mapping>/
"""
import argparse
import glob
import json
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mappings import BASE_DIR, COLORS, cell_tile, list_mappings, load_mapping

# Standard ARC color palette
PALETTE = {
    0: (0, 0, 0),
    1: (0, 116, 217),
    2: (255, 65, 54),
    3: (46, 204, 64),
    4: (255, 220, 0),
    5: (170, 170, 170),
    6: (240, 18, 190),
    7: (255, 133, 27),
    8: (127, 219, 255),
    9: (135, 12, 37),
}
BG = (255, 255, 255)
TEXT = (20, 20, 20)
GRIDLINE = (85, 85, 85)
MASK_FILL = (225, 225, 225)
MASK_TEXT = (120, 120, 120)

MARGIN = 30
PANEL_GAP = 40
MAX_GRID_PX = 260  # longest grid side in pixels
MIN_WIDTH = 700
MIN_PATTERN_CELL = 20  # patterns need more pixels than flat colours to stay readable
GREYSCALE_DIR = BASE_DIR / "greyscale_images"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def strip_unrenderable(text: str) -> str:
    """Normalize full-width punctuation and drop emoji the default font cannot draw."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if ord(ch) < 0x10000 and not 0x2600 <= ord(ch) < 0x2800).strip()


def wrap_text(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and fnt.getlength(candidate) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def cell_size(rows: int, cols: int, min_cell: int = 10) -> int:
    return max(min_cell, min(60, MAX_GRID_PX // max(rows, cols)))


def draw_grid(draw: ImageDraw.ImageDraw, x: int, y: int, grid: list[list[int]], cell: int) -> None:
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            x0, y0 = x + c * cell, y + r * cell
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=PALETTE.get(val, (255, 255, 255)), outline=GRIDLINE)


def draw_pattern_grid(img: Image.Image, x: int, y: int, grid: list[list[int]], cell: int, mapping: dict[int, str]) -> None:
    draw = ImageDraw.Draw(img)
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            x0, y0 = x + c * cell, y + r * cell
            img.paste(cell_tile(mapping[val], cell), (x0, y0))
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], outline=GRIDLINE)


def draw_masked(draw: ImageDraw.ImageDraw, x: int, y: int, rows: int, cols: int, cell: int) -> None:
    w, h = cols * cell, rows * cell
    draw.rectangle([x, y, x + w, y + h], fill=MASK_FILL, outline=GRIDLINE, width=2)
    q_font = font(max(16, min(int(h * 0.6), int(w * 0.9))))
    draw.text((x + w / 2, y + h / 2), "?", fill=MASK_TEXT, font=q_font, anchor="mm")


def render_puzzle(data: dict, mapping: dict[int, str] | None = None) -> Image.Image:
    """Colour image by default; with a mapping, each value is drawn as its pattern."""
    sequence = data["sequence"]
    title = strip_unrenderable(data.get("title") or data.get("puzzle_id", ""))
    narrative = data.get("narrative", "")

    # Panel geometry
    panels = []
    for step in sequence:
        cell = cell_size(step["rows"], step["cols"], MIN_PATTERN_CELL if mapping else 10)
        panels.append((step, cell, step["cols"] * cell, step["rows"] * cell))
    label_h = 28
    panels_w = sum(max(w, 90) for _, _, w, _ in panels) + PANEL_GAP * (len(panels) - 1)
    panels_h = max(h for _, _, _, h in panels) + label_h
    width = max(MIN_WIDTH, panels_w + 2 * MARGIN)

    # Text geometry
    title_font, body_font, label_font = font(28), font(18), font(16)
    lines = wrap_text(strip_unrenderable(narrative), body_font, width - 2 * MARGIN)
    line_h = 24
    title_h = 44
    text_h = title_h + len(lines) * line_h + 20

    height = MARGIN + text_h + panels_h + MARGIN
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    y = MARGIN
    draw.text((MARGIN, y), title, fill=TEXT, font=title_font)
    y += title_h
    for line in lines:
        draw.text((MARGIN, y), line, fill=TEXT, font=body_font)
        y += line_h
    y += 20

    x = (width - panels_w) // 2
    for step, cell, w, h in panels:
        slot_w = max(w, 90)
        gx = x + (slot_w - w) // 2
        draw.text((x + slot_w / 2, y), f"Position {step['position']}", fill=TEXT, font=label_font, anchor="mt")
        if step.get("masked") or step.get("grid") is None:
            draw_masked(draw, gx, y + label_h, step["rows"], step["cols"], cell)
        elif mapping:
            draw_pattern_grid(img, gx, y + label_h, step["grid"], cell, mapping)
        else:
            draw_grid(draw, gx, y + label_h, step["grid"], cell)
        x += slot_w + PANEL_GAP

    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(BASE_DIR / "data"))
    parser.add_argument("--out-dir", default=str(BASE_DIR / "images"), help="output folder for colour images")
    parser.add_argument("--mapping", nargs="+", choices=[COLORS] + list_mappings(),
                        help="pattern mappings from mappings/ to render into greyscale_images/<mapping>/")
    args = parser.parse_args()

    paths = sorted(glob.glob(f"{args.data_dir}/*.json"))
    for name in args.mapping or [COLORS]:
        mapping = None if name == COLORS else load_mapping(name)
        out_dir = Path(args.out_dir) if name == COLORS else GREYSCALE_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            out_path = out_dir / f"{Path(path).stem}.png"
            render_puzzle(data, mapping).save(out_path)
            print(f"Wrote {out_path}")
        print(f"Rendered {len(paths)} puzzles to {out_dir}/")


if __name__ == "__main__":
    main()
