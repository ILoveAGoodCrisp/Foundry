"""Run with Blender --background --factory-startup --python this_file."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import sys
import tempfile
import unittest
from zipfile import ZipFile

import addon_utils
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blender/addons'))
_wheel_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for wheel_path in (ROOT / 'blender/addons/io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(wheel_path) as wheel:
        wheel.extractall(_wheel_directory.name)
sys.path.insert(0, _wheel_directory.name)
import io_scene_foundry
io_scene_foundry.startup.load_projects = lambda: None
addon_utils.enable('io_scene_foundry', default_set=True, persistent=False)

from io_scene_foundry import import_transform, utils
from io_scene_foundry.legacy.jma import Node
from io_scene_foundry.tags.animation import AnimationTag, AnimationType
from io_scene_foundry.tags.animation_resource import (
    AnimationData, FrameInfoType, MovementData, apply_movement_data,
)
from io_scene_foundry.tags.animation_graph import AnimationBlendScreen
from io_scene_foundry.tools.animation.legacy_import import (
    prepare_reach_skeleton, convert_blend_screen, generate_reach_aim_look_overlays,
)
from io_scene_foundry.tools import importer as importer_module
from io_scene_foundry.tools.animation import legacy_turns
from io_scene_foundry.tools.animation.reach_import import (
    LegacyAnimationConverter, legacy_screen_vertices, remap_legacy_screen_events,
    resample_screen_event_curves, sample_pose_screen,
)
from io_scene_foundry.tools.animation.generate_aim_look_overlays import (
    _fcurve_map, _rest_local_matrix, _sample_local_matrices, _world_matrices,
)
from io_scene_foundry.tools.importer import draw_animation_graph_import_options, draw_graph_import_options


class LegacyImportTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        self.nwo = utils.get_scene_props()
        self.nwo.scale = 'blender'
        self.nwo.forward_direction = 'y'
        self.nwo.animations.clear()
        bpy.ops.object.armature_add()
        self.arm = bpy.context.object
        self.arm.data.bones[0].name = 'root'

    def assertMatrix(self, actual, expected):
        for row, other in zip(actual, expected):
            for value, target in zip(row, other):
                self.assertAlmostEqual(value, target, places=4)

    def test_skeleton_reuse_and_partial_skeleton(self):
        rest = self.arm.data.bones['root'].matrix_local.copy()
        bpy.ops.object.mode_set(mode='EDIT')
        pedestal = self.arm.data.edit_bones.new('b_pedestal')
        pedestal.tail = (0, 1, 0)
        bpy.ops.object.mode_set(mode='OBJECT')
        names = prepare_reach_skeleton(self.arm)
        self.assertEqual(names['pedestal'], 'b_pedestal')
        self.assertEqual(self.arm.data.bones['root'].parent.name, 'b_pedestal')
        self.assertMatrix(self.arm.data.bones['root'].matrix_local, rest)
        before = [(b.name, b.parent.name if b.parent else None, b.matrix_local.copy()) for b in self.arm.data.bones]
        self.assertEqual(prepare_reach_skeleton(self.arm), names)
        self.assertEqual(len(self.arm.data.bones), 4)
        for name, parent, matrix in before:
            bone = self.arm.data.bones[name]
            self.assertEqual(bone.parent.name if bone.parent else None, parent)
            self.assertMatrix(bone.matrix_local, matrix)

    def test_movement_curves_preserve_world_pose_and_leave_root_stationary(self):
        names = prepare_reach_skeleton(self.arm)
        tag = object.__new__(AnimationTag)
        tag.game = 'reach'
        root, pedestal = Node('root'), Node(names['pedestal'])
        tag._reach_pedestal_node = pedestal
        tag._reach_pedestal_rest = self.arm.data.bones[names['pedestal']].matrix_local.copy()
        tag._reach_unmoved_roots = {}
        turn = Quaternion((0, 0, 1), 0.3)
        pose = {
            'frames': [[(0, 0, 1, 0, 0, 0, 1, 1)]] * 3,
            'movement': [(0.2, 0.1, 0, turn.x, turn.y, turn.z, turn.w)] * 3,
            'movement_kind': 'DxDyDyaw',
        }
        tag._tag = SimpleNamespace(animation_pose=lambda *args: pose)
        animation = SimpleNamespace(index=0, animation_type=AnimationType.BASE, frame_info_type=FrameInfoType.DX_DY_DYAW)
        cache = {}
        transforms = tag._animation_transforms(animation, [], [], [root], {}, None, {}, cache, [])
        original = cache[0].frame_matrices()
        for frame, values in transforms.items():
            self.assertMatrix(values[pedestal] @ values[root], import_transform.armature_bone_matrix(original[frame - 1][0], root=True))
        self.arm.animation_data_create()
        for scale_to_skeleton in (False, True):
            action = bpy.data.actions.new('movement')
            slot = action.slots.new('OBJECT', self.arm.name)
            self.arm.animation_data.action = action
            self.arm.animation_data.action_slot = slot
            tag._to_armature_action(transforms, self.arm, action, [root, pedestal], [], None, {}, set(),
                                    scale_animations_to_skeleton=scale_to_skeleton)
            curves = utils.get_fcurves(action, slot)
            for axis in range(3):
                curve = curves.find('pose.bones["root"].location', index=axis)
                self.assertAlmostEqual(curve.evaluate(1), curve.evaluate(4), places=5)
            for frame in transforms:
                bpy.context.scene.frame_set(frame)
                self.assertMatrix(self.arm.pose.bones['root'].matrix, import_transform.armature_bone_matrix(original[frame - 1][0], root=True))

    def test_movement_yaw_precedes_rotated_legacy_root_pose(self):
        angle = 0.3
        root_pose = Quaternion((1, 0, 0), 1.1)
        turn = Quaternion((0, 0, 1), angle)
        animation = AnimationData(
            1,
            [[Vector()]],
            [[root_pose.copy()]],
            [[1.0]],
            [False], [True], [False],
        )
        movement = MovementData(
            FrameInfoType.DX_DY_DYAW,
            [Vector()],
            [turn],
        )
        apply_movement_data(animation, movement)
        movement_delta = animation.rotations[0][0] @ root_pose.inverted()
        axis, actual_angle = movement_delta.to_axis_angle()
        self.assertAlmostEqual(abs(axis.z), 1.0, places=5)
        self.assertAlmostEqual(axis.x, 0.0, places=5)
        self.assertAlmostEqual(axis.y, 0.0, places=5)
        self.assertAlmostEqual(actual_angle, angle, places=5)

        # The old order turns this same Z yaw into the root's tilted Y axis.
        old_order = root_pose @ turn
        old_delta = old_order @ root_pose.inverted()
        old_axis, _ = old_delta.to_axis_angle()
        self.assertGreater(abs(old_axis.y), 0.5)

    def test_skeletal_motion_is_preserved_with_and_without_movement(self):
        names = prepare_reach_skeleton(self.arm)
        self.arm.data.bones['root'].name = 'b_root'
        tag = object.__new__(AnimationTag)
        tag.game = 'reach'
        root, pedestal = Node('root'), Node(names['pedestal'])
        tag._reach_pedestal_node = pedestal
        tag._reach_pedestal_rest = self.arm.data.bones[names['pedestal']].matrix_local.copy()
        tag._reach_unmoved_roots = {}
        frames = []
        for frame in range(3):
            q = Quaternion((1, 0, 0), frame * 0.2)
            frames.append([(0.1 * frame, 0, 1, q.x, q.y, q.z, q.w, 1)])
        animation = SimpleNamespace(index=0, animation_type=AnimationType.BASE, frame_info_type=FrameInfoType.DX_DY_DYAW)
        self.arm.animation_data_create()
        for movement in ([], [(0.2, 0, 0, 0, 0, 0, 1)] * 3):
            tag._tag = SimpleNamespace(animation_pose=lambda *args: {
                'frames': frames,
                'movement': movement,
                'movement_kind': 'DxDyDyaw',
            })
            cache = {}
            transforms = tag._animation_transforms(animation, [], [], [root], {}, None, {}, cache, [])
            action = bpy.data.actions.new('skeletal_motion')
            slot = action.slots.new('OBJECT', self.arm.name)
            self.arm.animation_data.action = action
            self.arm.animation_data.action_slot = slot
            tag._to_armature_action(transforms, self.arm, action, [root, pedestal], [], None, {}, set())
            original = cache[0].frame_matrices()
            for frame in transforms:
                bpy.context.scene.frame_set(frame)
                self.assertMatrix(self.arm.pose.bones['b_root'].matrix, import_transform.armature_bone_matrix(original[frame - 1][0], root=True))

    def test_option_shown_in_graph_and_object_settings(self):
        class Layout:
            enabled = True
            def __init__(self):
                self.properties = []
            def row(self): return self
            def column(self, **kwargs): return self
            def box(self): return self
            def prop(self, operator, name): self.properties.append(name)
        operator = SimpleNamespace(tag_animation=True, graph_import_animations=True)
        for draw in (draw_animation_graph_import_options, draw_graph_import_options):
            for corinth in (False, True):
                layout = Layout()
                draw(operator, layout, corinth)
                self.assertEqual(layout.properties.count('convert_animations'), 1)
                self.assertNotIn('graph_convert_to_reach', layout.properties)
                self.assertNotIn('convert_animation_names', layout.properties)
        for operator_type in (importer_module.NWO_Import, importer_module.NWO_OT_ImportFromDrop):
            self.assertTrue(operator_type.__annotations__['convert_animations'].keywords['default'])

    def reverse_fixture(self):
        pedestal, body, yaw = Node('pedestal'), Node('root'), Node('aim_yaw')
        body.parent = yaw.parent = pedestal
        body.parent_index = yaw.parent_index = 0
        nodes = [pedestal, body, yaw]
        vertices = [(y, p) for y in (0.0, -1.0, 1.0) for p in (1.0, 0.0, -1.0)]
        vertices.append((4.0, 0.0))  # Reach wrap duplicate, never a legacy sample.
        poses = [[Matrix.Identity(4), Matrix.Translation((y, p, 1)), Matrix.Rotation(y, 4, 'Z')]
                 for y, p in vertices]
        reference = [Matrix.Identity(4), Matrix.Translation((10, 10, 1)), Matrix.Identity(4)]
        overlay = SimpleNamespace(index=0, name=utils.AnimationName('combat rifle aim_still_up'),
                                  animation_type=AnimationType.OVERLAY, is_pose_overlay=True)
        tag = SimpleNamespace(_native_node_usages={'pedestal': 0, 'pose blend yaw': 2},
                              _pose_overlay_blend_screen_vertices=lambda animation: vertices)
        data = SimpleNamespace(frame_matrices=lambda: [reference, *poses])
        converter = LegacyAnimationConverter(tag, nodes, [overlay], lambda animation: data)
        return converter, overlay, data, nodes, vertices, poses

    def test_reverse_screen_order_controls_reference_and_events(self):
        converter, overlay, data, _, vertices, poses = self.reverse_fixture()
        frames = converter.frames(overlay, data)
        self.assertEqual(len(frames), 10)
        self.assertMatrix(frames[0][1], Matrix.Translation((10, 10, 1)))
        for frame, (yaw, pitch) in zip(frames[1:], legacy_screen_vertices()):
            self.assertMatrix(frame[1], Matrix.Translation((max(-1, min(1, yaw)), max(-1, min(1, pitch)), 1)))
            self.assertMatrix(frame[2], Matrix.Identity(4))
        self.assertMatrix(poses[4][2], Matrix.Rotation(-1, 4, 'Z'))
        # Interpolate ragged columns and clamp beyond the authored limits.
        pose = sample_pose_screen(vertices, poses, 0.5, -0.25)
        self.assertMatrix(pose[1], Matrix.Translation((0.5, -0.25, 1)))
        self.assertIsNone(sample_pose_screen([(-1, 1)], poses[:1], 0, 0, require_coverage=True))
        animation = self.nwo.animations.add()
        animation.name = 'combat rifle aim_still_up'
        event = animation.animation_events.add()
        event.frame_frame = 3  # Source yaw=0, pitch=0 becomes legacy frame 6.
        event = animation.animation_events.add()
        event.event_type = legacy_turns._WRAP_EVENT_TYPE
        event.import_name = next(iter(legacy_turns._WRAP_EVENT_NAMES))
        event.frame_frame = 11
        animation.loop_frame_index = 2
        remap_legacy_screen_events([animation], {animation.name: converter.frame_maps[0]})
        self.assertEqual(len(animation.animation_events), 1)
        self.assertEqual(animation.animation_events[0].frame_frame, 6)
        self.assertEqual(animation.loop_frame_index, 5)
        overlay.name = utils.AnimationName('combat rifle pain_gut')
        converter.frame_maps.clear()
        self.assertEqual(converter.frames(overlay, data), data.frame_matrices())
        self.assertEqual(converter.frame_maps, {})

    def test_reverse_turn_keeps_pedestal_and_local_motion_with_filtered_reference(self):
        converter, _, _, _, _, _ = self.reverse_fixture()
        for index, state in enumerate(legacy_turns._TURN_DIRECTIONS, start=1):
            turn = SimpleNamespace(index=index, name=utils.AnimationName(f'combat rifle {state}'),
                                   animation_type=AnimationType.BASE, is_pose_overlay=False)
            original = [[Matrix.Rotation(frame / 3, 4, 'Z'),
                         Matrix.Translation((-1 + frame / 4, 0, 1)) @ Matrix.Rotation(frame / 8, 4, 'X'),
                         Matrix.Rotation(-1, 4, 'Z')] for frame in range(4)]
            result = converter.frames(turn, SimpleNamespace(frame_matrices=lambda: original))
            for frame in range(4):
                self.assertIs(result[frame][0], original[frame][0])
                self.assertMatrix(result[frame][1], Matrix.Translation((frame / 4, 0, 1)) @ Matrix.Rotation(frame / 8, 4, 'X'))
                self.assertMatrix(result[frame][2], Matrix.Identity(4))
            self.assertIn(index, converter.converted_turns)
        turn.name = utils.AnimationName('combat pistol turn_right')
        self.assertEqual(converter.frames(turn, SimpleNamespace(frame_matrices=lambda: original)), original)

    def test_reverse_event_values_follow_screen_samples_without_rewriting_body(self):
        converter, overlay, data, _, vertices, _ = self.reverse_fixture()
        converter.frames(overlay, data)
        animation = self.add_overlay_fixture_animation('combat rifle aim_still_up', overlay=True)
        track = animation.action_tracks[0]
        curves = utils.get_fcurves(track.action, self.arm)
        preserved = {curve.as_pointer() for curve in curves}
        original = {curve.as_pointer(): [tuple(key.co) for key in curve.keyframe_points] for curve in curves}
        event_curve = curves.new(data_path='pose.bones["root"]["event_weight"]')
        event_curve.keyframe_points.insert(1, 123)
        for frame, (yaw, pitch) in enumerate(vertices, start=2):
            event_curve.keyframe_points.insert(frame, yaw + 10 * pitch)
        event_curve.update()
        resample_screen_event_curves(animation, converter.frame_samples[0], preserved)
        self.assertEqual(len(event_curve.keyframe_points), 10)
        self.assertAlmostEqual(event_curve.evaluate(1), 123)
        for frame, (yaw, pitch) in enumerate(legacy_screen_vertices(), start=2):
            self.assertAlmostEqual(event_curve.evaluate(frame), max(-1, min(1, yaw)) + 10 * max(-1, min(1, pitch)))
        for curve in curves:
            if curve.as_pointer() in preserved:
                self.assertEqual([tuple(key.co) for key in curve.keyframe_points], original[curve.as_pointer()])

    def test_reverse_action_folds_missing_pedestal_into_legacy_root(self):
        tag = object.__new__(AnimationTag)
        tag._legacy_conversion = True
        pedestal, root = Node('pedestal'), Node('root')
        root.parent, root.parent_index = pedestal, 0
        self.arm.animation_data_create()
        action = bpy.data.actions.new('reverse turn')
        slot = action.slots.new('OBJECT', self.arm.name)
        self.arm.animation_data.action = action
        self.arm.animation_data.action_slot = slot
        transforms = {frame: {pedestal: Matrix.Rotation(frame / 3, 4, 'Z'),
                              root: Matrix.Translation((1, 0, 1))} for frame in range(1, 4)}
        tag._to_armature_action(transforms, self.arm, action, [pedestal, root], [], None, {}, set(),
                                node_usages={'pedestal': 0})
        curves, _ = _fcurve_map(action, self.arm)
        rest = {bone.name: _rest_local_matrix(bone) for bone in self.arm.pose.bones}
        for frame, pose in transforms.items():
            result = _sample_local_matrices(self.arm, curves, frame, rest)
            self.assertMatrix(result['root'], pose[pedestal] @ pose[root])

    def test_blend_screen_keys_correct_action_and_replaces_wrap_events(self):
        names = prepare_reach_skeleton(self.arm)
        self.arm.animation_data_create()
        record = AnimationBlendScreen('aim', 90, 90, 3, 3, 45, 45, 1, 1)
        unrelated = bpy.data.actions.new('unrelated')
        unrelated.slots.new('OBJECT', 'unrelated')
        self.arm.animation_data.action = unrelated
        action = bpy.data.actions.new('aim')
        slot = action.slots.new('OBJECT', self.arm.name)
        animation = self.nwo.animations.add()
        animation.name = 'combat:rifle:aim'
        animation.frame_start = 1
        convert_blend_screen(self.arm, animation, action, slot, record, names)
        event_count = len(animation.animation_events)
        self.assertGreater(event_count, 0)
        convert_blend_screen(self.arm, animation, action, slot, record, names)
        self.assertEqual(len(animation.animation_events), event_count)
        self.assertEqual(animation.frame_end, 22)
        self.assertTrue(animation.pose_overlay)
        curves = utils.get_fcurves(action, slot)
        for name in ('aim_yaw', 'aim_pitch'):
            curve = curves.find(f'pose.bones["{name}"].rotation_quaternion', index=0)
            self.assertIsNotNone(curve)
            self.assertEqual(len(curve.keyframe_points), 22)
        self.assertFalse(utils.get_fcurves(unrelated, unrelated.slots[0]))

    def add_overlay_fixture_animation(self, name, *, overlay=False, height=0):
        animation = self.nwo.animations.add()
        animation.name = name
        animation.animation_type = 'overlay' if overlay else 'base'
        animation.pose_overlay = overlay
        animation.frame_start = 1
        animation.frame_end = 3
        action = bpy.data.actions.new(name)
        slot = action.slots.new('OBJECT', self.arm.name)
        self.arm.animation_data_create()
        self.arm.animation_data.action = action
        self.arm.animation_data.action_slot = slot
        track = animation.action_tracks.add()
        track.object = self.arm
        track.action = action
        for frame in range(1, 4):
            for bone in self.arm.pose.bones:
                bone.matrix_basis = Matrix.Identity(4)
                bone.rotation_mode = 'QUATERNION'
                if bone.name == 'root':
                    bone.location.z = height + (frame if overlay else 0)
                if bone.name == 'aim_yaw' and overlay and frame > 1:
                    bone.rotation_quaternion = Quaternion((0, 0, 1), 2.1)
                bone.keyframe_insert('location', frame=frame)
                bone.keyframe_insert('rotation_quaternion', frame=frame)
        return animation

    def test_import_generates_overlay_poses_metadata_and_preserves_existing(self):
        prepare_reach_skeleton(self.arm)
        self.nwo.node_usage_pelvis = 'root'
        source = self.add_overlay_fixture_animation('combat rifle aim_still_up var2', overlay=True)
        source.animation_renames.add().name = 'combat pistol aim_still_up var2'
        event = source.animation_events.add()
        event.event_type = '_connected_geometry_animation_event_type_frame'
        event.frame_frame = 2
        event = source.animation_events.add()
        event.event_type = '_connected_geometry_animation_event_type_import'
        event.import_name = 'Wrapped Right'
        event.frame_frame = 99
        look = self.add_overlay_fixture_animation('combat rifle look_still', overlay=True)
        walk = self.add_overlay_fixture_animation('combat rifle walk_front', height=4)
        move = self.add_overlay_fixture_animation('combat rifle move_front', height=8)
        existing = self.add_overlay_fixture_animation('combat rifle aim_move_front_up var2', overlay=True)
        existing_action = existing.action_tracks[0].action
        # Scene entries outside the current import must not become sources/bases.
        self.add_overlay_fixture_animation('combat rifle airborne')
        self.add_overlay_fixture_animation('combat rifle aim_still_down', overlay=True)
        self.add_overlay_fixture_animation('combat rifle move_left')
        imported = self.nwo.animations[:5]
        previous_action = self.arm.animation_data.action
        previous_frame = bpy.context.scene.frame_current
        generated = generate_reach_aim_look_overlays(self.nwo, self.arm, imported)
        self.assertEqual({a.name for a in generated}, {
            'combat rifle aim_walk_front_up var2',
            'combat rifle look_walk_front', 'combat rifle look_move_front',
        })
        self.assertEqual(self.arm.animation_data.action, previous_action)
        self.assertEqual(bpy.context.scene.frame_current, previous_frame)
        target = next(a for a in generated if 'aim_walk' in a.name)
        self.assertTrue(target.pose_overlay)
        self.assertEqual(target.animation_type, 'overlay')
        self.assertEqual(target.animation_renames[0].name, 'combat pistol aim_walk_front_up var2')
        self.assertEqual([e.frame_frame for e in target.animation_events
                          if e.event_type == '_connected_geometry_animation_event_type_frame'], [2])
        wraps = [e for e in target.animation_events
                 if e.event_type == '_connected_geometry_animation_event_type_import']
        self.assertEqual([e.frame_frame for e in wraps], [2, 3])
        action = target.action_tracks[0].action
        self.assertNotEqual(action, self.nwo.animations[0].action_tracks[0].action)
        curves = utils.get_fcurves(action, action.slots[0])
        root_z = curves.find('pose.bones["root"].location', index=2)
        for frame in range(1, 4):
            self.assertAlmostEqual(root_z.evaluate(frame), 4)
        self.assertEqual(self.nwo.animations[4].action_tracks[0].action, existing_action)
        self.assertEqual(generate_reach_aim_look_overlays(self.nwo, self.arm, self.nwo.animations[:5]), [])

    def test_graph_import_generates_overlays_only_for_legacy_reach_conversion(self):
        prepare_reach_skeleton(self.arm)
        for game, enabled, import_animations, expected in (
                ('halo1', True, True, True), ('halo2', True, True, True),
                ('halo3', True, True, True), ('halo3odst', True, True, True),
                ('reach', True, True, False), ('halo4', True, True, False),
                ('halo3', False, True, False), ('halo3', True, False, False)):
            with self.subTest(game=game, enabled=enabled, import_animations=import_animations):
                self.nwo.animations.clear()
                graph = MagicMock()
                graph.game = game
                graph.force_uncompressed_for_import.return_value = (0, False)
                graph.__enter__.return_value = graph
                tag = MagicMock()
                tag.__enter__.return_value = tag

                def import_actions(*args, **kwargs):
                    self.assertEqual(kwargs['convert_to_reach'], expected)
                    source = self.add_overlay_fixture_animation('combat rifle aim_still', overlay=True)
                    base = self.add_overlay_fixture_animation('combat rifle walk_front')
                    return [a.action_tracks[0].action for a in (source, base)], [source.name, base.name]

                def import_renames(*args):
                    if self.nwo.animations:
                        self.nwo.animations[0].animation_renames.add().name = 'combat pistol aim_still'

                tag.to_blender.side_effect = import_actions
                graph.generate_renames.side_effect = import_renames
                importer = SimpleNamespace(
                    import_info_sources_for_tag=lambda file: [], scene_nwo=self.nwo,
                    context=bpy.context, tags_dir='', tag_animation_filter='',
                    convert_animations=enabled, graph_import_ik_chains=False,
                    graph_import_animations=import_animations, corinth=False,
                    graph_scale_animations_to_skeleton=False, game=game,
                    target_game='reach', graph_generate_renames=True,
                    graph_import_events=False, register_control_rig_actions=MagicMock(),
                )
                with patch.object(importer_module.utils, 'TagImportMover'), \
                        patch.object(importer_module, 'AnimationGraphTag', return_value=graph), \
                        patch.object(importer_module, 'AnimationTag', return_value=tag), \
                        patch.object(legacy_turns, 'convert_reach_turn_poses', wraps=legacy_turns.convert_reach_turn_poses) as convert_turns:
                    actions, names = importer_module.NWOImporter.import_animation_graph(
                        importer, 'test.model_animation_graph', self.arm, None, return_animations=True)
                self.assertEqual(convert_turns.call_count, int(expected))
                self.assertEqual('combat rifle aim_walk_front' in names, expected)
                self.assertEqual(len(actions), (3 if expected else 2) if import_animations else 0)
                if expected:
                    generated = self.nwo.animations[-1]
                    self.assertEqual(generated.animation_renames[0].name, 'combat pistol aim_walk_front')
                    self.assertIn(generated.action_tracks[0].action, actions)
                importer.register_control_rig_actions.assert_called_once_with(self.arm, actions)

    def test_reverse_conversion_gating_and_source_file_bypass(self):
        for source, target, enabled, expected in (
                ('reach', 'halo2', True, True), ('reach', 'halo1', True, True),
                ('halo4', 'halo3', True, True), ('halo2a', 'halo3odst', True, True),
                ('reach', 'halo2', False, False), ('reach', 'reach', True, False),
                ('halo2', 'halo3', True, False)):
            with self.subTest(source=source, target=target, enabled=enabled):
                metadata = MagicMock(game=source)
                metadata.force_uncompressed_for_import.return_value = (0, False)
                metadata.__enter__.return_value = metadata
                graph = MagicMock()
                graph.to_blender.return_value = ([], [])
                graph.legacy_frame_maps = {}
                graph.__enter__.return_value = graph
                importer = SimpleNamespace(
                    import_info_sources_for_tag=lambda file: ['source.jmo'] if expected else [],
                    scene_nwo=self.nwo, context=bpy.context, tags_dir='', tag_animation_filter='',
                    convert_animations=enabled, graph_import_ik_chains=False, graph_import_animations=True,
                    corinth=False, graph_scale_animations_to_skeleton=False, game=source, target_game=target,
                    graph_generate_renames=False, graph_import_events=False, register_control_rig_actions=MagicMock(),
                )
                with patch.object(importer_module.utils, 'TagImportMover'), \
                        patch.object(importer_module, 'AnimationGraphTag', return_value=metadata), \
                        patch.object(importer_module, 'AnimationTag', return_value=graph):
                    importer_module.NWOImporter.import_animation_graph(importer, 'test.model_animation_graph', self.arm, None)
                self.assertEqual(graph.to_blender.call_args.kwargs['convert_to_legacy'], expected)
                self.assertFalse(graph.to_blender.call_args.kwargs['convert_to_reach'])
                self.assertEqual(graph.to_blender.call_args.kwargs['convert_animation_names'], enabled)

    def make_turn_aim_overlay(self, name='combat rifle aim_still_up'):
        animation = self.add_overlay_fixture_animation(name, overlay=True)
        animation.frame_end = 5
        # Frame 1 is the reference; the extreme pitch poses must not be selected.
        for frame, yaw, pitch, x in ((1, 1.6, 0, 99), (2, -1.4, -0.6, 99),
                                     (3, -0.7, 0, 3), (4, 0.9, 0, 4), (5, 1.4, 0.6, 99)):
            for bone in self.arm.pose.bones:
                bone.matrix_basis = Matrix.Identity(4)
                if bone.name == 'root':
                    bone.location.x = x
                    bone.rotation_quaternion = Quaternion((0, 1, 0), x / 10)
                elif bone.name == 'aim_yaw':
                    bone.rotation_quaternion = Quaternion((0, 0, 1), yaw)
                elif bone.name == 'aim_pitch':
                    bone.rotation_quaternion = Quaternion((0, 1, 0), pitch)
                bone.keyframe_insert('location', frame=frame)
                bone.keyframe_insert('rotation_quaternion', frame=frame)
        return animation

    def test_turn_pose_matches_directional_aim_and_keeps_movement_timing_events(self):
        prepare_reach_skeleton(self.arm)
        self.make_turn_aim_overlay()
        for direction in ('left', 'right'):
            for suffix in ('', '_fast', '_slow'):
                name = f'combat rifle turn_{direction}{suffix}'
                turn = self.add_overlay_fixture_animation(name)
                action = turn.action_tracks[0].action
                action.use_frame_range = True
                action.frame_start, action.frame_end = 1, 3
                event = turn.animation_events.add()
                event.frame_frame = 2
                for frame in range(1, 4):
                    self.arm.pose.bones['root'].location = (10 + frame, 0, 0)
                    self.arm.pose.bones['root'].rotation_quaternion = Quaternion((1, 0, 0), frame / 10)
                    pedestal = self.arm.pose.bones['pedestal']
                    pedestal.rotation_quaternion = Quaternion((0, 0, 1), frame / 5)
                    pedestal.location = (frame / 3, frame / 4, 0)
                    for bone in (self.arm.pose.bones['root'], pedestal):
                        bone.keyframe_insert('location', frame=frame)
                        bone.keyframe_insert('rotation_quaternion', frame=frame)
                    self.arm.location.x = frame / 8
                    self.arm.keyframe_insert('location', frame=frame)
        def movement_curves(action):
            curves, _ = _fcurve_map(action, self.arm)
            return {key: (curve.as_pointer(), [tuple(p.co) for p in curve.keyframe_points])
                    for key, curve in curves.items()
                    if key[0].startswith('pose.bones["pedestal"]') or key[0] == 'location'}
        before = {a.name: movement_curves(a.action_tracks[0].action) for a in self.nwo.animations[1:]}
        previous_action = self.arm.animation_data.action
        previous_frame = bpy.context.scene.frame_current
        converted = legacy_turns.convert_reach_turn_poses(self.nwo, self.arm, self.nwo.animations[:])
        self.assertEqual(set(converted), set(before))
        self.assertEqual(self.arm.animation_data.action, previous_action)
        self.assertEqual(bpy.context.scene.frame_current, previous_frame)
        for name in converted:
            with self.subTest(name=name):
                animation = self.nwo.animations[name]
                action = animation.action_tracks[0].action
                self.assertEqual(movement_curves(action), before[name])
                self.assertEqual((animation.frame_start, animation.frame_end, action.frame_start, action.frame_end), (1, 3, 1, 3))
                self.assertEqual(animation.animation_events[0].frame_frame, 2)
                x, yaw = (4, 0.9) if 'turn_left' in name else (3, -0.7)
                curves, _ = _fcurve_map(action, self.arm)
                for frame in range(1, 4):
                    self.assertAlmostEqual(curves[('pose.bones["root"].location', 0)].evaluate(frame), x+frame-1, places=4)
                    values = [curves[('pose.bones["root"].rotation_quaternion', i)].evaluate(frame) for i in range(4)]
                    expected = Quaternion((0, 1, 0), x/10) @ Quaternion((1, 0, 0), (frame-1)/10)
                    self.assertMatrix(Quaternion(values).to_matrix(), expected.to_matrix())
                    values = [curves[('pose.bones["aim_yaw"].rotation_quaternion', i)].evaluate(frame) for i in range(4)]
                    self.assertMatrix(Quaternion(values).to_matrix(), Quaternion((0, 0, 1), yaw).to_matrix())

    def test_converted_turn_overlay_uses_new_aim_reference_without_extra_offset(self):
        prepare_reach_skeleton(self.arm)
        self.make_turn_aim_overlay()
        self.add_overlay_fixture_animation('combat rifle turn_right')
        converted = legacy_turns.convert_reach_turn_poses(self.nwo, self.arm, self.nwo.animations[:])
        generated = generate_reach_aim_look_overlays(self.nwo, self.arm, self.nwo.animations[:], turns_with_aim_pose=converted)
        self.assertEqual([a.name for a in generated], ['combat rifle aim_turn_right_up'])
        action = generated[0].action_tracks[0].action
        curves, _ = _fcurve_map(action, self.arm)
        rest = {b.name: _rest_local_matrix(b) for b in self.arm.pose.bones}
        world = _world_matrices(self.arm, _sample_local_matrices(self.arm, curves, 1, rest))
        reference = world['pedestal'].inverted_safe() @ world['aim_yaw']
        self.assertMatrix(reference, Matrix.Rotation(-0.7, 4, 'Z'))

    def test_turn_pose_matching_and_missing_samples(self):
        prepare_reach_skeleton(self.arm)
        self.make_turn_aim_overlay('combat any aim_still_up')
        self.make_turn_aim_overlay('combat rifle aim_still_up')
        self.make_turn_aim_overlay('combat rifle pr aim_still_up')
        self.add_overlay_fixture_animation('combat rifle pr turn_right')
        name = utils.AnimationName('combat rifle pr turn_right')
        selected = legacy_turns._matching_aim_overlay(self.nwo.animations, self.arm, name)
        self.assertEqual(selected.name, 'combat rifle pr aim_still_up')
        # An aim screen outside this filtered import is not a dependency to mutate/use.
        self.assertEqual(legacy_turns.convert_reach_turn_poses(self.nwo, self.arm, self.nwo.animations[-1:]), [])
        # No yaw keys in the matching screen: do not invent a directional pose.
        track = self.nwo.animations[2].action_tracks[0]
        curves = utils.get_fcurves(track.action, track.action.slots[0])
        for curve in list(curves):
            if 'aim_yaw' in curve.data_path:
                curves.remove(curve)
        self.assertEqual(legacy_turns.convert_reach_turn_poses(self.nwo, self.arm, self.nwo.animations[:]), [])


if __name__ == '__main__':
    unittest.main(argv=['test_legacy_animation_import_blender'])
