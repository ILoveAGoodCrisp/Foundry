"""Run in background Blender; optionally append -- --kit <Reach editing kit>.

Native tests copy Tool into an isolated temporary project. The supplied kit's
assets are never changed. Other tests need only the bundled blam-tags wheel.
"""
import argparse
import ast
import importlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile

import bpy
import numpy as np

ADDON = Path(__file__).resolve().parent / 'addons/io_scene_foundry'
parser = argparse.ArgumentParser()
parser.add_argument('--kit', type=Path)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
TEMP = tempfile.TemporaryDirectory(prefix='foundry_bitmap_export_', ignore_cleanup_errors=True)
ROOT = Path(TEMP.name)
DATA = ROOT / 'data'
TAGS = ROOT / 'tags'
DATA.mkdir()
TAGS.mkdir()
zipfile.ZipFile(next((ADDON / 'wheels').glob('blam_tags*'))).extractall(ROOT / 'python')
sys.path.insert(0, str(ROOT / 'python'))
if args.kit:
    for name in ('tool.exe', 'granny2_x64.dll', 'libfbxsdk.dll', 'steam_appid.txt'):
        if (args.kit / name).is_file():
            shutil.copy2(args.kit / name, ROOT / name)

package = types.ModuleType('bitmap_test_foundry')
package.__path__ = [str(ADDON)]
sys.modules[package.__name__] = package
tools_package = types.ModuleType(package.__name__ + '.tools')
tools_package.__path__ = [str(ADDON / 'tools')]
sys.modules[tools_package.__name__] = tools_package
utils = types.ModuleType(package.__name__ + '.utils')
utils.get_data_path = lambda: str(DATA)
utils.get_tags_path = lambda: str(TAGS)
utils.get_asset_path = lambda: 'asset'
utils.get_scene_props = lambda: types.SimpleNamespace(scene_project='test')
utils.get_project = lambda *a, **kw: types.SimpleNamespace(game='reach', data_directory=str(DATA))
utils.relative_path = lambda p: str(Path(p).relative_to(DATA))
utils.valid_image_name = lambda name: Path(name).stem
utils.dot_partition = lambda name: name.rpartition('.')[0]
utils.is_corinth = lambda: False
utils.print_warning = utils.print_error = print
sys.modules[utils.__name__] = utils


def run_tool(argv, *unused):
    result = subprocess.run([str(ROOT / 'tool.exe'), *argv], cwd=ROOT,
                            capture_output=True, timeout=50)
    if result.returncode or b'compression support is not configured' in result.stderr:
        raise RuntimeError(result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
    return 0


utils.run_tool = run_tool
exporter = importlib.import_module(package.__name__ + '.tools.export_bitmaps')
tiff = importlib.import_module(package.__name__ + '.tools.bitmap_tiff')
baker_module = importlib.import_module(package.__name__ + '.tools.material_bitmap_mapping')
BitmapTag = exporter.BitmapTag


class ImageProperties(bpy.types.PropertyGroup):
    filepath: bpy.props.StringProperty()
    source_name: bpy.props.StringProperty()
    bitmap_type: bpy.props.StringProperty(default='Material Map')
    reexport_tiff: bpy.props.BoolProperty()


bpy.utils.register_class(ImageProperties)
bpy.types.Image.nwo = bpy.props.PointerProperty(type=ImageProperties)

# Exercise the actual shader writer's cache/path selection without initializing
# unrelated shader tag readers and UI modules.
source = ast.parse((ADDON / 'tags/shader_converter.py').read_text())
method = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == '_get_bitmap_path')
scope = dict(vars(exporter))
exec(compile(ast.Module(body=[method], type_ignores=[]), 'shader_converter.py', 'exec'), scope)
writer = types.SimpleNamespace(tags_dir=str(TAGS), data_dir=str(DATA))


def image_fixture(name, width=16, height=8):
    image = bpy.data.images.new(name, width=width, height=height, alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    image.alpha_mode = 'CHANNEL_PACKED'
    y, x = np.mgrid[:height, :width]
    pixels = np.stack((x / max(1, width - 1), y / max(1, height - 1),
                       np.ones_like(x) * .4, x / max(1, width - 1)), axis=-1)
    image.pixels.foreach_set(pixels.astype(np.float32).ravel())
    image.filepath_raw = str(DATA / (name + '.tif'))
    image.file_format = 'TIFF'
    image.nwo.filepath = name + '.tif'
    return image


class BitmapExportTests(unittest.TestCase):
    def cube_fixture(self, name, *, metadata=False, numbered=False):
        folder = ROOT / 'foreign_data'
        folder.mkdir(exist_ok=True)
        raw = folder / (name + '.tiff')
        if numbered:
            raw = folder / name / (name + '_00001.tiff')
            raw.parent.mkdir(exist_ok=True)
        rgba = np.zeros((48, 64, 4), dtype=np.uint8)
        rgba[:] = (0, 0, 255, 255)  # Tool's color-plate background marker.
        for (col, row), color in zip([(1,0), (0,1), (1,1), (2,1), (3,1), (1,2)],
                                     [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (255,0,255), (0,255,255)]):
            gradient = np.arange(16, dtype=np.uint8)[None, :, None] * 3
            rgba[row*16:(row+1)*16, col*16:(col+1)*16, :3] = (np.array(color) * .75).astype(np.uint8) + gradient
            rgba[row*16:(row+1)*16, col*16:(col+1)*16, 3] = 255
        tiff.write_rgba_tiff(raw, 64, 48, rgba.tobytes())
        preview = image_fixture(name + '_equirectangular' + ('_00001' if numbered else ''), 64, 32)
        preview.filepath_raw = str(folder / Path(preview.filepath_raw).name)
        if metadata:
            preview['foundry_cubemap_source'] = str(raw)
        return preview, raw

    def test_uncompressed_tiff_preserves_rows_and_alpha(self):
        image = image_fixture('roundtrip')
        tiff.write_image_tiff(image, image.filepath_raw)
        data = Path(image.filepath_raw).read_bytes()
        count = struct.unpack_from('<H', data, 8)[0]
        fields = dict((struct.unpack_from('<HHII', data, 10+i*12)[0], struct.unpack_from('<HHII', data, 10+i*12)[3]) for i in range(count))
        self.assertEqual(fields[259], 1)
        loaded = bpy.data.images.load(image.filepath_raw, check_existing=False)
        loaded.colorspace_settings.name = 'Non-Color'
        loaded.alpha_mode = 'CHANNEL_PACKED'
        self.assertEqual(tuple(loaded.size), (16, 8))
        np.testing.assert_allclose(loaded.pixels[:], image.pixels[:], atol=1/255)

    def test_conversion_baker_writes_tool_compatible_tiff(self):
        mat = bpy.data.materials.new('bake_test')
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = image_fixture('bake_input')
        baker = baker_module.DataTextureBaker(mat.node_tree, DATA)
        baked = baker.bake(tex.outputs['Alpha'], 'mask')
        self.assertEqual(baked.image.source, 'FILE')
        data = Path(baked.image.filepath_raw).read_bytes()
        _, _, value = next(struct.unpack_from('<HII', data, 12+i*12) for i in range(struct.unpack_from('<H', data, 8)[0]) if struct.unpack_from('<H', data, 10+i*12)[0] == 259)
        self.assertEqual(value, 1)

    def test_cube_resolution_metadata_legacy_and_numbered(self):
        for metadata, numbered in [(True, False), (False, False), (False, True)]:
            preview, raw = self.cube_fixture(f'cube_{metadata}_{numbered}', metadata=metadata, numbered=numbered)
            cube = exporter.bitmap_export_image(preview)
            self.assertEqual(Path(cube.filepath_from_user()), raw)
            self.assertEqual(cube.nwo.bitmap_type, 'Cube Map (Reflection Map)')
            self.assertNotEqual(cube, preview)
            self.assertEqual(tuple(preview.size), (64, 32))

    def test_missing_cube_source_fails_instead_of_writing_preview(self):
        image = image_fixture('missing_equirectangular')
        with self.assertRaisesRegex(RuntimeError, 'original cubemap TIFF is missing'):
            exporter.export_bitmap(image)

    @unittest.skipUnless(args.kit, 'requires --kit Reach editing kit')
    def test_compiler_preserves_generated_maps_and_repairs_existing_tags(self):
        for name, usage in [('specular', 'Material Map'), ('self_illum', 'Self-Illum Map')]:
            image = image_fixture(name)
            image.nwo.bitmap_type = usage
            image['foundry_channel_conversion'] = True
            image.save()  # Old Blender-generated Deflate TIFF.
            # Existing tags must not short-circuit the repair path.
            with BitmapTag(path=name + '.bitmap') as bitmap:
                bitmap.new_bitmap(name, usage, 'Non-Color')
            path = scope['_get_bitmap_path'](writer, types.SimpleNamespace(image=image))
            self.assertEqual(Path(path), Path(name + '.bitmap'))
            with BitmapTag(path=path) as bitmap:
                width, height, rgba = bitmap._uncompressed_rgba_tiff(bitmap.tag.bitmap_tiff(0))
                self.assertEqual((width, height), (16, 8))
                decoded = np.frombuffer(rgba, dtype=np.uint8).reshape(height, width, 4)[::-1]
                expected = np.asarray(image.pixels[:]).reshape(height, width, 4) * 255
                # DXT5 shares a color line within each 4x4 block; the fixture
                # deliberately varies R and G independently. Alpha is separate.
                np.testing.assert_allclose(decoded[:, :, :3], expected[:, :, :3], atol=32)
                np.testing.assert_allclose(decoded[:, :, 3], expected[:, :, 3], atol=5)
            self.assertFalse(exporter.bitmap_needs_rebuild(image))

    @unittest.skipUnless(args.kit, 'requires --kit Reach editing kit')
    def test_compiler_exports_original_cube_cross(self):
        preview, raw = self.cube_fixture('native_cube', metadata=True)
        # An old, existing equirectangular bitmap must not be reused.
        with BitmapTag(path=Path(preview.nwo.filepath).with_suffix('.bitmap')) as bitmap:
            bitmap.new_bitmap('bad_preview', 'Diffuse Map', 'sRGB')
        path = scope['_get_bitmap_path'](writer, types.SimpleNamespace(image=preview))
        self.assertNotIn('equirectangular', str(path))
        with BitmapTag(path=path) as bitmap:
            self.assertTrue(bitmap.is_cubemap)
            self.assertEqual(bitmap._select_int(bitmap.block_bitmaps[0], 'width'), 16)
            self.assertEqual(bitmap._select_int(bitmap.block_bitmaps[0], 'height'), 16)
            _, _, original = bitmap._uncompressed_rgba_tiff(raw.read_bytes())
            original = np.frombuffer(original, dtype=np.uint8).reshape(48, 64, 4)
            raw_pixels = bitmap.tag.root().field('processed pixel data').value
            # Tool stores all six faces of each mip together. Decode each top
            # face as 2D; the library's cube TIFF reader assumes chain-major data.
            first = bitmap.block_bitmaps[0]
            first.field('type').set('2D texture')
            first.field('mipmap count').set(0)
            for index, (col, row) in enumerate(((0,1), (2,1), (1,0), (1,2), (1,1), (3,1))):
                bitmap.tag.root().field('processed pixel data').set(raw_pixels[index*256:(index+1)*256])
                width, height, rgba = bitmap._uncompressed_rgba_tiff(bitmap.tag.bitmap_tiff(0))
                decoded = np.frombuffer(rgba, dtype=np.uint8).reshape(height, width, 4)
                expected = original[row*16:(row+1)*16, col*16:(col+1)*16]
                np.testing.assert_allclose(decoded.astype(float), expected.astype(float), atol=8)
        self.assertTrue((DATA / Path(path).with_suffix('.tif')).exists())
        # Reusing the preview must find the resolved tag without recompiling.
        original_run = utils.run_tool
        try:
            utils.run_tool = lambda *a, **kw: self.fail('already exported cube was compiled again')
            self.assertEqual(scope['_get_bitmap_path'](writer, types.SimpleNamespace(image=preview)), str(path))
        finally:
            utils.run_tool = original_run


try:
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BitmapExportTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
finally:
    del bpy.types.Image.nwo
    bpy.utils.unregister_class(ImageProperties)
    TEMP.cleanup()
