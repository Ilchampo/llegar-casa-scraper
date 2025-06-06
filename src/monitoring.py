"""Monitoring endpoints and health checks for production readiness."""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from .circuit_breaker import get_all_circuit_breakers
from .retry_handler import get_all_retry_handlers
from .metrics import metrics
from .scraper.service import ScraperService
from .logging_config import get_logger

logger = get_logger("monitoring")

monitoring_router = APIRouter()


class SystemHealth(BaseModel):
    """System health status model."""
    status: str
    timestamp: str
    uptime_seconds: float
    version: str
    environment: str


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status model."""
    name: str
    state: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    success_rate_percent: float
    consecutive_failures: int
    consecutive_successes: int
    circuit_opened_count: int
    last_failure_time: Optional[str] = None
    last_success_time: Optional[str] = None
    config: Dict[str, Any]


class RetryHandlerStatus(BaseModel):
    """Retry handler status model."""
    name: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    total_retries: int
    average_attempts: float
    config: Dict[str, Any]


class MetricsSummary(BaseModel):
    """Metrics summary model."""
    timestamp: str
    overview: Dict[str, Any]
    performance: Dict[str, Any]
    business_metrics: Dict[str, Any]


app_start_time = datetime.now()


@monitoring_router.get("/health/system", response_model=SystemHealth)
async def system_health():
    """
    System-level health check.
    
    Returns overall system health, uptime, and basic information.
    """
    from .config import settings
    
    uptime = (datetime.now() - app_start_time).total_seconds()
    
    return SystemHealth(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        uptime_seconds=uptime,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT.value
    )


@monitoring_router.get("/health/detailed")
async def detailed_health():
    """
    Detailed health check including all subsystems.
    
    Returns comprehensive health information for all components.
    """
    scraper_service = ScraperService()
    scraper_health = await scraper_service.health_check()
    
    circuit_breakers = get_all_circuit_breakers()
    cb_statuses = {name: cb.get_status() for name, cb in circuit_breakers.items()}
    
    retry_handlers = get_all_retry_handlers()
    retry_statuses = {name: rh.get_stats() for name, rh in retry_handlers.items()}
    
    metrics_summary = metrics.get_summary()
    
    overall_status = "healthy"
    
    open_circuit_breakers = [
        name for name, status in cb_statuses.items() 
        if status["state"] == "open"
    ]
    
    if open_circuit_breakers:
        overall_status = "degraded"
    
    if scraper_health.status != "healthy":
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "scraper": {
                "status": scraper_health.status,
                "browser_available": scraper_health.browser_available,
                "last_successful_search": (
                    scraper_health.last_successful_search.isoformat()
                    if scraper_health.last_successful_search else None
                ),
                "circuit_breaker_state": getattr(scraper_health, 'circuit_breaker_state', 'unknown')
            },
            "circuit_breakers": cb_statuses,
            "retry_handlers": retry_statuses,
            "metrics": metrics_summary
        },
        "issues": {
            "open_circuit_breakers": open_circuit_breakers,
            "unhealthy_components": [
                comp for comp, details in {
                    "scraper": scraper_health.status != "healthy"
                }.items() if details
            ]
        }
    }


@monitoring_router.get("/metrics", response_model=MetricsSummary)
async def get_metrics_summary():
    """
    Get application metrics summary.
    
    Returns key performance and business metrics.
    """
    summary = metrics.get_summary()
    
    return MetricsSummary(
        timestamp=summary["timestamp"],
        overview=summary["overview"],
        performance=summary["performance"],
        business_metrics=summary["business_metrics"]
    )


@monitoring_router.get("/metrics/detailed")
async def get_detailed_metrics():
    """
    Get all application metrics.
    
    Returns comprehensive metrics data including histograms and counters.
    """
    return metrics.get_all_metrics()


@monitoring_router.get("/circuit-breakers")
async def get_circuit_breakers():
    """
    Get circuit breaker statuses.
    
    Returns status of all circuit breakers in the system.
    """
    circuit_breakers = get_all_circuit_breakers()
    
    statuses = []
    for name, cb in circuit_breakers.items():
        status = cb.get_status()
        
        total_calls = status["stats"]["total_calls"]
        successful_calls = status["stats"]["successful_calls"]
        success_rate = (
            (successful_calls / total_calls * 100) if total_calls > 0 else 0
        )
        
        statuses.append(CircuitBreakerStatus(
            name=status["name"],
            state=status["state"],
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=status["stats"]["failed_calls"],
            success_rate_percent=round(success_rate, 2),
            consecutive_failures=status["stats"]["consecutive_failures"],
            consecutive_successes=status["stats"]["consecutive_successes"],
            circuit_opened_count=status["stats"]["circuit_opened_count"],
            last_failure_time=status["stats"]["last_failure_time"],
            last_success_time=status["stats"]["last_success_time"],
            config=status["config"]
        ))
    
    return {
        "timestamp": datetime.now().isoformat(),
        "circuit_breakers": statuses
    }


@monitoring_router.get("/retry-handlers")
async def get_retry_handlers():
    """
    Get retry handler statistics.
    
    Returns statistics for all retry handlers in the system.
    """
    retry_handlers = get_all_retry_handlers()
    
    statuses = []
    for name, rh in retry_handlers.items():
        stats = rh.get_stats()
        
        statuses.append(RetryHandlerStatus(
            name=stats["name"],
            total_attempts=stats["stats"]["total_attempts"],
            successful_attempts=stats["stats"]["successful_attempts"],
            failed_attempts=stats["stats"]["failed_attempts"],
            total_retries=stats["stats"]["total_retries"],
            average_attempts=round(stats["stats"]["average_attempts"], 2),
            config=stats["config"]
        ))
    
    return {
        "timestamp": datetime.now().isoformat(),
        "retry_handlers": statuses
    }


@monitoring_router.get("/performance")
async def get_performance_metrics():
    """
    Get performance-focused metrics.
    
    Returns metrics specifically related to performance and latency.
    """
    http_duration = metrics.get_histogram("http_request_duration")
    http_stats = http_duration.get_stats() if http_duration else {}
    
    search_duration = metrics.get_histogram("scraper_search_duration")
    search_stats = search_duration.get_stats() if search_duration else {}
    
    cb_calls = metrics.get_counter("circuit_breaker_calls")
    cb_opens = metrics.get_counter("circuit_breaker_opens")
    
    retry_attempts = metrics.get_counter("retry_attempts")
    retry_delay = metrics.get_histogram("retry_delay")
    retry_delay_stats = retry_delay.get_stats() if retry_delay else {}
    
    return {
        "timestamp": datetime.now().isoformat(),
        "response_times": {
            "http_requests": {
                "count": http_stats.get("count", 0),
                "avg_seconds": round(http_stats.get("avg", 0), 3),
                "total_seconds": round(http_stats.get("sum", 0), 2)
            },
            "scraper_searches": {
                "count": search_stats.get("count", 0),
                "avg_seconds": round(search_stats.get("avg", 0), 3),
                "total_seconds": round(search_stats.get("sum", 0), 2)
            }
        },
        "resilience": {
            "circuit_breaker_calls": cb_calls.get_value() if cb_calls else 0,
            "circuit_breaker_opens": cb_opens.get_value() if cb_opens else 0,
            "total_retry_attempts": retry_attempts.get_value() if retry_attempts else 0,
            "avg_retry_delay_seconds": round(retry_delay_stats.get("avg", 0), 3)
        },
        "active_resources": {
            "active_searches": metrics.get_gauge("scraper_active_searches").get_value(),
            "browser_instances": metrics.get_gauge("browser_instances").get_value()
        }
    }


@monitoring_router.get("/business")
async def get_business_metrics():
    """
    Get business-focused metrics.
    
    Returns metrics related to business operations and outcomes.
    """
    plates_searched = metrics.get_counter("license_plates_searched")
    matches_found = metrics.get_counter("name_matches_found")
    incapsula_blocks = metrics.get_counter("incapsula_blocks")
    
    total_searches = metrics.get_counter("scraper_searches_total")
    successful_searches = metrics.get_counter("scraper_searches_successful")
    failed_searches = metrics.get_counter("scraper_searches_failed")
    
    total_search_count = total_searches.get_value() if total_searches else 0
    success_count = successful_searches.get_value() if successful_searches else 0
    plate_count = plates_searched.get_value() if plates_searched else 0
    match_count = matches_found.get_value() if matches_found else 0
    
    success_rate = (success_count / total_search_count * 100) if total_search_count > 0 else 0
    match_rate = (match_count / plate_count * 100) if plate_count > 0 else 0
    
    return {
        "timestamp": datetime.now().isoformat(),
        "search_operations": {
            "total_searches": total_search_count,
            "successful_searches": success_count,
            "failed_searches": failed_searches.get_value() if failed_searches else 0,
            "success_rate_percent": round(success_rate, 2)
        },
        "business_outcomes": {
            "license_plates_searched": plate_count,
            "name_matches_found": match_count,
            "match_rate_percent": round(match_rate, 2)
        },
        "external_factors": {
            "incapsula_blocks": incapsula_blocks.get_value() if incapsula_blocks else 0
        }
    }


@monitoring_router.post("/reset-metrics")
async def reset_metrics():
    """
    Reset all metrics (for testing/development only).
    
    WARNING: This will clear all accumulated metrics data.
    """
    logger.warning("Metrics reset requested")
    
    return {
        "message": "Metrics reset is not implemented in production for safety",
        "timestamp": datetime.now().isoformat()
    }


async def get_system_health_status() -> str:
    """Dependency to get system health status."""
    health = await detailed_health()
    return health["status"] 