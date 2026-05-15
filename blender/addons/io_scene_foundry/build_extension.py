#!/usr/bin/env python3
"""Download extension wheels and regenerate blender_manifest.toml."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_MANIFEST_VERSION = "1.7.26"
DEFAULT_PYTHON_VERSION = "3.13"
DEFAULT_IMPLEMENTATION = "cp"
DEFAULT_ABI = "cp313"
DEFAULT_PLATFORM = "win_amd64"
ASSEMBLY_FILE_VERSION_PATTERN = (
    r'(\[assembly:\s*AssemblyFileVersion\(")([0-9.]+)("\)\])'
)
ASSEMBLY_VERSION_PATTERN = r'(\[assembly:\s*AssemblyVersion\(")([0-9.]+)("\)\])'
ASSEMBLY_VERSION_PATTERNS: tuple[str, ...] = (
    r'\[assembly:\s*AssemblyFileVersion\("([0-9.]+)"\)\]',
    r'\[assembly:\s*AssemblyVersion\("([0-9.]+)"\)\]',
)

REQUIRED_WHEELS: tuple[tuple[str, str], ...] = (
    ("cffi", "2.0.0"),
    ("clr_loader", "0.2.7.post0"),
    ("pycparser", "3.0"),
    ("pythonnet", "3.0.5"),
    ("networkx", "3.4.2"),
    ("scipy", "1.16.0"),
    ("pillow", "12.2.0"),
    ("py360convert", "1.0.4"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the io_scene_foundry extension wheels and regenerate "
            "blender_manifest.toml."
        )
    )
    parser.add_argument(
        "--manifest-path",
        default="blender_manifest.toml",
        help="Path to the manifest file to generate.",
    )
    parser.add_argument(
        "--wheels-dir",
        default="wheels",
        help="Directory used for downloaded wheel files.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Skip downloading and regenerate the manifest from existing wheels.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing wheel files when downloading.",
    )
    parser.add_argument(
        "--version",
        help="Override extension version written to the manifest.",
    )
    parser.add_argument(
        "--version-from-assembly-info",
        help=(
            "Read AssemblyFileVersion/AssemblyVersion from a C# AssemblyInfo.cs "
            "file and use it to set the manifest version."
        ),
    )
    parser.add_argument(
        "--bump-assembly-info-version",
        help=(
            "Increment the patch component of AssemblyVersion/AssemblyFileVersion "
            "in a C# AssemblyInfo.cs file before writing the manifest."
        ),
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON_VERSION,
        help=f"Target Python version for wheel download (default: {DEFAULT_PYTHON_VERSION}).",
    )
    parser.add_argument(
        "--implementation",
        default=DEFAULT_IMPLEMENTATION,
        help=f"Target Python implementation for wheels (default: {DEFAULT_IMPLEMENTATION}).",
    )
    parser.add_argument(
        "--abi",
        default=DEFAULT_ABI,
        help=f"Target Python ABI for wheels (default: {DEFAULT_ABI}).",
    )
    parser.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        help=f"Target platform tag for wheels (default: {DEFAULT_PLATFORM}).",
    )
    return parser.parse_args()


def resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_manifest_version(manifest_path: Path) -> str | None:
    if not manifest_path.exists():
        return None
    content = manifest_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', content, flags=re.MULTILINE)
    return match.group(1) if match else None


def to_manifest_version(version_text: str) -> str:
    numeric_parts = [str(part) for part in parse_numeric_version(version_text)]

    while len(numeric_parts) < 3:
        numeric_parts.append("0")

    return ".".join(numeric_parts[:3])


def parse_numeric_version(version_text: str) -> list[int]:
    parts = version_text.strip().split(".")
    if not parts:
        raise ValueError("Version is empty.")

    numeric_parts: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"Version part is not numeric: {part!r}")
        numeric_parts.append(int(part))

    return numeric_parts


def read_assembly_info_version(assembly_info_path: Path) -> str:
    if not assembly_info_path.exists():
        raise FileNotFoundError(f"AssemblyInfo file does not exist: {assembly_info_path}")

    text = assembly_info_path.read_text(encoding="utf-8")
    for pattern in ASSEMBLY_VERSION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return to_manifest_version(match.group(1))

    raise ValueError(
        f"Failed to find AssemblyFileVersion or AssemblyVersion in {assembly_info_path}"
    )


def bump_assembly_info_version(assembly_info_path: Path) -> str:
    if not assembly_info_path.exists():
        raise FileNotFoundError(f"AssemblyInfo file does not exist: {assembly_info_path}")

    text = assembly_info_path.read_text(encoding="utf-8")
    match = re.search(ASSEMBLY_VERSION_PATTERNS[0], text) or re.search(
        ASSEMBLY_VERSION_PATTERNS[1], text
    )
    if not match:
        raise ValueError(
            f"Failed to find AssemblyFileVersion or AssemblyVersion in {assembly_info_path}"
        )

    current_version = match.group(1)
    parts = parse_numeric_version(current_version)
    while len(parts) < 4:
        parts.append(0)

    parts[2] += 1
    parts[3] = 0
    bumped_version = ".".join(str(part) for part in parts[:4])

    updated_text, file_version_count = re.subn(
        ASSEMBLY_FILE_VERSION_PATTERN,
        rf"\g<1>{bumped_version}\g<3>",
        text,
    )
    updated_text, assembly_version_count = re.subn(
        ASSEMBLY_VERSION_PATTERN,
        rf"\g<1>{bumped_version}\g<3>",
        updated_text,
    )

    if file_version_count == 0 or assembly_version_count == 0:
        raise ValueError(
            "Failed to update AssemblyVersion and AssemblyFileVersion in "
            f"{assembly_info_path}"
        )

    assembly_info_path.write_text(updated_text, encoding="utf-8")
    manifest_version = to_manifest_version(bumped_version)
    print(
        f"Bumped {assembly_info_path} from {current_version} to {bumped_version} "
        f"(manifest {manifest_version})."
    )
    return manifest_version


def clear_existing_wheels(wheels_dir: Path) -> None:
    for wheel_path in wheels_dir.glob("*.whl"):
        wheel_path.unlink()


def download_wheels(args: argparse.Namespace, wheels_dir: Path) -> None:
    existing_wheels = {path.name for path in wheels_dir.glob("*.whl") if path.is_file()}
    missing_requirements = [
        (name, version)
        for name, version in REQUIRED_WHEELS
        if not any(
            (
                normalize_name(path_name.split("-")[0]) == normalize_name(name)
                and len(path_name.split("-")) >= 2
                and path_name.split("-")[1] == version
            )
            for path_name in existing_wheels
        )
    ]

    if not missing_requirements:
        print("All required wheels already exist. Skipping download.")
        return

    requirements = [f"{name}=={version}" for name, version in missing_requirements]
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--dest",
        str(wheels_dir),
        "--only-binary=:all:",
        "--no-deps",
        "--implementation",
        args.implementation,
        "--python-version",
        args.python_version,
        "--abi",
        args.abi,
        "--platform",
        args.platform,
        *requirements,
    ]
    subprocess.run(command, check=True)


def collect_required_wheels(wheels_dir: Path) -> list[str]:
    if not wheels_dir.exists():
        raise FileNotFoundError(f"Wheel directory does not exist: {wheels_dir}")

    wheel_files = [p for p in wheels_dir.glob("*.whl") if p.is_file()]
    selected: list[str] = []

    for package_name, package_version in REQUIRED_WHEELS:
        matches: list[Path] = []
        required_name = normalize_name(package_name)

        for wheel_path in wheel_files:
            parts = wheel_path.name.split("-")
            if len(parts) < 5:
                continue

            wheel_name = normalize_name(parts[0])
            wheel_version = parts[1]
            if wheel_name == required_name and wheel_version == package_version:
                matches.append(wheel_path)

        if not matches:
            raise FileNotFoundError(
                f"Missing wheel for requirement {package_name}=={package_version} "
                f"in {wheels_dir}"
            )

        if len(matches) > 1:
            matching_names = ", ".join(sorted(p.name for p in matches))
            raise RuntimeError(
                f"Multiple wheels match {package_name}=={package_version}: {matching_names}"
            )

        selected.append(matches[0].name)

    return selected


def render_manifest(version: str, wheel_files: list[str]) -> str:
    wheel_lines = "\n".join(
        (
            f'  "./wheels/{wheel_name}",'
            if index < len(wheel_files) - 1
            else f'  "./wheels/{wheel_name}"'
        )
        for index, wheel_name in enumerate(wheel_files)
    )
    return (
        'schema_version = "1.0.0"\n'
        "\n"
        'id = "io_scene_foundry"\n'
        f'version = "{version}"\n'
        'name = "Foundry"\n'
        'tagline = "An import & export pipeline for Halo Reach, Halo 4, and Halo 2 '
        'Anniversary Multiplayer"\n'
        'maintainer = "Crisp"\n'
        'type = "add-on"\n'
        "\n"
        'permissions = ["files", "clipboard"]\n'
        "\n"
        'website = "https://c20.reclaimers.net/general/community-tools/foundry/"\n'
        "\n"
        'tags = ["Import-Export", "Pipeline"]\n'
        "\n"
        'blender_version_min = "5.1.0"\n'
        "\n"
        'license = ["SPDX:GPL-3.0-or-later"]\n'
        "\n"
        'platforms = ["windows-amd64", "windows-x64"]\n'
        "\n"
        "wheels = [\n"
        f"{wheel_lines}\n"
        "]\n"
        "\n"
        "[build]\n"
        "paths_exclude_pattern = [\n"
        '  "/.git/",\n'
        '  "__pycache__/"\n'
        "]\n"
    )


def main() -> int:
    args = parse_args()
    addon_root = Path(__file__).resolve().parent
    manifest_path = resolve_path(addon_root, args.manifest_path)
    wheels_dir = resolve_path(addon_root, args.wheels_dir)
    bumped_manifest_version: str | None = None

    # if args.bump_assembly_info_version:
    #     bump_path = resolve_path(addon_root, args.bump_assembly_info_version)
    #     bumped_manifest_version = bump_assembly_info_version(bump_path)

    wheels_dir.mkdir(parents=True, exist_ok=True)
    if not args.manifest_only:
        if not args.keep_existing:
            clear_existing_wheels(wheels_dir)
        download_wheels(args, wheels_dir)

    wheel_files = collect_required_wheels(wheels_dir)
    version = args.version
    if version is None and bumped_manifest_version is not None:
        version = bumped_manifest_version
    if version is None and args.version_from_assembly_info:
        assembly_info_path = resolve_path(addon_root, args.version_from_assembly_info)
        version = read_assembly_info_version(assembly_info_path)
    if version is None:
        version = read_manifest_version(manifest_path)
    if version is None:
        version = DEFAULT_MANIFEST_VERSION

    version = to_manifest_version(version)
    manifest_contents = render_manifest(version=version, wheel_files=wheel_files)
    manifest_path.write_text(manifest_contents, encoding="utf-8", newline="\n")

    print(f"Wrote {manifest_path} with {len(wheel_files)} wheel entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
