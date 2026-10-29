"""Colour -> pattern mappings for greyscale puzzle images.

A mapping is a small JSON file in mappings/ that assigns each grid value (0-9) a
built-in pattern name, or a path to a PNG tile (e.g. "tiles/star.png").

Usage:
  python mappings.py list                          # show saved mappings
  python mappings.py new <name>                    # write the default mapping
  python mappings.py shuffle <name> --seed 3       # write a random (reproducible) mapping
  python mappings.py preview <name>                # render mappings/<name>.png legend sheet
"""
import argparse
import json
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent
MAPPINGS_DIR = BASE_DIR / "mappings"
COLORS = "colors"  # reserved name: the original colour images in images/

INK = (0, 0, 0)
PAPER = (255, 255, 255)

# Built-in patterns and how they are described to the model
PATTERNS = {
    "none": "blank (white)",
    "solid": "solid black",
    "dots": "dots",
    "diag": "diagonal stripes (\\)",
    "antidiag": "diagonal stripes (/)",
    "cross": "grid of crossing lines",
    "horiz": "horizontal stripes",
    "vert": "vertical stripes",
    "checker": "checkerboard",
    "ring": "ring (circle outline)",
}
DEFAULT_MAPPING = {
    "0": "none", "1": "solid", "2": "dots", "3": "diag", "4": "cross",
    "5": "horiz", "6": "vert", "7": "checker", "8": "ring", "9": "antidiag",
}


def _draw_pattern(name: str, size: int) -> Image.Image:
    tile = Image.new("RGB", (size, size), PAPER)
    d = ImageDraw.Draw(tile)
    line = max(1, size // 12)
    step = max(3, size // 4)
    if name == "none":
        pass
    elif name == "solid":
        d.rectangle([0, 0, size, size], fill=INK)
    elif name == "dots":
        r = max(1, size // 10)
        for cy in (size / 4, size / 2, 3 * size / 4):
            for cx in (size / 4, size / 2, 3 * size / 4):
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)
    elif name in ("diag", "antidiag"):
        for k in range(-size, 2 * size, step):
            if name == "diag":
                d.line([(k, 0), (k + size, size)], fill=INK, width=line)
            else:
                d.line([(k, 0), (k - size, size)], fill=INK, width=line)
    elif name in ("horiz", "vert", "cross"):
        for k in range(step // 2, size, step):
            if name in ("horiz", "cross"):
                d.line([(0, k), (size, k)], fill=INK, width=line)
            if name in ("vert", "cross"):
                d.line([(k, 0), (k, size)], fill=INK, width=line)
    elif name == "checker":
        n = 4
        sq = size / n
        for r in range(n):
            for c in range(n):
                if (r + c) % 2 == 0:
                    d.rectangle([c * sq, r * sq, (c + 1) * sq, (r + 1) * sq], fill=INK)
    elif name == "ring":
        pad = size * 0.2
        d.ellipse([pad, pad, size - pad, size - pad], outline=INK, width=max(1, size // 8))
    else:
        raise ValueError(f"Unknown pattern: {name}")
    return tile


@lru_cache(maxsize=None)
def cell_tile(value: str, size: int) -> Image.Image:
    """A size x size tile for a pattern name or a PNG tile path."""
    if value in PATTERNS:
        return _draw_pattern(value, size)
    return Image.open(BASE_DIR / value).convert("L").convert("RGB").resize((size, size), Image.NEAREST)


def validate(mapping: dict) -> dict[int, str]:
    keys = sorted(mapping, key=str)
    if keys != [str(i) for i in range(10)]:
        raise ValueError(f"Mapping must have exactly the keys 0-9, got {keys}")
    for k, v in mapping.items():
        if v not in PATTERNS and not (BASE_DIR / v).is_file():
            raise ValueError(f"Colour {k}: '{v}' is not a pattern ({', '.join(PATTERNS)}) or an existing tile file")
    values = list(mapping.values())
    dupes = sorted({v for v in values if values.count(v) > 1})
    if dupes:
        raise ValueError(f"Each colour needs its own pattern; used more than once: {dupes}")
    return {int(k): v for k, v in mapping.items()}


def list_mappings() -> list[str]:
    return sorted(p.stem for p in MAPPINGS_DIR.glob("*.json"))


def load_mapping(name: str) -> dict[int, str]:
    path = MAPPINGS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"No mapping '{name}' in {MAPPINGS_DIR}/ (have: {', '.join(list_mappings()) or 'none'})")
    with open(path, "r", encoding="utf-8") as f:
        return validate(json.load(f))


def legend_text(mapping: dict[int, str]) -> str:
    """e.g. '0 = blank (white), 1 = solid black, ...' for the prompt."""
    return ", ".join(f"{k} = {PATTERNS.get(v, Path(v).stem)}" for k, v in sorted(mapping.items()))


def save_mapping(name: str, mapping: dict, overwrite: bool = False) -> Path:
    validate(mapping)
    path = MAPPINGS_DIR / f"{name}.json"
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists (use --overwrite)")
    MAPPINGS_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
        f.write("\n")
    return path


def render_legend(name: str) -> Path:
    mapping = load_mapping(name)
    tile, gap, label_h, margin = 64, 20, 50, 20
    width = margin * 2 + 10 * tile + 9 * gap
    img = Image.new("RGB", (width, margin * 2 + tile + label_h), PAPER)
    d = ImageDraw.Draw(img)
    fnt = ImageFont.load_default(size=16)
    for i, (k, v) in enumerate(sorted(mapping.items())):
        x = margin + i * (tile + gap)
        img.paste(cell_tile(v, tile), (x, margin))
        d.rectangle([x, margin, x + tile, margin + tile], outline=(85, 85, 85))
        d.text((x + tile / 2, margin + tile + 8), str(k), fill=INK, font=fnt, anchor="mt")
        d.text((x + tile / 2, margin + tile + 28), Path(v).stem, fill=(90, 90, 90), font=ImageFont.load_default(size=12), anchor="mt")
    out = MAPPINGS_DIR / f"{name}.png"
    img.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show saved mappings")
    p_new = sub.add_parser("new", help="write the default mapping")
    p_new.add_argument("name")
    p_new.add_argument("--overwrite", action="store_true")
    p_shuf = sub.add_parser("shuffle", help="write a random mapping")
    p_shuf.add_argument("name")
    p_shuf.add_argument("--seed", type=int, required=True)
    p_shuf.add_argument("--include-zero", action="store_true", help="also shuffle 0 (by default 0 stays blank)")
    p_shuf.add_argument("--overwrite", action="store_true")
    p_prev = sub.add_parser("preview", help="render a legend sheet PNG")
    p_prev.add_argument("name")
    args = parser.parse_args()

    if args.command == "list":
        for name in list_mappings():
            print(f"{name}: {legend_text(load_mapping(name))}")
    elif args.command == "new":
        print(f"Wrote {save_mapping(args.name, DEFAULT_MAPPING, args.overwrite)}")
    elif args.command == "shuffle":
        rng = random.Random(args.seed)
        keys = [str(i) for i in range(10)] if args.include_zero else [str(i) for i in range(1, 10)]
        patterns = [DEFAULT_MAPPING[k] for k in keys]
        rng.shuffle(patterns)
        mapping = dict(DEFAULT_MAPPING, **dict(zip(keys, patterns)))
        mapping = {str(i): mapping[str(i)] for i in range(10)}
        print(f"Wrote {save_mapping(args.name, mapping, args.overwrite)}")
    elif args.command == "preview":
        print(f"Wrote {render_legend(args.name)}")


if __name__ == "__main__":
    main()
