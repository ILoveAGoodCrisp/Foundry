from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str
    project: Path
    output: Path
    test_path: Path
    build_path: Path


def get_msbuild_path() -> Path:
    return Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\amd64\MSBuild.exe")

def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FoundryPlugin targets.")
    parser.add_argument(
        "--configuration",
        choices=("Debug", "Release"),
        default="Release",
    )
    parser.add_argument(
        "--test",
        action="store_true",
    )
    parser.add_argument(
        "--build",
        action="store_true",
    )

    args = parser.parse_args()

    script_root = Path(__file__).resolve()
    foundry_root = script_root.parent
    msbuild = get_msbuild_path()
    output_subdir = "debug" if args.configuration == "Debug" else "release"

    targets = (
        Target(
            name="Omaha / HREK",
            project=script_root / "FoundryPluginOmaha" / "FoundryPluginOmaha.csproj",
            output=script_root / "FoundryPluginOmaha" / "bin" / output_subdir / "FoundryPlugin.dll",
            test_path=Path(r"S:\Halo\Modding\Main\HREK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll"),
            build_path=foundry_root / "blender" / "addons" / "io_scene_foundry" / "resources" / "foundation" / "FoundryPluginOmaha.dll",
        ),
        Target(
            name="Midnight / H4EK",
            project=script_root / "FoundryPluginMidnight" / "FoundryPluginMidnight.csproj",
            output=script_root / "FoundryPluginMidnight" / "bin" / output_subdir / "FoundryPlugin.dll",
            test_path=Path(r"S:\Halo\Modding\Main\H4EK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll"),
            build_path=foundry_root / "blender" / "addons" / "io_scene_foundry" / "resources" / "foundation" / "FoundryPluginMidnight.dll",
        ),
        Target(
            name="Groundhog / H2AMPEK",
            project=script_root / "FoundryPluginGroundhog" / "FoundryPluginGroundhog.csproj",
            output=script_root / "FoundryPluginGroundhog" / "bin" / output_subdir / "FoundryPlugin.dll",
            test_path=Path(r"S:\Halo\Modding\Main\H2AMPEK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll"),
            build_path=foundry_root / "blender" / "addons" / "io_scene_foundry" / "resources" / "foundation" / "FoundryPluginGroundhog.dll",
        ),
    )

    for target in targets:
        print(f"Building {target.name}...")

        result = subprocess.run(
            [
                str(msbuild),
                str(target.project),
                f"/p:Configuration={args.configuration}",
                f"/p:Platform={args.platform}",
            ],
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Build failed for {target.name}.")

        if not target.output.exists():
            raise FileNotFoundError(f"Expected output was not produced for {target.name}: {target.output}")

        file_hash = sha256_file(target.output)
        print(f"  Output: {target.output}")
        print(f"  SHA256: {file_hash}")

        print(f"  Copying build DLL to {target.build_path}...")
        target.build_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target.output, target.build_path)

        if args.deploy:
            print(f"  Deploying to {target.deploy_path}...")
            target.deploy_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target.output, target.deploy_path)

if __name__ == "__main__":
    main()