from api.routers.agent import _catalog_product_cards, _catalog_query_terms


def test_catalog_query_terms_filters_stopwords():
    terms = _catalog_query_terms("Show me the red running shoes")
    assert "show" not in terms
    assert "me" not in terms
    assert "the" not in terms
    assert "red" in terms
    assert "running" in terms
    assert "shoes" in terms


def test_catalog_query_terms_removes_connector_words_and_numbers():
    terms = _catalog_query_terms("I want to buy a smartwatch and my budget is not more than 500")
    assert terms == ["smartwatch"], terms


def test_catalog_product_cards_returns_catalog_match():
    cards = _catalog_product_cards("Need noise cancelling headphones", limit=5)
    assert cards, "Expected catalog lookup to return at least one product"
    top_card = cards[0]
    assert top_card.source == "catalog"
    assert "headphones" in top_card.title.lower()
    assert top_card.category == "electronics"
    assert top_card.description


def test_catalog_product_cards_focus_on_relevant_matches():
    cards = _catalog_product_cards("Looking for a smartwatch", limit=5)
    assert cards, "Expected smartwatch lookup to return catalog results"
    assert all("smartwatch" in card.title.lower() for card in cards)