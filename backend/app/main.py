"""
BharatTrip SSOT Backend - FastAPI Application Entrypoint.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.routers.auth import router as auth_router
from backend.app.routers.support import router as support_router
from backend.app.routers.finance import router as finance_router
from backend.app.routers.escalations import router as escalations_router
from backend.app.routers.reconciliation import router as reconciliation_router
from backend.app.routers.metrics import router as metrics_router
from backend.app.routers.partners import router as partners_router
from backend.app.scripts.seed_db import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bharattrip.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup table creation and database hydration."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Auto-seed if database is empty
    db = SessionLocal()
    try:
        counts = seed_database(db=db, force=False)
        logger.info("Database hydration verified: %s", counts)
    except Exception as err:
        logger.error("Database initialization warning: %s", err)
    finally:
        db.close()
        
    yield
    logger.info("Shutting down BharatTrip SSOT API...")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Production REST API for BharatTrip AI Escalation Resolver & SSOT Management.",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    api_prefix = settings.API_V1_PREFIX
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(support_router, prefix=api_prefix)
    app.include_router(finance_router, prefix=api_prefix)
    app.include_router(escalations_router, prefix=api_prefix)
    app.include_router(reconciliation_router, prefix=api_prefix)
    app.include_router(metrics_router, prefix=api_prefix)
    app.include_router(partners_router, prefix=api_prefix)


    # Root & Health Endpoints
    @app.get("/", tags=["Health"])
    def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs_url": "/docs",
            "health_url": "/health",
        }

    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
        }

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error occurred. Please try again later."},
        )

    return app


app = create_app()
