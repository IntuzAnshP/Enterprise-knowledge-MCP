from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.database import get_db
from app.retrieval.retrieval_service import RetrievalService
from app.schemas.retrieval import MetadataFilter, SearchKnowledgeResult
from app.schemas.api_response import APIResponse
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.config import settings

router = APIRouter()
retrieval_service = RetrievalService()

class SearchRequest(BaseModel):
    query: str
    filters: Optional[MetadataFilter] = None
    limit: int = settings.RETRIEVAL_FINAL_K

@router.post("/search", response_model=APIResponse[SearchKnowledgeResult])
def search_knowledge(request: SearchRequest, db: Session = Depends(get_db)):
    try:
        result = retrieval_service.search(
            query=request.query,
            filters=request.filters,
            limit=request.limit,
            db=db
        )
        return APIResponse(
            message=f"Found {result.returned_chunks} relevant chunks",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/{document_id}/chunks/{chunk_id}", response_model=APIResponse[Dict[str, Any]])
def get_document_chunk(document_id: str, chunk_id: str, db: Session = Depends(get_db)):
    chunk = db.query(DocumentChunk).filter(
        DocumentChunk.id == chunk_id,
        DocumentChunk.document_id == document_id
    ).first()
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
        
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return APIResponse(
        message="Successfully retrieved chunk",
        data={
            "chunk_id": str(chunk.id),
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "metadata": chunk.metadata_ or {},
            "document_title": doc.title,
            "source_type": doc.source_type,
            "source_url": doc.source_url
        }
    )
