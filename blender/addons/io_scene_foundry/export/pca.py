"""Install Tool's external PCA solver before exporting H4+ blend shapes."""
import os
from pathlib import Path
import shutil
import tempfile


def ensure_pcatool(project_root):
    """Copy the bundled solver only if the kit has none; preserve custom tools."""
    destination = Path(project_root) / 'bin/pcatool.exe'
    if destination.is_file():
        return destination
    source = Path(__file__).resolve().parents[1] / 'resources/pcatool.exe'
    if not source.is_file():
        raise FileNotFoundError(
            'Foundry is missing resources/pcatool.exe. Reinstall the complete Foundry '
            'extension, or build it with blender/build_pcatool.py before exporting blend shapes.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Publish only the complete file. Windows rename will not replace an
    # existing destination, including one installed by a concurrent export.
    fd, temporary = tempfile.mkstemp(prefix='pcatool-', suffix='.tmp', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as output, source.open('rb') as input_file:
            shutil.copyfileobj(input_file, output)
        try:
            os.rename(temporary, destination)
        except FileExistsError:
            if not destination.is_file():
                raise
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
