import asyncio
import json
import logging
from typing import Optional, Any
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from app.database import SessionLocal
from app.retrieval.retrieval_service import RetrievalService
from app.schemas.retrieval import MetadataFilter
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.config import settings

# Base directory for the MCP Server
BASE_DIR = Path(__file__).resolve().parent

# Configure logging to go to a file in the project directory, since stdout/stderr are used by MCP stdio
logging.basicConfig(
    filename=str(BASE_DIR / 'mcp_server.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server")

mcp = MCPServer("enterprise-knowledge")
retrieval_service = RetrievalService()

@mcp.tool()
def search_knowledge(
    query: str,
    source_type: Optional[str] = None,
    content_type: Optional[str] = None,
    document_id: Optional[str] = None,
    limit: int = settings.RETRIEVAL_FINAL_K
) -> str:
    """
    Search the enterprise knowledge base for information using semantic search.
    
    Args:
        query: The natural language query to search for.
        source_type: Optional filter by source type (local, notion, google_drive).
        content_type: Optional filter by content type (pdf, docx, xlsx).
        document_id: Optional filter by specific document ID.
        limit: Maximum number of chunks to return.
    """
    logger.info(f"Tool called: search_knowledge with query: {query}")
    db = SessionLocal()
    try:
        filters = MetadataFilter(
            source_type=source_type,
            content_type=content_type,
            document_id=document_id
        )
        
        result = retrieval_service.search(query=query, filters=filters, limit=limit, db=db)
        return result.model_dump_json()
    except Exception as e:
        logger.error(f"Error in search_knowledge: {e}", exc_info=True)
        return f"Error: {str(e)}"
    finally:
        db.close()

from typing import Optional, Any, Literal

@mcp.tool()
def list_documents(
    search: Optional[str] = None,
    source_type: Optional[Literal["local", "google_drive", "notion"]] = None,
    content_type: Optional[Literal["pdf", "docx", "xlsx"]] = None,
    sort_by: Literal["created_at", "title"] = "created_at",
    order: Literal["asc", "desc"] = "desc"
) -> str:
    """
    List all documents in the enterprise knowledge base.
    
    Args:
        search: Optional string to search for in the document title.
        source_type: Optional filter by source type.
        content_type: Optional filter by content type.
        sort_by: Field to sort by (created_at or title).
        order: Sort order (asc or desc).
    """
    logger.info(f"Tool called: list_documents with source_type: {source_type}, content_type: {content_type}")
    db = SessionLocal()
    try:
        query = db.query(Document)
        
        if search:
            query = query.filter(Document.title.ilike(f"%{search}%"))
            
        if source_type:
            query = query.filter(Document.source_type == source_type)
            
        if content_type:
            query = query.filter(Document.content_type == content_type)
            
        if sort_by == "title":
            order_col = Document.title
        else:
            order_col = Document.created_at
            
        if order.lower() == "asc":
            query = query.order_by(order_col.asc())
        else:
            query = query.order_by(order_col.desc())
            
        docs = query.all()
        
        results = [{
            "id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
            "content_type": doc.content_type,
            "indexing_status": doc.indexing_status.value if doc.indexing_status else "pending",
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        } for doc in docs]
        
        return json.dumps(results)
    except Exception as e:
        logger.error(f"Error in list_documents: {e}", exc_info=True)
        return f"Error: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def get_document(document_id: str) -> str:
    """
    Get metadata for a specific document by ID.
    """
    logger.info(f"Tool called: get_document for {document_id}")
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return f"Error: Document {document_id} not found"
            
        doc_info = {
            "id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
            "content_type": doc.content_type,
            "source_url": doc.source_url,
            "metadata": doc.metadata_,
            "indexing_status": doc.indexing_status.value if doc.indexing_status else None,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }
        return json.dumps(doc_info)
    except Exception as e:
        logger.error(f"Error in get_document: {e}", exc_info=True)
        return f"Error: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def get_document_chunk(chunk_id: str, document_id: str) -> str:
    """
    Get a specific document chunk by ID.
    """
    logger.info(f"Tool called: get_document_chunk for {chunk_id}")
    db = SessionLocal()
    try:
        chunk = db.query(DocumentChunk).filter(
            DocumentChunk.id == chunk_id,
            DocumentChunk.document_id == document_id
        ).first()
        
        if not chunk:
            return f"Error: Chunk {chunk_id} not found"
            
        chunk_info = {
            "id": str(chunk.id),
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "metadata": chunk.metadata_
        }
        return json.dumps(chunk_info)
    except Exception as e:
        logger.error(f"Error in get_document_chunk: {e}", exc_info=True)
        return f"Error: {str(e)}"
    finally:
        db.close()

def main():
    logger.info("Starting Enterprise Knowledge MCP Server (v2 stdio)")
    mcp.run()

if __name__ == "__main__":
    main()
