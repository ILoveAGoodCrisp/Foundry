"""Build and stage blam-tags and generated schemas for the Foundry extension.

Run with a Python environment containing maturin; Rust and MSVC are required.
The source checkout is copied to a temporary directory and never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

PROFILES = ('haloce_mcc', 'halo2_mcc', 'halo3_mcc', 'halo3odst_mcc',
            'haloreach_mcc', 'halo4_mcc', 'halo2amp_mcc')
SCHEMAS = ('scenario.json', 'scenario_cinematics_resource.json',
           'scenario_structure_bsp.json', 'scenario_structure_lighting_info.json',
           'frame_event_list.json', 'model_animation_graph.json',
           'structure_design.json', 'cinematic.json', 'cinematic_transition.json',
           'cinematic_scene.json', 'cinematic_scene_data.json', 'polyart_asset.json',
           'decorator_set.json', 'particle_emitter_custom_points.json', 'prefab.json',
           'multiplayer_object_type_list.json',
           'camera_track.json', 'bitmap.json', 'globals.json', 'render_method_option.json',
           'render_method_definition.json', 'material_shader.json', 'model.json',
           'sound_effect_collection.json', 'sound_classes.json', 'cache_file_sound.json',
           'render_method.json', 'material.json', 'shader.json', 'shader_cortana.json',
           'shader_custom.json', 'shader_decal.json', 'shader_foliage.json',
           'shader_fur.json', 'shader_fur_stencil.json', 'shader_glass.json',
           'shader_halogram.json', 'shader_mux.json', 'shader_mux_material.json',
           'shader_screen.json', 'shader_skin.json', 'shader_terrain.json',
           'shader_water.json',
           'render_model.json', 'lightmapper_globals.json', 'new_cinematic_lighting.json', '_meta.json',
           'object.json', 'item.json', 'unit.json', 'device.json',
           'scenery.json', 'weapon.json', 'biped.json', 'vehicle.json',
           'equipment.json', 'crate.json', 'creature.json', 'giant.json',
           'device_dispenser.json', 'spawner.json',
           'device_machine.json', 'device_control.json', 'device_terminal.json', 'projectile.json',
           'sound_scenery.json', 'effect_scenery.json', 'light.json', 'cheap_light.json',
           'structure_seams.json', 'structure_meta.json', 'pca_animation.json', 'collision_model.json', 'physics_model.json',
           'camera_fx_settings.json', 'area_screen_effect.json', 'ssao_definition.json',
           'atmosphere_globals.json', 'sky_atm_parameters.json', 'chocolate_mountain_new.json')


def stage_schemas(source, addon):
    hashes = {}
    for profile in PROFILES:
        destination = addon / 'tags/definitions' / profile
        destination.mkdir(parents=True, exist_ok=True)
        names = set(SCHEMAS)
        if profile in {'haloce_mcc', 'halo2_mcc'}:
            names.update(path.name for path in (source / 'definitions' / profile).glob('*.json'))
        for name in sorted(names):
            schema = source / 'definitions' / profile / name
            if not schema.is_file():
                if name in ('camera_track.json', '_meta.json'):
                    raise FileNotFoundError(schema)
                continue  # Not every title has every tag group.
            shutil.copy2(schema, destination / name)
            hashes[f'{profile}/{name}'] = hashlib.sha256(schema.read_bytes()).hexdigest()
    return hashes


def validate_wheel(wheel):
    """Fail before staging when a checkout lacks APIs used by migrated workflows."""
    with tempfile.TemporaryDirectory(prefix='foundry-blam-check-') as folder:
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(folder)
        script = """
import sys
sys.path.insert(0, sys.argv[1])
import blam_tags as api
required = {
    'TagFile': ('read', 'read_classic', 'new', 'new_classic', 'write_atomic', 'particle_meshes', 'physics_shapes_h2', 'bitmap_tiff',
                'render_model_meshes', 'sbsp_render_meshes', 'classic_sbsp_scene',
                'animation_pose', 'animation_pose_classic'),
    'TagField': ('options', 'as_array', 'copy_value_from'),
    'TagBlock': ('copy_from',),
    'TagStruct': ('raw_bytes',),
    'TagFunctionEditor': ('describe', 'evaluate', 'evaluate_shape',
                          'set_master_type', 'set_color_graph_type',
                          'set_color', 'set_clamp_range'),
}
missing = [f'{cls}.{method}' for cls, methods in required.items()
           for method in methods if not hasattr(getattr(api, cls, None), method)]
if missing:
    raise RuntimeError('blam-tags build lacks required Foundry APIs: ' + ', '.join(missing))
"""
        subprocess.run([sys.executable, '-c', script, folder], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--schemas-only', action='store_true',
                        help='Refresh generated schemas without rebuilding the wheel')
    args = parser.parse_args()
    source = args.source.resolve()
    addon = Path(__file__).resolve().parent / 'addons/io_scene_foundry'
    if args.schemas_only:
        hashes = stage_schemas(source, addon)
        provenance_path = addon / 'tags/definitions/build.json'
        provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
        provenance['schemas'] = hashes
        provenance_path.write_text(json.dumps(provenance, indent=2) + '\n')
        print(f'Staged {len(hashes)} schema assets.')
        return
    with tempfile.TemporaryDirectory(prefix='foundry-blam-') as folder:
        checkout = Path(folder)
        for name in ('blam-tags', 'blam-tags-py', 'blam-tags-bindgen', 'blam-tag-shell'):
            shutil.copytree(source / name, checkout / name,
                            ignore=shutil.ignore_patterns('target', '__pycache__', 'dist'))
        shutil.copy2(source / 'Cargo.toml', checkout / 'Cargo.toml')
        if (source / 'Cargo.lock').exists():
            shutil.copy2(source / 'Cargo.lock', checkout / 'Cargo.lock')
        subprocess.run([sys.executable, '-m', 'maturin', 'build', '--release',
                        '-m', str(checkout / 'blam-tags-py/Cargo.toml'),
                        '-o', str(checkout / 'dist')], check=True, cwd=checkout)
        wheels = list((checkout / 'dist').glob('*.whl'))
        if len(wheels) != 1:
            raise RuntimeError(f'Expected one wheel, got {wheels}')
        wheel = wheels[0]
        validate_wheel(wheel)
        (addon / 'wheels').mkdir(exist_ok=True)
        shutil.copy2(wheel, addon / 'wheels' / wheel.name)
        hashes = stage_schemas(source, addon)
        provenance = {'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                      'schemas': hashes}
        (addon / 'tags/definitions/build.json').write_text(json.dumps(provenance, indent=2) + '\n')
        manifest = addon / 'blender_manifest.toml'
        text = manifest.read_text()
        entry = f'  "./wheels/{wheel.name}",'
        text = re.sub(r'(?m)^  "\./wheels/blam_tags-[^"]+",?\r?\n', '', text)
        text = text.replace('wheels = [', 'wheels = [\n' + entry, 1)
        manifest.write_text(text)
        print(f'Staged {wheel.name} and {len(hashes)} schema assets for migrated features.')


if __name__ == '__main__':
    main()
