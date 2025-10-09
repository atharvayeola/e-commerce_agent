import base64
import io

from PIL import Image

from api.routers.catalog import image_search
from api.schemas import ImageSearchRequest


def _blue_image_b64() -> str:
    img = Image.new("RGB", (32, 32), (30, 80, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_image_search_uses_color_hints():
    payload = ImageSearchRequest(image_b64=_blue_image_b64(), query=None, limit=2)
    response = image_search(payload)
    assert response.results
    first = response.results[0]
    assert first.source == "catalog"
    assert response.debug["matched"] > 0
    dominant = response.debug.get("image_analysis", {}).get("dominant_colors", [])
    assert dominant
    assert dominant[0] in {"blue", "navy"}