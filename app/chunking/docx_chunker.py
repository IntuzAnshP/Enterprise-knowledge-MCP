from typing import List
from app.chunking.base import AbstractChunker
from app.schemas.normalized_document import NormalizedDocument, TextSection
from app.schemas.chunk import DocumentChunkSchema, ChunkMetadata

class DOCXChunker(AbstractChunker):
    def chunk(self, doc: NormalizedDocument) -> List[DocumentChunkSchema]:
        chunks = []
        
        current_chunk_content = []
        current_token_count = 0
        current_section_context = None
        
        chunk_index = 0
        
        def finalize_chunk(chunk_type="paragraph"):
            nonlocal current_chunk_content, current_token_count, chunk_index
            if not current_chunk_content:
                return
            
            content_str = "\n\n".join(current_chunk_content)
            
            metadata = ChunkMetadata(
                document_id=doc.source_id,
                chunk_index=chunk_index,
                chunk_type=chunk_type,
                source_type=doc.source_type,
                source_url=doc.source_url,
                title=doc.title,
                section_context=current_section_context
            )
            
            chunks.append(DocumentChunkSchema(
                content=content_str,
                metadata=metadata
            ))
            
            chunk_index += 1
            # Simple overlap handling could go here, but for structure-aware 
            # DOCX chunking, we often prefer clean boundaries over overlaps.
            current_chunk_content = []
            current_token_count = 0

        for section in doc.structured_sections:
            text = section.content
            if not text:
                continue
                
            tokens = self._approx_token_count(text)
            
            # If we hit a heading, ALWAYS split the chunk to preserve context boundaries
            if section.section_type == "heading":
                finalize_chunk()
                
                # Update section context from the heading's section_path
                if "section_path" in section.metadata and section.metadata["section_path"]:
                    current_section_context = " > ".join(section.metadata["section_path"])
                else:
                    current_section_context = text
                    
                current_chunk_content.append(text)
                current_token_count += tokens
                continue
                
            # If the current section itself is huge (e.g. a massive table), we might need to flush first
            if current_token_count + tokens > self.chunk_size:
                finalize_chunk(chunk_type=section.section_type)
                
            current_chunk_content.append(text)
            current_token_count += tokens
            
            # Flush if we exceed the chunk size
            if current_token_count >= self.chunk_size:
                finalize_chunk(chunk_type=section.section_type)
                
        # Flush remaining
        finalize_chunk()
        
        return chunks
