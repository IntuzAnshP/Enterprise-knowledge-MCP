from typing import List
from sqlalchemy.orm import Session
from app.models.document_chunk import DocumentChunk
from app.schemas.chunk import DocumentChunkSchema
from app.models.document import Document

class VectorStorageService:
    def store_chunks(self, document_id: str, chunks: List[DocumentChunkSchema], db: Session) -> None:
        """Insert new chunks with their embeddings."""
        db_chunks = []
        for chunk in chunks:
            db_chunks.append(DocumentChunk(
                document_id=document_id,
                chunk_index=chunk.metadata.chunk_index,
                chunk_type=chunk.metadata.chunk_type,
                content=chunk.content,
                metadata_=chunk.metadata.model_dump(),
                embedding=chunk.embedding
            ))
            
        db.add_all(db_chunks)
        db.commit()

    def delete_chunks(self, document_id: str, db: Session) -> None:
        """Delete all chunks for a document."""
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.commit()

    def chunk_count(self, document_id: str, db: Session) -> int:
        """Returns number of stored chunks for a document."""
        return db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
