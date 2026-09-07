import asyncio
import json
import logging
import sys
from typing import Optional, Any
from pathlib import Path

# Base directory for the MCP Server
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from mcp.server.mcpserver import MCPServer


from app.database import SessionLocal
from app.retrieval.retrieval_service import RetrievalService
from app.schemas.retrieval import MetadataFilter
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.config import settings

# Configure logging to go to stderr so it doesn't interfere with MCP stdio
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server")

mcp = MCPServer("enterprise-knowledge")
retrieval_service = RetrievalService()

@mcp.tool()
def search_knowledge(
    query: str,
    source_type: Optional[Literal["local", "google_drive", "notion"]] = None,
    content_type: Optional[Literal["pdf", "docx", "xlsx", "notion"]] = None,
    document_id: Optional[str] = None,
    document_title: Optional[str] = None,
    limit: int = settings.RETRIEVAL_FINAL_K
) -> str:
    """
    Search the enterprise knowledge base for information using semantic search.

    CRITICAL - QUERY FORMULATION RULES:
    - NEVER pass vague or structural phrases as the query (e.g., "introduction section", "chapter 2", "summary").
      These have no semantic meaning and will produce poor results.
    - ALWAYS reformulate the query to describe the CONTENT you expect to find in the matching chunks.
      Think: "What words and concepts would appear in the text I am looking for?"
    - Expand the query with domain-specific vocabulary, key concepts, and relevant terminology.

    GOOD query examples:
    - User asks "give me the introduction": query="recurrent neural networks LSTM sequence modeling attention mechanism encoder decoder"
    - User asks "what is the conclusion": query="results state of the art performance improvements future work"
    - User asks "explain the methodology": query="experimental setup dataset training procedure evaluation metrics"

    BAD query examples (DO NOT USE):
    - "introduction section" — too vague, no content signal
    - "chapter 3" — structural label, not semantic content
    - "give me the summary" — describes user intent, not document content

    Args:
        query: A content-rich, semantically meaningful query describing what you expect the text to contain.
        source_type: Optional filter by source type (local, notion, google_drive).
        content_type: Optional filter by content type (pdf, docx, xlsx, notion).
        document_id: Optional filter by specific document ID.
        document_title: Optional filter by document name. If you only know the name of the document, use this instead of document_id.
        limit: Maximum number of chunks to return.
    """
    logger.info(f"Tool called: search_knowledge with query: {query}, document_title: {document_title}")
    db = SessionLocal()
    try:
        if document_title and not document_id:
            docs = db.query(Document).filter(Document.title.ilike(f"%{document_title}%")).all()
            if docs:
                document_id = str(docs[0].id)
                logger.info(f"Resolved document_title '{document_title}' to ID '{document_id}'")
            else:
                return f"Error: No document found matching title '{document_title}'. Try using list_documents to find the correct name."
                
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
    content_type: Optional[Literal["pdf", "docx", "xlsx", "notion"]] = None,
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
    WARNING: If you only have the document name, you must first use list_documents with the 'search' argument to find its ID. Do not guess the ID.
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
    WARNING: If you only have the document name, you must first use list_documents with the 'search' argument to find its ID.
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
import threading
import time

def auto_sync_loop():
    if not settings.GOOGLE_DRIVE_CREDENTIALS_JSON or not settings.GOOGLE_DRIVE_FOLDER_ID:
        logger.info("Google Drive credentials/folder not configured. Auto-sync disabled.")
        return
        
    interval_seconds = settings.GOOGLE_DRIVE_SYNC_INTERVAL_MINUTES * 60
    logger.info(f"Google Drive auto-sync scheduled every {settings.GOOGLE_DRIVE_SYNC_INTERVAL_MINUTES} minutes.")
    
    time.sleep(10)
    
    while True:
        try:
            logger.info("Starting scheduled Google Drive sync...")
            db = SessionLocal()
            try:
                from app.api.v1.google_drive import _get_connector
                from app.connectors.google_drive.sync_service import GoogleDriveSyncService
                from app.ingestion.pipeline import IngestionPipeline
                
                connector = _get_connector()
                sync_service = GoogleDriveSyncService(
                    connector=connector,
                    pipeline=IngestionPipeline()
                )
                result = sync_service.run_sync(db)
                logger.info(f"Scheduled sync complete: {result.new} new, {result.updated} updated, {result.deleted} deleted.")
            finally:
                db.close()
                
            time.sleep(interval_seconds)
        except Exception as e:
            logger.error(f"Error in Google Drive auto-sync: {e}", exc_info=True)
            time.sleep(60)

def notion_auto_sync_loop():
    if not settings.NOTION_API_KEY or not settings.NOTION_ROOT_PAGE_ID:
        logger.info("Notion credentials/root page not configured. Auto-sync disabled.")
        return
        
    interval_seconds = settings.NOTION_SYNC_INTERVAL_MINUTES * 60
    logger.info(f"Notion auto-sync scheduled every {settings.NOTION_SYNC_INTERVAL_MINUTES} minutes.")
    
    time.sleep(15)
    
    while True:
        try:
            logger.info("Starting scheduled Notion sync...")
            db = SessionLocal()
            try:
                from app.api.v1.notion import _get_connector as get_notion_connector
                from app.connectors.notion.sync_service import NotionSyncService
                from app.ingestion.pipeline import IngestionPipeline
                
                connector = get_notion_connector()
                sync_service = NotionSyncService(
                    connector=connector,
                    pipeline=IngestionPipeline()
                )
                result = sync_service.run_sync(db)
                logger.info(f"Scheduled Notion sync complete: {result.new} new, {result.updated} updated, {result.deleted} deleted.")
            finally:
                db.close()
                
            time.sleep(interval_seconds)
        except Exception as e:
            logger.error(f"Error in Notion auto-sync: {e}", exc_info=True)
            time.sleep(60)

def main():
    logger.info("Starting Enterprise Knowledge MCP Server (v2 stdio)")
    gd_sync_thread = threading.Thread(target=auto_sync_loop, daemon=True)
    gd_sync_thread.start()
    
    notion_sync_thread = threading.Thread(target=notion_auto_sync_loop, daemon=True)
    notion_sync_thread.start()
    
    mcp.run()

if __name__ == "__main__":
    main()
