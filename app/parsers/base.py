from abc import ABC, abstractmethod
from app.schemas.source_item import SourceItem
from app.schemas.extracted_document import ExtractedDocument

class BaseParser(ABC):
    @abstractmethod
    def parse(self, source_item: SourceItem) -> ExtractedDocument:
        """Parse the source file and return an ExtractedDocument."""
        pass
    
    @abstractmethod
    def supports(self, content_type: str) -> bool:
        """Return True if this parser supports the given content type."""
        pass
