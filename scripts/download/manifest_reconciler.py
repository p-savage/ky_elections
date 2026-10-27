"""
This module uses the validated temporary manifest to generate a queue for
the authoritative manifest. Addition to the manifest is 
contigent upon one invariant:

DOWNLOAD_6 - No content hash in the append queue already exists in the 
authoritative manifest.

Entries in the append queue with unique content hashes get appended to 
the authoritative manifest. Entries with content hashes that already 
exist in the manifest are reported for investigation.
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.environment import config

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "temporary_manifest_file_name",
    help="""
    The name of the temporary manifest created and validated by the 
    latest download cycle. Do not include the file extension.
    """,
)

@dataclass
class ListViolation:
    invariant_id: str
    description: str
    details: list[str]

def validate_path(paths: tuple[Path, Path]) -> None:

    for path in paths:
        if not path.exists() or not path.is_file():
            sys.exit("""The path formed using the provided file name either
            does not exists or is not a file.""")

def extract_temp_hashes(path: Path) -> list[tuple[str, str]]:

    temp_hash_list = []
    with open(path, newline='') as temp_manifest:
        reader = csv.DictReader(temp_manifest)
        for row in reader:
            temp_hash_list.append((
                row['file_url'],
                row['file_content_hash'],
            ))
    return temp_hash_list

def extract_auth_hashes(path: Path) -> list[tuple[str, str]]:

    auth_hash_list = []
    with open(path, newline='') as auth_manifest:
        reader = csv.DictReader(auth_manifest)
        for row in reader:
            auth_hash_list.append((
                row['file_url'],
                row['file_content_hash'],
            ))
    return auth_hash_list

def compare_hash_lists(
        hash_lists: tuple[
            list[tuple[str,str]],
            list[tuple[str, str]]]
) -> tuple[
    ListViolation | None,
    set[str],
]:

    dl6_violations = None
    duplicates = []
    temp_tup_list = hash_lists[0]
    auth_tup_list = hash_lists[1]
    auth_hashes_set = set()
    approved_url_set: set[str] = set()
    for url, hash in auth_tup_list:
        auth_hashes_set.add(hash)
    for url, hash in temp_tup_list:
        if hash in auth_hashes_set:
            duplicates.append(url)
        else:
            approved_url_set.add(url)
    if duplicates:
        dl6_violations = ListViolation(
            invariant_id="DOWNLOAD_6",
            description="""The following file urls from the temporary 
            manifest have content hashes that already exist in the 
            authoritative manifest:""",
            details=duplicates,
        )
    return dl6_violations, approved_url_set

def summarize_violations(violation: ListViolation) -> None:

        print(f"INVARIANT VIOLATED: {violation.invariant_id}")
        print(f"{violation.description}")
        for url in violation.details:
            print(f"{url}")    

def append_to_manifest(
        url_set: set[str],
        temp_manifest: Path,
        manifest: Path,
) -> None:

    with open(manifest, mode='a', newline='') as auth_man, \
        open(temp_manifest, newline='') as temp_man:
        manifest_appender = csv.DictWriter(
            auth_man, 
            fieldnames=config.MANIFEST_FIELDNAMES,
            )
        temp_manifest_reader = csv.DictReader(temp_man)
        for row in temp_manifest_reader:
            if row['file_url'] in url_set:
                manifest_appender.writerow(row)

def main() -> None:

    arg = arg_parser.parse_args()
    temp_manifest_file_path = config.METADATA_DIR / f"{arg.temporary_manifest_file_name}.csv.tmp"
    auth_manifest_file_path = config.METADATA_DIR / config.MANIFEST_FILE_NAME
    paths = (temp_manifest_file_path, auth_manifest_file_path)
    validate_path(paths=paths)
    temp_hash_list = extract_temp_hashes(path=temp_manifest_file_path)
    auth_hash_list = extract_auth_hashes(path=auth_manifest_file_path)
    hash_lists = (temp_hash_list, auth_hash_list)
    dl6_violations, approved_url_set = compare_hash_lists(
        hash_lists=hash_lists
        )
    if dl6_violations is not None:
        summarize_violations(violation=dl6_violations)
    append_to_manifest(
        url_set=approved_url_set,
        temp_manifest=temp_manifest_file_path,
        manifest=auth_manifest_file_path,
    )
    

if __name__ == "__main__":
    main()