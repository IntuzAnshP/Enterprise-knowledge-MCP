import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.config import settings
from app.schemas.source_item import SourceItem
from app.parsers.router import ParserRouter

class UploadService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.router = ParserRouter()

    async def save_upload_file(self, upload_file: UploadFile) -> SourceItem:
        # Validate size (approximate using seek if needed, or we rely on FastAPI middleware)
        # Assuming we check it during read or from headers in production
        
        # Check if empty filename
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        source_id = str(uuid.uuid4())
        file_dir = self.upload_dir / source_id
        file_dir.mkdir(parents=True, exist_ok=True)
        
        raw_path = file_dir / upload_file.filename
        
        # Write file to disk
        file_size = 0
        with open(raw_path, "wb") as buffer:
            while chunk := await upload_file.read(8192):
                file_size += len(chunk)
                buffer.write(chunk)
                
        # Validate max size
        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            os.remove(raw_path)
            file_dir.rmdir()
            raise HTTPException(status_code=413, detail=f"File too large. Max size is {settings.MAX_FILE_SIZE_MB}MB")

        # Detect content type using python-magic
        content_type = self.router.detect_content_type(str(raw_path))
        
        if content_type == "unknown":
            # Clean up
            os.remove(raw_path)
            file_dir.rmdir()
            raise HTTPException(status_code=415, detail="Unsupported file format. Only PDF, DOCX, and XLSX are supported.")
            
        return SourceItem(
            source_type="local",
            source_id=source_id,
            content_type=content_type,
            raw_path=raw_path.absolute(),
            original_filename=upload_file.filename,
            file_size=file_size,
            uploaded_at=datetime.now(timezone.utc)
        )
