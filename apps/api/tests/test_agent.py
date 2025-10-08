from api.routers.agent import _detect_intent, _smalltalk_response


def test_detect_intent_smalltalk():
    assert _detect_intent("Hello, what's your name?", has_image=False) == "smalltalk"


def test_detect_intent_image_keyword():
    assert _detect_intent("Show me an image of red shoes", has_image=False) == "image_search"


def test_detect_intent_with_image_flag():
    assert _detect_intent("", has_image=True) == "image_search"


def test_smalltalk_name_response():
    assert "CommerceAgent" in _smalltalk_response("What's your name?")

