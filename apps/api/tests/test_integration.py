import json

import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_root_health():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "message" in body


def test_agent_chat_smalltalk():
    payload = {"message": "Hi there"}
    r = client.post("/agent/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "smalltalk"


def test_agent_chat_recommendation():
    payload = {"message": "I want running shoes"}
    r = client.post("/agent/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "text_recommendation"
    assert isinstance(data.get("products", []), list)


def test_recommend_endpoint():
    payload = {"goal": "comfortable sandals", "limit": 3}
    r = client.post("/recommend", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert len(data["results"]) <= 3

