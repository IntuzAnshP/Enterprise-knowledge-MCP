"""
Notion Sync Service — Phase 5
-------------------------------------
Orchestrates a full sync cycle between Notion and the local
vector database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Set

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.connectors.notion.connector import NotionConnector, NotionPageMetadata
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document
from app.vector_store.vector_storage_service import VectorStorageService

logger = logging.getLogger(__name__)


# ── Result schema ──────────────────────────────────────────────────────────────

class SyncResult(BaseModel):
    """Summary returned after a completed sync run."""

    started_at: datetime
    finished_at: Optional[datetime] = None
    total_pages: int = 0
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

class NotionSyncService:
    """
    Drives a full Notion sync cycle.
    """

    def __init__(
        self,
        connector: NotionConnector,
        pipeline: IngestionPipeline,
    ) -> None:
        self._connector = connector
        self._pipeline = pipeline
        self._vector_store = VectorStorageService()

    # ── Public ────────────────────────────────────────────────────────────────

    def run_sync(self, db: Session) -> SyncResult:
        """
        Execute a full sync cycle and return a :class:`SyncResult`.
        """
        result = SyncResult(started_at=datetime.now(timezone.utc))
        logger.info("Notion sync started at %s", result.started_at.isoformat())

        # ── 1. List all current Notion pages ──────────────────────────────────
        try:
            notion_pages: List[NotionPageMetadata] = self._connector.list_pages()
        except Exception as exc:
            msg = f"Failed to list Notion pages: {exc}"
            logger.error(msg, exc_info=True)
            result.errors.append(msg)
            result.finished_at = datetime.now(timezone.utc)
            return result

        result.total_pages = len(notion_pages)
        current_source_ids: Set[str] = {p.source_id for p in notion_pages}

        # ── 2. Ingest each page ───────────────────────────────────────────────
        for page_meta in notion_pages:
            local_path = None
            try:
                logger.info(
                    "Processing: %s (%s)", page_meta.name, page_meta.page_id
                )

                # Download page JSON locally
                local_path = self._connector.download_page_json(
                    page_meta.page_id, page_meta.name
                )

                # Build SourceItem and run through the pipeline
                source_item = self._connector.build_source_item(page_meta, local_path)
                db_doc = self._pipeline.run(source_item, db)

                self._classify_outcome(page_meta, db_doc, result)

            except Exception as exc:
                msg = f"Failed to process '{page_meta.name}' ({page_meta.page_id}): {exc}"
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
            "Notion sync finished in %.1fs | "
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
        page_meta: NotionPageMetadata,
        db_doc: Document,
        result: SyncResult,
    ) -> None:
        """
        Increment the appropriate counter on *result* based on what the
        pipeline did for this file.
        """
        now = datetime.now(timezone.utc)
        created_delta = (now - db_doc.created_at).total_seconds()
        updated_delta = (now - db_doc.updated_at).total_seconds()

        if created_delta < 10:
            result.new += 1
        elif updated_delta < 10:
            result.updated += 1
        else:
            result.unchanged += 1

    def _handle_deletions(
        self, current_source_ids: Set[str], db: Session
    ) -> int:
        """
        Remove documents from the DB that are no longer present in Notion.
        """
        db_docs = (
            db.query(Document)
            .filter(Document.source_type == "notion")
            .all()
        )
        db_source_ids: Set[str] = {doc.source_id for doc in db_docs}

        deleted_ids = db_source_ids - current_source_ids
        if not deleted_ids:
            logger.info("No deleted Notion pages detected.")
            return 0

        logger.info(
            "%d Notion page(s) deleted — removing from vector DB.", len(deleted_ids)
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
                    logger.info("Removed deleted Notion document: %s", source_id)
                except Exception as exc:
                    logger.error(
                        "Failed to delete document %s: %s", source_id, exc, exc_info=True
                    )
                    db.rollback()

        return count
