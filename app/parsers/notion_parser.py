import json
from app.parsers.base import BaseParser
from app.schemas.source_item import SourceItem
from app.schemas.extracted_document import ExtractedDocument, DocumentMetadata
from app.schemas.document_elements import HeadingElement, ParagraphElement, ListItemElement

class NotionParser(BaseParser):
    def supports(self, content_type: str) -> bool:
        return content_type == "notion"

    def _extract_rich_text(self, rich_text_array: list) -> str:
        if not rich_text_array:
            return ""
        return "".join(item.get("plain_text", "") for item in rich_text_array)

    def parse(self, source_item: SourceItem) -> ExtractedDocument:
        with open(source_item.raw_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata_obj = data.get("metadata", {})
        blocks = data.get("blocks", [])

        title = source_item.original_filename.replace(".json", "")
        if "properties" in metadata_obj:
            for prop_val in metadata_obj["properties"].values():
                if isinstance(prop_val, dict) and prop_val.get("type") == "title":
                    title_arr = prop_val.get("title", [])
                    if title_arr:
                        title = self._extract_rich_text(title_arr)
                    break

        created_time = metadata_obj.get("created_time")
        last_edited_time = metadata_obj.get("last_edited_time")

        doc_metadata = DocumentMetadata(
            title=title or "",
            author="",
            created_at=str(created_time) if created_time else "",
            modified_at=str(last_edited_time) if last_edited_time else "",
            source_type=source_item.source_type or "",
            content_type=source_item.content_type or "",
            file_name=source_item.original_filename or "",
            file_path=str(source_item.raw_path) or ""
        )

        elements = []
        full_text_blocks = []
        current_section_path = []
        element_index = 0

        def _process_blocks(blocks_list, section_path):
            nonlocal element_index, current_section_path
            
            for block in blocks_list:
                b_type = block.get("type")
                if not b_type:
                    continue

                b_data = block.get(b_type, {})
                text_content = ""
                
                if b_type == "table_row":
                    cells = b_data.get("cells", [])
                    row_text = []
                    for cell in cells:
                        row_text.append(self._extract_rich_text(cell).strip())
                    text_content = " | ".join(row_text)
                elif b_type == "child_page":
                    text_content = f"[Child Page]: {b_data.get('title', 'Untitled')}"
                elif b_type == "child_database":
                    text_content = f"[Child Database]: {b_data.get('title', 'Untitled')}"
                else:
                    rich_text = b_data.get("rich_text", [])
                    text_content = self._extract_rich_text(rich_text).strip()
                
                if text_content:
                    full_text_blocks.append(text_content)

                    if b_type.startswith("heading_") or b_type in ["child_page", "child_database"]:
                        if b_type.startswith("heading_"):
                            level_str = b_type.replace("heading_", "")
                            level = int(level_str) if level_str.isdigit() else 1
                        else:
                            # Treat embedded pages/databases as top-level headings to isolate their context
                            level = 1
                        
                        section_path = section_path[:level - 1]
                        section_path.append(text_content)
                        current_section_path = section_path

                        elements.append(HeadingElement(
                            index=element_index,
                            text=text_content,
                            level=level,
                            section_path=list(section_path),
                            page_number=1
                        ))
                    elif b_type in ["bulleted_list_item", "numbered_list_item"]:
                        list_type = "bullet" if b_type == "bulleted_list_item" else "numbered"
                        elements.append(ListItemElement(
                            index=element_index,
                            text=text_content,
                            list_type=list_type,
                            level=1,
                            section_path=list(section_path),
                            page_number=1
                        ))
                    else:
                        elements.append(ParagraphElement(
                            index=element_index,
                            text=text_content,
                            style="Normal",
                            heading_level=None,
                            section_path=list(section_path),
                            page_number=1
                        ))

                    element_index += 1
                    
                # Recursively process children
                children = block.get("children", [])
                if children:
                    _process_blocks(children, section_path)

        _process_blocks(blocks, current_section_path)

        return ExtractedDocument(
            source_item=source_item,
            raw_text="\n\n".join(full_text_blocks),
            metadata=doc_metadata,
            elements=elements,
            parser_metadata={"block_count": len(blocks)}
        )
