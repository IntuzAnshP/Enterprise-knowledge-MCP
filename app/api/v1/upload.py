from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.connectors.local.upload_service import UploadService
from app.ingestion.pipeline import IngestionPipeline
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.models.document_chunk import DocumentChunk
from app.models.document import Document
from app.schemas.api_response import APIResponse

router = APIRouter()
pipeline = IngestionPipeline()
upload_service = UploadService()

class DocumentResponse(BaseModel):
    id: str
    title: str
    source_type: str
    content_type: str
    source_url: str
    metadata: Dict[str, Any]
    indexing_status: str
    created_at: datetime
    updated_at: datetime

class ChunkResponse(BaseModel):
    chunk_index: int
    chunk_type: Optional[str]
    content: str
    metadata: Dict[str, Any]

@router.post("/upload", response_model=APIResponse[DocumentResponse])
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # 1. Save file locally
        source_item = await upload_service.save_upload_file(file)
        
        # 2. Run ingestion pipeline
        db_doc = pipeline.run(source_item, db)
        
        # 3. Get chunk count
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == db_doc.id).count()
        
        return APIResponse(
            message=f"successfully completed ingestion created {chunk_count} chunks and stored in vector db.",
            data=DocumentResponse(
                id=str(db_doc.id),
                title=db_doc.title,
                source_type=db_doc.source_type,
                content_type=db_doc.content_type,
                source_url=db_doc.source_url,
                metadata=db_doc.metadata_ or {},
                indexing_status=db_doc.indexing_status.value,
                created_at=db_doc.created_at,
                updated_at=db_doc.updated_at
            )
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/{document_id}/chunks", response_model=APIResponse[List[ChunkResponse]])
def get_document_chunks(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).all()
    
    return APIResponse(
        message="Successfully retrieved document chunks",
        data=[
            ChunkResponse(
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                metadata=chunk.metadata_ or {}
            ) for chunk in chunks
        ]
    )

from enum import Enum

class SourceTypeEnum(str, Enum):
    local = "local"
    google_drive = "google_drive"
    notion = "notion"

class ContentTypeEnum(str, Enum):
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"

class SortByEnum(str, Enum):
    created_at = "created_at"
    title = "title"

class OrderEnum(str, Enum):
    asc = "asc"
    desc = "desc"

@router.get("/documents", response_model=APIResponse[List[Dict[str, Any]]])
def list_documents(
    search: Optional[str] = None,
    source_type: Optional[SourceTypeEnum] = None,
    content_type: Optional[ContentTypeEnum] = None,
    sort_by: SortByEnum = Query(SortByEnum.created_at, description="Field to sort by"),
    order: OrderEnum = Query(OrderEnum.desc, description="Sort order"),
    db: Session = Depends(get_db)
):
    query = db.query(Document)
    
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))
        
    if source_type:
        query = query.filter(Document.source_type == source_type.value)
        
    if content_type:
        query = query.filter(Document.content_type == content_type.value)
        
    if sort_by == SortByEnum.title:
        order_col = Document.title
    else:
        order_col = Document.created_at
        
    if order == OrderEnum.asc:
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
        
    docs = query.all()
    
    return APIResponse(
        message="Successfully retrieved document list",
        data=[{
            "id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
            "content_type": doc.content_type,
            "indexing_status": doc.indexing_status.value if doc.indexing_status else "pending",
            "created_at": doc.created_at
        } for doc in docs]
    )

@router.get("/documents/{document_id}", response_model=APIResponse[Dict[str, Any]])
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return APIResponse(
        message="Successfully retrieved document",
        data={
            "id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
            "content_type": doc.content_type,
            "source_url": doc.source_url,
            "metadata": doc.metadata_,
            "indexing_status": doc.indexing_status.value if doc.indexing_status else "pending",
            "created_at": doc.created_at,
            "updated_at": doc.updated_at
        }
    )

class TextResponse(BaseModel):
    document_id: str
    text: str

@router.get("/documents/{document_id}/parsed-text", response_model=APIResponse[TextResponse])
def get_parsed_text(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return APIResponse(
        message="Successfully retrieved parsed text",
        data=TextResponse(
            document_id=str(doc.id),
            text=doc.raw_text or ""
        )
    )

@router.get("/documents/{document_id}/normalized-text", response_model=APIResponse[TextResponse])
def get_normalized_text(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return APIResponse(
        message="Successfully retrieved normalized text",
        data=TextResponse(
            document_id=str(doc.id),
            text=doc.full_text or ""
        )
    )

import os
import shutil
from pathlib import Path

@router.delete("/documents/{document_id}", response_model=APIResponse[None])
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # 1. Delete physical file and its parent UUID folder if it exists
    if doc.source_url and doc.source_type == "local":
        file_path = Path(doc.source_url)
        if file_path.exists():
            parent_dir = file_path.parent
            # Only delete the parent dir if it's inside the uploads directory to be safe
            if parent_dir.parent.name == "uploads":
                shutil.rmtree(parent_dir, ignore_errors=True)
            else:
                os.remove(file_path)
                
    # 2. Delete DB record (Cascade delete will automatically wipe all chunks in document_chunks table)
    db.delete(doc)
    db.commit()
    
    return APIResponse(status="success", message=f"Document {document_id} and all its chunks have been permanently deleted.")
