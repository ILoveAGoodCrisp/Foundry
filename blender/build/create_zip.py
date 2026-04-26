from zipfile import ZipFile, ZIP_DEFLATED
import os
from pathlib import Path

def main():
    # Get relevant paths
    abs_file = Path(__file__).absolute()
    sln_dir_path = abs_file.parent.parent.parent
    extension_path = Path(sln_dir_path, "blender", "addons", "io_scene_foundry")
    
    zip_path = Path(sln_dir_path, "site", "api", "v1", "extensions", "io_scene_foundry.zip")
    zip_dir = zip_path.parent
    
    if not zip_dir.exists():
        zip_dir.mkdir(parents=True, exist_ok=True)
    
    with ZipFile(zip_path, mode='w', compression=ZIP_DEFLATED, compresslevel=9) as zip:
        zip.write(Path(sln_dir_path, "LICENSE"), Path("LICENSE"))
        zip.write(Path(sln_dir_path, "README.md"), Path("README.md"))

        for dir, dirs, files in os.walk(extension_path):
            dir_path = Path(dir)

            dirs[:] = [
                d for d in dirs
                if not d.startswith("_")
                and d != "__pycache__"
            ]

            for file in files:
                file_path = dir_path / file

                if file_path.suffix == ".pyc":
                    continue

                archive_path = Path("io_scene_foundry") / file_path.relative_to(extension_path)
                zip.write(file_path, archive_path)
                
    print(f"Zipped Blender Extension to {zip_path}")

if __name__ == "__main__":
    main()
