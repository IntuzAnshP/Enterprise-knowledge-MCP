from sqlalchemy.orm import Session
from app.schemas.source_item import SourceItem
from app.parsers.router import ParserRouter
from app.normalizer.normalizer import NormalizationService
from app.models.document import Document, IndexingStatus
from app.ingestion.change_detection import ChangeDetectionService, ChangeResult
from app.chunking.router import ChunkingRouter
from app.embedding.embedding_service import EmbeddingService
from app.vector_store.vector_storage_service import VectorStorageService
import logging

logger = logging.getLogger(__name__)

class IngestionPipeline:
    def __init__(self):
        self.parser_router = ParserRouter()
        self.normalizer = NormalizationService()
        self.change_detector = ChangeDetectionService()
        self.chunking_router = ChunkingRouter()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStorageService()

    def run(self, source_item: SourceItem, db: Session) -> Document:
        # 1. Parse
        parser = self.parser_router.route(source_item)
        extracted_doc = parser.parse(source_item)
        
        # 2. Normalize
        normalized_doc = self.normalizer.normalize(extracted_doc)
        
        # 3. Change Detection
        change_status = self.change_detector.detect(normalized_doc.source_id, normalized_doc.content_hash, db)
        
        if change_status == ChangeResult.UNCHANGED:
            logger.info(f"Document {normalized_doc.source_id} unchanged. Skipping.")
            return db.query(Document).filter(Document.source_id == normalized_doc.source_id).first()
            
        if change_status == ChangeResult.UPDATED:
            logger.info(f"Document {normalized_doc.source_id} updated. Deleting old chunks.")
            db_doc = db.query(Document).filter(Document.source_id == normalized_doc.source_id).first()
            self.vector_store.delete_chunks(db_doc.id, db)
            
            # Update existing document metadata
            db_doc.title = normalized_doc.title
            db_doc.content_hash = normalized_doc.content_hash
            db_doc.source_updated_at = normalized_doc.source_updated_at
            db_doc.metadata_ = normalized_doc.metadata
            db_doc.raw_text = normalized_doc.raw_text
            db_doc.full_text = normalized_doc.full_text
            db_doc.indexing_status = IndexingStatus.PROCESSING
            db.commit()
            
        else: # NEW
            logger.info(f"Document {normalized_doc.source_id} is new. Creating record.")
            db_doc = Document(
                source_type=normalized_doc.source_type,
                source_id=normalized_doc.source_id,
                title=normalized_doc.title,
                content_type=normalized_doc.content_type,
                content_hash=normalized_doc.content_hash,
                source_url=normalized_doc.source_url,
                source_updated_at=normalized_doc.source_updated_at,
                metadata_=normalized_doc.metadata,
                raw_text=normalized_doc.raw_text,
                full_text=normalized_doc.full_text,
                indexing_status=IndexingStatus.PROCESSING
            )
            db.add(db_doc)
            db.commit()
            db.refresh(db_doc)
            
        # 4. Chunking
        logger.info(f"Chunking document {db_doc.id}")
        try:
            chunker = self.chunking_router.route(normalized_doc)
            chunks = chunker.chunk(normalized_doc)
            
            # 5. Embedding
            logger.info(f"Embedding {len(chunks)} chunks")
            texts_to_embed = [chunk.content for chunk in chunks]
            embeddings = self.embedding_service.embed_batch(texts_to_embed)
            
            for i, chunk in enumerate(chunks):
                chunk.embedding = embeddings[i]
                
            # 6. Store Chunks
            logger.info("Storing chunks in vector database")
            self.vector_store.store_chunks(db_doc.id, chunks, db)
            
            db_doc.indexing_status = IndexingStatus.COMPLETED
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to process document {db_doc.id}: {str(e)}")
            db_doc.indexing_status = IndexingStatus.FAILED
            db.commit()
            raise e
            
        return db_doc
