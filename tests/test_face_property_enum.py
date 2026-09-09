"""Run with Python, or Blender --background --factory-startup --python this_file."""
import ast
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'face_mode': 0, 'render_only': 1, 'collision_only': 2, 'sphere_collision_only': 3, 'breakable': 4, 'lightmap_only': 5, 'face_sides': 7, 'transparent': 8, 'region': 9, 'draw_distance': 10, 'global_material': 11, 'ladder': 12, 'slip_surface': 13, 'decal_offset': 14, 'no_shadow': 15, 'precise_position': 16, 'uncompressed': 17, 'additional_compression': 18, 'no_lightmap': 19, 'no_pvs': 20, 'mesh_tessellation_density': 21, 'lightmap_resolution_scale': 22, 'lightmap_ignore_default_resolution_scale': 23, 'lightmap_chart_group': 24, 'lightmap_type': 25, 'lightmap_additive_transparency': 26, 'lightmap_transparency_override': 27, 'lightmap_analytical_bounce_modifier': 28, 'lightmap_general_bounce_modifier': 29, 'lightmap_translucency_tint_color': 30, 'lightmap_lighting_from_both_sides': 31, 'emissive': 32}


def enum_items():
    source = (ROOT / 'blender/addons/io_scene_foundry/constants.py').read_text()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'face_prop_type_items'
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError('Missing face property enum')


class FacePropertyEnumTests(unittest.TestCase):
    def test_legacy_numbers(self):
        items = enum_items()
        actual = {item[0]: item[3] for item in items}
        for name, number in EXPECTED.items():
            self.assertEqual(actual[name], number, name)
        self.assertNotIn('collision_type', actual)
        self.assertNotIn(6, actual.values())
        self.assertEqual(len(set(actual.values())), len(items))

    def test_blender_saved_values(self):
        try:
            import bpy
        except ImportError:
            self.skipTest('Run inside Blender to verify saved RNA values')

        class SavedFaceProperty(bpy.types.PropertyGroup):
            type: bpy.props.EnumProperty(items=enum_items())

        bpy.utils.register_class(SavedFaceProperty)
        for owner_type in (bpy.types.Mesh, bpy.types.Material):
            owner_type.enum_regression = bpy.props.CollectionProperty(type=SavedFaceProperty)
        try:
            mesh = bpy.data.meshes.new('enum_regression')
            material = bpy.data.materials.new('enum_regression')
            for owner in (mesh, material):
                owner.use_fake_user = True
                for name, number in EXPECTED.items():
                    prop = owner.enum_regression.add()
                    prop['type'] = number
                    self.assertEqual(prop.type, name)
            with tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / 'enum.blend')
                bpy.ops.wm.save_as_mainfile(filepath=path)
                bpy.ops.wm.open_mainfile(filepath=path)
                for owner in (bpy.data.meshes['enum_regression'], bpy.data.materials['enum_regression']):
                    self.assertEqual([p.type for p in owner.enum_regression], list(EXPECTED))
        finally:
            del bpy.types.Mesh.enum_regression
            del bpy.types.Material.enum_regression
            bpy.utils.unregister_class(SavedFaceProperty)


if __name__ == '__main__':
    unittest.main(argv=[__file__])
