from fastapi import FastAPI
from app.api.v1 import upload
from app.database import engine, Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise Knowledge MCP Server",
        description="Phase 1: Project Foundation + Local Document Ingestion",
        version="1.0.0",
    )

    app.include_router(upload.router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting up Enterprise Knowledge MCP Server")
        # In a real app we might run migrations here or ensure DB connectivity
        pass

    @app.get("/health")
    def health_check():
        from app.schemas.api_response import APIResponse
        return APIResponse(status="success", data={"status": "ok"})

    return app

app = create_app()
