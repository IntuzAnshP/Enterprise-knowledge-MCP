from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
import time

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.embedding.embedding_service import EmbeddingService
from app.schemas.retrieval import (
    MetadataFilter, 
    RetrievedChunk, 
    ChunkCitation, 
    SearchKnowledgeResult
)
from app.retrieval.reranker_service import RerankerService
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class RetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.reranker_service = RerankerService()
        # BGE models require this prefix for asymmetric retrieval queries
        self.query_prefix = "Represent this sentence for searching relevant passages: "

    def search(
        self,
        query: str,
        filters: Optional[MetadataFilter],
        limit: int,
        db: Session
    ) -> SearchKnowledgeResult:
        """
        Main retrieval pipeline:
        1. Embed the query
        2. Perform pgvector similarity search
        3. Apply metadata filters
        4. (Optional) Apply CrossEncoder reranking
        5. Format and return citations
        """
        pipeline_start = time.perf_counter()

        logger.info("=" * 60)
        logger.info(f"[RETRIEVAL] Query: \"{query}\"")

        # Log active filters
        if filters and any([filters.source_type, filters.content_type, filters.document_id]):
            active = {k: v for k, v in filters.model_dump().items() if v is not None}
            logger.info(f"[RETRIEVAL] Filters: {active}")
        else:
            logger.info("[RETRIEVAL] Filters: none (global search)")

        logger.info(f"[RETRIEVAL] Limit: {limit} | Reranker: {'ON' if settings.ENABLE_RERANKER else 'OFF'}")

        # 1. Embed query (with BGE prefix)
        t0 = time.perf_counter()
        full_query = f"{self.query_prefix}{query}"
        query_embedding = self.embedding_service.embed_single(full_query)
        embed_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[EMBEDDING] Query embedded in {embed_ms:.1f}ms (dim={len(query_embedding)})")

        # 2 & 3. pgvector similarity search with metadata filtering
        # Include distance in the select
        distance_col = DocumentChunk.embedding.cosine_distance(query_embedding).label('distance')
        stmt = select(DocumentChunk, Document, distance_col).join(
            Document, DocumentChunk.document_id == Document.id
        )

        # Apply filters if provided
        where_clauses = []
        if filters:
            if filters.source_type:
                where_clauses.append(Document.source_type == filters.source_type)
            if filters.content_type:
                where_clauses.append(Document.content_type == filters.content_type)
            if filters.document_id:
                where_clauses.append(Document.id == filters.document_id)
                
        if where_clauses:
            stmt = stmt.where(and_(*where_clauses))

        # Retrieve TOP_K candidates first for potential reranking
        candidate_limit = settings.RETRIEVAL_TOP_K if settings.ENABLE_RERANKER else limit
        stmt = stmt.order_by(distance_col).limit(candidate_limit)
        
        # Execute the query
        t0 = time.perf_counter()
        results = db.execute(stmt).all()
        search_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[PGVECTOR] Search completed in {search_ms:.1f}ms — retrieved {len(results)} candidates (limit={candidate_limit})")

        candidates: List[RetrievedChunk] = []
        
        for chunk, doc, distance in results:
            # Distance is 1 - cosine_similarity for pgvector
            similarity_score = 1.0 - float(distance)
            
            # Extract metadata safely
            metadata = chunk.metadata_ or {}
            
            citation = ChunkCitation(
                document_id=str(doc.id),
                document_title=doc.title,
                source_type=doc.source_type,
                source_url=doc.source_url,
                page_number=metadata.get("page_number"),
                sheet_name=metadata.get("sheet_name"),
                heading_context=metadata.get("heading_context"),
                section_context=metadata.get("section_context"),
            )
            
            retrieved = RetrievedChunk(
                chunk_id=str(chunk.id),
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                score=similarity_score,
                citation=citation
            )
            
            candidates.append(retrieved)

        # Log top candidate scores before reranking
        if candidates:
            top_scores = [f"{c.score:.4f}" for c in candidates[:5]]
            logger.info(f"[PGVECTOR] Top-5 similarity scores: [{', '.join(top_scores)}]")
            
        reranked = False
        final_chunks = candidates
        
        # 4. Optional Reranking
        if settings.ENABLE_RERANKER and candidates:
            t0 = time.perf_counter()
            logger.info(f"[RERANKER] Reranking {len(candidates)} candidates → selecting top {limit}...")
            final_chunks = self.reranker_service.rerank(query, candidates, top_n=limit)
            rerank_ms = (time.perf_counter() - t0) * 1000
            reranked = True
            top_reranked = [f"{c.score:.4f}" for c in final_chunks]
            logger.info(f"[RERANKER] Done in {rerank_ms:.1f}ms — final scores: [{', '.join(top_reranked)}]")
        else:
            final_chunks = candidates[:limit]

        # Summary
        total_ms = (time.perf_counter() - pipeline_start) * 1000
        logger.info(f"[RETRIEVAL] Returning {len(final_chunks)} chunks | Total pipeline time: {total_ms:.1f}ms")
        if final_chunks:
            for i, chunk in enumerate(final_chunks):
                logger.info(
                    f"  [{i+1}] score={chunk.score:.4f} | doc=\"{chunk.citation.document_title}\" "
                    f"| type={chunk.chunk_type} | chunk_idx={chunk.chunk_index}"
                )
        logger.info("=" * 60)
            
        return SearchKnowledgeResult(
            query=query,
            total_candidates=len(candidates),
            returned_chunks=len(final_chunks),
            reranked=reranked,
            chunks=final_chunks
        )
