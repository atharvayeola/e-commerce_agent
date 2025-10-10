"""Lightweight image analysis helpers for the demo image search flow."""

from __future__ import annotations

import base64
import io
import math
import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

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
    caption: Optional[str] = None

    def to_dict(self) -> Dict:
        data = asdict(self)
        # round brightness for easier debugging
        data["brightness"] = round(self.brightness, 3)
        return data

@dataclass
class LabelHints:
    """Lightweight representation of object labels useful for ranking."""

    keywords: List[str]
    categories: List[str]

    def to_dict(self) -> Dict[str, List[str]]:
        return {"keywords": self.keywords, "categories": self.categories}
    
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

_LABEL_HINTS: Dict[str, Dict[str, List[str]]] = {
    "shoe": {"keywords": ["shoe", "sneaker", "running"], "categories": ["fashion", "fitness"]},
    "sandal": {"keywords": ["sandal", "shoe"], "categories": ["fashion"]},
    "boot": {"keywords": ["boot", "shoe"], "categories": ["fashion", "outdoor"]},
    "backpack": {"keywords": ["backpack", "bag"], "categories": ["outdoor", "fashion"]},
    "handbag": {"keywords": ["bag", "handbag"], "categories": ["fashion"]},
    "laptop": {"keywords": ["laptop", "computer"], "categories": ["electronics"]},
    "notebook computer": {"keywords": ["laptop", "computer"], "categories": ["electronics"]},
    "keyboard": {"keywords": ["keyboard"], "categories": ["electronics", "office"]},
    "monitor": {"keywords": ["monitor", "display"], "categories": ["electronics", "office"]},
    "screen": {"keywords": ["monitor", "display"], "categories": ["electronics"]},
    "tablet": {"keywords": ["tablet"], "categories": ["electronics"]},
    "phone": {"keywords": ["phone", "smartphone"], "categories": ["electronics"]},
    "camera": {"keywords": ["camera"], "categories": ["electronics"]},
    "headphone": {"keywords": ["headphone", "audio"], "categories": ["electronics"]},
    "earphone": {"keywords": ["earbud", "audio"], "categories": ["electronics"]},
    "speaker": {"keywords": ["speaker", "audio"], "categories": ["electronics", "office"]},
    "microphone": {"keywords": ["microphone", "audio"], "categories": ["electronics", "office"]},
    "watch": {"keywords": ["watch"], "categories": ["electronics", "fitness"]},
    "smartwatch": {"keywords": ["smartwatch", "watch"], "categories": ["electronics", "fitness"]},
    "vacuum": {"keywords": ["vacuum"], "categories": ["home-appliance"]},
    "iron": {"keywords": ["iron"], "categories": ["home-appliance"]},
    "humidifier": {"keywords": ["humidifier"], "categories": ["home-appliance", "beauty"]},
    "purifier": {"keywords": ["purifier", "filter"], "categories": ["home-appliance"]},
    "heater": {"keywords": ["heater"], "categories": ["home-appliance"]},
    "stove": {"keywords": ["stove", "burner"], "categories": ["kitchenware", "outdoor"]},
    "grill": {"keywords": ["grill"], "categories": ["outdoor", "kitchenware"]},
    "knife": {"keywords": ["knife"], "categories": ["kitchenware"]},
    "skillet": {"keywords": ["skillet", "pan"], "categories": ["kitchenware"]},
    "pot": {"keywords": ["pot", "cookware"], "categories": ["kitchenware"]},
    "coffee": {"keywords": ["coffee"], "categories": ["kitchenware"]},
    "grinder": {"keywords": ["grinder"], "categories": ["kitchenware"]},
    "bottle": {"keywords": ["bottle", "insulated"], "categories": ["outdoor", "fitness"]},
    "lantern": {"keywords": ["lantern", "light"], "categories": ["outdoor"]},
    "tent": {"keywords": ["tent"], "categories": ["outdoor"]},
    "backcountry": {"keywords": ["outdoor"], "categories": ["outdoor"]},
    "mat": {"keywords": ["mat"], "categories": ["fitness", "home-appliance"]},
    "yoga": {"keywords": ["yoga"], "categories": ["fitness"]},
    "dumbbell": {"keywords": ["dumbbell", "weights"], "categories": ["fitness"]},
    "band": {"keywords": ["band", "resistance"], "categories": ["fitness"]},
    "book": {"keywords": ["book"], "categories": ["books"]},
    "journal": {"keywords": ["journal", "notebook"], "categories": ["books", "office"]},
    "pencil": {"keywords": ["pencil"], "categories": ["office"]},
    "pen": {"keywords": ["pen"], "categories": ["office"]},
    "lamp": {"keywords": ["lamp", "light"], "categories": ["office", "home-appliance"]},
    "organizer": {"keywords": ["organizer", "desk"], "categories": ["office"]},
    "desk": {"keywords": ["desk"], "categories": ["office"]},
    "robot": {"keywords": ["robot", "toy"], "categories": ["toys"]},
    "block": {"keywords": ["blocks", "toy"], "categories": ["toys"]},
    "kit": {"keywords": ["kit", "toy"], "categories": ["toys", "office"]},
    "dress": {"keywords": ["dress"], "categories": ["fashion"]},
    "jacket": {"keywords": ["jacket", "coat"], "categories": ["fashion", "outdoor"]},
    "sweater": {"keywords": ["sweater", "knit"], "categories": ["fashion"]},
    "parka": {"keywords": ["parka", "coat"], "categories": ["fashion", "outdoor"]},
    "jean": {"keywords": ["denim", "jeans"], "categories": ["fashion"]},
    "serum": {"keywords": ["serum", "skincare"], "categories": ["beauty"]},
    "cream": {"keywords": ["cream", "skincare"], "categories": ["beauty"]},
    "moisturizer": {"keywords": ["moisturizer", "skincare"], "categories": ["beauty"]},
    "palette": {"keywords": ["makeup", "palette"], "categories": ["beauty"]},
    "cleanser": {"keywords": ["cleanser", "skincare"], "categories": ["beauty"]},
    "diffuser": {"keywords": ["diffuser", "aroma"], "categories": ["beauty", "home-appliance"]},
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
_CAPTIONER: Optional[Any] = None
_CAPTIONER_DISABLED = object()


def _object_labels(image: "Image.Image") -> List[str]:  # type: ignore[name-defined]
    """Return high-confidence labels detected by a ViT classifier."""

    global _CLASSIFIER

    allow_classifier = os.environ.get("ENABLE_IMAGE_CLASSIFIER", "").lower() in {
        "1",
        "true",
        "yes",
    }

    if pipeline is None:
        return []

    if not allow_classifier:
        _CLASSIFIER = _CLASSIFIER_DISABLED
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

def _describe_image(image: "Image.Image") -> Optional[str]:  # type: ignore[name-defined]
    """Generate a descriptive caption for the image when possible."""

    global _CAPTIONER

    allow_captioner = os.environ.get("ENABLE_IMAGE_CAPTIONING", "1").lower() in {
        "1",
        "true",
        "yes",
    }

    if pipeline is None or not allow_captioner:
        if not allow_captioner:
            _CAPTIONER = _CAPTIONER_DISABLED
        return None

    if _CAPTIONER is _CAPTIONER_DISABLED:
        return None

    if _CAPTIONER is None:
        try:
            _CAPTIONER = pipeline(
                "image-to-text",
                model="Salesforce/blip-image-captioning-base",
            )
        except Exception:
            _CAPTIONER = _CAPTIONER_DISABLED
            return None

    if _CAPTIONER is _CAPTIONER_DISABLED or _CAPTIONER is None:
        return None

    try:
        result = _CAPTIONER(image)  # type: ignore[misc]
    except Exception:
        return None

    caption: Optional[str] = None
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            caption = first.get("generated_text") or first.get("caption")
        elif isinstance(first, str):
            caption = first
    elif isinstance(result, dict):
        caption = result.get("generated_text") or result.get("caption")

    if caption:
        cleaned = caption.strip()
        return cleaned or None
    return None

def _normalize_label(label: str) -> str:
    return label.lower().replace("_", " ").replace("-", " ").strip()


def labels_to_hints(analysis: Optional[ImageAnalysis]) -> LabelHints:
    """Translate detected objects into catalog-friendly keywords and categories."""

    if not analysis or not analysis.detected_objects:
        return LabelHints(keywords=[], categories=[])

    keywords: List[str] = []
    categories: List[str] = []
    seen_keywords: Set[str] = set()
    seen_categories: Set[str] = set()

    caption_tokens: List[str] = []
    caption = analysis.caption or ""
    if caption:
        for token in re.split(r"[^a-z0-9]+", caption.lower()):
            if not token:
                continue
            if len(token) <= 3:
                continue
            if token in {"with", "from", "that", "this", "there", "into", "over", "under", "their", "your", "have"}:
                continue
            caption_tokens.append(token)

    for raw_label in analysis.detected_objects + caption_tokens:
        normalized = _normalize_label(raw_label)
        matched = False
        for key, spec in _LABEL_HINTS.items():
            if key in normalized:
                matched = True
                for kw in spec.get("keywords", []):
                    if kw not in seen_keywords:
                        keywords.append(kw)
                        seen_keywords.add(kw)
                for category in spec.get("categories", []):
                    if category not in seen_categories:
                        categories.append(category)
                        seen_categories.add(category)
        if not matched:
            for token in normalized.split():
                spec = _LABEL_HINTS.get(token)
                if not spec:
                    continue
                matched = True
                for kw in spec.get("keywords", []):
                    if kw not in seen_keywords:
                        keywords.append(kw)
                        seen_keywords.add(kw)
                for category in spec.get("categories", []):
                    if category not in seen_categories:
                        categories.append(category)
                        seen_categories.add(category)

        if not matched:
            for token in normalized.split():
                if token.isalpha() and len(token) > 4 and token not in seen_keywords:
                    keywords.append(token)
                    seen_keywords.add(token)

    return LabelHints(keywords=keywords, categories=categories)

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

    caption = _describe_image(img)

    return ImageAnalysis(
        dominant_colors=top_colors,
        average_color=avg,
        brightness=brightness,
        aspect_ratio=aspect_ratio,
        notes=notes,
        detected_objects=detected_objects,
        caption=caption,
    )


def colors_to_filters(analysis: Optional[ImageAnalysis]) -> List[str]:
    """Map dominant colors to catalog filter values."""

    if not analysis:
        return []
    primary = []
    for color in analysis.dominant_colors:
        if color in {
            "black",
            "gray",
            "white",
            "blue",
            "navy",
            "green",
            "red",
            "yellow",
            "orange",
            "purple",
            "pink",
            "brown",
            "teal",
        }:
            primary.append(color)
    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for color in primary:
        if color not in seen:
            ordered.append(color)
            seen.add(color)
    return ordered