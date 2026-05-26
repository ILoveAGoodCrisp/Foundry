

from collections import defaultdict
from math import atan2, cos, radians, sin, tau
from typing import cast
import bpy
from mathutils import Matrix, Vector
from ...constants import WU_SCALAR
from ... import utils
from .shapes import *

bone_x = 0, (1 / WU_SCALAR), 0
bone_x_negative = 0, -(1 / WU_SCALAR), 0
bone_y = -(1 / WU_SCALAR), 0, 0
bone_y_negative = (1 / WU_SCALAR), 0, 0

pedestal_name, aim_pitch_name, aim_yaw_name = 'pedestal', 'aim_pitch', 'aim_yaw'
aim_control_name = 'CTRL_aim'
head_control_name = 'CTRL_head'
look_control_name = 'CTRL_look'
gun_control_name = 'CTRL_gun'
gun_bone_name = 'b_gun'
fk_ik_switch_bone_name = "FK_IK_Switch"
fk_ik_slider_bone_name = "FK_IK"
settings_control_name = 'CTRL_settings'
fk_control_shape_name = "fk_control_shape"

head_look_shape_name = 'head_look_shape'
eye_look_shape_name = 'eye_look_shape'
pelvis_shape_name = 'pelvis_shape'
torso_shape_name = 'torso_shape'
settings_shape_name = 'settings_shape'

free_deform_collection_name = "Free Deform Bones"
controlled_deform_collection_name = "Controlled Deform Bones"
helper_deform_collection_name = "Helper Deform Bones"
face_deform_collection_name = "Face Deform Bones"
pedestal_collection_name = "Pedestal Bones"
aim_collection_name = "Aim Bones"
fk_collection_name = "FK"
ik_collection_name = "IK"
settings_control_collection_name = "Settings Control"
misc_control_collection_name = "Other"
legacy_deform_collection_names = ("Deform Bones", "Deform", "Pedestal & Aim Bones")
foundry_bone_collection_names = (
    free_deform_collection_name,
    controlled_deform_collection_name,
    helper_deform_collection_name,
    face_deform_collection_name,
    pedestal_collection_name,
    aim_collection_name,
    fk_collection_name,
    ik_collection_name,
    settings_control_collection_name,
    misc_control_collection_name,
    *legacy_deform_collection_names,
)

head_track_constraint_name = 'Foundry Head Track'
neck_assist_constraint_name = 'Foundry Neck Assist Track'
eye_track_constraint_name = 'Foundry Eye Track'
root_child_of_constraint_name = 'Foundry Root Child Of'
look_child_of_constraint_name = 'Foundry Look Child Of'
gun_copy_transforms_constraint_name = 'Foundry Gun Copy Transforms'
ik_constraint_name = 'Foundry IK'
ik_copy_rotation_constraint_name = 'Foundry IK Copy Rotation'
head_follow_root_prop_name = "Head track ignores root"
look_follow_root_prop_name = "Look track ignores root"
look_follow_head_prop_name = "Look ignores head"
head_track_prop_name = "Head Track"
eye_track_prop_name = "Eye Track"
gun_control_prop_name = "gun_control"

reach_fp_ik_fix_render_models = frozenset({
    r"objects\characters\spartans\fp\fp.render_model",
    r"objects\characters\elite\fp\fp.render_model",
})


def needs_reach_fp_ik_fix(tag_path: str) -> bool:
    return str(tag_path).replace("/", "\\").lower() in reach_fp_ik_fix_render_models

# Bone that should be connected
bone_links = (
    ("upperarm", "forearm", "hand"),
    ("thigh", "calf", "foot"),
    ("thigh", "shin", "toe_hinge", "toe"),
    ("upper_leg", "lower_leg", "tarsus"),
    ("low", "mid", "tip"),
    ("neck", "head"),
    ("neck0", "neck1", "head"),
    ("neck1", "neck2", "neck3", "neck4", "head"),
    ("neck1", "neck2", "neck3", "head"),
    ("neck1", "neck2", "head"),
    ("neck1", "head"),
    # ("spine", "spine1"),
    ("index1", "index2", "index3"),
    ("thumb1", "thumb2", "thumb3"),
    ("pinky1", "pinky2", "pinky3"),
    ("ring1", "ring2", "ring3"),
    ("middle1", "middle2", "middle3"),
    ("thigh", "shin", "hinge", "toe", "toe_atr_u"),
)

bones_to_add_fk = (
    "pelvis",
    "spine",
    "spine0",
    "spine1",
    "spine2",
    "spine3",
    "chest",
)

ik_endpoint_bone_suffixes = ("foot", "tarsus", "hand", "toe_atr_u")

head_bone_name = '_head'
eyes_bone_name = '_eye'

start_link_bones = defaultdict(list)
start_link_bones_keys = tuple()

def reset_start_link_bones():
    global start_link_bones
    global start_link_bones_keys
    start_link_bones = defaultdict(list)
    for b in bone_links:
        start_link_bones[b[0]].append(b[1:])

    start_link_bones_keys = tuple(start_link_bones.keys())
    
reset_start_link_bones()

key_deform_bones = (
    "pelvis",
)

# Also connect sequential bones indicated by a number at the end of their name e.g. pinky1, pinky2
# Any deform bones controlled by an FK bone are hidden by default
# Final bone in the chain gets IK added

# Bones which play a minor role in deformation, to go in their own collection and hidden by default
helper_bones = (
    "fixup",
    "helper",
    "twist",
)

special_bones = (
    "pedestal",
    "aim_pitch",
    "aim_yaw",
)

class HaloRig:
    def __init__(self, context=bpy.context, scale=None, forward=None, has_pose_bones=False, set_scene_rig_props=False):
        self.context = context
        self.scene_nwo = utils.get_scene_props()
        shape_scale = (1 / 0.03048) if self.scene_nwo.scale == 'max' else 1
        self.scale = shape_scale if scale is None else scale
        self.shape_scale = shape_scale
        self.scale_matrix = Matrix.Scale(self.scale, 4)
        self.forward = self.scene_nwo.forward_direction if forward is None else forward
        self.has_pose_bones = has_pose_bones
        self.set_scene_rig_props = set_scene_rig_props
        self.rig_data: bpy.types.Armature = None
        self.rig_ob: bpy.types.Object = None
        self.rig_pose: bpy.types.Pose = None
        
        self.pedestal: bpy.types.PoseBone = None
        self.pitch: bpy.types.PoseBone = None
        self.yaw: bpy.types.PoseBone = None
        self.aim_control: bpy.types.PoseBone = None
        
        self.fk_bones: list[bpy.types.PoseBone] = []
        self.ik_bones: list[bpy.types.PoseBone] = []
        
        self.bones_with_fk_controllers = set()
    
    def build_and_apply_control_shapes(self, pedestal=None, pitch=None, yaw=None, aim_control=None, aim_control_only=False, reverse_control=False, reach_fp_fix=False, constraints_only=False):
        min_size, max_size = utils.to_aabb(self.rig_ob)
        shape_scale = abs((max_size - min_size).length)
        if not aim_control_only:
            if not pedestal:
                pedestal: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, pedestal_name)
            else:
                pedestal = self.rig_ob.pose.bones.get(pedestal)
            if pedestal is not None:
                shape_ob = bpy.data.objects.get(pedestal_shape_name)
                if shape_ob is None:
                    shape_data = bpy.data.meshes.new(pedestal_shape_name)
                    verts = [Vector(co) for co in pedestal_shape_vert_coords]
                    shape_data.from_pydata(vertices=verts, edges=pedestal_shape_edges, faces=[])
                    shape_ob = bpy.data.objects.new(pedestal_shape_name, shape_data)
                    
                    shape_ob.nwo.export_this = False
                
                pedestal.color.palette = 'THEME04'
                pedestal.custom_shape = shape_ob
                pedestal.custom_shape_scale_xyz = Vector((1, 1, 1)) * shape_scale * self.shape_scale
                pedestal.use_custom_shape_bone_size = False
                
                if reach_fp_fix:
                    pedestal.custom_shape_rotation_euler.x = radians(-90)
                
                # if wireframe:
                #     self.rig_data.bones[pedestal.name].show_wire = True
        
        if self.has_pose_bones:
            if not aim_control:
                aim_control: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_control_name)
            elif isinstance(aim_control, str):
                aim_control = self.rig_ob.pose.bones.get(aim_control)

            if aim_control is None:
                aim_control: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_control_name)

            if not pitch:
                pitch: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_pitch_name)
            elif isinstance(pitch, str):
                pitch = self.rig_ob.pose.bones.get(pitch)

            if pitch is None:
                pitch: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_pitch_name)

            if not yaw:
                yaw: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_yaw_name)
            elif isinstance(yaw, str):
                yaw = self.rig_ob.pose.bones.get(yaw)

            if yaw is None:
                yaw: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_yaw_name)

            if not (pedestal or pitch or yaw or aim_control):
                return

            if not aim_control_only and not constraints_only and pedestal is not None and aim_control is not None:
                pedestal_name_for_sync = pedestal.name
                aim_control_name_for_sync = aim_control.name
                pitch_name_for_sync = pitch.name if pitch is not None else None
                yaw_name_for_sync = yaw.name if yaw is not None else None
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                pedestal_edit = self.rig_data.edit_bones.get(pedestal_name_for_sync)
                aim_control_edit = self.rig_data.edit_bones.get(aim_control_name_for_sync)
                if pedestal_edit is not None and aim_control_edit is not None:
                    match_edit_bone_length(aim_control_edit, pedestal_edit)
                    aim_control_edit.use_connect = False
                    aim_control_edit.use_deform = False
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
                self.rig_pose = self.rig_ob.pose
                pedestal = self.rig_pose.bones.get(pedestal_name_for_sync)
                aim_control = self.rig_pose.bones.get(aim_control_name_for_sync)
                pitch = self.rig_pose.bones.get(pitch_name_for_sync) if pitch_name_for_sync else None
                yaw = self.rig_pose.bones.get(yaw_name_for_sync) if yaw_name_for_sync else None

            if not constraints_only and (aim_control is not None or pitch is not None or yaw is not None):
                shape_ob = bpy.data.objects.get(aim_shape_name)
                if shape_ob is None:
                    shape_data = bpy.data.meshes.new(aim_shape_name)
                    verts = [Vector(co) for co in aim_shape_vert_coords]
                    shape_data.from_pydata(vertices=verts, edges=aim_shape_edges, faces=[])
                    shape_ob = bpy.data.objects.new(aim_shape_name, shape_data)
                    shape_ob.nwo.export_this = False

                if aim_control is not None:
                    aim_control.color.palette = 'THEME04'
                    aim_control.custom_shape = shape_ob
                    aim_control.custom_shape_scale_xyz = Vector((1, 1, 1)) * shape_scale * self.shape_scale
                    aim_control.use_custom_shape_bone_size = False

                    if reach_fp_fix:
                        aim_control.custom_shape_rotation_euler.z = radians(90)

                    # if wireframe:
                    #     self.rig_data.bones[aim_control.name].show_wire = True

                if pitch is not None:
                    pitch.color.palette = 'THEME04'
                    pitch.custom_shape = shape_ob
                    pitch.custom_shape_scale_xyz = Vector((0.2, 0.2, 0.2)) * shape_scale * self.shape_scale
                    pitch.use_custom_shape_bone_size = False
                    if not reach_fp_fix:
                        pitch.custom_shape_rotation_euler.x = radians(90)

                    # if wireframe:
                    #     self.rig_data.bones[pitch.name].show_wire = True

                if yaw is not None:
                    yaw.color.palette = 'THEME04'
                    yaw.custom_shape = shape_ob
                    yaw.custom_shape_scale_xyz = Vector((0.2, 0.2, 0.2)) * shape_scale * self.shape_scale
                    yaw.use_custom_shape_bone_size = False

                    if reach_fp_fix:
                        yaw.custom_shape_rotation_euler.x = radians(90)

                    # if wireframe:
                    #     self.rig_data.bones[yaw.name].show_wire = True

            if aim_control is not None and pitch is not None and yaw is not None:
                        
                # def add_aim_control_driver(c, invert):
                #     result = c.driver_add('influence')
                #     driver = result.driver
                #     driver.type = 'SCRIPTED'
                #     var = driver.variables.new()
                #     var.name = "var"
                #     var.type = 'SINGLE_PROP'
                #     var.targets[0].id = self.rig_ob
                #     var.targets[0].data_path = '["_invert_control_aim"]'
                #     driver.expression = var.name if invert else f"not {var.name}"
                    
                if reach_fp_fix:
                    pitch_con_bone = yaw
                    yaw_con_bone = pitch
                else:
                    pitch_con_bone = pitch
                    yaw_con_bone = yaw
                
                if aim_control:
                    utils.clear_constraints(aim_control)
                if yaw:
                    utils.clear_constraints(yaw)
                if pitch:
                    utils.clear_constraints(pitch)
                
                self.rig_ob.nwo.control_aim = aim_control.name
                
                con = aim_control.constraints.new('LIMIT_SCALE')
                con.use_min_x = True
                con.use_min_y = True
                con.use_min_z = True
                con.use_max_x = True
                con.use_max_y = True
                con.use_max_z = True
                con.min_x = 1
                con.min_y = 1
                con.min_z = 1
                con.max_x = 1
                con.max_y = 1
                con.max_z = 1
                con.use_transform_limit = True
                con.owner_space = 'LOCAL'
                
                con = aim_control.constraints.new('LIMIT_LOCATION')
                con.use_min_x = True
                con.use_min_y = True
                con.use_min_z = True
                con.use_max_x = True
                con.use_max_y = True
                con.use_max_z = True
                con.use_transform_limit = True
                con.owner_space = 'LOCAL'
                
                con = aim_control.constraints.new('LIMIT_ROTATION')
                con.min_x = 0
                con.max_x = 0
                con.use_limit_x = True
                con.use_limit_y = True
                if reach_fp_fix:
                    con.min_x = radians(-90)
                    con.max_x = radians(90)
                else:
                    con.min_y = radians(-90)
                    con.max_y = radians(90)
                con.euler_order = 'YXZ'
                con.use_transform_limit = True
                con.owner_space = 'LOCAL'
                
                # When invert True
                if reverse_control:
                    self.rig_ob.nwo.invert_control_aim = True
                    con = aim_control.constraints.new('COPY_ROTATION')
                    con.target = self.rig_ob
                    con.subtarget = pitch_con_bone.name
                    con.use_x = False
                    con.use_z = False
                    con.target_space = 'LOCAL_OWNER_ORIENT'
                    con.owner_space = 'LOCAL'
                    
                    con = aim_control.constraints.new('COPY_ROTATION')
                    con.target = self.rig_ob
                    con.subtarget = yaw_con_bone.name
                    con.use_x = False
                    con.use_y = False
                    con.target_space = 'LOCAL_OWNER_ORIENT'
                    con.owner_space = 'LOCAL'
                
                # When invert false
                else:
                    self.rig_ob.nwo.invert_control_aim = False
                    con = pitch_con_bone.constraints.new('COPY_ROTATION')
                    con.target = self.rig_ob
                    con.subtarget = aim_control.name
                    con.use_x = False
                    con.use_z = False
                    con.target_space = 'LOCAL_OWNER_ORIENT'
                    con.owner_space = 'LOCAL'
                    
                    con = yaw_con_bone.constraints.new('COPY_ROTATION')
                    con.target = self.rig_ob
                    con.subtarget = aim_control.name
                    con.use_x = False
                    con.use_y = False
                    con.target_space = 'LOCAL_OWNER_ORIENT'
                    con.owner_space = 'LOCAL'
                    
                    # constraint to handle gimbal lock scenario where X becomes our yaw
                    con = yaw_con_bone.constraints.new('TRANSFORM')
                    con.target = self.rig_ob
                    con.subtarget = aim_control.name
                    con.map_from = 'ROTATION'
                    con.from_min_x_rot = radians(-90)
                    con.from_max_x_rot = radians(90)
                    con.map_to = 'ROTATION'
                    con.map_to_z_from = 'X'
                    con.to_min_z_rot = radians(-90)
                    con.to_max_z_rot = radians(90)
                    con.target_space = 'LOCAL_OWNER_ORIENT'
                    con.owner_space = 'LOCAL'
    
    def build_bones(self, pedestal=None, pitch=None, yaw=None, set_control=True):
        bone_tail = globals()[f"bone_{self.forward.replace('-', '_negative')}"]
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        if pedestal is None:
            for b in self.rig_data.edit_bones:
                if utils.remove_node_prefix(b.name).lower() == pedestal_name:
                    pedestal = b
                    break
            else:
                pedestal = self.rig_data.edit_bones.new(pedestal_name)
                pedestal.tail = bone_tail
                pedestal.transform(self.scale_matrix)
        else:
            pedestal = self.rig_data.edit_bones.get(pedestal)
            
        if self.set_scene_rig_props and self.has_pose_bones and not self.scene_nwo.node_usage_pedestal:
            self.scene_nwo.node_usage_pedestal = pedestal_name
        
        if self.has_pose_bones:
            if pitch is None:
                for b in self.rig_data.edit_bones:
                    if utils.remove_node_prefix(b.name).lower() == aim_pitch_name:
                        pitch = b
                        break
                else:
                    pitch = self.rig_data.edit_bones.new(aim_pitch_name)
                    pitch.parent = pedestal
                    pitch.tail = bone_tail
                    pitch.transform(self.scale_matrix)
            else:
                pitch = self.rig_data.edit_bones.get(pitch)
            
            if yaw is None:
                for b in self.rig_data.edit_bones:
                    if utils.remove_node_prefix(b.name).lower() == aim_yaw_name:
                        yaw = b
                        break
                else:
                    yaw = self.rig_data.edit_bones.new(aim_yaw_name)
                    yaw.parent = pedestal
                    yaw.tail = bone_tail
                    yaw.transform(self.scale_matrix)
            else:
                yaw = self.rig_data.edit_bones.get(yaw)
                
            if self.set_scene_rig_props:
                if not self.scene_nwo.node_usage_pose_blend_pitch:
                    self.scene_nwo.node_usage_pose_blend_pitch = aim_pitch_name
                if not self.scene_nwo.node_usage_pose_blend_yaw:
                    self.scene_nwo.node_usage_pose_blend_yaw = aim_yaw_name
                    
            aim_control = self.rig_data.edit_bones.new(aim_control_name)
            aim_control.use_deform = False
            aim_control.parent = pedestal
            aim_control.use_connect = False
            aim_control.tail = bone_tail
            aim_control.transform(self.scale_matrix)
            if pedestal is not None:
                match_edit_bone_length(aim_control, pedestal)

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
                
    def make_parent(self, child_bone_name):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        pedestal = self.rig_data.edit_bones.get(pedestal_name)
        child_bone = self.rig_data.edit_bones.get(child_bone_name)
        child_bone.parent = pedestal
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    
    def build_armature(self):
        self.rig_data = bpy.data.armatures.new('Armature')
        self.rig_ob = bpy.data.objects.new('Armature', self.rig_data)
        self.context.scene.collection.objects.link(self.rig_ob)
        self.context.view_layer.objects.active = self.rig_ob
        self.rig_ob.select_set(True)
        if self.set_scene_rig_props and not self.scene_nwo.main_armature:
            self.scene_nwo.main_armature = self.rig_ob
            
    def generate_bone_collections(self):
        """Sorts bones into bone collections"""
        unparent_legacy_bone_collection_groups(self.rig_data)
        halo_free = ensure_top_level_bone_collection(self.rig_data, free_deform_collection_name)
        halo_controlled = ensure_top_level_bone_collection(self.rig_data, controlled_deform_collection_name)
        halo_helpers = ensure_top_level_bone_collection(self.rig_data, helper_deform_collection_name)
        halo_face = ensure_top_level_bone_collection(self.rig_data, face_deform_collection_name)
        pedestal_collection = ensure_top_level_bone_collection(self.rig_data, pedestal_collection_name)
        aim_collection = ensure_top_level_bone_collection(self.rig_data, aim_collection_name)
        fk_collection = ensure_top_level_bone_collection(self.rig_data, fk_collection_name)
        ik_collection = ensure_top_level_bone_collection(self.rig_data, ik_collection_name)
        settings_collection = ensure_top_level_bone_collection(self.rig_data, settings_control_collection_name)
        ctrl_collection = ensure_top_level_bone_collection(self.rig_data, misc_control_collection_name)

        clear_foundry_bone_collection_assignments(self.rig_data)
        face_bone_names = face_deform_bone_names(self.rig_data)
        
        for bone in self.rig_data.bones:
            no_digit_name = bone.name.strip("0123456789")
            if bone.use_deform:
                if bone_name_matches_suffix(no_digit_name, pedestal_name):
                    pedestal_collection.assign(bone)
                elif bone_name_matches_suffix(no_digit_name, aim_pitch_name) or bone_name_matches_suffix(no_digit_name, aim_yaw_name):
                    aim_collection.assign(bone)
                elif bone.name in face_bone_names:
                    halo_face.assign(bone)
                elif no_digit_name.endswith(helper_bones):
                    halo_helpers.assign(bone)
                elif bone.name in self.bones_with_fk_controllers:
                    halo_controlled.assign(bone)
                else:
                    halo_free.assign(bone)
            else:
                if bone.name == settings_control_name or bone.name.startswith(f"{settings_control_name}."):
                    settings_collection.assign(bone)
                elif no_digit_name.startswith("FK_"):
                    fk_collection.assign(bone)
                elif no_digit_name.startswith(("IK_", "PT_")):
                    ik_collection.assign(bone)
                else:
                    ctrl_collection.assign(bone)

        for name in legacy_deform_collection_names:
            remove_empty_bone_collection(self.rig_data, name)

        # ctrl_collection.is_visible = False

        if any(not bone.use_deform for bone in self.rig_data.bones):
            halo_controlled.is_visible = False
            halo_free.is_visible = False
            halo_helpers.is_visible = False
            halo_face.is_visible = False
            settings_collection.is_visible = False
            # pedestal_collection.is_visible = True
            # aim_collection.is_visible = True

    def apply_halo_bone_shape(self):
        """Applies a custom shape to every halo bone that is not the pedestal or an aim bone"""
        shape = bpy.data.objects.get(deform_shape_name)
        if shape is None:
            shape_mesh = bpy.data.meshes.new("halo_deform_bone_shape")
            utils.mesh_to_cube(shape_mesh)
            shape = bpy.data.objects.new("halo_deform_bone_shape", shape_mesh)

            shape_mesh = bpy.data.meshes.new(deform_shape_name)
            shape_mesh.from_pydata(
                vertices=[Vector(co) for co in deform_shape_vert_coords],
                edges=deform_shape_edges,
                faces=[],
            )
            shape = bpy.data.objects.new(deform_shape_name, shape_mesh)
            shape.nwo.export_this = False

        min_size, max_size = utils.to_aabb(self.rig_ob)
        shape_scale = abs((max_size - min_size).length)
        deform_bone_names = {
            bone.name
            for bone in self.rig_data.bones
            if bone.use_deform and (not bone.name.endswith(special_bones) and not bone.name.startswith(("FK_", "IK_", "CTRL_")))
        }
        deform_bounds = vertex_group_bounds_by_deform_bone(self.rig_ob, self.rig_pose, deform_bone_names)

        for pbone in self.rig_pose.bones:
            bone = self.rig_data.bones.get(pbone.name)
            if bone is None or not bone.use_deform or bone.name not in deform_bone_names:
                continue

            if pbone.custom_shape is None or is_foundry_deform_custom_shape(pbone.custom_shape):
                fallback_scale, fallback_translation = fallback_deform_shape_transform(pbone, shape_scale * self.shape_scale)
                pbone.custom_shape = shape
                pbone.use_custom_shape_bone_size = False
                pbone.custom_shape_rotation_euler = Vector((0.0, 0.0, 0.0))
                bounds = deform_bounds.get(bone.name)
                if bounds is None:
                    pbone.custom_shape_scale_xyz = fallback_scale
                    pbone.custom_shape_translation = fallback_translation
                else:
                    pbone.custom_shape_scale_xyz, pbone.custom_shape_translation = deform_shape_transform_from_bounds(
                        bounds,
                        pbone.length,
                        fallback_scale,
                        fallback_translation,
                    )
                bone.show_wire = True

    def build_extra_control_bones(self, deform_fk_mapping: dict[str, str], constraints_only=False):
        head_deform_name = find_deform_pose_bone_name_by_suffix(self.rig_ob, "head")
        eye_bone_names = choose_eye_bone_names(find_deform_pose_bone_names_by_suffix(self.rig_ob, "eye"))
        gun_pose_bone_name = find_pose_bone_name_by_node_names(self.rig_ob, (gun_bone_name, "gun"))
        head_driver_name = get_head_driver_bone_name(self.rig_ob, head_deform_name, deform_fk_mapping)

        if not constraints_only:
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            edit_bones = self.rig_data.edit_bones
            root = edit_bones[0] if len(edit_bones) else None
            head_control = None
            head_height_source = None
            look_control = None
            gun_control = None

            if root is not None and head_driver_name:
                head_source = edit_bones.get(head_driver_name)
                if head_source is not None:
                    head_height_source = head_source
                    head_control = ensure_control_bone(edit_bones, head_control_name)
                    place_front_control_bone(
                        head_control,
                        root,
                        head_source,
                        self.scale,
                        None,
                    )

            if root is not None and len(eye_bone_names) >= 2:
                head_control = head_control or edit_bones.get(head_control_name)
                if head_control is not None:
                    eye_sources = [edit_bones.get(name) for name in eye_bone_names[:2]]
                    eye_sources = [bone for bone in eye_sources if bone is not None]
                    if len(eye_sources) >= 2:
                        look_control = ensure_control_bone(edit_bones, look_control_name)
                        height_source = head_height_source or head_control
                        place_front_control_bone(
                            look_control,
                            root,
                            height_source,
                            self.scale,
                            None,
                            max(sum(bone.length for bone in eye_sources) / len(eye_sources), head_control.length),
                        )

            if root is not None and gun_pose_bone_name:
                gun_bone = edit_bones.get(gun_pose_bone_name)
                if gun_bone is not None:
                    gun_control = ensure_control_bone(edit_bones, gun_control_name)
                    copy_edit_bone_transform(gun_control, gun_bone)
                    gun_control.parent = root
                    gun_control.use_connect = False
                    gun_control.use_deform = False

            if root is not None and (head_control is not None or look_control is not None or gun_control is not None):
                ensure_settings_control_bone(edit_bones, root, self.scale)

            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            self.rig_pose = self.rig_ob.pose
        elif any(self.rig_pose.bones.get(name) is not None for name in (look_control_name, head_control_name, gun_control_name)):
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            edit_bones = self.rig_data.edit_bones
            root = edit_bones[0] if len(edit_bones) else None
            any_extra_control = self.rig_pose.bones.get(gun_control_name) is not None
            for control_name in (head_control_name, look_control_name):
                control_bone = edit_bones.get(control_name)
                if control_bone is None:
                    continue

                control_bone.parent = None
                control_bone.use_connect = False
                control_bone.use_deform = False
                any_extra_control = True

            if root is not None and any_extra_control:
                ensure_settings_control_bone(edit_bones, root, self.scale)

            if root is not None and gun_pose_bone_name:
                gun_bone = edit_bones.get(gun_pose_bone_name)
                gun_control = edit_bones.get(gun_control_name)
                if gun_bone is not None and gun_control is not None:
                    copy_edit_bone_transform(gun_control, gun_bone)
                    gun_control.parent = root
                    gun_control.use_connect = False
                    gun_control.use_deform = False

            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            self.rig_pose = self.rig_ob.pose

        root_control = self.rig_pose.bones[0] if len(self.rig_pose.bones) else None
        min_size, max_size = utils.to_aabb(self.rig_ob)
        control_shape_scale = abs((max_size - min_size).length) * 0.1 * self.shape_scale
        if control_shape_scale <= 0:
            control_shape_scale = self.shape_scale

        head_control = self.rig_pose.bones.get(head_control_name)
        if head_control is not None:
            head_shape = get_or_create_shape(head_look_shape_name, head_look_shape_vert_coords, head_look_shape_edges)
            apply_control_shape(head_control, head_shape, control_shape_scale, 'THEME04')

        look_control = self.rig_pose.bones.get(look_control_name)
        if look_control is not None:
            eye_shape = get_or_create_shape(eye_look_shape_name, eye_look_shape_vert_coords, eye_look_shape_edges)
            apply_control_shape(look_control, eye_shape, control_shape_scale * 0.4, 'THEME04')

        settings_control = self.rig_pose.bones.get(settings_control_name)
        if settings_control is not None:
            apply_settings_control_shape(settings_control, get_or_create_shape(settings_shape_name, settings_shape_vert_coords, settings_shape_edges))
            ensure_look_control_props(
                settings_control,
                has_head_control=head_control is not None,
                has_look_control=look_control is not None,
                has_eye_controls=look_control is not None and len(eye_bone_names) >= 2,
            )

        if root_control is not None and settings_control is not None:
            if head_control is not None:
                add_root_child_of_constraint(head_control, self.rig_ob, root_control.name, head_follow_root_prop_name)
            if look_control is not None:
                add_root_child_of_constraint(look_control, self.rig_ob, root_control.name, look_follow_root_prop_name)

        gun_control = self.rig_pose.bones.get(gun_control_name)
        if gun_control is not None:
            gun_shape = get_or_create_shape(pole_vector_shape_name, pole_vector_shape_vert_coords, pole_vector_shape_edges)
            apply_control_shape(gun_control, gun_shape, control_shape_scale, 'THEME04', use_bone_size=False)
            if settings_control is not None:
                ensure_gun_control_props(settings_control)

        if head_driver_name and head_control is not None:
            head_driver = self.rig_pose.bones.get(head_driver_name)
            if head_driver is not None:
                clear_matching_constraints(
                    head_driver,
                    head_track_constraint_name,
                    'DAMPED_TRACK',
                    self.rig_ob,
                    head_control_name,
                )
                con = cast(bpy.types.Constraint, head_driver.constraints.new('DAMPED_TRACK'))
                con.name = head_track_constraint_name
                con.target = self.rig_ob
                con.subtarget = head_control_name
                con.track_axis = 'TRACK_Z'
                con.influence = 0.0
                if settings_control is not None:
                    add_settings_control_prop_driver(con, self.rig_ob, head_track_prop_name)
                clear_neck_assist_constraints(head_driver)
                if head_driver.name == head_deform_name:
                    self.bones_with_fk_controllers.add(head_driver.name)

        if look_control is not None and head_control is not None and settings_control is not None:
            clear_matching_constraints(
                look_control,
                look_child_of_constraint_name,
                'CHILD_OF',
                self.rig_ob,
                head_control_name,
            )
            con = cast(bpy.types.Constraint, look_control.constraints.new('CHILD_OF'))
            con.name = look_child_of_constraint_name
            con.target = self.rig_ob
            con.subtarget = head_control_name
            con.influence = 0.0
            con.set_inverse_pending = True
            add_settings_control_prop_driver(con, self.rig_ob, look_follow_head_prop_name, invert=True)

        if len(eye_bone_names) >= 2 and look_control is not None:
            for eye_name in eye_bone_names[:2]:
                eye_bone = self.rig_pose.bones.get(eye_name)
                if eye_bone is None:
                    continue

                clear_matching_constraints(
                    eye_bone,
                    eye_track_constraint_name,
                    'DAMPED_TRACK',
                    self.rig_ob,
                    look_control_name,
                )
                con = cast(bpy.types.Constraint, eye_bone.constraints.new('DAMPED_TRACK'))
                con.name = eye_track_constraint_name
                con.target = self.rig_ob
                con.subtarget = look_control_name
                con.track_axis = 'TRACK_X'
                con.influence = 0.0
                if settings_control is not None:
                    add_settings_control_prop_driver(con, self.rig_ob, eye_track_prop_name)
                self.bones_with_fk_controllers.add(eye_name)

        if gun_pose_bone_name and gun_control is not None:
            gun_bone = self.rig_pose.bones.get(gun_pose_bone_name)
            root_bone = self.rig_pose.bones[0] if len(self.rig_pose.bones) else None
            if gun_bone is not None:
                clear_matching_constraints(
                    gun_bone,
                    gun_copy_transforms_constraint_name,
                    'COPY_TRANSFORMS',
                    self.rig_ob,
                    gun_control_name,
                )
                if gun_bone != root_bone:
                    con = cast(bpy.types.Constraint, gun_bone.constraints.new('COPY_TRANSFORMS'))
                    con.name = gun_copy_transforms_constraint_name
                    con.target = self.rig_ob
                    con.subtarget = gun_control_name
                    con.target_space = 'WORLD'
                    con.owner_space = 'WORLD'
                    con.influence = 0.0
                    if settings_control is not None:
                        add_settings_control_prop_driver(con, self.rig_ob, gun_control_prop_name)
                    self.bones_with_fk_controllers.add(gun_pose_bone_name)
        
    def build_fk_ik_rig(self, reverse_controls=False, constraints_only=False, reach_fp_ik_fix=False):
        """Generates an FK/IK skeleton for the halo rig"""
        
        deform_fk_mapping = {}
        fk_ik_mapping = {}
        fk_bone_names = []
        ik_bone_names = []
        fk_bones_for_ik = []
        settings_bone_name = None
        
        processed_bones = set()
        
        def deform_bone_from_fk_name(name):
            if name.startswith("FK_"):
                name = name[3:]
            
            if name.endswith(".R"):
                name = f"r_{utils.dot_partition(name)}"
            elif name.endswith(".L"):
                name = f"l_{utils.dot_partition(name)}"
            
            pbone = utils.get_pose_bone(self.rig_ob, name)
            
            return pbone
        
        if constraints_only:
            existing_ik_targets = []
            existing_head_fk_names = []

            for bone in self.rig_pose.bones:
                if is_fk_control_bone(bone.name):
                    fk_bone_names.append(bone.name)
                    if bone_name_matches_suffix(bone.name[3:], "head"):
                        existing_head_fk_names.append(bone.name)
                    dbone = deform_bone_from_fk_name(bone.name)
                    if dbone is not None:
                        deform_fk_mapping[dbone.name] = bone.name
                    if is_ik_endpoint_fk_name(bone.name):
                        ik_name = bone.name.replace("FK_", "IK_", 1)
                        pt_name = ik_name.replace("IK_", "PT_", 1)
                        if self.rig_pose.bones.get(ik_name) is not None and self.rig_pose.bones.get(pt_name) is not None:
                            existing_ik_targets.append((bone.name, ik_name, pt_name))

            if existing_ik_targets or existing_head_fk_names:
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                edit_bones = self.rig_data.edit_bones
                root = edit_bones[0] if len(edit_bones) else None
                for fk_head_name in existing_head_fk_names:
                    fk_head = edit_bones.get(fk_head_name)
                    if fk_head is not None:
                        point_bone_tail_global_up(fk_head)

                if existing_ik_targets:
                    remove_legacy_fk_ik_slider_bones(edit_bones)
                    if root is not None:
                        settings_bone = ensure_settings_control_bone(edit_bones, root, self.scale)
                        settings_bone_name = settings_bone.name
                    for fkb_name, ik_name, pt_name in existing_ik_targets:
                        fkb = edit_bones.get(fkb_name)
                        ik_target = edit_bones.get(ik_name)
                        pole_target = edit_bones.get(pt_name)
                        if fkb is None or ik_target is None or pole_target is None or fkb.parent is None or fkb.parent.parent is None:
                            continue

                        ik_target.parent = None
                        ik_target.use_connect = False
                        ik_target.use_deform = False
                        pole_target.parent = None
                        pole_target.use_connect = False
                        pole_target.use_deform = False

                        root_fkb = fkb.parent.parent
                        mid_fkb = fkb.parent
                        if root is not None and reach_fp_ik_fix and "_hand." in fkb.name:
                            pole_pos = calculate_lateral_pole_position(root, root_fkb, mid_fkb, fkb)
                            pole_target.head = pole_pos
                            pole_target.tail = pole_pos + (mid_fkb.y_axis.normalized() * max(mid_fkb.length * 0.35, 0.01))

                        angle = calculate_pole_angle(root_fkb, fkb, pole_target.head)
                        fk_ik_mapping[fkb_name] = ik_name, pt_name, angle
                        ik_bone_names.append(ik_name)
                        ik_bone_names.append(pt_name)

                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
                self.rig_pose = self.rig_ob.pose
        else:
            bone_chains = []
            
            def get_chain(b: bpy.types.PoseBone, i: int):
                matched_chains = [links for k, links in start_link_bones.items() if b.name.endswith(k)]
                if not matched_chains:
                    return

                start_index = i
                candidates = []
                for link_tuples in matched_chains:
                    for link_chain in link_tuples:
                        chain_iter = iter(link_chain)
                        chain = [b.name]
                        next_link = next(chain_iter, None)
                        allowed_bones = set(b.children_recursive)
                        search_index = start_index

                        while next_link and search_index < len(self.rig_pose.bones):
                            next_bone = self.rig_pose.bones[search_index]
                            if next_bone.name.endswith(next_link) and next_bone in allowed_bones:
                                chain.append(next_bone.name)
                                next_link = next(chain_iter, None)
                                allowed_bones = set(next_bone.children_recursive)
                                if not next_link:
                                    break
                            search_index += 1

                        if len(chain) > 1:
                            candidates.append((next_link is None, len(chain), chain))

                if candidates:
                    complete_candidates = [candidate for candidate in candidates if candidate[0]]
                    best_candidates = complete_candidates or candidates
                    _, _, chain = max(best_candidates, key=lambda candidate: candidate[1])
                    bone_chains.append(chain)
                    processed_bones.update(chain[1:])

                reset_start_link_bones()
            
            # def get_chain_digit(b: bpy.types.PoseBone, i: int):
            #     current_bone_chain = []
            #     current_bone_chain.append(b.name)
            #     allowed_bones = set(b.children_recursive)
            #     next_expected = b.name[:-1] + str(int(b.name[-1]) + 1)
            #     while i < len(self.rig_pose.bones):
            #         next_bone = self.rig_pose.bones[i]
            #         if next_bone.name == next_expected and next_bone in allowed_bones:
            #             current_bone_chain.append(next_bone.name)
            #             processed_bones.add(next_bone.name)
            #             allowed_bones = set(next_bone.children_recursive)
            #             next_expected = next_bone.name[:-1] + str(int(next_bone.name[-1]) + 1)
                        
            #         i += 1
                    
            #     if len(current_bone_chain) > 1:
            #         bone_chains.append(current_bone_chain)
            
            for idx, bone in enumerate(self.rig_pose.bones):
                if bone.name in processed_bones:
                    continue
                if bone.name.endswith(start_link_bones_keys):
                    get_chain(bone, idx + 1)
                # elif bone.name[-1] == "1":
                #     get_chain_digit(bone, idx + 1) # NOTE Moving to pre-defined chains only
                    
            def fk_name(name):
                no_prefix = utils.remove_node_prefix(name)
                side = ""
                
                if len(no_prefix) > 2:
                    halo_side = no_prefix[0:2]
                    if halo_side == "r_":
                        side = ".R"
                    elif halo_side == "l_":
                        side = ".L"
                        
                if side:
                    end = no_prefix[2:]
                else:
                    end = no_prefix
                
                return f"FK_{end}{side}"

            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            
            root = self.rig_data.edit_bones[0]
            for chain in bone_chains:
                previous_fk_bone = None
                for idx, bone_name in enumerate(chain):
                    edit_bone = self.rig_data.edit_bones[bone_name]
                    next_edit_bone = None
                    next_bone_idx = idx + 1
                    if next_bone_idx < len(chain):
                        next_edit_bone = self.rig_data.edit_bones[chain[next_bone_idx]]
                    
                    fk_bone = self.rig_data.edit_bones.new(fk_name(bone_name))
                        
                    fk_bone.head = edit_bone.head

                    if next_edit_bone is None:
                        children = edit_bone.children

                        if children:
                            avg = Vector((0.0, 0.0, 0.0))
                            for child in children:
                                avg += child.head
                            fk_bone.tail = avg / len(children)

                        else:
                            fk_bone.tail = predict_tail_from_previous(previous_fk_bone, edit_bone)
                            if fk_bone.length > previous_fk_bone.length:
                                fk_bone.length = previous_fk_bone.length
                    else:
                        fk_bone.tail = next_edit_bone.head

                    if bone_name_matches_suffix(edit_bone.name, "head"):
                        point_bone_tail_global_up(fk_bone, edit_bone.length)

                    align_edit_bone_roll_to_source(fk_bone, edit_bone)

                    if previous_fk_bone is None:
                        fk_bone.parent = edit_bone.parent
                    else:
                        fk_bone.parent = previous_fk_bone
                        fk_bone.use_connect = True
                        
                    deform_fk_mapping[edit_bone.name] = fk_bone.name
                    fk_bone_names.append(fk_bone.name)
                    if is_ik_endpoint_fk_name(fk_bone.name):
                        fk_bones_for_ik.append(fk_bone)
                    previous_fk_bone = fk_bone

            torso_fk_bone_names = {}
            for edit_bone in list(self.rig_data.edit_bones):
                if edit_bone.name in deform_fk_mapping or not is_torso_deform_bone_name(edit_bone.name):
                    continue

                torso_fk_name = fk_name(edit_bone.name)
                if self.rig_data.edit_bones.get(torso_fk_name) is not None:
                    continue

                fk_bone = self.rig_data.edit_bones.new(torso_fk_name)
                fk_bone.matrix = edit_bone.matrix.copy()
                fk_bone.length = max(edit_bone.length, 0.01)
                align_edit_bone_roll_to_source(fk_bone, edit_bone)
                fk_bone.use_connect = False

                deform_fk_mapping[edit_bone.name] = fk_bone.name
                fk_bone_names.append(fk_bone.name)
                torso_fk_bone_names[edit_bone.name] = fk_bone.name

            for deform_name, fk_bone_name in torso_fk_bone_names.items():
                edit_bone = self.rig_data.edit_bones.get(deform_name)
                fk_bone = self.rig_data.edit_bones.get(fk_bone_name)
                if edit_bone is None or fk_bone is None:
                    continue

                parent_fk_name = deform_fk_mapping.get(edit_bone.parent.name) if edit_bone.parent is not None else None
                parent_fk = self.rig_data.edit_bones.get(parent_fk_name) if parent_fk_name is not None else None
                fk_bone.parent = parent_fk or edit_bone.parent

            if not fk_bone_names:
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
                self.rig_pose = self.rig_ob.pose
                self.build_extra_control_bones(deform_fk_mapping, constraints_only)
                return
                    
            # IK
            if fk_bones_for_ik:
                settings_bone = ensure_settings_control_bone(self.rig_data.edit_bones, root, self.scale)
                settings_bone_name = settings_bone.name

            for fkb in fk_bones_for_ik:
                if fkb.parent is None or fkb.parent.parent is None:
                    continue
                root_fkb = fkb.parent.parent
                mid_fkb = fkb.parent

                ikb = self.rig_data.edit_bones.new(fkb.name.replace("FK_", "IK_"))
                ikb: bpy.types.EditBone
                copy_edit_bone_transform(ikb, fkb)
                ikb.parent = None
                
                pole_target = self.rig_data.edit_bones.new(ikb.name.replace("IK_", "PT_"))
                if reach_fp_ik_fix and "_hand." in fkb.name:
                    pole_pos = calculate_lateral_pole_position(root, root_fkb, mid_fkb, fkb)
                else:
                    pole_pos = calculate_pole_position(root_fkb, mid_fkb, fkb)
                angle = calculate_pole_angle(root_fkb, fkb, pole_pos)
                pole_target.head = pole_pos
                pole_target.tail = pole_pos + (mid_fkb.y_axis.normalized() * max(mid_fkb.length * 0.35, 0.01))
                pole_target.parent = None
                
                fk_ik_mapping[fkb.name] = ikb.name, pole_target.name, angle
                
                ik_bone_names.append(ikb.name)
                ik_bone_names.append(pole_target.name)
                
                    
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            
            for b in self.rig_data.bones:
                if b.name in fk_bone_names or b.name in ik_bone_names or b.name == settings_bone_name:
                    b.use_deform = False
                
        if reverse_controls:
            self.rig_ob.nwo.invert_control_rig = True
        else:
            self.rig_ob.nwo.invert_control_rig = False

        min_size, max_size = utils.to_aabb(self.rig_ob)
        shape_scale = abs((max_size - min_size).length) * 0.1
        ik_shape = bpy.data.objects.get(ik_shape_name)
        if ik_shape is None:
            ik_shape_data = bpy.data.meshes.new(ik_shape_name)
            ik_shape_data.from_pydata(
                vertices=[Vector(co) for co in ik_shape_vert_coords],
                edges=ik_shape_edges,
                faces=[],
            )
            ik_shape = bpy.data.objects.new(ik_shape_name, ik_shape_data)
            ik_shape.nwo.export_this = False

        pole_shape = bpy.data.objects.get(pole_vector_shape_name)
        if pole_shape is None:
            pole_shape_data = bpy.data.meshes.new(pole_vector_shape_name)
            pole_shape_data.from_pydata(
                vertices=[Vector(co) for co in pole_vector_shape_vert_coords],
                edges=pole_vector_shape_edges,
                faces=[],
            )
            pole_shape = bpy.data.objects.new(pole_vector_shape_name, pole_shape_data)
            pole_shape.nwo.export_this = False

        fk_shape = get_or_create_fk_control_shape()
        fk_to_deform_mapping = {fk_name: deform_name for deform_name, fk_name in deform_fk_mapping.items()}
                
        for db_name, fkb_name in deform_fk_mapping.items():
            fkb = self.rig_pose.bones[fkb_name]
            db = self.rig_pose.bones[db_name]
            self.bones_with_fk_controllers.add(db_name)
            clear_copy_transforms(fkb)
            clear_copy_transforms(db)
            if reverse_controls:
                con = cast(bpy.types.Constraint, fkb.constraints.new('COPY_TRANSFORMS'))
                con.target = self.rig_ob
                con.subtarget = db_name
            else:
                con = cast(bpy.types.Constraint, db.constraints.new('COPY_TRANSFORMS'))
                con.target = self.rig_ob
                con.subtarget = fkb_name
                
            con.target_space = 'LOCAL_OWNER_ORIENT'
            con.owner_space = 'LOCAL'

        self.build_extra_control_bones(deform_fk_mapping, constraints_only)

        apply_fk_control_shapes(self.rig_pose, fk_bone_names, fk_shape)
        apply_torso_control_shapes(self.rig_pose, deform_fk_mapping, shape_scale * self.shape_scale)

        settings_pb = self.rig_pose.bones.get(settings_control_name)
        if settings_pb is not None:
            apply_settings_control_shape(settings_pb, get_or_create_shape(settings_shape_name, settings_shape_vert_coords, settings_shape_edges))
            ensure_ik_control_props(settings_pb, fk_ik_mapping)

        root_control = self.rig_pose.bones[0] if len(self.rig_pose.bones) else None
            
        for fkb_name, (ikb_name, pt_name, angle) in fk_ik_mapping.items():
            fkb = self.rig_pose.bones[fkb_name]
            ikb = self.rig_pose.bones[ikb_name]
            ptb = self.rig_pose.bones[pt_name]
            
            fkb.color.palette = 'THEME07'
            ikb.color.palette = 'THEME01'
            ptb.color.palette = 'THEME01'

            ikb.custom_shape = ik_shape
            ikb.custom_shape_scale_xyz *= self.scale / 0.03048 * 1.2
            ikb.use_custom_shape_bone_size = True
            ikb.custom_shape_translation = Vector((0.0, ikb.length, 0.0))
            source_deform_name = fk_to_deform_mapping.get(fkb_name)
            source_deform = self.rig_pose.bones.get(source_deform_name) if source_deform_name is not None else None
            ikb.custom_shape_rotation_euler = ik_shape_rotation_for_source(ikb, source_deform or fkb)

            ptb.custom_shape = pole_shape
            ptb.custom_shape_scale_xyz *= self.scale / 0.03048
            # ptb.use_custom_shape_bone_size = True
            ptb.custom_shape_translation = Vector((0.0, 0.0, 0.0))
            ptb.custom_shape_rotation_euler = Vector((0.0, 0.0, 0.0))

            if settings_pb is not None and root_control is not None:
                prop_name = ik_root_follow_property_name(fkb_name)
                add_root_child_of_constraint(ikb, self.rig_ob, root_control.name, prop_name)
                add_root_child_of_constraint(ptb, self.rig_ob, root_control.name, prop_name)
            
            clear_matching_constraints(
                fkb,
                ik_constraint_name,
                'IK',
                self.rig_ob,
                ikb_name,
            )
            con = cast(bpy.types.Constraint, fkb.constraints.new('IK'))
            con.name = ik_constraint_name
            con.target = self.rig_ob
            con.subtarget = ikb_name
            con.chain_count = fk_ik_chain_count(fkb)
            con.use_tail = False
            
            con.pole_target = self.rig_ob
            con.pole_subtarget = pt_name
            con.pole_angle = angle
            con.influence = 0.0
            if settings_pb is not None:
                add_ik_control_prop_driver(con, self.rig_ob, ik_control_property_name(fkb_name))

            clear_matching_constraints(
                fkb,
                ik_copy_rotation_constraint_name,
                'COPY_ROTATION',
                self.rig_ob,
                ikb_name,
            )
            con = cast(bpy.types.Constraint, fkb.constraints.new('COPY_ROTATION'))
            con.name = ik_copy_rotation_constraint_name
            con.target = self.rig_ob
            con.subtarget = ikb_name
            con.influence = 0.0
            if settings_pb is not None:
                add_ik_control_prop_driver(con, self.rig_ob, ik_control_property_name(fkb_name))
            
def fk_ik_chain_count(fkb: bpy.types.PoseBone):
    count = 0
    while fkb.parent is not None:
        parent = fkb.parent
        if parent.name.startswith("FK_"):
            count += 1
            fkb = parent
        else:
            break
        
    return count

def add_settings_control_prop_driver(con: bpy.types.Constraint, rig_ob: bpy.types.Object, prop_name: str, multiplier=1.0, invert=False):
    driver = con.driver_add("influence").driver
    driver.type = 'SCRIPTED'

    control_var = driver.variables.new()
    control_var.name = "control_value"
    control_var.type = 'SINGLE_PROP'
    control_target = control_var.targets[0]
    control_target.id = rig_ob
    control_target.data_path = f'pose.bones["{settings_control_name}"]["{prop_name}"]'

    if invert:
        driver.expression = f"min(max(1 - control_value, 0.0), 1.0) * {multiplier:.6f}"
    else:
        driver.expression = f"min(max(control_value, 0.0), 1.0) * {multiplier:.6f}"

def add_ik_control_prop_driver(con: bpy.types.Constraint, rig_ob: bpy.types.Object, prop_name: str):
    add_settings_control_prop_driver(con, rig_ob, prop_name)

def add_root_child_of_constraint(pbone: bpy.types.PoseBone, rig_ob: bpy.types.Object, root_name: str, prop_name: str):
    settings_bone = rig_ob.pose.bones.get(settings_control_name)
    if settings_bone is not None:
        ensure_settings_float_prop(
            settings_bone,
            prop_name,
            f"How much {pbone.name} ignores the root bone",
        )

    clear_matching_constraints(
        pbone,
        root_child_of_constraint_name,
        'CHILD_OF',
        rig_ob,
        root_name,
    )
    con = cast(bpy.types.Constraint, pbone.constraints.new('CHILD_OF'))
    con.name = root_child_of_constraint_name
    con.target = rig_ob
    con.subtarget = root_name
    con.influence = 1.0
    con.set_inverse_pending = True
    if settings_bone is not None:
        add_settings_control_prop_driver(con, rig_ob, prop_name, invert=True)

def get_bone_collection(armature_data: bpy.types.Armature, name: str):
    collections_all = getattr(armature_data, "collections_all", None)
    if collections_all is not None:
        return collections_all.get(name)

    return armature_data.collections.get(name)

def ensure_top_level_bone_collection(armature_data: bpy.types.Armature, name: str):
    collection = get_bone_collection(armature_data, name)
    if collection is None:
        collection = armature_data.collections.new(name)
    else:
        collection.parent = None

    return collection

def unparent_legacy_bone_collection_groups(armature_data: bpy.types.Armature):
    for name in ("Deform Bones", "Deform"):
        collection = get_bone_collection(armature_data, name)
        if collection is None:
            continue

        for child in tuple(collection.children):
            child.parent = None

def clear_foundry_bone_collection_assignments(armature_data: bpy.types.Armature):
    collections = tuple(
        collection
        for collection in (get_bone_collection(armature_data, name) for name in foundry_bone_collection_names)
        if collection is not None
    )
    if not collections:
        return

    for bone in armature_data.bones:
        for collection in collections:
            collection.unassign(bone)

def remove_empty_bone_collection(armature_data: bpy.types.Armature, name: str):
    collection = get_bone_collection(armature_data, name)
    if collection is None or len(collection.children) or len(collection.bones):
        return

    collection.parent = None
    armature_data.collections.remove(collection)

def face_deform_bone_names(armature_data: bpy.types.Armature) -> set[str]:
    head_bone = find_deform_data_bone_by_suffix(armature_data, "head")
    if head_bone is None:
        return set()

    names = set()
    collect_deform_descendant_bone_names(head_bone, names)
    return names

def find_deform_data_bone_by_suffix(armature_data: bpy.types.Armature, suffix: str) -> bpy.types.Bone | None:
    for bone in armature_data.bones:
        if bone.use_deform and bone_name_matches_suffix(bone.name, suffix):
            return bone

def collect_deform_descendant_bone_names(bone: bpy.types.Bone, names: set[str]):
    for child in bone.children:
        if child.use_deform:
            names.add(child.name)
        collect_deform_descendant_bone_names(child, names)

def vertex_group_bounds_by_deform_bone(arm: bpy.types.Object, rig_pose: bpy.types.Pose, bone_names: set[str]) -> dict[str, tuple[Vector, Vector]]:
    if not bone_names:
        return {}

    bone_inverses = {}
    for bone_name in bone_names:
        pbone = rig_pose.bones.get(bone_name)
        if pbone is not None:
            bone_inverses[bone_name] = pbone.bone.matrix_local.inverted_safe()

    if not bone_inverses:
        return {}

    hard_bounds = {}
    soft_bounds = {}
    armature_inv = arm.matrix_world.inverted_safe()
    bone_name_lookup = deform_bone_vertex_group_lookup(bone_inverses)

    for ob in bpy.data.objects:
        if not mesh_uses_armature_vertex_groups(ob, arm):
            continue

        group_to_bone = {}
        for group in ob.vertex_groups:
            bone_name = deform_bone_name_from_vertex_group(group.name, bone_inverses, bone_name_lookup)
            if bone_name is not None:
                group_to_bone[group.index] = bone_name

        if not group_to_bone:
            continue

        mesh_to_armature = armature_inv @ ob.matrix_world
        for vert in ob.data.vertices:
            if not vert.groups:
                continue

            armature_co = mesh_to_armature @ vert.co
            for group_weight in vert.groups:
                bone_name = group_to_bone.get(group_weight.group)
                if bone_name is None or group_weight.weight <= 0.001:
                    continue

                local_co = bone_inverses[bone_name] @ armature_co
                if group_weight.weight >= 0.8:
                    update_bounds(hard_bounds, bone_name, local_co)
                else:
                    update_bounds(soft_bounds, bone_name, local_co)

    for bone_name, bounds in soft_bounds.items():
        if bone_name not in hard_bounds:
            hard_bounds[bone_name] = bounds

    return hard_bounds

def deform_bone_vertex_group_lookup(bone_inverses: dict[str, Matrix]) -> dict[str, str]:
    aliases = defaultdict(set)
    for bone_name in bone_inverses:
        for alias in deform_bone_vertex_group_aliases(bone_name):
            aliases[alias].add(bone_name)

    return {
        alias: next(iter(matches))
        for alias, matches in aliases.items()
        if len(matches) == 1
    }

def deform_bone_vertex_group_aliases(name: str) -> set[str]:
    aliases = {name, name.casefold()}
    stripped = utils.remove_node_prefix(name)
    aliases.add(stripped)
    aliases.add(stripped.casefold())
    normalized = normalized_bone_name(name)
    aliases.add(normalized)
    aliases.add(normalized.casefold())
    return {alias for alias in aliases if alias}

def deform_bone_name_from_vertex_group(group_name: str, bone_inverses: dict[str, Matrix], lookup: dict[str, str]) -> str | None:
    if group_name in bone_inverses:
        return group_name

    for alias in deform_bone_vertex_group_aliases(group_name):
        bone_name = lookup.get(alias)
        if bone_name is not None:
            return bone_name

def mesh_uses_armature_vertex_groups(ob: bpy.types.Object, arm: bpy.types.Object) -> bool:
    if ob.type != 'MESH' or not ob.data.vertices or not ob.vertex_groups:
        return False

    if ob.parent == arm:
        return True

    for mod in ob.modifiers:
        if mod.type == 'ARMATURE' and mod.object == arm and mod.use_vertex_groups:
            return True

    return ob.find_armature() == arm

def update_bounds(bounds: dict[str, tuple[Vector, Vector]], bone_name: str, co: Vector):
    existing = bounds.get(bone_name)
    if existing is None:
        bounds[bone_name] = co.copy(), co.copy()
        return

    min_co, max_co = existing
    min_co.x = min(min_co.x, co.x)
    min_co.y = min(min_co.y, co.y)
    min_co.z = min(min_co.z, co.z)
    max_co.x = max(max_co.x, co.x)
    max_co.y = max(max_co.y, co.y)
    max_co.z = max(max_co.z, co.z)

def fallback_deform_shape_transform(pbone: bpy.types.PoseBone, rig_shape_scale: float) -> tuple[Vector, Vector]:
    bone_length = max(pbone.length, 0.01)
    thickness = max(bone_length * 0.12, rig_shape_scale * 0.005, 0.005)
    return Vector((thickness, bone_length * 0.5, thickness)), Vector((0.0, bone_length * 0.5, 0.0))

def deform_shape_transform_from_bounds(bounds: tuple[Vector, Vector], bone_length: float, fallback_scale: Vector, fallback_translation: Vector) -> tuple[Vector, Vector]:
    min_co, max_co = bounds
    dimensions = max_co - min_co
    if max(dimensions.x, dimensions.y, dimensions.z) < 1e-6:
        return fallback_scale, fallback_translation

    half_extents = dimensions * 0.55
    largest_extent = max(half_extents.x, half_extents.y, half_extents.z)
    min_half_extent = max(largest_extent * 0.08, bone_length * 0.025, 0.005)
    half_extents.x = max(half_extents.x, min_half_extent)
    half_extents.y = max(half_extents.y, min_half_extent)
    half_extents.z = max(half_extents.z, min_half_extent)

    return half_extents, (min_co + max_co) * 0.5

def is_foundry_deform_custom_shape(shape: bpy.types.Object) -> bool:
    names = {shape.name}
    if shape.data is not None:
        names.add(shape.data.name)

    for name in names:
        if name == deform_shape_name or name.startswith(f"{deform_shape_name}."):
            return True
        if name == "halo_deform_bone_shape" or name.startswith("halo_deform_bone_shape."):
            return True

    return False


def predict_tail_from_previous(previous_fk_bone, current_edit_bone):
    if previous_fk_bone is None:
        return current_edit_bone.tail.copy()

    direction = previous_fk_bone.tail - previous_fk_bone.head
    prev_len = direction.length

    if prev_len < 1e-6:
        return current_edit_bone.tail.copy()

    direction.normalize()

    return current_edit_bone.head + direction

def point_bone_tail_global_up(edit_bone: bpy.types.EditBone, length: float | None = None):
    length = edit_bone.length if length is None else length
    edit_bone.tail = edit_bone.head + Vector((0.0, 0.0, max(length, 0.01)))
    edit_bone.roll = 0.0

def align_edit_bone_roll_to_source(target_bone: bpy.types.EditBone, source_bone: bpy.types.EditBone):
    target_y = target_bone.y_axis.copy()
    if target_y.length < 1e-6:
        target_bone.roll = source_bone.roll
        return

    target_y.normalize()
    source_axis = source_bone.z_axis.copy()
    roll_axis = source_axis - target_y * source_axis.dot(target_y)

    if roll_axis.length < 1e-6:
        source_axis = source_bone.x_axis.copy()
        roll_axis = source_axis - target_y * source_axis.dot(target_y)

    if roll_axis.length < 1e-6:
        target_bone.roll = source_bone.roll
        return

    roll_axis.normalize()
    target_bone.align_roll(roll_axis)

def calculate_pole_position(root_bone: bpy.types.EditBone, mid_bone: bpy.types.EditBone, end_bone: bpy.types.EditBone, distance_scale=1.25):
    a = root_bone.head.copy()
    b = mid_bone.head.copy()
    c = end_bone.head.copy()

    ac = c - a
    if ac.length < 1e-6:
        return b.copy()

    ac_dir = ac.normalized()
    projection = a + ac_dir * ((b - a).dot(ac_dir))
    pole_dir = b - projection

    # Straight chains do not define a bend plane, so fall back to the joint axes.
    if pole_dir.length < 1e-6:
        pole_dir = mid_bone.x_axis.copy()
        if pole_dir.length < 1e-6:
            pole_dir = mid_bone.z_axis.copy()
        if pole_dir.length < 1e-6:
            pole_dir = Vector((0.0, 0.0, 1.0))

    pole_dir.normalize()
    dist = max((b - a).length, (c - b).length) * distance_scale
    return b + pole_dir * dist

def calculate_lateral_pole_position(rig_root: bpy.types.EditBone, root_bone: bpy.types.EditBone, mid_bone: bpy.types.EditBone, end_bone: bpy.types.EditBone, distance_scale=1.25):
    chain_axis = end_bone.head - root_bone.head
    pole_dir = root_bone.head - rig_root.head

    if chain_axis.length >= 1e-6:
        chain_axis.normalize()
        pole_dir -= chain_axis * pole_dir.dot(chain_axis)

    if pole_dir.length < 1e-6:
        return calculate_pole_position(root_bone, mid_bone, end_bone, distance_scale)

    pole_dir.normalize()
    dist = max((mid_bone.head - root_bone.head).length, (end_bone.head - mid_bone.head).length) * distance_scale
    return mid_bone.head + pole_dir * dist

def calculate_pole_angle(root_bone: bpy.types.EditBone, end_bone: bpy.types.EditBone, pole_position: Vector, use_tail=False) -> float:
    root_axis = root_bone.tail - root_bone.head
    chain_end = end_bone.tail if use_tail else end_bone.head
    chain_axis = chain_end - root_bone.head
    pole_axis = pole_position - root_bone.head

    if root_axis.length < 1e-6 or chain_axis.length < 1e-6 or pole_axis.length < 1e-6:
        return 0.0

    pole_normal = chain_axis.cross(pole_axis)
    if pole_normal.length < 1e-6:
        return 0.0

    projected_pole_axis = pole_normal.cross(root_axis)
    if projected_pole_axis.length < 1e-6:
        return 0.0

    root_axis.normalize()
    projected_pole_axis.normalize()
    reference_axis = root_bone.x_axis.normalized()

    return -atan2(
        root_axis.dot(reference_axis.cross(projected_pole_axis)),
        reference_axis.dot(projected_pole_axis),
    )

def is_descendant(bone: bpy.types.PoseBone, ancestor: bpy.types.PoseBone) -> bool:
    parent = bone.parent
    while parent:
        if parent == ancestor:
            return True
        parent = parent.parent
    return False

def clear_copy_transforms(pbone):
    for con in reversed(pbone.constraints):
        if con.type == 'COPY_TRANSFORMS':
            pbone.constraints.remove(con)

def get_or_create_shape(shape_name, vert_coords, edges):
    shape = bpy.data.objects.get(shape_name)
    if shape is None:
        shape_data = bpy.data.meshes.new(shape_name)
        shape_data.from_pydata(
            vertices=[Vector(co) for co in vert_coords],
            edges=edges,
            faces=[],
        )
        shape = bpy.data.objects.new(shape_name, shape_data)
        shape.nwo.export_this = False

    return shape

def get_or_create_fk_control_shape():
    shape = bpy.data.objects.get(fk_control_shape_name)
    if shape is None:
        verts, edges = fk_control_shape_data()
        shape_data = bpy.data.meshes.new(fk_control_shape_name)
        shape_data.from_pydata(verts, edges, [])
        shape = bpy.data.objects.new(fk_control_shape_name, shape_data)
        shape.nwo.export_this = False

    return shape

def fk_control_shape_data(segments=32, radius=0.45):
    verts = []
    edges = []

    # for plane in ("xy", "xz", "yz"):
    for plane in ("xz",):
        start = len(verts)
        for idx in range(segments):
            angle = tau * idx / segments
            a = cos(angle) * radius
            b = sin(angle) * radius
            if plane == "xy":
                verts.append((a, b, 0.0))
            elif plane == "xz":
                verts.append((a, 0.0, b))
            else:
                verts.append((0.0, a, b))

        for idx in range(segments):
            edges.append([start + idx, start + ((idx + 1) % segments)])

    return verts, edges

def apply_fk_control_shapes(rig_pose: bpy.types.Pose, fk_bone_names: list[str], shape: bpy.types.Object):
    for name in dict.fromkeys(fk_bone_names):
        if not is_fk_control_bone(name):
            continue

        pbone = rig_pose.bones.get(name)
        if pbone is None:
            continue

        pbone.color.palette = 'THEME07'
        pbone.custom_shape = shape
        source_name = name[3:] if name.startswith("FK_") else name
        shape_scale = 2.2 if bone_name_matches_suffix(source_name, "hand") else 1.0
        pbone.custom_shape_scale_xyz = Vector.Fill(3, shape_scale)
        pbone.custom_shape_translation = Vector((0.0, pbone.length * 0.5, 0.0))
        pbone.custom_shape_rotation_euler = Vector((0.0, 0.0, 0.0))
        pbone.use_custom_shape_bone_size = True

def apply_torso_control_shapes(rig_pose: bpy.types.Pose, deform_fk_mapping: dict[str, str], shape_scale: float):
    pelvis_shape = None
    torso_shape = None
    if shape_scale <= 0:
        shape_scale = 1.0

    pelvis_shape_rotation = Vector((radians(90), 0, radians(180)))
    spine_shape_rotation = Vector((radians(90), radians(90), 0))

    for deform_name, fk_name in deform_fk_mapping.items():
        pbone = rig_pose.bones.get(fk_name)
        if pbone is None:
            continue

        if bone_name_matches_suffix(deform_name, "pelvis"):
            if pelvis_shape is None:
                pelvis_shape = get_or_create_shape(pelvis_shape_name, pelvis_shape_vert_coords, pelvis_shape_edges)

            apply_control_shape(pbone, pelvis_shape, shape_scale * 2.0, 'THEME07', pelvis_shape_rotation)
        elif is_spine_deform_bone_name(deform_name):
            if torso_shape is None:
                torso_shape = get_or_create_shape(torso_shape_name, torso_shape_vert_coords, torso_shape_edges)

            apply_control_shape(pbone, torso_shape, shape_scale * 1.5, 'THEME07', spine_shape_rotation)

def apply_settings_control_shape(pbone: bpy.types.PoseBone, shape: bpy.types.Object):
    pbone.color.palette = 'THEME01'
    pbone.custom_shape = shape
    pbone.custom_shape_scale_xyz = Vector.Fill(3, 1.0)
    pbone.custom_shape_rotation_euler = Vector((0.0, 0.0, radians(90)))
    pbone.use_custom_shape_bone_size = True

def apply_control_shape(pbone: bpy.types.PoseBone, shape: bpy.types.Object, scale: float, palette='THEME04', rotation=Vector((0.0, 0.0, 0.0)), translation= Vector((0.0, 0.0, 0.0)), use_bone_size=False):
    pbone.color.palette = palette
    pbone.custom_shape = shape
    pbone.custom_shape_scale_xyz = Vector.Fill(3, scale)
    pbone.custom_shape_translation = translation
    pbone.custom_shape_rotation_euler = rotation
    pbone.use_custom_shape_bone_size = use_bone_size

def ik_shape_rotation_for_source(ik_bone: bpy.types.PoseBone, source_bone: bpy.types.PoseBone) -> Vector:
    if is_foot_ik_source_name(ik_bone.name):
        return flat_foot_ik_shape_rotation(ik_bone.bone, source_bone.bone)

    roll = roll_angle_between_bone_planes(ik_bone.bone, source_bone.bone)
    return Vector((0.0, roll, 0.0))

def is_ik_endpoint_fk_name(name: str) -> bool:
    if not is_fk_control_bone(name):
        return False

    source_name = name[3:]
    return any(bone_name_matches_suffix(source_name, suffix) for suffix in ik_endpoint_bone_suffixes)

def flat_foot_ik_shape_rotation(ik_bone: bpy.types.Bone, source_bone: bpy.types.Bone) -> Vector:
    up = Vector((0.0, 0.0, 1.0))
    forward = projected_axis(bone_local_axis(source_bone, Vector((0.0, 1.0, 0.0))), up)
    if forward is None:
        forward = projected_axis(bone_local_axis(ik_bone, Vector((0.0, 1.0, 0.0))), up)
    if forward is None:
        forward = Vector((0.0, 1.0, 0.0))

    forward.normalize()
    side = forward.cross(up)
    if side.length < 1e-6:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    forward = up.cross(side)
    forward.normalize()

    desired_shape_orientation = Matrix((side, forward, up)).transposed()
    shape_rotation = ik_bone.matrix_local.to_3x3().inverted_safe() @ desired_shape_orientation
    return Vector(shape_rotation.to_euler())

def is_foot_ik_source_name(name: str) -> bool:
    if name.startswith(("FK_", "IK_", "PT_")):
        name = name[3:]

    return any(bone_name_matches_suffix(name, suffix) for suffix in ("foot", "tarsus", "toe_atr_u"))

def roll_angle_between_bone_planes(owner_bone: bpy.types.Bone, source_bone: bpy.types.Bone) -> float:
    owner_y = bone_local_axis(owner_bone, Vector((0.0, 1.0, 0.0)))
    owner_z = bone_local_axis(owner_bone, Vector((0.0, 0.0, 1.0)))
    source_z = bone_local_axis(source_bone, Vector((0.0, 0.0, 1.0)))
    target_z = projected_axis(source_z, owner_y)

    if target_z is None:
        source_x = bone_local_axis(source_bone, Vector((1.0, 0.0, 0.0)))
        target_z = projected_axis(source_x, owner_y)

    current_z = projected_axis(owner_z, owner_y)
    if current_z is None or target_z is None:
        return 0.0

    return atan2(current_z.cross(target_z).dot(owner_y), current_z.dot(target_z))

def bone_local_axis(bone: bpy.types.Bone, axis: Vector) -> Vector:
    result = bone.matrix_local.to_3x3() @ axis
    if result.length < 1e-6:
        return axis.copy()

    result.normalize()
    return result

def projected_axis(axis: Vector, normal: Vector) -> Vector | None:
    projected = axis - normal * axis.dot(normal)
    if projected.length < 1e-6:
        return None

    projected.normalize()
    return projected

def clear_neck_assist_constraints(head_driver: bpy.types.PoseBone):
    if not is_fk_control_bone(head_driver.name):
        return

    neck_bone = head_driver.parent
    while neck_bone is not None and is_neck_control_bone_name(neck_bone.name):
        for con in reversed(neck_bone.constraints):
            if con.name == neck_assist_constraint_name or con.name.startswith(f"{neck_assist_constraint_name}."):
                neck_bone.constraints.remove(con)
        neck_bone = neck_bone.parent

def ensure_control_bone(edit_bones, name: str) -> bpy.types.EditBone:
    bone = edit_bones.get(name)
    if bone is None:
        bone = edit_bones.new(name)

    bone.use_deform = False
    bone.use_connect = False
    return bone

def copy_edit_bone_transform(target: bpy.types.EditBone, source: bpy.types.EditBone):
    target.head = source.head.copy()
    target.tail = source.tail.copy()
    target.roll = source.roll

def match_edit_bone_length(target: bpy.types.EditBone, source: bpy.types.EditBone):
    target.length = max(source.length, 0.01)

def ensure_settings_control_bone(edit_bones, root: bpy.types.EditBone, scale: float) -> bpy.types.EditBone:
    bone = ensure_control_bone(edit_bones, settings_control_name)
    bone.matrix = root.matrix.copy()
    bone.length = max(root.length, 0.01)
    offset = Vector((0.0, (-2 / 0.03048) * scale, 0.0))
    bone.head += offset
    bone.tail += offset
    bone.parent = root
    bone.use_connect = False
    bone.use_deform = False
    return bone

def place_front_control_bone(
    control_bone: bpy.types.EditBone,
    root: bpy.types.EditBone,
    height_source: bpy.types.EditBone,
    scale: float,
    parent: bpy.types.EditBone | None,
    length_source: bpy.types.EditBone | float | None = None,
) -> bpy.types.EditBone:
    control_bone.matrix = root.matrix.copy()
    if hasattr(length_source, "length"):
        source_length = length_source.length
    elif isinstance(length_source, (int, float)):
        source_length = length_source
    else:
        source_length = height_source.length

    control_bone.length = max(source_length * 0.35, 0.01)
    bone_axis = control_bone.tail - control_bone.head
    offset = Vector((0.0, (-2 / 0.03048) * scale, 0.0))
    control_bone.head = height_source.head + offset
    control_bone.tail = control_bone.head + bone_axis

    control_bone.parent = parent
    control_bone.use_connect = False
    control_bone.use_deform = False
    return control_bone

def remove_legacy_fk_ik_slider_bones(edit_bones):
    for legacy_name in (fk_ik_slider_bone_name, fk_ik_switch_bone_name):
        for name in [bone.name for bone in edit_bones if bone.name == legacy_name or bone.name.startswith(f"{legacy_name}.")]:
            bone = edit_bones.get(name)
            if bone is not None:
                edit_bones.remove(bone)

def ensure_ik_control_props(settings_bone: bpy.types.PoseBone, fk_ik_mapping: dict[str, tuple[str, str, float]]):
    for fkb_name in fk_ik_mapping:
        prop_name = ik_control_property_name(fkb_name)
        ensure_settings_float_prop(settings_bone, prop_name, f"IK influence for {fkb_name}")
        ensure_settings_float_prop(
            settings_bone,
            ik_root_follow_property_name(fkb_name),
            f"How much {fkb_name.replace('FK_', 'IK_', 1)} ignores the root bone",
        )

def ensure_look_control_props(
    settings_bone: bpy.types.PoseBone,
    has_head_control: bool,
    has_look_control: bool,
    has_eye_controls: bool,
):
    if has_head_control:
        ensure_settings_float_prop(
            settings_bone,
            head_track_prop_name,
            f"How much the head tracks {head_control_name}",
        )
        ensure_settings_float_prop(
            settings_bone,
            head_follow_root_prop_name,
            f"How much {head_control_name} ignores the root bone",
        )
    else:
        remove_settings_prop(settings_bone, head_track_prop_name)
        remove_settings_prop(settings_bone, head_follow_root_prop_name)

    if has_look_control:
        ensure_settings_float_prop(
            settings_bone,
            look_follow_root_prop_name,
            f"How much {look_control_name} ignores the root bone",
        )
    else:
        remove_settings_prop(settings_bone, look_follow_root_prop_name)

    if has_look_control and has_head_control:
        ensure_settings_float_prop(
            settings_bone,
            look_follow_head_prop_name,
            f"How much {look_control_name} ignores {head_control_name}",
        )
    else:
        remove_settings_prop(settings_bone, look_follow_head_prop_name)

    if has_eye_controls:
        ensure_settings_float_prop(
            settings_bone,
            eye_track_prop_name,
            f"How much the eyes track {look_control_name}",
        )
    else:
        remove_settings_prop(settings_bone, eye_track_prop_name)

def ensure_gun_control_props(settings_bone: bpy.types.PoseBone):
    ensure_settings_float_prop(
        settings_bone,
        gun_control_prop_name,
        f"How much {gun_bone_name} copies {gun_control_name}",
    )

def ik_root_follow_property_name(fkb_name: str) -> str:
    return f"{ik_control_property_name(fkb_name)} ignore root"

def remove_settings_prop(settings_bone: bpy.types.PoseBone, prop_name: str):
    if prop_name in settings_bone:
        del settings_bone[prop_name]

def ensure_settings_float_prop(settings_bone: bpy.types.PoseBone, prop_name: str, description: str, default=0.0):
    if prop_name not in settings_bone:
        settings_bone[prop_name] = default

    settings_bone.id_properties_ui(prop_name).update(
        min=0.0,
        max=1.0,
        soft_min=0.0,
        soft_max=1.0,
        description=description,
    )

def ik_control_property_name(fkb_name: str) -> str:
    name = fkb_name[3:] if fkb_name.startswith("FK_") else fkb_name
    name = name.replace(".L", "_l").replace(".R", "_r")
    name = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")
    while "__" in name:
        name = name.replace("__", "_")

    return f"IK {name}"

def is_torso_deform_bone_name(name: str) -> bool:
    if is_control_bone_name(name):
        return False

    return any(bone_name_matches_suffix(name, suffix) for suffix in bones_to_add_fk)

def is_spine_deform_bone_name(name: str) -> bool:
    return any(bone_name_matches_suffix(name, suffix) for suffix in ("spine", "spine1", "spine2", "spine3", "chest"))

def place_target_control_bone(
    control_bone: bpy.types.EditBone,
    source_bone: bpy.types.EditBone,
    parent: bpy.types.EditBone,
    direction: Vector | None = None,
    offset=0.0,
):
    direction = bone_direction(source_bone, direction)

    direction.normalize()
    length = max(source_bone.length * 0.35, 0.01)
    control_bone.head = source_bone.tail.copy() + direction * offset
    control_bone.tail = control_bone.head + direction * length
    control_bone.roll = source_bone.roll
    control_bone.parent = parent
    control_bone.use_connect = False
    control_bone.use_deform = False

def place_average_target_control_bone(
    control_bone: bpy.types.EditBone,
    source_bones: list[bpy.types.EditBone],
    parent: bpy.types.EditBone,
    direction: Vector | None = None,
    offset=0.0,
):
    head = Vector((0.0, 0.0, 0.0))
    average_direction = Vector((0.0, 0.0, 0.0))
    length = 0.0

    for bone in source_bones:
        head += bone.tail
        average_direction += bone_direction(bone)
        length += bone.length

    head /= len(source_bones)
    direction = direction.copy() if direction is not None else average_direction
    if direction.length < 1e-6:
        direction = bone_direction(source_bones[0])

    direction.normalize()
    length = max((length / len(source_bones)) * 0.35, 0.01)
    control_bone.head = head + direction * offset
    control_bone.tail = control_bone.head + direction * length
    control_bone.parent = parent
    control_bone.use_connect = False
    control_bone.use_deform = False

def bone_direction(bone: bpy.types.EditBone, fallback: Vector | None = None) -> Vector:
    direction = fallback.copy() if fallback is not None else bone.y_axis.copy()
    if direction.length < 1e-6:
        direction = bone.y_axis.copy()
    if direction.length < 1e-6:
        direction = bone.tail - bone.head
    if direction.length < 1e-6:
        direction = Vector((0.0, 1.0, 0.0))

    return direction

def control_forward_direction(forward: str) -> Vector:
    direction = Vector(globals()[f"bone_{forward.replace('-', '_negative')}"])
    if direction.length < 1e-6:
        return Vector((0.0, 1.0, 0.0))

    return direction.normalized()

def clear_matching_constraints(
    pbone: bpy.types.PoseBone,
    constraint_name: str,
    constraint_type: str,
    target: bpy.types.Object | None = None,
    subtarget: str | None = None,
):
    for con in reversed(pbone.constraints):
        name_matches = con.name == constraint_name or con.name.startswith(f"{constraint_name}.")
        target_matches = target is None or getattr(con, "target", None) == target
        subtarget_matches = subtarget is None or getattr(con, "subtarget", None) == subtarget
        if name_matches or (con.type == constraint_type and target_matches and subtarget_matches):
            pbone.constraints.remove(con)

def get_head_driver_bone_name(arm: bpy.types.Object, head_deform_name: str | None, deform_fk_mapping: dict[str, str]) -> str | None:
    if head_deform_name:
        fk_name = deform_fk_mapping.get(head_deform_name)
        if fk_name and arm.pose.bones.get(fk_name):
            return fk_name

    fk_name = find_fk_pose_bone_name_by_suffix(arm, "head")
    if fk_name:
        return fk_name

    return head_deform_name

def find_fk_pose_bone_name_by_suffix(arm: bpy.types.Object, suffix: str) -> str | None:
    for pbone in arm.pose.bones:
        if pbone.name.startswith("FK_") and bone_name_matches_suffix(pbone.name[3:], suffix):
            return pbone.name

def find_deform_pose_bone_name_by_suffix(arm: bpy.types.Object, suffix: str) -> str | None:
    names = find_deform_pose_bone_names_by_suffix(arm, suffix)
    if names:
        return names[0]

def find_deform_pose_bone_names_by_suffix(arm: bpy.types.Object, suffix: str) -> list[str]:
    names = []
    for pbone in arm.pose.bones:
        bone = arm.data.bones.get(pbone.name)
        if bone is None or not bone.use_deform or is_control_bone_name(pbone.name):
            continue
        if bone_name_matches_suffix(pbone.name, suffix):
            names.append(pbone.name)

    return names

def choose_eye_bone_names(eye_bone_names: list[str]) -> list[str]:
    if len(eye_bone_names) <= 2:
        return eye_bone_names

    lateral_eye_bones = [name for name in eye_bone_names if is_lateral_bone_name(name)]
    if len(lateral_eye_bones) >= 2:
        return lateral_eye_bones[:2]

    return eye_bone_names[:2]

def find_pose_bone_name_by_node_names(arm: bpy.types.Object, node_names: tuple[str, ...]) -> str | None:
    lower_names = tuple(name.lower() for name in node_names)
    for pbone in arm.pose.bones:
        if pbone.name.lower() in lower_names:
            return pbone.name

    normalized_names = tuple(normalized_bone_name(name) for name in node_names)
    for pbone in arm.pose.bones:
        if normalized_bone_name(pbone.name) in normalized_names:
            return pbone.name

def bone_name_matches_suffix(name: str, suffix: str) -> bool:
    base_name = normalized_bone_name(name)
    suffix = suffix.lower()
    return (
        base_name == suffix or
        base_name.endswith(f"_{suffix}") or
        base_name.endswith(f" {suffix}") or
        base_name.endswith(f".{suffix}")
    )

def normalized_bone_name(name: str) -> str:
    name = utils.remove_node_prefix(name).lower()
    if name.endswith((".l", ".r")):
        name = name[:-2]

    return name

def is_lateral_bone_name(name: str) -> bool:
    name = normalized_bone_name(name)
    return name.startswith(("l_", "r_", "left_", "right_")) or name.endswith(("_l", "_r"))

def is_neck_control_bone_name(name: str) -> bool:
    if is_fk_control_bone(name):
        name = name[3:]

    name = normalized_bone_name(name)
    return name == "neck" or name.startswith("neck") or name.endswith("neck") or "_neck" in name

def is_control_bone_name(name: str) -> bool:
    return name.startswith(("FK_", "IK_", "PT_", "CTRL_"))

def is_fk_control_bone(name: str) -> bool:
    legacy_slider = name == fk_ik_slider_bone_name or name.startswith(f"{fk_ik_slider_bone_name}.")
    legacy_switch = name == fk_ik_switch_bone_name or name.startswith(f"{fk_ik_switch_bone_name}.")
    return name.startswith("FK_") and not (legacy_slider or legacy_switch)
