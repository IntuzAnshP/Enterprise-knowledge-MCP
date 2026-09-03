from pydantic import BaseModel, Field
from typing import List, Optional, Union, Annotated, Literal

class BaseElement(BaseModel):
    index: int
    section_path: List[str] = Field(default_factory=list)
    page_number: Optional[int] = None

class ParagraphElement(BaseElement):
    type: Literal["paragraph"] = "paragraph"
    text: str
    style: str
    heading_level: Optional[int] = None

class HeadingElement(BaseElement):
    type: Literal["heading"] = "heading"
    text: str
    level: int

class ListItemElement(BaseElement):
    type: Literal["list_item"] = "list_item"
    text: str
    list_type: str  # "bullet" or "numbered"
    level: int

class TableElement(BaseElement):
    type: Literal["table"] = "table"
    headers: List[str]
    rows: List[List[str]]
    text: str

DocumentElement = Annotated[
    Union[ParagraphElement, HeadingElement, ListItemElement, TableElement],
    Field(discriminator="type")
]
