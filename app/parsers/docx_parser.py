import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from app.parsers.base import BaseParser
from app.schemas.source_item import SourceItem
from app.schemas.extracted_document import ExtractedDocument, DocumentMetadata
from app.schemas.document_elements import (
    ParagraphElement,
    HeadingElement,
    ListItemElement,
    TableElement
)

def iter_block_items(parent):
    """
    Yield each paragraph and table child within *parent*, in document order.
    *parent* would generally be a docx.document.Document object.
    """
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Unsupported parent type")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

class DOCXParser(BaseParser):
    def supports(self, content_type: str) -> bool:
        return content_type == "docx"

    def parse(self, source_item: SourceItem) -> ExtractedDocument:
        doc = docx.Document(source_item.raw_path)
        
        elements = []
        raw_text_parts = []
        section_path = []
        element_index = 0
        
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                
                style_name = block.style.name if block.style else "Normal"
                
                # Check for Headings
                if style_name.startswith("Heading"):
                    try:
                        level = int(style_name.replace("Heading", "").strip())
                    except ValueError:
                        level = 1
                        
                    # Update section path
                    section_path = section_path[:level - 1]
                    section_path.append(text)
                    
                    elements.append(
                        HeadingElement(
                            index=element_index,
                            section_path=list(section_path),
                            text=text,
                            level=level
                        )
                    )
                    raw_text_parts.append(text)
                    element_index += 1
                
                # Check for Lists
                elif "List" in style_name or block._p.pPr is not None and block._p.pPr.numPr is not None:
                    list_type = "bullet" if "Bullet" in style_name else "numbered"
                    
                    # Try to determine level from numPr or style name
                    level = 0
                    if block._p.pPr is not None and block._p.pPr.numPr is not None:
                        ilvl = block._p.pPr.numPr.ilvl
                        if ilvl is not None:
                            level = ilvl.val
                    elif " 2" in style_name: level = 1
                    elif " 3" in style_name: level = 2
                    elif " 4" in style_name: level = 3
                    
                    elements.append(
                        ListItemElement(
                            index=element_index,
                            section_path=list(section_path),
                            text=text,
                            list_type=list_type,
                            level=level
                        )
                    )
                    raw_text_parts.append(f"{'  ' * level}- {text}")
                    element_index += 1
                
                # Standard Paragraph
                else:
                    elements.append(
                        ParagraphElement(
                            index=element_index,
                            section_path=list(section_path),
                            text=text,
                            style=style_name
                        )
                    )
                    raw_text_parts.append(text)
                    element_index += 1
                    
            elif isinstance(block, Table):
                headers = []
                rows = []
                
                if len(block.rows) > 0:
                    # Treat first row as header
                    headers = [cell.text.strip() for cell in block.rows[0].cells]
                    
                    for row in block.rows[1:]:
                        row_data = [cell.text.strip() for cell in row.cells]
                        rows.append(row_data)
                        
                # Create markdown-like text representation
                table_text_parts = []
                if headers:
                    table_text_parts.append(" | ".join(headers))
                for row_data in rows:
                    table_text_parts.append(" | ".join(row_data))
                
                table_text = "\n".join(table_text_parts)
                
                elements.append(
                    TableElement(
                        index=element_index,
                        section_path=list(section_path),
                        headers=headers,
                        rows=rows,
                        text=table_text
                    )
                )
                raw_text_parts.append(table_text)
                element_index += 1

        core_props = doc.core_properties
        
        metadata = DocumentMetadata(
            title=core_props.title or "",
            author=core_props.author or "",
            created_at=core_props.created.isoformat() if core_props.created else "",
            modified_at=core_props.modified.isoformat() if core_props.modified else "",
            source_type=source_item.source_type,
            content_type=source_item.content_type,
            file_name=source_item.original_filename,
            file_path=str(source_item.raw_path)
        )
        
        return ExtractedDocument(
            source_item=source_item,
            raw_text="\n\n".join(raw_text_parts),
            metadata=metadata,
            elements=elements,
            parser_metadata={} # Kept for backward compatibility
        )
