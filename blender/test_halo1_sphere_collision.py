"""Run with Blender --background --factory-startup --python this_file."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest

runpy.run_path(str(Path(__file__).with_name('test_classic_geometry.py')), run_name='bootstrap')
import bpy
from mathutils import Matrix, Vector
from io_scene_foundry import utils, import_transform
from io_scene_foundry.tags.halo1_bsp_blender import apply_collision_surface_flags, replace_collision_only


class SphereCollisionTests(unittest.TestCase):
    def test_invisible_surface_overrides_collision_only(self):
        points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (3, 0, 0), (4, 0, 0), (3, 1, 0)]
        edges = []
        for surface in range(2):
            for i in range(3):
                edges.append({'left surface': surface, 'start vertex': surface*3+i,
                              'forward edge': surface*3+(i+1)%3})
        bsp = {'vertices': [{'point': SimpleNamespace(to_array=lambda p=p: p)} for p in points],
               'edges': edges,
               'surfaces': [{'first edge': i*3, 'flags': SimpleNamespace(
                   get_flag=lambda name, i=i: name == 'invisible' and i == 0)} for i in range(2)]}
        root = {'collision bsp': [bsp], 'breakable surfaces': []}
        tag = SimpleNamespace(tag=SimpleNamespace(root=lambda: root),
                              block=lambda struct, name: struct[name],
                              value=lambda struct, name: struct[name],
                              required_field=lambda struct, name: struct[name])
        mesh = bpy.data.meshes.new('sphere_collision_test')
        mesh.nwo.mesh_type = '_connected_geometry_mesh_type_structure'
        transform = import_transform.transform_matrix(Matrix.Identity(4))
        mesh.from_pydata([transform @ (Vector(p)*100) for p in points], [], [(0, 1, 2), (3, 4, 5)])
        # A material-less native collision slot must not become +sky for '*'.
        mesh.materials.append(bpy.data.materials.new('default'))
        ob = bpy.data.objects.new('sphere_collision_test', mesh)
        utils.add_face_prop(mesh, 'face_mode').face_mode = 'collision_only'
        apply_collision_surface_flags(tag, [ob])
        modes = {p.face_mode: [v.value for v in mesh.attributes[p.attribute_name].data]
                 for p in mesh.nwo.face_props if p.type == 'face_mode'}
        self.assertEqual(modes, {'collision_only': [False, True], 'sphere_collision_only': [True, False]})
        replace_collision_only([ob])
        self.assertEqual(mesh.materials[mesh.polygons[0].material_index].name, 'default')
        self.assertEqual(mesh.materials[mesh.polygons[1].material_index].name, '+sky')
        self.assertTrue(any(p.face_mode == 'sphere_collision_only' for p in mesh.nwo.face_props))


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('H1 sphere collision tests failed')
