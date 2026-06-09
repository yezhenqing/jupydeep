# 在 Python 端手动读取某个扩展的设置文件
from pathlib import Path
from typing import List, Union, Optional, Set

from .logging import get_logger

logger = get_logger(__name__)


def find_dirs_with_nested_subfolder(
    paths: List[Union[str, Path]], subfolder_name: str
) -> List[Path]:
    """
    Scan given paths to locate all nested directories matching the specified subfolder name.

    Args:
        paths: A list of directory paths (strings or Path objects) to search within.
        subfolder_name: The target directory name to find.

    Returns:
        List[Path]: A deduplicated list of absolute Path objects pointing to the matched subfolders.
    """
    results: Set[Path] = set()

    for p in paths:
        if not p:
            continue

        # Ensure config_dir is a Path object and exists.
        path_obj = Path(p).resolve()
        if not path_obj.exists():
            continue

        # rglob recursively matches all directories named subfolder_name.
        for match in path_obj.rglob(f"{subfolder_name}"):
            if match.is_dir():
                results.add(match.resolve())

    return list(results)


def get_setting_paths(
    setting_json_dirs: List[Path], prefix: str
) -> Optional[List[Path]]:
    """
    Find configuration paths with the specified prefix.

    Returns:
        List[Path]: A list of matching paths, or None if no matches are found.
    """
    setting_paths = []

    for config_dir in setting_json_dirs:
        # Validate that config_dir exists as a Path
        if not config_dir.exists() or not config_dir.is_dir():
            logger.debug(
                f"Config directory {config_dir} does not exist or is not a directory, skipping."
            )
            continue

        found_files = list(config_dir.glob(f"{prefix}.*"))
        setting_paths.extend(found_files)

    # Key point：returns a list of Paths, or None if no match is found.
    return setting_paths if setting_paths else None


__all__ = (
    find_dirs_with_nested_subfolder,
    get_setting_paths,
)
