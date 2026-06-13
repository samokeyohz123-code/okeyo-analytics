from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from loguru import logger
import time, sys, os

from app.core.config import settings
from app.db.session import init_db
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.endpoints import (
    users_router, customers_router, statements_router,
    analysis_router, reports_router, audit_router, dashboard_router,
)

logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OKEYO Analytics Backend starting...")
    os.makedirs(settings.UPLOAD_DIR,  exist_ok=True)
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    await init_db()
    logger.info(f"OKEYO Analytics v{settings.APP_VERSION} ready")
    yield
    logger.info("OKEYO Analytics shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def request_timer(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.time() - start) * 1000, 1))
    return response

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(l) for l in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"success": False, "error": "Validation failed", "details": errors})

@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"success": False, "error": "Internal server error"})

PREFIX = "/api/v1"
app.include_router(auth_router,       prefix=PREFIX)
app.include_router(users_router,      prefix=PREFIX)
app.include_router(customers_router,  prefix=PREFIX)
app.include_router(statements_router, prefix=PREFIX)
app.include_router(analysis_router,   prefix=PREFIX)
app.include_router(reports_router,    prefix=PREFIX)
app.include_router(audit_router,      prefix=PREFIX)
app.include_router(dashboard_router,  prefix=PREFIX)

@app.get("/health")
async def health():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}

@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/api/docs"}
