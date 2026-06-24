"""
RAG 知识库服务 — Semantic Structured Chunking + Hybrid Search (BM25 + Vector)
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.database import SessionLocal
from app.db.models import RagDocument, RagChunk, RagChunkEmbedding
from app.utils.helpers import create_httpx_client, estimate_tokens
from app.utils.chunking import (
    structured_chunk,
    build_embedding_content,
    generate_keywords,
    extract_metadata,
    BM25Scorer,
    tokenize_query,
    fuse_scores,
)
from app.schemas.chunk import (
    ChunkType, CarMetadata, SearchFilters, SearchResult,
    ChunkingResult,
)


class RAGService:
    """Car price knowledge base with semantic structured chunking and hybrid search.

    Key capabilities:
      - Semantic Structured Chunking (Brand → Model → Feature → Comparison)
      - One model → one core ModelChunk
      - Feature isolation as standalone chunks
      - Brand summaries auto-generated
      - Metadata-driven filtering
      - Hybrid search: BM25 pre-filter + Vector similarity + score fusion
      - Re-ranking with keyword overlap
      - Context compression with dedup
    """

    def __init__(
        self,
        embedding_model: str = "bge-m3",
        embedding_dim: int = 1024,
        ollama_base_url: str = None,
    ):
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.ollama_base_url = (ollama_base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._bm25 = BM25Scorer()

    # ═══════════════════════════════════════════════════════════
    #  Embedding
    # ═══════════════════════════════════════════════════════════

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via Ollama /api/embed (batch)."""
        with create_httpx_client(timeout=120) as client:
            payload = {"model": self.embedding_model, "input": texts}
            resp = client.post(f"{self.ollama_base_url}/api/embed", json=payload)
            if resp.status_code != 200:
                # Fallback to sequential /api/embeddings
                results = []
                for text_chunk in texts:
                    payload2 = {"model": self.embedding_model, "prompt": text_chunk}
                    resp2 = client.post(
                        f"{self.ollama_base_url}/api/embeddings", json=payload2
                    )
                    if resp2.status_code != 200:
                        raise RuntimeError(
                            f"Embedding failed ({resp2.status_code}): {resp2.text[:300]}. "
                            f"Is '{self.embedding_model}' pulled?"
                        )
                    results.append(resp2.json()["embedding"])
                return results
            return resp.json()["embeddings"]

    def embed_query(self, query: str) -> List[float]:
        """Generate a single query embedding."""
        return self._embed([query])[0]

    # ═══════════════════════════════════════════════════════════
    #  Structured Chunking Pipeline
    # ═══════════════════════════════════════════════════════════

    def chunk_document(
        self,
        text: str,
        source_brand: str = "",
        source_model: str = "",
        source: str = "car_price",
        extract_features: bool = True,
    ) -> ChunkingResult:
        """Run the full Semantic Structured Chunking pipeline.

        Produces typed chunks: BrandChunk → ModelChunk → FeatureChunk → ComparisonChunk.

        Returns ChunkingResult with all chunk types.
        """
        return structured_chunk(
            text=text,
            source_brand=source_brand,
            source_model=source_model,
            source=source,
            extract_features=extract_features,
        )

    # ═══════════════════════════════════════════════════════════
    #  Ingestion Pipeline
    # ═══════════════════════════════════════════════════════════

    def ingest_car_data(self, db: Session, car_json: dict) -> Optional[int]:
        """Full ingestion pipeline: validate → chunk → embed → store.

        Uses Semantic Structured Chunking to produce brand/model/feature chunks.

        Returns the document ID, or None if the document already exists.
        """
        # 1. Validate
        ok, msg = validate_car_json(car_json)
        if not ok:
            logger.warning(f"Skipping car data: {msg}")
            return None

        # 2. Build text representation
        doc_text = _car_json_to_text(car_json)
        content_hash = hashlib.sha256(doc_text.encode()).hexdigest()

        # 3. Dedup
        existing = db.query(RagDocument).filter(
            RagDocument.content_hash == content_hash,
            RagDocument.is_deleted == False,
        ).first()
        if existing:
            logger.info(f"Car data already ingested (doc_id={existing.id})")
            return existing.id

        # 4. Create document record
        source_brand = car_json.get("brand", "")
        source_model = car_json.get("model", "")
        doc = RagDocument(
            source_type="car_price",
            source_uri=car_json.get("source_url", ""),
            title=f"{source_brand} {source_model} ({car_json.get('year', '?')})",
            content_hash=content_hash,
            doc_status="ready",
            metadata_={
                "brand": source_brand,
                "model": source_model,
                "year": car_json.get("year"),
                "energy_type": car_json.get("energy_type"),
            },
        )
        db.add(doc)
        db.flush()

        # 5. Structured chunking
        result = self.chunk_document(
            doc_text,
            source_brand=source_brand,
            source_model=source_model,
            source="car_price",
        )
        if not result.all_chunks:
            logger.warning(f"No chunks generated for {doc.title}")
            return doc.id

        # 6. Embed all chunks using embedding_content
        embedding_texts = [c.embedding_content for c in result.all_chunks]
        try:
            embeddings = self._embed(embedding_texts)
        except Exception:
            logger.exception("Embedding generation failed")
            db.rollback()
            raise

        # 7. Store chunks + embeddings
        try:
            self._store_chunks(
                db=db,
                doc_id=doc.id,
                chunking_result=result,
                embeddings=embeddings,
            )
        except Exception:
            db.rollback()
            raise

        db.commit()
        logger.info(
            f"Ingested car data: {doc.title} "
            f"(doc_id={doc.id}, chunks={len(result.all_chunks)})"
        )
        return doc.id

    def ingest_free_text(
        self,
        db: Session,
        content: str,
        title: str = "",
        brand: str = "",
        model: str = "",
        source_type: str = "user_saved",
    ) -> Optional[int]:
        """Ingest arbitrary text into the knowledge base with structured chunking."""
        if not content or not content.strip():
            return None

        content = content.strip()
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Dedup
        existing = db.query(RagDocument).filter(
            RagDocument.content_hash == content_hash,
            RagDocument.is_deleted == False,
        ).first()
        if existing:
            logger.info(f"Free text already ingested (doc_id={existing.id})")
            return existing.id

        if not title:
            title = content[:100].replace("\n", " ").strip()
            if len(title) >= 100:
                title = title[:97] + "..."

        doc = RagDocument(
            source_type=source_type,
            source_uri="",
            title=title,
            content_hash=content_hash,
            doc_status="ready",
            metadata_={"brand": brand, "model": model, "source_type": source_type},
        )
        db.add(doc)
        db.flush()

        result = self.chunk_document(
            content, source_brand=brand, source_model=model, source=source_type,
        )
        if not result.all_chunks:
            logger.warning(f"No chunks generated for free text: {title[:50]}")
            return doc.id

        embedding_texts = [c.embedding_content for c in result.all_chunks]
        try:
            embeddings = self._embed(embedding_texts)
        except Exception:
            logger.exception("Embedding generation failed for free text")
            db.rollback()
            raise

        try:
            self._store_chunks(db=db, doc_id=doc.id, chunking_result=result, embeddings=embeddings)
        except Exception:
            db.rollback()
            raise

        db.commit()
        logger.info(
            f"Ingested free text: {title[:50]} (doc_id={doc.id}, chunks={len(result.all_chunks)})"
        )
        return doc.id

    def ingest_batch(self, db: Session, car_list: List[dict]) -> int:
        """Batch ingest multiple car records."""
        count = 0
        for car_json in car_list:
            try:
                doc_id = self.ingest_car_data(db, car_json)
                if doc_id:
                    count += 1
            except Exception:
                logger.exception(
                    f"Failed to ingest: {car_json.get('brand', '?')} {car_json.get('model', '?')}"
                )
                db.rollback()
        return count

    def _store_chunks(
        self, db: Session, doc_id: int,
        chunking_result: ChunkingResult,
        embeddings: List[List[float]],
    ) -> None:
        """Store all chunk types + embeddings from a ChunkingResult."""
        all_chunks = chunking_result.all_chunks
        for i, (chunk_obj, vector) in enumerate(zip(all_chunks, embeddings)):
            chunk_type = chunk_obj.chunk_type
            content = chunk_obj.content
            metadata_dict = _chunk_to_metadata_dict(chunk_obj)
            metadata_dict["document_id"] = doc_id

            chunk_row = RagChunk(
                document_id=doc_id,
                chunk_index=i,
                chunk_id=chunk_obj.chunk_id,
                chunk_type=str(chunk_type),
                content=content,
                token_count=estimate_tokens(chunk_obj.embedding_content),
                metadata_=metadata_dict,
            )
            db.add(chunk_row)
            db.flush()

            embedding_row = RagChunkEmbedding(
                chunk_id=chunk_row.id,
                embedding_model=self.embedding_model,
                embedding=vector,
                metadata={"dim": self.embedding_dim},
            )
            db.add(embedding_row)

    # ═══════════════════════════════════════════════════════════
    #  Hybrid Search (BM25 + Vector)
    # ═══════════════════════════════════════════════════════════

    def search(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        rerank: bool = True,
        hybrid: bool = True,
    ) -> List[Dict]:
        """Hybrid search: BM25 pre-filter + Vector similarity + score fusion.

        Pipeline:
        1. Tokenize query → BM25 terms
        2. Vector search via pgvector cosine distance
        3. Apply metadata filters (brand, model, chunk_type, etc.)
        4. BM25 keyword scoring on retrieval_keywords
        5. Score fusion: 60% vector + 40% BM25
        6. Optional re-rank with keyword overlap
        """
        fetch_k = top_k * 3 if hybrid else top_k * 2
        query_embedding = self.embed_query(query)
        query_terms = tokenize_query(query) if hybrid else []

        # Base query: vector similarity search
        q = (
            db.query(
                RagChunk,
                RagChunkEmbedding,
                RagDocument,
                RagChunkEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(RagChunkEmbedding, RagChunkEmbedding.chunk_id == RagChunk.id)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .filter(RagChunk.is_deleted == False)
            .filter(RagChunkEmbedding.is_deleted == False)
            .filter(RagDocument.is_deleted == False)
        )

        # Apply metadata filters
        q = self._apply_filters(q, filters)

        # Prefer model chunks for general queries, but allow all types
        if filters is None or "chunk_type" not in (filters or {}):
            # Boost model chunks: fetch more of them
            pass

        rows = q.order_by("distance").limit(fetch_k).all()

        # Build results with BM25 scoring
        results = []
        max_bm25 = 0.0
        for chunk, embedding_row, doc, distance in rows:
            vec_sim = round(1 - float(distance), 4)
            chunk_meta = chunk.metadata_ or {}

            # BM25 score on retrieval_keywords
            doc_keywords = chunk_meta.get("retrieval_keywords", [])
            bm25 = self._bm25.score(
                query_terms, doc_keywords,
                doc_length=len(chunk.content or ""),
                avg_doc_length=500.0,
            ) if hybrid else 0.0
            max_bm25 = max(max_bm25, bm25)

            results.append({
                "chunk_id": chunk_meta.get("chunk_id", f"chunk:{chunk.id}"),
                "chunk_type": chunk.chunk_type,
                "brand": chunk_meta.get("brand", ""),
                "model": chunk_meta.get("model", ""),
                "content": chunk.content,
                "distance": float(distance),
                "similarity": vec_sim,
                "bm25_score": round(bm25, 4),
                "combined_score": 0.0,  # computed below
                "metadata": chunk_meta,
                "retrieval_keywords": doc_keywords,
                "document_id": doc.id,
                "title": doc.title,
                "source_url": doc.source_uri or "",
                "topic": chunk_meta.get("topic", ""),
                "price_range": chunk_meta.get("price_range", ""),
                "vehicle_type": chunk_meta.get("vehicle_type", ""),
                "power_type": chunk_meta.get("power_type", []),
                "smart_drive": chunk_meta.get("smart_drive", ""),
                "year": chunk_meta.get("year", ""),
            })

        # Fuse scores
        for r in results:
            r["combined_score"] = fuse_scores(
                vector_similarity=r["similarity"],
                bm25_score=r["bm25_score"],
                max_bm25=max_bm25,
            )

        # Sort by combined score
        results.sort(key=lambda x: x["combined_score"], reverse=True)

        # Re-rank if requested
        if rerank and results:
            results = self._rerank(query, results, top_k)
        else:
            results = results[:top_k]

        logger.info(
            f"Hybrid search: '{query[:60]}' → {len(results)} results "
            f"(hybrid={hybrid}, filters={bool(filters)})"
        )
        return results

    def _apply_filters(self, query, filters: Optional[Dict]):
        """Apply typed metadata filters to a SQLAlchemy query."""
        if not filters:
            return query

        # Brand filter (on chunk metadata JSONB)
        if filters.get("brand"):
            query = query.filter(
                func.lower(func.jsonb_extract_path_text(RagChunk.metadata_, 'brand'))
                == filters["brand"].lower()
            )

        # Model filter
        if filters.get("model"):
            query = query.filter(
                func.lower(func.jsonb_extract_path_text(RagChunk.metadata_, 'model'))
                == filters["model"].lower()
            )

        # Chunk type filter
        if filters.get("chunk_type"):
            query = query.filter(RagChunk.chunk_type == filters["chunk_type"])

        # Vehicle type filter
        if filters.get("vehicle_type"):
            query = query.filter(
                func.jsonb_extract_path_text(RagChunk.metadata_, 'vehicle_type')
                == filters["vehicle_type"]
            )

        # Smart drive filter
        if filters.get("smart_drive"):
            query = query.filter(
                func.jsonb_extract_path_text(RagChunk.metadata_, 'smart_drive')
                == filters["smart_drive"]
            )

        # Price range filter
        if filters.get("price_range"):
            query = query.filter(
                func.jsonb_extract_path_text(RagChunk.metadata_, 'price_range')
                == filters["price_range"]
            )

        # Year filter
        if filters.get("year"):
            query = query.filter(
                func.jsonb_extract_path_text(RagChunk.metadata_, 'year')
                == filters["year"]
            )

        # Topic filter (for feature chunks)
        if filters.get("topic"):
            query = query.filter(
                func.jsonb_extract_path_text(RagChunk.metadata_, 'topic')
                == filters["topic"]
            )

        return query

    def structured_search(
        self,
        db: Session,
        query: str,
        search_filters: SearchFilters,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Typed structured search using SearchFilters."""
        filters_dict = {}
        if search_filters.brand:
            filters_dict["brand"] = search_filters.brand
        if search_filters.model:
            filters_dict["model"] = search_filters.model
        if search_filters.chunk_type:
            filters_dict["chunk_type"] = str(search_filters.chunk_type)
        if search_filters.vehicle_type:
            filters_dict["vehicle_type"] = search_filters.vehicle_type
        if search_filters.power_type:
            filters_dict["power_type"] = search_filters.power_type
        if search_filters.smart_drive:
            filters_dict["smart_drive"] = search_filters.smart_drive
        if search_filters.price_range:
            filters_dict["price_range"] = search_filters.price_range
        if search_filters.year:
            filters_dict["year"] = search_filters.year
        if search_filters.topic:
            filters_dict["topic"] = search_filters.topic

        raw_results = self.search(db, query, top_k=top_k, filters=filters_dict or None)

        typed_results = []
        for r in raw_results:
            typed_results.append(SearchResult(
                chunk_id=r["chunk_id"],
                chunk_type=ChunkType(r["chunk_type"]),
                brand=r["brand"],
                model=r["model"],
                content=r["content"],
                similarity=r["similarity"],
                bm25_score=r.get("bm25_score", 0.0),
                combined_score=r.get("combined_score", 0.0),
                metadata=CarMetadata(
                    brand=r["brand"],
                    model=r["model"],
                    price_range=r.get("price_range", ""),
                    vehicle_type=r.get("vehicle_type", ""),
                    power_type=r.get("power_type", []),
                    smart_drive=r.get("smart_drive", ""),
                    year=r.get("year", ""),
                ),
                retrieval_keywords=r.get("retrieval_keywords", []),
                document_id=r.get("document_id"),
                title=r.get("title", ""),
                source_url=r.get("source_url", ""),
            ))

        return typed_results

    # ═══════════════════════════════════════════════════════════
    #  Re-rank
    # ═══════════════════════════════════════════════════════════

    def _rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """Re-rank using keyword overlap scoring + brand boost.

        Combined score weighting:
          0.3 * vector_similarity + 0.4 * keyword_overlap + 0.15 * brand_boost + 0.15 * chunk_type_boost
        """
        if not candidates:
            return candidates

        # Extract query terms
        query_terms = set()
        for i in range(len(query) - 1):
            bigram = query[i:i+2]
            if not any(c in ' \t\n\r,，。！？、：；()（）' for c in bigram):
                query_terms.add(bigram)
        for word in query.split():
            if len(word) > 1:
                query_terms.add(word.lower())

        if not query_terms:
            return candidates[:top_k]

        for c in candidates:
            content = (c.get("content", "") + " " + c.get("title", "")).lower()

            # Keyword overlap
            matches = sum(1 for term in query_terms if term in content)
            keyword_score = min(matches / len(query_terms), 1.0) if query_terms else 0.0

            # Brand boost
            brand_boost = 0.0
            brand = c.get("brand", "")
            if brand and brand in query:
                brand_boost = 0.15
            elif brand:
                # Partial brand match
                for b_name in [brand]:
                    if any(ch in query for ch in [b_name[:2], b_name]):
                        brand_boost = 0.08
                        break

            # Chunk type boost: model chunks are more informative
            type_boost = 0.0
            chunk_type = c.get("chunk_type", "")
            if chunk_type == "model":
                type_boost = 0.05
            elif chunk_type == "feature":
                type_boost = 0.02

            c["keyword_score"] = round(keyword_score, 4)
            c["combined_score"] = round(
                0.3 * c.get("similarity", 0)
                + 0.4 * keyword_score
                + 0.15 * brand_boost
                + 0.15 * type_boost,
                4,
            )

        candidates.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
        return candidates[:top_k]

    # ═══════════════════════════════════════════════════════════
    #  Context Compression
    # ═══════════════════════════════════════════════════════════

    def compress_context(
        self,
        results: List[Dict],
        query: str,
        max_total_tokens: int = 2000,
        prefer_model_chunks: bool = True,
    ) -> str:
        """Build a compressed LLM-ready context string.

        Strategy:
        1. Sort: model chunks first (most informative), then features, then brands
        2. Deduplicate by content signature
        3. Extract query-relevant sentences from oversized chunks
        4. Enforce total token budget
        """
        if not results:
            return ""

        # Sort: model chunks first for better context quality
        if prefer_model_chunks:
            type_order = {"model": 0, "feature": 1, "comparison": 2, "brand": 3}
            results = sorted(results, key=lambda r: type_order.get(r.get("chunk_type", ""), 9))

        parts = ["以下是从知识库中检索到的车辆相关信息：\n"]
        total_tokens = estimate_tokens(parts[0])
        seen_hashes = set()

        for i, r in enumerate(results):
            if total_tokens >= max_total_tokens:
                break

            content = r.get("content", "")
            content_sig = hashlib.md5(content[:100].encode()).hexdigest()
            if content_sig in seen_hashes:
                continue
            seen_hashes.add(content_sig)

            budget = min(500, max_total_tokens - total_tokens)
            if estimate_tokens(content) > budget:
                content = self._extract_relevant_sentences(content, query)

            # Build entry with structured metadata
            chunk_type = r.get("chunk_type", "")
            brand = r.get("brand", "")
            model = r.get("model", "")
            topic = r.get("topic", "")
            title = r.get("title", "未知")

            entry = f"---\n[来源 {i+1}] {title}"
            if brand:
                entry += f" | 品牌: {brand}"
            if model:
                entry += f" | 车型: {model}"
            if topic:
                entry += f" | 主题: {topic}"
            if chunk_type:
                type_labels = {"model": "车型综述", "feature": "特性详情", "brand": "品牌概览", "comparison": "对比"}
                entry += f" | 类型: {type_labels.get(chunk_type, chunk_type)}"

            price = r.get("price_range", "")
            if price:
                entry += f" | 价格: {price}"
            sd = r.get("smart_drive", "")
            if sd:
                entry += f" | 智驾: {sd}"

            entry += f"\n{content}\n"

            entry_tokens = estimate_tokens(entry)
            if total_tokens + entry_tokens > max_total_tokens:
                break

            parts.append(entry)
            total_tokens += entry_tokens

        return "\n".join(parts)

    def _extract_relevant_sentences(self, text: str, query: str, max_sentences: int = 5) -> str:
        """Extract query-relevant sentences via keyword overlap scoring."""
        import re as _re
        sentences = _re.split(r'(?<=[。！？；.!?])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

        if len(sentences) <= max_sentences:
            return text

        query_terms = set()
        for i in range(len(query) - 1):
            bigram = query[i:i+2]
            if not any(c in ' \t\n\r,，。！？、：；()（）' for c in bigram):
                query_terms.add(bigram)
        for word in query.split():
            if len(word) > 1:
                query_terms.add(word.lower())

        if not query_terms:
            return text[:1000]

        scored = [(sum(1 for t in query_terms if t in s.lower()), s) for s in sentences]
        scored.sort(key=lambda x: x[0], reverse=True)

        top = scored[:max_sentences]
        order_map = {sent: i for i, sent in enumerate(sentences)}
        top.sort(key=lambda s: order_map.get(s[1], 0))

        return " ".join(s[1] for s in top)

    def build_context(self, db: Session, query: str, top_k: int = 5) -> str:
        """Build an LLM-ready compressed context string.

        Pipeline: hybrid search → re-rank → compress_context
        """
        results = self.search(db, query, top_k=top_k * 2, rerank=True, hybrid=True)
        if not results:
            return ""
        return self.compress_context(results, query)

    # ═══════════════════════════════════════════════════════════
    #  Maintenance
    # ═══════════════════════════════════════════════════════════

    def delete_document(self, db: Session, doc_id: int) -> bool:
        """Soft-delete a document and its chunks/embeddings."""
        doc = db.query(RagDocument).filter(RagDocument.id == doc_id).first()
        if not doc:
            return False
        doc.is_deleted = True
        doc.deleted_at = datetime.now(timezone.utc)

        db.query(RagChunk).filter(RagChunk.document_id == doc_id).update(
            {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}
        )
        db.query(RagChunkEmbedding).filter(
            RagChunkEmbedding.chunk_id.in_(
                db.query(RagChunk.id).filter(RagChunk.document_id == doc_id)
            )
        ).update({"is_deleted": True, "deleted_at": datetime.now(timezone.utc)},
                 synchronize_session=False)

        db.commit()
        logger.info(f"Soft-deleted document {doc_id}")
        return True

    def get_stats(self, db: Session) -> Dict:
        """Return knowledge base statistics with chunk type breakdown."""
        doc_count = db.query(RagDocument).filter(RagDocument.is_deleted == False).count()
        chunk_count = db.query(RagChunk).filter(RagChunk.is_deleted == False).count()

        # Chunk type breakdown
        from sqlalchemy import func as sa_func
        type_counts = (
            db.query(RagChunk.chunk_type, sa_func.count(RagChunk.id))
            .filter(RagChunk.is_deleted == False)
            .group_by(RagChunk.chunk_type)
            .all()
        )
        chunk_types = {t: c for t, c in type_counts}

        brands = (
            db.query(func.jsonb_extract_path_text(RagDocument.metadata_, 'brand'))
            .select_from(RagDocument)
            .filter(RagDocument.is_deleted == False)
            .distinct()
            .all()
        )

        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "chunk_types": chunk_types,
            "brands": sorted([b[0] for b in brands if b[0] and b[0].strip()]),
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
        }


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _car_json_to_text(car: dict) -> str:
    """Convert structured car JSON to natural-language text."""
    parts = [
        f"品牌：{car.get('brand', '?')}",
        f"车型：{car.get('model', '?')}",
    ]
    if car.get("year"):
        parts.append(f"年份：{car['year']}")
    if car.get("price"):
        parts.append(f"官方售价：{car['price']}")
    if car.get("dealer_price"):
        parts.append(f"经销商报价：{car['dealer_price']}")
    if car.get("used_price"):
        parts.append(f"二手车价格：{car['used_price']}")
    if car.get("energy_type"):
        parts.append(f"能源类型：{car['energy_type']}")
    if car.get("range_km"):
        parts.append(f"续航里程：{car['range_km']} km")
    if car.get("horsepower"):
        parts.append(f"马力：{car['horsepower']}")
    if car.get("battery"):
        parts.append(f"电池：{car['battery']}")
    if car.get("transmission"):
        parts.append(f"变速箱：{car['transmission']}")
    if car.get("publish_time"):
        parts.append(f"发布时间：{car['publish_time']}")
    if car.get("source_url"):
        parts.append(f"来源：{car['source_url']}")
    if car.get("content"):
        parts.append(f"详情：{car['content']}")
    return "\n".join(parts)


def validate_car_json(data: dict) -> tuple:
    """Validate a car data dict against the standard schema."""
    if not isinstance(data, dict):
        return False, "Not a dict"
    if not data.get("brand"):
        return False, "Missing required field: brand"
    if not data.get("model"):
        return False, "Missing required field: model"
    return True, "ok"


def _chunk_to_metadata_dict(chunk_obj) -> dict:
    """Convert a typed chunk object to a flat metadata dict for JSONB storage."""
    from app.schemas.chunk import BrandChunk, ModelChunk, FeatureChunk, ComparisonChunk

    base = {
        "chunk_id": chunk_obj.chunk_id,
        "chunk_type": str(chunk_obj.chunk_type),
        "brand": chunk_obj.brand if hasattr(chunk_obj, "brand") else "",
        "model": chunk_obj.model if hasattr(chunk_obj, "model") else "",
        "embedding_content": chunk_obj.embedding_content,
        "retrieval_keywords": chunk_obj.retrieval_keywords,
    }

    # Car metadata
    meta = chunk_obj.metadata
    base["price_range"] = meta.price_range
    base["vehicle_type"] = meta.vehicle_type
    base["power_type"] = meta.power_type
    base["smart_drive"] = meta.smart_drive
    base["year"] = meta.year
    base["source"] = meta.source

    # Chunk-type-specific fields
    if isinstance(chunk_obj, FeatureChunk):
        base["topic"] = chunk_obj.topic
    elif isinstance(chunk_obj, ComparisonChunk):
        base["brands"] = chunk_obj.brands
        base["models"] = chunk_obj.models
        base["comparison_dimensions"] = chunk_obj.comparison_dimensions

    return base


# ═══════════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════════

rag_service = RAGService()
