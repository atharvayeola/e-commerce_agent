from __future__ import annotations

import os
from typing import Optional

import requests

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/gpt2"
HF_TOKEN = os.environ.get("HF_TOKEN")


def summarize_text(text: str, max_length: int = 200) -> str:
    """Try to call HF Inference API if token present, otherwise return a simple mock summary."""
    if HF_TOKEN:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {"inputs": text[:1000]}
        try:
            resp = requests.post(HF_INFERENCE_URL, headers=headers, json=payload, timeout=5)
            if resp.ok:
                data = resp.json()
                # HF text-generation models return list of outputs; pick the text
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "")[:max_length]
        except Exception:
            pass
    # Mock fallback: return the first 200 chars + ellipsis
    return (text[: max_length - 3] + "...") if len(text) > max_length else text
