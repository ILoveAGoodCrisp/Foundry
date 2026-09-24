"""Run with Blender background mode; exercises native tags and bundled H1 groups."""
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import bpy

ADDONS = Path(__file__).resolve().parents[1] / 'blender/addons'
sys.path.insert(0, str(ADDONS))
_wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (ADDONS / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(_wheels.name)
sys.path.insert(0, _wheels.name)

from io_scene_foundry import utils
from io_scene_foundry.tags import shader_converter
from io_scene_foundry.tags.shader_converter import ShaderTag


class Halo1ShaderNodeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = self.stack.enter_context(tempfile.TemporaryDirectory())
        for name, value in (
                ('get_scene_props', SimpleNamespace(scene_project='test')),
                ('get_project', SimpleNamespace(game='halo1')),
                ('get_tags_path', root), ('get_data_path', root),
                ('get_prefs', SimpleNamespace(link_resource_nodes=False))):
            self.stack.enter_context(patch.object(utils, name, return_value=value))
        self.images = []
        self.materials = []
        self.extract = self.stack.enter_context(patch.object(
            shader_converter, 'bitmap_to_image', side_effect=self.image))

    def tearDown(self):
        for mat in self.materials:
            bpy.data.materials.remove(mat)
        for image in self.images:
            bpy.data.images.remove(image)

    def image(self, path, always_extract):
        image = bpy.data.images.new(Path(path).stem, 4, 4, alpha=True)
        self.images.append(image)
        return SimpleNamespace(image=image, cubemap='cube' in path)

    def tag(self, shader_type):
        return self.stack.enter_context(ShaderTag(shader_type + '.' + shader_type,
                                                  tag_must_exist=False))

    def child(self, tag, name):
        return tag.tag.root().field(name).as_struct()

    def set_value(self, struct, name, value):
        field = struct.field(name)
        if isinstance(value, tuple):
            value = type(field.value)(*value)
        field.set(value)

    def set_bitmap(self, tag, struct, name):
        tag.set_reference(struct, name, name.replace(' ', '_') + '.bitmap')

    def convert(self, tag, **kwargs):
        mat = bpy.data.materials.new(tag.path)
        self.materials.append(mat)
        tag.to_nodes(mat, **kwargs)
        groups = [n for n in mat.node_tree.nodes if n.type == 'GROUP']
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.node_tree.name, 'foundry_h1.' + tag.system_path.suffix[1:])
        output = next(n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
        self.assertEqual(output.inputs['Surface'].links[0].from_node, group)
        self.assertFalse(any(n.type == 'BSDF_PRINCIPLED' for n in mat.node_tree.nodes))
        return mat, group

    def assert_map(self, group, socket, name, scale=None, reflection=False):
        node = group.inputs[socket].links[0].from_node
        self.assertEqual(node.name, name)
        alpha = group.inputs.get(socket + ' Alpha')
        if alpha is not None:
            link = alpha.links[0]
            self.assertEqual(link.from_node, node)
            self.assertEqual(link.from_socket.name, 'Alpha')
        source = node.inputs['Vector'].links[0]
        if scale is not None:
            self.assertEqual(source.from_node.type, 'MAPPING')
            self.assertEqual(tuple(source.from_node.inputs['Scale'].default_value), (*scale, 1.0))
        if reflection:
            self.assertEqual(node.type, 'TEX_ENVIRONMENT')
            self.assertEqual(source.from_socket.name, 'Reflection')
        return node

    def test_model_settings_maps_and_change_color(self):
        tag = self.tag('shader_model')
        flags = self.child(tag, 'properties').field('flags')
        for name in ('detail after reflection', 'two sided', 'not alpha tested',
                     'alpha blended decal', 'use xbox multipurpose channel order'):
            flags.set_flag(name, True)
        self.child(tag, 'change color').field('change color source').set('c')
        radiosity = self.child(tag, 'radiosity')
        self.set_value(radiosity, 'power', 3.0)
        self.set_value(radiosity, 'color of emitted light', (0.25, 0.5, 1.0))
        illumination = self.child(tag, 'self-illumination')
        self.set_value(illumination, 'animation color upper bound', (1.0, 0.5, 0.25))
        maps = self.child(tag, 'maps')
        for name in ('base map', 'multipurpose map', 'detail map'):
            self.set_bitmap(tag, maps, name)
        for name, value in (('map u scale', 2.0), ('map v scale', 3.0),
                            ('detail map scale', 4.0), ('detail map v scale', 5.0)):
            maps.field(name).set(value)
        maps.field('detail function').set('double biased add')
        maps.field('detail mask').set('auxiliary mask inverse')
        reflection = self.child(tag, 'reflection')
        self.set_bitmap(tag, reflection, 'cube map')
        self.set_value(reflection.field('cube map properties').as_struct(),
                       'perpendicular brightness', 0.75)

        mat, group = self.convert(tag, always_extract_bitmaps=True)
        self.assertEqual(mat.surface_render_method, 'BLENDED')
        for name in ('Detail After Reflections', 'Two-Sided', 'Not Alpha-Tested',
                     'Alpha-Blended Decal', 'Multipurpose Map Uses OG Xbox Channel Order'):
            self.assertTrue(group.inputs[name].default_value)
        self.assertEqual(group.inputs['Power'].default_value, 3.0)
        self.assertEqual(tuple(group.inputs['Color of Emitted Light'].default_value), (0.25, 0.5, 1, 1))
        self.assertEqual(group.inputs['Detail Function'].default_value, 'double/biased add')
        self.assertEqual(group.inputs['Detail Mask'].default_value, 'multipurpose map alpha inverse')
        self.assertEqual(group.inputs['Perpendicular Brightness'].default_value, 0.75)
        attribute = group.inputs['Primary Change Color'].links[0].from_node
        self.assertEqual((attribute.attribute_type, attribute.attribute_name), ('INSTANCER', 'Tertiary Color'))
        self.assert_map(group, 'Base Map', 'base map', (2, 3))
        multipurpose = self.assert_map(group, 'Multipurpose Map', 'multipurpose map', (2, 3))
        self.assertEqual(multipurpose.image.colorspace_settings.name, 'Non-Color')
        self.assert_map(group, 'Detail Map', 'detail map', (8, 15))
        self.assert_map(group, 'Reflection Cube Map', 'cube map', reflection=True)
        self.assertTrue(all(call.args[1] for call in self.extract.call_args_list))

    def test_environment_settings_and_all_maps(self):
        tag = self.tag('shader_environment')
        properties = self.child(tag, 'properties')
        properties.field('flags').set_flag('alpha tested', True)
        properties.field('shader environment type').set('blended base specular')
        diffuse = self.child(tag, 'diffuse')
        self.set_bitmap(tag, diffuse, 'base map')
        diffuse.field('detail map function').set('multiply')
        diffuse.field('micro detail map function').set('double biased add')
        for i, name in enumerate(('primary detail map', 'secondary detail map', 'micro detail map'), 2):
            self.set_bitmap(tag, diffuse, name)
            diffuse.field(name + ' scale').set(float(i))
        bump = self.child(tag, 'bump')
        self.set_bitmap(tag, bump, 'bump map')
        bump.field('bump map scale').set(5.0)
        illumination = self.child(tag, 'self-illumination')
        self.set_bitmap(tag, illumination, 'map')
        illumination.field('map scale').set(6.0)
        illumination.field('secondary animation function').set('zero')
        self.set_value(illumination, 'primary on color', (0.25, 0.5, 1.0))
        self.set_value(self.child(tag, 'specular'), 'brightness', 0.5)
        reflection = self.child(tag, 'reflection')
        self.set_bitmap(tag, reflection, 'reflection cube map')
        reflection.field('parallel brightness').set(0.75)

        mat, group = self.convert(tag)
        self.assertEqual(mat.surface_render_method, 'DITHERED')
        self.assertTrue(group.inputs['Alpha Tested'].default_value)
        self.assertEqual(group.inputs['Blend Type'].default_value, 'blended base specular')
        self.assertEqual(group.inputs['Detail Map Function'].default_value, 'multiply')
        self.assertEqual(group.inputs['Micro Detail Map Function'].default_value, 'double/biased add')
        self.assertEqual(group.inputs['Bump Strength'].default_value, 1.0)
        self.assertEqual(group.inputs['Primary Self-Illumination Activation Level'].default_value, 1.0)
        self.assertEqual(group.inputs['Secondary Self-Illumination Activation Level'].default_value, 0.0)
        self.assertEqual(tuple(group.inputs['Primary On Color'].default_value), (0.25, 0.5, 1, 1))
        self.assertEqual(group.inputs['Brightness'].default_value, 0.5)
        self.assertEqual(group.inputs['Parallel Brightness'].default_value, 0.75)
        self.assert_map(group, 'Base Map', 'base map')
        for i, name in enumerate(('primary detail map', 'secondary detail map', 'micro detail map'), 2):
            self.assert_map(group, name.title(), name, (i, i))
        bump_node = self.assert_map(group, 'Bump Map', 'bump map', (5, 5))
        self.assertEqual(bump_node.image.colorspace_settings.name, 'Non-Color')
        self.assert_map(group, 'Self-Illumination Map', 'map', (6, 6))
        self.assert_map(group, 'Reflection Cube Map', 'reflection cube map', reflection=True)

    def test_empty_tags_keep_group_defaults_and_reuse_resources(self):
        for shader_type in ('shader_model', 'shader_environment'):
            with self.subTest(shader_type=shader_type):
                tag = self.tag(shader_type)
                mat, group = self.convert(tag)
                self.assertFalse(any(n.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} for n in mat.node_tree.nodes))
                self.assertEqual(group.inputs['Base Map Alpha'].default_value, 1.0)
                _, other = self.convert(tag)
                self.assertEqual(group.node_tree, other.node_tree)
                if shader_type == 'shader_environment':
                    self.assertEqual(group.inputs['Bump Strength'].default_value, 0.0)
        self.extract.assert_not_called()

    def test_all_model_menu_names_match_resource(self):
        tag = self.tag('shader_model')
        maps = self.child(tag, 'maps')
        for name in ('none', 'reflection mask inverse', 'reflection mask',
                     'self illumination mask inverse', 'self illumination mask',
                     'change color mask inverse', 'change color mask',
                     'auxiliary mask inverse', 'auxiliary mask'):
            with self.subTest(mask=name):
                maps.field('detail mask').set(name)
                self.convert(tag)

    def test_generated_coordinates_and_zero_scale_defaults(self):
        tag = self.tag('shader_model')
        maps = self.child(tag, 'maps')
        self.set_bitmap(tag, maps, 'base map')
        _, group = self.convert(tag, generated_uvs=True)
        image = group.inputs['Base Map'].links[0].from_node
        self.assertEqual(image.inputs['Vector'].links[0].from_socket.name, 'Generated')
        self.assertFalse(any(n.type == 'MAPPING' for n in group.id_data.nodes))

    def test_other_halo1_shader_families_keep_basic_material(self):
        tag = self.tag('shader_transparent_glass')
        mat = bpy.data.materials.new('glass')
        self.materials.append(mat)
        tag.to_nodes(mat)
        self.assertTrue(any(n.type == 'BSDF_PRINCIPLED' for n in mat.node_tree.nodes))
        self.assertFalse(any(n.type == 'GROUP' for n in mat.node_tree.nodes))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
