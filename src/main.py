from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time

from .config import settings
from .constants import Environment
from .logging_config import setup_logging, get_logger
from .metrics import inc_requests, inc_errors, observe_request_duration

setup_logging()
logger = get_logger(__name__)

app_configs = {
    "title": settings.APP_NAME,
    "description": "A microservice for web scraping crime report data from Ecuador's SIAF system",
    "version": settings.APP_VERSION,
}

if settings.ENVIRONMENT == Environment.PRODUCTION:
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Add metrics collection and request timing."""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    path_template = request.url.path
    method = request.method
    client_ip = request.client.host
    
    logger.info(
        f"Request started: {method} {path_template}",
        extra={
            "request_id": request_id,
            "method": method,
            "path": path_template,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", "")
        }
    )
    
    inc_requests(labels={"method": method, "path": path_template})
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    status_code = response.status_code
    
    observe_request_duration(duration)
    
    if status_code >= 400:
        inc_errors(labels={
            "method": method, 
            "path": path_template, 
            "status_code": str(status_code)
        })
    
    logger.info(
        f"Request completed: {method} {path_template} - {status_code}",
        extra={
            "request_id": request_id,
            "method": method,
            "path": path_template,
            "status_code": status_code,
            "duration_seconds": round(duration, 3),
            "client_ip": client_ip
        }
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

from .scraper.router import router as scraper_router
from .monitoring import monitoring_router

app.include_router(scraper_router, prefix="/scraper", tags=["Scraper"])
app.include_router(monitoring_router, prefix="/monitoring", tags=["Monitoring"])

@app.get("/")
async def root():
    """Root endpoint with service information."""
    logger.info("Root endpoint accessed")
    return {
        "message": f"{settings.APP_NAME} is running!",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs" if settings.SHOW_DOCS else None,
        "monitoring": {
            "health": "/monitoring/health/system",
            "detailed_health": "/monitoring/health/detailed", 
            "metrics": "/monitoring/metrics",
            "performance": "/monitoring/performance",
            "business": "/monitoring/business"
        }
    }

@app.get("/health")
async def health_check():
    """Global health check endpoint."""
    logger.info("Global health check accessed")
    return {
        "status": "healthy", 
        "service": "llegar-casa-scrapper",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "Application starting up",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT.value
        }
    )
    
    logger.info(
        "Production features enabled",
        extra={
            "features": [
                "structured_logging",
                "request_tracing", 
                "metrics_collection",
                "circuit_breakers",
                "retry_logic",
                "rate_limiting",
                "input_validation",
                "monitoring_endpoints"
            ]
        }
    )

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Application shutting down")