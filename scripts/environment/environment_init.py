import csv

from scripts.environment import config


def main() -> None:
    """
    Establishes the canonical directory hierarchy and metadata artifacts
    required for the pipeline.

    References file type list in config to construct the directory
    hierarchy that subsequent pipeline tasks will rely upon.
    """
    
    first_layer = (config.METADATA_DIR, config.RAW_DIR)
    for path in first_layer:
        path.mkdir(parents=True, exist_ok=True)
    for file_type in config.SUPPORTED_FILE_TYPES:
        filetype_dir = config.RAW_DIR / file_type
        filetype_dir.mkdir(parents=True, exist_ok=True)
    man_file_path = config.METADATA_DIR / config.MANIFEST_FILE_NAME
    if not man_file_path.exists():
        with open(file=man_file_path, mode='w', newline='') as manifest:
            manifest_writer = csv.DictWriter(
                manifest,
                fieldnames=config.MANIFEST_FIELDNAMES,
                )
            manifest_writer.writeheader()
        
if __name__ == '__main__':
    main()