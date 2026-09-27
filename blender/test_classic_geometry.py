"""Blender --background --factory-startup --python this_file (optional -- --b40)."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from zipfile import ZipFile

import bpy
import numpy as np
from mathutils import Matrix

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(wheels.name)
sys.path.insert(0, wheels.name)
from io_scene_foundry import props, utils, import_transform
from io_scene_foundry.tags.classic_geometry import merge_classic_surfaces
from io_scene_foundry.tags.backend import TagDocument

utils.get_project = lambda *a, **k: SimpleNamespace(game='halo1', corinth=False)
props.register()


def mesh(points, faces, material):
    result = bpy.data.meshes.new('merge_test')
    result.from_pydata(points, [], faces)
    result.materials.append(material)
    return result


def marked(result):
    return {i for prop in result.nwo.face_props if prop.type == 'face_mode'
            for i, value in enumerate(result.attributes[prop.attribute_name].data) if value.value}


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.material = bpy.data.materials.new('wall')
        self.points = [(0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10)]
        self.faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]

    def pair(self, points, material=None):
        return mesh(self.points, self.faces, self.material), mesh(points, self.faces, material or self.material)

    def test_connected_compiler_corner(self):
        r, c = self.pair([(0.0012, 0, 0), *self.points[1:]])
        merge_classic_surfaces(r, c, 0.000762)
        self.assertFalse(marked(r))
        self.assertEqual(len(c.polygons), 0)

    def test_disconnected_offset_shell_is_not_merged(self):
        r, c = self.pair([(x + .0012, y + .0012, z + .0012) for x, y, z in self.points])
        merge_classic_surfaces(r, c, 0.000762)
        self.assertEqual(len(marked(r)), 4)
        self.assertEqual(len(c.polygons), 4)

    def test_larger_authored_displacement_is_not_merged(self):
        r, c = self.pair([(0.01, 0.01, 0.01), *self.points[1:]])
        merge_classic_surfaces(r, c, 0.000762)
        self.assertTrue(marked(r))
        self.assertGreater(len(c.polygons), 0)

    def test_distinct_materials_remain_separate(self):
        r, c = self.pair([(0.0012, 0, 0), *self.points[1:]], bpy.data.materials.new('detail'))
        merge_classic_surfaces(r, c, 0.000762)
        self.assertEqual(len(marked(r)), 4)
        self.assertEqual(len(c.polygons), 4)

    @unittest.skipUnless('--b40' in sys.argv, 'Optional real HCEEK b40 fixture')
    def test_b40_selected_wrl_corner(self):
        root = r'G:\Halo\Modding\Main\HCEEK\tags'
        with TagDocument('levels/b40/b40_c1.scenario_structure_bsp', tags_root=root,
                         game='halo1', must_exist=True) as tag:
            scene = tag.tag.classic_sbsp_scene()
        bpy.context.scene.nwo.scale = 'blender'
        bpy.context.scene.nwo.forward_direction = 'y-'
        materials = []
        for name, path in zip(scene['materials'], scene['material_paths']):
            material = bpy.data.materials.new(name)
            material.nwo['shader_path'] = path
            materials.append(material)
        meshes = []
        for raw in scene['objects']:
            result = bpy.data.meshes.new('b40_source')
            result.from_pydata(raw['positions'], [], np.array(raw['indices']).reshape(-1, 3).tolist())
            # Match the importer's separate local scale and object rotation.
            result.transform(import_transform.mesh_matrix() @ Matrix.Scale(100, 4))
            result.transform(import_transform.rotation_matrix())
            for material in materials:
                result.materials.append(material)
            for part in raw['parts']:
                for face in result.polygons[part['index_start']//3:(part['index_start']+part['index_count'])//3]:
                    face.material_index = part['material_index']
            meshes.append(result)
        merge_classic_surfaces(*meshes, 0.000762)
        point = np.array((-2167.5, -865, 190))
        checked = 0
        for result in meshes:
            flags = marked(result)
            for face in result.polygons:
                material = result.materials[face.material_index]
                coords = np.array([tuple(result.vertices[v].co) for v in face.vertices])
                if (material.name.startswith('metal strips wide a')
                        and np.min(np.linalg.norm(coords-point, axis=1)) < 8):
                    self.assertNotIn(face.index, flags)
                    checked += 1
        self.assertGreater(checked, 0)
        render = meshes[0]
        self.assertTrue(any(render.materials[render.polygons[i].material_index].name.startswith('c10light')
                            for i in marked(render)))


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Classic geometry regression tests failed')
