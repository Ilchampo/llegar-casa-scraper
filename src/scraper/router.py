"""Scraper module FastAPI router."""

import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Request, status

from .schemas import ComplaintSearchResponse, ScraperHealthResponse
from .service import ScraperService
from .exceptions import ScraperException, PlateNotFound, ScrapingTimeout, IncapsulaBlockedException
from .dependencies import check_rate_limit, validate_license_plate, ServiceHealth
from ..logging_config import get_logger, RequestLogger

router = APIRouter()

scraper_service = ScraperService()

logger = get_logger(__name__)


@router.get("/complaints", response_model=ComplaintSearchResponse)
async def search_complaints(
    request: Request,
    license_plate: Annotated[str, Depends(validate_license_plate)],
):
    """
    Search for crime complaints by license plate.
    
    This endpoint searches the SIAF database for crime reports associated with
    the given license plate and returns the crime data if found.
    
    **Rate Limiting:** Maximum 20 requests per 5 minutes per IP address.
    
    **Response Examples:**
    
    **Success with results found:**
    ```json
    {
        "searched_plate": "ABC1234",
        "search_successful": true,
        "crime_report_number": "100301816010030",
        "lugar": "IMBABURA - COTACACHI", 
        "fecha": "2016-01-27",
        "delito": "RECEPTACIÓN(3575)",
        "error_message": null
    }
    ```
    
    **No results found:**
    ```json
    {
        "searched_plate": "ABC1234",
        "search_successful": true,
        "crime_report_number": null,
        "lugar": null,
        "fecha": null,
        "delito": null,
        "error_message": "No results found for license plate: ABC1234"
    }
    ```
    
    **Search failed (e.g., website down):**
    ```json
    {
        "searched_plate": "ABC1234",
        "search_successful": false,
        "crime_report_number": null,
        "lugar": null,
        "fecha": null,
        "delito": null,
        "error_message": "Service temporarily unavailable due to anti-bot protection"
    }
    ```
    """
    request_id = str(uuid.uuid4())
    client_ip = request.client.host
    
    with RequestLogger(
        "scraper_search", 
        request_id=request_id,
        license_plate=license_plate,
        client_ip=client_ip
    ) as req_logger:
        
        try:
            await check_rate_limit(request)
            
            req_logger.log("Starting complaint search", "info")
            
            from .schemas import ComplaintSearchRequest
            search_request = ComplaintSearchRequest(license_plate=license_plate)
            
            result = await scraper_service.search_by_license_plate(search_request)
            
            req_logger.log(
                "Search completed successfully", 
                "info",
                found_results=result.crime_report_number is not None
            )
            
            return result
            
        except PlateNotFound as e:
            req_logger.log(f"No results found: {str(e)}", "info")
            
            return ComplaintSearchResponse(
                searched_plate=license_plate,
                search_successful=True,
                crime_report_number=None,
                lugar=None,
                fecha=None,
                delito=None,
                error_message=str(e)
            )
            
        except IncapsulaBlockedException as e:
            req_logger.log(f"Incapsula blocking detected: {str(e)}", "warning")
            
            return ComplaintSearchResponse(
                searched_plate=license_plate,
                search_successful=False,
                crime_report_number=None,
                lugar=None,
                fecha=None,
                delito=None,
                error_message="Service temporarily unavailable due to anti-bot protection. Please try again later."
            )
            
        except ScrapingTimeout as e:
            req_logger.log(f"Search timeout: {str(e)}", "warning")
            
            return ComplaintSearchResponse(
                searched_plate=license_plate,
                search_successful=False,
                crime_report_number=None,
                lugar=None,
                fecha=None,
                delito=None,
                error_message="Search operation timed out. The target website may be slow or unavailable."
            )
            
        except ScraperException as e:
            req_logger.log(f"Scraper error: {str(e)}", "error")
            
            return ComplaintSearchResponse(
                searched_plate=license_plate,
                search_successful=False,
                crime_report_number=None,
                lugar=None,
                fecha=None,
                delito=None,
                error_message="Internal scraping error occurred. Please try again later."
            )
            
        except Exception as e:
            req_logger.log(f"Unexpected error: {str(e)}", "error")
            
            return ComplaintSearchResponse(
                searched_plate=license_plate,
                search_successful=False,
                crime_report_number=None,
                lugar=None,
                fecha=None,
                delito=None,
                error_message="An unexpected error occurred. Please try again later."
            )


@router.get("/health", response_model=ScraperHealthResponse)
async def scraper_health_check(
    service_health: Annotated[dict, Depends(ServiceHealth.check_scraper_service)]
):
    """
    Health check endpoint for the scraper service.
    
    Returns the current status of the scraper service, browser availability,
    and other diagnostic information.
    
    **Response Example:**
    ```json
    {
        "status": "healthy",
        "browser_available": true,
        "last_successful_search": "2024-01-15T10:30:00",
        "service_name": "scraper"
    }
    ```
    """
    try:
        health_info = await scraper_service.health_check()
        
        health_info.browser_available = service_health.get("playwright_available", False)
        
        logger.info("Health check performed", extra={
            "status": health_info.status,
            "browser_available": health_info.browser_available
        })
        
        return health_info
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        
        return ScraperHealthResponse(
            status="unhealthy",
            browser_available=False,
            service_name="scraper"
        )
