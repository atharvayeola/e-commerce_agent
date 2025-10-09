from api.routers.agent import _detect_intent, _smalltalk_response


def test_detect_intent_smalltalk():
    intent, topic = _detect_intent("Hello, what's your name?", has_image=False)
    assert intent == "smalltalk"
    assert topic == "identity"

def test_detect_intent_image_keyword():
    intent, topic = _detect_intent("Show me an image of red shoes", has_image=False)
    assert intent == "image_search"
    assert topic is None


def test_detect_intent_with_image_flag():
    intent, topic = _detect_intent("", has_image=True)
    assert intent == "image_search"
    assert topic is None



def test_smalltalk_name_response():
    response = _smalltalk_response("What's your name?", topic="identity")
    assert "CommerceAgent" in response


