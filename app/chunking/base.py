from abc import ABC, abstractmethod
from typing import List
from app.schemas.normalized_document import NormalizedDocument
from app.schemas.chunk import DocumentChunkSchema

class AbstractChunker(ABC):
    # Recommended settings for BAAI/bge-base-en-v1.5
    chunk_size: int = 425
    chunk_overlap: int = 60

    @abstractmethod
    def chunk(self, doc: NormalizedDocument) -> List[DocumentChunkSchema]:
        """
        Takes a NormalizedDocument and returns a list of DocumentChunks.
        Must respect structured_sections if present, else fallback to full_text.
        """
        pass

    def _approx_token_count(self, text: str) -> int:
        """
        Simple heuristic: ~4 characters per token for English text.
        For production, use a real tokenizer (e.g. transformers AutoTokenizer).
        """
        return len(text) // 4
