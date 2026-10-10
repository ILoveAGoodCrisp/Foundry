"""Export Foundry's authored declarations for the compiled writer's build input."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'blender/addons/io_scene_foundry'))
from granny_export.standard_schemas import STANDARD_DEFINITIONS, curve_definitions

def generate():
    definitions = {**STANDARD_DEFINITIONS, **curve_definitions()}
    result = [{'name': name, 'members': [{'name': field.name, 'kind': int(field.kind),
        'width': field.width, 'reference': field.reference, 'extra': field.extra} for field in fields]}
        for name, fields in definitions.items()]
    destination = ROOT/'rust/granny_writer/src/standard_schemas.json'
    destination.write_text(json.dumps(result, separators=(',', ':'))+'\n', encoding='utf-8')
    print(f'Generated {len(result)} authored schema declarations: {destination}')

if __name__ == '__main__': generate()
