"""Real-binding metadata regression tests, no Blender or .NET required."""
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
package = ModuleType('foundry_native_tags')
package.__path__ = [str(ADDON / 'tags')]
sys.modules[package.__name__] = package
metadata = importlib.import_module('foundry_native_tags.metadata')
backend = importlib.import_module('foundry_native_tags.backend')
lighting = importlib.import_module('foundry_native_tags.lighting')
lighting = importlib.import_module('foundry_native_tags.lighting')
animation_names = importlib.import_module('foundry_native_tags.animation_names')


class MetadataTests(unittest.TestCase):
    def test_animation_names_convert_for_target_project(self):
        convert = animation_names.convert_animation_name_for_project
        mode_names = {
            'stand': 'combat', 'B-driver': 'banshee_d',
            'W-driver': 'warthog_d', 'W-gunner': 'warthog_g',
            'W-passenger': 'warthog_p', 'scorpion-driver': 'scorpion_d',
            'GT-gunner': 'shade_g', 'G-driver': 'ghost_d',
            'P-riderLB02': 'pelican_p_l05', 'P-riderLB01': 'pelican_p_l04',
            'P-riderLB': 'pelican_p_l03', 'P-riderLM': 'pelican_p_l02',
            'P-riderLF': 'pelican_p_l01', 'P-riderRB02': 'pelican_p_r05',
            'P-riderRB01': 'pelican_p_r04', 'P-riderRB': 'pelican_p_r03',
            'P-riderRM': 'pelican_p_r02', 'P-riderRF': 'pelican_p_r01',
            'scorpionLF': 'scorpion_p_lf', 'scorpionLB': 'scorpion_p_lb',
            'scorpionRF': 'scorpion_p_rf', 'scorpionRB': 'scorpion_p_rb',
            'wraith-driver': 'wraith_d', 'CD-passenger01': 'fork_p_r1',
            'CD-passengerL01': 'fork_p_l1',
        }
        for source, target in mode_names.items():
            with self.subTest(source=source):
                self.assertEqual(
                    convert(f'{source} rifle idle', 'halo1', 'halo2'),
                    f'{target} rifle idle')

        self.assertEqual(
            convert('stand unarmed aim-move%12', 'halo1', 'reach'),
            'combat unarmed aim_move_up var12')
        self.assertEqual(
            convert('W-driver:any:any:any:aim-still%2', 'halo1', 'halo3'),
            'warthog_d:any:any:any:aim_still_up:var2')
        self.assertEqual(
            convert('stand idle 2 W-driver aim-still', 'halo1', 'halo2'),
            'combat idle 2 warthog_d aim_still_up')
        self.assertEqual(
            convert('stand h-kill front l-thigh', 'halo1', 'halo2'),
            'combat h_kill front l_leg')
        self.assertEqual(
            convert('stand h-kill back r-thigh', 'halo1', 'reach'),
            'combat h_kill back r_leg')
        self.assertEqual(
            convert('combat stand idle', 'halo1', 'halo2'),
            'combat stand idle')
        self.assertEqual(
            convert('combat rifle berserk', 'halo3', 'reach'),
            'combat rifle go_berserk')
        self.assertEqual(
            convert('stand rifle idle%1', 'halo1', 'halo1'),
            'stand rifle idle%1')

    def test_animation_names_convert_back_to_legacy(self):
        convert = animation_names.convert_animation_name_for_project
        for source in ('reach', 'halo4', 'halo2a'):
            for target in ('halo1', 'halo2', 'halo3', 'halo3odst'):
                expected = 'stand rifle berserk%2' if target == 'halo1' else 'combat rifle berserk var2'
                self.assertEqual(convert('combat rifle go_berserk var2', source, target), expected)
        for legacy_mode, later_mode in animation_names.H1_MODE_CONVERSIONS.items():
            self.assertEqual(convert(f'{later_mode}:rifle:aim_still_up:var3', 'reach', 'halo1'),
                             f'{legacy_mode}:rifle:aim-still%3')
        self.assertEqual(convert('combat h_kill front l_leg', 'reach', 'halo1'), 'stand h-kill front l-thigh')
        self.assertEqual(convert('combat idle 2 warthog_d aim_still_up', 'reach', 'halo1'),
                         'stand idle 2 w-driver aim-still')
        self.assertEqual(convert('combat go_berserk idle', 'reach', 'halo2'), 'combat go_berserk idle')
        self.assertEqual(convert('combat beam_rifle turn_left', 'reach', 'halo1'), 'stand beam_rifle turn-left')
        self.assertEqual(convert('combat rifle idle var1', 'reach', 'reach'), 'combat rifle idle var1')

    def test_native_pca_render_metadata_and_coefficients(self):
        import struct
        pca = importlib.import_module('foundry_native_tags.pca')
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with backend.TagDocument('test.render_model', **args) as render:
                    geometry = render.required_field(render.tag.root(), 'render geometry').as_struct()
                    meshes = render.block(geometry, 'per mesh temporary')
                    mesh = meshes[meshes.add()]
                    vertices = render.block(mesh, 'raw vertices')
                    vertices.add()
                    vertices.add()
                    indices = render.block(geometry, 'PCA Mesh Indices')
                    for i in (0, -1, 99):
                        render.required_field(indices[indices.add()], 'mesh index').set(i)
                    compression = render.block(geometry, 'compression info')
                    bounds = compression[compression.add()]
                    for name, values in [('position bounds 0', (0., 1., 2.)), ('position bounds 1', (3., 4., 5.))]:
                        field = render.required_field(bounds, name)
                        field.set(type(field.value)(*values))
                with pca.PCAAnimationDocument('test.pca_animation', **args) as doc:
                    doc.set_reference(doc.tag.root(), 'RenderModel', 'test.render_model')
                    block = doc.block(doc.tag.root(), 'frame data')
                    for row in ((0., .25), (1., .75)):
                        doc.required_field(block[block.add()], 'Coefficients').set(struct.pack('<ff', *row))
                before = (Path(root) / 'test.pca_animation').read_bytes()
                with pca.PCAAnimationDocument('test.pca_animation', **args) as doc:
                    counts, bounds = doc.render_mesh_info()
                    self.assertEqual(counts, {2: 0})
                    self.assertEqual((bounds.x0, bounds.x1, bounds.y0, bounds.y1, bounds.z0, bounds.z1), (0, 100, 200, 300, 400, 500))
                    self.assertEqual(doc.coefficient_rows(), [(0., .25), (1., .75)])
                    doc.required_field(doc.block(doc.tag.root(), 'frame data')[0], 'Coefficients').set(b'bad')
                    with self.assertRaisesRegex(ValueError, 'incomplete float'):
                        doc.coefficient_rows()
                self.assertEqual((Path(root) / 'test.pca_animation').read_bytes(), before)

    def test_native_structure_seam_geometry(self):
        seams = importlib.import_module('foundry_native_tags.seams')
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with seams.StructureSeamsDocument('test.structure_seams', **args) as doc:
                    block = doc.block(doc.tag.root(), 'seams')
                    element = block[block.add()]
                    final = doc.required_field(element, 'final').as_struct()
                    points = doc.block(final, 'points')
                    for coords in ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)):
                        p = points[points.add()]
                        field = doc.required_field(p, 'final point')
                        field.set(type(field.value)(*coords))
                    triangles = doc.block(final, 'triangles')
                    triangle = triangles[triangles.add()]
                    for i, value in enumerate((2, 0, 1)):
                        doc.required_field(triangle, f'final point{i}').set(value)
                    # Original vertices and final edges intentionally empty: triangles index final points.
                path = Path(root) / 'test.structure_seams'
                before = path.read_bytes()
                with seams.StructureSeamsDocument(path, **args) as doc:
                    record, = doc.read_geometry()
                    self.assertEqual(record.vertices, ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))
                    self.assertEqual(record.triangles, ((2, 0, 1),))
                    final = doc.required_field(doc.block(doc.tag.root(), 'seams')[0], 'final').as_struct()
                    triangle = doc.block(final, 'triangles')[0]
                    doc.required_field(triangle, 'final point0').set(-1)
                    with self.assertRaisesRegex(ValueError, 'invalid triangle'):
                        doc.read_geometry()
                    doc.required_field(triangle, 'final point0').set(0)
                    with self.assertRaisesRegex(ValueError, 'degenerate triangle'):
                        doc.read_geometry()
                self.assertEqual(path.read_bytes(), before)

    def test_cinematic_dynamic_lighting_metadata(self):
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                (Path(root) / 'lamp.light').touch()
                with lighting.CinematicLightingDocument('test.new_cinematic_lighting', **args) as doc:
                    if game not in {'halo4', 'halo2a'}:
                        block = doc.block(doc.tag.root(), 'dynamic lights')
                        for reference in ('lamp.light', 'missing.light', None):
                            element = block[block.add()]
                            doc.set_reference(element, 'light', reference)
                            for field, value in [('Direction', 90.), ('Front-Back', 30.), ('Distance', 2.)]:
                                doc.required_field(element, field).set(value)
                            flags = doc.required_field(element, 'Flags')
                            flags.set_flag('follow object', True)
                            flags.set_flag('position at marker', True)
                path = Path(root) / 'test.new_cinematic_lighting'
                before = path.read_bytes()
                with lighting.CinematicLightingDocument(path, **args) as doc:
                    records = doc.dynamic_lights()
                    self.assertFalse(doc.tag_has_changes)
                self.assertEqual(before, path.read_bytes())
                if game in {'halo4', 'halo2a'}:
                    self.assertEqual(records, [])
                else:
                    self.assertEqual(len(records), 1)
                    record = records[0]
                    self.assertEqual(record.reference.RelativePathWithExtension, 'lamp.light')
                    self.assertTrue(record.follow_object and record.use_marker)
                    self.assertEqual((record.direction, record.front_back, record.distance), (90., 30., 2.))

    def test_lightmap_region_settings(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    doc.restrict_to_region((-1., -2., -3.), (1., 2., 3.))
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    settings = doc.settings('Global lightmapper settings')
                    self.assertEqual(doc.value(settings, 'Mode'), 'One bounce')
                    self.assertEqual(tuple(doc.value(settings, 'Indirect Restrict AABB Min').to_array()), (-1., -2., -3.))
                    self.assertTrue(doc.required_field(settings, 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    self.assertTrue(doc.required_field(doc.settings('Local lightmapper settings'), 'Local flags').get_flag('Enable AO'))
                    doc.required_field(settings, 'Mode').set(2)
                    doc.restrict_to_region((0., 0., 0.), (1., 1., 1.))
                    self.assertEqual(doc.value(settings, 'Mode'), 'Two bounce')
                    doc.clear_region_restriction()
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    self.assertFalse(doc.required_field(doc.settings('Global lightmapper settings'), 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    with self.assertRaises(ValueError):
                        doc.restrict_to_region((1., 0., 0.), (0., 0., 0.))

    def test_lightmap_region_settings(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    doc.restrict_to_region((-1., -2., -3.), (1., 2., 3.))
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    settings = doc.settings('Global lightmapper settings')
                    self.assertEqual(doc.value(settings, 'Mode'), 'One bounce')
                    self.assertEqual(tuple(doc.value(settings, 'Indirect Restrict AABB Min').to_array()), (-1., -2., -3.))
                    self.assertTrue(doc.required_field(settings, 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    self.assertTrue(doc.required_field(doc.settings('Local lightmapper settings'), 'Local flags').get_flag('Enable AO'))
                    doc.required_field(settings, 'Mode').set(2)
                    doc.restrict_to_region((0., 0., 0.), (1., 1., 1.))
                    self.assertEqual(doc.value(settings, 'Mode'), 'Two bounce')
                    doc.clear_region_restriction()
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    self.assertFalse(doc.required_field(doc.settings('Global lightmapper settings'), 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    with self.assertRaises(ValueError):
                        doc.restrict_to_region((1., 0., 0.), (0., 0., 0.))

    def create(self, cls, root, game, name='test'):
        return cls(name + '.' + cls.tag_ext, tags_root=root, game=game)

    def populate_option(self, doc):
        block = doc.parameters()
        for index, kind in enumerate(metadata.OPTION_TYPES):
            element = block[block.add()]
            for name, value in [('parameter name', kind), ('parameter type', index),
                                ('default real value', 2.5), ('default int/bool value', 7)]:
                doc.required_field(element, name).set(value)
            if index == 0:
                doc.required_field(element, 'default bitmap').set((doc.api.parse_group_tag('bitm'), 'textures/test'))
            color_field = doc.required_field(element, 'default color')
            color_field.set(type(color_field.value)(0xFF804020))
        doc.tag_has_changes = True

    def test_option_types_and_detached_defaults(self):
        for game in ('halo3', 'halo3odst', 'reach'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(metadata.RenderMethodOptionDocument, root, game) as doc:
                    self.populate_option(doc)
                with self.create(metadata.RenderMethodOptionDocument, root, game) as doc:
                    result = doc.get_option_parameters()
                    self.assertEqual(doc.read_parameter_types(), dict(zip(metadata.OPTION_TYPES, range(6))))
                    self.assertEqual(doc.read_defaults()['real'], 2.5)
                    self.assertEqual(doc.read_parameter_names()['real'], 'real')
                self.assertEqual(result['int'].default, 7)
                self.assertEqual(result['argb color'].default[1], 2.5)
                self.assertEqual(result['color'].default, (128/255, 64/255, 32/255, 1.))
                reference = result['bitmap'].default
                self.assertEqual(reference.RelativePathWithExtension, r'textures\test.bitmap')
                self.assertEqual(reference.Filename, str(Path(root) / r'textures\test.bitmap'))

    def test_definition_follows_reference_and_handles_null(self):
        with tempfile.TemporaryDirectory() as root:
            with self.create(metadata.RenderMethodOptionDocument, root, 'reach', 'option') as doc:
                self.populate_option(doc)
            with self.create(metadata.RenderMethodDefinitionDocument, root, 'reach') as doc:
                categories = doc.block(doc.tag.root(), 'categories')
                category = categories[categories.add()]
                doc.required_field(category, 'category name').set('albedo')
                options = doc.block(category, 'options')
                option = options[options.add()]
                doc.required_field(option, 'option name').set('default')
                doc.required_field(option, 'option').set((doc.api.parse_group_tag('rmop'), 'option'))
                option = options[options.add()]
                doc.required_field(option, 'option name').set('none')
            with self.create(metadata.RenderMethodDefinitionDocument, root, 'reach') as doc:
                result = doc.get_defaults()
                self.assertEqual(result['albedo']['default']['real'].default, 2.5)
                self.assertEqual(result['albedo']['none'], {})

    def test_material_defaults_for_h4_and_h2amp(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(metadata.MaterialShaderDocument, root, game) as doc:
                    block = doc.parameters()
                    for index, kind in enumerate(metadata.MATERIAL_TYPES):
                        element = block[block.add()]
                        for name, value in [('parameter name', kind), ('parameter type', index),
                                            ('display name', b'Display\0'), ('real', 3.5), ('int/bool', 5)]:
                            doc.required_field(element, name).set(value)
                with self.create(metadata.MaterialShaderDocument, root, game) as doc:
                    result = doc.get_defaults()
                    self.assertEqual(doc.read_parameters()['real'], ['Display', 'real'])
                    self.assertEqual(doc.read_parameters_list(), list(metadata.MATERIAL_TYPES))
                self.assertEqual(result['real'].default, 3.5)
                self.assertEqual(result['bitmap'].default, None)
                self.assertEqual(result['color'].ui_name, 'Display')

    def test_globals_names_and_empty_camera(self):
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(metadata.GlobalsDocument, root, game) as doc:
                    block = doc.block(doc.tag.root(), 'materials')
                    element = block[block.add()]
                    doc.required_field(element, 'name').set('metal')
                with self.create(metadata.GlobalsDocument, root, game) as doc:
                    self.assertEqual(doc.get_global_materials(), ['metal'])
                    self.assertIsNone(doc.get_camera_fov())
                    cameras = doc.block(doc.tag.root(), 'camera')
                    camera = cameras[cameras.add()]
                    field = camera.field('field of view')
                    if field is not None:
                        field.set(78.)
                    self.assertEqual(doc.get_camera_fov(), None if game == 'halo3' else 78.)


if __name__ == '__main__':
    unittest.main()
