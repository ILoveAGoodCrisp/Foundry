"""Build the local Rust writer wheel for Foundry; never install globally."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--output', type=Path, default=ROOT/'blender/addons/io_scene_foundry/wheels')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--target', help='Optional Rust target triple; requires its compiler/linker toolchain')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.python, str(ROOT/'blender/generate_granny_rust_schemas.py')], check=True)
    env = dict(os.environ)
    env.setdefault('CARGO_TARGET_DIR', str(ROOT/'blender/output/granny_rust_build/target'))
    command = [args.python, '-m', 'maturin', 'build', '--release', '--locked', '--manifest-path',
        str(ROOT/'rust/granny_writer/Cargo.toml'), '--interpreter', args.python, '--out', str(args.output)]
    if args.offline: command.append('--offline')
    if args.target: command.extend(('--target', args.target))
    subprocess.run(command, env=env, check=True)

if __name__ == '__main__': main()
