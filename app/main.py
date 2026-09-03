from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
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

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": str(exc.detail), "data": None, "meta": None}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Validation Error", "data": None, "meta": None}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc), "data": None, "meta": None}
        )

    @app.get("/health")
    def health_check():
        from app.schemas.api_response import APIResponse
        return APIResponse(status="success", message="Health check successful", data={"status": "ok"})

    return app

app = create_app()
