

from collections import defaultdict
from math import atan2, radians
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

# Bone that should be connected
bone_links = (
    ("upperarm", "forearm", "hand"),
    ("thigh", "calf", "foot"),
    ("thigh", "shin", "toe_hinge", "toe"),
    ("upper_leg", "lower_leg", "tarsus"),
    ("low", "mid", "tip"),
    ("neck", "head"),
    ("neck0", "neck1", "head"),
    # ("spine", "spine1"),
    ("index1", "index2", "index3"),
    ("thumb1", "thumb2", "thumb3"),
    ("pinky1", "pinky2", "pinky3"),
    ("ring1", "ring2", "ring3"),
    ("middle1", "middle2", "middle3"),
)

bones_to_add_fk = (
    "pelvis",
    "spine",
    "spine1",
    "spine2",
    "spine3",
)

bones_for_ik = ('_foot.', '_tarsus.', '_hand.')

head_bone_name = '_head'
eyes_bone_name = '_eye'

start_link_bones = defaultdict(list)
start_link_bones_keys = tuple()

def reset_start_link_bones():
    global start_link_bones
    global start_link_bones_keys
    start_link_bones = defaultdict(list)
    for b in bone_links:
        start_link_bones[b[0]].append(iter(b[1:]))

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
        self.scale = ((1 / 0.03048) if self.scene_nwo.scale == 'max' else 1) if scale is None else scale
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
                pedestal.custom_shape_scale_xyz = Vector((1, 1, 1)) * shape_scale * self.scale
                pedestal.use_custom_shape_bone_size = False
                
                if reach_fp_fix:
                    pedestal.custom_shape_rotation_euler.x = radians(-90)
                
                # if wireframe:
                #     self.rig_data.bones[pedestal.name].show_wire = True
        
        if self.has_pose_bones:
            if not aim_control:
                aim_control: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_control_name)
            if aim_control is not None:
                if not constraints_only:
                    shape_ob = bpy.data.objects.get(aim_shape_name)
                    if shape_ob is None:
                        shape_data = bpy.data.meshes.new(aim_shape_name)
                        verts = [Vector(co) for co in aim_shape_vert_coords]
                        shape_data.from_pydata(vertices=verts, edges=aim_shape_edges, faces=[])
                        shape_ob = bpy.data.objects.new(aim_shape_name, shape_data)
                        shape_ob.nwo.export_this = False
                    
                    aim_control.color.palette = 'THEME04'
                    aim_control.custom_shape = shape_ob
                    aim_control.custom_shape_scale_xyz = Vector((1, 1, 1)) * shape_scale * self.scale
                    aim_control.use_custom_shape_bone_size = False
                
                    if reach_fp_fix:
                        aim_control.custom_shape_rotation_euler.z = radians(90)
                    
                    # if wireframe:
                    #     self.rig_data.bones[aim_control.name].show_wire = True
                
                if not pitch:
                    pitch: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_pitch_name)
                else:
                    pitch = self.rig_ob.pose.bones.get(pitch)
                    
                if pitch is None:
                    pitch: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_pitch_name)
                    
                if not yaw:
                    yaw: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_yaw_name)
                else:
                    yaw = self.rig_ob.pose.bones.get(yaw)
                    
                if yaw is None:
                    yaw: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_yaw_name)
                    
                if not (pedestal or pitch or yaw or aim_control):
                    return
                
                if not constraints_only:
                    if pitch:
                        pitch.color.palette = 'THEME04'
                        pitch.custom_shape = shape_ob
                        pitch.custom_shape_scale_xyz = Vector((0.2, 0.2, 0.2)) * shape_scale * self.scale
                        pitch.use_custom_shape_bone_size = False
                        if not reach_fp_fix:
                            pitch.custom_shape_rotation_euler.x = radians(90)
                        
                        # if wireframe:
                        #     self.rig_data.bones[pitch.name].show_wire = True
                            
                    if yaw:
                        yaw.color.palette = 'THEME04'
                        yaw.custom_shape = shape_ob
                        yaw.custom_shape_scale_xyz = Vector((0.2, 0.2, 0.2)) * shape_scale * self.scale
                        yaw.use_custom_shape_bone_size = False
                        
                        if reach_fp_fix:
                            yaw.custom_shape_rotation_euler.x = radians(90)
                        
                        # if wireframe:
                        #     self.rig_data.bones[yaw.name].show_wire = True
                        
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
        bpy.ops.object.editmode_toggle()
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
            aim_control.tail = bone_tail

        bpy.ops.object.editmode_toggle()
                
    def make_parent(self, child_bone_name):
        bpy.ops.object.editmode_toggle()
        pedestal = self.rig_data.edit_bones.get(pedestal_name)
        child_bone = self.rig_data.edit_bones.get(child_bone_name)
        child_bone.parent = pedestal
        bpy.ops.object.editmode_toggle()
    
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
        bone_collections = self.rig_data.collections
        halo_collection = bone_collections.get("Deform")
        
        if halo_collection is None:
            halo_collection = bone_collections.new("Deform Bones")
            
        halo_free = bone_collections.get("Free Deform Bones")
        if halo_free is None:
            halo_free = bone_collections.new("Free Deform Bones", parent=halo_collection)
            
        halo_controlled = bone_collections.get("Controlled Deform Bones")
        if halo_controlled is None:
            halo_controlled = bone_collections.new("Controlled Deform Bones", parent=halo_collection)
            
        halo_helpers = bone_collections.get("Helper Deform Bones")
        if halo_helpers is None:
            halo_helpers = bone_collections.new("Helper Deform Bones", parent=halo_collection)
            
        pedestal_aim_collection = bone_collections.get("Pedestal & Aim Bones")
        if pedestal_aim_collection is None:
            pedestal_aim_collection = bone_collections.new("Pedestal & Aim Bones")
            
        fk_collection = bone_collections.get("FK")
        if fk_collection is None:
            fk_collection = bone_collections.new("FK")
            
        fk_collection = bone_collections.get("FK")
        if fk_collection is None:
            fk_collection = bone_collections.new("FK")

        ik_collection = bone_collections.get("IK")
        if ik_collection is None:
            ik_collection = bone_collections.new("IK")
            
        ctrl_collection = bone_collections.get("Misc Control")
        if ctrl_collection is None:
            ctrl_collection = bone_collections.new("Misc Control")
        
        for bone in self.rig_data.bones:
            no_digit_name = bone.name.strip("0123456789")
            if bone.use_deform:
                if no_digit_name.endswith(special_bones):
                    pedestal_aim_collection.assign(bone)
                elif no_digit_name.endswith(helper_bones):
                    halo_helpers.assign(bone)
                elif bone.name in self.bones_with_fk_controllers:
                    halo_controlled.assign(bone)
                else:
                    halo_free.assign(bone)
            else:
                if no_digit_name.startswith("FK_"):
                    fk_collection.assign(bone)
                elif no_digit_name.startswith(("IK_", "PT_")):
                    ik_collection.assign(bone)
                else:
                    ctrl_collection.assign(bone)
                    
        if fk_collection.bones:
            halo_controlled.is_visible = False
            halo_free.is_visible = False

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
            
        for pbone, bone in zip(self.rig_pose.bones, self.rig_data.bones):
            if pbone.custom_shape is None and bone.use_deform and (not bone.name.endswith(special_bones) and not bone.name.startswith(("FK_", "IK_", "CTRL_"))):
                pelvis_factor = 4 if bone.name.lower().endswith(("pelvis")) else 0.5
                pbone.custom_shape = shape
                pbone.custom_shape_scale_xyz = Vector((0.5, 0.5, 0.5)) * shape_scale * self.scale * pelvis_factor
                bone.show_wire = True
        
    def build_fk_ik_rig(self, reverse_controls=False, constraints_only=False):
        """Generates an FK/IK skeleton for the halo rig"""
        
        deform_fk_mapping = {}
        fk_ik_mapping = {}
        fk_bone_names = []
        ik_bone_names = []
        fk_bones_for_ik = []
        switch_bone_names = []
        switch_name = None
        slider_name = None
        
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
            for bone in self.rig_pose.bones:
                if bone.name.startswith("FK_"):
                    dbone = deform_bone_from_fk_name(bone.name)
                    if dbone is not None:
                        deform_fk_mapping[dbone.name] = bone.name
        else:
            bone_chains = []
            
            def get_chain(b: bpy.types.PoseBone, i: int):
                matched_chains = [links for k, links in start_link_bones.items() if b.name.endswith(k)]
                if not matched_chains:
                    return

                for link_tuples in matched_chains:
                    for link_chain in link_tuples:
                        chain_iter = iter(link_chain)
                        chain = [b.name]
                        next_link = next(chain_iter, None)
                        allowed_bones = set(b.children_recursive)

                        while next_link and i < len(self.rig_pose.bones):
                            next_bone = self.rig_pose.bones[i]
                            if next_bone.name.endswith(next_link) and next_bone in allowed_bones:
                                chain.append(next_bone.name)
                                processed_bones.add(next_bone.name)
                                next_link = next(chain_iter, None)
                                allowed_bones = set(next_bone.children_recursive)
                                if not next_link:
                                    break
                            i += 1

                        if len(chain) > 1:
                            bone_chains.append(chain)

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
                    
            if not bone_chains:
                return
            
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

            bpy.ops.object.editmode_toggle()
            
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

                                        
                    if previous_fk_bone is None:
                        fk_bone.parent = edit_bone.parent
                    else:
                        fk_bone.parent = previous_fk_bone
                        fk_bone.use_connect = True
                        
                    deform_fk_mapping[edit_bone.name] = fk_bone.name
                    fk_bone_names.append(fk_bone.name)
                    if any(a in fk_bone.name for a in bones_for_ik):
                        fk_bones_for_ik.append(fk_bone)
                    previous_fk_bone = fk_bone
                    
            # IK
            if fk_bones_for_ik:
                switch_name = "FK_IK_Switch"
                switch_bone = self.rig_data.edit_bones.new(switch_name)
                switch_bone.matrix = root.matrix.copy()
                switch_bone.length = root.length
                switch_bone.tail.y = -2 / 0.03048
                switch_bone.head.y = -2 / 0.03048
                switch_bone.parent = root

                slider_name = "FK_IK"
                slider_bone = self.rig_data.edit_bones.new(slider_name)
                slider_bone.matrix = switch_bone.matrix.copy()
                slider_bone.parent = switch_bone

                switch_bone_names.append(switch_bone.name)
                switch_bone_names.append(slider_bone.name)

            for fkb in fk_bones_for_ik:
                if fkb.parent is None or fkb.parent.parent is None:
                    continue
                root_fkb = fkb.parent.parent
                mid_fkb = fkb.parent

                ikb = self.rig_data.edit_bones.new(fkb.name.replace("FK_", "IK_"))
                ikb: bpy.types.EditBone
                ikb.head = fkb.head
                ikb.tail = fkb.tail
                ikb.parent = root
                
                pole_target = self.rig_data.edit_bones.new(ikb.name.replace("IK_", "PT_"))
                pole_pos = calculate_pole_position(root_fkb, mid_fkb, fkb)
                angle = calculate_pole_angle(root_fkb, fkb, pole_pos)
                pole_target.head = pole_pos
                pole_target.tail = pole_pos + (mid_fkb.y_axis.normalized() * max(mid_fkb.length * 0.35, 0.01))
                pole_target.parent = root
                
                fk_ik_mapping[fkb.name] = ikb.name, pole_target.name, angle
                
                ik_bone_names.append(ikb.name)
                ik_bone_names.append(pole_target.name)
                
                    
            bpy.ops.object.editmode_toggle()
            
            for b in self.rig_data.bones:
                if b.name in fk_bone_names or b.name in ik_bone_names or b.name in switch_bone_names:
                    b.use_deform = False
                
        if reverse_controls:
            self.rig_ob.nwo.invert_control_rig = True
        else:
            self.rig_ob.nwo.invert_control_rig = False

        min_size, max_size = utils.to_aabb(self.rig_ob)
        shape_scale = abs((max_size - min_size).length) * 0.1
        switch_shape = bpy.data.objects.get(fk_ik_switch_shape_name)
        if switch_shape is None:
            switch_shape_data = bpy.data.meshes.new(fk_ik_switch_shape_name)
            switch_shape_data.from_pydata(
                vertices=[Vector(co) for co in fk_ik_switch_shape_vert_coords],
                edges=fk_ik_switch_shape_edges,
                faces=[],
            )
            switch_shape = bpy.data.objects.new(fk_ik_switch_shape_name, switch_shape_data)
            switch_shape.nwo.export_this = False

        slider_shape = bpy.data.objects.get(fk_ik_circle_shape_name)
        if slider_shape is None:
            slider_shape_data = bpy.data.meshes.new(fk_ik_circle_shape_name)
            slider_shape_data.from_pydata(
                vertices=[Vector(co) for co in fk_ik_circle_shape_vert_coords],
                edges=fk_ik_circle_shape_edges,
                faces=[],
            )
            slider_shape = bpy.data.objects.new(fk_ik_circle_shape_name, slider_shape_data)
            slider_shape.nwo.export_this = False

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
            
        if switch_name is not None and slider_name is not None:
            switch_pb = self.rig_pose.bones.get(switch_name)
            slider_pb = self.rig_pose.bones.get(slider_name)
            
            switch_pb.color.palette = 'THEME01'
            slider_pb.color.palette = 'THEME01'

            switch_pb.custom_shape = switch_shape
            switch_pb.custom_shape_rotation_euler.x = radians(-90)
            switch_pb.custom_shape_scale_xyz = Vector.Fill(3, 1 / 0.03048) * self.scale
            switch_pb.use_custom_shape_bone_size = False

            slider_pb.custom_shape = slider_shape
            slider_pb.custom_shape_translation.x = -0.5 / 0.03048
            slider_pb.custom_shape_rotation_euler.x = radians(-90)
            slider_pb.custom_shape_scale_xyz = Vector.Fill(3, 1 / 0.03048) * self.scale
            slider_pb.use_custom_shape_bone_size = False

            slider_pb.lock_location = False, True, True
            slider_pb.lock_rotation = True, True, True
            slider_pb.lock_scale = True, True, True

            slider_limit_con = cast(bpy.types.Constraint, slider_pb.constraints.new('LIMIT_LOCATION'))
            slider_limit_con.name = "FK_IK_Slider_Limit"
            slider_limit_con.use_min_x = True
            slider_limit_con.use_min_y = True
            slider_limit_con.use_min_z = True
            slider_limit_con.use_max_x = True
            slider_limit_con.use_max_y = True
            slider_limit_con.use_max_z = True
            slider_limit_con.min_x = 0
            slider_limit_con.max_x = 1/ 0.03048
            slider_limit_con.min_y = 0
            slider_limit_con.max_y = 0
            slider_limit_con.min_z = 0
            slider_limit_con.max_z = 0
            slider_limit_con.use_transform_limit = True
            slider_limit_con.owner_space = 'LOCAL'
            
        for fkb_name, (ikb_name, pt_name, angle) in fk_ik_mapping.items():
            fkb = self.rig_pose.bones[fkb_name]
            ikb = self.rig_pose.bones[ikb_name]
            ptb = self.rig_pose.bones[pt_name]
            
            fkb.color.palette = 'THEME07'
            ikb.color.palette = 'THEME01'
            ptb.color.palette = 'THEME01'

            ikb.custom_shape = ik_shape
            ikb.custom_shape_scale_xyz *= self.scale / 0.03048
            ikb.use_custom_shape_bone_size = True
            ikb.custom_shape_translation = Vector((0.0, ikb.length, 0.0))
            ikb.custom_shape_rotation_euler = Vector((0.0, 0.0, 0.0))

            ptb.custom_shape = pole_shape
            ptb.custom_shape_scale_xyz *= self.scale / 0.03048
            ptb.use_custom_shape_bone_size = True
            ptb.custom_shape_translation = Vector((0.0, 0.0, 0.0))
            ptb.custom_shape_rotation_euler = Vector((0.0, 0.0, 0.0))
            
            con = cast(bpy.types.Constraint, fkb.constraints.new('IK'))
            con.target = self.rig_ob
            con.subtarget = ikb_name
            con.chain_count = fk_parents_count(fkb)
            con.use_tail = False
            
            con.pole_target = self.rig_ob
            con.pole_subtarget = pt_name
            con.pole_angle = angle
            if slider_name is not None:
                driver = con.driver_add("influence").driver
                driver.type = 'SCRIPTED'

                slider_x_var = driver.variables.new()
                slider_x_var.name = "slider_x"
                slider_x_var.type = 'SINGLE_PROP'
                slider_x_target = slider_x_var.targets[0]
                slider_x_target.id = self.rig_ob
                slider_x_target.data_path = f'pose.bones["{slider_name}"].location[0]'

                slider_max_var = driver.variables.new()
                slider_max_var.name = "slider_max"
                slider_max_var.type = 'SINGLE_PROP'
                slider_max_target = slider_max_var.targets[0]
                slider_max_target.id = self.rig_ob
                slider_max_target.data_path = f'pose.bones["{slider_name}"].constraints["FK_IK_Slider_Limit"].max_x'

                driver.expression = "min(max(slider_x / slider_max, 0.0), 1.0)"
            
def fk_parents_count(fkb: bpy.types.PoseBone):
    count = 0
    while fkb.parent is not None:
        parent = fkb.parent
        if parent.name.startswith("FK_"):
            count += 1
            fkb = parent
        else:
            break
        
    return count
            

def predict_tail_from_previous(previous_fk_bone, current_edit_bone):
    if previous_fk_bone is None:
        return current_edit_bone.tail.copy()

    direction = previous_fk_bone.tail - previous_fk_bone.head
    prev_len = direction.length

    if prev_len < 1e-6:
        return current_edit_bone.tail.copy()

    direction.normalize()

    return current_edit_bone.head + direction

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

def calculate_pole_angle(root_bone: bpy.types.EditBone, end_bone: bpy.types.EditBone, pole_position: Vector) -> float:
    root_axis = root_bone.tail - root_bone.head
    chain_axis = end_bone.tail - root_bone.head
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
