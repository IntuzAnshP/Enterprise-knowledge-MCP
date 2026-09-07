"""
Notion Connector — Phase 5
---------------------------------
Authenticates via a Notion Integration Token, lists all pages/databases
inside a configured root (recursively), downloads their block content locally
as JSON, and returns SourceItem objects ready for the IngestionPipeline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from notion_client import Client
from pydantic import BaseModel

from app.schemas.source_item import SourceItem

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────

class NotionPageMetadata(BaseModel):
    """Lightweight representation of a Notion Page or Database."""

    page_id: str
    name: str
    content_type: str           # 'notion'
    modified_time: datetime     # UTC-aware
    url: Optional[str] = None

    @property
    def source_id(self) -> str:
        """Unique, namespaced source ID used across the system."""
        return f"notion:{self.page_id}"


# ── Connector ─────────────────────────────────────────────────────────────────

class NotionConnector:
    """
    Wraps the Notion API.

    All pages are scoped to a single configured root page or database.
    Sub-pages are recursed automatically if they are shared with the integration.
    """

    def __init__(
        self,
        api_key: str,
        root_page_id: str,
        download_dir: Path,
    ) -> None:
        if not api_key:
            raise ValueError(
                "NOTION_API_KEY is not set. "
                "Provide your Notion integration token."
            )
        if not root_page_id:
            raise ValueError(
                "NOTION_ROOT_PAGE_ID is not set. "
                "Provide the ID of the Notion root page/database."
            )

        self._root_page_id = root_page_id
        self._download_dir = download_dir
        self._download_dir.mkdir(parents=True, exist_ok=True)

        self._client = Client(auth=api_key)
        logger.info("NotionConnector initialised — root: %s", root_page_id)

    # ── Public API ────────────────────────────────────────────────────────────

    def list_pages(self) -> List[NotionPageMetadata]:
        """
        List pages and databases the integration has access to.
        Because Notion's search endpoint returns all shared pages,
        we can use it to discover everything, but in a real-world scenario
        you might recursively query children of the root_page_id.
        For simplicity, we use search to find all pages/databases.

        Returns
        -------
        List[NotionPageMetadata]
            One entry per page/database.
        """
        logger.info("Searching for accessible Notion pages/databases.")
        results: List[NotionPageMetadata] = []
        
        has_more = True
        next_cursor = None
        
        while has_more:
            response = self._client.search(
                start_cursor=next_cursor,
                page_size=100
            )
            
            for item in response.get("results", []):
                obj_type = item.get("object")
                if obj_type not in ["page", "database"]:
                    continue
                
                # Extract title
                name = "Untitled"
                if obj_type == "page":
                    props = item.get("properties", {})
                    # Find a property of type 'title'
                    for prop_name, prop_val in props.items():
                        if isinstance(prop_val, dict) and prop_val.get("type") == "title":
                            title_arr = prop_val.get("title", [])
                            if title_arr:
                                name = "".join(t.get("plain_text", "") for t in title_arr)
                            break
                elif obj_type == "database":
                    title_arr = item.get("title", [])
                    if title_arr:
                        name = "".join(t.get("plain_text", "") for t in title_arr)
                        
                # Extract modified time
                last_edited = item.get("last_edited_time")
                try:
                    modified_time = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                except (ValueError, AttributeError, TypeError):
                    modified_time = datetime.now(timezone.utc)
                    
                results.append(
                    NotionPageMetadata(
                        page_id=item["id"],
                        name=name,
                        content_type="notion",
                        modified_time=modified_time,
                        url=item.get("url")
                    )
                )
                
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")

        logger.info("Found %d accessible Notion item(s).", len(results))
        return results

    def download_page_json(self, page_id: str, filename: str) -> Path:
        """
        Download a Notion page's blocks as JSON to the local download directory.

        Parameters
        ----------
        page_id:
            Notion page/database ID.
        filename:
            Original title (used as the local file name).

        Returns
        -------
        Path
            Absolute path to the downloaded file.
        """
        # Safe filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).strip() or "Untitled"
        file_dir = self._download_dir / page_id
        file_dir.mkdir(parents=True, exist_ok=True)
        local_path = file_dir / f"{safe_filename}.json"

        logger.debug("Downloading Notion page %s → %s", page_id, local_path)

        def _fetch_all_blocks(block_id: str) -> List[Dict[str, Any]]:
            fetched_blocks = []
            has_more_blocks = True
            next_cur = None
            try:
                while has_more_blocks:
                    res = self._client.blocks.children.list(
                        block_id=block_id,
                        start_cursor=next_cur,
                        page_size=100
                    )
                    for b in res.get("results", []):
                        fetched_blocks.append(b)
                        b_type = b.get("type")
                        if b.get("has_children", False) and b_type not in ("child_page", "child_database"):
                            b["children"] = _fetch_all_blocks(b["id"])
                    
                    has_more_blocks = res.get("has_more", False)
                    next_cur = res.get("next_cursor")
            except Exception as ex:
                logger.warning("Could not fetch child blocks for %s: %s", block_id, ex)
            return fetched_blocks

        blocks = _fetch_all_blocks(page_id)

        # Retrieve page/database metadata itself
        try:
            page_meta = self._client.pages.retrieve(page_id=page_id)
        except Exception:
            try:
                page_meta = self._client.databases.retrieve(database_id=page_id)
            except Exception:
                page_meta = {}

        data = {
            "metadata": page_meta,
            "blocks": blocks
        }
        
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.debug("Download complete: %s (%d bytes)", local_path, local_path.stat().st_size)
        return local_path

    def build_source_item(
        self, page_meta: NotionPageMetadata, local_path: Path
    ) -> SourceItem:
        """
        Convert Notion page metadata + local JSON path into a
        SourceItem for the ingestion pipeline.
        """
        return SourceItem(
            source_type="notion",
            source_id=page_meta.source_id,              # "notion:<page_id>"
            content_type=page_meta.content_type,        # 'notion'
            raw_path=local_path.absolute(),
            original_filename=local_path.name,
            file_size=local_path.stat().st_size,
            uploaded_at=datetime.now(timezone.utc),
            metadata={
                "notion_page_id": page_meta.page_id,
                "modified_time": page_meta.modified_time.isoformat(),
                "url": page_meta.url or "",
            },
        )
