"""
Google Drive Connector — Phase 4
---------------------------------
Authenticates via a Service Account JSON, lists all supported files
(PDF / DOCX / XLSX) inside a configured root folder (recursively),
downloads them locally, and returns SourceItem objects ready for the
existing IngestionPipeline.

Usage
-----
connector = GoogleDriveConnector(
    credentials_path=settings.GOOGLE_DRIVE_CREDENTIALS_JSON,
    folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
    download_dir=settings.GOOGLE_DRIVE_DOWNLOAD_DIR,
)
files = connector.list_files()
for f in files:
    local_path = connector.download_file(f.file_id, f.name)
    source_item = connector.build_source_item(f, local_path)
    pipeline.run(source_item, db)
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from pydantic import BaseModel

from app.schemas.source_item import SourceItem

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

# Maps Google Drive MIME types → our internal content_type strings
SUPPORTED_MIME_TYPES: Dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}

# Google API scope — read-only is sufficient; we never write back to Drive
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Drive API files.list page size (max 1000)
PAGE_SIZE = 200


# ── Data Models ───────────────────────────────────────────────────────────────

class DriveFileMetadata(BaseModel):
    """Lightweight representation of a Google Drive file."""

    file_id: str
    name: str
    mime_type: str
    content_type: str           # 'pdf' | 'docx' | 'xlsx'
    modified_time: datetime     # UTC-aware
    web_view_link: Optional[str] = None
    size_bytes: int = 0

    @property
    def source_id(self) -> str:
        """Unique, namespaced source ID used across the system."""
        return f"google_drive:{self.file_id}"


# ── Connector ─────────────────────────────────────────────────────────────────

class GoogleDriveConnector:
    """
    Wraps the Google Drive API v3.

    All files are scoped to a single configured root folder.
    Sub-folders are recursed automatically.
    Only PDF, DOCX, and XLSX files are returned.
    """

    def __init__(
        self,
        credentials_path: str,
        folder_id: str,
        download_dir: Path,
    ) -> None:
        if not credentials_path:
            raise ValueError(
                "GOOGLE_DRIVE_CREDENTIALS_JSON is not set. "
                "Provide the path to your service account JSON file."
            )
        if not folder_id:
            raise ValueError(
                "GOOGLE_DRIVE_FOLDER_ID is not set. "
                "Provide the ID of the Drive folder to watch."
            )

        self._folder_id = folder_id
        self._download_dir = download_dir
        self._download_dir.mkdir(parents=True, exist_ok=True)

        # Build the authenticated Drive service
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info(
            "GoogleDriveConnector initialised — root folder: %s", folder_id
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def list_files(self) -> List[DriveFileMetadata]:
        """
        Recursively list all supported files under the configured root folder.

        Returns
        -------
        List[DriveFileMetadata]
            One entry per file, sorted by name for reproducible ordering.
        """
        logger.info("Listing Drive files under folder: %s", self._folder_id)
        results: List[DriveFileMetadata] = []
        self._collect_files(self._folder_id, results)
        logger.info("Found %d supported file(s) in Drive.", len(results))
        return results

    def download_file(self, file_id: str, filename: str) -> Path:
        """
        Download a Drive file to the local download directory.

        The file is saved as ``<download_dir>/<file_id>/<filename>``
        so parallel downloads never overwrite each other.

        Parameters
        ----------
        file_id:
            Google Drive file ID.
        filename:
            Original filename (used as the local file name).

        Returns
        -------
        Path
            Absolute path to the downloaded file.
        """
        file_dir = self._download_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        local_path = file_dir / filename

        logger.debug("Downloading Drive file %s → %s", file_id, local_path)

        request = self._service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        local_path.write_bytes(buffer.getvalue())
        logger.debug("Download complete: %s (%d bytes)", local_path, local_path.stat().st_size)
        return local_path

    def build_source_item(
        self, file_meta: DriveFileMetadata, local_path: Path
    ) -> SourceItem:
        """
        Convert Drive file metadata + local download path into a
        :class:`~app.schemas.source_item.SourceItem` for the ingestion pipeline.
        """
        return SourceItem(
            source_type="google_drive",
            source_id=file_meta.source_id,              # "google_drive:<file_id>"
            content_type=file_meta.content_type,        # 'pdf' | 'docx' | 'xlsx'
            raw_path=local_path.absolute(),
            original_filename=file_meta.name,
            file_size=file_meta.size_bytes or local_path.stat().st_size,
            uploaded_at=datetime.now(timezone.utc),
            metadata={
                "google_drive_file_id": file_meta.file_id,
                "mime_type": file_meta.mime_type,
                "modified_time": file_meta.modified_time.isoformat(),
                "web_view_link": file_meta.web_view_link or "",
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _collect_files(
        self, folder_id: str, results: List[DriveFileMetadata]
    ) -> None:
        """
        Recursively collect supported files from *folder_id*.

        Sub-folders (``application/vnd.google-apps.folder``) are traversed
        depth-first. Unsupported MIME types are silently skipped.
        """
        page_token: Optional[str] = None

        # Build MIME filter: include sub-folders so we can recurse,
        # plus the three supported file types.
        supported_mime_filter = " or ".join(
            [f"mimeType='{m}'" for m in SUPPORTED_MIME_TYPES]
            + ["mimeType='application/vnd.google-apps.folder'"]
        )
        query = (
            f"'{folder_id}' in parents"
            f" and ({supported_mime_filter})"
            f" and trashed=false"
        )

        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    pageSize=PAGE_SIZE,
                    pageToken=page_token,
                    fields=(
                        "nextPageToken, files("
                        "id, name, mimeType, modifiedTime, webViewLink, size"
                        ")"
                    ),
                )
                .execute()
            )

            for item in response.get("files", []):
                mime = item["mimeType"]

                if mime == "application/vnd.google-apps.folder":
                    # Recurse into sub-folder
                    logger.debug("Recursing into sub-folder: %s (%s)", item["name"], item["id"])
                    self._collect_files(item["id"], results)

                elif mime in SUPPORTED_MIME_TYPES:
                    try:
                        modified_time = datetime.fromisoformat(
                            item["modifiedTime"].replace("Z", "+00:00")
                        )
                    except (KeyError, ValueError):
                        modified_time = datetime.now(timezone.utc)

                    results.append(
                        DriveFileMetadata(
                            file_id=item["id"],
                            name=item["name"],
                            mime_type=mime,
                            content_type=SUPPORTED_MIME_TYPES[mime],
                            modified_time=modified_time,
                            web_view_link=item.get("webViewLink"),
                            size_bytes=int(item.get("size", 0)),
                        )
                    )

            page_token = response.get("nextPageToken")
            if not page_token:
                break
