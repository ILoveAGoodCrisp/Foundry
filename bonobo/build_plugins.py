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


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FoundryPlugin targets.")
    parser.add_argument(
        "--configuration",
        choices=("Debug", "Release"),
        default="Release",
        help="Build configuration for plugin projects.",
    )
    parser.add_argument(
        "--platform",
        choices=("x64",),
        default="x64",
        help="Build platform for plugin projects.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Copy outputs into the Foundry add-on resources folder.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Copy outputs into installed Editing Kit plugin folders.",
    )
    parser.add_argument(
        "--msbuild-path",
        help=(
            "Explicit path to MSBuild.exe"
        ),
        required=True,
    )
    args = parser.parse_args()

    if not args.build and not args.test:
        args.build = True

    script_dir = Path(__file__).resolve().parent
    foundry_root = script_dir.parent
    output_subdir = "debug" if args.configuration == "Debug" else "release"
    msbuild = args.msbuild_path

    print(f"Using MSBuild: {msbuild}")

    targets = (
        Target(
            name="Omaha / HREK",
            project=script_dir / "FoundryPluginOmaha" / "FoundryPluginOmaha.csproj",
            output=script_dir / "FoundryPluginOmaha" / "bin" / output_subdir / "FoundryPlugin.dll",
            test_path=Path(r"S:\Halo\Modding\Main\HREK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll"),
            build_path=foundry_root
            / "blender"
            / "addons"
            / "io_scene_foundry"
            / "resources"
            / "foundation"
            / "FoundryPluginOmaha.dll",
        ),
        Target(
            name="Midnight / H4EK",
            project=script_dir / "FoundryPluginMidnight" / "FoundryPluginMidnight.csproj",
            output=script_dir / "FoundryPluginMidnight" / "bin" / output_subdir / "FoundryPlugin.dll",
            test_path=Path(r"S:\Halo\Modding\Main\H4EK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll"),
            build_path=foundry_root
            / "blender"
            / "addons"
            / "io_scene_foundry"
            / "resources"
            / "foundation"
            / "FoundryPluginMidnight.dll",
        ),
        Target(
            name="Groundhog / H2AMPEK",
            project=script_dir / "FoundryPluginGroundhog" / "FoundryPluginGroundhog.csproj",
            output=script_dir / "FoundryPluginGroundhog" / "bin" / output_subdir / "FoundryPlugin.dll",
            test_path=Path(r"S:\Halo\Modding\Main\H2AMPEK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll"),
            build_path=foundry_root
            / "blender"
            / "addons"
            / "io_scene_foundry"
            / "resources"
            / "foundation"
            / "FoundryPluginGroundhog.dll",
        ),
    )

    for target in targets:
        print(f"Building {target.name}...")

        if not target.project.exists():
            raise FileNotFoundError(f"Project file does not exist: {target.project}")

        command = [
            msbuild,
            str(target.project),
            f"/p:Configuration={args.configuration}",
            f"/p:Platform={args.platform}",
        ]
        result = subprocess.run(command, check=False)

        if result.returncode != 0:
            raise RuntimeError(f"Build failed for {target.name}.")

        if not target.output.exists():
            raise FileNotFoundError(
                f"Expected output was not produced for {target.name}: {target.output}"
            )

        file_hash = sha256_file(target.output)
        print(f"  Output: {target.output}")
        print(f"  SHA256: {file_hash}")

        if args.build:
            print(f"  Copying build DLL to {target.build_path}...")
            copy_file(target.output, target.build_path)

        if output_subdir == "debug":
            print(f"  Deploying test DLL to {target.test_path}...")
            copy_file(target.output, target.test_path)


if __name__ == "__main__":
    main()
