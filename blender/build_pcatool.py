"""Build the standalone Windows PCA solver into the extension's resources."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'x86_64-pc-windows-msvc'


def write_dependency_licenses(cargo, manifest, env, destination):
    metadata = json.loads(subprocess.check_output(
        [cargo, 'metadata', '--format-version', '1', '--locked', '--offline',
         '--filter-platform', TARGET, '--manifest-path', str(manifest)], env=env))
    dependencies = {node['id'] for node in metadata['resolve']['nodes']}
    sections = ["Third-party licenses for Foundry pcatool.exe\n"]
    for package in sorted(metadata['packages'], key=lambda p: p['name']):
        if package['id'] not in dependencies or package['source'] is None:
            continue
        root = Path(package['manifest_path']).parent
        license_files = sorted(set(root.glob('LICENSE*')) | set(root.glob('COPYING*')))
        if package.get('license_file'):
            license_files.append(root / package['license_file'])
        license_files = [path for path in license_files if path.is_file()]
        if not license_files:
            raise RuntimeError(f"No license text found for {package['name']}")
        sections.append(f"\n{'=' * 72}\n{package['name']} {package['version']} ({package['license']})\n")
        for path in license_files:
            sections.append(f'\n{path.name}\n\n{path.read_text(encoding="utf-8")}\n')
    destination.write_text(''.join(sections), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    cargo = shutil.which('cargo')
    if not cargo:
        candidate = Path(os.environ.get('CARGO_HOME', Path.home() / '.cargo')) / 'bin/cargo.exe'
        if candidate.is_file():
            cargo = str(candidate)
        else:
            parser.error('Install the Rust MSVC toolchain and Visual Studio C++ build tools to build pcatool.exe')
    target_dir = ROOT / 'blender/output/pcatool_build/target'
    env = dict(os.environ, CARGO_TARGET_DIR=str(target_dir))
    # Statically link the C runtime, so the editing kit needs no runtime install.
    env['CARGO_ENCODED_RUSTFLAGS'] = '-C\x1ftarget-feature=+crt-static'
    manifest = ROOT / 'rust/pcatool/Cargo.toml'
    command = [cargo, 'build', '--release', '--locked', '--target', TARGET,
               '--manifest-path', str(manifest)]
    if args.offline:
        command.append('--offline')
    subprocess.run(command, env=env, check=True)
    source = target_dir / TARGET / 'release/pcatool.exe'
    destination = ROOT / 'blender/addons/io_scene_foundry/resources/pcatool.exe'
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_dependency_licenses(cargo, manifest, env, destination.with_name('pcatool-LICENSES.txt'))
    shutil.copy2(source, destination)
    subprocess.run([str(destination), '--version'], check=True)
    print(f'Packaged PCA solver: {destination}')


if __name__ == '__main__':
    main()
