"""Blender --background --factory-startup --python-exit-code 1 --python this_file.py.

Real shipped groups and image I/O; no installed editing kit is required.
"""
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
import bpy
import numpy as np

ADDON = Path(__file__).resolve().parent / 'addons' / 'io_scene_foundry'
TEMP = tempfile.TemporaryDirectory(prefix='foundry_material_mapping_')
warnings = []


def load_resource(library, name):
    existing = bpy.data.node_groups.get(name)
    if existing is not None:
        return existing
    with bpy.data.libraries.load(str(ADDON / 'blends' / f'{library}.blend'), link=False) as (src, dst):
        if name not in src.node_groups:
            return None
        dst.node_groups = [name]
    return dst.node_groups[0]


package = types.ModuleType('mapping_test_foundry')
package.__path__ = [str(ADDON)]
sys.modules[package.__name__] = package
tools_package = types.ModuleType(package.__name__ + '.tools')
tools_package.__path__ = [str(ADDON / 'tools')]
sys.modules[tools_package.__name__] = tools_package
utils = types.ModuleType(package.__name__ + '.utils')
utils.add_node_from_resources = load_resource
utils.print_warning = warnings.append
utils.get_project = lambda **kwargs: types.SimpleNamespace(data_directory=TEMP.name)
sys.modules[utils.__name__] = utils
mapping = importlib.import_module(package.__name__ + '.tools.material_game_mapping')
bitmap_mapping = importlib.import_module(package.__name__ + '.tools.material_bitmap_mapping')


def material(library, name):
    mat = bpy.data.materials.new('mapping_test')
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node = tree.nodes.new('ShaderNodeGroup')
    node.node_tree = load_resource(library, name)
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    tree.links.new(next(s for s in node.outputs if s.type == 'SHADER'), output.inputs['Surface'])
    return mat, node


def surface(mat):
    output = next(n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
    return output.inputs['Surface'].links[0].from_node


def texture(mat, group, socket, pixels, alpha=None):
    image = bpy.data.images.new('multipurpose_fixture', width=2, height=1, alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    image.alpha_mode = 'CHANNEL_PACKED'
    image.pixels.foreach_set(np.asarray(pixels, dtype=np.float32).ravel())
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = image
    uv = mat.node_tree.nodes.new('ShaderNodeMapping')
    uv.inputs['Scale'].default_value = (3, 4, 1)
    mat.node_tree.links.new(uv.outputs[0], tex.inputs['Vector'])
    mat.node_tree.links.new(tex.outputs['Color'], group.inputs[socket])
    if alpha:
        mat.node_tree.links.new(tex.outputs['Alpha'], group.inputs[alpha])
    return tex, uv


class MappingTests(unittest.TestCase):
    def setUp(self):
        warnings.clear()

    def test_supported_game_matrix(self):
        fixtures = {'halo1': ('h1_nodes', 'foundry_h1.shader_model'),
                    'halo3': ('h3_nodes', 'foundry_h3.shader'),
                    'halo3odst': ('h3_nodes', 'foundry_h3.shader'),
                    'reach': ('reach_nodes', 'foundry_reach.shader'),
                    'halo4': ('h4_nodes', 'srf_blinn'),
                    'halo2a': ('h4_nodes', 'srf_blinn')}
        for source_game, fixture in fixtures.items():
            for target_game in fixtures:
                with self.subTest(source=source_game, target=target_game):
                    mat, node = material(*fixture)
                    same = mapping.GAME_LIBRARIES[source_game] == mapping.GAME_LIBRARIES[target_game]
                    self.assertEqual(mapping.convert_material_game(mat, source_game, target_game), not same, warnings)
                    if not same:
                        prefix = mapping.GAME_LIBRARIES[target_game][1] or 'srf_'
                        self.assertTrue(surface(mat).node_tree.name.startswith(prefix))
                    else:
                        self.assertEqual(surface(mat), node)
                    bpy.data.materials.remove(mat)

    def test_halo1_pc_and_xbox_masks_and_saved_pixels(self):
        pixels = np.array([[.1,.2,.3,.4], [.5,.6,.7,.8]], dtype=np.float32)
        for xbox in (False, True):
            mat, source = material('h1_nodes', 'foundry_h1.shader_model')
            source.inputs['Multipurpose Map Uses OG Xbox Channel Order'].default_value = xbox
            tex, uv = texture(mat, source, 'Multipurpose Map', pixels, 'Multipurpose Map Alpha')
            attribute = mat.node_tree.nodes.new('ShaderNodeAttribute')
            mat.node_tree.links.new(attribute.outputs['Color'], source.inputs['Primary Change Color'])
            self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
            target = surface(mat)
            for socket_name, column in [('specular_mask_texture.a', 0 if xbox else 2),
                                        ('self_illum_map.rgb', 1), ('change_color_map.rgb', 2 if xbox else 3)]:
                with self.subTest(xbox=xbox, socket=socket_name):
                    node = target.inputs[socket_name].links[0].from_node
                    self.assertEqual(node.type, 'TEX_IMAGE', warnings)
                    self.assertEqual(node.inputs['Vector'].links[0].from_node, uv)
                    path = Path(node.image.filepath)
                    self.assertTrue(path.is_relative_to(TEMP.name))
                    self.assertTrue(path.is_file())
                    reloaded = bpy.data.images.load(str(path), check_existing=False)
                    reloaded.colorspace_settings.name = 'Non-Color'
                    reloaded.alpha_mode = 'CHANNEL_PACKED'
                    result = np.array(reloaded.pixels[:]).reshape(-1, 4)
                    channel = 3 if socket_name.endswith('.a') else 0
                    np.testing.assert_allclose(result[:, channel], pixels[:, column], atol=1/255)
            np.testing.assert_allclose(np.array(tex.image.pixels[:]).reshape(-1, 4), pixels, atol=1/255)

    def test_same_family_links_and_duplicate_sockets(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        tex, uv = texture(mat, source, 'base_map.rgb', [[.1,.2,.3,1], [.4,.5,.6,1]], 'base_map.a')
        source.inputs['albedo'].default_value = 'two_detail'
        for index, socket in enumerate(s for s in source.inputs if s.name == 'environment_map_specular_contribution'):
            socket.default_value = .2 + index * .3
        self.assertTrue(mapping.convert_material_game(mat, 'reach', 'halo3'), warnings)
        target = surface(mat)
        self.assertEqual(target.inputs['base_map.rgb'].links[0].from_node, tex)
        self.assertEqual(tex.inputs['Vector'].links[0].from_node, uv)
        self.assertEqual(target.inputs['albedo'].default_value, 'two_detail')
        result = [s.default_value for s in target.inputs if s.name == 'environment_map_specular_contribution']
        np.testing.assert_allclose(result[:2], [.2, .5])

    def test_specialized_families(self):
        for source_game, library, prefix in [('halo3', 'h3_nodes', 'foundry_h3.'), ('reach', 'reach_nodes', 'foundry_reach.')]:
            families = ['shader_terrain', 'shader_halogram', 'shader_decal', 'shader_custom']
            if source_game == 'reach':
                families += ['shader_foliage', 'shader_glass']
            for family in families:
                for target_game in ('halo1', 'halo3', 'reach', 'halo4'):
                    if source_game == target_game:
                        continue
                    with self.subTest(source=source_game, family=family, target=target_game):
                        mat, _ = material(library, prefix + family)
                        self.assertTrue(mapping.convert_material_game(mat, source_game, target_game), warnings)

    def test_halo1_environment(self):
        mat, source = material('h1_nodes', 'foundry_h1.shader_environment')
        texture(mat, source, 'Bump Map', [[.5,.5,1,1], [.5,.5,1,1]])
        source.inputs['Alpha Tested'].default_value = True
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
        self.assertEqual(surface(mat).inputs['bump_mapping'].default_value, 'standard')
        self.assertEqual(surface(mat).inputs['alpha_test'].default_value, 'simple')

    def test_h2_source_and_unsupported_target(self):
        mat = bpy.data.materials.new('h2_preview')
        mat.use_nodes = True
        self.assertTrue(mapping.convert_material_game(mat, 'halo2', 'reach'), warnings)
        nodes = set(mat.node_tree.nodes)
        self.assertFalse(mapping.convert_material_game(mat, 'reach', 'halo2'))
        self.assertEqual(nodes, set(mat.node_tree.nodes))

    def test_missing_resource_retains_graph(self):
        mat, source = material('h1_nodes', 'foundry_h1.shader_model')
        nodes = set(mat.node_tree.nodes)
        original = utils.add_node_from_resources
        utils.add_node_from_resources = lambda *args: None
        try:
            self.assertFalse(mapping.convert_material_game(mat, 'halo1', 'reach'))
            self.assertEqual(set(mat.node_tree.nodes), nodes)
            self.assertEqual(surface(mat), source)
        finally:
            utils.add_node_from_resources = original

    def test_incompatible_uvs_do_not_bake(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        tex1, _ = texture(mat, source, 'base_map.rgb', [[.1,.2,.3,1]] * 2)
        tex2, _ = texture(mat, source, 'detail_map.rgb', [[.1,.2,.3,1]] * 2)
        baker = bitmap_mapping.DataTextureBaker(mat.node_tree, TEMP.name)
        with self.assertRaisesRegex(ValueError, 'different dimensions or UV'):
            baker.bake(tex1.outputs['Color'], 'incompatible', tex2.outputs['Alpha'])


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MappingTests))
    TEMP.cleanup()
    if not result.wasSuccessful():
        raise SystemExit(1)
