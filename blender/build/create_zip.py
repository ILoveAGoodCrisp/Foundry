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
        zip.write(Path(sln_dir_path, "LICENSE"), Path("io_scene_foundry", "LICENSE"))
        zip.write(Path(sln_dir_path, "README.md"), Path("io_scene_foundry", "README.md"))

        for dir, _, files in os.walk(extension_path):
            for file in files:
                f = Path(file)
                if f.suffix == ".pyc":
                    continue
                zip.write(Path(dir, f))
                
    print(f"Zipped Blender Extension to {zip_path}")

if __name__ == "__main__":
    main()
