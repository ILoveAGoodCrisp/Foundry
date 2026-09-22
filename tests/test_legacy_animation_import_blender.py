"""Run with Blender --background --factory-startup --python this_file."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import addon_utils
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blender/addons'))
sys.path.extend(str(p) for p in (ROOT / 'blender/addons/io_scene_foundry/wheels').glob('*none-any.whl'))
import io_scene_foundry
io_scene_foundry.startup.load_projects = lambda: None
addon_utils.enable('io_scene_foundry', default_set=True, persistent=False)

from io_scene_foundry import import_transform, utils
from io_scene_foundry.legacy.jma import Node
from io_scene_foundry.managed_blam.animation import AnimationTag, AnimationType
from io_scene_foundry.tags.animation_resource import FrameInfoType
from io_scene_foundry.tags.animation_graph import AnimationBlendScreen
from io_scene_foundry.tools.animation.legacy_import import prepare_reach_skeleton, convert_blend_screen
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
        root, pedestal = Node('root'), Node(names['pedestal'])
        tag._reach_pedestal_node = pedestal
        tag._reach_pedestal_rest = self.arm.data.bones[names['pedestal']].matrix_local.copy()
        tag._reach_unmoved_roots = {}
        turn = Quaternion((0, 0, 1), 0.3)
        pose = {
            'frames': [[(0, 0, 1, 0, 0, 0, 1, 1)]] * 3,
            'movement': [(0.2, 0.1, 0, turn.x, turn.y, turn.z, turn.w)] * 3,
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

    def test_skeletal_motion_is_preserved_with_and_without_movement(self):
        names = prepare_reach_skeleton(self.arm)
        self.arm.data.bones['root'].name = 'b_root'
        tag = object.__new__(AnimationTag)
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
            tag._tag = SimpleNamespace(animation_pose=lambda *args: {'frames': frames, 'movement': movement})
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
                self.assertIn('graph_convert_to_reach', layout.properties)

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


if __name__ == '__main__':
    unittest.main(argv=['test_legacy_animation_import_blender'])
