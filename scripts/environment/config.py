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
    'User-Agent': 'ky-elections-etl/0.1 (pjslouisville502@gmail.com)'
    }
TIMEOUT = 10.00
MAX_TRIES = 5
RETRY_STATUS_CODES = [
    408,
    429,
    500,
    502,
    503,
    504,
]
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
KY_COUNTIES = [
    'Adair','Allen','Anderson','Ballard','Barren','Bath','Bell','Boone',
    'Bourbon','Boyd','Boyle','Bracken','Breathitt','Breckinridge',
    'Bullitt','Butler','Caldwell','Calloway','Campbell','Carlisle',
    'Carroll','Carter','Casey','Christian','Clark','Clay','Clinton',
    'Crittenden','Cumberland','Daviess','Edmonson','Elliott','Estill',
    'Fayette','Fleming','Floyd','Franklin','Fulton','Gallatin','Garrard',
    'Grant','Graves','Grayson','Green','Greenup','Hancock','Hardin',
    'Harlan','Harrison','Hart','Henderson','Henry','Hickman','Hopkins',
    'Jackson','Jefferson','Jessamine','Johnson','Kenton','Knott','Knox',
    'LaRue','Laurel','Lawrence','Lee','Leslie','Letcher','Lewis',
    'Lincoln','Livingston','Logan','Lyon','Madison','Magoffin','Marion',
    'Marshall','Martin','Mason','McCracken','McCreary','McLean','Meade',
    'Menifee','Mercer','Metcalfe','Monroe','Montgomery','Morgan',
    'Muhlenberg','Nelson','Nicholas','Ohio','Oldham','Owen','Owsley',
    'Pendleton','Perry','Pike','Powell','Pulaski','Robertson',
    'Rockcastle','Rowan','Russell','Scott','Shelby','Simpson','Spencer',
    'Taylor','Todd','Trigg','Trimble','Union','Warren','Washington',
    'Wayne','Webster','Whitley','Wolfe','Woodford',
]