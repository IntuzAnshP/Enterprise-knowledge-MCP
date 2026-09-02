import magic
from typing import Optional
from app.schemas.source_item import SourceItem
from app.parsers.base import BaseParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.xlsx_parser import XLSXParser

class UnsupportedContentTypeError(Exception):
    pass

class ParserRouter:
    def __init__(self):
        self.parsers = [
            PDFParser(),
            DOCXParser(),
            XLSXParser()
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
        
        return "unknown"

    def get_parser(self, content_type: str) -> BaseParser:
        for parser in self.parsers:
            if parser.supports(content_type):
                return parser
        raise UnsupportedContentTypeError(f"No parser found for content type: {content_type}")

    def route(self, source_item: SourceItem) -> BaseParser:
        return self.get_parser(source_item.content_type)
