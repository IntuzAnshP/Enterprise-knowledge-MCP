import uuid
from sqlalchemy import Column, String, DateTime, func, JSON, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.database import Base
from sqlalchemy.orm import relationship, backref

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True, default={})
    chunk_type = Column(String, nullable=True) # 'paragraph', 'heading', 'table', 'row'
    embedding = Column(Vector(768), nullable=True) # Populated in Phase 2
    citation_metadata = Column(JSON, nullable=True, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    document = relationship("Document", backref=backref("chunks", cascade="all, delete", passive_deletes=True))
