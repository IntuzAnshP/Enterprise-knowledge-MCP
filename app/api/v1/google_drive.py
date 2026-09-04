"""
Google Drive API Router — Phase 4
-----------------------------------
Exposes two REST endpoints:

  POST /api/v1/google-drive/sync
      Trigger a manual full sync.
      Returns a SyncResult with counts of new / updated / deleted / failed.

  GET  /api/v1/google-drive/status
      Returns connector configuration info and the count of indexed
      Google Drive documents.

Both endpoints validate that Google Drive credentials are configured
before attempting any Drive API calls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.google_drive.connector import GoogleDriveConnector
from app.connectors.google_drive.sync_service import GoogleDriveSyncService, SyncResult
from app.database import get_db
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document
from app.schemas.api_response import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Dependency helpers ─────────────────────────────────────────────────────────

def _get_connector() -> GoogleDriveConnector:
    """
    Build and return an authenticated GoogleDriveConnector.

    Raises 503 if credentials or folder ID are not configured.
    """
    if not settings.GOOGLE_DRIVE_CREDENTIALS_JSON:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Drive connector is not configured. "
                "Set GOOGLE_DRIVE_CREDENTIALS_JSON in your .env file."
            ),
        )
    if not settings.GOOGLE_DRIVE_FOLDER_ID:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Drive folder is not configured. "
                "Set GOOGLE_DRIVE_FOLDER_ID in your .env file."
            ),
        )
    return GoogleDriveConnector(
        credentials_path=settings.GOOGLE_DRIVE_CREDENTIALS_JSON,
        folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
        download_dir=settings.GOOGLE_DRIVE_DOWNLOAD_DIR,
    )


def _get_sync_service(
    connector: GoogleDriveConnector = Depends(_get_connector),
) -> GoogleDriveSyncService:
    return GoogleDriveSyncService(
        connector=connector,
        pipeline=IngestionPipeline(),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/google-drive/sync",
    summary="Trigger Google Drive sync",
    description=(
        "Performs a full sync of the configured Google Drive folder. "
        "New files are indexed, updated files are re-indexed, and "
        "deleted files are removed from the vector database."
    ),
    response_model=APIResponse,
)
def trigger_sync(
    db: Session = Depends(get_db),
    sync_service: GoogleDriveSyncService = Depends(_get_sync_service),
) -> APIResponse:
    """
    POST /api/v1/google-drive/sync

    Runs the sync inline and returns a SyncResult summary.
    For large folders (100+ files) consider moving this to a background task.
    """
    logger.info("Manual Google Drive sync triggered via API.")
    try:
        result: SyncResult = sync_service.run_sync(db)
    except Exception as exc:
        logger.error("Sync failed with unexpected error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return APIResponse(
        status="success",
        message="Google Drive sync completed.",
        data=result.model_dump(),
    )


@router.get(
    "/google-drive/status",
    summary="Google Drive connector status",
    description="Returns connector configuration and the number of indexed Google Drive documents.",
    response_model=APIResponse,
)
def get_status(db: Session = Depends(get_db)) -> APIResponse:
    """
    GET /api/v1/google-drive/status

    Does NOT call the Drive API — safe to call even when credentials are
    not yet configured (returns is_configured=False in that case).
    """
    is_configured = bool(
        settings.GOOGLE_DRIVE_CREDENTIALS_JSON and settings.GOOGLE_DRIVE_FOLDER_ID
    )

    indexed_count: int = (
        db.query(Document)
        .filter(Document.source_type == "google_drive")
        .count()
    )

    data: Dict[str, Any] = {
        "is_configured": is_configured,
        "folder_id": settings.GOOGLE_DRIVE_FOLDER_ID or None,
        "sync_interval_minutes": settings.GOOGLE_DRIVE_SYNC_INTERVAL_MINUTES,
        "indexed_document_count": indexed_count,
        "supported_file_types": ["pdf", "docx", "xlsx"],
    }

    return APIResponse(
        status="success",
        message="Google Drive connector status retrieved.",
        data=data,
    )
