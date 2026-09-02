import fitz  # PyMuPDF
import re
from collections import Counter
from app.parsers.base import BaseParser
from app.schemas.source_item import SourceItem
from app.schemas.extracted_document import ExtractedDocument, DocumentMetadata
from app.schemas.document_elements import HeadingElement, ParagraphElement

class PDFParser(BaseParser):
    def supports(self, content_type: str) -> bool:
        return content_type == "pdf"

    def parse(self, source_item: SourceItem) -> ExtractedDocument:
        doc = fitz.open(source_item.raw_path)
        
        full_text_blocks = []
        elements = []
        element_index = 0
        current_section_path = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Use "dict" to get span-level font sizes
            page_dict = page.get_text("dict")
            blocks = page_dict.get("blocks", [])
            
            # Find the most common font size on this page to serve as "body" font size
            font_sizes = []
            for b in blocks:
                if b.get("type") == 0:  # text block
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                font_sizes.append(round(span.get("size", 10.0), 1))
                                
            if font_sizes:
                most_common_size = Counter(font_sizes).most_common(1)[0][0]
            else:
                most_common_size = 11.0 # fallback
                
            for b in blocks:
                if b.get("type") != 0: # skip image blocks
                    continue
                    
                block_text = ""
                max_font_size = 0.0
                
                # Re-flow logic: join lines that probably shouldn't be broken
                lines_text = []
                for line in b.get("lines", []):
                    line_str = ""
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        line_str += span_text
                        size = span.get("size", 10.0)
                        if size > max_font_size and span_text.strip():
                            max_font_size = size
                            
                    lines_text.append(line_str.strip())
                    
                if not lines_text:
                    continue
                    
                # Re-flow paragraph: join lines softly
                reflowed_lines = []
                for i, line in enumerate(lines_text):
                    if not line:
                        continue
                    # If line doesn't end with punctuation, assume soft wrap
                    if i < len(lines_text) - 1 and not line[-1] in ".!?:,;-":
                        reflowed_lines.append(line + " ")
                    else:
                        reflowed_lines.append(line + "\n")
                        
                block_text = "".join(reflowed_lines).strip()
                
                if not block_text:
                    continue
                
                full_text_blocks.append(block_text)
                
                is_heading = False
                heading_level = 1
                
                # It's a heading if the max font size in the block is significantly larger than body text
                if max_font_size >= most_common_size + 1.5:
                    is_heading = True
                    # Estimate level based on size difference
                    size_diff = max_font_size - most_common_size
                    if size_diff > 8:
                        heading_level = 1
                    elif size_diff > 4:
                        heading_level = 2
                    else:
                        heading_level = 3
                        
                # Alternative heading detection for same-size font (like "1. Introduction")
                elif len(block_text) < 100:
                    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
                    first_line = lines[0] if lines else ""
                    # Strict regex
                    strict_heading_regex = re.compile(
                        r'^(?:(?:\d+\.){1,4}\s+[A-Z][a-zA-Z0-9\s]*|Chapter\s+\d+|SECTION\s+\d+)$'
                    )
                    if strict_heading_regex.match(first_line):
                        is_heading = True
                        dot_count = first_line.split()[0].count('.') if first_line else 0
                        heading_level = min(dot_count + 1, 4) if dot_count > 0 else 1

                if is_heading:
                    # Update hierarchy
                    first_line = block_text.split("\n")[0][:100]
                    if heading_level <= len(current_section_path):
                        current_section_path = current_section_path[:heading_level - 1]
                    current_section_path.append(first_line)
                    
                    elements.append(HeadingElement(
                        index=element_index,
                        text=block_text,
                        level=heading_level,
                        section_path=list(current_section_path)
                    ))
                else:
                    elements.append(ParagraphElement(
                        index=element_index,
                        text=block_text,
                        style="Normal",
                        heading_level=None,
                        section_path=list(current_section_path)
                    ))
                
                element_index += 1

        doc_metadata = DocumentMetadata(
            title=doc.metadata.get("title") or source_item.original_filename,
            author=doc.metadata.get("author"),
            created_at=doc.metadata.get("creationDate"),
            modified_at=doc.metadata.get("modDate"),
            source_type=source_item.source_type,
            content_type=source_item.content_type,
            file_name=source_item.original_filename,
            file_path=str(source_item.raw_path)
        )
        
        return ExtractedDocument(
            source_item=source_item,
            raw_text="\n\n".join(full_text_blocks),
            metadata=doc_metadata,
            elements=elements,
            parser_metadata={"page_count": len(doc)}
        )
