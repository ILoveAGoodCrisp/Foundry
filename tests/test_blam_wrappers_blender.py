"""Exercise the real addon imports and migrated wrappers without starting .NET."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import call, patch
import sys
from zipfile import ZipFile

ADDONS = Path(__file__).resolve().parents[1] / 'blender/addons'
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ADDONS))
sys.path.insert(0, str(TESTS))
_wheel_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for wheel_path in (ADDONS / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(wheel_path) as wheel:
        wheel.extractall(_wheel_directory.name)
sys.path.insert(0, _wheel_directory.name)
from io_scene_foundry import utils


class _RemovedManagedBlam:
    mb_init = None
    Tag = type('RemovedTag', (), {})
    Tags = None


managed_blam = _RemovedManagedBlam()
from io_scene_foundry.tags.model_blender import ModelTag
from io_scene_foundry.tags.object_blender import ObjectTag
from io_scene_foundry.tags.cinematic_lighting import CinematicLightingTag
from io_scene_foundry.tags.globals import GlobalsTag
from io_scene_foundry.tags.render_method_option import RenderMethodOptionTag
from io_scene_foundry.tags.render_method_definition import RenderMethodDefinitionTag
from io_scene_foundry.tags.material_shader import MaterialShaderTag


class WrapperTests(unittest.TestCase):
    def test_legacy_animation_nodes_prefer_exact_prefixed_bones(self):
        from io_scene_foundry.tags.animation import AnimationTag

        frame_head = SimpleNamespace(name='frame head')
        bip_head = SimpleNamespace(name='bip01 head')
        nodes = [
            SimpleNamespace(name='frame head', pose_bone=None),
            SimpleNamespace(name='bip01 head', pose_bone=None),
        ]
        AnimationTag._match_animation_nodes_to_pose_bones(
            nodes, [frame_head, bip_head])
        self.assertIs(nodes[0].pose_bone, frame_head)
        self.assertIs(nodes[1].pose_bone, bip_head)

        fallback = SimpleNamespace(name='head', pose_bone=None)
        AnimationTag._match_animation_nodes_to_pose_bones(
            [fallback], [frame_head])
        self.assertIs(fallback.pose_bone, frame_head)

        ambiguous = SimpleNamespace(name='head', pose_bone=None)
        AnimationTag._match_animation_nodes_to_pose_bones(
            [ambiguous], [frame_head, bip_head])
        self.assertIsNone(ambiguous.pose_bone)

    def test_material_opens_in_generation_specific_tag_editor(self):
        from io_scene_foundry.ui.panel import material
        from io_scene_foundry.tools import halo_launcher

        with tempfile.TemporaryDirectory() as root:
            tag_path = Path(root, 'test.shader_model')
            tag_path.touch()
            context = SimpleNamespace(
                object=SimpleNamespace(
                    active_material=SimpleNamespace(
                        nwo=SimpleNamespace(shader_path=tag_path.name))))
            operator = SimpleNamespace(report=lambda *_args: None)

            with patch.object(material.utils, 'get_tags_path', return_value=root), \
                 patch.object(material.utils, 'run_ek_cmd') as run, \
                 patch.object(halo_launcher, 'tag_editor_executable', return_value='guerilla.exe'):
                material.NWO_OT_MaterialOpenTag.execute(operator, context)
                run.assert_called_once_with(['guerilla.exe', str(tag_path)], True)

            with patch.object(material.utils, 'get_tags_path', return_value=root), \
                 patch.object(material.utils, 'run_ek_cmd') as run, \
                 patch.object(halo_launcher, 'tag_editor_executable', return_value='Foundation.exe'):
                material.NWO_OT_MaterialOpenTag.execute(operator, context)
                run.assert_called_once_with(
                    ['Foundation.exe', '/dontloadlastopenedwindows', str(tag_path)], True)

    def test_halo1_import_sets_classic_model_templates(self):
        from io_scene_foundry.tools import importer
        from io_scene_foundry.tools import get_tag_list

        with tempfile.TemporaryDirectory() as root:
            render_path = Path('objects/test/test.gbxmodel')
            for extension in ('.gbxmodel', '.model_collision_geometry',
                              '.model_animations', '.scenery'):
                path = Path(root, render_path.with_suffix(extension))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            scene_nwo = SimpleNamespace(
                template_model='stale.model',
                template_render_model='',
                template_collision_model='stale.collision_model',
                template_model_animation_graph='stale.model_animation_graph',
                template_physics_model='stale.physics_model',
            )
            armature = SimpleNamespace(
                type='ARMATURE', name='test',
                nwo=SimpleNamespace(node_order_source=str(render_path)))
            class FakeAnimation:
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    pass

                def get_nodes(self):
                    return []

                def node_usages(self):
                    return {}

            with patch.object(importer.utils, 'get_scene_props', return_value=scene_nwo), \
                 patch.object(importer.utils, 'get_project', return_value=SimpleNamespace(game='halo1')), \
                 patch.object(importer.utils, 'get_tags_path', return_value=root), \
                 patch.object(importer, 'AnimationGraphTag', return_value=FakeAnimation()):
                importer.set_asset('.scenery', armature)

            self.assertEqual(scene_nwo.template_model, '')
            self.assertEqual(scene_nwo.template_render_model, str(render_path))
            self.assertEqual(
                scene_nwo.template_collision_model,
                str(render_path.with_suffix('.model_collision_geometry')))
            self.assertEqual(
                scene_nwo.template_model_animation_graph,
                str(render_path.with_suffix('.model_animations')))
            self.assertEqual(scene_nwo.template_physics_model, '')

            with patch.object(utils, 'valid_nwo_asset', return_value=True), \
                 patch.object(utils, 'get_asset_info', return_value=(str(render_path.parent), 'test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo1')), \
                 patch.object(utils, 'get_tags_path', return_value=root):
                self.assertEqual(utils.get_asset_render_model(), str(render_path))
                self.assertEqual(
                    utils.get_asset_collision_model(),
                    str(render_path.with_suffix('.model_collision_geometry')))
                self.assertEqual(
                    utils.get_asset_animation_graph(),
                    str(render_path.with_suffix('.model_animations')))

            with patch.object(get_tag_list, 'get_project',
                              return_value=SimpleNamespace(game='halo1')):
                self.assertEqual(
                    get_tag_list.extensions_from_type('template_render_model'),
                    ('.model', '.gbxmodel'))
                self.assertEqual(
                    get_tag_list.extensions_from_type('template_collision_model'),
                    '.model_collision_geometry')
                self.assertEqual(
                    get_tag_list.extensions_from_type('template_model_animation_graph'),
                    '.model_animations')
                self.assertEqual(
                    get_tag_list.get_glob_from_prop('template_render_model'),
                    '*.model;*.gbxmodel')

    def test_halo1_render_mesh_skips_unsupported_face_properties(self):
        from io_scene_foundry.tags import connected_geometry as geometry

        owner = object.__new__(geometry.Mesh)
        owner.corinth = False
        material = SimpleNamespace(
            lm_res=1,
            lm_ignore_default_res=True,
            lm_chart_group_index=-1,
            lm_transparency=1,
            lm_transparency_override=True,
            lm_analytical_absorb=0.0,
            lm_normal_absorb=0.0,
            lm_translucency=1,
            lm_both_sides=True,
            emissive=SimpleNamespace(),
            emissive_invalid=False,
        )
        part = SimpleNamespace(
            part_type=geometry.PartType.opaque_non_shadowing,
            draw_distance=geometry.DrawDistance.detail_close,
            tessellation=geometry.Tessellation._4x,
            lm_type_per_vertex=True,
            material=material,
        )
        subpart = SimpleNamespace(part=part)
        mesh = SimpleNamespace(polygons=[None])

        with patch.object(geometry.utils, 'get_project',
                          return_value=SimpleNamespace(game='halo1')), \
             patch.object(geometry.utils, 'add_face_prop') as add_face_prop:
            owner._apply_subpart_props(mesh, subpart, None)

        add_face_prop.assert_not_called()

    def test_legacy_jms_implied_root(self):
        from mathutils import Matrix
        from io_scene_foundry.export.legacy import LegacyExportScene

        scene = object.__new__(LegacyExportScene)
        scene.bones = []
        scene.bone_index = {}
        scene.bone_parents = {}
        scene.jms_version = 8213
        scene.to_halo_scale = 1
        scene.export_tag_types = set()
        scene.asset_type = SimpleNamespace(name='MODEL')
        asset = scene.jms_asset('default', [], [], 'render')
        self.assertEqual([node.name for node in asset.nodes], ['implied_root_node'])
        self.assertEqual(asset.nodes[0].parent, -1)
        self.assertEqual(asset.nodes[0].transform.rotation, (0, 0, 0, 1))
        self.assertEqual(asset.nodes[0].transform.translation, (0, 0, 0))

        mesh = SimpleNamespace(
            positions=[(1, 2, 3)], normals=[(0, 0, 1)], bone_weights=None,
            bone_indices=None, bone_bindings=[], vertex_colors=[], texcoords=[])
        node = SimpleNamespace(mesh=mesh, ob=None)
        vertex, = scene.vertices(
            node, Matrix.Identity(4), implied_root=True)
        self.assertEqual(vertex.influences, ((0, 1),))

    def test_h3_legacy_model_tool_dispatch(self):
        from io_scene_foundry.export.legacy import LegacyExportScene

        with tempfile.TemporaryDirectory() as root:
            scene = object.__new__(LegacyExportScene)
            scene.target_game = 'halo3'
            scene.asset_type = SimpleNamespace(name='MODEL')
            scene.asset_path = root
            scene.asset_path_relative = r'objects\test'
            scene.export_settings = SimpleNamespace(
                lightmap_structure=False, event_level='WARNING',
                export_animations='NONE')
            with patch.object(utils, 'run_tool') as run_tool, \
                 patch.object(scene, 'write_object_tags') as write_objects, \
                 patch.object(scene, 'write_classic_animation_events'):
                scene.write_tags()
            run_tool.assert_called_once_with(
                ['bulk-import-model-folder-draft', r'objects\test'],
                event_level='WARNING')
            write_objects.assert_called_once_with()

            scene.export_settings.lightmap_structure = True
            scene.export_settings.export_animations = 'ALL'
            animations = Path(root, 'animations')
            animations.mkdir()
            (animations / 'any idle.jmm').write_text('source')
            with patch.object(utils, 'run_tool') as run_tool, \
                 patch.object(scene, 'write_object_tags'), \
                 patch.object(scene, 'write_classic_animation_events'):
                scene.write_tags()
            self.assertEqual(run_tool.call_args_list, [
                call(
                    ['bulk-import-model-folder', r'objects\test'],
                    event_level='WARNING'),
                call(
                    ['model-animations', r'objects\test'],
                    event_level='WARNING'),
            ])

    def test_native_particle_model_geometry(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.tags import particle_model as module

        class NativeTag:
            def particle_meshes(self, stem):
                self.stem = stem
                return [{
                    'name': 'particle_piece',
                    'positions': [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                    'normals': [(0.0, 0.0, 1.0)] * 3,
                    'texcoords': [(0.0, 0.25), (1.0, 0.25), (0.0, 0.75)],
                    'indices': [0, 1, 2],
                    'material': None,
                }]

        objects_before, meshes_before = set(bpy.data.objects), set(bpy.data.meshes)
        collection = bpy.data.collections.new('particle_test')
        try:
            document = object.__new__(module.ParticleModelTag)
            document._tag = NativeTag()
            document.path = 'particles/test.particle_model'
            with patch.object(module.import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                imported, = document.to_blend_objects(collection, 'requested_name')
            self.assertEqual(document.tag.stem, 'requested_name')
            self.assertEqual(imported.name, 'particle_piece')
            self.assertEqual([tuple(vertex.co) for vertex in imported.data.vertices],
                             [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 100.0, 0.0)])
            self.assertEqual(tuple(imported.data.polygons[0].vertices), (0, 1, 2))
            uv = imported.data.uv_layers['UVMap0'].data
            self.assertEqual([tuple(item.uv) for item in uv],
                             [(0.0, 0.75), (1.0, 0.75), (0.0, 0.25)])

            document.tag.particle_meshes = lambda stem: [{
                'name': 'bad', 'positions': [(0, 0, 0)], 'normals': [(0, 0, 1)],
                'texcoords': [(0, 0)], 'indices': [0, 1, 0]}]
            count = len(bpy.data.meshes)
            with self.assertRaisesRegex(ValueError, 'invalid vertex index'):
                document.to_blend_objects(collection, 'bad')
            self.assertEqual(len(bpy.data.meshes), count)
        finally:
            for ob in set(bpy.data.objects) - objects_before:
                bpy.data.objects.remove(ob, do_unlink=True)
            for mesh in set(bpy.data.meshes) - meshes_before:
                bpy.data.meshes.remove(mesh)
            bpy.data.collections.remove(collection)

    def test_native_lightmap_region_geometry(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.tags import structure_lighting as module
        class RegionProps(bpy.types.PropertyGroup):
            mesh_type: bpy.props.StringProperty()
        bpy.utils.register_class(RegionProps)
        bpy.types.Mesh.nwo = bpy.props.PointerProperty(type=RegionProps)
        objects_before, meshes_before = set(bpy.data.objects), set(bpy.data.meshes)
        collections_before = set(bpy.data.collections)
        try:
            mesh = bpy.data.meshes.new('source_region')
            mesh.from_pydata([(0,0,0),(100,0,0),(100,100,0),(0,100,0)],[],[(0,1,2,3)])
            source = bpy.data.objects.new('source_region', mesh)
            empty = bpy.data.objects.new('empty_region', bpy.data.meshes.new('empty_region'))
            with tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=Path(root)), \
                 patch.object(utils, 'halo_transforms', return_value=Matrix.Scale(.01,4)), \
                 patch.object(module.import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(module.import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(module, 'apply_props_material'), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                path = Path(root, 'regions.scenario_structure_lighting_info')
                with module.ScenarioStructureLightingInfoTag(path) as doc:
                    doc.lightmap_regions_from_blender([SimpleNamespace(ob=empty,name='Empty'),
                                                      SimpleNamespace(ob=source,name='Test Region')])
                before = path.read_bytes()
                with module.ScenarioStructureLightingInfoTag(path) as doc:
                    regions = doc.block(doc.tag.root(), 'regions')
                    self.assertEqual(len(regions),1)
                    self.assertEqual(doc.value(regions[0], 'name'), 'test region')
                    imported, = doc.lightmap_regions_to_blender()
                    self.assertEqual(len(imported.data.polygons), 2)
                    self.assertEqual(imported.data.nwo.mesh_type, '_connected_geometry_mesh_type_lightmap_region')
                    self.assertEqual({tuple(v.co) for v in imported.data.vertices}, {tuple(v.co) for v in mesh.vertices})
                self.assertEqual(path.read_bytes(), before)
                with module.ScenarioStructureLightingInfoTag(path) as doc:
                    doc.lightmap_regions_from_blender([])
                with module.ScenarioStructureLightingInfoTag(path) as doc:
                    self.assertEqual(doc.lightmap_regions_to_blender(), [])
        finally:
            for ob in set(bpy.data.objects) - objects_before:
                bpy.data.objects.remove(ob, do_unlink=True)
            for mesh in set(bpy.data.meshes) - meshes_before:
                bpy.data.meshes.remove(mesh)
            for collection in set(bpy.data.collections) - collections_before:
                bpy.data.collections.remove(collection)
            del bpy.types.Mesh.nwo
            bpy.utils.unregister_class(RegionProps)

    def test_native_structure_lighting_roundtrip(self):
        import bpy
        from mathutils import Matrix, Color
        from io_scene_foundry.tags import structure_lighting as module
        cls = module.ScenarioStructureLightingInfoTag
        string_props = ('light_shape light_cone_projection_shape light_dynamic_shadow_quality light_cinema '
                        'light_jitter_quality light_mode light_game_type light_tag_override light_shader_reference '
                        'light_gel_reference light_lens_flare_reference mesh_type').split()
        bool_props = ('light_physically_correct light_shadows light_screenspace light_ignore_dynamic_objects '
                      'light_cinema_objects_only light_specular_contribution light_diffuse_contribution '
                      'is_sun light_indirect_only light_static_analytic is_cinematic_light light_screenspace_has_specular').split()
        float_props = ('light_intensity light_far_attenuation_start light_far_attenuation_end light_shadow_near_clipplane '
                       'light_shadow_far_clipplane light_shadow_bias_offset light_amplification_factor light_jitter_angle '
                       'light_bounce_ratio light_volume_distance light_volume_intensity light_fade_end_distance '
                       'light_fade_start_distance light_aspect').split()
        props = type('NativeLightingTestProps', (bpy.types.PropertyGroup,), {'__annotations__': {
            **{n: bpy.props.StringProperty() for n in string_props},
            **{n: bpy.props.BoolProperty() for n in bool_props},
            **{n: bpy.props.FloatProperty() for n in float_props}}})
        bpy.utils.register_class(props)
        bpy.types.Light.nwo = bpy.props.PointerProperty(type=props)
        bpy.types.Object.nwo = bpy.props.PointerProperty(type=props)
        original_objects, original_lights = set(bpy.data.objects), set(bpy.data.lights)
        original_collections = set(bpy.data.collections)
        try:
            for game in ('reach','halo4','halo2a'):
                with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=Path(root)), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                     patch.object(utils, 'make_halo_light'), patch.object(utils, 'get_import_scale', return_value=1.), \
                     patch.object(utils, 'calc_light_energy', return_value=4.), \
                     patch.object(module.import_transform, 'scale_factor', return_value=1.), \
                     patch.object(module.import_transform, 'distance', side_effect=lambda v: v * 100), \
                     patch.object(module.import_transform, 'transform_matrix', side_effect=lambda m: m):
                    definitions = []
                    for kind in range(3):
                        name = f'light_{kind}'
                        definitions.append(SimpleNamespace(data_name=name, id=utils.id_from_string(name), type=kind,
                            shape=1, color=Color((.5,.25,.125)), intensity=4., hotspot_size=30., hotspot_cutoff=60.,
                            hotspot_falloff=1., near_attenuation_start=.1, near_attenuation_end=.2,
                            far_attenuation_start=2., far_attenuation_end=8., inverse_squared_falloff=True,
                            aspect=1., lighting_mode=0, cone_shape=0, is_sun=kind == 2,
                            shadow_near_clip=.1, shadow_far_clip=10., shadow_bias=.01, shadow_quality=1,
                            shadows=1, screen_space=0, ignore_dynamic_objects=0, cinema_objects_only=0,
                            cinema_only=0, cinema_exclude=0, specular_contribution=1, diffuse_contribution=1,
                            indirect_amp=1., jitter_sphere=.2, jitter_angle=10., jitter_quality=2,
                            indirect_only=0, static_analytic=1))
                    instances = [SimpleNamespace(data_name=d.data_name, origin=(1.,2.,3.), forward=(1.,0.,0.),
                        up=(0.,0.,1.), light_mode=1, game_type=2, screen_space_specular=True, bounce_ratio=.5,
                        volume_distance=2., volume_intensity=3., fade_out_distance=8., fade_start_distance=6.,
                        light_tag='', shader='', gel='', lens_flare='') for d in reversed(definitions)]
                    path = Path(root, 'test.scenario_structure_lighting_info')
                    with cls(path) as doc:
                        doc.build_tag(instances, definitions)
                    # Repeated writes update existing definitions, then removal/addition remaps indices.
                    with cls(path) as doc:
                        doc.build_tag(instances, definitions)
                        self.assertEqual(len(doc.block_generic_light_definitions), 3)
                        self.assertEqual(len(doc.block_generic_light_instances), 3)
                    with cls(path) as doc:
                        doc.build_tag(instances[:2], definitions[1:])
                    with cls(path) as doc:
                        self.assertEqual(len(doc.block_generic_light_definitions), 2)
                        key = 'Light Definition Index' if game != 'reach' else 'definition index'
                        self.assertEqual([doc.value(e, key) for e in doc.block_generic_light_instances], [1,0])
                        doc.build_tag(instances, definitions)
                    before = path.read_bytes()
                    with cls(path) as doc:
                        objects = doc.to_blender()
                        self.assertEqual([o.data.type for o in objects], ['SUN','SPOT','POINT'])
                        self.assertEqual(tuple(objects[0].matrix_world.translation), (100.,200.,300.))
                        self.assertEqual(objects[1].data.nwo.light_intensity, 4.)
                        self.assertAlmostEqual(objects[1].data.spot_size, 1.04719755)
                        self.assertAlmostEqual(objects[1].data.spot_blend, .5)
                        self.assertAlmostEqual(objects[2].data.color[0], utils.srgb_to_linear(.5))
                    self.assertEqual(path.read_bytes(), before)
                    with cls(path) as doc:
                        instance = doc.block_generic_light_instances[0]
                        doc._set(instance, 'Light Definition Index' if game != 'reach' else 'definition index', 99)
                        count = len(bpy.data.objects)
                        with self.assertRaisesRegex(ValueError, 'invalid light definition index'):
                            doc.to_blender()
                        self.assertEqual(len(bpy.data.objects), count)
                    definitions[0].intensity = float('nan')
                    with self.assertRaisesRegex(ValueError, 'non-finite'):
                        with cls(path) as doc:
                            doc.build_tag(instances, definitions)
                    self.assertEqual(path.read_bytes(), before)
                    definitions[0].intensity = 4.
                    if game != 'reach':
                        with cls(path) as doc:
                            block = doc.block(doc.tag.root(), 'cinematic light instances')
                            entry = block[block.add()]
                            doc._set(entry, 'Light Instance Index', 1)
                            chunks = doc.required_field(entry, 'Active Shots').as_array()
                            doc._set(chunks[0], 'shot flag data', 0x80000000)
                            doc._set(chunks[1], 'shot flag data', 2)
                            doc.tag_has_changes = True
                        with cls(path) as doc:
                            objects = doc.to_blender(cinematic_cameras=list(range(34)))
                            self.assertEqual(doc.camera_lights[31], {objects[1]})
                            self.assertEqual(doc.camera_lights[33], {objects[1]})
                            self.assertEqual(doc.camera_lights[0], set())
                            with self.assertRaisesRegex(NotImplementedError, 'cinematic light links'):
                                doc.build_tag(instances, definitions)
                    with cls(path) as doc:
                        doc.clear_lights()
                    with cls(path) as doc:
                        self.assertEqual(doc.to_blender(), [])
        finally:
            for ob in set(bpy.data.objects) - original_objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            for light in set(bpy.data.lights) - original_lights:
                bpy.data.lights.remove(light)
            for collection in set(bpy.data.collections) - original_collections:
                bpy.data.collections.remove(collection)
            del bpy.types.Light.nwo
            del bpy.types.Object.nwo
            bpy.utils.unregister_class(props)

    def test_native_frame_event_list_roundtrip_and_partial_export(self):
        from io_scene_foundry.tags.frame_event_list import FrameEventListTag, FRAME_EVENT_TYPE
        for game in ('reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=Path(root)), \
                 patch.object(utils, 'game_frame', side_effect=lambda frame: frame), \
                 patch.object(utils, 'blender_frame', side_effect=lambda frame: frame), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                def data(kind, offset=2):
                    result = SimpleNamespace(data_type=kind, frame_offset=offset, marker_name='muzzle', marker=None,
                        event_sound_tag='sound/test.sound', event_effect_tag='effects/test.effect',
                        event_model='objects/test.model', variant='default',
                        damage_effect_reporting_type='unknown', dialogue_event='bump')
                    for attr, _ in FrameEventListTag.reference_flags:
                        setattr(result, 'flag_' + attr, attr == 'allow_on_player')
                    return result
                def animation(name, frame_type='primary keyframe'):
                    event = SimpleNamespace(event_type=FRAME_EVENT_TYPE, frame_frame=14, frame_name=frame_type,
                        event_id=1234, multi_frame='single', event_data=[data('SOUND'), data('EFFECT'), data('DIALOGUE')])
                    return SimpleNamespace(name=name, frame_start=10, export_this=True, animation_events=[event])
                def exported(name):
                    return SimpleNamespace(name=SimpleNamespace(data_name=name, tag_name=name), frame_count=30)
                first, other = animation('owned'), animation('untouched')
                nwo = SimpleNamespace(scene_project='test', animations={'owned': first, 'untouched': other})
                path = Path(root, 'test.frame_event_list')
                with patch.object(utils, 'get_scene_props', return_value=nwo):
                    with FrameEventListTag(path) as doc:
                        doc.from_blender([exported('owned'), exported('untouched')], nwo.animations)
                    with FrameEventListTag(path) as doc:
                        events = doc.collect_events()
                        self.assertEqual(set(events), {'owned','untouched'})
                        event, = events['owned']
                        self.assertEqual((event.frame, event.type, event.unique_id), (4, 'primary keyframe', 1234))
                        self.assertEqual(event.sound_events[0].sound_reference.tag, 'sound\\test.sound')
                        self.assertTrue(event.sound_events[0].sound_reference.allow_on_player)
                        self.assertEqual(event.sound_events[0].frame_offset, 2)
                        self.assertEqual(event.effect_events[0].damage_effect_reporting_type, 'unknown')
                        self.assertEqual(event.dialogue_events[0].dialogue_type, 'bump')
                        if game != 'reach':
                            self.assertEqual(event.sound_events[0].sound_reference.variant, 'default')
                            self.assertEqual(event.sound_events[0].sound_reference.model_tag, 'objects\\test.model')
                            # Scripts owned by another blend must survive a partial export.
                            row = doc._root_block('frame events')[1]
                            scripts = doc.block(row, 'script events')
                            script = scripts[scripts.add()]
                            doc.required_field(script, 'frame event').set(-1)
                            doc.required_field(script, 'script name').set('keep_me')
                            doc.tag_has_changes = True
                    first.animation_events[0].frame_name = 'none'
                    first.animation_events[0].event_data.append(data('SOUND', offset=3))
                    for _ in range(2):
                        with FrameEventListTag(path) as doc:
                            doc.from_blender([exported('owned')], {'owned': first})
                            self.assertEqual(len(doc._root_block('sound references')), 1)
                            self.assertEqual(len(doc._root_block('effect references')), 1)
                            self.assertEqual(len(doc._root_block('frame events')), 2)
                    with FrameEventListTag(path) as doc:
                        nwo.animations = {'owned': first}
                        event, = doc.collect_events()['owned']
                        self.assertEqual(event.type, 'none')
                        self.assertEqual([e.frame_offset for e in event.sound_events], [6,7])
                        self.assertTrue(all(e.animation_event_index == -1 for e in event.sound_events))
                        other_row = doc._root_block('frame events')[1]
                        self.assertEqual(doc.value(doc.block(other_row, 'animation events')[0], 'unique ID'), 1234)
                        if game != 'reach':
                            self.assertEqual(doc.value(doc.block(other_row, 'script events')[0], 'script name'), 'keep_me')
                    before = path.read_bytes()
                    # A failed write after changing references must not overwrite the saved tag.
                    first.animation_events[0].frame_name = 'unsupported event'
                    first.animation_events[0].event_data[0].event_sound_tag = 'sound/new.sound'
                    with self.assertRaisesRegex(ValueError, 'unsupported type'):
                        with FrameEventListTag(path) as doc:
                            doc.from_blender([exported('owned')], {'owned': first})
                    self.assertEqual(path.read_bytes(), before)
                    if game != 'reach':
                        with self.assertRaisesRegex(NotImplementedError, 'script events'):
                            with FrameEventListTag(path) as doc:
                                doc.from_blender([exported('untouched')], {'untouched': other})
                        self.assertEqual(path.read_bytes(), before)
                        with FrameEventListTag(path) as doc:
                            nwo.animations = {'untouched': other}
                            with self.assertRaisesRegex(NotImplementedError, 'script events'):
                                doc.collect_events()
                            nwo.animations = {'owned': first}
                    with FrameEventListTag(path) as doc:
                        sound = doc.block(doc._root_block('frame events')[0], 'sound events')[0]
                        doc.required_field(sound, 'sound').set(99)
                        with self.assertRaisesRegex(ValueError, 'invalid sound reference index'):
                            doc.collect_events()
                        doc.required_field(sound, 'sound').set(0)
                        doc.required_field(sound, 'frame event').set(99)
                        with self.assertRaisesRegex(ValueError, 'invalid frame event index'):
                            doc.collect_events()
                    self.assertEqual(path.read_bytes(), before)
                    first.animation_events.clear()
                    ranged = animation('owned').animation_events[0]
                    ranged.multi_frame = 'range'
                    ranged.frame_range = 17
                    first.animation_events.append(ranged)
                    with FrameEventListTag(path) as doc:
                        doc.from_blender([exported('owned')], {'owned': first})
                    with FrameEventListTag(path) as doc:
                        event, = doc.collect_events()['owned']
                        self.assertEqual((event.frame, event.end_frame), (4,7))
                        self.assertEqual(len(event.sound_events), 1)
                        self.assertEqual(len(doc.block(doc._root_block('frame events')[0], 'animation events')), 4)
                    first.animation_events.clear()
                    with FrameEventListTag(path) as doc:
                        doc.from_blender([exported('owned')], {'owned': first})
                    with FrameEventListTag(path) as doc:
                        self.assertEqual(doc.collect_events()['owned'], [])
                        self.assertEqual(len(doc.block(doc._root_block('frame events')[1], 'animation events')), 1)
                        doc.clear()
                    with FrameEventListTag(path) as doc:
                        self.assertTrue(all(len(doc._root_block(n)) == 0 for n in
                            ('frame events','sound references','effect references')))

    def test_native_structure_design_rejects_incomplete_data(self):
        from io_scene_foundry.tags.structure_design import StructureDesignDocument
        for game in ('halo3', 'reach'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                path = Path(root, 'bad.structure_design')
                with StructureDesignDocument(path, tags_root=root, game=game) as doc:
                    physics = doc.required_field(doc.tag.root(), 'physics').as_struct()
                    groups = doc.block(physics, 'water groups block')
                    groups.add()
                    waters = doc.block(physics, 'water instances block')
                    water = waters[waters.add()]
                    doc.required_field(water, 'group').set(0)
                    doc.block(water, 'water debug triangles block').add()
                before = path.read_bytes()
                with StructureDesignDocument(path, tags_root=root, game=game) as doc:
                    physics = doc.required_field(doc.tag.root(), 'physics').as_struct()
                    water = doc.block(physics, 'water instances block')[0]
                    if game == 'halo3':
                        with self.assertRaisesRegex(NotImplementedError, 'direction/angle'):
                            doc.surfaces()
                    else:
                        doc.required_field(water, 'fog murkiness').set(float('nan'))
                        with self.assertRaisesRegex(ValueError, 'non-finite fog murkiness'):
                            doc.surfaces()
                        doc.required_field(water, 'fog murkiness').set(0.)
                    doc.required_field(water, 'group').set(12)
                    with self.assertRaisesRegex(ValueError, 'invalid water group index'):
                        doc.surfaces()
                    if game == 'reach':
                        doc.required_field(water, 'group').set(0)
                        fogs = doc.block(doc.required_field(doc.tag.root(), 'planar fog set').as_struct(), 'planar fogs')
                        fog = fogs[fogs.add()]
                        doc.block(fog, 'vertices').add()
                        with self.assertRaisesRegex(ValueError, 'complete triangles'):
                            doc.surfaces()
                self.assertEqual(path.read_bytes(), before)

    def test_native_structure_design_surfaces(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.tags.structure_design_blender import StructureDesignTag
        from io_scene_foundry.tags import structure_design_blender as module
        from io_scene_foundry.tags.structure_design import StructureDesignDocument

        class SurfaceProperties(bpy.types.PropertyGroup):
            mesh_type: bpy.props.StringProperty()
            boundary_surface_type: bpy.props.StringProperty()
            fog_appearance_tag: bpy.props.StringProperty()
            fog_volume_depth: bpy.props.FloatProperty()
            water_type: bpy.props.StringProperty()
            water_volume_depth: bpy.props.FloatProperty()
            water_volume_flow_direction: bpy.props.FloatProperty()
            water_volume_flow_velocity: bpy.props.FloatProperty()
            water_volume_fog_color: bpy.props.FloatVectorProperty(size=4)
            water_volume_fog_murkiness: bpy.props.FloatProperty()

        bpy.utils.register_class(SurfaceProperties)
        bpy.types.Mesh.nwo = bpy.props.PointerProperty(type=SurfaceProperties)
        bpy.types.Object.nwo = bpy.props.PointerProperty(type=SurfaceProperties)
        original_objects, original_meshes = set(bpy.data.objects), set(bpy.data.meshes)
        water_material = bpy.data.materials.get('WaterDirection')
        created_material = water_material is None
        if created_material:
            water_material = bpy.data.materials.new('WaterDirection')
        collection = bpy.data.collections.new('native_structure_test')
        try:
            for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
                with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test', forward_direction='x')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=Path(root)), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                     patch.object(module.import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                     patch.object(module.import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)), \
                     patch.object(module, 'apply_props_material'):
                    path = Path(root, 'test.structure_design')
                    def add(doc, parent, name):
                        block = doc.block(parent, name)
                        return block[block.add()]
                    def vector(doc, parent, name, values):
                        field = doc.required_field(parent, name)
                        field.set(type(field.value)(*values))
                    points = ((0.,0.,2.), (1.,0.,2.), (0.,1.,2.))
                    later = game not in {'halo3', 'halo3odst'}
                    with StructureDesignDocument(path, tags_root=root, game=game) as doc:
                        physics = doc.required_field(doc.tag.root(), 'physics').as_struct()
                        for kind in range(3):
                            ceiling = add(doc, physics, 'soft ceilings block')
                            doc.required_field(ceiling, 'type').set(kind)
                            triangle = add(doc, ceiling, 'soft ceiling triangles')
                            for i, point in enumerate(points):
                                vector(doc, triangle, f'vertex{i}', point)
                        if later:
                            fogs = doc.required_field(doc.tag.root(), 'planar fog set').as_struct()
                            fog = add(doc, fogs, 'planar fogs')
                            doc.required_field(fog, 'name').set('fog')
                            doc.required_field(fog, 'depth').set(3.)
                            for point in points:
                                vector(doc, add(doc, fog, 'vertices'), 'position', point)
                            doc.required_field(add(doc, physics, 'water groups block'), 'name').set('water')
                            water = add(doc, physics, 'water instances block')
                            doc.required_field(water, 'group').set(0)
                            vector(doc, water, 'flow velocity', (2.,0.,0.))
                            vector(doc, water, 'fog color', (1.,.5,.25,0.))
                            doc.required_field(water, 'fog murkiness').set(.75)
                            for z in (0.,2.):
                                triangle = add(doc, water, 'water debug triangles block')
                                for i, point in enumerate(points):
                                    vector(doc, triangle, f'point{i}', (*point[:2],z))
                    before = path.read_bytes()
                    with StructureDesignTag(path) as doc:
                        objects = doc.to_blender(collection)
                        self.assertEqual(len(objects), 5 if later else 3)
                        self.assertEqual([ob.data.nwo.boundary_surface_type for ob in objects[:3]],
                                         ['SOFT_CEILING','SOFT_KILL','SLIP_SURFACE'])
                        self.assertEqual(tuple(objects[0].data.vertices[0].co), (0.,0.,200.))
                        self.assertTrue(all(len(ob.data.polygons) == 1 for ob in objects))
                        if later:
                            self.assertEqual(objects[3].nwo.fog_volume_depth, 3.)
                            self.assertEqual(objects[4].nwo.water_volume_flow_velocity, 2.)
                            self.assertAlmostEqual(objects[4].nwo.water_volume_depth, 2 / module.WU_SCALAR, places=4)
                            # Unsupported rain must fail before any object is allocated.
                            add(doc, doc.tag.root(), 'instanced geometries definitions')
                            count = len(bpy.data.objects)
                            with self.assertRaisesRegex(NotImplementedError, 'rain-blocker'):
                                doc.to_blender(collection)
                            self.assertEqual(len(bpy.data.objects), count)
                    self.assertEqual(path.read_bytes(), before)
        finally:
            for ob in set(bpy.data.objects) - original_objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            for mesh in set(bpy.data.meshes) - original_meshes:
                bpy.data.meshes.remove(mesh)
            bpy.data.collections.remove(collection)
            if created_material:
                bpy.data.materials.remove(water_material)
            del bpy.types.Mesh.nwo
            del bpy.types.Object.nwo
            bpy.utils.unregister_class(SurfaceProperties)

    def test_native_cinematic_entry_points(self):
        from io_scene_foundry.tags.cinematic_root import NativeCinematicTag, SceneData
        from io_scene_foundry.tags.cinematic_scene import NativeCinematicSceneTag
        from io_scene_foundry.tags.cinematic import CinematicSceneDataTag
        from io_scene_foundry.tags.backend import TagDocument
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=Path(root)), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                later = game in {'halo4', 'halo2a'}
                with NativeCinematicSceneTag('scene.cinematic_scene', tag_must_exist=False):
                    pass
                if later:
                    with CinematicSceneDataTag('scene.cinematic_scene_data', tag_must_exist=False):
                        pass
                with NativeCinematicTag('test.cinematic', tag_must_exist=False) as doc:
                    scenes = doc.block(doc.tag.root(), 'scenes')
                    element = scenes[scenes.add()]
                    doc.set_reference(element, 'scene', 'scene.cinematic_scene')
                    if later:
                        doc.set_reference(element, 'data', 'scene.cinematic_scene_data')
                    settings = doc.required_field(doc.tag.root(), 'scenario and zone set').as_struct()
                    doc.required_field(settings, 'zone set').set(-1)
                path = Path(root, 'test.cinematic')
                before = path.read_bytes()
                # Exercise native scene/data constructors through the real dispatch, while
                # keeping camera allocation outside this discovery regression.
                result = ('scene', None, [], [], '', [], [], [])
                with NativeCinematicTag(path) as doc, \
                     patch.object(NativeCinematicSceneTag, 'to_blender', return_value=result) as convert:
                    self.assertIsInstance(doc, TagDocument)
                    self.assertEqual(doc.scenario_reference()[1], -1)
                    imported, scenario, zone = doc.to_blender(36)
                    self.assertEqual(len(imported), 1)
                    self.assertEqual(imported[0].name, 'scene')
                    self.assertIsNone(scenario)
                    self.assertEqual(zone, '')
                    self.assertEqual(convert.call_count, 1)
                    self.assertEqual(doc.to_blender(36, specific_scene='missing')[0], [])
                self.assertEqual(path.read_bytes(), before)

    def test_native_cinematic_shot_arrays(self):
        from io_scene_foundry.tags.cinematic import CinematicCameraDocument
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                path = Path(root, 'test.cinematic_scene_data')
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    shots = doc.block(doc.tag.root(), 'shots')
                    for _ in range(34):
                        shots.add()
                    objects = doc.block(doc.tag.root(), 'objects')
                    element = objects[objects.add()]
                    flags = doc.required_field(element, 'shots active flags')
                    chunks = flags.as_array()
                    self.assertGreaterEqual(len(chunks), 2)
                    doc.required_field(chunks[0], 'shot flag data').set(0x80000001)
                    doc.required_field(chunks[1], 'shot flag data').set(7)
                    self.assertEqual(doc.object_records()[0].active_shots, [0,31,32,33])
                    self.assertIsNone(doc.required_field(element, 'name').as_array())
                    stale = chunks[0]
                    objects.add()
                    with self.assertRaises(doc.api.StaleHandleError):
                        doc.value(stale, 'shot flag data')
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    self.assertEqual(doc.object_records()[0].active_shots, [0,31,32,33])

    def test_native_cinematic_music(self):
        from io_scene_foundry.tags.cinematic import CinematicCameraDocument
        from io_scene_foundry.tags.cinematic_scene import CinematicMusic
        from io_scene_foundry.tags.cinematic_scene import CinematicObjectFunctionKeyframe
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                path = Path(root, 'test.cinematic_scene')
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    shots = doc.block(doc.tag.root(), 'shots')
                    music = doc.block(shots[shots.add()], 'music')
                    doc.required_field(doc.tag.root(), 'anchor').set('cinematic_anchor')
                    if game in {'halo4','halo2a'}:
                        lights = doc.block(doc.tag.root(), 'lights')
                        doc.set_reference(lights[lights.add()], 'structure lighting info', 'lighting/test.scenario_structure_lighting_info')
                    for stop in (False, True):
                        element = music[music.add()]
                        doc.set_reference(element, r'music\foley', 'sound/music.sound_looping')
                        doc.required_field(element, 'frame').set(15)
                        doc.required_field(element, 'flags').set_flag('Stop Music At Frame (rather than starting it)', stop)
                    music.add()
                    if game != 'halo3':
                        screens = doc.block(shots[0], 'screen effects')
                        screen = screens[screens.add()]
                        doc.set_reference(screen, 'screen effect', 'effects/test.area_screen_effect')
                        doc.required_field(screen, 'frame').set(5)
                        doc.required_field(screen, 'stop frame').set(25)
                        if game in {'halo4','halo2a'}:
                            doc.required_field(screen, 'flags').set_flag('Persist Entire Shot', True)
                        screens.add()
                        constraints = doc.block(shots[0], 'user input constraints')
                        constraint = constraints[constraints.add()]
                        field = doc.required_field(constraint, 'maximum look angles')
                        field.set(type(field.value)(10, -20, -30, 40))
                        doc.required_field(constraint, 'frame').set(7)
                        doc.required_field(constraint, 'ticks').set(60)
                        doc.required_field(constraint, 'frictional force').set(.5)
                    objects = doc.block(doc.tag.root(), 'objects')
                    doc.required_field(objects[objects.add()], 'name').set('chief')
                    doc.required_field(objects[0], 'variant name').set('default')
                    if game in {'halo3', 'halo3odst', 'reach'}:
                        doc.required_field(objects[0], 'shots active flags').set(3)
                    lights = doc.block(shots[0], 'lighting')
                    for subject in (0, -1, 99):
                        light = lights[lights.add()]
                        doc.set_reference(light, 'lighting', 'lighting/test.new_cinematic_lighting')
                        doc.required_field(light, 'subject').set(subject)
                        doc.required_field(light, 'marker').set('head')
                        if light.field('flags') is not None:
                            doc.required_field(light, 'flags').set_flag('persists across shots', True)
                    lights.add()
                    functions = doc.block(shots[0], 'object functions')
                    function = functions[functions.add()]
                    doc.required_field(function, 'object').set(0)
                    doc.required_field(function, 'function name').set('shield')
                    keys = doc.block(function, 'keyframes')
                    for value in (.25, .75):
                        key = keys[keys.add()]
                        doc.required_field(key, 'frame').set(15)
                        doc.required_field(key, 'value').set(value)
                        doc.required_field(key, 'interpolation time').set(30)
                        doc.required_field(key, 'flags').set_flag('clear function (Value and Interpolation time are unused)', True)
                before = path.read_bytes()
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    records, = doc.music_shots()
                    metadata = doc.scene_metadata()
                    self.assertEqual(metadata.anchor, 'cinematic_anchor')
                    self.assertEqual(len(metadata.lights), 1 if game in {'halo4','halo2a'} else 0)
                    object_record, = doc.object_records()
                    self.assertEqual((object_record.index, object_record.name, object_record.variant), (0,'chief','default'))
                    self.assertEqual(object_record.active_shots, [0] if game in {'halo3','halo3odst','reach'} else None)
                    light, = doc.lighting_shots()[0]
                    self.assertEqual((light.subject, light.marker), (0, 'head'))
                    self.assertEqual(light.lighting.RelativePathWithExtension, 'lighting\\test.new_cinematic_lighting')
                    if game != 'halo3':
                        screen, = doc.screen_effect_shots()[0]
                        self.assertEqual(screen.screen_effect.RelativePathWithExtension, 'effects\\test.area_screen_effect')
                        self.assertEqual((screen.frame, screen.stop_frame), (5,25))
                        self.assertEqual(screen.persist_entire_shot, game in {'halo4','halo2a'})
                        constraint, = doc.user_constraint_shots()[0]
                        self.assertEqual(constraint.maximum_look_angles, (10,-20,-30,40))
                        self.assertEqual((constraint.frame, constraint.ticks, constraint.frictional_force), (7,60,.5))
                    else:
                        self.assertEqual(doc.user_constraint_shots(), [[]])
                    function_record, = doc.object_function_shots()[0]
                    self.assertEqual(function_record.object, 'chief')
                    event = SimpleNamespace()
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        CinematicObjectFunctionKeyframe.from_native(function_record).to_event(
                            SimpleNamespace(cinematic_events=SimpleNamespace(add=lambda: event)), game in {'halo4','halo2a'})
                    self.assertEqual(event.value, .75)
                    self.assertEqual(event.interpolation_time, 1.)
                    self.assertEqual(event.function_name, 'shield')
                    self.assertTrue(event.clear_function)
                self.assertEqual(len(records), 2)
                for record, stop in zip(records, (False, True)):
                    event = SimpleNamespace()
                    nwo = SimpleNamespace(cinematic_events=SimpleNamespace(add=lambda: event))
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        CinematicMusic.from_native(record).to_event(nwo, game in {'halo4','halo2a'})
                    self.assertEqual(event.music, 'sound\\music.sound_looping')
                    self.assertEqual(event.stop, stop)
                    self.assertEqual(event.frame, 15 if game in {'halo4','halo2a'} else 16)
                self.assertEqual(before, path.read_bytes())

    def test_native_cinematic_camera_frames(self):
        from io_scene_foundry.tags.cinematic import CinematicCameraDocument
        from io_scene_foundry.tags.cinematic_scene import CinematicDialogue, CinematicEffect, CinematicCustomScript
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                extension = 'cinematic_scene_data' if game in {'halo4', 'halo2a'} else 'cinematic_scene'
                path = Path(root, 'test.' + extension)
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    shots = doc.block(doc.tag.root(), 'shots')
                    frames = doc.block(shots[shots.add()], 'frame data')
                    doc.required_field(shots[0], 'frame count').set(24)
                    camera = doc.required_field(frames[frames.add()], 'camera frame').as_struct()
                    dynamic = camera.field('dynamic data')
                    constant = camera.field('constant data')
                    dynamic = dynamic.as_struct() if dynamic is not None else camera
                    constant = constant.as_struct() if constant is not None else camera
                    for name, values in [('camera position',(1.,2.,3.)), ('camera forward',(1.,0.,0.)), ('camera up',(0.,0.,1.))]:
                        field = doc.required_field(dynamic, name)
                        field.set(type(field.value)(*values))
                    doc.required_field(constant, 'focal length').set(35.)
                    dialogue = doc.block(shots[0], 'dialogue')
                    element = dialogue[dialogue.add()]
                    doc.set_reference(element, 'dialogue', 'sound/test.sound')
                    doc.required_field(element, 'frame').set(10)
                    doc.required_field(element, 'scale').set(.5)
                    doc.required_field(element, 'lipsync actor').set('chief')
                    doc.required_field(element, 'subtitle').set('hello')
                    objects = doc.block(doc.tag.root(), 'objects')
                    doc.required_field(objects[objects.add()], 'name').set('chief')
                    effects = doc.block(shots[0], 'effects')
                    element = effects[effects.add()]
                    doc.set_reference(element, 'effect', 'effects/test.effect')
                    doc.required_field(element, 'marker parent').set(0)
                    doc.required_field(element, 'frame').set(20)
                    if game in {'halo4', 'halo2a'}:
                        doc.required_field(element, 'state').set(2)
                        doc.required_field(element, 'flags').set_flag('looping', True)
                    effects.add()  # Empty effect references must not create events.
                    doc.set_reference(objects[0], 'model animation graph', 'objects/chief.model_animation_graph')
                    doc.set_reference(objects[0], 'object type', 'objects/chief.biped')
                    scripts = doc.block(shots[0], 'custom script')
                    element = scripts[scripts.add()]
                    doc.required_field(element, 'frame').set(12)
                    script = doc.required_field(element, 'script').as_struct()
                    doc.required_field(script, 'script').set(b'(print "hello")\r\n\x00')
                before = path.read_bytes()
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    records = doc.camera_shots()
                    self.assertEqual(doc.shot_frame_counts(), [24])
                    self.assertEqual(records[0][0].position, (1.,2.,3.))
                    self.assertEqual(records[0][0].lens, 35.)
                    dialogue_record = doc.dialogue_shots()[0][0]
                    dialogue = CinematicDialogue.from_native(dialogue_record)
                    event = SimpleNamespace()
                    nwo = SimpleNamespace(cinematic_events=SimpleNamespace(add=lambda: event))
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        dialogue.to_event(nwo, game in {'halo4', 'halo2a'})
                    self.assertEqual(event.sound_tag, 'sound\\test.sound')
                    self.assertEqual(event.frame, 10 if game in {'halo4','halo2a'} else 11)
                    self.assertEqual(event.sound_scale, .5)
                    self.assertEqual(event.subtitle, 'hello')
                    self.assertEqual(dialogue.actor, 'chief')
                    object_record, = doc.object_records()
                    self.assertEqual(object_record.graph.RelativePathWithExtension, 'objects\\chief.model_animation_graph')
                    self.assertEqual(object_record.object_type.RelativePathWithExtension, 'objects\\chief.biped')
                    effect_record, = doc.effect_shots()[0]
                    effect = CinematicEffect.from_native(effect_record)
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        effect.to_event(nwo, game in {'halo4', 'halo2a'})
                    self.assertEqual(effect.marker_parent, 'chief')
                    self.assertEqual(event.effect, 'effects\\test.effect')
                    self.assertEqual(event.effect_state, '2' if game in {'halo4','halo2a'} else '0')
                    self.assertEqual(event.frame, 20 if game in {'halo4','halo2a'} else 21)
                    script_record, = doc.script_shots()[0]
                    self.assertEqual(script_record.frame, 12)
                    CinematicCustomScript.from_native(script_record).to_event(nwo)
                    self.assertEqual(event.type, 'SCRIPT')
                    self.assertEqual(event.script_type, 'CUSTOM')
                    self.assertEqual(event.script, '(print "hello")\r\n')
                    frames = doc.block(doc.block(doc.tag.root(), 'shots')[0], 'frame data')
                    frames.clear()
                    with self.assertRaisesRegex(ValueError, 'no camera frames'):
                        doc.camera_shots()
                self.assertEqual(records[0][0].forward, (1.,0.,0.))
                self.assertEqual(before, path.read_bytes())

    def test_native_polyart_roundtrip_and_mesh(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.tags.polyart import PolyArtTag, _float_to_short
        from io_scene_foundry import import_transform
        packed = [tuple(_float_to_short(v, 'test') for v in row) for row in
                  [(0.,0.,0.,.5,0.,0.), (10.,0.,0.,1.,1.,0.), (0.,10.,0.,.25,0.,1.)]]
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                 patch.object(import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(import_transform, 'object_matrix', side_effect=lambda m: m), \
                 patch.object(import_transform, 'scale_factor', return_value=1.):
                with PolyArtTag('test.polyart_asset') as tag:
                    tag.from_blender(packed, [(0,1,2)])
                before = Path(root, 'test.polyart_asset').read_bytes()
                old_objects, old_meshes, old_cameras, old_materials = map(set, (bpy.data.objects, bpy.data.meshes, bpy.data.cameras, bpy.data.materials))
                try:
                    with PolyArtTag('test.polyart_asset') as tag:
                        self.assertEqual(len(tag.block_vertices), 3)
                        self.assertEqual(len(tag.placement_data), 1)
                        objects = tag.to_blender()
                        mesh = next(ob.data for ob in objects if ob.type == 'MESH')
                        self.assertEqual(len(mesh.polygons), 1)
                        self.assertAlmostEqual(mesh.vertices[1].co.x, 1.)
                        self.assertAlmostEqual(mesh.color_attributes['Color'].data[0].color[3], .5)
                        self.assertEqual(tuple(mesh.uv_layers[0].data[1].uv), (1.,0.))
                        with self.assertRaisesRegex(RuntimeError, 'outside the vertex block'):
                            tag.from_blender(packed, [(0,1,99)])
                    self.assertEqual(before, Path(root, 'test.polyart_asset').read_bytes())
                finally:
                    for ob in set(bpy.data.objects) - old_objects:
                        bpy.data.objects.remove(ob, do_unlink=True)
                    for data, previous in ((bpy.data.meshes, old_meshes), (bpy.data.cameras, old_cameras), (bpy.data.materials, old_materials)):
                        for item in set(data) - previous:
                            data.remove(item)

    def test_native_decorator_metadata(self):
        from io_scene_foundry.tags.decorator_set import DecoratorSetTag
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with DecoratorSetTag('test.decorator_set', tag_must_exist=False) as tag:
                    instances = tag.block(tag.tag.root(), 'render model instance names')
                    tag.required_field(instances[instances.add()], 'name').set('grass')
                    types = tag.block(tag.tag.root(), 'decorator types')
                    for index in (-1, 0, 99):
                        tag.required_field(types[types.add()], 'mesh').set(index)
                    if game in {'halo3', 'halo3odst'}:
                        tag.reference_base.Path = 'grass.render_model'
                    else:
                        tag.reference_lod2.Path = 'grass.render_model'
                Path(root, 'grass.render_model').touch()
                before = Path(root, 'test.decorator_set').read_bytes()
                with DecoratorSetTag('test.decorator_set') as tag:
                    item, = tag.get_decorator_types()
                    self.assertEqual((item.decorator_type_name, item.decorator_type_index, item.render_model_instance_index), ('grass', 1, 0))
                    self.assertEqual(tag.get_first_valid_render_model().RelativePathWithExtension, 'grass.render_model')
                self.assertEqual(before, Path(root, 'test.decorator_set').read_bytes())

    def test_native_serialized_physics_records(self):
        from io_scene_foundry.tags.physics_blender import PhysicsTag
        from io_scene_foundry.tags.connected_geometry import HavokCollision, RigidBody
        from io_scene_foundry import import_transform
        from mathutils import Matrix
        from unittest.mock import MagicMock
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with PhysicsTag('serialized.physics_model') as tag:
                    groups = tag.block(tag.tag.root(), 'RigidBody Serialized Shapes')
                    group = groups[groups.add()]
                    shapes = tag.block(group, 'Mopp Serialized Havok Data')
                    element = shapes[shapes.add()]
                    base = tag.required_field(element, 'base').as_struct()
                    tag.required_field(base, 'name').set('serialized_body')
                    tag.required_field(base, 'material').set(-1)
                    tag.required_field(base, 'friction').set(.5)
                    tag.required_field(element, 'Serialized Havok Data').set(b'\x00\x01\xfe\xff')
                    def add(parent, name):
                        block = tag.block(parent, name)
                        return block[block.add()]
                    tag.required_field(add(tag.tag.root(), 'nodes'), 'name').set('root')
                    body = add(tag.tag.root(), 'rigid bodies')
                    tag.required_field(body, 'node').set(0)
                    tag.required_field(body, 'serialized shapes').set(0)
                    reference = tag.required_field(body, 'shape reference').as_struct()
                    tag.required_field(reference, 'shape').set(-1)
                    region = add(tag.tag.root(), 'regions')
                    permutation = add(region, 'permutations')
                    tag.required_field(add(permutation, 'rigid bodies'), 'rigid body').set(0)
                before = (Path(root) / 'serialized.physics_model').read_bytes()
                with PhysicsTag('serialized.physics_model') as tag:
                    record, = tag.serialized_shapes(0)
                    with self.assertRaisesRegex(ValueError, 'index'):
                        tag.serialized_shapes(-1)
                    with self.assertRaisesRegex(ValueError, 'index'):
                        tag.serialized_shapes(1)
                    native_record, = tag.primitive_bodies(include_serialized=True)
                    self.assertEqual(native_record.kind, 'serialized')
                    rig = SimpleNamespace(pose=SimpleNamespace(bones={'root': SimpleNamespace(matrix=Matrix.Identity(4))}))
                    collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
                    decoded = SimpleNamespace()
                    def convert(body):
                        body.shapes[0].ob = SimpleNamespace()
                    with patch.object(HavokCollision, 'from_serialized_shape', return_value=decoded) as decoder, \
                         patch.object(RigidBody, 'to_objects', convert), \
                         patch.object(utils, 'set_region'), patch.object(utils, 'set_permutation'), \
                         patch.object(import_transform, 'object_matrix', side_effect=lambda matrix, **kw: matrix):
                        objects = tag.to_blend_objects(collection, rig)
                        self.assertEqual(len(objects), 1)
                        self.assertEqual(objects[0].parent_bone, 'root')
                        self.assertEqual(decoded.friction, .5)
                        decoder.assert_called_once()
                        collection.objects.link.reset_mock()
                        with self.assertRaisesRegex(ValueError, 'armature bone'):
                            tag.to_blend_objects(collection, SimpleNamespace(pose=SimpleNamespace(bones={})))
                        collection.objects.link.assert_not_called()
                    with patch.object(HavokCollision, 'from_serialized_shape', return_value=None), \
                         patch.object(RigidBody, 'to_objects') as convert, \
                         patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                        from io_scene_foundry.tags.physics import PhysicsShapesUnsupported
                        with self.assertRaisesRegex(PhysicsShapesUnsupported, 'Unsupported serialized'):
                            tag.to_blend_objects(collection, rig)
                        convert.assert_not_called()
                        collection.objects.link.assert_not_called()
                self.assertEqual(record.data, b'\x00\x01\xfe\xff')
                self.assertEqual(record.name, 'serialized_body')
                self.assertEqual(record.friction, .5)
                self.assertIsNone(record.material)
                self.assertEqual((Path(root) / 'serialized.physics_model').read_bytes(), before)

    def test_native_physics_mesh_creation(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.tags.connected_geometry import Sphere, Box, Pill, Polyhedron, RigidBody, HavokCollision
        from io_scene_foundry import import_transform

        class PhysicsTestProperties(bpy.types.PropertyGroup):
            mesh_type: bpy.props.StringProperty()
            mesh_primitive_type: bpy.props.StringProperty()
            global_material: bpy.props.StringProperty()

        bpy.utils.register_class(PhysicsTestProperties)
        bpy.types.Mesh.nwo = bpy.props.PointerProperty(type=PhysicsTestProperties)
        bpy.types.Object.nwo = bpy.props.PointerProperty(type=PhysicsTestProperties)
        existing_objects, existing_meshes = set(bpy.data.objects), set(bpy.data.meshes)
        existing_materials = set(bpy.data.materials)
        try:
            with patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                 patch.object(import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)):
                record = SimpleNamespace(name='native_physics_mesh', material=SimpleNamespace(name='metal'),
                    material_index=0, friction=.5, restitution=.25, radius=.5, translation=(1.,2.,3.),
                    half_extents=(1.,2.,3.), axes=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),
                    bottom=(0.,0.,0.), top=(0.,0.,2.), offset=0,
                    vertices=[(0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.)])
                for cls in (Sphere, Box, Pill, Polyhedron, HavokCollision):
                    with self.subTest(shape=cls.__name__):
                        if cls is HavokCollision:
                            shape = HavokCollision(record.name, [(0.,0.,0.),(100.,0.,0.),(0.,100.,0.)],
                                [(0,1,2)], [0], [record.material], [(7,8)])
                            shape.material = record.material
                        else:
                            shape = cls.from_native(record)
                        body = RigidBody.__new__(RigidBody)
                        body.shapes, body.is_havok_rigid_body = [shape], False
                        body.to_objects()
                        self.assertGreater(len(shape.ob.data.polygons), 0)
                        self.assertEqual(shape.ob.nwo.global_material, 'metal')
                        self.assertEqual(shape.ob.data.nwo.mesh_type, '_connected_geometry_mesh_type_physics')
                        self.assertEqual(shape.ob.data.materials[0].name, 'Physics')
                        if cls is Box:
                            self.assertEqual(len(shape.ob.data.polygons), 6)
                        elif cls is Polyhedron:
                            self.assertEqual(len(shape.ob.data.polygons), 4)
                        elif cls is HavokCollision:
                            self.assertEqual(len(shape.ob.data.polygons), 1)
                            self.assertEqual(shape.ob.data.attributes['foundry_havok_render_triangle_index'].data[0].value, 7)
                            self.assertEqual(shape.ob.data.attributes['foundry_havok_render_triangle_count'].data[0].value, 2)
        finally:
            for ob in set(bpy.data.objects) - existing_objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            for mesh in set(bpy.data.meshes) - existing_meshes:
                bpy.data.meshes.remove(mesh)
            for material in set(bpy.data.materials) - existing_materials:
                bpy.data.materials.remove(material)
            del bpy.types.Object.nwo
            del bpy.types.Mesh.nwo
            bpy.utils.unregister_class(PhysicsTestProperties)

    def test_native_physics_primitive_bodies(self):
        from mathutils import Matrix, Vector
        from unittest.mock import MagicMock
        from io_scene_foundry.tags.physics_blender import PhysicsTag
        from io_scene_foundry.tags.connected_geometry import RigidBody, Sphere, Box, Pill, Polyhedron
        from io_scene_foundry.tags.physics import PhysicsShapesUnsupported
        from io_scene_foundry import import_transform
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with PhysicsTag('test.physics_model') as tag:
                    def add(parent, name):
                        block = tag.block(parent, name)
                        return block[block.add()]
                    node = add(tag.tag.root(), 'nodes')
                    tag.required_field(node, 'name').set('root')
                    material = add(tag.tag.root(), 'materials')
                    tag.required_field(material, 'name').set('metal')
                    sphere = add(tag.tag.root(), 'spheres')
                    base = tag.required_field(sphere, 'base').as_struct()
                    tag.required_field(base, 'name').set('ball')
                    tag.required_field(base, 'material').set(0)
                    translate = tag.required_field(sphere, 'translate shape').as_struct()
                    convex = tag.required_field(translate, 'convex').as_struct()
                    tag.required_field(convex, 'radius').set(.5)
                    field = tag.required_field(translate, 'translation')
                    field.set(type(field.value)(1., 2., 3.))
                    body = add(tag.tag.root(), 'rigid bodies')
                    tag.required_field(body, 'node').set(0)
                    if game in {'halo4', 'halo2a'}:
                        tag.required_field(body, 'serialized shapes').set(-1)
                    reference = tag.required_field(body, 'shape reference').as_struct()
                    tag.required_field(reference, 'shape type').set(0)
                    tag.required_field(reference, 'shape').set(0)
                    region = add(tag.tag.root(), 'regions')
                    tag.required_field(region, 'name').set('body')
                    permutation = add(region, 'permutations')
                    tag.required_field(permutation, 'name').set('default')
                    tag.required_field(add(permutation, 'rigid bodies'), 'rigid body').set(0)
                before = (Path(root) / 'test.physics_model').read_bytes()
                rig = SimpleNamespace(pose=SimpleNamespace(bones={'root': SimpleNamespace(matrix=Matrix.Identity(4))}))
                collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
                def convert(body):
                    body.shapes[0].ob = SimpleNamespace()
                with PhysicsTag('test.physics_model') as tag, \
                     patch.object(RigidBody, 'to_objects', convert), \
                     patch.object(utils, 'set_region') as region_set, patch.object(utils, 'set_permutation'), \
                     patch.object(import_transform, 'object_matrix', side_effect=lambda matrix, **kw: matrix):
                    record, = tag.primitive_bodies()
                    shape = Sphere.from_native(record)
                    self.assertEqual(shape.radius, 50.)
                    self.assertEqual(shape.material.name, 'metal')
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(len(objects), 1)
                    self.assertEqual(objects[0].parent_bone, 'root')
                    self.assertEqual(tuple(objects[0].matrix_world.translation), (100., 200., 300.))
                    region_set.assert_called_once()
                    base = tag.required_field(tag.block(tag.tag.root(), 'spheres')[0], 'base').as_struct()
                    friction = tag.required_field(base, 'friction')
                    saved_friction = friction.value
                    friction.set(float('nan'))
                    collection.objects.link.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'friction or restitution'):
                        tag.to_blend_objects(collection, rig)
                    collection.objects.link.assert_not_called()
                    friction.set(saved_friction)
                    body = tag.block(tag.tag.root(), 'rigid bodies')[0]
                    if game in {'halo4', 'halo2a'}:
                        flags = tag.required_field(body, 'flags')
                        for flag in ('Havok rigid body', 'explicit mass', 'absolute center of mass'):
                            flags.set_flag(flag, True)
                        for name, value in [('mass', 12.), ('inertia tensor scale', 2.),
                                            ('inertia tensor scale x', 1.), ('inertia tensor scale y', 2.),
                                            ('inertia tensor scale z', 3.), ('linear damping', .5), ('angular damping', .25)]:
                            tag.required_field(body, name).set(value)
                        center = tag.required_field(body, 'center off mass offset')
                        center.set(type(center.value)(1., 2., 3.))
                        record, = tag.primitive_bodies()
                        native_body = RigidBody.__new__(RigidBody)
                        native_body.havok_info = record.havok
                        native_shape = Sphere.from_native(record)
                        native_shape.ob = SimpleNamespace(nwo=SimpleNamespace())
                        native_body.setup_havok_props(native_shape)
                        props = native_shape.ob.nwo
                        self.assertEqual(props.havok_mass, 12.)
                        self.assertTrue(props.havok_change_mass)
                        self.assertEqual(props.havok_center_of_mass, (1., 2., 3.))
                        self.assertEqual(props.havok_inertia_tensor, (1., 2., 3.))
                        self.assertEqual(props.havok_linear_damping, .5)
                        self.assertEqual(props.rigid_body_type, 'HAVOK')
                        tag.required_field(body, 'serialized shapes').set(0)
                        with self.assertRaisesRegex(PhysicsShapesUnsupported, 'Serialized'):
                            tag.primitive_bodies()
                        tag.required_field(body, 'serialized shapes').set(-1)
                        flags.set_flag('Havok rigid body', False)
                    reference = tag.required_field(body, 'shape reference').as_struct()
                    tag.required_field(reference, 'shape type').set(2)
                    boxes = tag.block(tag.tag.root(), 'boxes')
                    box = boxes[boxes.add()]
                    base = tag.required_field(box, 'base').as_struct()
                    tag.required_field(base, 'name').set('box')
                    tag.required_field(base, 'material').set(0)
                    convex = tag.required_field(box, 'box shape').as_struct()
                    tag.required_field(convex, 'radius').set(.5)
                    transform = tag.required_field(box, 'convex transform shape').as_struct()
                    for name, values in [('translation', (1., 2., 3.)), ('rotation i', (1.,0.,0.)),
                                         ('rotation j', (0.,1.,0.)), ('rotation k', (0.,0.,1.))]:
                        field = tag.required_field(transform, name)
                        field.set(type(field.value)(*values))
                    extents = tag.required_field(box, 'half extents')
                    extents.set(type(extents.value)(.25, .75, 1.25))
                    record, = tag.primitive_bodies()
                    converted = Box.from_native(record)
                    self.assertEqual((converted.width, converted.length, converted.height), (150., 250., 350.))
                    self.assertEqual(tuple(converted.matrix.to_scale()), (150., 250., 350.))
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(tuple(objects[0].matrix_world.translation), (100., 200., 300.))
                    extents.set(type(extents.value)(-1., .75, 1.25))
                    with self.assertRaisesRegex(ValueError, 'box dimensions'):
                        tag.primitive_bodies()
                    extents.set(type(extents.value)(.25, .75, 1.25))
                    tag.required_field(body, 'node').set(-1)
                    unbound, = tag.primitive_bodies()
                    self.assertEqual(unbound.node_index, -1)
                    self.assertIsNone(unbound.bone)
                    tag.required_field(body, 'node').set(0)
                    tag.required_field(reference, 'shape type').set(1)
                    pills = tag.block(tag.tag.root(), 'pills')
                    pill = pills[pills.add()]
                    base = tag.required_field(pill, 'base').as_struct()
                    tag.required_field(base, 'name').set('capsule')
                    tag.required_field(base, 'material').set(0)
                    capsule = tag.required_field(pill, 'capsule shape').as_struct()
                    tag.required_field(capsule, 'radius').set(.5)
                    for name, values in [('bottom', (1., 2., 3.)), ('top', (1., 2., 5.))]:
                        field = tag.required_field(pill, name)
                        field.set(type(field.value)(*values))
                    record, = tag.primitive_bodies()
                    converted = Pill.from_native(record)
                    self.assertEqual(converted.radius, 50.)
                    self.assertEqual(tuple(converted.matrix @ Vector((0., 0., 0.))), (100., 200., 250.))
                    self.assertEqual(tuple(converted.matrix @ Vector((0., 0., 2.))), (100., 200., 550.))
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(tuple(objects[0].matrix_world.translation), (100., 200., 250.))
                    top = tag.required_field(pill, 'top')
                    top.set(type(top.value)(1., 2., 3.))
                    with self.assertRaisesRegex(PhysicsShapesUnsupported, 'Zero-length'):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(4)
                    polyhedra = tag.block(tag.tag.root(), 'polyhedra')
                    for i in range(2):
                        poly = polyhedra[polyhedra.add()]
                        tag.required_field(poly, 'four vectors size').set(1)
                    tag.required_field(reference, 'shape').set(1)
                    vectors = tag.block(tag.tag.root(), 'polyhedron four vectors')
                    vectors.add()  # First shape's vector group must not leak into the second.
                    packed = vectors[vectors.add()]
                    for axis, values, last in [('x', (0.,1.,0.), 0.), ('y',(0.,0.,1.),0.), ('z',(0.,0.,0.),1.)]:
                        field = tag.required_field(packed, f'four vectors {axis}')
                        field.set(type(field.value)(*values))
                        tag.required_field(packed, f'havok w four vectors {axis}').set(last)
                    record, = tag.primitive_bodies()
                    self.assertEqual(record.offset, 1)
                    converted = Polyhedron.from_native(record)
                    self.assertEqual([tuple(v) for v in converted.vertices], [(0.,0.,0.),(100.,0.,0.),(0.,100.,0.),(0.,0.,100.)])
                    import bmesh
                    bm = bmesh.new()
                    try:
                        for point in converted.vertices:
                            bm.verts.new(point)
                        bmesh.ops.convex_hull(bm, input=list(bm.verts))
                        self.assertEqual(len(bm.faces), 4)
                    finally:
                        bm.free()
                    self.assertEqual(len(tag.to_blend_objects(collection, rig)), 1)
                    poly = polyhedra[1]
                    tag.required_field(poly, 'four vectors size').set(99)
                    with self.assertRaisesRegex(ValueError, 'vector range'):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(14)
                    lists = tag.block(tag.tag.root(), 'lists')
                    for count in (1, 2):
                        element = lists[lists.add()]
                        tag.required_field(element, 'child shapes size').set(count)
                    children = tag.block(tag.tag.root(), 'list shapes')
                    for kind in (3, 0, 0):
                        child = children[children.add()]
                        child_ref = tag.required_field(child, 'shape reference').as_struct()
                        tag.required_field(child_ref, 'shape type').set(kind)
                        tag.required_field(child_ref, 'shape').set(0)
                    # List 1 skips the unsupported child belonging to list 0.
                    records = tag.primitive_bodies()
                    self.assertEqual([r.name for r in records], ['ball', 'ball'])
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(len(objects), 2)
                    self.assertTrue(all(ob.parent_bone == 'root' for ob in objects))
                    mopps = tag.block(tag.tag.root(), 'mopps')
                    mopp = mopps[mopps.add()]
                    if game in {'halo4', 'halo2a'}:
                        mopp_ref = tag.required_field(mopp, 'childShapePointer').as_struct()
                        tag.required_field(mopp_ref, 'shape type').set(14)
                        tag.required_field(mopp_ref, 'shape').set(1)
                    else:
                        tag.required_field(mopp, 'list').set(1)
                    tag.required_field(reference, 'shape type').set(15)
                    tag.required_field(reference, 'shape').set(0)
                    self.assertEqual([r.name for r in tag.primitive_bodies()], ['ball', 'ball'])
                    self.assertEqual(len(tag.to_blend_objects(collection, rig)), 2)
                    if game == 'halo3':
                        # Older H4 tags retain the pre-serialized-body/MOPP layout.
                        tag.game = 'halo4'
                        try:
                            self.assertEqual([r.name for r in tag.primitive_bodies()], ['ball', 'ball'])
                            self.assertEqual(len(tag.to_blend_objects(collection, rig)), 2)
                        finally:
                            tag.game = game
                    tag.required_field(reference, 'shape').set(99)
                    with self.assertRaisesRegex(ValueError, 'MOPP index'):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape').set(0)
                    if game in {'halo4', 'halo2a'}:
                        tag.required_field(mopp_ref, 'shape type').set(0)
                        tag.required_field(mopp_ref, 'shape').set(0)
                        self.assertEqual(len(tag.primitive_bodies()), 1)
                        tag.required_field(mopp_ref, 'shape type').set(15)
                        with self.assertRaisesRegex(ValueError, 'Circular'):
                            tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(14)
                    tag.required_field(reference, 'shape').set(1)
                    tag.required_field(lists[1], 'child shapes size').set(99)
                    with self.assertRaisesRegex(ValueError, 'list child range'):
                        tag.primitive_bodies()
                    tag.required_field(lists[1], 'child shapes size').set(-1)
                    with self.assertRaisesRegex(ValueError, 'Negative physics list'):
                        tag.primitive_bodies()
                    tag.required_field(lists[1], 'child shapes size').set(2)
                    child_ref = tag.required_field(children[2], 'shape reference').as_struct()
                    tag.required_field(child_ref, 'shape type').set(14)
                    first_ref = tag.required_field(children[0], 'shape reference').as_struct()
                    tag.required_field(first_ref, 'shape type').set(0)
                    self.assertEqual([r.name for r in tag.primitive_bodies()], ['ball', 'ball'])
                    # Reusing a list in separate branches is not a cycle.
                    second_ref = tag.required_field(children[1], 'shape reference').as_struct()
                    tag.required_field(second_ref, 'shape type').set(14)
                    self.assertEqual(len(tag.to_blend_objects(collection, rig)), 2)
                    tag.required_field(first_ref, 'shape type').set(14)
                    tag.required_field(first_ref, 'shape').set(1)
                    collection.objects.link.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'Circular'):
                        tag.to_blend_objects(collection, rig)
                    collection.objects.link.assert_not_called()
                    tag.required_field(first_ref, 'shape type').set(3)
                    with self.assertRaises(PhysicsShapesUnsupported):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(3)
                    with self.assertRaises(PhysicsShapesUnsupported):
                        tag.primitive_bodies()
                self.assertEqual((Path(root) / 'test.physics_model').read_bytes(), before)

    def test_halo1_physics_mass_points_use_model_space_rotation(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.tags.physics_blender import PhysicsTag
        from io_scene_foundry.tags.connected_geometry import RigidBody

        scene_nwo = SimpleNamespace(scene_project='test', scale='max', forward_direction='y-')
        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=scene_nwo), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo1')), \
             patch.object(utils, 'get_tags_path', return_value=root), \
             patch.object(utils, 'get_rig', return_value=None):
            with PhysicsTag('test.physics') as tag:
                points = tag.block(tag.tag.root(), 'mass points')
                point = points[points.add()]
                tag.required_field(point, 'name').set('mass point')
                tag.required_field(point, 'model node').set(-1)
                tag.required_field(point, 'radius').set(.25)
                position = tag.required_field(point, 'position')
                position.set(type(position.value)(1., 2., 3.))

            collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
            def convert(body):
                body.shapes[0].ob = SimpleNamespace()
            with PhysicsTag('test.physics') as tag, \
                patch.object(RigidBody, 'to_objects', convert), \
                 patch.object(utils, 'set_region'), patch.object(utils, 'set_permutation'):
                imported, = tag.to_blend_objects(collection)
                for actual, expected in zip(imported.matrix_world.translation, (200., -100., 300.)):
                    self.assertAlmostEqual(actual, expected, places=4)

    def test_native_physics_constraints(self):
        from mathutils import Matrix
        from unittest.mock import MagicMock
        from io_scene_foundry.tags.physics_blender import PhysicsTag
        from io_scene_foundry.tags import connected_geometry
        from io_scene_foundry import import_transform
        from io_scene_foundry.tags.physics import CONSTRAINT_FIELDS
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with PhysicsTag('test.physics_model') as tag:
                    nodes = tag.block(tag.tag.root(), 'nodes')
                    for name in ('parent', 'child'):
                        tag.required_field(nodes[nodes.add()], 'name').set(name)
                    for kind, fields in CONSTRAINT_FIELDS.items():
                        block = tag.block(tag.tag.root(), kind)
                        element = block[block.add()]
                        body = tag.required_field(element, 'constraint bodies').as_struct()
                        tag.required_field(body, 'name').set(kind)
                        tag.required_field(body, 'node a').set(0)
                        tag.required_field(body, 'node b').set(1)
                        for side in ('a', 'b'):
                            for name, values in [('forward', (1.,0.,0.)), ('left',(0.,1.,0.)), ('up',(0.,0.,1.)),
                                                 ('position', (1.,2.,3. if side == 'a' else 7.))]:
                                field = tag.required_field(body, f'{side} {name}')
                                field.set(type(field.value)(*values))
                        for i, name in enumerate(fields.values(), start=1):
                            tag.required_field(element, name).set(float(i))
                before = (Path(root) / 'test.physics_model').read_bytes()
                factory = MagicMock(side_effect=lambda name, data: SimpleNamespace(name=name, nwo=SimpleNamespace(), empty_display_size=1.))
                fake = SimpleNamespace(data=SimpleNamespace(objects=SimpleNamespace(new=factory)))
                rig = SimpleNamespace(pose=SimpleNamespace(bones={name: SimpleNamespace(matrix=Matrix.Identity(4)) for name in ('parent','child')}))
                collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
                with PhysicsTag('test.physics_model') as tag, patch.object(connected_geometry, 'bpy', fake), \
                     patch.object(import_transform, 'scale_factor', return_value=1.), \
                     patch.object(import_transform, 'object_matrix', side_effect=lambda matrix, **kw: matrix), \
                     patch.object(import_transform, 'keep_marker_axis', side_effect=lambda matrix: matrix):
                    records = tag.constraints()
                    constraint = connected_geometry.Constraint.from_native(records[0])
                    self.assertEqual(constraint.matrix_a.translation.z, 300.)
                    self.assertEqual(constraint.matrix_b.translation.z, 700.)
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(len(objects), 6)
                    self.assertEqual(objects[0].nwo.physics_constraint_type, '_connected_geometry_marker_type_physics_hinge_constraint')
                    self.assertAlmostEqual(objects[1].nwo.hinge_constraint_maximum, .034906585)
                    self.assertEqual(objects[-1].nwo.prismatic_limit_min, 1.)
                    self.assertEqual(objects[-1].nwo.prismatic_limit_max, 2.)
                    self.assertEqual(objects[-1].nwo.prismatic_limit_friction, 3.)
                    self.assertEqual(objects[-1].parent_bone, 'parent')
                    factory.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'requires both armature bones'):
                        tag.to_blend_objects(collection, SimpleNamespace(pose=SimpleNamespace(bones={})))
                    factory.assert_not_called()
                self.assertEqual((Path(root) / 'test.physics_model').read_bytes(), before)

    def test_native_collision_geometry_and_invalid_loops(self):
        from mathutils import Vector
        from io_scene_foundry.tags.collision_blender import CollisionTag
        from io_scene_foundry.tags.connected_geometry import ModelCollision
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with CollisionTag('test.collision_model') as tag:
                    def add(parent, name):
                        block = tag.block(parent, name)
                        return block[block.add()]
                    node = add(tag.tag.root(), 'nodes')
                    tag.required_field(node, 'name').set('root')
                    material = add(tag.tag.root(), 'materials')
                    tag.required_field(material, 'name').set('metal')
                    region = add(tag.tag.root(), 'regions')
                    tag.required_field(region, 'name').set('body')
                    permutation = add(region, 'permutations')
                    tag.required_field(permutation, 'name').set('default')
                    record = add(permutation, 'bsps')
                    tag.required_field(record, 'node index').set(0)
                    bsp = tag.required_field(record, 'bsp').as_struct()
                    for point in ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)):
                        vertex = add(bsp, 'vertices')
                        field = tag.required_field(vertex, 'point')
                        field.set(type(field.value)(*point))
                    for i in range(3):
                        edge = add(bsp, 'edges')
                        for name, value in [('start vertex', i), ('end vertex', (i+1)%3),
                                            ('forward edge', (i+1)%3), ('reverse edge', -1),
                                            ('left surface', 0), ('right surface', -1)]:
                            tag.required_field(edge, name).set(65535 if value == -1 and game in {'halo4', 'halo2a'} else value)
                    surface = add(bsp, 'surfaces')
                    tag.required_field(surface, 'first edge').set(0)
                    tag.required_field(surface, 'material').set(0)
                    tag.required_field(surface, 'flags').set_flag('climbable', True)
                    if game in {'halo3', 'halo3odst'}:
                        tag.required_field(surface, 'plane').set(-32768)
                    else:
                        tag.required_field(surface, 'flags').set_flag('plane negated', True)
                    sphere = add(tag.tag.root(), 'pathfinding spheres')
                    tag.required_field(sphere, 'node').set(0)
                    tag.required_field(sphere, 'radius').set(.5)
                    tag.required_field(sphere, 'flags').set_flag('vehicle only', True)
                before = (Path(root) / 'test.collision_model').read_bytes()
                with CollisionTag('test.collision_model') as tag:
                    meshes, spheres = tag.read_collision()
                    self.assertEqual(meshes[0].polygons, [[0, 1, 2]])
                    self.assertEqual(meshes[0].bone, 'root')
                    self.assertTrue(meshes[0].surfaces[0].ladder)
                    self.assertTrue(meshes[0].surfaces[0].negated)
                    self.assertEqual(meshes[0].surfaces[0].material.name, 'metal')
                    self.assertTrue(spheres[0].vehicle)
                    collision = ModelCollision.from_native(meshes[0])
                    hit, normal, index, distance = collision.to_bvh().ray_cast(Vector((25, 25, 100)), Vector((0, 0, -1)))
                    self.assertAlmostEqual(hit.z, 0.)
                    self.assertAlmostEqual(distance, 100.)
                    with self.assertRaisesRegex(ValueError, 'missing from the armature'):
                        tag.to_blend_objects(None, SimpleNamespace(pose=SimpleNamespace(bones={})))
                    region = tag.block(tag.tag.root(), 'regions')[0]
                    perm = tag.block(region, 'permutations')[0]
                    bsp = tag.required_field(tag.block(perm, 'bsps')[0], 'bsp').as_struct()
                    tag.required_field(tag.block(bsp, 'edges')[1], 'forward edge').set(1)
                    with self.assertRaisesRegex(ValueError, 'invalid edge loop'):
                        tag.read_collision()
                self.assertEqual((Path(root) / 'test.collision_model').read_bytes(), before)

    def test_halo1_collision_uses_node_region_and_bsp_permutation(self):
        from io_scene_foundry.tags.collision_blender import CollisionTag

        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo1')), \
             patch.object(utils, 'get_tags_path', return_value=root):
            with CollisionTag('test.model_collision_geometry') as tag:
                def add(parent, name):
                    block = tag.block(parent, name)
                    return block[block.add()]

                region = add(tag.tag.root(), 'regions')
                tag.required_field(region, 'name').set('__unnamed')
                permutation = add(region, 'permutations')
                tag.required_field(permutation, 'name').set('base00')

                node = add(tag.tag.root(), 'nodes')
                tag.required_field(node, 'name').set('frame rock')
                tag.required_field(node, 'region').set(0)
                bsp = add(node, 'bsps')
                for point in ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)):
                    vertex = add(bsp, 'vertices')
                    field = tag.required_field(vertex, 'point')
                    field.set(type(field.value)(*point))
                for i in range(3):
                    edge = add(bsp, 'edges')
                    for name, value in (
                            ('start vertex', i), ('end vertex', (i + 1) % 3),
                            ('forward edge', (i + 1) % 3), ('reverse edge', -1),
                            ('left surface', 0), ('right surface', -1)):
                        tag.required_field(edge, name).set(value)
                surface = add(bsp, 'surfaces')
                tag.required_field(surface, 'first edge').set(0)
                tag.required_field(surface, 'material').set(-1)

            with CollisionTag('test.model_collision_geometry') as tag:
                meshes, _spheres = tag.read_collision()

            self.assertEqual(len(meshes), 1)
            self.assertEqual(meshes[0].region, '__unnamed')
            self.assertEqual(meshes[0].permutation, 'base00')
            self.assertEqual(meshes[0].bone, 'frame rock')

    def test_native_pca_creates_shape_keys_and_animation(self):
        import bpy
        import struct
        from io_scene_foundry.tags.pca_blender import PCAAnimationTag
        for game in ('halo4', 'halo2a'):
            mesh = bpy.data.meshes.new('native_pca_test')
            mesh.from_pydata([(0., 0., 0.), (1., 1., 0.)], [], [])
            ob = bpy.data.objects.new('native_pca_test', mesh)
            action = None
            try:
                with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=root), \
                     patch.object(utils, 'halo_scale', return_value=1.), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                    with PCAAnimationTag('test.pca_animation') as tag:
                        meshes = tag.mesh_data()
                        item = meshes[meshes.add()]
                        tag.required_field(item, 'vertices per shape').set(2)
                        vertices = tag.block(item, 'raw blendshape verts')
                        for vector in ((1., 0., 0.), (0., 1., 0.)):
                            field = tag.required_field(vertices[vertices.add()], 'position')
                            field.set(type(field.value)(*vector))
                        frames = tag.block(tag.tag.root(), 'frame data')
                        for weight in (0., 1.):
                            tag.required_field(frames[frames.add()], 'Coefficients').set(struct.pack('<f', weight))
                    with PCAAnimationTag('test.pca_animation') as tag:
                        bounds = SimpleNamespace(x0=0., x1=10., y0=0., y1=10., z0=0., z1=10.)
                        animation = SimpleNamespace(action_tracks=SimpleNamespace(add=lambda: SimpleNamespace()))
                        with self.assertRaisesRegex(ValueError, 'frame range'):
                            tag.import_animation(ob, 0, bounds, 5, 1, 1, 0, 'bad', animation, 'pca', {})
                        self.assertIsNone(mesh.shape_keys)
                        keys, action, slot = tag.import_animation(ob, 0, bounds, 0, 2, 1, 0, 'test', animation, 'pca', {})
                        self.assertEqual(tuple(keys.key_blocks['pca_1'].data[0].co), (1., 0., 0.))
                        self.assertEqual(tuple(keys.key_blocks['pca_1'].data[1].co), (1., 2., 0.))
                        fcurve, = utils.get_fcurves(action, slot)
                        self.assertEqual([tuple(k.co) for k in fcurve.keyframe_points], [(1., 0.), (2., 1.)])
                        self.assertTrue(all(k.interpolation == 'LINEAR' for k in fcurve.keyframe_points))
            finally:
                bpy.data.objects.remove(ob, do_unlink=True)
                bpy.data.meshes.remove(mesh)
                if action is not None:
                    bpy.data.actions.remove(action)

    def test_native_structure_metadata_markers(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.tags import structure_meta
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with structure_meta.StructureMetaTag('test.structure_meta') as tag:
                    def add(name):
                        block = tag.block(tag.tag.root(), name)
                        return block[block.add()]
                    def vector(element, name, values):
                        field = tag.required_field(element, name)
                        field.set(type(field.value)(*values))
                    effect = add('Effects markers')
                    tag.required_field(effect, 'marker name').set('fx')
                    vector(effect, 'rotation', (0., 0., 0., 1.))
                    vector(effect, 'position', (1., 2., 3.))
                    tag.set_reference(effect, 'optional attached effect', 'test.effect')
                    air = add('Airprobes')
                    tag.required_field(air, 'airprobe name').set('air')
                    vector(air, 'airprobe position', (4., 5., 6.))
                    cone = add('Light Cones')
                    tag.required_field(cone, 'marker name').set('cone')
                    vector(cone, 'rotation', (0., 0., 0., 1.))
                    for name, number in (('length', 2.), ('width', 3.), ('intensity', 4.)):
                        tag.required_field(cone, name).set(number)
                    vector(cone, 'light color', (1., .2, .4, .6))
                    tag.set_reference(cone, 'light cone tag', 'test.light_cone')
                    tag.set_reference(cone, 'intensity curve', 'test.curve_scalar')
                    palette = add('Object Palette')
                    tag.set_reference(palette, 'definition', 'test.scenery')
                    obj = add('Objects')
                    tag.required_field(obj, 'name').set('instance')
                    vector(obj, 'rotation', (0., 0., 0., 1.))
                    vector(obj, 'translation', (7., 8., 9.))
                    tag.required_field(obj, 'scale').set(2.)
                    tag.required_field(obj, 'palette_index').set(0)
                    tag.required_field(obj, 'variant name').set('variant')
                    tag.required_field(obj, 'flags').set_flag('scripts always run', True)
                before = (Path(root) / 'test.structure_meta').read_bytes()
                collections = []
                def collection(name):
                    result = SimpleNamespace(name=name, objects=SimpleNamespace(link=MagicMock()))
                    collections.append(result)
                    return result
                fake = SimpleNamespace(types=SimpleNamespace(Collection=object), data=SimpleNamespace(
                    collections=SimpleNamespace(new=collection), objects=SimpleNamespace(
                        new=lambda name, data: SimpleNamespace(name=name, nwo=SimpleNamespace(), empty_display_size=1.))))
                parent = SimpleNamespace(children=SimpleNamespace(link=MagicMock()))
                with structure_meta.StructureMetaTag('test.structure_meta') as tag, \
                     patch.object(structure_meta, 'bpy', fake), \
                     patch.object(structure_meta.import_transform, 'scale_factor', return_value=1.), \
                     patch.object(structure_meta.import_transform, 'marker_matrix', side_effect=lambda m: m):
                    markers, instances = tag.to_blender(parent)
                    self.assertEqual([o.name for o in markers], ['fx', 'air', 'cone'])
                    self.assertEqual(tuple(markers[0].matrix_world.translation), (100., 200., 300.))
                    self.assertAlmostEqual(markers[0].matrix_world.to_quaternion().w, 1.)
                    self.assertEqual(markers[2].nwo.marker_light_cone_intensity, 4.)
                    self.assertEqual(markers[2].nwo.marker_light_cone_curve, 'test.curve_scalar')
                    self.assertAlmostEqual(markers[2].nwo.marker_light_cone_color[0], .2)
                    self.assertEqual(instances[0].nwo.marker_game_instance_tag_name, 'test.scenery')
                    self.assertTrue(instances[0].nwo.marker_always_run_scripts)
                    self.assertEqual(instances[0].nwo.marker_game_instance_tag_variant_name, 'variant')
                    self.assertEqual(tuple(instances[0].matrix_world.to_scale()), (2., 2., 2.))
                    self.assertEqual([c.name for c in collections], ['test_effects', 'test_airprobes', 'test_light_cones', 'test_objects'])
                    self.assertEqual(tag.to_blender(parent, objects_only=True)[0], [])
                self.assertEqual((Path(root) / 'test.structure_meta').read_bytes(), before)

    def test_native_structure_seam_blender_mesh(self):
        import bpy
        from mathutils import Matrix, Vector
        from io_scene_foundry.tags import structure_seams_blender as structure_seams
        class SeamTestProperties(bpy.types.PropertyGroup):
            mesh_type: bpy.props.StringProperty()
            region_name: bpy.props.StringProperty()
            seam_back: bpy.props.StringProperty()
        bpy.utils.register_class(SeamTestProperties)
        bpy.types.Mesh.nwo = bpy.props.PointerProperty(type=SeamTestProperties)
        bpy.types.Object.nwo = bpy.props.PointerProperty(type=SeamTestProperties)
        collection = bpy.data.collections.new('native_seam_test')
        objects = []
        try:
            with tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with structure_seams.StructureSeamsTag('test.structure_seams') as tag:
                    block = tag.block(tag.tag.root(), 'seams')
                    element = block[block.add()]
                    final = tag.required_field(element, 'final').as_struct()
                    points = tag.block(final, 'points')
                    for coords in ((0., 0., 0.), (0., 1., 0.), (1., 0., 0.)):
                        point = points[points.add()]
                        field = tag.required_field(point, 'final point')
                        field.set(type(field.value)(*coords))
                    triangles = tag.block(final, 'triangles')
                    triangle = triangles[triangles.add()]
                    for i in range(3):
                        tag.required_field(triangle, f'final point{i}').set(i)
                    with patch.object(structure_seams, 'apply_props_material'), \
                         patch.object(structure_seams.import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                         patch.object(structure_seams.import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)):
                        with self.assertRaisesRegex(ValueError, 'metadata'):
                            tag.to_blend_objects([], collection)
                        self.assertEqual(len(collection.objects), 0)
                        objects = tag.to_blend_objects([SimpleNamespace(bsps=['front', 'back'], origin=Vector((0, 0, 100)))], collection)
                        ob, = objects
                        self.assertEqual(ob.nwo.region_name, 'front')
                        self.assertEqual(ob.nwo.seam_back, 'back')
                        self.assertEqual(len(ob.data.polygons), 1)
                        self.assertAlmostEqual(max(v.co.x for v in ob.data.vertices), 100.)
                        self.assertGreater(ob.data.polygons[0].normal.z, .99)
        finally:
            for ob in list(collection.objects):
                mesh = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                bpy.data.meshes.remove(mesh)
            bpy.data.collections.remove(collection)
            del bpy.types.Mesh.nwo
            del bpy.types.Object.nwo
            bpy.utils.unregister_class(SeamTestProperties)

    def test_unconnected_native_curves_resolve_constant_light_values(self):
        import struct
        from blam_tags import TagFunctionEditor
        from io_scene_foundry.tags.connected_material import Function, OutputModifierType
        from io_scene_foundry.tags.light_functions import constant_light_value
        from test_blam_functions import function_blob
        # A nonlinear exponent curve whose endpoint differs from both clamp bounds.
        blob = function_blob(9, (struct.pack('<fff', 2., 6., 2.),))
        function = Function()
        function.native_function_type = 9
        function.editor = TagFunctionEditor(blob)
        function.clamp_min, function.clamp_max = .25, .75
        self.assertAlmostEqual(constant_light_value(function), 3.25)
        function.uses_input = True
        self.assertIsNone(constant_light_value(function))
        function.uses_input = False
        function.is_ranged, function.range = True, 'radius_range'
        self.assertIsNone(constant_light_value(function))
        function.range = ''
        self.assertAlmostEqual(constant_light_value(function), 3.25)
        function.output_modifier_type = OutputModifierType.TIMES
        self.assertIsNone(constant_light_value(function))
        function.output_modifier_type = OutputModifierType.NONE
        function.native_function_type = 3  # Periodic/noise must not be frozen.
        self.assertIsNone(constant_light_value(function))

    def test_normalized_light_additive_modifier_keeps_units(self):
        import bpy
        from io_scene_foundry.tags import connected_material as material
        function = material.Function()
        function.clamp_min, function.clamp_max = 2., 8.
        function.output_modifier_type = material.OutputModifierType.PLUS
        function.output_modifier = 'boost'
        tree = bpy.data.node_groups.new('native_light_modifier_test', 'ShaderNodeTree')
        def attribute(tree, name):
            node = tree.nodes.new('ShaderNodeValue')
            node.outputs[0].default_value = 3.
            return node
        def evaluate(socket):
            node = socket.node
            if node.bl_idname == 'ShaderNodeValue':
                return socket.default_value
            values = [evaluate(i.links[0].from_socket) if i.is_linked else i.default_value for i in node.inputs[:2]]
            if node.operation == 'ADD':
                return sum(values)
            if node.operation == 'DIVIDE':
                return values[0] / values[1]
            self.fail(f'Unexpected operation: {node.operation}')
        try:
            with patch.object(material, 'add_attribute_node', side_effect=attribute):
                output = function.to_blend_nodes(tree=tree, normalize=True)
            self.assertAlmostEqual(evaluate(output) * 8., 5.)  # 2 intensity + 3 boost.
        finally:
            bpy.data.node_groups.remove(tree)

    def test_native_light_conversion(self):
        import struct
        from unittest.mock import MagicMock
        from io_scene_foundry.tags import cheap_light, light
        from io_scene_foundry.tags.connected_material import Function, OutputModifierType

        def mapping(tag, name, value, color=False):
            element = tag.required_field(tag.tag.root(), name).as_struct()
            data = bytearray(32)
            data[0] = 1
            if color:
                data[2] = 1
                struct.pack_into('<I', data, 4, 0xff804020)
            else:
                struct.pack_into('<ff', data, 4, value, value)
            function = tag.required_field(element, 'Mapping').as_struct()
            tag.required_field(function, 'data').set(bytes(data))
            if name == 'intensity':
                tag.required_field(element, 'Input Variable').set('power')
                tag.required_field(element, 'Range Variable').set('pulse')
                tag.required_field(element, 'Output Modifier Input').set('boost')
                tag.required_field(element, 'Output Modifier').set(2)
                parsed = Function()
                parsed.from_native_light(tag, element)
                self.assertEqual(parsed.output_modifier_type, OutputModifierType.TIMES)
                self.assertTrue(parsed.uses_input)
                self.assertEqual(parsed.range, 'pulse')

        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            for module, cls in ((cheap_light, cheap_light.CheapLightTag), (light, light.LightTag)):
                if game in {'halo3', 'halo3odst'}:
                    continue  # No cheap_light group; regular light falloff is not supported yet.
                if cls is light.LightTag and game in {'halo4', 'halo2a'}:
                    continue  # Covered by the separate Midnight parameter-layout test.
                with self.subTest(game=game, kind=cls.tag_ext), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=root), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                    path = 'lamp.' + cls.tag_ext
                    unsupported = cls is light.LightTag and game in {'halo4', 'halo2a'}
                    with cls(path) as tag:
                        if not unsupported:
                            mapping(tag, 'color', 0, True)
                            mapping(tag, 'intensity', 4.)
                            if cls is cheap_light.CheapLightTag:
                                mapping(tag, 'Falloff End' if tag.corinth else 'radius', 8.)
                            else:
                                for name, value in [('type', 1), ('frustum field of view', 60.),
                                                    ('angular hotspot', 30.), ('attenuation start distance', 2.),
                                                    ('attenuation end distance', 8.)]:
                                    tag.required_field(tag.tag.root(), name).set(value)
                    before = (Path(root) / path).read_bytes()
                    data = SimpleNamespace(nwo=SimpleNamespace())
                    factory = MagicMock(return_value=data)
                    fake_bpy = SimpleNamespace(data=SimpleNamespace(lights=SimpleNamespace(new=factory)))
                    attachment = SimpleNamespace(function_names=set())
                    with cls(path) as tag, patch.object(module, 'bpy', fake_bpy), \
                         patch.object(module.import_transform, 'scale_factor', return_value=1.), \
                         patch.object(module.import_transform, 'distance', side_effect=lambda x: x * 100), \
                         patch.object(utils, 'make_halo_light') as make:
                        result = tag.to_blender('primary', 'secondary', attachment)
                        if unsupported:
                            self.assertIsNone(result)
                            factory.assert_not_called()
                        else:
                            self.assertIs(result, data)
                            self.assertEqual(data.nwo.light_intensity, 4.)
                            self.assertEqual(data.nwo.light_far_attenuation_end, 800.)
                            self.assertEqual(data.color, [utils.srgb_to_linear(c / 255) for c in (128, 64, 32)])
                            self.assertEqual(attachment.function_names, {'power', 'boost'})
                            make.assert_called_once()
                            if cls is light.LightTag:
                                self.assertAlmostEqual(data.spot_size, 1.0471975512)
                                self.assertEqual(data.spot_blend, .5)
                                self.assertEqual(data.nwo.light_far_attenuation_start, 200.)
                    self.assertEqual(before, (Path(root) / path).read_bytes())

    def test_native_midnight_lights(self):
        import struct
        from unittest.mock import MagicMock
        from io_scene_foundry.tags import light
        for game in ('halo4', 'halo2a'):
            for kind in (0, 1, 2, 3, 4):
                for mode in (0, 1):
                    with self.subTest(game=game, kind=kind, mode=mode), tempfile.TemporaryDirectory() as root, \
                         patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                         patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                         patch.object(utils, 'get_tags_path', return_value=root), \
                         patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                        with light.LightTag('lamp.light') as tag:
                            parameters = tag.required_field(tag.tag.root(), 'Midnight_Light_Parameters').as_struct()
                            for name, value in [('Light Type', kind), ('Lighting Mode', mode),
                                                ('Inner Cone Angle', 30.), ('Distance Attenuation Start', 2.),
                                                ('Shadows', 1), ('Cinema Only', 1), ('Specular Contribution', 1)]:
                                tag.required_field(parameters, name).set(value)
                            color = tag.required_field(parameters, 'Light Color')
                            color.set(type(color.value)(.5, .25, .125))
                            for name, number in [('Intensity', 4.), ('Distance Attenuation End', 8.), ('Outer Cone End', 60.)]:
                                element = tag.required_field(parameters, name).as_struct()
                                mapping = tag.required_field(element, 'Mapping').as_struct()
                                blob = bytearray(32)
                                blob[0] = 1
                                struct.pack_into('<ff', blob, 4, number, number)
                                if name == 'Distance Attenuation End':
                                    blob[0] = 0  # Unconnected identity resolves at input=1, not clamp_min.
                                    struct.pack_into('<ff', blob, 4, 2., number)
                                tag.required_field(mapping, 'data').set(bytes(blob))
                        before = (Path(root) / 'lamp.light').read_bytes()
                        data = SimpleNamespace(nwo=SimpleNamespace())
                        factory = MagicMock(return_value=data)
                        fake_bpy = SimpleNamespace(context=object(), data=SimpleNamespace(lights=SimpleNamespace(new=factory)))
                        with light.LightTag('lamp.light') as tag, patch.object(light, 'bpy', fake_bpy), \
                             patch.object(light.import_transform, 'distance', side_effect=lambda x: x * 100), \
                             patch.object(utils, 'get_import_scale', return_value=10.), \
                             patch.object(utils, 'make_halo_light') as make:
                            if kind == 3:
                                with self.assertRaisesRegex(NotImplementedError, 'Area'):
                                    tag.to_blender()
                                factory.assert_not_called()
                                continue
                            self.assertIs(tag.to_blender(), data)
                            self.assertEqual(factory.call_args.kwargs['type'], ('POINT', 'SPOT', 'SUN', 'AREA', 'SUN')[kind])
                            self.assertEqual(data.nwo.light_intensity, 4.)
                            self.assertEqual(data.nwo.light_far_attenuation_start, 200.)
                            self.assertEqual(data.nwo.light_far_attenuation_end, 800.)
                            self.assertEqual(data.color, [utils.srgb_to_linear(c) for c in (.5, .25, .125)])
                            self.assertTrue(data.nwo.light_shadows)
                            self.assertEqual(data.nwo.light_cinema, '_connected_geometry_lighting_cinema_only')
                            if kind == 1:
                                self.assertAlmostEqual(data.spot_size, 1.0471975512)
                                self.assertEqual(data.spot_blend, .5)
                            if kind in {2, 4}:
                                self.assertEqual(data.energy, 4.)
                                make.assert_not_called()
                            elif mode == 0:
                                self.assertEqual(data.energy, 400.)
                                make.assert_not_called()
                            else:
                                make.assert_called_once()
                        self.assertEqual(before, (Path(root) / 'lamp.light').read_bytes())

    def test_animated_midnight_intensity(self):
        import struct
        from unittest.mock import MagicMock
        from io_scene_foundry.tags import light
        from io_scene_foundry.tags.connected_material import Function
        for game in ('halo4', 'halo2a'):
            for mode, animated_radius in ((1, False), (0, False), (1, True)):
                with self.subTest(game=game, mode=mode, radius=animated_radius), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=root), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                    with light.LightTag('lamp.light') as tag:
                        p = tag.required_field(tag.tag.root(), 'Midnight_Light_Parameters').as_struct()
                        tag.required_field(p, 'Lighting Mode').set(mode)
                        for name in ('Intensity', 'Distance Attenuation End'):
                            element = tag.required_field(p, name).as_struct()
                            mapping = tag.required_field(element, 'Mapping').as_struct()
                            blob = bytearray(32)  # Identity curve; no editor trailer.
                            limits = (2., 8.) if name == 'Intensity' or animated_radius else (8., 8.)
                            struct.pack_into('<ff', blob, 4, *limits)
                            if name == 'Distance Attenuation End' and animated_radius:
                                tag.required_field(element, 'Input Variable').set('radius_control')
                            if name == 'Intensity':
                                blob[1] = 1  # Ranged.
                                tag.required_field(element, 'Input Variable').set('power')
                                tag.required_field(element, 'Range Variable').set('pulse')
                                tag.required_field(element, 'Output Modifier Input').set('boost')
                                tag.required_field(element, 'Output Modifier').set(2)
                            tag.required_field(mapping, 'data').set(bytes(blob))
                    before = (Path(root) / 'lamp.light').read_bytes()
                    data = SimpleNamespace(nwo=SimpleNamespace())
                    factory = MagicMock(return_value=data)
                    fake = SimpleNamespace(data=SimpleNamespace(lights=SimpleNamespace(new=factory)))
                    attachment = SimpleNamespace(function_names=set())
                    strength = object()
                    with light.LightTag('lamp.light') as tag, patch.object(light, 'bpy', fake), \
                         patch.object(light.import_transform, 'distance', side_effect=lambda x: x * 100), \
                         patch.object(Function, 'to_blend_nodes', return_value=strength) as nodes, \
                         patch.object(utils, 'make_halo_light') as make:
                        if mode == 0 or animated_radius:
                            with self.assertRaises(NotImplementedError):
                                tag.to_blender(attachment=attachment)
                            factory.assert_not_called()
                            nodes.assert_not_called()
                        else:
                            self.assertIs(tag.to_blender('primary', 'secondary', attachment), data)
                            self.assertEqual(data.nwo.light_intensity, 8.)
                            self.assertEqual(data.nwo.light_far_attenuation_end, 800.)
                            self.assertEqual(attachment.function_names, {'power', 'pulse', 'boost'})
                            nodes.assert_called_once_with(name='lamp_strength', normalize=True)
                            self.assertIs(make.call_args.kwargs['strength_node_tree'], strength)
                    self.assertEqual(before, (Path(root) / 'lamp.light').read_bytes())

    def test_bad_light_mapping_falls_back_before_creating_lights(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.tags import cheap_light
        factory = MagicMock()
        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
             patch.object(utils, 'get_tags_path', return_value=root):
            with cheap_light.CheapLightTag('bad.cheap_light') as tag:
                color = tag.required_field(tag.tag.root(), 'color').as_struct()
                mapping = tag.required_field(color, 'Mapping').as_struct()
                tag.required_field(mapping, 'data').set(b'bad')
            with cheap_light.CheapLightTag('bad.cheap_light') as tag, \
                 patch.object(cheap_light, 'bpy', SimpleNamespace(data=SimpleNamespace(lights=SimpleNamespace(new=factory)))):
                with self.assertRaisesRegex(ValueError, 'invalid function data'):
                    tag.to_blender()
                factory.assert_not_called()

    def test_native_object_functions_create_blender_nodes(self):
        import bpy
        import struct
        from io_scene_foundry.tags.connected_material import Function
        name = 'foundry_native_function_test'
        group_name = 'function -> ' + name
        try:
            with tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                blob = bytearray(32)
                blob[0] = 1  # Scalar constant.
                struct.pack_into('<ff', blob, 4, 0.375, 1.)
                with ObjectTag('test.scenery') as obj:
                    functions = obj.block(obj.object_struct(), 'functions')
                    element = functions[functions.add()]
                    obj.required_field(element, 'export name').set(name)
                    mapping = obj.nested(element, 'default function')
                    next(f for f in mapping.fields() if f.type_name == 'data').set(bytes(blob))
                    dependencies = obj.functions_to_blender()
                    self.assertEqual(dependencies[name], ['one'])
                    group = bpy.data.node_groups[group_name]
                    values = [n.outputs[0].default_value for n in group.nodes if n.bl_idname == 'ShaderNodeValue']
                    self.assertIn(0.375, values)
                    decoded = Function()
                    decoded.from_native_object(obj, element)
                    self.assertEqual(decoded.sample(0, 1, 4), [(0.25, 0.375, 'AUTO'), (0.5, 0.375, 'AUTO'), (0.75, 0.375, 'AUTO')])
                    blob[0] = 0  # Identity has no curve-editor trailer.
                    next(f for f in mapping.fields() if f.type_name == 'data').set(bytes(blob))
                    identity = Function()
                    identity.from_native_object(obj, element)
                    tree = bpy.data.node_groups.new('native_identity_curve_test', 'ShaderNodeTree')
                    try:
                        identity._graph_to_nodes(tree, 0, False)
                        curve_node = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeFloatCurve')
                        curve = curve_node.mapping.curves[0]
                        for x in (0., .25, .5, 1.):
                            self.assertAlmostEqual(curve_node.mapping.evaluate(curve, x), x, places=5)
                    finally:
                        bpy.data.node_groups.remove(tree)
                    blob[0] = 0  # Identity has no curve-editor trailer.
                    next(f for f in mapping.fields() if f.type_name == 'data').set(bytes(blob))
                    identity = Function()
                    identity.from_native_object(obj, element)
                    tree = bpy.data.node_groups.new('native_identity_curve_test', 'ShaderNodeTree')
                    try:
                        identity._graph_to_nodes(tree, 0, False)
                        curve_node = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeFloatCurve')
                        curve = curve_node.mapping.curves[0]
                        for x in (0., .25, .5, 1.):
                            self.assertAlmostEqual(curve_node.mapping.evaluate(curve, x), x, places=5)
                    finally:
                        bpy.data.node_groups.remove(tree)
                    unsupported = functions[functions.add()]
                    obj.required_field(unsupported, 'export name').set(name + '_unsupported')
                    mapping = obj.nested(unsupported, 'default function')
                    next(f for f in mapping.fields() if f.type_name == 'data').set(b'bad')
                    with patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                         patch.object(Function, 'make_node_group') as create_nodes:
                        with self.assertRaisesRegex(ValueError, 'Cannot decode native object functions'):
                            obj.functions_to_blender()
                        create_nodes.assert_not_called()
                    unsupported = functions[functions.add()]
                    obj.required_field(unsupported, 'export name').set(name + '_unsupported')
                    mapping = obj.nested(unsupported, 'default function')
                    next(f for f in mapping.fields() if f.type_name == 'data').set(b'bad')
                    with patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                         patch.object(Function, 'make_node_group') as create_nodes:
                        with self.assertRaisesRegex(ValueError, 'Cannot decode native object functions'):
                            obj.functions_to_blender()
                        create_nodes.assert_not_called()
        finally:
            group = bpy.data.node_groups.get(group_name)
            if group is not None:
                bpy.data.node_groups.remove(group)

    def test_native_attachment_records_reach_light_converter(self):
        from unittest.mock import MagicMock
        collection = SimpleNamespace(nwo=SimpleNamespace(), objects=SimpleNamespace(link=MagicMock()))
        parent = SimpleNamespace(children=SimpleNamespace(link=MagicMock()))
        created = []
        def new_object(name, data):
            ob = SimpleNamespace(name=name, data=data, type='EMPTY')
            created.append(ob)
            return ob
        fake_bpy = SimpleNamespace(data=SimpleNamespace(
            collections=SimpleNamespace(new=MagicMock(return_value=collection), remove=MagicMock()),
            objects=SimpleNamespace(new=new_object)))
        marker = SimpleNamespace(nwo=SimpleNamespace(marker_model_group='head'))
        other = SimpleNamespace(nwo=SimpleNamespace(marker_model_group='body'))
        armature = object()
        converter = MagicMock()
        converter.__enter__.return_value.to_blender.return_value = SimpleNamespace(name='lamp')
        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
             patch.object(utils, 'get_tags_path', return_value=root), \
             patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
            (Path(root) / 'lamp.light').touch()
            with ObjectTag('test.scenery') as obj:
                block = obj.block(obj.object_struct(), 'attachments')
                element = block[block.add()]
                obj.set_reference(element, 'type', 'lamp.light')
                obj.required_field(element, 'marker').set('head')
                obj.required_field(element, 'primary scale').set('power')
                obj.required_field(element, 'secondary scale').set('pulse')
                with patch.dict(sys.modules, {'bpy': fake_bpy}), \
                     patch('io_scene_foundry.tags.light.LightTag', return_value=converter) as factory:
                    attachments = obj.attachments_to_blender(armature, [marker, other], parent)
                self.assertEqual(factory.call_args.kwargs['path'].RelativePathWithExtension, 'lamp.light')
                self.assertTrue(factory.call_args.kwargs['tag_must_exist'])
                self.assertEqual(len(created), 1)
                self.assertIs(created[0].parent, marker)
                self.assertEqual(attachments[0].objects, created)
                self.assertIs(attachments[0].armature, armature)
                self.assertEqual(attachments[0].function_names, {'power', 'pulse'})
                converter.__enter__.return_value.to_blender.assert_called_once_with('power', 'pulse', attachments[0])
                parent.children.link.assert_called_once_with(collection)

    def test_migrated_wrappers_do_not_initialize_managedblam(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(utils, 'get_asset_path', return_value='objects/test'), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with ModelTag('test.model') as model:
                    model.reference_render_model.Path = 'test.render_model'
                    self.assertEqual(model.get_model_variants(), [])
                with ModelTag('test.model') as model:
                    self.assertEqual(model.reference_render_model.Path.RelativePathWithExtension, 'test.render_model')
                with ObjectTag('test.scenery') as obj:
                    obj.set_model_tag_path('test.model')
                    self.assertEqual(obj.get_variants(), [])
                    self.assertEqual(obj.functions_to_blender(), {})
                    self.assertEqual(obj.attachments_to_blender(None, [], None), [])
                    attachments = obj.block(obj.object_struct(), 'attachments')
                    for reference in (None, 'missing.light', 'test.model'):
                        obj.set_reference(attachments[attachments.add()], 'type', reference)
                    # A populated block must not start .NET for missing or unsupported attachments.
                    self.assertEqual(obj.attachments_to_blender(None, [], None), [])
                with ObjectTag('test.scenery') as obj:
                    self.assertEqual(obj.get_model_tag_path(), 'test.model')
                    with ObjectTag('cinematic.scenery') as scenery:
                        scenery.copy_cinematic_object(obj)
                        self.assertEqual(scenery.get_model_tag_path(), 'test.model')
                (Path(root) / 'lamp.light').touch()
                with CinematicLightingTag('test.new_cinematic_lighting') as tag:
                    block = tag.block(tag.tag.root(), 'dynamic lights')
                    element = block[block.add()]
                    tag.set_reference(element, 'light', 'lamp.light')
                    for field, value in [('Direction', 90.), ('Front-Back', 30.), ('Distance', 2.)]:
                        tag.required_field(element, field).set(value)
                    result = tag.to_cinematic_lighting('head', True, 3)
                    self.assertEqual((result.marker, result.persist, result.shot_index), ('head', True, 3))
                    light = result.dynamic_lights[0]
                    self.assertEqual(light.light_tag.RelativePathWithExtension, 'lamp.light')
                    self.assertAlmostEqual(light.matrix.translation.x, 0., places=4)
                    self.assertAlmostEqual(light.matrix.translation.y, 173.20508, places=4)
                    self.assertAlmostEqual(light.matrix.translation.z, 100., places=4)
                for cls, method in [(GlobalsTag, 'get_global_materials'),
                                    (RenderMethodOptionTag, 'read_options'),
                                    (RenderMethodDefinitionTag, 'get_defaults')]:
                    with cls('test.' + cls.tag_ext, tag_must_exist=False) as tag:
                        self.assertFalse(getattr(tag, method)())
                with patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo4')):
                    with MaterialShaderTag('test.material_shader', tag_must_exist=False) as tag:
                        self.assertEqual(tag.read_parameters_list(), [])
                (Path(root) / 'bad.model').write_bytes(b'not a tag')
                with ModelTag('bad.model', raise_on_error=False, hide_prints=True, always_save=True) as model:
                    self.assertFalse(model.valid)
                    self.assertIsNotNone(model.error)
                self.assertEqual((Path(root) / 'bad.model').read_bytes(), b'not a tag')

    def test_native_reference_properties(self):
        from io_scene_foundry.tags.backend import TagReference
        reference = TagReference(Path('G:/tags'), 'textures/test', 'bitmap')
        self.assertEqual(reference.RelativePath, 'textures/test')
        self.assertEqual(reference.RelativePathWithExtension, 'textures/test.bitmap')
        self.assertEqual(reference.Extension, 'bitmap')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
