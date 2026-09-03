from pydantic import BaseModel
from typing import Optional, List, Literal
from uuid import UUID

class MetadataFilter(BaseModel):
    source_type: Optional[Literal["local", "notion", "google_drive"]] = None
    content_type: Optional[Literal["pdf", "docx", "xlsx"]] = None
    document_id: Optional[UUID] = None

class ChunkCitation(BaseModel):
    document_id: str
    document_title: str
    source_type: str
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    heading_context: Optional[str] = None
    section_context: Optional[str] = None

class RetrievedChunk(BaseModel):
    chunk_id: str
    chunk_index: int
    chunk_type: Optional[str] = None
    content: str
    score: float
    citation: ChunkCitation

class SearchKnowledgeResult(BaseModel):
    query: str
    total_candidates: int
    returned_chunks: int
    reranked: bool
    chunks: List[RetrievedChunk]
