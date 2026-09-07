import magic
from typing import Optional
from app.schemas.source_item import SourceItem
from app.parsers.base import BaseParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.xlsx_parser import XLSXParser
from app.parsers.notion_parser import NotionParser

class UnsupportedContentTypeError(Exception):
    pass

class ParserRouter:
    def __init__(self):
        self.parsers = [
            PDFParser(),
            DOCXParser(),
            XLSXParser(),
            NotionParser()
        ]
        
    def detect_content_type(self, file_path: str) -> str:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        
        if mime_type == "application/pdf":
            return "pdf"
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return "docx"
        elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            return "xlsx"
        elif file_path.endswith(".json"):
            # Temporary heuristic for Notion parser since we save it as json.
            # In a real app we might inspect the json content.
            return "notion"
        
        return "unknown"

    def get_parser(self, content_type: str) -> BaseParser:
        for parser in self.parsers:
            if parser.supports(content_type):
                return parser
        raise UnsupportedContentTypeError(f"No parser found for content type: {content_type}")

    def route(self, source_item: SourceItem) -> BaseParser:
        return self.get_parser(source_item.content_type)
