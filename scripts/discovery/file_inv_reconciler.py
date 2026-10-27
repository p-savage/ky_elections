"""
Compares the file inventory from the latest discovery cycle to the 
current state of the authoritative manifest to determine action queues:

Download
Activate
Deactivate
"""

import argparse
import csv
import sys
from pathlib import Path

from scripts.environment import config

arg_parser = argparse.ArgumentParser()

arg_parser.add_argument(
    "file_inventory_name",
    help="""
    The name of the file inventory from the latest discovery run. Do not
    include the file extension.
    """
)

def validate_path(path: Path):

    if not (path.exists() and path.is_file()):
        sys.exit("""The file name provided either does not exists or 
        refers to a directory.""")

def read_file_inv(path: Path) -> dict[str, dict[str, bool | str | None]]:

    state_dict = {}
    with open(path, newline='') as file_inv:
        reader = csv.DictReader(file_inv)
        for row in reader:
            state_dict[row['file_url']] = {}
            state_dict[row['file_url']]['source_url'] = row['source_url']
            state_dict[row['file_url']]['in_inventory'] = True
            state_dict[row['file_url']]['is_current'] = None
    return state_dict

def read_manifest(
        path: Path,
        state_dict: dict[str, dict[str, bool | str | None]]
    ) -> dict[str, dict[str, bool | str | None]]:

    with open(path, newline='') as manifest:
        reader = csv.DictReader(manifest)
        for row in reader:
            if row['file_url'] in state_dict:
                if row['is_current'] == "True":
                    state_dict[row['file_url']]['is_current'] = True
                else:
                    state_dict[row['file_url']]['is_current'] = False
            else:
                state_dict[row['file_url']] = {}
                state_dict[row['file_url']]['source_url'] = row['source_url']
                state_dict[row['file_url']]['in_inventory'] = False
                if row['is_current'] == "True":
                    state_dict[row['file_url']]['is_current'] = True
                else:
                    state_dict[row['file_url']]['is_current'] = False
    return state_dict

def sort_state_dict(
        state_dict: dict[str, dict[str, bool | str | None]]
        ) -> tuple[
            list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]],
        ]:
    """Iterates over the constructed state dictionary and use value 
    combinations to assign URLs to appropriate action queues.
    
    URLs can be passed over silently or added to a queue meant for 
    download, activation, or deactivation. Queues returned as a tuple."""
    
    downloads = []
    activates = []
    deactivates = []
    for url, states in state_dict.items():
        if (states['in_inventory'] and states['is_current'] is None):
            downloads.append((url, states['source_url']))
        elif (states['in_inventory'] and not states['is_current']):
            activates.append((url, states['source_url']))
        elif (not states['in_inventory'] and states['is_current']):
            deactivates.append((url, states['source_url']))
    return downloads, activates, deactivates

def write_queue_files(
        downloads: list[tuple[str, str]],
        activates: list[tuple[str, str]],
        deactivates: list[tuple[str, str]],
        ) -> None:
    download_path = config.DOWNLOAD_QUEUE_FILE_PATH
    activate_path = config.ACTIVATE_QUEUE_FILE_PATH
    deactivate_path = config.DEACTIVATE_QUEUE_FILE_PATH
    download_tup = (download_path, downloads)
    activate_tup = (activate_path, activates)
    deactivate_tup = (deactivate_path, deactivates)
    tups = (download_tup, activate_tup, deactivate_tup) 
    fieldnames = ['file_url', 'source_url']
    for tup in tups:
        file_path = tup[0]
        url_list = tup[1]
        with open(file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for url, source in url_list:
                writer.writerow({'file_url': url,
                                 'source_url': source})

def main() -> None:

    arg = arg_parser.parse_args()
    file_inv_path = config.METADATA_DIR / f"{arg.file_inventory_name}.csv.tmp"
    validate_path(file_inv_path)
    manifest_path = config.METADATA_DIR / config.MANIFEST_FILE_NAME
    state_dict = read_file_inv(path=file_inv_path)
    state_dict = read_manifest(
        path=manifest_path,
        state_dict=state_dict
        )
    queues = sort_state_dict(state_dict=state_dict)
    downloads, activates, deactivates = queues
    write_queue_files(
        downloads=downloads,
        activates=activates,
        deactivates=deactivates,
        )

if __name__ == "__main__":
    main()