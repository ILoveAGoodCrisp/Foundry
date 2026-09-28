"""Run with Blender --background --factory-startup --python-exit-code 1 --python this_file."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

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
from io_scene_foundry.tools.animation.legacy_import import generate_reach_aim_look_overlays
from io_scene_foundry.tools.animation.generate_aim_look_overlays import _fcurve_map, _sample_local_matrices, _rest_local_matrix
from io_scene_foundry.tools.animation.composites import CompositeXML

props.register()
utils.get_project = lambda *args, **kwargs: SimpleNamespace(game='halo4', corinth=True)


class LocomoteTests(unittest.TestCase):
    def setUp(self):
        self.scene = bpy.context.scene.nwo
        self.scene.animations.clear()
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        data = bpy.data.armatures.new('test')
        self.arm = bpy.data.objects.new('test', data)
        bpy.context.collection.objects.link(self.arm)
        bpy.context.view_layer.objects.active = self.arm
        self.arm.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        for name, parent in [('pedestal', None), ('pelvis', 'pedestal'), ('l_thigh', 'pelvis'),
                             ('l_foot', 'l_thigh'), ('spine', 'pelvis'),
                             ('aim_yaw', 'pedestal'), ('aim_pitch', 'pedestal')]:
            bone = data.edit_bones.new(name)
            bone.tail = (0, 1, 0)
            if parent:
                bone.parent = data.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in self.arm.pose.bones:
            bone.rotation_mode = 'QUATERNION'
        self.scene.node_usage_pedestal = 'pedestal'
        self.scene.node_usage_pelvis = 'pelvis'
        self.scene.node_usage_left_foot = 'l_foot'
        self.scene.node_usage_pose_blend_yaw = 'aim_yaw'
        self.scene.node_usage_pose_blend_pitch = 'aim_pitch'
        self.scene.scale = 'max'
        bpy.context.scene.render.fps = 30
        bpy.context.scene.render.fps_base = 1

    def animation(self, state, delta=(0, 0, 0), end=11, overlay=False, scope='combat rifle', leg=0):
        action = bpy.data.actions.new(f'{scope} {state}')
        self.arm.animation_data_create()
        self.arm.animation_data.action = action
        for frame, factor in [(1, 0), (end, 1)]:
            for bone in self.arm.pose.bones:
                bone.location = tuple(v * factor for v in delta) if bone.name == 'pedestal' else (0, 0, leg * factor if bone.name == 'l_thigh' else 0)
                bone.keyframe_insert('location', frame=frame)
        for curve in utils.get_fcurves(action, self.arm):
            for point in curve.keyframe_points:
                point.interpolation = 'LINEAR'
        animation = self.scene.animations.add()
        animation.name = animation.name_old = f'{scope} {state}'
        animation.animation_type = 'overlay' if overlay else 'base'
        animation.pose_overlay = overlay
        animation.frame_start, animation.frame_end = 1, end
        animation.animation_movement_data = 'xy'
        track = animation.action_tracks.add()
        track.object, track.action = self.arm, action
        return animation

    def test_names(self):
        self.assertEqual(locomote.locomote_name('combat:rifle:move_front:var2'), 'combat rifle locomote_run_front var2')
        self.assertEqual(locomote.locomote_name('combat rifle aim_walk_left_up'), 'combat rifle aim_locomote_walk_left_up')
        for name in ('warthog_d move_front', 'combat rifle turn_left', 'combat rifle idle 2 crouch idle'):
            self.assertEqual(locomote.locomote_name(name), name)

    def test_composites_diagonals_and_export(self):
        self.animation('idle')
        self.animation('aim_still_up', overlay=True)
        for direction, delta in [('front', (10, 0, 0)), ('left', (0, 10, 0)), ('back', (-10, 0, 0)), ('right', (0, -10, 0))]:
            self.animation('move_' + direction, delta, leg=2 if direction == 'left' else 0)
            self.animation('aim_move_' + direction + '_up', overlay=True)
        self.animation('turn_left')
        generated = locomote.convert_locomotion(self.scene, self.arm, 0)
        self.assertEqual(len(generated), 6)
        composite = self.scene.animations['combat rifle locomote']
        self.assertEqual(composite.animation_type, 'composite')
        leaves = composite.blend_axis[1].phase_sets[0].leaves
        self.assertEqual(len(leaves), 9)
        self.assertEqual({leaf.blend_axis_1 for leaf in leaves}, set(locomote.ANGLES.values()))
        self.assertAlmostEqual(max(leaf.blend_axis_0 for leaf in leaves), .3, places=5)
        aim = self.scene.animations['combat rifle aim_locomote_up']
        self.assertEqual(len(aim.blend_axis[1].phase_sets[0].leaves), 5)
        diagonal = self.scene.animations['combat rifle locomote_run_frontleft']
        curves, _ = _fcurve_map(diagonal.action_tracks[0].action, self.arm)
        rest = {bone.name: _rest_local_matrix(bone) for bone in self.arm.pose.bones}
        pose = _sample_local_matrices(self.arm, curves, 11, rest)
        self.assertAlmostEqual(pose['pedestal'].translation.x, 10 / 2 ** .5, places=5)
        self.assertAlmostEqual(pose['pedestal'].translation.y, 10 / 2 ** .5, places=5)
        self.assertAlmostEqual(pose['l_thigh'].translation.z, 1)
        self.assertEqual(pose['spine'].translation.z, 0)
        self.assertFalse(any('turn' in item.name and item.animation_type == 'composite' for item in self.scene.animations))
        xml = CompositeXML(composite)
        parent = ET.Element('composite')
        xml.write_blend_axis_entry(composite.blend_axis[1], parent,
                                   [composite.blend_axis[0], composite.blend_axis[1]])
        self.assertEqual(len(parent.findall('.//leaf')), 9)
        self.assertEqual(locomote.convert_locomotion(self.scene, self.arm, 0), [])

    def test_missing_directions_scope_and_authored(self):
        self.animation('move_front', (10, 0, 0), scope='combat pistol')
        start = len(self.scene.animations)
        self.animation('move_front', (10, 0, 0))
        self.animation('move_left', (0, 10, 0))
        authored = self.animation('locomote_run_frontleft', (7, 7, 0)).action_tracks[0].action
        locomote.convert_locomotion(self.scene, self.arm, start)
        self.assertIs(self.scene.animations['combat rifle locomote_run_frontleft'].action_tracks[0].action, authored)
        self.assertIn('combat pistol move_front', self.scene.animations)
        self.assertNotIn('combat rifle locomote_run_backleft', self.scene.animations)

    def test_move_overlay_preferred(self):
        self.animation('aim_still_up', overlay=True)
        self.animation('aim_move_up', overlay=True)
        self.animation('move_front', (10, 0, 0))
        calls = []
        def generate(scene, source, armature, bases, **kwargs):
            calls.append((source.name, [state for state, _ in bases]))
            return [], 0, []
        with patch('io_scene_foundry.tools.animation.generate_aim_look_overlays.generate_aim_look_overlays', generate):
            generate_reach_aim_look_overlays(self.scene, self.arm, list(self.scene.animations), prefer_move=True)
        self.assertEqual(calls[0], ('combat rifle aim_move_up', ['move_front']))
        calls.clear()
        with patch('io_scene_foundry.tools.animation.generate_aim_look_overlays.generate_aim_look_overlays', generate):
            generate_reach_aim_look_overlays(self.scene, self.arm, list(self.scene.animations))
        self.assertEqual(calls, [('combat rifle aim_still_up', ['move_front'])])

    def test_actual_overlay_generation(self):
        self.animation('aim_still_up', overlay=True)
        source = self.animation('aim_move_up', overlay=True)
        source.animation_events.add().frame_frame = 4
        self.animation('move_front', (10, 0, 0))
        generated = generate_reach_aim_look_overlays(
            self.scene, self.arm, list(self.scene.animations), prefer_move=True)
        self.assertEqual([item.name for item in generated], ['combat rifle aim_move_front_up'])
        self.assertTrue(generated[0].pose_overlay)
        self.assertEqual(generate_reach_aim_look_overlays(
            self.scene, self.arm, list(self.scene.animations), prefer_move=True), [])
        locomote.convert_locomotion(self.scene, self.arm, 0)
        self.assertIn('combat rifle aim_locomote_up', self.scene.animations)

    def test_blender_scale_and_h2amp(self):
        with patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo2a', corinth=True)):
            self.scene.scale = 'blender'
            self.animation('move_front', (.3048, 0, 0))
            self.animation('move_left', (0, .3048, 0))
            locomote.convert_locomotion(self.scene, self.arm, 0)
            composite = self.scene.animations['combat rifle locomote']
            self.assertAlmostEqual(composite.blend_axis[0].animation_source_bounds[1], .3, places=5)

    def test_different_durations_and_footfall_alignment(self):
        first = self.animation('move_front', (10, 0, 0))
        event = first.animation_events.add()
        event.event_type = '_connected_geometry_animation_event_type_frame'
        event.frame_name, event.frame_frame = 'left foot', 1
        second = self.animation('move_left', (0, 20, 0), end=21, leg=4)
        event = second.animation_events.add()
        event.event_type = '_connected_geometry_animation_event_type_frame'
        event.frame_name, event.frame_frame = 'left foot', 11
        locomote.convert_locomotion(self.scene, self.arm, 0)
        diagonal = self.scene.animations['combat rifle locomote_run_frontleft']
        self.assertEqual(diagonal.frame_end, 11)
        self.assertEqual(diagonal.animation_events[0].frame_frame, 1)
        curves, _ = _fcurve_map(diagonal.action_tracks[0].action, self.arm)
        rest = {bone.name: _rest_local_matrix(bone) for bone in self.arm.pose.bones}
        pose = _sample_local_matrices(self.arm, curves, 1, rest)
        self.assertAlmostEqual(pose['l_thigh'].translation.z, 1)
        self.assertAlmostEqual(locomote._speed(diagonal, self.arm, self.scene), .3, places=5)


unittest.main(argv=[sys.argv[0]])
