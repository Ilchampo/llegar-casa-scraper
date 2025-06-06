"""Scraper module custom exceptions."""


class ScraperException(Exception):
    """Base exception for scraper-related errors."""
    pass


class BrowserException(ScraperException):
    """Exception raised when browser operations fail."""
    pass


class PageLoadException(ScraperException):
    """Exception raised when page loading fails."""
    pass


class PlateNotFound(ScraperException):
    """Exception raised when no results are found for a license plate."""
    pass


class ScrapingTimeout(ScraperException):
    """Exception raised when scraping operations timeout."""
    pass


class DataExtractionException(ScraperException):
    """Exception raised when data extraction from page fails."""
    pass


class IncapsulaBlockedException(ScraperException):
    """Exception raised when request is blocked by Incapsula protection."""
    pass


class InvalidPlateFormat(ScraperException):
    """Exception raised when license plate format is invalid."""
    pass


class SearchException(ScraperException):
    """Exception raised when search operation fails."""
    pass
