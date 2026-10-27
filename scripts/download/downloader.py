"""
Downloads files from a download queue into the local raw-data
store while producing temporary manifest and error log artifacts for
subsequent verification.
"""
import argparse
import csv
import datetime as dt
import time
from dataclasses import asdict, dataclass, fields
from enum import Enum
from hashlib import sha256
from pathlib import Path
from sys import exit

import requests
from tqdm import tqdm

from scripts.environment import config

#________________________________________________________________________
# CONFIGURATION
#________________________________________________________________________

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "temp_manifest_name", 
    help="""
    The file name for the temporary manifest that will be created during 
    this download run. Do not include file extension.
    """)
arg_parser.add_argument(
    "error_log_name",
    help="""
    The file name for the temporary log where information will be stored 
    for file links that fail processing during this run. Do not include 
    file extension.
    """
)

@dataclass
class DownloadReport:
    """
    Represents the cumulative results of a download run. 
    
    Stores a count of successfully downloaded files and stores 
    information about download failures into categorized lists for 
    summary reporting.
    """
    wrong_filetypes: list[str]
    non_200_codes: list[tuple[int, str, str]]
    failed_downloads: list[str]
    transient_request_errors: list[str]
    permanent_request_errors: list[tuple[str, str]]
    failed_file_writes: list[tuple[str, str]]
    file_count: int

@dataclass
class ErrorEntry:
    """
    Represents an error log entry for a file inventory row that failed to 
    process.

    Identifies the file that failed to process with relevant information
    for the cause of the failure.
    """

    error_type: str
    error_name: str | None
    file_url: str
    source_url: str
    http_code: int | None

@dataclass
class ManifestEntry:
    """
    Represents an entry to the manifest for a single file download.

    Stores descriptive information about the file and the process used to
    acquire it.
    """

    is_current: bool | None
    file_name: str | None
    file_url: str | None
    source_url: str | None
    date_accessed: str | None
    filetype: str | None
    extraction_paradigm: str | None
    file_byte_size: int | None
    file_content_hash: str | None


class Error(Enum):
    """
    Defines the categories of error that can occur during file inventory
    row processing.

    Enum members store a descriptive string of the processing error for 
    use in summary reporting.
    """

    FILETYPE = "FILETYPE"
    STATUS_CODE = "STATUS_CODE"
    FILE_SIZE = "FILE_SIZE"
    REQUEST = "REQUEST_EXCEPTION"
    WRITE = "SYSTEM_WRITE_ERROR"

#________________________________________________________________________
# FUNCTIONS
#________________________________________________________________________

def validate_temporary_file_names(
        man_file_path: Path,
        log_file_path: Path,
    ) -> bool:
    """
    Validates the command-line inputs for the temporary manifest and log
    names.

    Verifies that paths constructed from the arguments provided by the 
    user are not identical and do not already exist. Script is exited 
    with an error message if the validation fails. 
    """

    if (not man_file_path.exists() 
        and not log_file_path.exists() 
        and man_file_path != log_file_path):
        return True
    else:
        exit("""
             The temporary file paths that were provided either already 
             exist or are identical.
             """)        
        
def validate_queue_path(download_queue_path: Path) -> bool:
    """
    Validates the file path specified in config.

    Run downloader only after successful validation and reconciliation of
    artifacts created by the last file_finder run to avoid validation 
    failure.
    """

    if download_queue_path.exists() and download_queue_path.is_file():
        return True
    else:
        exit(f"""
             '{download_queue_path}' either does not exist or is a directory.
             """)        

def get_csv_len(queue_path: Path) -> int:
    """
    Iterates over the inventory .csv file to acquire an accurate row 
    total.

    Returns an int to be used by the tqdm call for the terminal progress
    bar.
    """

    csv_len = 0
    with open(
        file=queue_path,
        newline='',
    ) as queue:
        reader = csv.DictReader(queue)
        for row in reader:
            csv_len+=1
    return csv_len

def process_row(
        row: dict[str, str], 
        report: DownloadReport
    ) -> tuple[
        ErrorEntry | None,
        ManifestEntry | None,
        bytes | None,
    ]:
    """
    Handles the primary task of downloading files and reporting failures-
    to-process.

    Takes a row dict from the inventory .csv file and uses values to 
    attempt a file download. Error log entries for failed downloads and 
    manifest entries for successful downloads are returned via their 
    respective dataclass objects. File contents are returned as bytes.   
    """

    errs = None
    manifest = None
    file_content = None
    response = None
    source_url = row['source_url']
    file_url = row['file_url']
    raw_file_type_str = file_url[-4:]
    if raw_file_type_str.startswith("."):
        file_type = raw_file_type_str[1:]
    else: 
        file_type = raw_file_type_str
    if file_type not in config.SUPPORTED_FILE_TYPES:
        report.wrong_filetypes.append(file_url)
        errs = ErrorEntry(
        error_type=Error.FILETYPE.value,
        error_name=None,
        file_url=file_url,
        source_url=source_url,
        http_code=None,
        )
        return errs, manifest, file_content
    file_name_bytes = file_url.encode()
    file_name = sha256(file_name_bytes).hexdigest() + "." + file_type
    for attempt in range(config.MAX_TRIES):
        try:
            response = requests.get(
            url=file_url,
            headers=config.HEADER,
            timeout=config.TIMEOUT,
            )
            break
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:
            if attempt == config.MAX_TRIES - 1:
                report.transient_request_errors.append(file_url)
                errs = ErrorEntry(
                error_type=Error.REQUEST.value,
                error_name=type(exc).__name__,
                file_url=file_url,
                source_url=source_url,
                http_code=None,
                )
                return errs, manifest, file_content
            time.sleep(config.SLEEP_TIME)
        except (
            requests.exceptions.TooManyRedirects,
            requests.exceptions.SSLError,
            requests.exceptions.ContentDecodingError,
            requests.exceptions.RequestException,
        ) as exc:
            report.permanent_request_errors.append((file_url, source_url))
            errs = ErrorEntry(
            error_type=Error.REQUEST.value,
            error_name=type(exc).__name__,
            file_url=file_url,
            source_url=source_url,
            http_code=None,
            )
            return errs, manifest, file_content
    assert response is not None
    http_code = response.status_code
    if http_code != 200:
        report.non_200_codes.append((http_code, file_url, source_url))
        errs = ErrorEntry(
        error_type=Error.STATUS_CODE.value,
        error_name=None,
        file_url=file_url,
        source_url=source_url,
        http_code=http_code,
        )
        return errs, manifest, file_content
    file_content = response.content
    file_size = len(file_content)
    if file_size == 0:
        report.failed_downloads.append(file_url)
        errs = ErrorEntry(
        error_type=Error.FILE_SIZE.value,
        error_name=None,
        file_url=file_url,
        source_url=source_url,
        http_code=http_code,
        )
        return errs, manifest, file_content
    else:
        content_hash = sha256(file_content).hexdigest()
    date = dt.date.today() # noqa: DTZ011
    formatted_date = date.strftime(
        format='%Y-%m-%d',
    )
    try:
        _write_contents(
            file_type=file_type,
            name=file_name,
            contents=file_content
        )
        report.file_count += 1
    except OSError as exc:
        report.failed_file_writes.append((file_url, source_url))
        errs = ErrorEntry(
            error_type=Error.WRITE.value,
            error_name=type(exc).__name__,
            file_url=file_url,
            source_url=source_url,
            http_code=http_code,
        )
        return errs, manifest, file_content
    manifest = ManifestEntry(
        is_current=True,
        file_name=file_name,
        file_url=file_url,
        source_url=source_url,
        date_accessed=formatted_date,
        filetype=file_type,
        extraction_paradigm='static',
        file_byte_size=file_size,
        file_content_hash=content_hash,
    )
    return errs, manifest, file_content

def _write_contents(
        file_type: str,
        name: str,
        contents: bytes,
    ) -> None:
    """
    Stores the contents of successful file downloads to local file paths.

    String arguments for the file's type and name are used to 
    complete a local path template. The bytes of the file's contents are 
    then written to that path.
    """

    file_path = config.RAW_DIR / file_type / name
    file_path.write_bytes(contents)

def print_summary(report: DownloadReport) -> None:
    """
    Prints a summary of a download run to the terminal.

    Uses values from the DownloadReport object to print formatted summary
    information to the terminal following the completion of a download
    run. 
    """
    if report.wrong_filetypes:
        print(f"WRONG FILETYPES: {len(report.wrong_filetypes)}")
        for item in report.wrong_filetypes:
            print(item)
    if report.non_200_codes:
        print(f"NON-200 STATUS CODES: {len(report.non_200_codes)}")
        for code, file, source in report.non_200_codes:
            print(f"code: {code}\nurl: {file}\nsource: {source}")
    if report.failed_downloads:
        print(f"FAILED DOWNLOADS: {len(report.failed_downloads)}")
        for item in report.failed_downloads:
            print(item)
    if report.transient_request_errors:
        print(f"TRANSIENT REQUEST EXCEPTIONS: {len(report.transient_request_errors)}")
        for item in report.transient_request_errors:
            print(item)
    if report.permanent_request_errors:
        print(f"PERMANENT REQUEST EXCEPTIONS: {len(report.permanent_request_errors)}")
        for file, source in report.permanent_request_errors:
            print(f"file: {file}\nsource: {source}")
    if report.failed_file_writes:
        print(f"FAILED FILE CONTENT WRITES: {len(report.failed_file_writes)}")
        for file, source in report.failed_file_writes:
            print(f"file: {file}\nsource: {source}")
    print(f"TOTAL FILES DOWNLOADED: {report.file_count}")


#________________________________________________________________________
# PROCEDURE
# _______________________________________________________________________

def main() -> None:
    """
    Orchestrates the flow of a download run.

    Initializes .csv read/write sessions, calls for row processing,
    sifts processing results, triggers log/manifest entries, calls for 
    local file content storage, and reports download cycle summary
    information.
    """
    
    args = arg_parser.parse_args()
    temp_manifest_path = (
        config.METADATA_DIR / f"{args.temp_manifest_name}.csv.tmp"
    )
    temp_log_path = (
        config.METADATA_DIR / f"{args.error_log_name}.csv.tmp"
    )
    download_queue_path = config.DOWNLOAD_QUEUE_FILE_PATH
    validate_temporary_file_names(
        man_file_path=temp_manifest_path,
        log_file_path=temp_log_path,
    )
    validate_queue_path(download_queue_path=download_queue_path)
    csv_len = get_csv_len(queue_path=download_queue_path)
    with open(
        file=temp_manifest_path, mode='w', newline='',) as manifest_file,\
        open(
        file=(temp_log_path), mode='w', newline='',) as error_log:
        manifest_fieldnames = [
            field.name 
            for field in fields(ManifestEntry)
        ]
        error_log_fieldnames = [
            field.name 
            for field in fields(ErrorEntry)
        ]
        manifest_writer = csv.DictWriter(
            manifest_file,
            fieldnames=manifest_fieldnames,
        )
        error_log_writer = csv.DictWriter(
            error_log,
            fieldnames=error_log_fieldnames,
        )
        manifest_writer.writeheader()
        error_log_writer.writeheader()
        with open(file=(download_queue_path), newline='',) as queue:
            reader = csv.DictReader(queue)
            report = DownloadReport(
                wrong_filetypes=[],
                non_200_codes=[],
                failed_downloads=[],
                transient_request_errors=[],
                permanent_request_errors=[],
                failed_file_writes=[],
                file_count=0,
            )
            for row in tqdm(reader, total=csv_len):
                (errs, manifest, file_content) = process_row(
                    row=row, 
                    report=report
                    )
                if errs:
                    error_log_writer.writerow(asdict(errs))
                if manifest and file_content:
                    man_dict = asdict(manifest)
                    manifest_writer.writerow(man_dict)
                time.sleep(config.SLEEP_TIME)
        print_summary(report=report)

if __name__ == "__main__":
    main()