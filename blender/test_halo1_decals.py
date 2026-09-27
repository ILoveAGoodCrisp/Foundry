"""Blender --background --factory-startup --python this_file.

Render regressions use synthetic textures, so no editing-kit assets are needed.
"""
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

runpy.run_path(str(Path(__file__).with_name('test_classic_geometry.py')), run_name='bootstrap')
import bpy
from io_scene_foundry.tags import shader_converter as converter
from io_scene_foundry.tags.backend import TagDocument


class Struct:
    def __init__(self, **values):
        self.values = values

    def field(self, name):
        value = self.values.get(name)
        if value is None:
            return None
        return SimpleNamespace(value=value, as_struct=lambda: value,
                               options=lambda: SimpleNamespace(current_name=value))


class DecalTests(unittest.TestCase):
    def material(self, blend, rgba, intensity=(0, 0), generated=True):
        image = bpy.data.images.new('decal fixture', width=1, height=1, alpha=True)
        image.colorspace_settings.name = 'Non-Color'
        image.alpha_mode = 'CHANNEL_PACKED'
        image.pixels[:] = rgba
        root = Struct(
            properties=Struct(),
            appearance=Struct(**{'color upper bound': SimpleNamespace(red=1, green=1, blue=1),
                                 'intensity': SimpleNamespace(lower=intensity[0], upper=intensity[1])}),
            shader=Struct(**{'framebuffer blend function': blend}))
        reader = SimpleNamespace(
            system_path=Path('fixture.decal'), tag=SimpleNamespace(root=lambda: root),
            generated_uvs=generated, always_extract_bitmaps=False,
            value=lambda struct, name: struct.field(name).value,
            _halo1_decal_surface=converter.ShaderTag._halo1_decal_surface)
        mat = bpy.data.materials.new('decal fixture')
        with patch.object(TagDocument, 'reference', return_value=SimpleNamespace(
                RelativePath='fixture', Filename='fixture.bitmap')), patch.object(
                converter, 'bitmap_to_image', return_value=SimpleNamespace(image=image)):
            converter.ShaderTag._to_nodes_halo1(reader, mat)
        return mat

    def render(self, material, engine):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        scene = bpy.context.scene
        scene.render.engine = engine
        scene.render.resolution_x = scene.render.resolution_y = 16
        scene.render.resolution_percentage = 100
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        scene.world.color = (0, 0, 0)
        background = bpy.data.materials.new('background')
        background.use_nodes = True
        tree = background.node_tree
        tree.nodes.clear()
        emit = tree.nodes.new('ShaderNodeEmission')
        emit.inputs['Color'].default_value = (.25, .25, .25, 1)
        output = tree.nodes.new('ShaderNodeOutputMaterial')
        tree.links.new(emit.outputs[0], output.inputs[0])
        for z, mat in ((0, background), (.01, material)):
            mesh = bpy.data.meshes.new('quad without UVs')
            mesh.from_pydata([(-2,-2,z), (2,-2,z), (2,2,z), (-2,2,z)], [], [(0,1,2,3)])
            ob = bpy.data.objects.new('quad', mesh)
            scene.collection.objects.link(ob)
            mesh.materials.append(mat)
        camera = bpy.data.cameras.new('camera')
        camera.type = 'ORTHO'
        camera.ortho_scale = 2
        ob = bpy.data.objects.new('camera', camera)
        scene.collection.objects.link(ob)
        ob.location = (0, 0, 2)
        scene.camera = ob
        with tempfile.TemporaryDirectory() as directory:
            scene.render.image_settings.file_format = 'OPEN_EXR'
            scene.render.filepath = str(Path(directory) / 'test.exr')
            bpy.ops.render.render(write_still=True)
            image = bpy.data.images.load(scene.render.filepath, check_existing=False)
            pixels = list(image.pixels)
            bpy.data.images.remove(image)
        return pixels

    def test_generated_coordinates_and_uv_fallback(self):
        for generated in (True, False):
            mat = self.material('multiply', (1, 1, 1, 1), generated=generated)
            bitmap = mat.node_tree.nodes.get('map')
            self.assertEqual(bool(bitmap.inputs['Vector'].links), generated)
            if generated:
                self.assertEqual(bitmap.inputs['Vector'].links[0].from_socket.name, 'Generated')
            self.assertEqual(mat.surface_render_method, 'BLENDED')

    def test_blend_rendering(self):
        cases = [
            ('multiply', (1, 1, 1, 1), (0, 0), (.25, .25, .25)),
            # Multiply must use RGB even when bitmap alpha is zero.
            ('multiply', (.5, .25, 1, 0), (0, 0), (.125, .0625, .25)),
            ('multiply', (0, 0, 0, 1), (.5, .5), (.125, .125, .125)),
            ('alpha blend', (1, 0, 0, 0), (0, 0), (.25, .25, .25)),
            ('add', (.1, 0, 0, 0), (0, 0), (.35, .25, .25)),
            ('alpha multiply add', (.2, 0, 0, .5), (.5, .5), (.30, .25, .25)),
            ('double multiply', (.5, .5, .5, 1), (0, 0), (.25, .25, .25)),
        ]
        for engine in ('CYCLES', 'BLENDER_EEVEE'):
            for blend, rgba, intensity, expected in cases:
                with self.subTest(engine=engine, blend=blend, rgba=rgba):
                    pixels = self.render(self.material(blend, rgba, intensity), engine)
                    center = (8 * 16 + 8) * 4
                    for actual, target in zip(pixels[center:center + 3], expected):
                        self.assertAlmostEqual(actual, target, delta=.015)

    def test_generated_texture_covers_uvless_quad(self):
        material = self.material('multiply', (1, 1, 1, 1))
        bitmap = material.node_tree.nodes.get('map')
        bitmap.image.scale(2, 2)
        bitmap.image.pixels[:] = [1, 0, 0, 1, 0, 1, 0, 1,
                                 0, 0, 1, 1, 1, 1, 1, 1]
        bitmap.interpolation = 'Closest'
        for engine in ('CYCLES', 'BLENDER_EEVEE'):
            pixels = self.render(material, engine)
            for (x, y), expected in zip(
                    ((3, 3), (12, 3), (3, 12), (12, 12)),
                    ((.25, 0, 0), (0, .25, 0), (0, 0, .25), (.25, .25, .25))):
                with self.subTest(engine=engine, pixel=(x, y)):
                    index = (y * 16 + x) * 4
                    for actual, target in zip(pixels[index:index + 3], expected):
                        self.assertAlmostEqual(actual, target, delta=.015)

    def test_unsupported_blend_warns(self):
        for blend in ('subtract', 'component min', 'component max'):
            with patch.object(converter.utils, 'print_warning') as warning:
                self.material(blend, (1, 1, 1, 1))
                warning.assert_called_once()


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('H1 decal tests failed')
