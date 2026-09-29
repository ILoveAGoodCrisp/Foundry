"""Blender --background --factory-startup --python this_file."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest

runpy.run_path(str(Path(__file__).with_name('test_classic_geometry.py')), run_name='bootstrap')
import bpy
from io_scene_foundry import utils
from io_scene_foundry.export.virtual_geometry import gather_face_props, MeshType, AssetType
from io_scene_foundry.export.legacy_materials import material_variant


class H1TransparencyExportTests(unittest.TestCase):
    def test_face_index_is_not_treated_as_material_slot(self):
        mesh = bpy.data.meshes.new('transparent_indices_test')
        points = [(i*3+j, 0, 0) if j < 2 else (i*3, 1, 0)
                  for i in range(6) for j in range(3)]
        mesh.from_pydata(points, [], [tuple(range(i*3, i*3+3)) for i in range(6)])
        for index in range(6):
            mesh.materials.append(bpy.data.materials.new('+sky' if index == 5 else f'mat{index}'))
            mesh.polygons[index].material_index = index if index < 5 else 0
        mesh.polygons[4].material_index = 5  # Sky uses slot 5.
        prop = utils.add_face_prop(mesh, 'transparent', [0, 0, 0, 0, 0, 1])
        prop.transparent = True  # Only face 5 is transparent; it uses slot 0.
        scene = SimpleNamespace(game='halo1', corinth=False, asset_type=AssetType.SCENARIO,
                                regions={}, global_materials={})
        values = gather_face_props(mesh.nwo, mesh, len(mesh.polygons), scene, None,
                                   {mesh.materials[5]: [5]}, {},
                                   {'bungie_mesh_type': MeshType.default.value}, False, [])
        sides = values['bungie_face_sides'].array
        self.assertEqual(sides.tolist(), [0, 0, 0, 0, 0, 1])

    def test_h1_helpers_cannot_inherit_face_suffixes(self):
        for shader in ('+sky', '+seamsealer', '+portal', '+weatherpoly'):
            with self.subTest(shader=shader):
                name, _ = material_variant(shader, {'bungie_face_sides': 1,
                    'bungie_face_mode': 2}, target_game='halo1')
                self.assertEqual(name, shader)
        self.assertEqual(material_variant('+unused', {'bungie_mesh_type': 15},
                         target_game='halo1')[0], '+unused$')


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('H1 transparency export regression tests failed')
