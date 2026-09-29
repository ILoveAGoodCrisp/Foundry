"""Run with Blender --background --factory-startup --python-exit-code 1 --python this_file."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import bpy

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as archive:
        archive.extractall(wheels.name)
sys.path.insert(0, wheels.name)
from io_scene_foundry import props, utils
from io_scene_foundry.tools.animation import locomote_import as locomote

props.register()
utils.get_project = lambda *args, **kwargs: SimpleNamespace(game='halo4', corinth=True)


class StationaryTests(unittest.TestCase):
    def setUp(self):
        toggle = patch.object(locomote, 'DEBUG_LOCOMOTE_USE_PHASE_SETS', True)
        toggle.start()
        self.addCleanup(toggle.stop)
        self.scene = bpy.context.scene.nwo
        self.scene.animations.clear()
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        self.arm = bpy.data.objects.new('test', bpy.data.armatures.new('test'))
        bpy.context.collection.objects.link(self.arm)
        bpy.context.view_layer.objects.active = self.arm
        self.arm.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        for name, parent in [('pedestal', None), ('pelvis', 'pedestal')]:
            bone = self.arm.data.edit_bones.new(name)
            bone.head, bone.tail = (0, 0, 0), (0, 0, 1)
            if parent:
                bone.parent = self.arm.data.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')

    def animation(self, state, travel, hip):
        action = bpy.data.actions.new(state)
        self.arm.animation_data_create()
        self.arm.animation_data.action = action
        for frame, factor in [(1, 0), (3, 1), (5, 0)]:
            self.arm.pose.bones['pedestal'].location = (travel * (frame - 1), 0, 0)
            self.arm.pose.bones['pedestal'].keyframe_insert('location', frame=frame)
            self.arm.pose.bones['pelvis'].location = (0, 0, hip * factor)
            self.arm.pose.bones['pelvis'].keyframe_insert('location', frame=frame)
        item = self.scene.animations.add()
        item.name = item.name_old = 'combat rifle ' + state
        item.animation_type = 'base'
        item.frame_start, item.frame_end = 1, 5
        item.animation_movement_data = 'xy'
        track = item.action_tracks.add()
        track.object, track.action = self.arm, action
        for key in ('left foot', 'right foot'):
            event = item.animation_events.add()
            event.event_type = '_connected_geometry_animation_event_type_frame'
            event.frame_name, event.frame_frame = key, 3
        return item

    def test_slowest_forward_copy_preserves_gait_and_source(self):
        self.animation('idle', 0, 99)
        self.animation('move_front', 3, 1)
        self.animation('walk_front', 2, 2)
        slow = self.animation('walkslow_front', 1, 3)
        source_action = slow.action_tracks[0].action
        locomote.convert_locomotion(self.scene, self.arm, 0)
        stationary = self.scene.animations['combat rifle locomote_inplace_front']
        self.assertIsNot(stationary.action_tracks[0].action, source_action)
        self.assertEqual(stationary.animation_movement_data, 'none')
        self.assertEqual(len(stationary.animation_events), 2)
        source_curves, _ = locomote._fcurve_map(source_action, self.arm)
        curves, _ = locomote._fcurve_map(stationary.action_tracks[0].action, self.arm)
        rest = {b.name: locomote._rest_local_matrix(b) for b in self.arm.pose.bones}
        for frame in range(1, 6):
            original = locomote._sample_local_matrices(self.arm, source_curves, frame, rest)
            copied = locomote._sample_local_matrices(self.arm, curves, frame, rest)
            self.assertAlmostEqual(copied['pedestal'].translation.length, 0)
            self.assertAlmostEqual((copied['pelvis'].translation - original['pelvis'].translation).length, 0)
        self.assertGreater(locomote._sample_local_matrices(self.arm, source_curves, 5, rest)['pedestal'].translation.x, 0)
        composite = self.scene.animations['combat rifle locomote']
        phase = composite.blend_axis[0].phase_sets[0]
        self.assertTrue(phase.key_left_foot and phase.key_right_foot)
        self.assertEqual({leaf.animation for leaf in phase.leaves if leaf.blend_axis_0 == 0}, {stationary.name})
        self.assertFalse(any('idle' in leaf.animation for leaf in phase.leaves))
        self.assertEqual(locomote.convert_locomotion(self.scene, self.arm, 0), [])

    def test_directional_base_and_aim_use_stationary_gait_in_phase_sets(self):
        for direction in ('front', 'left'):
            self.animation('walk_' + direction, 2, 2 if direction == 'front' else 7)
            aim = self.animation('aim_walk_' + direction + '_up', 0, 4 if direction == 'front' else 9)
            aim.animation_type, aim.pose_overlay = 'overlay', True
        self.animation('idle', 0, 99)
        locomote.convert_locomotion(self.scene, self.arm, 0)
        for state, stationary in [('locomote', 'locomote_inplace'),
                                  ('aim_locomote_up', 'aim_locomote_inplace_up')]:
            composite = self.scene.animations['combat rifle ' + state]
            self.assertEqual([axis.name for axis in composite.blend_axis], ['movement_angles', 'movement_speed'])
            axis = composite.blend_axis[1]
            self.assertEqual(len(axis.leaves), 0)
            phase = axis.phase_sets[0]
            zero = [leaf for leaf in phase.leaves if leaf.blend_axis_1 == 0]
            self.assertEqual({leaf.blend_axis_0 for leaf in zero},
                             {leaf.blend_axis_0 for leaf in phase.leaves if leaf.blend_axis_1 > 0})
            self.assertEqual(len({leaf.animation for leaf in zero}), len(zero))
            coordinates = [(leaf.blend_axis_0 % 360, leaf.blend_axis_1) for leaf in phase.leaves]
            self.assertEqual(coordinates, sorted(coordinates))
            rest = {bone.name: locomote._rest_local_matrix(bone) for bone in self.arm.pose.bones}
            for leaf in zero:
                moving = min((other for other in phase.leaves if other.blend_axis_0 == leaf.blend_axis_0
                              and other.blend_axis_1 > 0), key=lambda other: other.blend_axis_1)
                source_action = self.scene.animations[moving.animation].action_tracks[0].action
                copied_action = self.scene.animations[leaf.animation].action_tracks[0].action
                self.assertIsNot(copied_action, source_action)
                source_curves, _ = locomote._fcurve_map(source_action, self.arm)
                copied_curves, _ = locomote._fcurve_map(copied_action, self.arm)
                for frame in range(1, 6):
                    source_pose = locomote._sample_local_matrices(self.arm, source_curves, frame, rest)
                    copied_pose = locomote._sample_local_matrices(self.arm, copied_curves, frame, rest)
                    self.assertAlmostEqual(copied_pose['pedestal'].translation.length, 0)
                    self.assertAlmostEqual((copied_pose['pelvis'].translation - source_pose['pelvis'].translation).length, 0)
            self.assertTrue(all(leaf.manual_blend_axis_0 and leaf.manual_blend_axis_1 for leaf in phase.leaves))

    def test_frontslow_alias_and_no_forward_does_not_fall_back_to_idle(self):
        self.assertEqual(locomote.locomote_name('combat rifle walk_frontslow'),
                         'combat rifle locomote_walkslow_front')
        self.animation('idle', 0, 99)
        self.animation('walk_left', 1, 2)
        locomote.convert_locomotion(self.scene, self.arm, 0)
        phase = self.scene.animations['combat rifle locomote'].blend_axis[0].phase_sets[0]
        self.assertEqual({leaf.animation for leaf in phase.leaves if leaf.blend_axis_0 == 0},
                         {'combat rifle locomote_inplace_left'})

    def test_toggle_preserves_coordinates_and_order_for_base_and_aim(self):
        leaves = [('combat rifle locomote_inplace_front', 0, 'front'),
                  ('combat rifle locomote_walk_front', .5, 'front'),
                  ('combat rifle locomote_inplace_left', 0, 'left'),
                  ('combat rifle locomote_walk_left', .5, 'left')]
        for overlay in (False, True):
            results = []
            for enabled in (False, True):
                with patch.object(locomote, 'DEBUG_LOCOMOTE_USE_PHASE_SETS', enabled):
                    name = locomote._composite(self.scene,
                        f'combat rifle {"aim_locomote_up" if overlay else "locomote"} var{int(enabled)}',
                        leaves, overlay=overlay)
                axis = self.scene.animations[name].blend_axis[-1]
                self.assertEqual(len(axis.phase_sets), int(enabled))
                sources = axis.phase_sets[0].leaves if enabled else axis.leaves
                results.append([(leaf.animation, leaf.blend_axis_0, leaf.blend_axis_1,
                                 leaf.manual_blend_axis_0, leaf.manual_blend_axis_1) for leaf in sources])
            self.assertEqual(results[0], results[1])


unittest.main(argv=[sys.argv[0]])
