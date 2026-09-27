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
    coordinates = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mat.node_tree.links.new(coordinates.outputs['UV'], uv.inputs['Vector'])
    mat.node_tree.links.new(uv.outputs[0], tex.inputs['Vector'])
    mat.node_tree.links.new(tex.outputs['Color'], group.inputs[socket])
    if alpha:
        mat.node_tree.links.new(tex.outputs['Alpha'], group.inputs[alpha])
    return tex, uv


class MappingTests(unittest.TestCase):
    def setUp(self):
        warnings.clear()

    def screenshot_material(self, mode='double/biased multiply'):
        mat, source = material('h1_nodes', 'foundry_h1.shader_model')
        base, base_uv = texture(mat, source, 'Base Map', [[.15,.15,.15,.25], [.15,.15,.15,.75]], 'Base Map Alpha')
        detail, detail_uv = texture(mat, source, 'Detail Map', [[.25,.25,.25,1], [.75,.75,.75,1]], 'Detail Map Alpha')
        multi, multi_uv = texture(mat, source, 'Multipurpose Map', [[.1,.2,0,.4], [.5,.6,1,.8]], 'Multipurpose Map Alpha')
        for node, uv in [(base, base_uv), (detail, detail_uv), (multi, multi_uv)]:
            node.interpolation = 'Closest'
            uv.inputs['Scale'].default_value = (1, 1, 1)
        for node in (base, detail):
            pixels = list(node.image.pixels[:])
            node.image.colorspace_settings.name = 'ACEScg'
            node.image.pixels.foreach_set(pixels)
        detail_uv.inputs['Scale'].default_value = (2, 1, 1)
        source.inputs['Detail Mask'].default_value = 'reflection mask'
        source.inputs['Detail Function'].default_value = mode
        source.inputs['Animation Color Lower Bound'].default_value = (.2,.1,.05,1)
        source.inputs['Animation Color Upper Bound'].default_value = (.8,.7,.65,1)
        source.inputs['Animation Color Bound Factor'].default_value = .5
        return mat, source, base, detail, multi

    def test_masked_detail_is_baked_and_does_not_reuse_multipurpose(self):
        mat, source, base, detail, multi = self.screenshot_material()
        original_image = multi.image
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
        target = surface(mat)
        self.assertEqual(target.inputs['base_map.rgb'].links[0].from_node, base)
        baked = target.inputs['detail_map.rgb'].links[0].from_node
        self.assertEqual(baked.type, 'TEX_IMAGE')
        self.assertEqual(tuple(baked.image.size), (4, 1))
        pixels = np.array(baked.image.pixels[:]).reshape(-1, 4)
        np.testing.assert_allclose(bitmap_mapping._linear(pixels[:, 0]), [.5,.5,.25,.75], atol=.007)
        saved = bpy.data.images.load(baked.image.filepath, check_existing=False)
        np.testing.assert_allclose(np.array(saved.pixels[:]).reshape(-1, 4)[:, :3], pixels[:, :3], atol=1/255)
        self.assertFalse(target.inputs['self_illum_color'].is_linked)
        np.testing.assert_allclose(target.inputs['self_illum_color'].default_value, [.5,.4,.35,1])
        self.assertFalse(any(n.type in {'MIX_RGB', 'MATH', 'SEPARATE_COLOR', 'COMBINE_COLOR'} for n in mat.node_tree.nodes))
        self.assertFalse(any(n.type == 'TEX_IMAGE' and n.image == original_image for n in mat.node_tree.nodes))
        for socket in target.inputs:
            if socket.is_linked and mapping._texture_parameter(socket.name):
                self.assertEqual(socket.links[0].from_node.type, 'TEX_IMAGE', socket.name)

    def test_unmasked_detail_uses_native_input_once(self):
        mat, source, base, detail, _ = self.screenshot_material()
        source.inputs['Detail Mask'].default_value = 'none'
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
        target = surface(mat)
        self.assertEqual(target.inputs['base_map.rgb'].links[0].from_node, base)
        self.assertEqual(target.inputs['detail_map.rgb'].links[0].from_node, detail)

    def test_biased_add_bakes_base_and_preserves_alpha(self):
        mat, source, base, _, _ = self.screenshot_material('double/biased add')
        original_image = base.image
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
        target = surface(mat)
        node = target.inputs['base_map.rgb'].links[0].from_node
        self.assertNotEqual(node.image, original_image)
        self.assertEqual(target.inputs['base_map.a'].links[0].from_node, node)
        pixels = np.array(node.image.pixels[:]).reshape(-1, 4)
        np.testing.assert_allclose(pixels[:, 3], [.25,.25,.75,.75], atol=1/255)

    def test_constant_assignment_disconnects_a_previous_texture(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        texture(mat, source, 'detail_map.rgb', [[.5,.5,.5,1]] * 2)
        mapping._put(mat.node_tree, source.inputs['detail_map.rgb'], (.5,.5,.5,1))
        self.assertFalse(source.inputs['detail_map.rgb'].is_linked)

    def test_required_bake_failure_rolls_back_and_blocks_shader_build(self):
        import ast
        mat, source, _, detail, _ = self.screenshot_material()
        detail.image.source = 'SEQUENCE'
        original_nodes = set(mat.node_tree.nodes)
        self.assertFalse(mapping.convert_material_game(mat, 'halo1', 'reach'))
        self.assertEqual(set(mat.node_tree.nodes), original_nodes)
        self.assertEqual(surface(mat), source)
        self.assertIn('foundry_material_conversion_error', mat)
        parsed = ast.parse((ADDON / 'tools/shader_builder.py').read_text())
        function = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'build_shader')
        namespace = {'utils': utils}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'shader_builder.py', 'exec'), namespace)
        reports = []
        self.assertEqual(namespace['build_shader'](mat, False, report=lambda severity, message: reports.append(message)), {'CANCELLED'})
        self.assertIn('conversion is incomplete', reports[0])

    def test_reach_exporter_reads_generated_maps_constants_and_tiling(self):
        """Exercise real exporter parameter discovery, not just graph shape."""
        import ast
        from enum import Enum
        mat, _, base, _, multi = self.screenshot_material()
        source_image = multi.image
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
        group = surface(mat)
        parsed_utils = ast.parse((ADDON / 'utils.py').read_text())
        utility_names = {'find_linked_node', 'find_node_in_chain', 'get_material_albedo', 'find_mapping_node'}
        utility_namespace = {'bpy': bpy, 'hit_target': False, 'is_halo_mapping_node': lambda node: False}
        functions = [n for n in parsed_utils.body if isinstance(n, ast.FunctionDef) and n.name in utility_names]
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'utils.py', 'exec'), utility_namespace)
        for name in utility_names:
            setattr(utils, name, utility_namespace[name])
        utils.remove_chars = lambda value, chars: ''.join(c for c in value if c not in chars)
        utils.game_str = lambda value: value.lower().replace(' ', '_')
        parsed = ast.parse((ADDON / 'tags/shader_converter.py').read_text())
        shader_class = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == 'ShaderTag')
        method_names = {'_from_nodes_group', '_source_from_input_and_parameter_type', '_function_parameters_from_node'}
        methods = [n for n in shader_class.body if isinstance(n, ast.FunctionDef) and n.name in method_names]
        animated = Enum('AnimatedParameterType', 'TRANSLATION_X TRANSLATION_Y SCALE_UNIFORM SCALE_X SCALE_Y VALUE COLOR')
        namespace = {'bpy': bpy, 'utils': utils, 'AnimatedParameterType': animated}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'shader_converter.py', 'exec'), namespace)
        Writer = type('Writer', (), {name: namespace[name] for name in method_names})
        writer = Writer()
        writer.group_node = group
        writer.group_option_start_input = 8
        writer.definition = types.SimpleNamespace(Path='shader.render_method_definition')
        writer.palette_vector_parameters = set()
        writer._get_info = lambda path: None
        writer._group_node_matches = lambda node: True
        writer._self_illumination_uses_palette_vector = lambda option: False
        selected = {s.name: s.default_value for s in group.inputs[:8]}
        writer._apply_group_options_from_node = lambda: selected
        specs = {'base_map': 'bitmap', 'detail_map': 'bitmap', 'specular_mask_texture': 'bitmap',
                 'self_illum_map': 'bitmap', 'self_illum_color': 'color', 'self_illum_intensity': 'real'}
        parameters = {name: types.SimpleNamespace(ui_name=name, type=kind) for name, kind in specs.items()}
        writer.category_parameters = {name: {value: parameters if name == 'albedo' else {}} for name, value in selected.items()}
        writer._parameter_type_tokens = lambda parameter: (parameter.type, parameter.type)
        captured, functions = {}, {}
        def setup(source, name, kind):
            captured[name] = source
            return name
        writer._setup_parameter = setup
        writer._setup_function_parameters = lambda source, name, kind: functions.update({name: writer._function_parameters_from_node(source, kind)})
        self.assertTrue(writer._from_nodes_group())
        self.assertEqual(captured['base_map'], base)
        for name in ('detail_map', 'specular_mask_texture', 'self_illum_map'):
            image = captured[name].image
            self.assertNotEqual(image, source_image)
            self.assertTrue(Path(image.filepath).is_file())
            self.assertTrue(Path(image.filepath).is_relative_to(TEMP.name))
        np.testing.assert_allclose(captured['self_illum_color'], [.5,.4,.35])
        self.assertEqual(functions['detail_map'][animated.SCALE_X], 1)
        self.assertEqual(functions['detail_map'][animated.SCALE_Y], 1)

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
                    warnings.clear()
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
            original_image = tex.image
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
            np.testing.assert_allclose(np.array(original_image.pixels[:]).reshape(-1, 4), pixels, atol=1/255)
            self.assertFalse(any(n.type == 'TEX_IMAGE' and n.image == original_image for n in mat.node_tree.nodes))

    def test_halo1_to_h4_packed_control(self):
        mat, source = material('h1_nodes', 'foundry_h1.shader_model')
        pixels = np.array([[.1,.2,.3,.4], [.5,.6,.7,.8]], dtype=np.float32)
        tex, uv = texture(mat, source, 'Multipurpose Map', pixels, 'Multipurpose Map Alpha')
        source.inputs['Animation Color Upper Bound'].default_value = (1, 1, 1, 1)
        source.inputs['Animation Color Bound Factor'].default_value = 1
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'halo4'), warnings)
        target = surface(mat)
        self.assertEqual(target.node_tree.name, 'srf_char_blinn_reflection_selfillum')
        node = target.inputs['control_map_spglrfsi'].links[0].from_node
        self.assertEqual(node.type, 'TEX_IMAGE', warnings)
        self.assertEqual(target.inputs['control_map_spglrfsi_alpha'].links[0].from_node, node)
        self.assertEqual(node.inputs['Vector'].links[0].from_node, uv)
        result = np.array(node.image.pixels[:]).reshape(-1, 4)
        np.testing.assert_allclose(result[:, 0], pixels[:, 2], atol=1/255)
        np.testing.assert_allclose(result[:, 3], pixels[:, 1], atol=1/255)

    def test_h4_control_unpack(self):
        mat, source = material('h4_nodes', 'srf_char_blinn_reflection_selfillum')
        pixels = np.array([[.1,.2,.3,.4], [.5,.6,.7,.8]], dtype=np.float32)
        texture(mat, source, 'control_map_spglrfsi', pixels, 'control_map_spglrfsi_alpha')
        self.assertTrue(mapping.convert_material_game(mat, 'halo4', 'reach'), warnings)
        target = surface(mat)
        for name, channel in [('specular_mask_texture.a', 0), ('self_illum_map.rgb', 3)]:
            node = target.inputs[name].links[0].from_node
            self.assertEqual(node.type, 'TEX_IMAGE', warnings)
            result = np.array(node.image.pixels[:]).reshape(-1, 4)
            np.testing.assert_allclose(result[:, 0], pixels[:, channel], atol=1/255)

    def test_copied_material_keeps_parameter_values(self):
        # Run the actual copier without importing unrelated add-on services.
        import ast
        parsed = ast.parse((ADDON / 'utils.py').read_text())
        function = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'copy_material_nodes')
        namespace = {'bpy': bpy}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'utils.py', 'exec'), namespace)
        mat, source = material('h1_nodes', 'foundry_h1.shader_model')
        self.assertTrue(mapping.convert_material_game(mat, 'halo1', 'reach'), warnings)
        target = surface(mat)
        copy, _ = material('reach_nodes', 'foundry_reach.shader')
        namespace['copy_material_nodes'](mat, copy)
        copied = surface(copy)
        for left, right in zip(target.inputs, copied.inputs):
            if left.type in {'RGBA', 'VECTOR'}:
                self.assertEqual(tuple(left.default_value), tuple(right.default_value), left.name)
            else:
                self.assertEqual(left.default_value, right.default_value, left.name)

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

    def test_baked_bitmaps_preserve_source_tagset_directories(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        tex, _ = texture(mat, source, 'base_map.rgb', [[.1,.2,.3,1]] * 2)
        original = r'objects\weapons\rifle\bitmaps\rifle_multi.bitmap'
        tex.image['foundry_source_bitmap_path'] = original
        baker = bitmap_mapping.DataTextureBaker(mat.node_tree, TEMP.name)
        first = baker.bake(tex.outputs['Color'], 'specular')
        second = baker.bake(first.outputs['Color'], 'illumination')
        expected = Path(TEMP.name) / 'objects/weapons/rifle/bitmaps'
        for node in (first, second):
            path = Path(node.image.filepath_raw)
            self.assertEqual(path.parent, expected)
            self.assertTrue(path.name.startswith('rifle_multi_'))
            self.assertTrue(path.is_file())
            self.assertEqual(Path(node.image['foundry_source_bitmap_path']), Path(original))
        self.assertNotEqual(first.image.filepath_raw, second.image.filepath_raw)
        self.assertEqual(tex.image['foundry_source_bitmap_path'], original)
        self.assertFalse((Path(TEMP.name) / 'foundry_material_conversions').exists())

    def test_baked_generated_inputs_do_not_use_special_folder(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        baker = bitmap_mapping.DataTextureBaker(mat.node_tree, TEMP.name)
        node = baker.bake(.5, 'constant')
        self.assertEqual(Path(node.image.filepath_raw).parent, Path(TEMP.name))

    def test_baked_source_path_cannot_escape_project(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        tex, _ = texture(mat, source, 'base_map.rgb', [[.1,.2,.3,1]] * 2)
        tex.image['foundry_source_bitmap_path'] = '../outside.bitmap'
        baker = bitmap_mapping.DataTextureBaker(mat.node_tree, TEMP.name)
        with self.assertRaisesRegex(ValueError, 'relative to its tagset'):
            baker.bake(tex.outputs['Color'], 'invalid')

    def test_incompatible_uvs_do_not_bake(self):
        mat, source = material('reach_nodes', 'foundry_reach.shader')
        tex1, _ = texture(mat, source, 'base_map.rgb', [[.1,.2,.3,1]] * 2)
        tex2, _ = texture(mat, source, 'detail_map.rgb', [[.1,.2,.3,1]] * 2)
        baker = bitmap_mapping.DataTextureBaker(mat.node_tree, TEMP.name)
        with self.assertRaisesRegex(ValueError, 'different dimensions or UV'):
            baker.bake(tex1.outputs['Color'], 'incompatible', tex2.outputs['Alpha'])

    def test_shader_reader_target_is_opt_in_and_detaches_foreign_tag(self):
        import ast

        class MaterialProps(bpy.types.PropertyGroup):
            shader_path: bpy.props.StringProperty()
            prev_shader_path: bpy.props.StringProperty()
            material_shader: bpy.props.StringProperty()
            uses_blender_nodes: bpy.props.BoolProperty()
            shader_type: bpy.props.StringProperty()
            game_functions: bpy.props.StringProperty()
            object_functions: bpy.props.StringProperty()

        class SourceTag:
            game = 'halo1'
            game_functions = {'primary_color'}
            object_functions = set()
            sequence_drivers = {}

            def __init__(self, path):
                self.system_path = Path(path)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def to_nodes(self, mat, *args):
                tree = mat.node_tree
                tree.nodes.clear()
                source = tree.nodes.new('ShaderNodeGroup')
                source.node_tree = load_resource('h1_nodes', 'foundry_h1.shader_model')
                output = tree.nodes.new('ShaderNodeOutputMaterial')
                tree.links.new(source.outputs['Shader'], output.inputs['Surface'])

        path = Path(TEMP.name, 'source.shader_model')
        path.touch()
        utils.get_tags_path = lambda: TEMP.name
        utils.relative_path = str
        parsed = ast.parse((ADDON / 'tools/shader_reader.py').read_text())
        function = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'tag_to_nodes')
        namespace = {'bpy': bpy, 'Path': Path, 'utils': utils, 'ShaderTag': SourceTag,
                     'arrange': lambda tree: None, '__package__': tools_package.__name__}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'shader_reader.py', 'exec'), namespace)
        bpy.utils.register_class(MaterialProps)
        bpy.types.Material.nwo = bpy.props.PointerProperty(type=MaterialProps)
        try:
            for target in (None, 'reach'):
                mat, _ = material('h1_nodes', 'foundry_h1.shader_model')
                mat.nwo.shader_path = str(path)
                namespace['tag_to_nodes'](False, mat, str(path), target_game=target)
                if target is None:
                    self.assertEqual(mat.nwo.shader_path, str(path))
                    self.assertTrue(surface(mat).node_tree.name.startswith('foundry_h1.'))
                else:
                    self.assertEqual(mat.nwo.shader_path, '')
                    self.assertEqual(mat['foundry_material_source_shader'], str(path))
                    self.assertEqual(mat.nwo.shader_type, '.shader')
                    self.assertTrue(mat.nwo.uses_blender_nodes)
                    self.assertEqual(mat.nwo.game_functions, 'primary_color')
                    self.assertTrue(surface(mat).node_tree.name.startswith('foundry_reach.'))
        finally:
            del bpy.types.Material.nwo
            bpy.utils.unregister_class(MaterialProps)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MappingTests))
    TEMP.cleanup()
    if not result.wasSuccessful():
        raise SystemExit(1)
