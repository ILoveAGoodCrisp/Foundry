"""Refresh VS Code's blam-tags stubs from the extension's packaged wheel.

Run with the same Python/platform compatibility required by the wheel. No
installation of blam-tags or Blender is needed.
"""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import zipfile


# Import in a separate process so an already loaded/installed blam-tags cannot
# supply documentation for a different version of the staged wheel.
_READ_DOCS = """
import ast
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
import blam_tags

tree = ast.parse(Path(sys.argv[1], 'blam_tags/__init__.pyi').read_text(encoding='utf-8'))
docs = {}
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        owner = getattr(blam_tags, node.name)
        members = node.body
        prefix = node.name + '.'
    elif isinstance(node, ast.FunctionDef):
        owner = blam_tags
        members = [node]
        prefix = ''
    else:
        continue
    for member in members:
        if isinstance(member, ast.FunctionDef) and member.name in vars(owner):
            doc = inspect.getdoc(getattr(owner, member.name))
            if doc:
                docs[prefix + member.name] = doc
print(json.dumps(docs))
"""


def stage_typings(wheel: Path, destination: Path) -> None:
    """Keep wheel signatures and add the native methods' hover descriptions."""
    with zipfile.ZipFile(wheel) as archive:
        source = archive.read('blam_tags/__init__.pyi').decode('utf-8')
        source = source.replace('\r\n', '\n').replace('\r', '')
        with tempfile.TemporaryDirectory(prefix='foundry-blam-typings-') as folder:
            archive.extractall(folder)
            result = subprocess.run(
                [sys.executable, '-I', '-c', _READ_DOCS, folder],
                check=True, capture_output=True, text=True, encoding='utf-8')
            docs = json.loads(result.stdout)

    lines = source.splitlines(keepends=True)
    edits = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            members, prefix = node.body, node.name + '.'
        elif isinstance(node, ast.FunctionDef):
            members, prefix = [node], ''
        else:
            continue
        for member in members:
            if not isinstance(member, ast.FunctionDef) or ast.get_docstring(member):
                continue
            doc = docs.get(prefix + member.name)
            if not doc or len(member.body) != 1:
                continue
            body = member.body[0]
            if not (isinstance(body, ast.Expr)
                    and isinstance(body.value, ast.Constant)
                    and body.value.value is Ellipsis):
                continue
            # AST columns count UTF-8 bytes, not Unicode characters.
            line = lines[body.lineno - 1]
            column = len(line.encode('utf-8')[:body.col_offset].decode('utf-8'))
            offset = sum(map(len, lines[:body.lineno - 1])) + column
            start = offset
            while source[start - 1] in ' \t':
                start -= 1
            escaped = doc.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
            replacement = '\n' + textwrap.indent(
                '"""' + escaped + '"""\n...', ' ' * (member.col_offset + 4))
            edits.append((start, offset + 3, replacement))
    for start, end, replacement in reversed(edits):
        source = source[:start] + replacement + source[end:]
    source = (
        f'# Generated from {wheel.name}; includes native method documentation.\n'
        '# Refresh with: python blender/update_blam_tags_typings.py\n'
        + source)
    ast.parse(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source, encoding='utf-8', newline='\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, help='Use this wheel instead of the manifest entry')
    args = parser.parse_args()
    blender = Path(__file__).resolve().parent
    addon = blender / 'addons/io_scene_foundry'
    wheel = args.wheel
    if wheel is None:
        manifest = tomllib.loads((addon / 'blender_manifest.toml').read_text(encoding='utf-8'))
        wheel, = (addon / name for name in manifest['wheels']
                  if Path(name).name.startswith('blam_tags-'))
    destination = blender.parent / 'typings/blam_tags/__init__.pyi'
    stage_typings(wheel, destination)
    print(f'Refreshed {destination} from {wheel.name}.')


if __name__ == '__main__':
    main()
