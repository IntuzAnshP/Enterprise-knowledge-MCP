"""
Google Drive Sync Service — Phase 4
-------------------------------------
Orchestrates a full sync cycle between Google Drive and the local
vector database.

Lifecycle per sync run
----------------------
1. List all current files from Drive (connector.list_files)
2. For each file:
   a. Download to local temp path
   b. Build SourceItem
   c. Feed through IngestionPipeline (handles new / updated / unchanged)
   d. Clean up the downloaded temp file
3. Detect deletions:
   - Find all source_ids in DB where source_type='google_drive'
   - Subtract the set of current Drive file IDs
   - Delete orphaned documents (chunks + document record)
4. Return a SyncResult summary
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Set

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.connectors.google_drive.connector import GoogleDriveConnector, DriveFileMetadata
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.change_detection import ChangeResult
from app.models.document import Document
from app.vector_store.vector_storage_service import VectorStorageService

logger = logging.getLogger(__name__)


# ── Result schema ──────────────────────────────────────────────────────────────

class SyncResult(BaseModel):
    """Summary returned after a completed sync run."""

    started_at: datetime
    finished_at: Optional[datetime] = None
    total_files: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    failed: int = 0
    errors: List[str] = []

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


# ── Sync Service ──────────────────────────────────────────────────────────────

class GoogleDriveSyncService:
    """
    Drives a full sync cycle.

    Parameters
    ----------
    connector:
        Authenticated :class:`~app.connectors.google_drive.connector.GoogleDriveConnector`.
    pipeline:
        The shared :class:`~app.ingestion.pipeline.IngestionPipeline` instance.
    """

    def __init__(
        self,
        connector: GoogleDriveConnector,
        pipeline: IngestionPipeline,
    ) -> None:
        self._connector = connector
        self._pipeline = pipeline
        self._vector_store = VectorStorageService()

    # ── Public ────────────────────────────────────────────────────────────────

    def run_sync(self, db: Session) -> SyncResult:
        """
        Execute a full sync cycle and return a :class:`SyncResult`.

        The method is intentionally synchronous — suitable for both
        direct HTTP calls and background scheduler invocation.
        """
        result = SyncResult(started_at=datetime.now(timezone.utc))
        logger.info("Google Drive sync started at %s", result.started_at.isoformat())

        # ── 1. List all current Drive files ───────────────────────────────────
        try:
            drive_files: List[DriveFileMetadata] = self._connector.list_files()
        except Exception as exc:
            msg = f"Failed to list Drive files: {exc}"
            logger.error(msg, exc_info=True)
            result.errors.append(msg)
            result.finished_at = datetime.now(timezone.utc)
            return result

        result.total_files = len(drive_files)
        current_source_ids: Set[str] = {f.source_id for f in drive_files}

        # ── 2. Ingest each file ───────────────────────────────────────────────
        for file_meta in drive_files:
            local_path = None
            try:
                logger.info(
                    "Processing: %s (%s)", file_meta.name, file_meta.file_id
                )

                # Download file locally
                local_path = self._connector.download_file(
                    file_meta.file_id, file_meta.name
                )

                # Build SourceItem and run through the pipeline
                source_item = self._connector.build_source_item(file_meta, local_path)
                db_doc = self._pipeline.run(source_item, db)

                # Determine what the pipeline did by inspecting change detection result
                # We re-check by comparing timestamps rather than adding coupling
                # to pipeline internals — the pipeline already handles the logic;
                # we just classify the outcome for the summary.
                self._classify_outcome(file_meta, db_doc, result)

            except Exception as exc:
                msg = f"Failed to process '{file_meta.name}' ({file_meta.file_id}): {exc}"
                logger.error(msg, exc_info=True)
                result.failed += 1
                result.errors.append(msg)

            finally:
                # ── Clean up downloaded temp file ─────────────────────────────
                if local_path and local_path.exists():
                    try:
                        local_path.unlink()
                        # Remove the per-file directory if it is now empty
                        parent = local_path.parent
                        if parent.exists() and not any(parent.iterdir()):
                            parent.rmdir()
                    except OSError as cleanup_err:
                        logger.warning(
                            "Could not clean up temp file %s: %s", local_path, cleanup_err
                        )

        # ── 3. Handle deletions ───────────────────────────────────────────────
        result.deleted = self._handle_deletions(current_source_ids, db)

        # ── 4. Finalise ───────────────────────────────────────────────────────
        result.finished_at = datetime.now(timezone.utc)
        logger.info(
            "Google Drive sync finished in %.1fs | "
            "new=%d updated=%d unchanged=%d deleted=%d failed=%d",
            result.duration_seconds,
            result.new,
            result.updated,
            result.unchanged,
            result.deleted,
            result.failed,
        )
        return result

    # ── Private ───────────────────────────────────────────────────────────────

    def _classify_outcome(
        self,
        file_meta: DriveFileMetadata,
        db_doc: Document,
        result: SyncResult,
    ) -> None:
        """
        Increment the appropriate counter on *result* based on what the
        pipeline did for this file.

        The pipeline itself handles the real new/updated/unchanged logic via
        ChangeDetectionService. We infer the outcome here by comparing the
        document's ``created_at`` and ``updated_at`` timestamps.
        """
        now = datetime.now(timezone.utc)
        created_delta = (now - db_doc.created_at).total_seconds()
        updated_delta = (now - db_doc.updated_at).total_seconds()

        if created_delta < 10:
            # Document was just created — it's new
            result.new += 1
        elif updated_delta < 10:
            # Document was just modified — it was updated
            result.updated += 1
        else:
            # No change
            result.unchanged += 1

    def _handle_deletions(
        self, current_source_ids: Set[str], db: Session
    ) -> int:
        """
        Remove documents from the DB that are no longer present in Drive.

        Returns the number of documents deleted.
        """
        # Fetch all google_drive source_ids currently in the DB
        db_docs = (
            db.query(Document)
            .filter(Document.source_type == "google_drive")
            .all()
        )
        db_source_ids: Set[str] = {doc.source_id for doc in db_docs}

        deleted_ids = db_source_ids - current_source_ids
        if not deleted_ids:
            logger.info("No deleted Drive files detected.")
            return 0

        logger.info(
            "%d Drive file(s) deleted — removing from vector DB.", len(deleted_ids)
        )
        count = 0
        for source_id in deleted_ids:
            doc = (
                db.query(Document)
                .filter(Document.source_id == source_id)
                .first()
            )
            if doc:
                try:
                    self._vector_store.delete_chunks(doc.id, db)
                    db.delete(doc)
                    db.commit()
                    count += 1
                    logger.info("Removed deleted Drive document: %s", source_id)
                except Exception as exc:
                    logger.error(
                        "Failed to delete document %s: %s", source_id, exc, exc_info=True
                    )
                    db.rollback()

        return count
