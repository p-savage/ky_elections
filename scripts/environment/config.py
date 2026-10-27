from pathlib import Path

MANIFEST_FILE_NAME = 'ky_sboe_manifest.csv'
MANIFEST_FIELDNAMES = [
    "is_current",
    "file_name",
    "file_url",
    "source_url",
    "date_accessed",
    "filetype",
    "extraction_paradigm",
    "file_byte_size",
    "file_content_hash",
]
ROOT_URL = 'https://elect.ky.gov/results/Pages/default.aspx'
HEADER = {
    'User-Agent': 
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
    'Version/18.6 Safari/605.1.15'
    }
TIMEOUT = 10.00
MAX_TRIES = 5
SUPPORTED_FILE_TYPES = [
    'pdf', 'txt', 'csv',
    'xls', 'xlsx', 'xml',
    'zip', 'doc', 'docx',
    'json',
]
SLEEP_TIME = 0.75
METADATA_DIR = Path('data/metadata')
RAW_DIR = Path('data/raw')
DOWNLOAD_QUEUE_FILE_PATH = METADATA_DIR / "download_queue.csv"
ACTIVATE_QUEUE_FILE_PATH = METADATA_DIR / "activation_queue.csv"
DEACTIVATE_QUEUE_FILE_PATH = METADATA_DIR / "deactivation_queue.csv"