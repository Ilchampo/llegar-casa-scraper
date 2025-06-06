# LlegarCasa Scrapper

A production-ready FastAPI microservice for extracting crime report data from Ecuador's SIAF (Sistema Integrado de Actuaciones Fiscales) database. This service provides a RESTful API interface for searching license plate information and matching driver names against processed persons in criminal cases.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Technical Stack](#technical-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Monitoring and Observability](#monitoring-and-observability)
- [Technical Challenges](#technical-challenges)
- [Production Considerations](#production-considerations)
- [Development](#development)
- [Contributing](#contributing)

## Architecture Overview

This microservice follows enterprise-grade patterns and practices:

### Core Components

- **FastAPI Application**: High-performance async web framework with automatic OpenAPI documentation
- **Playwright Engine**: Browser automation for JavaScript-heavy website scraping with stealth capabilities
- **Circuit Breaker Pattern**: Resilience mechanism to prevent cascading failures
- **Retry Logic**: Intelligent retry with exponential backoff and jitter
- **Metrics Collection**: Comprehensive monitoring with counters, gauges, and histograms
- **Structured Logging**: JSON-formatted logs with correlation IDs for distributed tracing

### Service Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│   FastAPI App   │────│  SIAF Website   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                    ┌─────────┼─────────┐
                    │         │         │
            ┌───────▼───┐ ┌───▼───┐ ┌───▼──────┐
            │ Metrics   │ │Logging│ │ Circuit  │
            │Collection │ │System │ │ Breaker  │
            └───────────┘ └───────┘ └──────────┘
```

## Features

### Core Functionality
- License plate search in Ecuador's SIAF crime database
- Driver name matching with intelligent algorithms (exact, partial, contains)
- Crime report data extraction (location, date, offense type, processed persons)
- Real-time scraping with Incapsula protection bypass

### Production Features
- **Rate Limiting**: Configurable request throttling per IP address
- **Input Validation**: Comprehensive request validation with Pydantic
- **Error Handling**: Structured error responses with appropriate HTTP status codes
- **Health Checks**: Multi-level health monitoring endpoints
- **Metrics Collection**: Business and technical metrics with Prometheus-compatible format
- **Circuit Breaker**: Automatic failure detection and recovery
- **Retry Logic**: Smart retry with exponential backoff
- **Request Tracing**: Unique request IDs for end-to-end tracking
- **Structured Logging**: JSON logs with contextual information

## Technical Stack

- **Runtime**: Python 3.9+
- **Web Framework**: FastAPI 0.104+
- **Browser Automation**: Playwright (Chromium)
- **Data Validation**: Pydantic 2.0+
- **HTTP Client**: HTTPX (async)
- **Configuration**: Pydantic Settings with environment variable support
- **Logging**: Python's logging module with custom formatters

## Installation

### Prerequisites

- Python 3.9 or higher
- Node.js (for Playwright browser installation)
- 2GB+ RAM (for browser instances)
- Linux/macOS/Windows

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Ilchampo/llegar-casa.git
   cd llegar-casa-scrapper
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

5. **Environment configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Application Settings
APP_NAME=LlegarCasa Scrapper
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=true

# CORS Settings
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3001"]
CORS_ALLOW_CREDENTIALS=true

# Scraper Settings
SCRAPER_HEADLESS_MODE=true
SCRAPER_SAVE_SCREENSHOTS=false
SCRAPER_DEBUG_MODE=false
SCRAPER_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Application environment (development/production) |
| `DEBUG` | `true` | Enable debug mode |
| `SCRAPER_HEADLESS_MODE` | `true` | Run browser in headless mode |
| `SCRAPER_SAVE_SCREENSHOTS` | `false` | Save debug screenshots |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |

## Running the Application

### Development Mode

**Option 1: FastAPI CLI (Recommended for Development)**
```bash
# Simple development server with auto-reload
fastapi dev src/main.py

# With custom host/port
fastapi dev src/main.py --host 0.0.0.0 --port 8000
```

**Option 2: Uvicorn Direct (More Control)**
```bash
# Start with auto-reload and explicit configuration
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# With custom settings
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
```

### Production Mode

**Option 1: FastAPI CLI (Simple Production)**
```bash
# Set production environment
export ENVIRONMENT=production
export DEBUG=false

# Start production server
fastapi run src/main.py
```

**Option 2: Uvicorn Direct (Enterprise Production)**
```bash
# Set production environment
export ENVIRONMENT=production
export DEBUG=false

# Start with multiple workers and explicit configuration
uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --access-log \
  --log-level info
```

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright
RUN playwright install chromium

COPY src/ src/
EXPOSE 8000

# Production: Use uvicorn for explicit control
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Which Approach to Choose?

| Scenario | Recommended Command | Reason |
|----------|-------------------|---------|
| **Local Development** | `fastapi dev` | Simple, user-friendly, sensible defaults |
| **Production (Simple)** | `fastapi run` | Easy production deployment |
| **Production (Enterprise)** | `uvicorn` | Full control, monitoring, scaling |
| **Docker/Containers** | `uvicorn` | Industry standard, better integration |
| **Kubernetes/Orchestration** | `uvicorn` | Explicit configuration, monitoring |

## Troubleshooting

### Common Issues

#### 1. Environment Variable Validation Errors

**Error**: 
```
ValidationError: 1 validation error for Settings
ENVIRONMENT
  Input should be 'development', 'staging' or 'production' [type=enum, input_value='local', input_type=str]
```

**Solution**: 
- Check if you have `ENVIRONMENT` set in your shell: `echo $ENVIRONMENT`
- If set to invalid value, unset it: `unset ENVIRONMENT`
- Ensure `.env` file has valid value: `ENVIRONMENT=development` or `ENVIRONMENT=production`

#### 2. Module Import Errors

**Error**: 
```
ModuleNotFoundError: No module named 'logging_config'
```

**Solution**: 
- Ensure you're running the application from the project root directory
- Use the correct import syntax: `uvicorn src.main:app` (not `uvicorn main:app`)
- Verify virtual environment is activated: `which python` should show `.venv/bin/python`

#### 3. Configuration Conflicts

**Error**: 
```
Extra inputs are not permitted [type=extra_forbidden, input_value='...', input_type=str]
```

**Solution**: 
- Check for conflicting environment variables in your shell
- Ensure `.env` file variables match the expected configuration schema
- Use `env | grep SCRAPER_` to check for unexpected environment variables

#### 4. Uvicorn Startup Issues

**Symptoms**: 
- Application starts but immediately crashes
- Endless error loops during startup
- Import errors in uvicorn output

**Solutions**: 
1. **Test imports first**:
   ```bash
   python -c "from src.main import app; print('Import successful')"
   ```

2. **Check environment variables**:
   ```bash
   # Unset problematic variables
   unset ENVIRONMENT
   
   # Verify .env file
   cat .env | grep ENVIRONMENT
   ```

3. **Use absolute module paths**:
   ```bash
   # Correct way
   uvicorn src.main:app --reload
   
   # Incorrect way (will cause import errors)
   cd src && uvicorn main:app --reload
   ```

#### 5. Browser Installation Issues

**Error**: 
```
Error: Browser not found
```

**Solution**: 
```bash
# Install browsers
playwright install chromium

# If permission issues on Linux
sudo playwright install-deps chromium
```

#### 6. Port Already in Use

**Error**: 
```
OSError: [Errno 48] Address already in use
```

**Solution**: 
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process (replace PID)
kill -9 <PID>

# Or use different port
uvicorn src.main:app --port 8001
```

### Quick Health Check

After starting the application, verify everything is working:

```bash
# 1. Test basic import
python -c "from src.main import app; print('✓ Import successful')"

# 2. Start application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &

# 3. Wait for startup and test endpoints
sleep 5
curl http://localhost:8000/health
curl http://localhost:8000/monitoring/health/system

# 4. Test scraper functionality (optional)
curl "http://localhost:8000/scraper/complaints?license_plate=PCJ8619&driver_name=JOSE"
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs**: Look in `src/logs/` directory for detailed error information
2. **Enable debug mode**: Set `DEBUG=true` in `.env` file
3. **Verify environment**: Run `python --version` and `pip list` to check dependencies
4. **Test step by step**: Start with basic imports, then configuration, then full application

## API Documentation

### Interactive Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Core Endpoints

#### Search Complaints
```http
GET /scraper/complaints?license_plate=PCJ8619&driver_name=JOSE%20TUQUEREZ
```

**Parameters**:
- `license_plate` (string): Vehicle license plate (6-7 characters)
- `driver_name` (string): Driver name to match (2-100 characters)

**Response**:
```json
{
  "crime_report_number": "100301816010030",
  "lugar": "IMBABURA - COTACACHI",
  "fecha": "2016-01-27",
  "delito": "RECEPTACIÓN(3575)",
  "procesados": ["TUQUEREZ JOSE FAUSTO", "SANCHEZ ALDAZ JOSE ANTONIO"],
  "name_match_found": true,
  "search_successful": true,
  "searched_plate": "PCJ8619",
  "searched_driver": "JOSE TUQUEREZ"
}
```

#### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "llegar-casa-scrapper",
  "version": "1.0.0",
  "environment": "development"
}
```

## Monitoring and Observability

### Health Endpoints

- `/monitoring/health/system` - Basic system health
- `/monitoring/health/detailed` - Comprehensive component health
- `/monitoring/metrics` - Application metrics summary
- `/monitoring/circuit-breakers` - Circuit breaker status
- `/monitoring/performance` - Performance metrics
- `/monitoring/business` - Business outcome metrics

### Metrics

The service collects comprehensive metrics:

**Request Metrics**:
- Total HTTP requests
- Request duration histograms
- Error rates by status code

**Business Metrics**:
- License plates searched
- Name matches found
- Incapsula blocks encountered

**Technical Metrics**:
- Circuit breaker operations
- Retry attempts
- Active browser instances

### Logging

Logs are written to:
- `src/logs/app.log` - Application logs
- `src/logs/error.log` - Error logs
- `src/logs/scraper.log` - Scraper-specific logs

Log format:
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "scraper.service",
  "message": "Search completed successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "license_plate": "PCJ8619",
  "duration_ms": 15000
}
```

## Technical Challenges

### 1. Incapsula Protection Bypass

**Challenge**: The SIAF website uses Incapsula anti-bot protection that blocks automated requests.

**Solution**: 
- Stealth browser configuration with realistic headers
- JavaScript injection to remove automation indicators
- Random delays and human-like behavior simulation
- User-agent rotation and viewport randomization

### 2. Dynamic Content Extraction

**Challenge**: Crime report data is dynamically generated and lacks consistent CSS selectors.

**Solution**:
- Robust regex patterns for data extraction
- Multiple fallback extraction strategies
- Content validation before processing
- Error handling for malformed data

### 3. Service Reliability

**Challenge**: External dependencies can fail, causing cascading failures.

**Solution**:
- Circuit breaker pattern with configurable thresholds
- Exponential backoff retry logic with jitter
- Graceful degradation under load
- Comprehensive health monitoring

### 4. Performance Optimization

**Challenge**: Browser automation is resource-intensive and slow.

**Solution**:
- Fresh browser instances per request (prevents memory leaks)
- Optimized browser launch arguments
- Intelligent timeouts and resource management
- Metrics-driven performance monitoring

### 5. Production Observability

**Challenge**: Debugging issues in production without proper monitoring.

**Solution**:
- Structured logging with correlation IDs
- Comprehensive metrics collection
- Multi-level health checks
- Request tracing across service boundaries

## Production Considerations

### Performance

- **Response Time**: Typically 10-25 seconds per search (limited by target website)
- **Throughput**: Recommended max 10 requests per hour per instance
- **Memory Usage**: ~200MB base + ~100MB per active browser instance
- **CPU Usage**: High during browser operations, low during idle

### Scaling

- **Horizontal Scaling**: Deploy multiple instances behind a load balancer
- **Rate Limiting**: Implement at load balancer level for global limits
- **Resource Planning**: 1 CPU core and 1GB RAM per instance recommended
- **Browser Management**: Consider browser pools for high-volume scenarios

### Security

- **Input Sanitization**: All inputs validated with Pydantic
- **Rate Limiting**: Configurable per-IP limits
- **Error Masking**: Generic error messages in production
- **Access Control**: Implement authentication for production deployment

### Monitoring

- **Health Checks**: Configure load balancer health checks
- **Alerting**: Set up alerts for circuit breaker opens and error rates
- **Logging**: Ship logs to centralized logging system
- **Metrics**: Export metrics to monitoring system (Prometheus/Grafana)

### Legal Compliance

- **Rate Limiting**: Respect target website resources
- **User Agent**: Use descriptive, honest user agent strings
- **Robots.txt**: Comply with website policies
- **Data Usage**: Follow data protection regulations

## Development

### Project Structure

```
src/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── constants.py           # Application constants
├── logging_config.py      # Logging configuration
├── circuit_breaker.py     # Circuit breaker implementation
├── retry_handler.py       # Retry logic
├── metrics.py             # Metrics collection
├── monitoring.py          # Monitoring endpoints
└── scraper/
    ├── __init__.py
    ├── router.py           # FastAPI routes
    ├── service.py          # Business logic
    ├── schemas.py          # Pydantic models
    ├── exceptions.py       # Custom exceptions
    ├── constants.py        # Scraper constants
    ├── config.py           # Scraper configuration
    └── dependencies.py     # FastAPI dependencies
```

### Code Quality

- **Type Hints**: Full type annotation coverage
- **Docstrings**: Comprehensive API documentation
- **Error Handling**: Structured exception hierarchy
- **Testing**: Unit and integration test coverage
- **Linting**: Code style enforcement

### Testing

```bash
# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Make changes with proper tests
5. Ensure code quality checks pass
6. Submit a pull request

### Code Standards

- Follow PEP 8 style guidelines
- Add type hints for all functions
- Write comprehensive docstrings
- Include unit tests for new features
- Update documentation for API changes

### Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Add entries to CHANGELOG.md
4. Request review from maintainers
5. Address feedback and merge

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For technical support or questions:

- Create an issue in the repository
- Review existing documentation
- Check monitoring endpoints for service status

## Changelog

### Version 1.0.0
- Initial release with core scraping functionality
- FastAPI-based REST API
- Playwright browser automation
- Circuit breaker pattern implementation
- Comprehensive monitoring and metrics
- Production-ready logging and observability
- Rate limiting and input validation
- Multi-level health checks
