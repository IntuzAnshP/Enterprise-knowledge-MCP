from typing import List
from app.chunking.base import AbstractChunker
from app.schemas.normalized_document import NormalizedDocument
from app.schemas.chunk import DocumentChunkSchema, ChunkMetadata

class PDFChunker(AbstractChunker):
    def chunk(self, doc: NormalizedDocument) -> List[DocumentChunkSchema]:
        # If we have structured sections (from PDF parser with detected headings/paragraphs)
        if doc.structured_sections:
            return self._chunk_structured(doc)
        
        # Fallback to standard token/character-based chunking
        return self._chunk_fallback(doc)

    def _chunk_structured(self, doc: NormalizedDocument) -> List[DocumentChunkSchema]:
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
            current_chunk_content = []
            current_token_count = 0

        for section in doc.structured_sections:
            text = section.content
            if not text:
                continue

            tokens = self._approx_token_count(text)

            # Heading boundary -> flush current chunk to keep sections clean
            if section.section_type == "heading":
                finalize_chunk()

                if "section_path" in section.metadata and section.metadata["section_path"]:
                    current_section_context = " > ".join(section.metadata["section_path"])
                else:
                    current_section_context = text

                current_chunk_content.append(text)
                current_token_count += tokens
                continue

            # Limit exceeded -> flush
            if current_token_count + tokens > self.chunk_size:
                finalize_chunk(chunk_type=section.section_type)

            current_chunk_content.append(text)
            current_token_count += tokens

            if current_token_count >= self.chunk_size:
                finalize_chunk(chunk_type=section.section_type)

        finalize_chunk()
        return chunks

    def _chunk_fallback(self, doc: NormalizedDocument) -> List[DocumentChunkSchema]:
        """Standard token/character sliding window chunking fallback."""
        chunks = []
        text = doc.full_text

        char_size = self.chunk_size * 4
        char_overlap = self.chunk_overlap * 4

        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + char_size
            chunk_content = text[start:end]

            metadata = ChunkMetadata(
                document_id=doc.source_id,
                chunk_index=chunk_index,
                chunk_type="text",
                source_type=doc.source_type,
                source_url=doc.source_url,
                title=doc.title
            )

            chunks.append(DocumentChunkSchema(
                content=chunk_content.strip(),
                metadata=metadata
            ))

            start += (char_size - char_overlap)
            chunk_index += 1

        return chunks
