import hashlib
import os
from datetime import datetime, timezone
from app.schemas.extracted_document import ExtractedDocument
from app.schemas.normalized_document import NormalizedDocument, TextSection
from app.normalizer.cleaner import ContentCleaner

class NormalizationService:
    def __init__(self):
        self.cleaner = ContentCleaner()

    def normalize(self, extracted: ExtractedDocument) -> NormalizedDocument:
        full_text = self.cleaner.clean(extracted.raw_text)
        
        # Compute hash
        content_hash = hashlib.sha256(full_text.encode('utf-8')).hexdigest()
        
        title = ""
        source_updated_at = None
        final_metadata = {}
        structured_sections = []
        
        # 1. Handle New Structured Metadata (e.g. DOCXParser)
        if extracted.metadata is not None:
            title = extracted.metadata.title
            
            if extracted.metadata.modified_at:
                try:
                    source_updated_at = datetime.fromisoformat(extracted.metadata.modified_at)
                    if source_updated_at.tzinfo is None:
                        source_updated_at = source_updated_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
                    
            final_metadata = extracted.metadata.model_dump()
            
            # Extract structured sections for chunkers
            if extracted.elements:
                for el in extracted.elements:
                    structured_sections.append(
                        TextSection(
                            section_type=el.type,
                            content=self.cleaner.clean(el.text) if hasattr(el, 'text') else "",
                            metadata=el.model_dump()
                        )
                    )
                
        # 2. Handle Old Legacy Metadata (e.g. PDFParser, XLSXParser)
        else:
            title = extracted.parser_metadata.get("title")
            
            if "modified" in extracted.parser_metadata and extracted.parser_metadata["modified"]:
                try:
                    source_updated_at = datetime.fromisoformat(extracted.parser_metadata["modified"])
                    if source_updated_at.tzinfo is None:
                        source_updated_at = source_updated_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
                    
            final_metadata = extracted.parser_metadata
            
        # Fallbacks
        if not title:
            title = extracted.source_item.original_filename
            
        if not source_updated_at:
            try:
                mtime = os.path.getmtime(extracted.source_item.raw_path)
                source_updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc)
            except (OSError, TypeError):
                # File may have been cleaned up (e.g. temp downloads) — fall back to now
                source_updated_at = datetime.now(timezone.utc)
            
        return NormalizedDocument(
            source_type=extracted.source_item.source_type,
            source_id=extracted.source_item.source_id,
            title=title,
            content_type=extracted.source_item.content_type,
            raw_text=extracted.raw_text,
            full_text=full_text,
            content_hash=content_hash,
            source_url=str(extracted.source_item.raw_path),
            source_updated_at=source_updated_at,
            metadata=final_metadata,
            structured_sections=structured_sections
        )
