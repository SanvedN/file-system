import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import structlog
import sys
import time

from .routes import get_file_service_router
from ..shared.db import init_db, close_db
from ..shared.cache import redis_client
from ..shared.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting File Service", port=settings.file_service_port)
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Connect to Redis
        await redis_client.connect()
        logger.info("Redis connected")
        
        # Create storage directories
        import os
        os.makedirs(settings.storage_base_path, exist_ok=True)
        logger.info("Storage directory created", path=settings.storage_base_path)
        
        yield
        
    except Exception as e:
        logger.error("Failed to start File Service", error=str(e))
        sys.exit(1)
    
    finally:
        # Shutdown
        logger.info("Shutting down File Service")
        
        try:
            # Close database connections
            await close_db()
            logger.info("Database connections closed")
            
            # Disconnect from Redis
            await redis_client.disconnect()
            logger.info("Redis disconnected")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title="File Management Service",
        description="Multi-tenant async file management and storage service",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log request
        logger.info(
            "Request processed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time
        )
        
        return response
    
    # Add global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception",
            error=str(exc),
            method=request.method,
            url=str(request.url),
            exc_info=True
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": "An unexpected error occurred",
                "error_code": "INTERNAL_ERROR"
            }
        )
    
    # Include routers
    app.include_router(get_file_service_router(), prefix="/api/v1")
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "service": "File Management Service",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs"
        }
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=settings.file_service_host,
        port=settings.file_service_port,
        reload=settings.debug,
        log_config=None,  # Use structlog instead
        access_log=False,  # Use custom middleware for logging
    )
