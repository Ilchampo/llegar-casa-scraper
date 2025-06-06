"""Scraper service module - Core business logic."""

import asyncio
import random
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import quote

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from .schemas import ComplaintSearchRequest, ComplaintSearchResponse, ScraperHealthResponse
from .exceptions import (
    ScraperException, PageLoadException, PlateNotFound,
    ScrapingTimeout, DataExtractionException, IncapsulaBlockedException, SearchException
)
from .constants import (
    SIAF_INDEX_URL, SIAF_SEARCH_URL, ErrorMessages, ProcessingStatus,
    MIN_DELAY, MAX_DELAY, PAGE_LOAD_TIMEOUT
)
from .config import scraper_settings
from ..logging_config import get_logger
from ..circuit_breaker import get_circuit_breaker, CircuitBreakerConfig, CircuitBreakerOpenException
from ..retry_handler import get_retry_handler, RetryConfig
from ..metrics import (
    metrics, inc_searches, observe_search_duration, set_active_searches, 
    set_browser_instances
)


class ScraperService:
    """Service class for handling web scraping operations."""
    
    def __init__(self):
        """Initialize the scraper service."""
        self.last_successful_search: Optional[datetime] = None
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.logger = get_logger("scraper.service")
        
        self.circuit_breaker = get_circuit_breaker(
            "siaf_scraper",
            CircuitBreakerConfig(
                failure_threshold=3,      # Open after 3 failures
                recovery_timeout=120,     # Wait 2 minutes before trying again
                success_threshold=2,      # Close after 2 successes
                timeout=45               # 45 second timeout per operation
            )
        )
        
        scraping_retry_config = RetryConfig(
            max_attempts=3,
            base_delay=3.0,              # Start with 3 second delay
            max_delay=30.0,              # Max 30 second delay
            exponential_base=2.0,
            retry_on=[
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError,
                PlaywrightTimeoutError,
                SearchException,         # Retry on search failures
                PageLoadException,       # Retry on page load issues
                OSError                  # Network errors
            ],
            stop_on=[
                PlateNotFound,           # Don't retry if plate truly not found
                DataExtractionException, # Don't retry extraction errors
                ValueError,
                TypeError
            ]
        )
        
        self.retry_handler = get_retry_handler("scraper_operations", scraping_retry_config)
        
        self.logger.info("ScraperService initialized with circuit breaker and retry logic")
    
    async def search_by_license_plate(
        self, 
        request: ComplaintSearchRequest
    ) -> ComplaintSearchResponse:
        """
        Search for crime complaints by license plate with circuit breaker and retry logic.
        """
        start_time = time.time()
        
        set_active_searches(1)
        
        try:
            self.logger.info(
                "Starting license plate search",
                extra={"license_plate": request.license_plate}
            )
            
            inc_searches(labels={"license_plate": request.license_plate})
            metrics.get_counter("license_plates_searched").inc()
            
            result = await self._search_with_resilience(request)
            
            inc_searches(success=True, labels={"license_plate": request.license_plate})
            self.last_successful_search = datetime.now()
            
            duration = time.time() - start_time
            observe_search_duration(duration)
            
            self.logger.info(
                "License plate search completed successfully",
                extra={
                    "license_plate": request.license_plate,
                    "found_results": result.crime_report_number is not None,
                    "duration_seconds": round(duration, 2),
                    "crime_report_number": result.crime_report_number
                }
            )
            
            return result
            
        except CircuitBreakerOpenException as e:
            inc_searches(success=False, labels={"license_plate": request.license_plate, "error": "circuit_open"})
            metrics.get_counter("circuit_breaker_opens").inc()
            
            self.logger.error(
                "Search blocked by circuit breaker",
                extra={
                    "license_plate": request.license_plate,
                    "circuit_breaker_state": "open"
                }
            )
            
            raise ScraperException("Service temporarily unavailable due to repeated failures")
            
        except PlateNotFound:
            inc_searches(success=True, labels={"license_plate": request.license_plate})
            duration = time.time() - start_time
            observe_search_duration(duration)
            raise
            
        except Exception as e:
            inc_searches(success=False, labels={"license_plate": request.license_plate})
            duration = time.time() - start_time
            observe_search_duration(duration)
            
            self.logger.error(
                "License plate search failed",
                extra={
                    "license_plate": request.license_plate,
                    "error": str(e),
                    "duration_seconds": round(duration, 2)
                },
                exc_info=True
            )
            raise
            
        finally:
            set_active_searches(0)
    
    async def _search_with_resilience(self, request: ComplaintSearchRequest) -> ComplaintSearchResponse:
        """
        Perform search with circuit breaker and retry logic.
        """
        async def _search_operation():
            return await self._perform_core_search(request)
        
        return await self.circuit_breaker.call(
            self.retry_handler.execute,
            _search_operation
        )
    
    async def _perform_core_search(self, request: ComplaintSearchRequest) -> ComplaintSearchResponse:
        """
        Core search logic wrapped by resilience patterns.
        """
        search_results = await self._perform_search(request.license_plate)
        
        if not search_results:
            self.logger.info(
                "No search results found",
                extra={"license_plate": request.license_plate}
            )
            raise PlateNotFound(f"No results found for license plate: {request.license_plate}")
        
        extracted_data = await self._extract_data(search_results)
        
        return ComplaintSearchResponse(
            searched_plate=request.license_plate,
            search_successful=True,
            crime_report_number=extracted_data.get("crime_report_number"),
            lugar=extracted_data.get("lugar"),
            fecha=extracted_data.get("fecha"),
            delito=extracted_data.get("delito"),
            error_message=None
        )
    
    async def health_check(self) -> ScraperHealthResponse:
        """
        Perform health check for the scraper service.
        """
        try:
            self.logger.debug("Performing health check")
            
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            await browser.close()
            await playwright.stop()
            
            cb_status = self.circuit_breaker.get_status()
            
            self.logger.info("Health check completed successfully")
            
            return ScraperHealthResponse(
                status="healthy",
                browser_available=True,
                last_successful_search=self.last_successful_search,
                service_name="scraper",
                circuit_breaker_state=cb_status["state"],
                retry_stats=self.retry_handler.get_stats()
            )
            
        except Exception as e:
            self.logger.error(
                "Health check failed",
                extra={"error": str(e)},
                exc_info=True
            )
            
            return ScraperHealthResponse(
                status="unhealthy",
                browser_available=False,
                last_successful_search=self.last_successful_search,
                service_name="scraper",
                circuit_breaker_state="unknown"
            )
    
    async def _perform_search(self, license_plate: str) -> Optional[str]:
        """
        Perform the actual search on the SIAF website with fresh browser instance.
        """
        playwright = None
        browser = None
        context = None
        page = None
        
        search_start = datetime.now()
        
        try:
            self.logger.debug(
                "Starting browser setup for search",
                extra={"license_plate": license_plate}
            )
            
            set_browser_instances(1)
            
            playwright = await async_playwright().start()
            
            browser = await playwright.chromium.launch(
                headless=scraper_settings.HEADLESS_MODE,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-ipc-flooding-protection',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-features=TranslateUI',
                    '--disable-web-security',
                    '--user-agent=' + scraper_settings.USER_AGENT,
                ]
            )
            
            context = await browser.new_context(
                user_agent=scraper_settings.USER_AGENT,
                viewport={'width': 1366, 'height': 768},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                }
            )
            
            page = await context.new_page()
            
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                delete navigator.__proto__.webdriver;
            """)
            
            self.logger.debug(
                "Loading index page",
                extra={
                    "license_plate": license_plate,
                    "url": SIAF_INDEX_URL
                }
            )
            
            await page.goto(SIAF_INDEX_URL, timeout=PAGE_LOAD_TIMEOUT, wait_until="networkidle")
            
            if scraper_settings.SAVE_SCREENSHOTS:
                await page.screenshot(path="debug_index.png")
                self.logger.debug("Screenshot saved: debug_index.png")
            
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            self.logger.debug(
                f"Applying random delay",
                extra={
                    "license_plate": license_plate,
                    "delay_seconds": round(delay, 2)
                }
            )
            await asyncio.sleep(delay)
            
            if await self._check_incapsula_block(page):
                self.logger.warning(
                    "Incapsula blocking detected, attempting retry",
                    extra={"license_plate": license_plate}
                )
                
                metrics.get_counter("incapsula_blocks").inc()
                
                await asyncio.sleep(random.uniform(5, 10))
                
                await page.reload(wait_until="networkidle")
                await asyncio.sleep(random.uniform(2, 4))
                
                if await self._check_incapsula_block(page):
                    self.logger.error(
                        "Incapsula blocking persisted after retry",
                        extra={"license_plate": license_plate}
                    )
                    raise IncapsulaBlockedException(ErrorMessages.INCAPSULA_BLOCKED)
            
            search_param = self._serialize_php_array([license_plate])
            search_url = f"{SIAF_SEARCH_URL}?businfo={quote(search_param)}"
            
            self.logger.debug(
                "Navigating to search results",
                extra={
                    "license_plate": license_plate,
                    "search_url": search_url,
                    "search_param": search_param
                }
            )
            
            response = await page.goto(search_url, timeout=PAGE_LOAD_TIMEOUT)
            
            if not response or response.status != 200:
                self.logger.error(
                    "Search request failed",
                    extra={
                        "license_plate": license_plate,
                        "status_code": response.status if response else None
                    }
                )
                raise SearchException(f"Search request failed with status: {response.status if response else 'None'}")
            
            await page.wait_for_timeout(3000)
            
            if scraper_settings.SAVE_SCREENSHOTS:
                await page.screenshot(path="debug_results.png")
                self.logger.debug("Screenshot saved: debug_results.png")
            
            content = await page.content()
            
            search_duration = int((datetime.now() - search_start).total_seconds() * 1000)
            
            self.logger.debug(
                "Search response received",
                extra={
                    "license_plate": license_plate,
                    "response_length": len(content),
                    "search_duration_ms": search_duration
                }
            )
            
            if "NOTICIA DEL DELITO" not in content:
                self.logger.info(
                    "No crime reports found in response",
                    extra={"license_plate": license_plate}
                )
                return None
            
            self.logger.info(
                "Crime report data found in response",
                extra={"license_plate": license_plate}
            )
            
            return content
            
        except PlaywrightTimeoutError as e:
            self.logger.error(
                "Playwright timeout during search",
                extra={
                    "license_plate": license_plate,
                    "error": str(e)
                },
                exc_info=True
            )
            raise ScrapingTimeout(f"Search operation timed out: {str(e)}")
            
        except IncapsulaBlockedException:
            raise
            
        except Exception as e:
            self.logger.error(
                "Search operation failed",
                extra={
                    "license_plate": license_plate,
                    "error": str(e)
                },
                exc_info=True
            )
            raise SearchException(f"{ErrorMessages.SEARCH_FAILED}: {str(e)}")
            
        finally:
            try:
                if page:
                    await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
                    
                set_browser_instances(0)
                    
                self.logger.debug(
                    "Browser cleanup completed",
                    extra={"license_plate": license_plate}
                )
            except Exception as e:
                self.logger.warning(
                    "Error during browser cleanup",
                    extra={
                        "license_plate": license_plate,
                        "error": str(e)
                    }
                )
    
    async def _extract_data(self, html_content: str) -> Dict[str, Any]:
        """
        Extract crime report data from the search results HTML.
        """
        try:
            data = {
                "crime_report_number": None,
                "lugar": None,
                "fecha": None,
                "delito": None
            }
            
            crime_number_match = re.search(r'NOTICIA DEL DELITO Nro\. ([\d]+)', html_content)
            if crime_number_match:
                data["crime_report_number"] = crime_number_match.group(1)
            
            lugar_patterns = [
                r'<td[^>]*style="[^"]*font-weight:\s*bold[^"]*"[^>]*>LUGAR</td>\s*<td[^>]*>([^<]+)</td>',
                r'<td[^>]*>LUGAR</td>\s*<td[^>]*>([^<]+)</td>',
                r'LUGAR.*?<td[^>]*>([^<]+)</td>'
            ]
            
            for pattern in lugar_patterns:
                lugar_match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if lugar_match:
                    data["lugar"] = lugar_match.group(1).strip()
                    break
            
            fecha_patterns = [
                r'<td[^>]*style="[^"]*font-weight:\s*bold[^"]*"[^>]*>FECHA</td>\s*<td[^>]*>([^<]+)</td>',
                r'<td[^>]*>FECHA</td>\s*<td[^>]*>([^<]+)</td>',
                r'FECHA.*?<td[^>]*>([^<]+)</td>'
            ]
            
            for pattern in fecha_patterns:
                fecha_match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if fecha_match:
                    data["fecha"] = fecha_match.group(1).strip()
                    break
            
            delito_patterns = [
                r'<td[^>]*style="[^"]*font-weight:\s*bold[^"]*"[^>]*>DELITO:</td>\s*<td[^>]*>([^<]+)</td>',
                r'<td[^>]*>DELITO:</td>\s*<td[^>]*>([^<]+)</td>',
                r'DELITO:.*?<td[^>]*>([^<]+)</td>'
            ]
            
            for pattern in delito_patterns:
                delito_match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if delito_match:
                    data["delito"] = delito_match.group(1).strip()
                    break
            
            if scraper_settings.DEBUG_MODE:
                print(f"Extracted data: {data}")
            
            return data
            
        except Exception as e:
            raise DataExtractionException(f"{ErrorMessages.EXTRACTION_FAILED}: {str(e)}")
    
    def _serialize_php_array(self, items: list[str]) -> str:
        """
        Create PHP serialized array format as expected by the SIAF system.
        Format: a:1:{i:0;s:7:"PCJ8619";}
        """
        result = f'a:{len(items)}:{{'
        
        for i, item in enumerate(items):
            result += f'i:{i};s:{len(item)}:"{item}";'
        
        result += '}'
        return result
    
    async def _check_incapsula_block(self, page: Page) -> bool:
        """
        Check if the page was blocked by Incapsula protection.
        """
        try:
            content = await page.content()
            
            incapsula_indicators = [
                'incapsula',
                'request blocked',
                'access denied',
                'imperva',
                '_incap_ses_'
            ]
            
            content_lower = content.lower()
            return any(indicator in content_lower for indicator in incapsula_indicators)
            
        except Exception:
            return False
    
    async def close(self):
        """
        Clean up browser resources.
        """
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
        except Exception:
            pass
