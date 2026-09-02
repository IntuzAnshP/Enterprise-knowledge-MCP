from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class SourceItem(BaseModel):
    source_type: str          # e.g., 'local'
    source_id: str            # file path or generated UUID
    content_type: str         # 'pdf', 'docx', 'xlsx'
    raw_path: Path            # absolute path to stored file
    original_filename: str
    file_size: int
    uploaded_at: datetime
    metadata: Dict[str, Any] = {}
