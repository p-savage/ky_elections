"""
Validates the two artifacts of the file discovery phase - the crawl log
and the file inventory.

Enforces four invariants:

DISCOVERY_1 - Every url_visited with a non-zero file_count in the crawl 
log is unique.

DISCOVERY_2 - Every source_url in the file inventory is present in the 
crawl log.

DISCOVERY_3 - The file count for each source in the crawl log equals the 
number of files in the inventory from that source.

DISCOVERY_4 - File_urls in the file inventory are unique.

Script execution is read-only. Neither artifact is modified during any 
execution process. Failure to validate triggers a non-zero exit code.
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.environment import config

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "crawl_log_file_name",
    help="""
    The name of the crawl log created by the last static_file_finder
    execution cycle. Do not include the file extension.
    """
)
arg_parser.add_argument(
    "file_inventory_file_name",
    help="""
    The name of the file inventory created by the last static_file_finder
    execution cycle. Do not include the file extension.
    """
)

@dataclass
class ListViolation:
    invariant_id: str
    description: str
    details: list[str]

@dataclass
class CountViolation:
    invariant_id: str
    description: str
    details: dict[str, dict[str, int]]

def validate_arg_paths(
    log_path: Path,
    inv_path: Path
) -> bool:
    """
    Validates the paths formed from the provided file names.

    Confirms that the paths formed using the command-line provided file
    names exist, do not reference directories, and are not identical. 
    Returns a formatted error message and exits the script if the check 
    fails.
    """
    
    if (log_path.exists()
        and log_path.is_file()
        and inv_path.exists()
        and inv_path.is_file()
        and log_path != inv_path
    ):
        return True
    else:
        sys.exit("""
        The file names provided either do not exist or reference a 
        directory or are identical.
        """)

def validate_source_urls(
        log_path: Path,
        inv_path: Path,
) -> tuple[
    ListViolation | None,
    ListViolation | None,
]:
    """
    Enforces the first and second invariants in the script's docstring.

    Takes the validated file paths formed from the command-line 
    arguments. Reads both CSV files and stores lists of source urls into 
    memory. Uses list and set comparisons to enforce the invariants. 
    Successful validations are passed silently. Failures print a 
    formatted error message identifying the invariant that was violated.
    """

    with open(log_path, newline='') as log,\
    open(inv_path, newline='') as inv:
        log_reader = csv.DictReader(log)
        inv_reader = csv.DictReader(inv)
        log_source_list = []
        inv_source_list =[]
        seen_sources = set()
        duplicate_crawl_sources = []
        missing_crawl_sources = []
        d1_violations = None
        d2_violations = None
        for row in log_reader:
            if int(row['file_count']) != 0:
                log_source_list.append(row['url_visited'])
        for row in inv_reader:
            inv_source_list.append(row['source_url'])
        for source_url in log_source_list:
            if source_url not in seen_sources:
                seen_sources.add(source_url)
            else:
                duplicate_crawl_sources.append(source_url)
        if duplicate_crawl_sources:
            d1_violations = ListViolation(
                invariant_id="DISCOVERY_1",
                description="""The following urls are duplicated in the 
                crawl log:""",
                details=duplicate_crawl_sources,
            )
        for source_url in inv_source_list:
            if source_url not in log_source_list:
                missing_crawl_sources.append(source_url)
        if missing_crawl_sources:
            d2_violations = ListViolation(
                invariant_id="DISCOVERY_2",
                description="""The following urls are listed as sources 
                in the file inventory but not present in the crawl log:
                """,
            details=missing_crawl_sources,
            )
        return d1_violations, d2_violations

def validate_inventory(
        log_path: Path,
        inv_path: Path,
) -> tuple[
    CountViolation | None,
    ListViolation | None,
]:
    """
    Enforces the third and fourth invariants in the script's docstring.

    Takes the validated file paths formed from the command-line 
    arguments. Reads both CSV files and stores descriptive data 
    structures into memory. Comparisons of the stored data structures are
    performed to enforce the invariants. Successful validations are 
    passed silently. Failures print a formatted error message identifying
    the invariant that was violated. Incompatible file count totals are 
    specified in the error message.
    
    Dependent upon previous, successful validate_source_urls call to 
    avoid possible KeyError.
    """

    with open(log_path, newline='') as log,\
    open(inv_path, newline='') as inv:
        log_reader = csv.DictReader(log)
        inv_reader = csv.DictReader(inv)
        file_urls = []
        seen_file_urls = set()
        duplicate_file_urls = []
        log_dict = {}
        inv_dict = {}
        bad_sources = {}
        d3_violations = None
        d4_violations = None
        for row in log_reader:
            if int(row['file_count']) != 0:
                log_dict[row['url_visited']] = int(row['file_count'])
        for row in inv_reader:
            file_urls.append(row['file_url'])
            if row['source_url'] in inv_dict:
                inv_dict[row['source_url']] += 1
            else:
                inv_dict[row['source_url']] = 1
        for source, count in log_dict.items():
            if inv_dict[source] != count:
                bad_sources[source] = {}
                bad_sources[source]['log_count'] = count
                bad_sources[source]['inv_count'] = inv_dict[source]
        if bad_sources:
            d3_violations = CountViolation(
                invariant_id="DISCOVERY_3",
                description="""The following source urls have a file 
                count in the crawl log that does not match the number of
                rows in the file inventory that cite them as sources:""",
                details=bad_sources,
            )
        for url in file_urls:
            if url not in seen_file_urls:
                seen_file_urls.add(url)
            else:
                duplicate_file_urls.append(url)
        if duplicate_file_urls:
            d4_violations = ListViolation(
                invariant_id="DISCOVERY_4",
                description="""The following file urls are duplicated in 
                the file inventory:""",
                details=duplicate_file_urls,
            )
        return d3_violations, d4_violations

def print_violations(
        d1: ListViolation | None,
        d2: ListViolation | None,
        d3: CountViolation | None,
        d4: ListViolation | None,
) -> None:

    if d1 is not None:
        print(f"INVARIANT VIOLATED: {d1.invariant_id}")
        print(f"{d1.description}")
        for url in d1.details:
            print(f"{url}")
    if d2 is not None:
        print(f"INVARIANT VIOLATED: {d2.invariant_id}")
        print(f"{d2.description}")
        for url in d2.details:
            print(f"{url}")
    if d3 is not None:
        print(f"INVARIANT VIOLATED: {d3.invariant_id}")
        print(f"{d3.description}")
        for url, count_dict in d3.details.items():
            print(f"{url}")
            for key in count_dict:
                print(f"{key}: {count_dict[key]}")
    if d4 is not None:
        print(f"INVARIANT VIOLATED: {d4.invariant_id}")
        print(f"{d4.description}")
        for url in d4.details:
            print(f"{url}")
    
def main() -> None:
    """
    Configures paths and controls the validation flow.

    Uses command-line arguments to form local paths. Calls for successive 
    validation checks for file paths, invariants relating to source urls,
    and invariants relating to file inventory contents.
    """

    args = arg_parser.parse_args()
    log_arg = args.crawl_log_file_name
    inv_arg = args.file_inventory_file_name
    log_path = config.METADATA_DIR / f"{log_arg}.csv.tmp"
    inv_path = config.METADATA_DIR / f"{inv_arg}.csv.tmp"
    validate_arg_paths(
        log_path=log_path,
        inv_path=inv_path,
    )
    d1, d2 = validate_source_urls(
        log_path=log_path,
        inv_path=inv_path,
    )
    d3, d4 = validate_inventory(
        log_path=log_path,
        inv_path=inv_path,
    )       
    if (d1 or d2 or d3 or d4):
        print_violations(
            d1=d1,
            d2=d2,
            d3=d3,
            d4=d4,
        )
        sys.exit(1)
    else:
        print("SUCCESSFULLY VALIDATED.")
if __name__ == "__main__":
    main()