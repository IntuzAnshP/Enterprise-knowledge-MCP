"""
Notion API Router — Phase 5
-----------------------------------
Exposes two REST endpoints:

  POST /api/v1/notion/sync
      Trigger a manual full sync.
      Returns a SyncResult with counts of new / updated / deleted / failed.

  GET  /api/v1/notion/status
      Returns connector configuration info and the count of indexed
      Notion pages.

Both endpoints validate that Notion credentials are configured
before attempting any API calls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.notion.connector import NotionConnector
from app.connectors.notion.sync_service import NotionSyncService, SyncResult
from app.database import get_db
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document
from app.schemas.api_response import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Dependency helpers ─────────────────────────────────────────────────────────

def _get_connector() -> NotionConnector:
    """
    Build and return an authenticated NotionConnector.

    Raises 503 if credentials or root page ID are not configured.
    """
    if not settings.NOTION_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Notion connector is not configured. "
                "Set NOTION_API_KEY in your .env file."
            ),
        )
    if not settings.NOTION_ROOT_PAGE_ID:
        raise HTTPException(
            status_code=503,
            detail=(
                "Notion root page is not configured. "
                "Set NOTION_ROOT_PAGE_ID in your .env file."
            ),
        )
    return NotionConnector(
        api_key=settings.NOTION_API_KEY,
        root_page_id=settings.NOTION_ROOT_PAGE_ID,
        download_dir=settings.NOTION_DOWNLOAD_DIR,
    )


def _get_sync_service(
    connector: NotionConnector = Depends(_get_connector),
) -> NotionSyncService:
    return NotionSyncService(
        connector=connector,
        pipeline=IngestionPipeline(),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/notion/sync",
    summary="Trigger Notion sync",
    description=(
        "Performs a full sync of the configured Notion pages. "
        "New pages are indexed, updated pages are re-indexed, and "
        "deleted pages are removed from the vector database."
    ),
    response_model=APIResponse,
)
def trigger_sync(
    db: Session = Depends(get_db),
    sync_service: NotionSyncService = Depends(_get_sync_service),
) -> APIResponse:
    """
    POST /api/v1/notion/sync

    Runs the sync inline and returns a SyncResult summary.
    """
    logger.info("Manual Notion sync triggered via API.")
    try:
        result: SyncResult = sync_service.run_sync(db)
    except Exception as exc:
        logger.error("Sync failed with unexpected error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return APIResponse(
        status="success",
        message="Notion sync completed.",
        data=result.model_dump(),
    )


@router.get(
    "/notion/status",
    summary="Notion connector status",
    description="Returns connector configuration and the number of indexed Notion documents.",
    response_model=APIResponse,
)
def get_status(db: Session = Depends(get_db)) -> APIResponse:
    """
    GET /api/v1/notion/status

    Does NOT call the Notion API — safe to call even when credentials are
    not yet configured (returns is_configured=False in that case).
    """
    is_configured = bool(
        settings.NOTION_API_KEY and settings.NOTION_ROOT_PAGE_ID
    )

    indexed_count: int = (
        db.query(Document)
        .filter(Document.source_type == "notion")
        .count()
    )

    data: Dict[str, Any] = {
        "is_configured": is_configured,
        "root_page_id": settings.NOTION_ROOT_PAGE_ID or None,
        "sync_interval_minutes": settings.NOTION_SYNC_INTERVAL_MINUTES,
        "indexed_document_count": indexed_count,
        "supported_file_types": ["notion"],
    }

    return APIResponse(
        status="success",
        message="Notion connector status retrieved.",
        data=data,
    )
