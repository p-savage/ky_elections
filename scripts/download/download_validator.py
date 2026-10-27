"""
This module validates the internal consistency of the temporary manifest
and the error log created by the latest downloader run.

It compares the two artifacts and successful validation is predicated 
upon the establishment of five invariants:

DOWNLOAD_1 - Every file_url in the temporary manifest is unique.

DOWNLOAD_2 - Every content hash in the temporary manifest is unique.

DOWNLOAD_3 - Every file_url in the error log is unique.

DOWNLOAD_4 - No file_url appears in both the temporary manifest and the 
error log.

DOWNLOAD_5 - Every file_url in the queue appears in either the temporary
manifest or the error log.
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.environment import config

# _______________________________________________________________________
# CONFIGURATION
# _______________________________________________________________________

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("temporary_manifest", help="""
                        Local file path to the temporary manifest created
                         by the last download run. Do not include the 
                         file extension.""")
arg_parser.add_argument("error_log", help="""Local file path to the error
                         log containing information about rows that 
                        failed to download during the last download run. 
                        Do not include the file extension.
                        """)

@dataclass
class ListViolation:
    invariant_id: str
    description: str
    details: list[str]

@dataclass
class DictViolation:
    invariant_id: str
    description: str
    details: dict[str, list[str]]

# _______________________________________________________________________
# FUNCTIONS
# _______________________________________________________________________

def validate_paths(paths: list[Path]) -> list[Path]:
    """
    Validates the existence of a command-line argument Path object.

    ASSUMPTION: Supplied Path refers to CSV file.
    Returns True if supplied Path exists and is a file. Returns False if 
    Path does not exist or is a directory.
    """

    invalid_paths = []
    for path in paths:
        if not path.exists() or not path.is_file():
            invalid_paths.append(path)
    return invalid_paths

def arg_error_message(paths: list[Path]) -> None:
    """
    Prints a formatted error message for command-line argument and exits
    the script.
    """
    for path in paths:
        print(f"Path to {path} either does not exist or is not a file.")
    sys.exit(1)

def read_queue(path: Path) -> set[str]:

    with open(
        file=path,
        newline='',
    ) as queue:
        reader = csv.DictReader(queue)
        queue_url_set: set[str] = set()
        for row in reader:
            queue_url_set.add(row['file_url'])
    return queue_url_set

def read_manifest(path: Path) -> tuple[
    set[str],
    ListViolation | None,
    DictViolation | None,
    ]:

    with open(
        file=path,
        newline='',
    ) as manifest:
        manifest_reader = csv.DictReader(manifest)
        manifest_url_set: set[str] = set()
        duplicate_urls = []
        content_hash_set = {}
        duplicate_content_hashes: dict[str, list[str]] = {}
        dl1_violations = None
        dl2_violations = None
        for row in manifest_reader:
            if row['file_url'] not in manifest_url_set:
                manifest_url_set.add(row['file_url'])
            else:
                duplicate_urls.append(row['file_url'])
            if row['file_content_hash'] not in content_hash_set:
                content_hash_set[row['file_content_hash']] = row['file_url']
            else:
                if row['file_content_hash'] not in duplicate_content_hashes:
                    duplicate_content_hashes[row['file_content_hash']] = []
                    duplicate_content_hashes[row['file_content_hash']].append(row['file_url'])
                    duplicate_content_hashes[row['file_content_hash']].append(content_hash_set[row['file_content_hash']])
                else:
                    duplicate_content_hashes[row['file_content_hash']].append(row['file_url'])
        if duplicate_urls:
            dl1_violations = ListViolation(
                invariant_id="DOWNLOAD_1",
                description="""
                The following file urls are duplicated 
                within the temporary manifest:
                """,
                details=duplicate_urls,
            )
        if duplicate_content_hashes:
            dl2_violations = DictViolation(
                invariant_id="DOWNLOAD_2",
                description="""
                The following content hashes are duplicated within the 
                temporary manifest and associated with the corresponding
                file urls:
                """,
                details=duplicate_content_hashes,
            )

    return manifest_url_set, dl1_violations, dl2_violations

def read_error_log(path: Path) -> tuple[
    set[str],
    ListViolation | None,
]:

    with open(
        file=path,
        newline='',
    ) as error:
        error_reader = csv.DictReader(error)
        error_url_set: set[str] = set()
        duplicate_urls = []
        dl3_violations = None
        for row in error_reader:
            if row['file_url'] not in error_url_set:
                error_url_set.add(row['file_url'])
            else:
                duplicate_urls.append(row['file_url'])
        if duplicate_urls:
            dl3_violations = ListViolation(
                invariant_id="DOWNLOAD_3",
                description="""
                The following file urls are duplicated within the error 
                log:
                """,
                details=duplicate_urls,
            )
    return error_url_set, dl3_violations

def compare_url_sets(
        queue_set: set[str],
        manifest_set: set[str],
        error_set: set[str],
) -> tuple[
    ListViolation | None,
    ListViolation | None,
]:

    seen_urls = set()
    duplicates = []
    missings = []
    dl4_violations = None
    dl5_violations = None
    for url in manifest_set:
        if url not in seen_urls:
            seen_urls.add(url)
        else:
            duplicates.append(url)
    for url in error_set:
        if url not in seen_urls:
            seen_urls.add(url)
        else:
            duplicates.append(url)
    if duplicates:
        dl4_violations = ListViolation(
            invariant_id="DOWNLOAD_4",
            description="""
            The following file urls appear in both the manifest and the 
            error log:
            """,
            details=duplicates,
        )
    for url in queue_set:
        if url not in seen_urls:
            missings.append(url)
    if missings:
        dl5_violations = ListViolation(
            invariant_id="DOWNLOAD_5",
            description="""
            The following file urls from the download queue were not 
            found in either download artifact:
            """,
            details=missings,
        )
    return dl4_violations, dl5_violations

def summarize_validation(
        violations: list[ListViolation | DictViolation | None]
) -> None:

    for violation in violations:
        if violation is None:
            continue
        if type(violation) is ListViolation:
            print(f"INVARIANT VIOLATED: {violation.invariant_id}")
            print(f"{violation.description}")
            for url in violation.details:
                print(f"{url}")
        elif type(violation) is DictViolation:
            print(f"INVARIANT VIOLATED: {violation.invariant_id}")
            print(f"{violation.description}")
            for hash, url_list in violation.details.items():
                print(f"HASH: {hash}")
                for url in url_list:
                    print(f"\t{url}")
    if any(violation is not None for violation in violations):
        sys.exit(1)
    else:
        print("VALIDATION PASSED.")

# _______________________________________________________________________
# PROCEDURE
# _______________________________________________________________________

def main() -> None:
    """
    Orchestrates the control flow of the reconciler script.

    Validates command-line Paths, handles Path errors, calls for the
    construction of dicts for file count comparison, notifies either 
    confirmation of reconciliation or displays offending source_urls for 
    manual follow-up. 
    """

    args = arg_parser.parse_args()
    queue_path = config.DOWNLOAD_QUEUE_FILE_PATH
    manifest_path = config.METADATA_DIR / f"{args.temporary_manifest}.csv.tmp"
    error_path = config.METADATA_DIR / f"{args.error_log}.csv.tmp"
    paths = [queue_path, manifest_path, error_path]
    invalids = validate_paths(paths=paths)
    if invalids:
        arg_error_message(paths=invalids)
    queue_url_set = read_queue(path=queue_path)
    manifest_return = read_manifest(path=manifest_path)
    error_log_return = read_error_log(path=error_path)
    manifest_url_set, dl1_violations, dl2_violations = manifest_return
    error_url_set, dl3_violations = error_log_return
    dl4_violations, dl5_violations = compare_url_sets(
        queue_set=queue_url_set,
        manifest_set=manifest_url_set,
        error_set=error_url_set,
    )
    violations = [
        dl1_violations,
        dl2_violations,
        dl3_violations,
        dl4_violations,
        dl5_violations,
    ]
    summarize_validation(violations=violations)

if __name__ == "__main__":
    main()