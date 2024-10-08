"""
Helper script to create a zip file that can just be extracted to the blender addon folder

SPDX-License-Identifier: MIT
"""

from zipfile import ZipFile, ZIP_DEFLATED, ZIP_LZMA
import io
import os
import sys
import subprocess
from pathlib import Path

version = "1.0.0"

def build_resources_zip() -> io.BytesIO:
    search_path = os.path.join("blender" ,"addons", "io_scene_foundry", "resources")
    print(f"Building resources zip (searching in {search_path})!")

    data = io.BytesIO()
    zip: ZipFile = ZipFile(data, mode='w', compression=ZIP_LZMA, compresslevel=9)

    for dir, _, files in os.walk(search_path):
        relative_dir = os.path.relpath(dir, search_path)
        print(f"Adding files in {dir} (mapped to {relative_dir} in zip)")
        for file in files:
            fs_path = os.path.join(dir, file)
            zip.write(fs_path, os.path.join(relative_dir, file))

    zip.close()
    zip.printdir()
    data.flush()
    print("Done building resources")
    return data

def build_release_zip(name: str):
    project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(project_path)
    print(f"Building release type name: {name}")
    
    if 'Debug' in sys.argv:
        output_folder = 'Debug'
    else:
        output_folder = 'Release'

    resources = build_resources_zip()

    # grab the version from git
    git_version = subprocess.check_output(["git", "describe", "--always"]).strip().decode()
    print(f"git version: {git_version}")

    # grab version from arguments if any
    if output_folder == 'Debug':
        version_string = f"{version}@{git_version}"
    else:
        version_string = f"{version}"
    print(f"version: {version_string}")

    # create the output directory
    Path("bin", "Release").mkdir(exist_ok=True)

    # create zip name from git hash/version
    # zip_name = f"{name}-{version_string}.zip"
    zip_name = f"{name}.zip"

    print(f"zip name: {zip_name}")

    def write_file(zip: ZipFile, path_fs, path_zip = None):
        if path_zip is None:
            path_zip = path_fs
        zip.write(path_fs, os.path.join("io_scene_foundry", path_zip))

    # Add files to zip
    zip: ZipFile = ZipFile(os.path.join("site", "api", "v1", "extensions", zip_name), mode='w', compression=ZIP_DEFLATED, compresslevel=9)
    write_file(zip, "LICENSE")
    write_file(zip, "README.md")
    os.chdir(Path("blender/addons"))
    for dir, _, files in os.walk(os.path.join("io_scene_foundry")):
        if dir.startswith(os.path.join("io_scene_foundry", "resources")):
            continue
        for file in files:
            main_dir_ignore = ['resources.zip', 'blender_manifest.toml']
            if file.endswith(".pyc") or (dir == 'io_scene_foundry' and file in main_dir_ignore):
                continue
            fs_path = os.path.join(dir, file)
            zip.write(fs_path)
    os.chdir(project_path)
    init_file = Path('blender/addons/io_scene_foundry/blender_manifest.toml').read_text()
    # init_file = init_file.replace('version = "1.0.0"', f'version = {git_version}')
    zip.writestr('io_scene_foundry/blender_manifest.toml', init_file)
    zip.writestr('io_scene_foundry/resources.zip', resources.getbuffer())
    zip.printdir()
    zip.close()

build_release_zip(name="io_scene_foundry")
print("done!")
