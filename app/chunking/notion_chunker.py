"""
Notion Chunker — v2
--------------------
Purpose-built chunker for Notion documents with full hierarchy-aware chunking.

Design Principles
-----------------
1. **Hierarchy preservation**: tracks H1 → H2 → body and always prepends the
   full breadcrumb as a preamble to every chunk so the embedding model has
   complete context even without the surrounding chunks.

2. **No standalone heading chunks**: a heading-only buffer is never emitted.
   Headings only become part of a chunk when they have body content beneath
   them. If two headings appear back-to-back (e.g. H1 then immediately H2),
   the outer heading is merged into the preamble of the inner chunk.

3. **H1/H2 boundaries only**: only top-level (H1) and section-level (H2)
   headings create chunk splits. H3+ headings accumulate inside the current
   section along with paragraphs and lists.

4. **Token-aware overflow**: when an H1/H2 section grows beyond `chunk_size`
   tokens the buffer is split using a character sliding window with `chunk_overlap`
   overlap, and the breadcrumb preamble is re-prepended to every sub-chunk.

5. **Rich section_context metadata**: each chunk carries the full breadcrumb
   path (e.g. "PHASE 1 – Core AWS > ☁️ Services to Master") so downstream
   citation logic works without reading the chunk content.
"""

from typing import List, Optional, Tuple
from app.chunking.base import AbstractChunker
from app.schemas.normalized_document import NormalizedDocument, TextSection
from app.schemas.chunk import DocumentChunkSchema, ChunkMetadata


class NotionChunker(AbstractChunker):

    def chunk(self, doc: NormalizedDocument) -> List[DocumentChunkSchema]:
        chunks: List[DocumentChunkSchema] = []
        chunk_index = 0

        # Breadcrumb: (h1_text, h2_text)
        current_h1: Optional[str] = None
        current_h2: Optional[str] = None

        # Accumulated body lines under the current H1/H2
        body_lines: List[str] = []

        # ── helpers ──────────────────────────────────────────────────────────

        def _breadcrumb() -> str:
            """Full parent path for the current section."""
            parts = [p for p in [current_h1, current_h2] if p]
            return " > ".join(parts)

        def _preamble() -> str:
            """Prepended to every chunk so embeddings carry parent context."""
            bc = _breadcrumb()
            return f"[Context: {bc}]\n\n" if bc else ""

        def _emit_chunks(body: str, h1: Optional[str], h2: Optional[str]) -> None:
            nonlocal chunk_index

            if not body.strip():
                return

            # Reconstruct breadcrumb at emit time (h1/h2 passed explicitly to
            # avoid closure issues when the outer vars change before _flush fires)
            parts = [p for p in [h1, h2] if p]
            section_ctx = " > ".join(parts) if parts else None
            preamble = f"[Context: {section_ctx}]\n\n" if section_ctx else ""

            full_content = preamble + body

            max_chars = self.chunk_size * 4
            if len(full_content) <= max_chars:
                chunks.append(_make_chunk(full_content, chunk_index, section_ctx))
                chunk_index += 1
            else:
                # Sliding window — re-prepend preamble on every sub-chunk
                overlap_chars = self.chunk_overlap * 4
                start = 0
                while start < len(full_content):
                    end = start + max_chars
                    piece = full_content[start:end].strip()
                    if piece:
                        # Ensure the preamble is included in each window piece
                        if preamble and not piece.startswith("[Context:"):
                            piece = preamble + piece
                        chunks.append(_make_chunk(piece, chunk_index, section_ctx))
                        chunk_index += 1
                    start += max_chars - overlap_chars

        def _flush(h1: Optional[str], h2: Optional[str]) -> None:
            nonlocal body_lines
            if not body_lines:
                return
            body = "\n\n".join(body_lines).strip()
            body_lines = []
            _emit_chunks(body, h1, h2)

        def _make_chunk(content: str, idx: int, section: Optional[str]) -> DocumentChunkSchema:
            return DocumentChunkSchema(
                content=content,
                metadata=ChunkMetadata(
                    document_id=doc.source_id,
                    chunk_index=idx,
                    chunk_type="section",
                    source_type=doc.source_type,
                    source_url=doc.source_url,
                    title=doc.title,
                    section_context=section,
                ),
            )

        # ── main pass ─────────────────────────────────────────────────────────

        for section in doc.structured_sections:
            text = section.content.strip()
            if not text:
                continue

            stype = section.section_type
            level = section.metadata.get("level") if stype == "heading" else None

            if stype == "heading" and level == 1:
                # New H1: flush whatever was in the previous H1/H2 bucket
                _flush(current_h1, current_h2)
                current_h1 = text
                current_h2 = None
                # Don't add heading to body yet — wait to see if body follows
                # (avoids standalone heading chunks)

            elif stype == "heading" and level == 2:
                # New H2 within same H1: flush previous H2 bucket ONLY if one exists
                if current_h2 is not None:
                    _flush(current_h1, current_h2)
                current_h2 = text
                # Same: don't emit the heading alone

            else:
                # Body content (H3+, paragraphs, lists, table rows, child pages)
                # If we have H3+ headings, include them as inline text in body
                if stype == "heading" and level is not None and level >= 3:
                    body_lines.append(text)
                else:
                    body_lines.append(text)

        # Final flush
        _flush(current_h1, current_h2)

        return chunks
