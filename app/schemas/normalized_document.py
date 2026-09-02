from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

class TextSection(BaseModel):
    section_type: str          # 'heading', 'paragraph', 'table', 'page', 'row'
    content: str               # raw section text
    metadata: Dict[str, Any]   # page_num, sheet_name, heading_level, etc.

class NormalizedDocument(BaseModel):
    source_type: str
    source_id: str
    title: str
    content_type: str
    raw_text: str             # uncleaned, parsed text
    full_text: str            # cleaned, combined text
    content_hash: str         # SHA256 of full text
    source_url: str
    source_updated_at: datetime
    metadata: Dict[str, Any]  # standardized metadata
    structured_sections: List[TextSection] = Field(default_factory=list)
