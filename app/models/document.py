import uuid
import enum
from sqlalchemy import Column, String, DateTime, func, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import Enum as SAEnum
from app.database import Base

class IndexingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_type = Column(String, index=True, nullable=False) # 'local', 'notion', 'google_drive'
    source_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    content_type = Column(String, nullable=False) # 'pdf', 'docx', 'xlsx'
    content_hash = Column(String, nullable=False) # SHA256 of raw file
    source_url = Column(String, nullable=True) # file path or external URL
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True, default={}) # author, size, page_count, etc.
    indexing_status = Column(SAEnum(IndexingStatus), default=IndexingStatus.PENDING, nullable=False, index=True)
    raw_text = Column(Text, nullable=True)  # uncleaned parsed text
    full_text = Column(Text, nullable=True) # cleaned text for chunking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
