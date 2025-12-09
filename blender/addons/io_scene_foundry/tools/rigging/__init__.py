

from math import radians
from typing import cast
import bpy
from mathutils import Vector

from ... import utils

bone_x = 0, 0.1, 0
bone_x_negative = 0, -0.1, 0
bone_y = -0.1, 0, 0
bone_y_negative = 0.1, 0, 0

pedestal_name, aim_pitch_name, aim_yaw_name = 'pedestal', 'aim_pitch', 'aim_yaw'
aim_control_name = 'CTRL_aim'
pedestal_shape_name, aim_shape_name = 'pedestal_shape', 'aim_shape'

pedestal_shape_vert_coords = [(0.809309, 0.60584, 0.0), (0.756688, 0.674648, 0.0), (0.690572, 0.74488, 0.0), (0.625647, 0.799433, 0.0), (0.552399, 0.849233, 0.0), (0.472018, 0.893502, 1e-06), (0.385693, 0.931465, 1e-06), (0.294613, 0.962344, 1e-06), (0.199964, 0.985363, 1e-06), (0.10294, 0.999742, 1e-06), (0.004724, 1.004709, 1e-06), (-0.093539, 0.999675, 1e-06), (-0.190899, 0.984823, 1e-06), (-0.28646, 0.960528, 1e-06), (-0.379317, 0.927159, 1e-06), (-0.468572, 0.885094, 1e-06), (-0.553322, 0.834703, 0.0), (-0.63267, 0.776358, 0.0), (-0.705711, 0.710436, 0.0), (-0.771635, 0.637395, 0.0), (-0.829979, 0.558048, 0.0), (-0.880369, 0.473297, 0.0), (-0.922439, 0.384043, 0.0), (-0.955806, 0.291185, 0.0), (-0.980101, 0.195624, 0.0), (-0.99495, 0.098263, 0.0), (-0.999985, -0.0, -0.0), (-0.99495, -0.098263, -0.0), (-0.980101, -0.195624, -0.0), (-0.955806, -0.291185, -0.0), (-0.922439, -0.384043, -0.0), (-0.880369, -0.473297, -0.0), (-0.829979, -0.558048, -0.0), (-0.771635, -0.637395, -0.0), (-0.705711, -0.710435, -0.0), (-0.63267, -0.776358, -0.0), (-0.553322, -0.834703, -0.0), (-0.468572, -0.885094, -1e-06), (-0.379317, -0.927159, -1e-06), (-0.28646, -0.960527, -1e-06), (-0.190899, -0.984823, -1e-06), (-0.093538, -0.999675, -1e-06), (0.004724, -1.004709, -1e-06), (0.102987, -0.999675, -1e-06), (0.200348, -0.984823, -1e-06), (0.295908, -0.960527, -1e-06), (0.388767, -0.92716, -1e-06), (0.478021, -0.885094, -1e-06), (0.562772, -0.834703, -0.0), (0.642119, -0.776358, -0.0), (0.71516, -0.710435, -0.0), (0.768886, -0.652072, -0.0), (0.817734, -0.589496, -0.0), (0.861507, -0.523183, -0.0), (0.90001, -0.4536, -0.0), (1.13563, -0.4536, -0.0), (1.13563, -0.9072, -1e-06), (2.042828, -0.0, -0.0), (1.135629, 0.9072, 1e-06), (1.13563, 0.4536, 0.0), (0.902965, 0.454077, 0.0), (0.859238, 0.528559, 0.0)]
aim_shape_vert_coords = [(1.955878, 0.885051, 0.0), (1.95143, -0.887275, 0.0), (2.307979, 0.003538, 0.0), (3.72598, 0.0, 0.0)]
pedestal_shape_faces = [[61, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]]
aim_shape_faces = [[1, 3, 0, 2]]

# Bone that should be connected, the final bone in the chain gets no FK bone of its own
bone_links = (
    ("upperarm", "forearm", "hand"),
    ("thigh", "calf", "foot"),
    ("low", "mid", "tip"),
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
        self.scale = ((1 / 0.03048) if context.scene.nwo.scale == 'max' else 1) if scale is None else scale
        self.forward = context.scene.nwo.forward_direction if forward is None else forward
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
    
    def build_and_apply_control_shapes(self, pedestal=None, pitch=None, yaw=None, aim_control=None, wireframe=False, aim_control_only=False, reverse_control=False, reach_fp_fix=False, constraints_only=False):
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
                    shape_data.from_pydata(vertices=verts, edges=[], faces=pedestal_shape_faces)
                    shape_ob = bpy.data.objects.new(pedestal_shape_name, shape_data)
                    
                    shape_ob.nwo.export_this = False
                    
                pedestal.custom_shape = shape_ob
                pedestal.custom_shape_scale_xyz = Vector((1, 1, 1)) * shape_scale
                pedestal.use_custom_shape_bone_size = False
                
                if reach_fp_fix:
                    pedestal.custom_shape_rotation_euler.x = radians(-90)
                
                if wireframe:
                    self.rig_data.bones[pedestal.name].show_wire = True
        
        if self.has_pose_bones:
            if not aim_control:
                aim_control: bpy.types.PoseBone = utils.get_pose_bone(self.rig_ob, aim_control_name)
            if aim_control is not None:
                if not constraints_only:
                    shape_ob = bpy.data.objects.get(aim_shape_name)
                    if shape_ob is None:
                        shape_data = bpy.data.meshes.new(aim_shape_name)
                        verts = [Vector(co) for co in aim_shape_vert_coords]
                        shape_data.from_pydata(vertices=verts, edges=[], faces=aim_shape_faces)
                        shape_ob = bpy.data.objects.new(aim_shape_name, shape_data)
                        shape_ob.nwo.export_this = False
                        
                    aim_control.custom_shape = shape_ob
                    aim_control.custom_shape_scale_xyz = Vector((1, 1, 1)) * shape_scale
                    aim_control.use_custom_shape_bone_size = False
                
                    if reach_fp_fix:
                        aim_control.custom_shape_rotation_euler.z = radians(90)
                    
                    if wireframe:
                        self.rig_data.bones[aim_control.name].show_wire = True
                
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
                        pitch.custom_shape = shape_ob
                        pitch.custom_shape_scale_xyz = Vector((0.2, 0.2, 0.2)) * shape_scale
                        pitch.use_custom_shape_bone_size = False
                        if not reach_fp_fix:
                            pitch.custom_shape_rotation_euler.x = radians(90)
                        
                        if wireframe:
                            self.rig_data.bones[pitch.name].show_wire = True
                            
                    if yaw:
                        yaw.custom_shape = shape_ob
                        yaw.custom_shape_scale_xyz = Vector((0.2, 0.2, 0.2)) * shape_scale
                        yaw.use_custom_shape_bone_size = False
                        
                        if reach_fp_fix:
                            yaw.custom_shape_rotation_euler.x = radians(90)
                        
                        if wireframe:
                            self.rig_data.bones[yaw.name].show_wire = True
                        
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
                
                utils.clear_constraints(aim_control)
                utils.clear_constraints(yaw)
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
        else:
            pedestal = self.rig_data.edit_bones.get(pedestal)
            
        if self.set_scene_rig_props and self.has_pose_bones and not self.context.scene.nwo.node_usage_pedestal:
            self.context.scene.nwo.node_usage_pedestal = pedestal_name
        
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
            else:
                yaw = self.rig_data.edit_bones.get(yaw)
                
            if self.set_scene_rig_props:
                if not self.context.scene.nwo.node_usage_pose_blend_pitch:
                    self.context.scene.nwo.node_usage_pose_blend_pitch = aim_pitch_name
                if not self.context.scene.nwo.node_usage_pose_blend_yaw:
                    self.context.scene.nwo.node_usage_pose_blend_yaw = aim_yaw_name
                    
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
        if self.set_scene_rig_props and not self.context.scene.nwo.main_armature:
            self.context.scene.nwo.main_armature = self.rig_ob
            
    def generate_bone_collections(self):
        """Sorts bones into bone collections"""
        bone_collections = self.rig_data.collections
        halo_collection = bone_collections.get("Halo Bones")
        
        if halo_collection is None:
            halo_collection = bone_collections.new("Halo Bones")
            
        halo_special = bone_collections.get("Halo Special Bones")
        if halo_special is None:
            halo_special = bone_collections.new("Halo Special Bones", parent=halo_collection)
            
        halo_helpers = bone_collections.get("Halo Helper Bones")
        if halo_helpers is None:
            halo_helpers = bone_collections.new("Halo Helper Bones", parent=halo_collection)
            
        fk_collection = bone_collections.get("FK")
        if fk_collection is None:
            fk_collection = bone_collections.new("FK")

        ik_collection = bone_collections.get("IK")
        if ik_collection is None:
            ik_collection = bone_collections.new("IK")
        
        for bone in self.rig_data.bones:
            no_digit_name = bone.name.strip("0123456789")
            if bone.use_deform:
                if no_digit_name.endswith(special_bones):
                    halo_special.assign(bone)
                elif no_digit_name.endswith(helper_bones):
                    halo_helpers.assign(bone)
                else:
                    halo_collection.assign(bone)
            else:
                if no_digit_name.startswith("FK_"):
                    fk_collection.assign(bone)
                elif no_digit_name.startswith("IK_"):
                    ik_collection.assign(bone)

    def apply_halo_bone_shape(self):
        """Applies a custom shape to every halo bone that is not the pedestal or an aim bone"""
        shape = bpy.data.objects.get("halo_deform_bone_shape")
        if shape is None:
            shape_mesh = bpy.data.meshes.new("halo_deform_bone_shape")
            utils.mesh_to_cube(shape_mesh)
            shape = bpy.data.objects.new("halo_deform_bone_shape", shape_mesh)
            
        for pbone, bone in zip(self.rig_pose.bones, self.rig_data.bones):
            if pbone.custom_shape is None and bone.use_deform:
                pbone.custom_shape = shape
                pbone.custom_shape_scale_xyz = Vector((0.5, 0.5, 0.5)) * self.scale
                bone.show_wire = True
        
    def build_fk_ik_rig(self, reverse_controls=False, constraints_only=False):
        """Generates an FK/IK skeleton for the halo rig"""
        
        deform_fk_mapping = {}
        deform_ik_mapping = {}
        
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
            start_link_bones = {b[0]: iter(b[1:]) for b in bone_links}
            start_link_bones_keys = tuple(start_link_bones)
            
            def get_chain(b: bpy.types.PoseBone, i: int):
                nonlocal start_link_bones
                current_bone_chain = []
                link_chain = next(v for k, v in start_link_bones.items() if b.name.endswith(k))
                current_bone_chain.append(b.name)
                next_link = next(link_chain, None)
                allowed_bones = set(b.children_recursive)
                if next_link is None:
                    return
                while i < len(self.rig_pose.bones):
                    next_bone = self.rig_pose.bones[i]
                    if next_bone.name.endswith(next_link) and next_bone in allowed_bones:
                        current_bone_chain.append(next_bone.name)
                        next_link = next(link_chain, None)
                        allowed_bones = set(b.children_recursive)
                        if next_link is None:
                            break
                    i += 1
                    
                if len(current_bone_chain) > 1:
                    bone_chains.append(current_bone_chain)
                
                start_link_bones = {b[0]: iter(b[1:]) for b in bone_links} # reset the iterators
            
            def get_chain_digit(b: bpy.types.PoseBone, i: int):
                current_bone_chain = []
                current_bone_chain.append(b.name)
                allowed_bones = set(b.children_recursive)
                next_expected = b.name[:-1] + str(int(b.name[-1]) + 1)
                while i < len(self.rig_pose.bones):
                    next_bone = self.rig_pose.bones[i]
                    if next_bone.name == next_expected and next_bone in allowed_bones:
                        current_bone_chain.append(next_bone.name)
                        allowed_bones = set(next_bone.children_recursive)
                        next_expected = next_bone.name[:-1] + str(int(next_bone.name[-1]) + 1)
                        
                    i += 1
                    
                if len(current_bone_chain) > 1:
                    bone_chains.append(current_bone_chain)
            
            for idx, bone in enumerate(self.rig_pose.bones):
                if bone.name.endswith(start_link_bones_keys):
                    get_chain(bone, idx + 1)
                elif bone.name[-1] == "1":
                    get_chain_digit(bone, idx + 1)
                    
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
            
            fk_bone_names = []
            
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
                    else:
                        fk_bone.tail = next_edit_bone.head

                                        
                    if previous_fk_bone is None:
                        fk_bone.parent = edit_bone.parent
                    else:
                        fk_bone.parent = previous_fk_bone
                        fk_bone.use_connect = True
                        
                    deform_fk_mapping[edit_bone.name] = fk_bone.name
                    fk_bone_names.append(fk_bone.name)
                    previous_fk_bone = fk_bone
                    
            bpy.ops.object.editmode_toggle()
            
            for b in self.rig_data.bones:
                if b.name in fk_bone_names:
                    b.use_deform = False
                
        if reverse_controls:
            self.rig_ob.nwo.invert_fkik = True
        else:
            self.rig_ob.nwo.invert_fkik = False
                
        for db_name, fkb_name in deform_fk_mapping.items():
            fkb = self.rig_pose.bones[fkb_name]
            db = self.rig_pose.bones[db_name]
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


def predict_tail_from_previous(previous_fk_bone, current_edit_bone):
    if previous_fk_bone is None:
        return current_edit_bone.tail.copy()

    direction = previous_fk_bone.tail - previous_fk_bone.head
    prev_len = direction.length

    if prev_len < 1e-6:
        return current_edit_bone.tail.copy()

    direction.normalize()

    return current_edit_bone.head + direction

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