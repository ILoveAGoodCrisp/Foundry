"""Blender 5.2 --background --factory-startup --python-exit-code 1 --python this_file.

Optional integration test: -- --cinematic <absolute .cinematic path> --game reach|halo3|halo3odst
Add --scenario for scenario geometry, --materials for shaders, or --save <output.blend>.
Source tags must remain read-only throughout the integration test.
"""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import bpy
from mathutils import Matrix

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(wheels.name)
sys.path.insert(0, wheels.name)

from io_scene_foundry import preferences, props, utils
from io_scene_foundry.constants import LIGHTMAP_CHART_GROUP_INDEX
from io_scene_foundry.tags.animation_graph import AnimationGraphTag
from io_scene_foundry.tags.backend import TagDocument
from io_scene_foundry.tags import connected_material
from io_scene_foundry.tools import shader_reader
from io_scene_foundry.tags.prefab import ScenarioStructureBspMetadataTag
from io_scene_foundry.tools import node_tree_arrange
from io_scene_foundry.tools.importer import (
    NWO_Import, NWOImporter, NWO_FH_Import, NWO_FH_ImportCinematic,
    add_scene_data_to_nla)

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
cinematic = Path(args[args.index('--cinematic') + 1]) if '--cinematic' in args else None


class CinematicImportTests(unittest.TestCase):
    def test_cinematic_import_info_is_disabled(self):
        for scene_is_cinematic, extensions, expected in (
                (True, {'model'}, False), (False, {'cinematic'}, False),
                (False, {'model'}, True)):
            importer = NWOImporter.__new__(NWOImporter)
            importer.for_cinematic = scene_is_cinematic
            importer.extensions = extensions
            importer.configure_import_info(Path(wheels.name))
            self.assertEqual(importer.use_import_info, expected)
            if not expected:
                self.assertEqual(importer.import_info_sources_for_tag('any.render_model'), [])

    def test_ass_anchor_cleanup_preserves_nested_world_transforms(self):
        from io_scene_foundry.legacy.ass_importer import ASSImporter
        importer = ASSImporter.__new__(ASSImporter)
        importer.ass = SimpleNamespace(instances=[SimpleNamespace(parent=p) for p in (-1, 0, 1)])
        importer.order = [0, 1, 2]
        importer.frame_instances = set()
        importer.anchors = {}
        importer.instance_objects = {}
        importer.objects = []
        collection = bpy.data.collections.new('anchor_cleanup_test')
        bpy.context.scene.collection.children.link(collection)
        for index, count in enumerate((1, 2, 1)):
            anchor = bpy.data.objects.new(f'anchor_{index}', None)
            collection.objects.link(anchor)
            anchor.parent = importer.anchors.get(index - 1)
            anchor.matrix_basis = Matrix.Translation((index + 2, 3, 1)) @ Matrix.Rotation(.3, 4, 'Z')
            anchor['ass_instance'] = str(index)
            importer.anchors[index] = anchor
            importer.objects.append(anchor)
            parts = []
            for part in range(count):
                ob = bpy.data.objects.new(f'part_{index}_{part}', None)
                collection.objects.link(ob)
                ob.parent = anchor
                ob.matrix_basis = Matrix.Translation((part, 2, 3)) @ Matrix.Scale(1.5, 4)
                parts.append(ob)
                importer.objects.append(ob)
            importer.instance_objects[index] = parts
        bpy.context.view_layer.update()
        expected = {ob: ob.matrix_world.copy() for ob in importer.objects
                    if ob not in (importer.anchors[0], importer.anchors[2])}
        importer.collapse_frames()
        self.assertEqual(set(importer.objects), set(expected))
        self.assertEqual(set(importer.anchors), {1})
        self.assertEqual(importer.anchors[1].parent, importer.instance_objects[0][0])
        self.assertEqual(importer.instance_objects[2][0].parent, importer.anchors[1])
        for ob, matrix in expected.items():
            self.assertLess(max(abs(a - b) for row_a, row_b in zip(ob.matrix_world, matrix)
                                for a, b in zip(row_a, row_b)), 1e-5)
        bpy.data.batch_remove(tuple(collection.objects))
        bpy.data.collections.remove(collection)

    def test_drag_drop_extensions_fit_blender_buffer(self):
        from io_scene_foundry.tools import classes
        handlers = [cls for cls in classes if issubclass(cls, bpy.types.FileHandler)]
        for handler in handlers:
            self.assertLess(len(handler.bl_file_extensions.encode('utf-8')), 512, handler.__name__)
        self.assertIn(NWO_FH_ImportCinematic, handlers)
        self.assertEqual(NWO_FH_ImportCinematic.bl_import_operator, NWO_FH_Import.bl_import_operator)
        self.assertIn('.cinematic', NWO_FH_ImportCinematic.bl_file_extensions.split(';'))
        for area_type, expected in [('VIEW_3D', True), ('TEXT_EDITOR', False)]:
            context = SimpleNamespace(area=SimpleNamespace(type=area_type))
            self.assertEqual(NWO_FH_ImportCinematic.poll_drop(context), expected)
        self.assertFalse(NWO_FH_ImportCinematic.poll_drop(SimpleNamespace(area=None)))
        for handler in (NWO_FH_Import, NWO_FH_ImportCinematic):
            bpy.utils.register_class(handler)
            try:
                self.assertIs(bpy.types.FileHandler.bl_rna_get_subclass_py(handler.bl_idname), handler)
            finally:
                bpy.utils.unregister_class(handler)

    def test_reused_animation_names_keep_their_own_actors(self):
        actors = []
        scene_nwo = SimpleNamespace(animations=[])
        for index in range(2):
            armature = bpy.data.objects.new(f'actor_{index}', bpy.data.armatures.new(f'rig_{index}'))
            armature.animation_data_create()
            action = bpy.data.actions.new('elite_01_1')
            action.slots.new('OBJECT', armature.name)
            action.use_frame_range = True
            action.frame_start, action.frame_end = 1, 10
            animation = SimpleNamespace(name='elite_01_1', frame_start=1, frame_end=10,
                action_tracks=[SimpleNamespace(object=armature, action=action, is_shape_key_action=False)])
            scene_nwo.animations.append(animation)
            actor = SimpleNamespace(armature=armature, animations={1: index})
            actors.append(actor)
            add_scene_data_to_nla(SimpleNamespace(shot_frames=[20], object_animations=[actor]), scene_nwo)
        for actor in actors:
            strips = [strip for track in actor.armature.animation_data.nla_tracks for strip in track.strips]
            self.assertEqual(len(strips), 1)
            self.assertEqual(strips[0].action, scene_nwo.animations[actor.animations[1]].action_tracks[0].action)
            self.assertEqual((strips[0].frame_start, strips[0].frame_end), (20, 29))

    def test_compression_preference_is_read_only(self):
        for original in range(4):
            field = SimpleNamespace(options=lambda: SimpleNamespace(current=original))
            graph = SimpleNamespace(_definitions=lambda: SimpleNamespace(field=lambda name: field))
            self.assertEqual(AnimationGraphTag.forced_compression(graph), original)
        graph = SimpleNamespace(_definitions=lambda: SimpleNamespace(field=lambda name: None))
        self.assertEqual(AnimationGraphTag.forced_compression(graph), 0)

    def test_old_material_layout_without_chart_group(self):
        fields = {name: SimpleNamespace(value=value) for name, value in {
            'lightmap resolution scale': 1.0,
            'lightmap additive transparency color': 0,
            'lightmap traslucency tint color': 0,
            'lightmap analytical light absorb': 0.0,
            'lightmap normal light absorb': 0.0,
            'imported material index': -1,
            'breakable surface index': -1,
        }.items()}
        fields['lightmap flags'] = SimpleNamespace(get_flag=lambda name: False)
        element = SimpleNamespace(field=fields.get, path='materials[0]')
        document = SimpleNamespace(
            tag=SimpleNamespace(root=lambda: None), path='old.render_model',
            block=lambda root, name: [element], reference=lambda *a: 'test.shader',
            value=lambda struct, name: fields[name].value,
            required_field=lambda struct, name: fields[name])
        material, = ScenarioStructureBspMetadataTag.render_materials(document)
        self.assertEqual(material.chart_group_index, LIGHTMAP_CHART_GROUP_INDEX)
        fields['lightmap chart group index'] = SimpleNamespace(value=7)
        material, = ScenarioStructureBspMetadataTag.render_materials(document)
        self.assertEqual(material.chart_group_index, 7)

    @unittest.skipUnless(cinematic, 'Pass --cinematic for the real-tag integration test')
    def test_cinematic_operator(self):
        tags = next(parent for parent in cinematic.parents if parent.name.lower() == 'tags')
        game = args[args.index('--game') + 1] if '--game' in args else 'reach'
        project = SimpleNamespace(game=game, corinth=False, tags_directory=str(tags),
                                  data_directory=str(tags.parent / 'data'), project_path=str(tags.parent))
        if '--materials' in args:
            project.data_directory = str(Path(wheels.name) / 'bitmap_data')
        target_project = SimpleNamespace(**vars(project))
        if '--target-game' in args:
            target_project.game = args[args.index('--target-game') + 1]

        def get_project(*args, use_external=True, **kwargs):
            return project if use_external else target_project
        props.register()
        preferences.register()
        bpy.context.preferences.addons.new().module = 'io_scene_foundry'
        bpy.utils.register_class(NWO_Import)
        bpy.context.scene.nwo.asset_type = 'cinematic'
        bpy.context.scene.nwo.is_main_scene = True
        scene_nwo = bpy.context.scene.nwo
        imported = []
        original_import = NWOImporter.import_cinematic

        def capture_import(importer, *args, **kwargs):
            result = original_import(importer, *args, **kwargs)
            imported.extend(result[0])
            return result

        def forbid_save(document):
            self.fail(f'Import attempted to rewrite source tag: {document.path}')

        def forbid_import_info(*args, **kwargs):
            self.fail('Cinematic import attempted to read import info')

        with (patch.object(utils, 'get_project', side_effect=get_project),
              patch.object(utils, 'get_tags_path', return_value=str(tags)),
              patch.object(utils, 'get_export_props', return_value=SimpleNamespace(show_output=False)),
              patch.object(utils, 'set_import_context_from_filepath'),
              patch.object(utils, 'clear_output'),
              patch.object(utils, 'get_version_string', return_value='test'),
              patch.object(utils, 'matrix_from_mouse', return_value=Matrix.Identity(4)),
              # Background Blender has no UI scale; skip only node positioning.
              patch.object(utils, 'arrange'),
              patch.object(connected_material, 'arrange'),
              patch.object(shader_reader, 'arrange'),
              patch.object(node_tree_arrange, 'arrange'),
              patch.object(TagDocument, 'save', forbid_save),
              patch.object(TagDocument, 'import_info_sources', forbid_import_info),
              patch.object(NWOImporter, 'import_cinematic', capture_import)):
            result = bpy.ops.nwo.foundry_import(
                filepath=str(cinematic), tag_cinematic_import_scenario='--scenario' in args,
                tag_cinematic_import_actors=True, build_blender_materials='--materials' in args,
                tag_import_lights=True, build_control_rig=False, graph_bake_to_control_rig=False)
            self.assertEqual(result, {'FINISHED'})
            self.assertTrue(imported)
            for data in imported:
                self.assertTrue(data.camera_objects)
                self.assertEqual([marker.frame for marker in data.blender_scene.timeline_markers],
                                 data.shot_frames)
                for camera in data.camera_objects:
                    self.assertIn(camera.name, data.blender_scene.objects)
                if '--scenario' in args and scene_nwo.cinematic_scenario:
                    instances = [ob.instance_collection for ob in data.blender_scene.objects
                                 if ob.instance_type == 'COLLECTION' and ob.instance_collection]
                    self.assertTrue(any(ob.type == 'MESH' for collection in instances
                                        for ob in collection.all_objects), data.name)
                for actor in data.object_animations:
                    self.assertIsNotNone(actor.armature)
                    self.assertIn(actor.armature.name, data.blender_scene.objects)
                    self.assertTrue(actor.animations, actor.name)
                    strips = [strip for track in actor.armature.animation_data.nla_tracks
                              for strip in track.strips]
                    self.assertTrue(strips, (data.name, actor.name))
                    for shot, animation_index in actor.animations.items():
                        # A shared graph can contain shots outside this cinematic scene.
                        if shot is None or not 1 <= shot <= len(data.shot_frames):
                            continue
                        animation = scene_nwo.animations[animation_index]
                        expected_start = data.shot_frames[shot - 1]
                        for track in animation.action_tracks:
                            self.assertTrue(any(strip.action == track.action and strip.frame_start == expected_start
                                                for strip in strips), (data.name, actor.name, shot))
                if cinematic.stem == '080lc_game_over':
                    self.assertTrue(any(ob.type == 'LIGHT' for ob in data.blender_scene.objects))
                print('VERIFIED', data.name, len(data.camera_objects), 'cameras,',
                      len(data.object_animations), 'animated actors')
            if cinematic.stem == '080lc_game_over':
                self.assertEqual([len(data.object_animations) for data in imported], [11, 25])
                self.assertEqual([data.shot_frames for data in imported], [[1, 77], [1, 778]])
            if '--materials' in args and cinematic.stem == '010pa_jail_bait':
                material = next(mat for mat in bpy.data.materials
                                if mat.nwo.shader_path.endswith('terrain_generic_rock.shader'))
                group = next(node for node in material.node_tree.nodes if node.type == 'GROUP'
                             and node.node_tree.name.startswith('foundry_h3.shader'))
                self.assertEqual(group.inputs[4].default_value, 'single_lobe_phong')
                self.assertTrue(any(image.source == 'FILE' and image.size[0] > 0 for image in bpy.data.images),
                                [(image.name, image.source, tuple(image.size)) for image in bpy.data.images])
            if '--save' in args:
                bpy.ops.wm.save_as_mainfile(filepath=str(Path(args[args.index('--save') + 1]).resolve()))


suite = unittest.defaultTestLoader.loadTestsFromTestCase(CinematicImportTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
