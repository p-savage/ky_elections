import argparse
import csv
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scripts.environment import config

# _______________________________________________________________________
# CONFIGURATION
# _______________________________________________________________________

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "crawl_log_name",
    help="""
    The name to be used for the crawl log file that is created. Do not 
    include the file extension.
    """)
arg_parser.add_argument(
    "file_inventory_name",
    help="""
    The name to be used for the file inventory that is created. Do not 
    include the file extension.
    """
)

@dataclass
class CrawlLogEntry:
    url_visited: str
    http_status_code: int | None
    files_found: bool
    file_count: int
    extraction_paradigm: str

@dataclass
class CrawlSummary:
    errors: list[tuple[Exception, str]]
    status_code_failures: list[tuple[str, int]]

TERMINAL_OUTPUT_WIDTH = 120

# _______________________________________________________________________
# FUNCTIONS
# _______________________________________________________________________

def validate_output_paths(
        crawl_log_path: Path,
        file_inv_path: Path,
) -> bool:
    
    if (not crawl_log_path.exists() 
        and not file_inv_path.exists() 
        and crawl_log_path != file_inv_path):
        return True
    else:
        sys.exit("""
             The temporary file paths that were provided either already 
             exist or are identical.
             """)

def fetch_root_page(url_str: str) -> BeautifulSoup:
    """Fetches and parses html for root results page."""

    for _ in range(config.MAX_TRIES):
        try:
            response = requests.get(
                url=url_str,
                headers=config.HEADER,
                timeout=config.TIMEOUT,
                )
            break
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            ):
            time.sleep(config.SLEEP_TIME)
        except (
            requests.exceptions.TooManyRedirects,
            requests.exceptions.SSLError,
            requests.exceptions.ContentDecodingError,
            requests.exceptions.RequestException,
            ) as exc:
            sys.exit(f"{type(exc).__name__} for root url.")
    else:
        sys.exit("Max tries exceeded for root url.")
    print("Root page loaded.")
    root_text = response.text
    return BeautifulSoup(root_text, 'html.parser')

def extract_election_year_page_urls(
        html: BeautifulSoup,
        root_url: str,
) -> set[str]:
    """Takes a BeautifulSoup response object and returns a set of unique
    urls for results pages."""
    
    election_year_urls = set()
    a_tags = html.find_all('a')
    for tag in a_tags:
        if (tag.has_attr('href') 
        and tag['href'][:9] == '/results/'
        ):
            new_url = urljoin(root_url, str(tag['href']))
            if new_url[-12:] != 'default.aspx':
                election_year_urls.add(new_url)
    print(f"\nRESULTS PAGES EXTRACTED: {len(election_year_urls)}\n")
    return election_year_urls

def find_file_urls(
        url_str: str,
        summary: CrawlSummary,
) -> tuple[
        CrawlLogEntry | None,
        set[tuple[str, str, str]],
]:
    """Takes a url string. Parses html to discover and build complete 
    file link urls. Records and returns crawler metadata as a dict. Also
    returns constructed direct file urls, its associated source url, and
    the link-text displayed in the html."""

    file_urls = set()
    crawl_log_entry = None
    response = None
    for attempt in range(config.MAX_TRIES):
        try:
            response = requests.get(
                url=url_str,
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
                summary.errors.append((exc,url_str))
                return crawl_log_entry, file_urls                
            time.sleep(config.SLEEP_TIME)
        except (
            requests.exceptions.TooManyRedirects,
            requests.exceptions.SSLError,
            requests.exceptions.ContentDecodingError,
            requests.exceptions.RequestException,
            ) as exc:
            summary.errors.append((exc,url_str))
            return crawl_log_entry, file_urls 
    assert response is not None
    if response.status_code != 200:
        summary.status_code_failures.append(
            (url_str, response.status_code)
        )
        return crawl_log_entry, file_urls
    new_text = response.text
    new_html = BeautifulSoup(new_text, 'html.parser')
    new_a_tags = new_html.find_all('a')
    for tag in new_a_tags:
        if tag.has_attr('href'):
            raw_file_type = tag['href'][-4:]
            if raw_file_type[0] == ".":
                file_type = raw_file_type[1:]
            else:
                file_type = raw_file_type
            if file_type in config.SUPPORTED_FILE_TYPES:
                file_address = urljoin(url_str, str(tag['href']))
                file_urls.add((file_type, file_address, url_str))
    if file_urls:
        files_found = True
    else:
        files_found = False
    crawl_log_entry = CrawlLogEntry(
        url_visited=url_str,
        http_status_code=response.status_code,
        files_found=files_found,
        file_count=len(file_urls),
        extraction_paradigm='static',
    )
    time.sleep(config.SLEEP_TIME)
    return crawl_log_entry, file_urls

def print_crawl_summary(
        errors: list[tuple[Exception,str]], 
        status_codes: list[tuple[str, int]],
) -> None:
    """
    Takes accumulated metadata values and prints a formatted summary
    of crawl failures.
    """

    if errors:
        print("REQUEST ERRORS:")
        for exc, url in errors:
            print(f"{type(exc).__name__} - {url}")
    else:
        print("NO TRANSIENT ERRORS")
    if status_codes:
        print("STATUS CODE ERRORS:")
        for url, code in status_codes:
            print(f"{code} - {url}")
    else:
        print("NO STATUS CODE FAILURES")

# _______________________________________________________________________
# PROCEDURE
# _______________________________________________________________________

def main() -> None:


    args = arg_parser.parse_args()
    crawl_log_name_arg = args.crawl_log_name
    file_inv_name_arg = args.file_inventory_name
    crawl_log_path = config.METADATA_DIR / f"{crawl_log_name_arg}.csv.tmp"
    file_inv_path = config.METADATA_DIR / f"{file_inv_name_arg}.csv.tmp"
    validate_output_paths(
        crawl_log_path=crawl_log_path,
        file_inv_path=file_inv_path,
    )
    root_html = fetch_root_page(url_str=config.ROOT_URL)
    election_year_page_urls = extract_election_year_page_urls(
        html=root_html,
        root_url=config.ROOT_URL,
    )
    with open(file=crawl_log_path, mode= 'w', newline='') as crawl_log_session,\
        open(file=file_inv_path, mode='w', newline='') as file_inv_session:
        crawl_log_fieldnames = [field.name for field in fields(CrawlLogEntry)]
        crawl_log_writer = csv.DictWriter(
            crawl_log_session,
            fieldnames=crawl_log_fieldnames,
        )
        file_inv_fieldnames = [
            'file_type',
            'file_url',
            'source_url',
            'extraction_paradigm',
        ]
        file_inv_writer = csv.DictWriter(
            file_inv_session,
            fieldnames=file_inv_fieldnames,
        )
        crawl_log_writer.writeheader()
        file_inv_writer.writeheader()
        crawl_summary = CrawlSummary(
            errors=[],
            status_code_failures=[]
        )
        for url in election_year_page_urls:
            print(
                f"\rProcessing url {url:<120}", end='', flush=True)
            crawl_log_entry, file_urls = find_file_urls(
                url_str=url,
                summary=crawl_summary,
                )
            if crawl_log_entry:
                crawl_log_writer.writerow(asdict(crawl_log_entry))
            if file_urls:
                for file_type, url, source in file_urls:
                    file_inv_writer.writerow({
                        'file_type': file_type,
                        'file_url': url,
                        'source_url': source,
                        'extraction_paradigm': 'static',
                    })
    print("\r" + " " * 120 + "\r", end="", flush=True)
    print_crawl_summary(
        errors=crawl_summary.errors,
        status_codes=crawl_summary.status_code_failures,
    )
    print("\nCrawl Complete.")

if __name__ == "__main__":
    main()