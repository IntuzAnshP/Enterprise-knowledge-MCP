from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.schemas.source_item import SourceItem
from app.schemas.document_elements import DocumentElement

class DocumentMetadata(BaseModel):
    title: str = ""
    author: str = ""
    created_at: str = ""
    modified_at: str = ""
    source_type: str = ""
    content_type: str = ""
    file_name: str = ""
    file_path: str = ""

class ExtractedDocument(BaseModel):
    source_item: SourceItem
    raw_text: str
    parser_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # New structured fields for optimized parsing
    metadata: Optional[DocumentMetadata] = None
    elements: List[DocumentElement] = Field(default_factory=list)

