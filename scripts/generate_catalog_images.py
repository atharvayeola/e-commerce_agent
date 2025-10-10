#!/usr/bin/env python3
"""
Generate simple local images for each product in the catalog and update
image_urls to reference the generated assets.

- Creates PNGs at apps/web/public/images/catalog/{product_id}.png
- Renders product title and optional brand/category as a clean card
- Updates data/sample_products.json to point to /images/catalog/{id}.png

Safe to run multiple times; it overwrites existing generated files.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    raise SystemExit("Pillow is required. Install it in your env: pip install Pillow")

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "sample_products.json"
PUBLIC_DIR = ROOT / "apps" / "web" / "public"
OUT_DIR = PUBLIC_DIR / "images" / "catalog"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1200, 630  # OpenGraph aspect, crisp on grid
BG = (248, 250, 252)  # slate-50
FG = (15, 23, 42)     # slate-900
SUB = (71, 85, 105)   # slate-600
ACCENT = (37, 99, 235)  # blue-600
PADDING = 64

# Try to find a decent font; fall back to default
FONT_PATHS = [
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in FONT_PATHS:
        fp = Path(p)
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except Exception:
                pass
    return ImageFont.load_default()

TITLE_FONT = load_font(48)
META_FONT = load_font(28)
BADGE_FONT = load_font(24)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    """Return width, height of text for the given font using textbbox (Pillow 10+)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_badge(draw: ImageDraw.ImageDraw, text: str, x: int, y: int) -> int:
    tw, th = text_size(draw, text, BADGE_FONT)
    pad_x, pad_y = 14, 8
    box = [x, y, x + tw + 2*pad_x, y + th + 2*pad_y]
    draw.rounded_rectangle(box, radius=14, fill=(226, 232, 240))  # slate-200
    draw.text((x + pad_x, y + pad_y), text, fill=SUB, font=BADGE_FONT)
    return box[3]  # new y


def render_card(title: str, brand: str | None, category: str | None, price: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    # Title
    max_title_width = WIDTH - 2 * PADDING
    # basic wrapping: break on words to ~40 chars per line
    lines: List[str] = []
    words = title.split()
    line = []
    for w in words:
        tentative = " ".join(line + [w])
        tw, _ = text_size(d, tentative, TITLE_FONT)
        if tw <= max_title_width:
            line.append(w)
        else:
            if line:
                lines.append(" ".join(line))
            line = [w]
    if line:
        lines.append(" ".join(line))

    y = PADDING
    for ln in lines[:3]:  # cap lines to keep card neat
        d.text((PADDING, y), ln, fill=FG, font=TITLE_FONT)
        y += 60

    # Meta line
    meta_parts = []
    if brand:
        meta_parts.append(brand)
    if category:
        meta_parts.append(category)
    meta = " • ".join(meta_parts)
    if meta:
        d.text((PADDING, y + 8), meta, fill=SUB, font=META_FONT)
        y += 48

    # Price badge
    dollars = f"${price/100:.2f}"
    draw_badge(d, dollars, PADDING, y + 16)

    # Accent bar
    d.rectangle([0, HEIGHT - 12, WIDTH, HEIGHT], fill=ACCENT)
    return img


def main() -> None:
    data: List[Dict] = json.loads(CATALOG_PATH.read_text())
    for item in data:
        pid = item.get("id")
        if not pid:
            continue
        title = item.get("title") or "Product"
        brand = item.get("brand")
        category = item.get("category")
        price_cents = int(item.get("price_cents") or 0)

        img = render_card(title, brand, category, price_cents)
        out_path = OUT_DIR / f"{pid}.png"
        img.save(out_path, format="PNG", optimize=True)

        # Update image_urls to local asset
        item["image_urls"] = [f"/images/catalog/{pid}.png"]

    # Write back catalog with updated image_urls
    CATALOG_PATH.write_text(json.dumps(data, indent=2))
    print(f"Generated {len(data)} images into {OUT_DIR} and updated {CATALOG_PATH}")


if __name__ == "__main__":
    main()
