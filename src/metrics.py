"""Metrics collection and monitoring for the scraper application."""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

from .logging_config import get_logger


@dataclass
class MetricPoint:
    """A single metric data point."""
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HistogramBucket:
    """Histogram bucket for latency measurements."""
    upper_bound: float
    count: int = 0


class Counter:
    """Thread-safe counter metric."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0
        self._lock = Lock()
        self._labels_values: Dict[str, int] = {}
    
    def inc(self, value: float = 1, labels: Dict[str, str] = None):
        """Increment counter by value."""
        with self._lock:
            self._value += value
            
            if labels:
                labels_key = self._labels_to_key(labels)
                self._labels_values[labels_key] = self._labels_values.get(labels_key, 0) + value
    
    def get_value(self, labels: Dict[str, str] = None) -> float:
        """Get counter value."""
        with self._lock:
            if labels:
                labels_key = self._labels_to_key(labels)
                return self._labels_values.get(labels_key, 0)
            return self._value
    
    def get_all_values(self) -> Dict[str, float]:
        """Get all label combinations and their values."""
        with self._lock:
            result = {"total": self._value}
            result.update(self._labels_values)
            return result
    
    @staticmethod
    def _labels_to_key(labels: Dict[str, str]) -> str:
        """Convert labels dict to string key."""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


class Gauge:
    """Thread-safe gauge metric."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0
        self._lock = Lock()
        self._labels_values: Dict[str, float] = {}
    
    def set(self, value: float, labels: Dict[str, str] = None):
        """Set gauge value."""
        with self._lock:
            self._value = value
            
            if labels:
                labels_key = Counter._labels_to_key(labels)
                self._labels_values[labels_key] = value
    
    def inc(self, value: float = 1, labels: Dict[str, str] = None):
        """Increment gauge by value."""
        with self._lock:
            self._value += value
            
            if labels:
                labels_key = Counter._labels_to_key(labels)
                self._labels_values[labels_key] = self._labels_values.get(labels_key, 0) + value
    
    def dec(self, value: float = 1, labels: Dict[str, str] = None):
        """Decrement gauge by value."""
        self.inc(-value, labels)
    
    def get_value(self, labels: Dict[str, str] = None) -> float:
        """Get gauge value."""
        with self._lock:
            if labels:
                labels_key = Counter._labels_to_key(labels)
                return self._labels_values.get(labels_key, 0)
            return self._value


class Histogram:
    """Histogram metric for tracking distributions (like response times)."""
    
    def __init__(self, name: str, description: str = "", buckets: List[float] = None):
        self.name = name
        self.description = description
        
        self.buckets = [HistogramBucket(upper_bound) for upper_bound in sorted(buckets)]
        self._sum = 0
        self._count = 0
        self._lock = Lock()
    
    def observe(self, value: float):
        """Record an observation."""
        with self._lock:
            self._sum += value
            self._count += 1
            
            for bucket in self.buckets:
                if value <= bucket.upper_bound:
                    bucket.count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get histogram statistics."""
        with self._lock:
            return {
                "count": self._count,
                "sum": self._sum,
                "avg": self._sum / self._count if self._count > 0 else 0,
                "buckets": [
                    {"upper_bound": b.upper_bound, "count": b.count}
                    for b in self.buckets
                ]
            }


class SlidingWindow:
    """Sliding window for time-based metrics."""
    
    def __init__(self, window_size: int = 300):
        self.window_size = window_size
        self.data: deque = deque()
        self._lock = Lock()
    
    def add(self, value: float, timestamp: datetime = None):
        """Add value to sliding window."""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            self.data.append((timestamp, value))
            self._cleanup()
    
    def get_values(self, since: datetime = None) -> List[float]:
        """Get values from the window."""
        with self._lock:
            return [value for timestamp, value in self.data if timestamp >= since]
    
    def get_stats(self) -> Dict[str, float]:
        """Get statistics for the current window."""
        values = self.get_values()
        
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values)
        }
    
    def _cleanup(self):
        """Remove old data points."""
        cutoff = datetime.now() - timedelta(seconds=self.window_size)
        while self.data and self.data[0][0] < cutoff:
            self.data.popleft()


class MetricsCollector:
    """Central metrics collector."""
    
    def __init__(self):
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.sliding_windows: Dict[str, SlidingWindow] = {}
        self.logger = get_logger("metrics")
        self._lock = Lock()
        
        self._init_core_metrics()
    
    def _init_core_metrics(self):
        """Initialize core application metrics."""
        self.register_counter("http_requests_total", "Total HTTP requests")
        self.register_counter("http_requests_errors", "HTTP request errors")
        self.register_histogram("http_request_duration", "HTTP request duration in seconds")
        
        self.register_counter("scraper_searches_total", "Total scraper searches")
        self.register_counter("scraper_searches_successful", "Successful scraper searches")
        self.register_counter("scraper_searches_failed", "Failed scraper searches")
        self.register_histogram("scraper_search_duration", "Scraper search duration in seconds")
        self.register_gauge("scraper_active_searches", "Currently active scraper searches")
        
        self.register_counter("license_plates_searched", "Total license plates searched")
        self.register_counter("name_matches_found", "Total name matches found")
        self.register_counter("incapsula_blocks", "Total Incapsula blocks encountered")
        
        self.register_counter("circuit_breaker_opens", "Circuit breaker opens")
        self.register_counter("circuit_breaker_calls", "Circuit breaker calls")
        
        self.register_counter("retry_attempts", "Total retry attempts")
        self.register_histogram("retry_delay", "Retry delay in seconds")
        
        self.register_gauge("browser_instances", "Active browser instances")
        
        self.logger.info("Core metrics initialized")
    
    def register_counter(self, name: str, description: str = "") -> Counter:
        """Register a new counter metric."""
        with self._lock:
            if name not in self.counters:
                self.counters[name] = Counter(name, description)
            return self.counters[name]
    
    def register_gauge(self, name: str, description: str = "") -> Gauge:
        """Register a new gauge metric."""
        with self._lock:
            if name not in self.gauges:
                self.gauges[name] = Gauge(name, description)
            return self.gauges[name]
    
    def register_histogram(self, name: str, description: str = "", buckets: List[float] = None) -> Histogram:
        """Register a new histogram metric."""
        with self._lock:
            if buckets is None:
                buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

            if name not in self.histograms:
                self.histograms[name] = Histogram(name, description, buckets)
            return self.histograms[name]
    
    def register_sliding_window(self, name: str, window_size: int = 300) -> SlidingWindow:
        """Register a new sliding window metric."""
        with self._lock:
            if name not in self.sliding_windows:
                self.sliding_windows[name] = SlidingWindow(window_size)
            return self.sliding_windows[name]
    
    def get_counter(self, name: str) -> Optional[Counter]:
        """Get counter by name."""
        return self.counters.get(name)
    
    def get_gauge(self, name: str) -> Optional[Gauge]:
        """Get gauge by name."""
        return self.gauges.get(name)
    
    def get_histogram(self, name: str) -> Optional[Histogram]:
        """Get histogram by name."""
        return self.histograms.get(name)
    
    def get_sliding_window(self, name: str) -> Optional[SlidingWindow]:
        """Get sliding window by name."""
        return self.sliding_windows.get(name)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics data."""
        with self._lock:
            result = {
                "timestamp": datetime.now().isoformat(),
                "counters": {},
                "gauges": {},
                "histograms": {},
                "sliding_windows": {}
            }
            
            for name, counter in self.counters.items():
                result["counters"][name] = {
                    "description": counter.description,
                    "values": counter.get_all_values()
                }
            
            for name, gauge in self.gauges.items():
                result["gauges"][name] = {
                    "description": gauge.description,
                    "value": gauge.get_value()
                }
            
            for name, histogram in self.histograms.items():
                result["histograms"][name] = {
                    "description": histogram.description,
                    "stats": histogram.get_stats()
                }
            
            for name, window in self.sliding_windows.items():
                result["sliding_windows"][name] = {
                    "stats": window.get_stats()
                }
            
            return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of key metrics."""
        now = datetime.now()
        
        total_requests = self.get_counter("http_requests_total").get_value()
        error_requests = self.get_counter("http_requests_errors").get_value()
        total_searches = self.get_counter("scraper_searches_total").get_value()
        successful_searches = self.get_counter("scraper_searches_successful").get_value()

        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
        success_rate = (successful_searches / total_searches * 100) if total_searches > 0 else 0
        
        response_time_stats = self.get_histogram("http_request_duration").get_stats()
        search_time_stats = self.get_histogram("scraper_search_duration").get_stats()
        
        return {
            "timestamp": now.isoformat(),
            "overview": {
                "total_requests": total_requests,
                "error_rate_percent": round(error_rate, 2),
                "total_searches": total_searches,
                "search_success_rate_percent": round(success_rate, 2),
                "active_searches": self.get_gauge("scraper_active_searches").get_value(),
                "active_browsers": self.get_gauge("browser_instances").get_value()
            },
            "performance": {
                "avg_response_time_seconds": round(response_time_stats.get("avg", 0), 3),
                "avg_search_time_seconds": round(search_time_stats.get("avg", 0), 3),
                "total_circuit_breaker_opens": self.get_counter("circuit_breaker_opens").get_value(),
                "total_retry_attempts": self.get_counter("retry_attempts").get_value()
            },
            "business_metrics": {
                "license_plates_searched": self.get_counter("license_plates_searched").get_value(),
                "name_matches_found": self.get_counter("name_matches_found").get_value(),
                "incapsula_blocks": self.get_counter("incapsula_blocks").get_value()
            }
        }


metrics = MetricsCollector()


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, histogram: Histogram):
        self.histogram = histogram
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.histogram.observe(duration)


def timer(histogram_name: str) -> TimerContext:
    """Create a timer context for measuring durations."""
    histogram = metrics.get_histogram(histogram_name)
    if not histogram:
        histogram = metrics.register_histogram(histogram_name, f"Duration for {histogram_name}")
    return TimerContext(histogram)


def inc_requests(labels: Dict[str, str] = None):
    """Increment HTTP requests counter."""
    metrics.get_counter("http_requests_total").inc(labels=labels)


def inc_errors(labels: Dict[str, str] = None):
    """Increment HTTP errors counter."""
    metrics.get_counter("http_requests_errors").inc(labels=labels)


def observe_request_duration(duration: float):
    """Record HTTP request duration."""
    metrics.get_histogram("http_request_duration").observe(duration)


def inc_searches(success: bool = None, labels: Dict[str, str] = None):
    """Increment search counters."""
    metrics.get_counter("scraper_searches_total").inc(labels=labels)
    if success is True:
        metrics.get_counter("scraper_searches_successful").inc(labels=labels)
    elif success is False:
        metrics.get_counter("scraper_searches_failed").inc(labels=labels)


def observe_search_duration(duration: float):
    """Record search duration."""
    metrics.get_histogram("scraper_search_duration").observe(duration)


def set_active_searches(count: int):
    """Set number of active searches."""
    metrics.get_gauge("scraper_active_searches").set(count)


def set_browser_instances(count: int):
    """Set number of browser instances."""
    metrics.get_gauge("browser_instances").set(count) 