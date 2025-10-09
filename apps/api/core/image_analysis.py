"""Lightweight image analysis helpers for the demo image search flow."""

from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

try:  # Pillow is an optional dependency for richer image search
    from PIL import Image
except Exception:  # pragma: no cover - gracefully degrade when Pillow missing
    Image = None  # type: ignore

try:  # Lightweight vision transformer for semantic labels
    from transformers import pipeline  # type: ignore
except Exception:  # pragma: no cover - allow running without transformers
    pipeline = None  # type: ignore


@dataclass
class ImageAnalysis:
    """Summary of coarse attributes extracted from an input image."""

    dominant_colors: List[str]
    average_color: Tuple[int, int, int]
    brightness: float
    aspect_ratio: float
    notes: List[str]
    detected_objects: List[str]

    def to_dict(self) -> Dict:
        data = asdict(self)
        # round brightness for easier debugging
        data["brightness"] = round(self.brightness, 3)
        return data


_BASIC_COLORS: Dict[str, Tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "gray": (127, 127, 127),
    "white": (255, 255, 255),
    "red": (220, 20, 60),
    "orange": (255, 140, 0),
    "yellow": (255, 215, 0),
    "green": (46, 139, 87),
    "teal": (0, 128, 128),
    "blue": (30, 144, 255),
    "navy": (0, 0, 128),
    "purple": (138, 43, 226),
    "pink": (255, 105, 180),
    "brown": (139, 69, 19),
}


def _euclidean(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return math.sqrt(sum((int(x) - int(y)) ** 2 for x, y in zip(a, b)))


def _nearest_color(rgb: Tuple[int, int, int]) -> str:
    best = None
    best_dist = float("inf")
    for name, value in _BASIC_COLORS.items():
        dist = _euclidean(rgb, value)
        if dist < best_dist:
            best = name
            best_dist = dist
    return best or "unknown"

_CLASSIFIER: Optional[Any] = None
_CLASSIFIER_DISABLED = object()


def _object_labels(image: "Image.Image") -> List[str]:  # type: ignore[name-defined]
    """Return high-confidence labels detected by a ViT classifier."""

    global _CLASSIFIER
    if pipeline is None:
        return []

    if _CLASSIFIER is _CLASSIFIER_DISABLED:
        return []

    if _CLASSIFIER is None:
        try:
            _CLASSIFIER = pipeline(
                "image-classification",
                model="google/vit-base-patch16-224",
                top_k=5,
            )
        except Exception:
            _CLASSIFIER = _CLASSIFIER_DISABLED
            return []

    if _CLASSIFIER is _CLASSIFIER_DISABLED or _CLASSIFIER is None:
        return []

    try:
        predictions = _CLASSIFIER(image)  # type: ignore[misc]
    except Exception:
        return []

    labels: List[str] = []
    for item in predictions:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        score = item.get("score", 0)
        if not label:
            continue
        if score is not None and score < 0.08:
            continue
        labels.append(str(label))
    return labels


def _decode_image(image_b64: str) -> Optional[Image.Image]:  # type: ignore[name-defined]
    if not Image:
        return None
    try:
        binary = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(binary))
        return img.convert("RGB")
    except Exception:
        return None


def analyze_image(image_b64: str) -> Optional[ImageAnalysis]:
    """Return coarse visual attributes for an image encoded as base64."""

    img = _decode_image(image_b64)
    if img is None:
        return None

    resized = img.resize((48, 48))
    pixels = list(resized.getdata())
    if not pixels:
        return None

    avg = tuple(sum(channel) // len(pixels) for channel in zip(*pixels))  # type: ignore[arg-type]
    brightness = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels) / (255 * len(pixels))

    color_votes: Dict[str, int] = {}
    for r, g, b in pixels:
        name = _nearest_color((r, g, b))
        color_votes[name] = color_votes.get(name, 0) + 1

    dominant = sorted(color_votes.items(), key=lambda item: item[1], reverse=True)
    top_colors = [name for name, _ in dominant[:3]]

    aspect_ratio = round(img.width / img.height, 3) if img.height else 1.0
    notes: List[str] = []
    if brightness < 0.35:
        notes.append("mostly_dark")
    elif brightness > 0.65:
        notes.append("mostly_light")
    if aspect_ratio > 1.3:
        notes.append("wider_than_tall")
    elif aspect_ratio < 0.75:
        notes.append("taller_than_wide")

    detected_objects = _object_labels(img)
    if detected_objects:
        notes.append(f"maybe_{detected_objects[0]}")

    return ImageAnalysis(
        dominant_colors=top_colors,
        average_color=avg,
        brightness=brightness,
        aspect_ratio=aspect_ratio,
        notes=notes,
        detected_objects=detected_objects,
    )


def colors_to_filters(analysis: Optional[ImageAnalysis]) -> List[str]:
    """Map dominant colors to catalog filter values."""

    if not analysis:
        return []
    primary = []
    for color in analysis.dominant_colors:
        if color in {"black", "gray", "white", "blue", "navy", "green", "red", "yellow", "orange", "purple", "pink", "brown", "teal"}:
            primary.append(color)
    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for color in primary:
        if color not in seen:
            ordered.append(color)
            seen.add(color)
    return ordered