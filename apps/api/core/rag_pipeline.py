"""LangChain + LangGraph powered retrieval-augmented generation for the catalog.

This module wraps our sample catalog in a lightweight vector index using
SentenceTransformer embeddings, then wires a LangGraph state machine that
retrieves the best-matching products and (optionally) lets an LLM craft a
natural-language answer. Everything degrades gracefully if optional
dependencies (OpenAI key, etc.) are not available.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional, Sequence, TypedDict

import numpy as np

try:
    from langchain_core.documents import Document
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    from langgraph.graph import StateGraph, START, END
except Exception as exc:  # pragma: no cover - import guard for optional deps
    raise RuntimeError(
        "LangChain / LangGraph dependencies are required for rag_pipeline: %s" % exc
    ) from exc

try:  # OpenAI client is optional (fallback text used when missing)
    from langchain_openai import ChatOpenAI  # type: ignore
except Exception:  # pragma: no cover - optional
    ChatOpenAI = None  # type: ignore

from pydantic import ValidationError

from ..schemas import ProductCard
from .dataset import Product, load_catalog
from .web_fetch import fetch_and_extract, to_product_card
from .web_search import search as web_search


class RAGState(TypedDict, total=False):
    """Graph state passed between LangGraph nodes."""

    query: str
    k: int
    documents: List[Document]
    product_ids: List[str]
    scores: List[float]
    web_documents: List[Document]
    web_cards: List[ProductCard]
    web_scores: List[float]
    context: str
    answer: str


@dataclass
class CatalogRAGResult:
    """Structured result returned by the catalog RAG run."""

    products: List[Product]
    answer: str
    references: List[Dict[str, object]]
    scores: List[float]
    context: str
    web_cards: List[ProductCard] = field(default_factory=list)


class CatalogRAG:
    """Wraps the catalog in a LangChain/LangGraph retrieval pipeline."""

    def __init__(self, *, default_k: int = 8) -> None:
        self._logger = logging.getLogger(__name__)
        self._default_k = default_k

        model_name = os.environ.get("RAG_EMBED_MODEL", "all-MiniLM-L6-v2")
        self._embedder = SentenceTransformerEmbeddings(model_name=model_name)

        self._products = load_catalog()
        if not self._products:
            raise ValueError("Catalog is empty; cannot initialise RAG pipeline")

        self._enable_web = os.environ.get("ENABLE_RAG_WEB", "1").strip().lower() in {"1", "true", "yes", "on"}
        try:
            self._web_limit = max(0, int(os.environ.get("RAG_WEB_LIMIT", "4")))
        except ValueError:
            self._web_limit = 4

        self._documents = self._build_documents(self._products)
        self._embeddings = self._build_embeddings(self._documents)
        self._doc_norms = self._compute_norms(self._embeddings)

        self._id_to_product: Dict[str, Product] = {p.id: p for p in self._products}

        self._graph = self._build_graph()
        self._llm_chain = self._build_llm_chain()

    @staticmethod
    def _build_documents(products: Sequence[Product]) -> List[Document]:
        docs: List[Document] = []
        for product in products:
            snippet = product.description or ", ".join(product.tags[:2]) or product.category or "Catalog item"
            sections = [
                product.title,
                f"Brand: {product.brand}" if product.brand else "",
                f"Category: {product.category}" if product.category else "",
                f"Price: {product.price_cents / 100:.2f} {product.currency}",
                f"Description: {product.description}" if product.description else "",
                f"Tags: {', '.join(product.tags)}" if product.tags else "",
                f"Colors: {', '.join(product.colors)}" if product.colors else "",
            ]
            content = "\n".join(filter(None, sections))
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "product_id": product.id,
                        "title": product.title,
                        "brand": product.brand,
                        "category": product.category,
                        "snippet": snippet,
                        "price_cents": product.price_cents,
                        "currency": product.currency,
                    },
                )
            )
        return docs

    def _build_embeddings(self, documents: Sequence[Document]) -> np.ndarray:
        contents = [doc.page_content for doc in documents]
        matrix = self._embedder.embed_documents(contents)
        return np.asarray(matrix, dtype=np.float32)

    @staticmethod
    def _compute_norms(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0.0] = 1e-12
        return norms

    def _build_graph(self):
        builder = StateGraph(RAGState)
        builder.add_node("retrieve", self._retrieve_node)
        builder.add_node("generate", self._generate_node)
        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", END)
        return builder.compile()

    def _build_llm_chain(self):
        if ChatOpenAI is None:
            return None
        try:
            model_name = os.environ.get("RAG_OPENAI_MODEL", os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini"))
            llm = ChatOpenAI(model=model_name, temperature=0)
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are a product expert helping a shopper. Use the provided catalog context to answer the question.",
                    ),
                    (
                        "human",
                        "Question: {question}\n\nCatalog context:\n{context}\n\nRecommend a handful of options using short sentences (<=120 words).",
                    ),
                ]
            )
            return prompt | llm | StrOutputParser()
        except Exception as exc:  # pragma: no cover - optional dependency failure
            logging.getLogger(__name__).info("Falling back to heuristic RAG answer: %s", exc)
            return None

    def _retrieve_node(self, state: RAGState) -> RAGState:
        query = (state.get("query") or "").strip()
        if not query:
            return {"documents": [], "product_ids": [], "scores": []}

        k = int(state.get("k") or self._default_k)
        documents, scores, query_vec = self._search(query, k)
        product_ids = [doc.metadata.get("product_id", "") for doc in documents]
        web_docs: List[Document] = []
        web_cards: List[ProductCard] = []
        web_scores: List[float] = []
        if query_vec is not None:
            web_docs, web_cards, web_scores = self._search_web(query, query_vec)
        return {
            "documents": documents,
            "product_ids": product_ids,
            "scores": scores,
            "web_documents": web_docs,
            "web_cards": web_cards,
            "web_scores": web_scores,
        }

    def _generate_node(self, state: RAGState) -> RAGState:
        documents = state.get("documents", [])
        web_documents = state.get("web_documents", [])
        query = state.get("query", "")
        if not documents and not web_documents:
            return {"answer": "I could not find relevant catalog or web entries for that request.", "context": ""}

        context_lines = []
        for doc in documents[:5]:
            meta = doc.metadata
            title = meta.get("title", "Item")
            snippet = meta.get("snippet", "")
            brand = meta.get("brand")
            line_parts = [title]
            if brand:
                line_parts.append(f"({brand})")
            if snippet:
                line_parts.append(f"- {snippet}")
            context_lines.append(" ".join(line_parts))

        for doc in web_documents[:3]:
            meta = doc.metadata
            title = meta.get("title", "Web item")
            snippet = meta.get("snippet", meta.get("description", ""))
            brand = meta.get("brand")
            line_parts = [f"[web] {title}"]
            if brand:
                line_parts.append(f"({brand})")
            if snippet:
                line_parts.append(f"- {snippet}")
            context_lines.append(" ".join(line_parts))
        context = "\n".join(context_lines)

        combined_docs = documents + web_documents
        answer = self._fallback_answer(query, combined_docs)
        if self._llm_chain:
            try:
                answer = self._llm_chain.invoke({"question": query, "context": context})
            except Exception as exc:  # pragma: no cover - network failure etc.
                self._logger.warning("RAG LLM generation failed, using fallback: %s", exc)
        return {"answer": answer, "context": context}

    def _search(self, query: str, k: int) -> tuple[List[Document], List[float], Optional[np.ndarray]]:
        query_vec = np.asarray(self._embedder.embed_query(query), dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm == 0.0:
            return [], [], None
        similarities = (self._embeddings @ query_vec) / (self._doc_norms * norm)
        if similarities.ndim > 1:
            similarities = similarities.reshape(-1)
        ranked_idx = list(np.argsort(similarities)[::-1])

        documents: List[Document] = []
        scores: List[float] = []
        seen: set[str] = set()
        for idx in ranked_idx:
            pid = self._documents[idx].metadata.get("product_id", "")
            if not pid or pid in seen:
                continue
            score = float(similarities[idx])
            if score <= 0:
                continue
            documents.append(self._documents[idx])
            scores.append(score)
            seen.add(pid)
            if len(documents) >= k:
                break
        return documents, scores, query_vec

    def _search_web(
        self, query: str, query_vec: np.ndarray
    ) -> tuple[List[Document], List[ProductCard], List[float]]:
        if not self._enable_web or self._web_limit <= 0:
            return [], [], []

        try:
            urls = web_search(query, limit=self._web_limit)
        except Exception as exc:  # pragma: no cover - network / API issues
            self._logger.warning("Web search failed for RAG: %s", exc)
            return [], [], []

        query_norm = float(np.linalg.norm(query_vec))
        if query_norm == 0.0:
            return [], [], []

        documents: List[Document] = []
        cards: List[ProductCard] = []
        scores: List[float] = []
        contents: List[str] = []

        for url in urls:
            if not url:
                continue
            try:
                fetched = fetch_and_extract(url)
            except Exception:
                continue
            if not fetched:
                continue
            product = to_product_card(fetched)
            if not product:
                continue

            image_urls = product.get("image_urls") or []
            image = next((img for img in image_urls if img), None)
            description = product.get("description") or fetched.get("excerpt") or ""
            short_description = description[:280].strip() if description else None

            badges: List[str] = []
            brand = product.get("brand")
            if brand:
                badges.append(str(brand))
            for tag in product.get("tags", []):
                if tag and tag not in badges:
                    badges.append(str(tag))
            badges = badges[:3]

            try:
                card = ProductCard(
                    id=product["id"],
                    title=product.get("title") or "Product",
                    image=image,
                    price_cents=product.get("price_cents") or 0,
                    currency=product.get("currency") or "USD",
                    category=product.get("category"),
                    description=short_description,
                    badges=badges,
                    rationale=short_description,
                    source="web",
                    url=fetched.get("url"),
                )
            except (ValidationError, KeyError):
                continue

            sections = [
                card.title,
                f"Brand: {product.get('brand')}" if product.get("brand") else "",
                f"Category: {product.get('category')}" if product.get("category") else "",
                f"Description: {short_description}" if short_description else "",
            ]
            content = "\n".join(filter(None, sections))
            if not content:
                continue

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": "web",
                        "title": card.title,
                        "brand": product.get("brand"),
                        "category": product.get("category"),
                        "snippet": short_description or "",
                        "url": fetched.get("url"),
                    },
                )
            )
            cards.append(card)
            contents.append(content)

        if not documents:
            return [], [], []

        matrix = np.asarray(self._embedder.embed_documents(contents), dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0.0] = 1e-12
        similarities = (matrix @ query_vec) / (norms * query_norm)
        ranked = sorted(
            zip(documents, cards, similarities.tolist()),
            key=lambda item: item[2],
            reverse=True,
        )

        top_documents: List[Document] = []
        top_cards: List[ProductCard] = []
        top_scores: List[float] = []
        for doc, card, score in ranked:
            if score <= 0:
                continue
            top_documents.append(doc)
            top_cards.append(card)
            top_scores.append(float(score))
            if len(top_documents) >= self._web_limit:
                break

        return top_documents, top_cards, top_scores

    @staticmethod
    def _fallback_answer(query: str, documents: Sequence[Document]) -> str:
        if not documents:
            return f"I could not find matching catalog entries for '{query}'."
        titles = [doc.metadata.get("title", "an item") for doc in documents[:3]]
        joined = ", ".join(titles)
        return f"Top catalog matches for '{query}': {joined}."

    def run(self, query: str, *, top_k: Optional[int] = None) -> CatalogRAGResult:
        k = top_k or self._default_k
        state = self._graph.invoke({"query": query, "k": k})
        product_ids = state.get("product_ids", [])
        documents = state.get("documents", [])
        scores = state.get("scores", [])
        web_documents = state.get("web_documents", [])
        web_cards = state.get("web_cards", [])
        web_scores = state.get("web_scores", [])

        deduped_ids: List[str] = []
        deduped_docs: List[Document] = []
        deduped_scores: List[float] = []
        for doc, pid, score in zip(documents, product_ids, scores):
            if pid and pid in self._id_to_product and pid not in deduped_ids:
                deduped_ids.append(pid)
                deduped_docs.append(doc)
                deduped_scores.append(score)

        products = [self._id_to_product[pid] for pid in deduped_ids]
        references: List[Dict[str, object]] = []
        for doc, score in zip(deduped_docs, deduped_scores):
            meta = doc.metadata
            references.append(
                {
                    "id": meta.get("product_id"),
                    "title": meta.get("title"),
                    "brand": meta.get("brand"),
                    "category": meta.get("category"),
                    "score": round(float(score), 4),
                    "source": "catalog",
                }
            )

        for doc, card, score in zip(web_documents, web_cards, web_scores):
            meta = doc.metadata
            references.append(
                {
                    "id": card.id,
                    "title": card.title,
                    "brand": meta.get("brand"),
                    "category": meta.get("category"),
                    "score": round(float(score), 4),
                    "source": "web",
                    "url": str(card.url) if card.url else None,
                }
            )

        return CatalogRAGResult(
            products=products,
            answer=state.get("answer", ""),
            references=references,
            scores=deduped_scores,
            context=state.get("context", ""),
            web_cards=web_cards,
        )

    @property
    def is_ready(self) -> bool:
        return bool(self._documents)


_catalog_rag: Optional[CatalogRAG] = None
_catalog_lock = Lock()


def _rag_enabled_via_env() -> bool:
    flag = os.environ.get("ENABLE_LANGCHAIN_RAG", "1").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def get_catalog_rag() -> Optional[CatalogRAG]:
    """Return a singleton CatalogRAG instance when enabled, else None."""

    if not _rag_enabled_via_env():
        return None

    global _catalog_rag
    if _catalog_rag is not None:
        return _catalog_rag

    with _catalog_lock:
        if _catalog_rag is None:
            try:
                _catalog_rag = CatalogRAG()
            except Exception as exc:
                logging.getLogger(__name__).warning("Failed to initialise LangChain RAG: %s", exc)
                _catalog_rag = None
        return _catalog_rag


def reset_catalog_rag() -> None:
    """Reset the cached CatalogRAG instance (useful for tests)."""

    global _catalog_rag
    with _catalog_lock:
        _catalog_rag = None
