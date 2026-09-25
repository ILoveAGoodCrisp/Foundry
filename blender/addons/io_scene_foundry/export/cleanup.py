"""Remove stale intermediates only inside explicitly owned export directories."""
from pathlib import Path


ANIMATION_EXTENSIONS = {'.jma', '.jmm', '.jmt', '.jmz', '.jmo', '.jmr', '.jmw', '.jmv', '.jmh'}


def prune_intermediates(asset_path, expected_paths, directories):
    """Compare complete inventories, never just the files written this run.

    Directories map to permitted extensions and are scanned non-recursively so
    child assets and source files cannot accidentally become cleanup candidates.
    """
    root = Path(asset_path).resolve()
    expected = {str(Path(path).resolve()).casefold() for path in expected_paths}
    removed = []
    for directory, extensions in directories.items():
        directory = Path(directory)
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            continue
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if (path.is_symlink() or not path.is_file()
                    or path.suffix.lower() not in extensions
                    or not path.resolve().is_relative_to(root)
                    or str(path.resolve()).casefold() in expected):
                continue
            path.unlink()
            removed.append(path)
            print(f'--- Removed unused intermediate: {path}')
    return removed
