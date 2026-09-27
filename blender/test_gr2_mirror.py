"""Run with Blender --background --factory-startup --python-exit-code 1 --python this_file.py.

Optionally set FOUNDRY_TEST_GRANNY_DLL to also exercise native conversion and GR2 I/O.
The export modules are real; unrelated UI/tag dependencies are stubbed.
"""

import ctypes as ct
import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

import bpy
from mathutils import Euler, Matrix, Vector
import numpy as np


ADDON = Path(__file__).resolve().parent / 'addons' / 'io_scene_foundry'
PACKAGE = 'gr2_mirror_test_foundry'


def stub(name, **attributes):
    module = types.ModuleType(PACKAGE + ('.' + name if name else ''))
    module.__dict__.update(attributes)
    module.__path__ = [str(ADDON / name.replace('.', '/'))]
    sys.modules[module.__name__] = module
    return module


stub('')
for name in ('export', 'props', 'tags', 'tools', 'legacy'):
    stub(name)
stub('utils', ExportObject=bpy.types.Object, get_version=lambda: (1, 0, 0),
     print_warning=print, get_halo_props_for_granny=lambda props: props)
stub('props.scene', NWO_ScenePropertiesGroup=object)
stub('props.mesh', NWO_MeshPropertiesGroup=object)
stub('tags.bitmap', BitmapTag=object)
stub('tags.shader', MaterialMetadataTag=object, ShaderMetadataTag=object)
stub('tools.asset_types', AssetType=object)
stub('export.cinematic', Actor=object, Frame=object)
vg = importlib.import_module(PACKAGE + '.export.virtual_geometry')
granny_module = importlib.import_module(PACKAGE + '.granny')
formats = importlib.import_module(PACKAGE + '.granny.formats')
exports = importlib.import_module(PACKAGE + '.granny.export_classes')
mirror = importlib.import_module(PACKAGE + '.granny.mirror')
legacy = importlib.import_module(PACKAGE + '.legacy.mirror')


def transform(x=0.4):
    return Matrix.LocRotScale(Vector((2, 3, 5)), Euler((x, -0.6, 0.8)).to_quaternion(), Vector((1, 2, 3)))


def unpack_transform(value):
    from mathutils import Quaternion
    x, y, z, w = value.orientation
    return (Matrix.Translation(Vector(value.position)) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
            @ Matrix(value.scale_shear).to_4x4())


def mesh_fixture():
    mesh = vg.VirtualMesh.__new__(vg.VirtualMesh)
    mesh.positions = np.array(((1, 2, 3), (4, 2, 3), (1, 6, 5)), dtype=np.float32)
    mesh.normals = np.tile(np.array((0, -1, 2), dtype=np.float32) / np.sqrt(5), (3, 1))
    mesh.bone_weights = np.tile(np.array((255, 0, 0, 0), dtype=np.uint8), (3, 1))
    mesh.bone_indices = np.zeros((3, 4), dtype=np.uint8)
    mesh.texcoords = [np.array(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32)]
    mesh.lighting_texcoords = None
    mesh.vertex_colors = [np.full((3, 3), 0.7, dtype=np.float32)]
    mesh.tension = mesh.pca_mask = mesh.vertex_ids = None
    mesh.indices = np.array((0, 1, 2), dtype=np.int32)
    mesh.pca_indices = mesh.indices.copy()
    mesh.groups = []
    mesh.face_properties = {}
    mesh.num_vertices = 3
    return mesh


class MirrorTests(unittest.TestCase):
    def assertMatrix(self, actual, expected):
        np.testing.assert_allclose(actual, expected, atol=2e-6)

    def test_mesh_and_morph_serializers_preserve_source_and_attributes(self):
        mesh = mesh_fixture()
        original = mesh.positions.copy()
        plain = types.SimpleNamespace(mirror=False, corinth=False)
        reflected = types.SimpleNamespace(mirror=True, corinth=False)
        _, _, _, dtypes = mesh._vertex_data_arrays(plain)
        for _ in range(2):  # Linked/repeated export must not reflect shared arrays twice.
            _, _, buffer, _, _ = mesh._make_vertex_array(reflected)
            actual = np.frombuffer(buffer, dtype=dtypes)
            _, _, buffer_plain, _, _ = mesh._make_vertex_array(plain)
            expected = np.frombuffer(buffer_plain, dtype=dtypes)
            for name in actual.dtype.names:
                target = mirror.mirror_vectors(expected[name]) if name in ('Position', 'Normal') else expected[name]
                np.testing.assert_array_equal(actual[name], target)
        np.testing.assert_array_equal(mesh.positions, original)

        morph = vg.VirtualMorphTargetData.__new__(vg.VirtualMorphTargetData)
        morph.positions, morph.normals, morph.tension = mesh.positions, mesh.normals, None
        morph._granny_vertex_data(reflected)
        actual = np.frombuffer(morph.vertex_array, dtype=[('Position', 'f4', 3), ('Normal', 'f4', 3)])
        np.testing.assert_array_equal(actual['Position'], mirror.mirror_vectors(original))
        np.testing.assert_array_equal(mesh.positions, original)

    def test_winding_for_regular_pca_and_negative_scale(self):
        mesh = mesh_fixture()
        mesh.to_granny_data(types.SimpleNamespace(mirror=True, corinth=False))
        for topology in (mesh.granny_tri_topology, mesh.pca_granny_tri_topology):
            self.assertEqual(list(topology.contents.indices[:3]), [0, 2, 1])
        np.testing.assert_array_equal(mesh.indices, (0, 1, 2))
        vertices = mirror.mirror_vectors(mesh.positions)
        normal = np.cross(vertices[2] - vertices[0], vertices[1] - vertices[0])
        self.assertGreater(np.dot(normal, mirror.mirror_vectors(mesh.normals)[0]), 0)
        # A second winding reversal (negative object determinant) cancels reflection's reversal.
        np.testing.assert_array_equal(mirror.mirror_indices(mirror.mirror_indices(mesh.indices)), mesh.indices)

    def test_skeleton_hierarchy_bind_pose_and_model(self):
        parent = transform()
        child_local = transform(-0.3)
        child_world = parent @ child_local
        for local, world in ((parent, parent), (child_local, child_world)):
            bone = vg.VirtualBone.__new__(vg.VirtualBone)
            bone.name, bone.parent_index = 'bone', -1
            bone.matrix_local, bone.matrix_world = local, world
            bone.granny_bone = formats.GrannyBone()
            bone.to_granny_data(types.SimpleNamespace(mirror=True))
            self.assertMatrix(unpack_transform(bone.granny_bone.local_transform), mirror.mirror_matrix(local))
            inverse = Matrix(bone.granny_bone.inverse_world_4x4).transposed()
            self.assertMatrix(inverse @ mirror.mirror_matrix(world), Matrix.Identity(4))
        self.assertMatrix(mirror.mirror_matrix(parent) @ mirror.mirror_matrix(child_local), mirror.mirror_matrix(child_world))
        model = exports.Model(types.SimpleNamespace(name='model', node=types.SimpleNamespace(matrix_local=parent)), 0, [], True)
        self.assertMatrix(unpack_transform(model.initial_placement), mirror.mirror_matrix(parent))

    def test_animation_samples_match_legacy_and_preserve_scale_shear(self):
        positions, orientations, scales = [], [], []
        for matrix in (transform(), transform(-0.7)):
            loc, rot, scale = matrix.decompose()
            positions.extend(loc)
            orientations.extend((rot.x, rot.y, rot.z, rot.w))
            scales.extend((scale.x, 0.2, 0.3, 0.4, scale.y, 0.5, 0.6, 0.7, scale.z))
        tracks = [(ct.c_float * len(values))(*values) for values in (positions, orientations, scales)]
        original = [np.ctypeslib.as_array(values).copy() for values in tracks]
        mirror.mirror_tracks(tracks)
        for i in range(2):
            value = types.SimpleNamespace(translation=positions[i*3:i*3+3], rotation=orientations[i*4:i*4+4])
            legacy.mirror_transform(value)
            np.testing.assert_allclose(tracks[0][i*3:i*3+3], value.translation)
            np.testing.assert_allclose(tracks[1][i*4:i*4+4], value.rotation)
            scale = np.array(scales[i*9:i*9+9]).reshape(3, 3)
            self.assertMatrix(np.array(tracks[2][i*9:i*9+9]).reshape(3, 3), np.diag((1, -1, 1)) @ scale @ np.diag((1, -1, 1)))
        mirror.mirror_tracks(tracks)
        for actual, expected in zip(tracks, original):
            np.testing.assert_array_equal(actual, expected)

    def test_geometry_object_transform_agrees_with_reflected_world_position(self):
        source = Vector((7, -2, 4, 1))
        for scale in (1, -1):
            matrix = transform() @ Matrix.Diagonal((scale, 1, 1, 1))
            affine, linear, _ = vg.calc_transforms(matrix, True)
            actual = np.array(linear).reshape(3, 3) @ np.array(mirror.REFLECTION @ source)[:3] + affine
            expected = np.array(mirror.REFLECTION @ matrix @ source)[:3]
            self.assertMatrix(actual, expected)

    def test_constraint_frames_follow_reflected_bones(self):
        scene = vg.VirtualScene.__new__(vg.VirtualScene)
        scene.corinth, scene.light_scale = True, 10
        matrix = transform()
        scene.mirror = True
        reflected = scene._constraint_space_props(matrix, 'parent')
        scene.mirror = False
        expected = scene._constraint_space_props(mirror.mirror_matrix(matrix), 'parent')
        self.assertEqual(reflected, expected)
        self.assertEqual(reflected['parentTranslationX'], -matrix.translation.y)

    @unittest.skipUnless(os.environ.get('FOUNDRY_TEST_GRANNY_DLL'), 'Set FOUNDRY_TEST_GRANNY_DLL for native PCA test')
    def test_native_pca_rest_and_morph_share_reflected_world_space(self):
        granny = granny_module.Granny(os.environ['FOUNDRY_TEST_GRANNY_DLL'], False)
        scene = types.SimpleNamespace(mirror=True, corinth=False, granny=granny, warnings=[])
        for negative in (False, True):
            mesh = mesh_fixture()
            matrix = transform() @ Matrix.Diagonal((-1 if negative else 1, 1, 1, 1))
            node = vg.VirtualNode.__new__(vg.VirtualNode)
            node.mesh, node.matrix_world = mesh, matrix
            node.granny_vertex_data_copies, node.granny_vertex_data_copy_buffers = {}, {}
            morph = vg.VirtualMorphTargetData.__new__(vg.VirtualMorphTargetData)
            morph.positions = mesh.positions + np.array((0, 2, 1), dtype=np.float32)
            morph.normals, morph.tension = mesh.normals, None
            morph.num_vertices, morph.invalid = 3, False
            morph._granny_vertex_data(scene)
            morph._write_vertex_position(scene, node)
            node.set_pca_vertex_data_copy('animation', scene, morph)
            expected = np.array([mirror.REFLECTION @ matrix @ Vector((*p, 1)) for p in morph.positions])[:, :3]
            _, _, _, rest_dtype = mesh._vertex_data_arrays(scene)
            for data, dtype in ((morph.granny_vertex_data.contents, [('Position', 'f4', 3), ('Normal', 'f4', 3)]),
                                (node.granny_vertex_data_copies['animation'].contents, rest_dtype)):
                size = np.dtype(dtype).itemsize * 3
                vertices = np.frombuffer(ct.string_at(data.vertices, size), dtype=dtype)
                self.assertMatrix(vertices['Position'], expected)

    @unittest.skipUnless(os.environ.get('FOUNDRY_TEST_GRANNY_DLL'), 'Set FOUNDRY_TEST_GRANNY_DLL for native GR2 test')
    def test_native_conversion_and_file_roundtrip(self):
        for corinth in (False, True):
            with self.subTest(corinth=corinth), tempfile.TemporaryDirectory() as directory:
                granny = granny_module.Granny(os.environ['FOUNDRY_TEST_GRANNY_DLL'], corinth)
                path = Path(directory) / 'mirror.gr2'
                granny.new(path, 'x', 1)
                self.assertEqual(tuple(granny.right_vector), (0, -1, 0))
                mesh = mesh_fixture()
                scene = types.SimpleNamespace(mirror=True, corinth=corinth)
                mesh.to_granny_data(scene)
                data = formats.GrannyVertexData()
                data.vertex_type = mesh.vertex_type
                data.vertex_count = 3
                data.vertices = ct.cast(mesh.vertex_array, ct.POINTER(ct.c_ubyte))
                granny.file_info.vertex_data_count = 1
                granny.file_info.vertex_datas = (ct.POINTER(formats.GrannyVertexData) * 1)(ct.pointer(data))
                granny.file_info.tri_topology_count = 1
                granny.file_info.tri_topologies = (ct.POINTER(formats.GrannyTriTopology) * 1)(mesh.granny_tri_topology)
                granny_mesh = formats.GrannyMesh()
                granny_mesh.name = b'mesh'
                granny_mesh.primary_vertex_data = ct.pointer(data)
                granny_mesh.primary_topology = mesh.granny_tri_topology
                granny.file_info.mesh_count = 1
                granny.file_info.meshes = (ct.POINTER(formats.GrannyMesh) * 1)(ct.pointer(granny_mesh))
                granny.transform()
                self.assertEqual(list(mesh.granny_tri_topology.contents.indices[:3]), [0, 2, 1])
                _, _, _, dtype = mesh._vertex_data_arrays(scene)
                vertices = np.frombuffer(mesh.vertex_array, dtype=dtype)
                expected = mirror.mirror_vectors(mesh.positions)
                if corinth:
                    expected = expected[:, (1, 2, 0)] * 0.1
                self.assertMatrix(vertices['Position'], expected)
                granny.save()
                self.assertGreater(path.stat().st_size, 0)
                # Read back through the same SDK, verifying serialized coordinates and winding.
                read = granny.dll.GrannyReadEntireFile
                read.argtypes, read.restype = [ct.c_char_p], ct.c_void_p
                get_info = granny.dll.GrannyGetFileInfo
                get_info.argtypes, get_info.restype = [ct.c_void_p], ct.POINTER(formats.GrannyFileInfo)
                free = granny.dll.GrannyFreeFile
                free.argtypes = [ct.c_void_p]
                file = read(str(path).encode())
                self.assertTrue(file)
                try:
                    info = get_info(file).contents
                    self.assertEqual(list(info.tri_topologies[0].contents.indices[:3]), [0, 2, 1])
                    loaded = info.vertex_datas[0].contents
                    self.assertEqual(ct.string_at(loaded.vertices, mesh.len_vertex_array), bytes(mesh.vertex_array))
                finally:
                    free(file)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MirrorTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
