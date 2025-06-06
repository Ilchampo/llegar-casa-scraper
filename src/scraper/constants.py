"""Scraper module constants."""

SIAF_BASE_URL = "https://www.gestiondefiscalias.gob.ec"
SIAF_INDEX_URL = f"{SIAF_BASE_URL}/siaf/informacion/web/noticiasdelito/index.php"
SIAF_SEARCH_URL = f"{SIAF_BASE_URL}/siaf/comunes/noticiasdelito/info_mod.php"

SEARCH_INPUT_SELECTOR = 'input[name="pwd"]'
SEARCH_BUTTON_SELECTOR = 'input[value="Buscar Denuncia"]'
RESULTS_CONTAINER_SELECTOR = '#resultados'

CRIME_INFO_TABLE_SELECTOR = 'table tbody tr'
SUJETOS_TABLE_SELECTOR = 'table:has(th:contains("SUJETOS")) tbody tr'
VEHICULOS_TABLE_SELECTOR = 'table:has(th:contains("VEHICULOS")) tbody tr'

BROWSER_TIMEOUT = 30000  # 30 seconds
PAGE_LOAD_TIMEOUT = 20000  # 20 seconds
SEARCH_TIMEOUT = 15000  # 15 seconds

MIN_DELAY = 2  # seconds
MAX_DELAY = 5  # seconds

class ErrorMessages:
    BROWSER_FAILED = "Failed to launch browser"
    PAGE_LOAD_FAILED = "Failed to load search page"
    SEARCH_FAILED = "Failed to perform search"
    NO_RESULTS = "No results found for the given license plate"
    EXTRACTION_FAILED = "Failed to extract data from results"
    INVALID_PLATE = "Invalid license plate format"
    INCAPSULA_BLOCKED = "Request blocked by Incapsula protection"

class ProcessingStatus:
    PROCESADO = "PROCESADO"
    DENUNCIANTE = "DENUNCIANTE"
    TESTIGO = "TESTIGO"
