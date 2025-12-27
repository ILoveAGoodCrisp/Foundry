

'''Operators for validating and fixing rig issues'''

import bpy
import math
from mathutils import Matrix
from ...tools.rigging import HaloRig
from ... import utils
import random

class NWO_ValidateRig(bpy.types.Operator):
    bl_idname = 'nwo.validate_rig'
    bl_label = 'Validate Rig'
    bl_description = 'Runs a number of checks on the model armature, highlighting issues and providing fixes'
    
    def get_root_bone(self, rig):
        root_bones = [b for b in rig.data.bones if b.use_deform and not b.parent]
        if root_bones:
            if len(root_bones) > 1:
                utils.get_scene_props().multiple_root_bones = True
                return
            return root_bones[0].name
    
    def validate_root_rot(self, rig, root_bone_name):
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        # Valid rotation depends on model forward direction
        # Given false tuples hightlight whether tail values should be zero = (x, y, z)
        # x_postive = (0, 1, 0)
        # y_postive = (-1, 0, 0)
        # x_negative = (0, -1, 0)
        # y_postive = (1, 0, 0)
        edit_root = rig.data.edit_bones.get(root_bone_name)
        match utils.get_scene_props().forward_direction:
            case 'x':
                tail_okay = (
                math.isclose(edit_root.tail[0], 0, abs_tol=1e-5) and
                edit_root.tail[1] > 0 and
                math.isclose(edit_root.tail[2], 0, abs_tol=1e-5))
            case 'x-':
                tail_okay = (
                math.isclose(edit_root.tail[0], 0, abs_tol=1e-5) and
                edit_root.tail[1] < 0 and
                math.isclose(edit_root.tail[2], 0, abs_tol=1e-5))
            case 'y':
                tail_okay = (
                edit_root.tail[0] < 0 and
                math.isclose(edit_root.tail[1], 0, abs_tol=1e-5) and
                math.isclose(edit_root.tail[2], 0, abs_tol=1e-5))
            case 'y-':
                tail_okay = (
                edit_root.tail[0] > 0 and
                math.isclose(edit_root.tail[1], 0, abs_tol=1e-5) and
                math.isclose(edit_root.tail[2], 0, abs_tol=1e-5))
                
        head_okay = math.isclose(edit_root.head[0], 0, abs_tol=1e-5) and math.isclose(edit_root.head[1], 0, abs_tol=1e-5) and math.isclose(edit_root.head[2], 0, abs_tol=1e-5)
        roll_okay = math.isclose(edit_root.roll, 0, abs_tol=1e-5)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        return tail_okay and head_okay and roll_okay
    
    def validate_pose_bones_transforms(self, scene_nwo):
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        edit_bones = self.rig.data.edit_bones
        pedestal: bpy.types.EditBone = edit_bones.get(scene_nwo.node_usage_pedestal)
        aim_yaw: bpy.types.EditBone = edit_bones.get(scene_nwo.node_usage_pose_blend_pitch)
        aim_pitch: bpy.types.EditBone = edit_bones.get(scene_nwo.node_usage_pose_blend_yaw)
        validated = pedestal.matrix == aim_pitch.matrix == aim_yaw.matrix
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        return validated
    
    def armature_transforms_valid(self, rig):
        return rig.matrix_world == Matrix.Identity(4)
            
    def complete_validation(self):
        if self.rig_was_unselectable:
            self.rig.hide_select = True
        if self.rig_was_hidden:
            self.rig.hide_set(True)
        if self.old_active:
            utils.set_active_object(self.old_active)
        if self.old_mode:
            if self.old_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
            elif self.old_mode.startswith('EDIT'):
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                
        return {'FINISHED'}
    
    def valid_message(self):
        options = [
            "Rig valid!",
            "Rig validated",
            "Rig is good",
            "Rig is ready for export",
            "Tool is gonna love this rig",
            "You are valid and your rig is valid",
        ]
        return random.choice(options)
    
    def too_many_bones(self, rig):
        bones = rig.data.bones
        return len(bones) > 253
    
    def bone_names_too_long(self):
        bones = self.rig.data.bones
        bones_with_long_names = [b.name for b in bones if len(b.name) > 31]
        for b in bones_with_long_names:
            self.report({'WARNING'}, b)
        return bool(bones_with_long_names)
        
    
    def strip_null_rig_refs(self, scene_nwo, rig):
        bone_names = [b.name for b in rig.data.bones]
        if rig.nwo.control_aim and rig.nwo.control_aim not in bone_names:
            rig.nwo.control_aim = ""
        if scene_nwo.node_usage_pedestal and scene_nwo.node_usage_pedestal not in bone_names:
            scene_nwo.node_usage_pedestal = ""
        if scene_nwo.node_usage_pose_blend_pitch and scene_nwo.node_usage_pose_blend_pitch not in bone_names:
            scene_nwo.node_usage_pose_blend_pitch = ""
        if scene_nwo.node_usage_pose_blend_yaw and scene_nwo.node_usage_pose_blend_yaw not in bone_names:
            scene_nwo.node_usage_pose_blend_yaw = ""
        if scene_nwo.node_usage_physics_control and scene_nwo.node_usage_physics_control not in bone_names:
            scene_nwo.node_usage_physics_control = ""
        if scene_nwo.node_usage_camera_control and scene_nwo.node_usage_camera_control not in bone_names:
            scene_nwo.node_usage_camera_control = ""
        if scene_nwo.node_usage_origin_marker and scene_nwo.node_usage_origin_marker not in bone_names:
            scene_nwo.node_usage_origin_marker = ""
        if scene_nwo.node_usage_weapon_ik and scene_nwo.node_usage_weapon_ik not in bone_names:
            scene_nwo.node_usage_weapon_ik = ""
        if scene_nwo.node_usage_pelvis and scene_nwo.node_usage_pelvis not in bone_names:
            scene_nwo.node_usage_pelvis = ""
        if scene_nwo.node_usage_left_clavicle and scene_nwo.node_usage_left_clavicle not in bone_names:
            scene_nwo.node_usage_left_clavicle = ""
        if scene_nwo.node_usage_left_clavicle and scene_nwo.node_usage_left_clavicle not in bone_names:
            scene_nwo.node_usage_left_clavicle = ""
        if scene_nwo.node_usage_left_upperarm and scene_nwo.node_usage_left_upperarm not in bone_names:
            scene_nwo.node_usage_left_upperarm = ""
        if scene_nwo.node_usage_left_foot and scene_nwo.node_usage_left_foot not in bone_names:
            scene_nwo.node_usage_left_foot = ""
        if scene_nwo.node_usage_left_hand and scene_nwo.node_usage_left_hand not in bone_names:
            scene_nwo.node_usage_left_hand = ""
        if scene_nwo.node_usage_right_foot and scene_nwo.node_usage_right_foot not in bone_names:
            scene_nwo.node_usage_right_foot = ""
        if scene_nwo.node_usage_right_hand and scene_nwo.node_usage_right_hand not in bone_names:
            scene_nwo.node_usage_right_hand = ""
        if scene_nwo.node_usage_damage_root_gut and scene_nwo.node_usage_damage_root_gut not in bone_names:
            scene_nwo.node_usage_damage_root_gut = ""
        if scene_nwo.node_usage_damage_root_chest and scene_nwo.node_usage_damage_root_chest not in bone_names:
            scene_nwo.node_usage_damage_root_chest = ""
        if scene_nwo.node_usage_damage_root_head and scene_nwo.node_usage_damage_root_head not in bone_names:
            scene_nwo.node_usage_damage_root_head = ""
        if scene_nwo.node_usage_damage_root_left_shoulder and scene_nwo.node_usage_damage_root_left_shoulder not in bone_names:
            scene_nwo.node_usage_damage_root_left_shoulder = ""
        if scene_nwo.node_usage_damage_root_left_arm and scene_nwo.node_usage_damage_root_left_arm not in bone_names:
            scene_nwo.node_usage_damage_root_left_arm = ""
        if scene_nwo.node_usage_damage_root_left_leg and scene_nwo.node_usage_damage_root_left_leg not in bone_names:
            scene_nwo.node_usage_damage_root_left_leg = ""
        if scene_nwo.node_usage_damage_root_left_foot and scene_nwo.node_usage_damage_root_left_foot not in bone_names:
            scene_nwo.node_usage_damage_root_left_foot = ""
        if scene_nwo.node_usage_damage_root_right_shoulder and scene_nwo.node_usage_damage_root_right_shoulder not in bone_names:
            scene_nwo.node_usage_damage_root_right_shoulder = ""
        if scene_nwo.node_usage_damage_root_right_arm and scene_nwo.node_usage_damage_root_right_arm not in bone_names:
            scene_nwo.node_usage_damage_root_right_arm = ""
        if scene_nwo.node_usage_damage_root_right_leg and scene_nwo.node_usage_damage_root_right_leg not in bone_names:
            scene_nwo.node_usage_damage_root_right_leg = ""
        if scene_nwo.node_usage_damage_root_right_foot and scene_nwo.node_usage_damage_root_right_foot not in bone_names:
            scene_nwo.node_usage_damage_root_right_foot = ""
            
    def execute(self, context):
        # NOTE 2024-10-01 No longer requiring specific root transforms for root bone or armature as this is managed with the new granny pipeline
        self.old_mode = context.mode
        self.old_active = context.object
        self.rig_was_unselectable = False
        self.rig_was_hidden = False
        utils.set_object_mode(context)
        scene = context.scene
        scene_nwo = utils.get_scene_props()
        self.rig = utils.get_rig(context, True)
        multi_rigs = type(self.rig) == list
        no_rig = self.rig is None

        scene_nwo.multiple_root_bones = False
        scene_nwo.invalid_root_bone = False
        # scene_nwo.needs_pose_bones = False
        scene_nwo.armature_bad_transforms = False
        scene_nwo.armature_has_parent = False
        scene_nwo.too_many_bones = False
        scene_nwo.bone_names_too_long = False
        scene_nwo.pose_bones_bad_transforms = False

        if no_rig or multi_rigs:
            if multi_rigs:
                self.report({'WARNING'}, 'Multiple armatures in scene. Please declare the main armature in the Asset Editor')
            else:
                self.report({'INFO'}, "No Armature in scene. Armature only required if you want this model to animate")
                scene_nwo.multiple_root_bones = False
                scene_nwo.invalid_root_bone = False
                # scene_nwo.needs_pose_bones = False
                scene_nwo.armature_bad_transforms = False
                scene_nwo.armature_has_parent = False
                scene_nwo.too_many_bones = False
                scene_nwo.bone_names_too_long = False
                scene_nwo.pose_bones_bad_transforms = False
                
            return self.complete_validation()
        
        self.strip_null_rig_refs(scene_nwo, self.rig)
        
        if self.rig.parent:
            scene_nwo.armature_has_parent = True
            self.report({'WARNING'}, 'Armature is parented')
        else:
            scene_nwo.armature_has_parent = False
        
        # if self.armature_transforms_valid(self.rig):
        #     scene_nwo.armature_bad_transforms = False
        # else:
        #     scene_nwo.armature_bad_transforms = True
        #     self.report({'WARNING'}, 'Rig has bad transforms')
        
        self.rig_was_unselectable = self.rig.hide_select
        self.rig_was_hidden = self.rig.hide_get()
        utils.set_active_object(self.rig)
        
        if self.rig.data.library:
            self.report({'INFO'}, f"{self.rig} is linked from another scene, further validation cancelled")
            return self.complete_validation()
        
        root_bone_name = self.get_root_bone(self.rig)
        if root_bone_name is None:
            if utils.get_scene_props().multiple_root_bones:
                self.report({'WARNING'}, 'Multiple root bones in armature. Export will fail. Ensure only one bone in the armature has no parent (or set additional root bones as non-deform bones)')
            else:
                self.report({'WARNING'}, f'Root bone of {self.rig.name} is marked non-deform. This rig will not export')
            return self.complete_validation()
        else:
            scene_nwo.multiple_root_bones = False
        
        
        if self.validate_root_rot(self.rig, root_bone_name):
            scene_nwo.invalid_root_bone = False
        else:
            self.report({'WARNING'}, f'Root bone [{root_bone_name}] has non-standard transforms. This may cause issues at export')
            scene_nwo.invalid_root_bone = True
            
        # if self.needs_pose_bones(scene_nwo):
        #     scene_nwo.needs_pose_bones = True
        #     self.report({'WARNING'}, 'Found pose overlay animations, but this rig has no aim bones')
        # else:
        #     scene_nwo.needs_pose_bones = False
            
        if scene_nwo.node_usage_pedestal and scene_nwo.node_usage_pose_blend_pitch and scene_nwo.node_usage_pose_blend_yaw:
            if self.validate_pose_bones_transforms(scene_nwo):
                scene_nwo.pose_bones_bad_transforms = False
            else:
                self.report({'WARNING'}, f"{scene_nwo.node_usage_pose_blend_pitch} & {scene_nwo.node_usage_pose_blend_yaw} bones have bad transforms. Pose overlays will not export correctly")
                scene_nwo.pose_bones_bad_transforms = True
            
        if self.too_many_bones(self.rig):
            scene_nwo.too_many_bones = True
            self.report({'WARNING'}, "Rig has more than 253 bones")
        else:
            scene_nwo.too_many_bones = False
            
        if self.bone_names_too_long():
            scene_nwo.bone_names_too_long = True
            self.report({'WARNING'}, "Rig has bone names that exceed 31 characters. These names will be cut to 31 chars at export")
        else:
            scene_nwo.bone_names_too_long = False
            
        if not (scene_nwo.multiple_root_bones or
                scene_nwo.invalid_root_bone or
                # scene_nwo.needs_pose_bones or
                scene_nwo.armature_bad_transforms or
                scene_nwo.armature_has_parent or
                scene_nwo.too_many_bones or
                scene_nwo.bone_names_too_long or
                scene_nwo.pose_bones_bad_transforms):
            self.report({'INFO'}, self.valid_message())
        
        return self.complete_validation()

class NWO_FixPoseBones(bpy.types.Operator):
    bl_idname = 'nwo.fix_pose_bones'
    bl_label = ''
    bl_description = 'Fixes the pose bone transform by making them match the pedestal bone'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        rig = utils.get_rig(context)
        self.old_mode = context.mode
        self.old_active = context.object
        utils.set_object_mode(context)
        utils.set_active_object(rig)
        scene_nwo = utils.get_scene_props()
        if not scene_nwo.node_usage_pedestal:
            self.report({'WARNING'}, "Cannot fix as pedestal bone is not set in the Asset Editor panel")
            return {'CANCELLED'}
        if not scene_nwo.node_usage_pose_blend_pitch:
            self.report({'WARNING'}, "Cannot fix as pitch bone is not set in the Asset Editor panel")
            return {'CANCELLED'}
        if not scene_nwo.node_usage_pose_blend_yaw:
            self.report({'WARNING'}, "Cannot fix as yaw bone is not set in the Asset Editor panel")
            return {'CANCELLED'} 
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_bones = rig.data.edit_bones
        edit_pedestal_matrix = edit_bones.get(scene_nwo.node_usage_pedestal).matrix
        edit_bones.get(scene_nwo.node_usage_pose_blend_pitch).matrix = edit_pedestal_matrix
        edit_bones.get(scene_nwo.node_usage_pose_blend_yaw).matrix = edit_pedestal_matrix
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        if self.old_active:
            utils.set_active_object(self.old_active)
        if self.old_mode:
            if self.old_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
            elif self.old_mode.startswith('EDIT'):
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        scene_nwo.pose_bones_bad_transforms = False
        return {'FINISHED'} 

class NWO_FixRootBone(bpy.types.Operator):
    bl_idname = 'nwo.fix_root_bone'
    bl_label = 'Fix Root Bones'
    bl_description = 'Sets the root bone to have transforms expected by Halo'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        arm = utils.get_rig(context)
        root_bones = [b for b in arm.data.bones if b.use_deform and not b.parent]
        if len(root_bones) > 1:
            return {'CANCELLED'}
        root_bone_name = root_bones[0].name
        self.old_mode = context.mode
        self.old_active = context.object
        utils.set_object_mode(context)
        utils.set_active_object(arm)
        scene_nwo = utils.get_scene_props()
        tail_size = 1 if scene_nwo.scale == 'blender' else (1 / 0.03048)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_root = arm.data.edit_bones.get(root_bone_name)
        match scene_nwo.forward_direction:
            case 'x':
                edit_root.tail[0] = 0
                edit_root.tail[1] = tail_size
                edit_root.tail[2] = 0
            case 'x-':
                edit_root.tail[0] = 0
                edit_root.tail[1] = -tail_size
                edit_root.tail[2] = 0
            case 'y':
                edit_root.tail[0] = -tail_size
                edit_root.tail[1] = 0
                edit_root.tail[2] = 0
            case 'y-':
                edit_root.tail[0] = tail_size
                edit_root.tail[1] = 0
                edit_root.tail[2] = 0
                
        edit_root.head[0] = 0
        edit_root.head[1] = 0
        edit_root.head[2] = 0
        edit_root.roll = 0
        
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        if self.old_active:
            utils.set_active_object(self.old_active)
        if self.old_mode:
            if self.old_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
            elif self.old_mode.startswith('EDIT'):
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        scene_nwo.invalid_root_bone = False
        return {'FINISHED'}
    
class NWO_FixArmatureTransforms(bpy.types.Operator):
    bl_idname = 'nwo.fix_armature_transforms'
    bl_label = ''
    bl_description = 'Sets the model armature to a location, scale, and rotation of 0,0,0'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        arm = utils.get_rig(context)
        arm.matrix_world = Matrix.Identity(4)
        utils.get_scene_props().armature_bad_transforms = False
        return {'FINISHED'}
    
class NWO_OT_AddAimDisplay(bpy.types.Operator):
    bl_idname = 'nwo.add_aim_display'
    bl_label = 'Add Aim Display Bone'
    bl_description = 'Adds an aim display bone to the selected armature'
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        utils.set_object_mode(context)
        scene_nwo = utils.get_scene_props()
        tail_scale = 1 if scene_nwo.scale == 'blender' else (1 / 0.03048)
        arm = utils.get_rig_prioritize_active(context)
        if not arm:
            self.report({'WARNING'}, 'No Armature Found')
            return {'CANCELLED'}
        bones = arm.data.bones
        scene_nwo.main_armature = arm
        for b in bones:
            if b.use_deform and not b.parent:
                scene_nwo.node_usage_pedestal = b.name
                parent_bone = b
                break
        else:
            self.report({'WARNING'}, 'Failed to assign pedestal node usage')
            return {'FINISHED'}
        
        for b in bones:
            if not scene_nwo.node_usage_pose_blend_pitch and b.use_deform and b.parent == parent_bone and 'pitch' in b.name:
                scene_nwo.node_usage_pose_blend_pitch = b.name
            elif not scene_nwo.node_usage_pose_blend_yaw and b.use_deform and b.parent == parent_bone and 'yaw' in b.name:
                scene_nwo.node_usage_pose_blend_yaw = b.name
                
        rig = HaloRig(context, tail_scale, scene_nwo.forward_direction, False, True)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        context.view_layer.objects.active = arm
        arm.select_set(True)
        rig.has_pose_bones = True
        rig.build_bones(pedestal=scene_nwo.node_usage_pedestal if scene_nwo.node_usage_pedestal else None, pitch=scene_nwo.node_usage_pose_blend_pitch if scene_nwo.node_usage_pose_blend_pitch else None, yaw=scene_nwo.node_usage_pose_blend_yaw if scene_nwo.node_usage_pose_blend_yaw else None, set_control=False)
        rig.build_and_apply_control_shapes(pitch=scene_nwo.node_usage_pose_blend_pitch, yaw=scene_nwo.node_usage_pose_blend_yaw, aim_control_only=True, reverse_control=True)
        return {'FINISHED'}
    
class NWO_AddPoseBones(bpy.types.Operator):
    bl_idname = 'nwo.add_pose_bones'
    bl_label = 'Add Aim Bones'
    bl_description = 'Adds aim bones to the armature if missing, optionally with a control bone. Assigns node usage bones'
    bl_options = {'REGISTER', 'UNDO'}
    
    add_control_bone: bpy.props.BoolProperty()
    has_control_bone: bpy.props.BoolProperty()
    skip_invoke: bpy.props.BoolProperty()
    
    armature: bpy.props.StringProperty()
        
    def execute(self, context):
        utils.set_object_mode(context)
        scene_nwo = utils.get_scene_props()
        tail_scale = 1 if scene_nwo.scale == 'blender' else (1 / 0.03048)
        if self.armature:
            arm = bpy.data.objects.get(self.armature)
        else:
            arm = utils.get_rig_prioritize_active(context)
        if not arm:
            self.report({'WARNING'}, 'No Armature Found')
            return {'CANCELLED'}
        scene_nwo.main_armature = arm
        bones = arm.data.bones
        for b in bones:
            if b.use_deform and not b.parent:
                scene_nwo.node_usage_pedestal = b.name
                parent_bone = b
                break
        else:
            self.report({'WARNING'}, 'Failed to assign pedestal node usage')
            return {'FINISHED'}
        
        for b in bones:
            if not scene_nwo.node_usage_pose_blend_pitch and b.use_deform and b.parent == parent_bone and 'pitch' in b.name:
                scene_nwo.node_usage_pose_blend_pitch = b.name
            elif not scene_nwo.node_usage_pose_blend_yaw and b.use_deform and b.parent == parent_bone and 'yaw' in b.name:
                scene_nwo.node_usage_pose_blend_yaw = b.name
                
        rig = HaloRig(context, tail_scale, scene_nwo.forward_direction, False, True)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        context.view_layer.objects.active = arm
        arm.select_set(True)
        rig.has_pose_bones = True
        rig.build_bones(pedestal=scene_nwo.node_usage_pedestal if scene_nwo.node_usage_pedestal else None, pitch=scene_nwo.node_usage_pose_blend_pitch if scene_nwo.node_usage_pose_blend_pitch else None, yaw=scene_nwo.node_usage_pose_blend_yaw if scene_nwo.node_usage_pose_blend_yaw else None)
        if self.add_control_bone:
            rig.build_and_apply_control_shapes(pitch=scene_nwo.node_usage_pose_blend_pitch, yaw=scene_nwo.node_usage_pose_blend_yaw, aim_control_only=True)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        rig = utils.get_rig_prioritize_active(context)
        if rig.nwo.control_aim:
            self.report({'INFO'}, "Aim Control bone already set")
            self.has_control_bone = True
            return self.execute(context)
        else:
            self.has_control_bone = False
            if self.skip_invoke:
                self.add_control_bone = True
                return self.execute(context)
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, 'add_control_bone', text='Add Aim Control Bone')