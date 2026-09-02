from app.schemas.normalized_document import NormalizedDocument
from app.chunking.base import AbstractChunker
from app.chunking.docx_chunker import DOCXChunker
from app.chunking.pdf_chunker import PDFChunker
from app.chunking.xlsx_chunker import XLSXChunker

class UnsupportedContentTypeError(Exception):
    pass

class ChunkingRouter:
    def __init__(self):
        self.chunkers = {
            "docx": DOCXChunker(),
            "pdf": PDFChunker(),
            "xlsx": XLSXChunker()
        }

    def route(self, doc: NormalizedDocument) -> AbstractChunker:
        chunker = self.chunkers.get(doc.content_type)
        if not chunker:
            raise UnsupportedContentTypeError(f"No chunker found for content type: {doc.content_type}")
        return chunker
