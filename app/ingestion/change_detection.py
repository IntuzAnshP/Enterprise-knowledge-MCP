from enum import Enum
from sqlalchemy.orm import Session
from app.models.document import Document

class ChangeResult(Enum):
    NEW = "new"
    UNCHANGED = "unchanged"
    UPDATED = "updated"

class ChangeDetectionService:
    def detect(self, source_id: str, new_hash: str, db: Session) -> ChangeResult:
        existing = db.query(Document).filter(Document.source_id == source_id).first()
        
        if not existing:
            return ChangeResult.NEW
            
        if existing.content_hash == new_hash:
            return ChangeResult.UNCHANGED
            
        return ChangeResult.UPDATED
