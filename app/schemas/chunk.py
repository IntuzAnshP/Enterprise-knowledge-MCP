from pydantic import BaseModel, Field
from typing import Optional, List

class ChunkMetadata(BaseModel):
    document_id: str
    chunk_index: int
    chunk_type: str             # 'paragraph', 'heading', 'table', 'row', etc.
    source_type: str
    source_url: str
    title: str
    
    # Citation fields
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    heading_context: Optional[str] = None
    section_context: Optional[str] = None

class DocumentChunkSchema(BaseModel):
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None
