import os
from pathlib import Path
from datetime import datetime, timezone
import pytest

from app.parsers.docx_parser import DOCXParser
from app.schemas.source_item import SourceItem
from app.schemas.document_elements import (
    ParagraphElement,
    HeadingElement,
    ListItemElement,
    TableElement
)

def test_docx_parser_with_sample_file():
    # Setup test file path
    sample_file = Path("./uploads/ebd17984-3a36-4d30-9cca-2211e81d82b6/sample-files.com-large-document.docx")
    
    # Skip if file doesn't exist to avoid CI failures if test file isn't present
    if not sample_file.exists():
        pytest.skip(f"Sample file not found at {sample_file}")

    # Create SourceItem
    source_item = SourceItem(
        source_type="local",
        source_id="test_docx_id",
        content_type="docx",
        raw_path=sample_file.absolute(),
        original_filename=sample_file.name,
        file_size=sample_file.stat().st_size,
        uploaded_at=datetime.now(timezone.utc)
    )

    # Initialize parser
    parser = DOCXParser()
    assert parser.supports("docx") is True

    # Parse document
    extracted = parser.parse(source_item)

    # Validate high-level metadata
    assert extracted.source_item.source_id == "test_docx_id"
    assert extracted.metadata is not None
    assert extracted.metadata.content_type == "docx"
    assert extracted.metadata.file_name == sample_file.name

    # Validate elements
    assert len(extracted.elements) > 0

    element_types = set(type(el) for el in extracted.elements)
    
    # Basic assertions on the structure of the elements
    # Since we don't know the exact contents, we'll verify the schemas are valid
    for i, el in enumerate(extracted.elements):
        assert el.index == i
        assert isinstance(el.section_path, list)
        
        if isinstance(el, ParagraphElement):
            assert el.type == "paragraph"
            assert isinstance(el.text, str)
            assert isinstance(el.style, str)
        elif isinstance(el, HeadingElement):
            assert el.type == "heading"
            assert isinstance(el.text, str)
            assert el.level > 0
            # By definition, the section path should end with this heading's text, 
            # or the parent heading's text if this is a higher level (handled implicitly by logic)
            if len(el.section_path) > 0:
                assert el.section_path[-1] == el.text
        elif isinstance(el, ListItemElement):
            assert el.type == "list_item"
            assert isinstance(el.text, str)
            assert el.list_type in ["bullet", "numbered"]
        elif isinstance(el, TableElement):
            assert el.type == "table"
            assert isinstance(el.headers, list)
            assert isinstance(el.rows, list)
            assert isinstance(el.text, str)

    # We expect some paragraphs at a minimum, and ideally a heading or a table
    # Since it's a "large-document", it should contain paragraphs.
    assert ParagraphElement in element_types, "Expected at least one paragraph"
    
    # Print a small summary for the test output
    print(f"\nSuccessfully parsed {len(extracted.elements)} elements.")
    for el_type in element_types:
        count = len([e for e in extracted.elements if isinstance(e, el_type)])
        print(f"- {el_type.__name__}: {count}")
    
    # Validate raw text is compiled correctly
    assert len(extracted.raw_text) > 0
    assert "\n\n" in extracted.raw_text
