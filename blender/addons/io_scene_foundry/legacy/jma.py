import math
from pathlib import Path
from typing import cast
from mathutils import Euler, Matrix, Quaternion, Vector
import bpy

from .. import utils

e90 = Euler((0, 0, math.radians(-90)))

class Node:
    def __init__(self, name: str, parent_index=-1, child_index=-1, sibling_index=-1):
        self.name = name
        self.parent_index = parent_index
        self.child_index = child_index
        self.sibling_index = sibling_index
        self.parent: Node = None
        self.fc_loc_x: bpy.types.FCurve
        self.fc_loc_y: bpy.types.FCurve
        self.fc_loc_z: bpy.types.FCurve
        self.fc_rot_w: bpy.types.FCurve
        self.fc_rot_x: bpy.types.FCurve
        self.fc_rot_y: bpy.types.FCurve
        self.fc_rot_z: bpy.types.FCurve
        self.fc_sca_x: bpy.types.FCurve
        self.fc_sca_y: bpy.types.FCurve
        self.fc_sca_z: bpy.types.FCurve
        self.pose_bone: bpy.types.PoseBone = None
    
def gen_lines(filepath: Path | str):
    with open(filepath, "r") as file:
        for line in file:
            yield line.partition(";")[0].strip()
            
def assign_parents_from_child_sibling(nodes: list[Node], index=0, parent_index=-1):
    if index == -1:
        return

    node = nodes[index]
    node.parent_index = parent_index

    # First child
    assign_parents_from_child_sibling(nodes, node.child_index, index)

    # Then next sibling
    assign_parents_from_child_sibling(nodes, node.sibling_index, parent_index)

class JMA:
    def __init__(self):
        self.name = ""
        self.version = 16395
        self.node_checksum = 0
        self.frame_count = 0
        self.fps = 30
        self.actor_count = 1
        self.actor_names = ["unnamedActor"]
        self.node_count = 0
        self.nodes: list[Node] = []
        self.transforms: list[dict[Node: Matrix]] = []
        
    def from_file(self, filepath: Path | str):
        self.name = Path(filepath).with_suffix("").name
        lines = gen_lines(filepath)
        get = lambda: next(lines)
            
        self.version = int(get())
        h1 = self.version < 16394
        if h1:
            self.frame_count = int(get())
            self.fps = int(get())
            self.actor_count = int(get())
            self.actor_names = get().split()
            self.node_count = int(get())
            self.node_checksum = int(get())
        else:
            self.node_checksum = int(get())
            self.frame_count = int(get())
            self.fps = int(get())
            self.actor_count = int(get())
            self.actor_names = get().split()
            self.node_count = int(get())
        
        if h1:
            for _ in range(self.node_count):
                self.nodes.append(Node(get(), child_index=int(get()), sibling_index=int(get())))
            
            assign_parents_from_child_sibling(self.nodes)
                
        else:
            for _ in range(self.node_count):
                self.nodes.append(Node(get(), parent_index=int(get())))
            
        for node in self.nodes:
            if node.parent_index > -1:
                node.parent = self.nodes[node.parent_index]
            
        for _ in range(self.frame_count):
            frame_data = {}
            for node in self.nodes:
                loc = Vector(tuple(map(float, get().split())))
                rot = tuple(map(float, get().split()))
                quat = Quaternion((rot[3], rot[0], rot[1], rot[2]))
                if h1:
                    quat.invert()
                scale = float(get())
                matrix = Matrix.LocRotScale(loc, quat, Vector.Fill(3, scale))
                frame_data[node] = matrix
                
            self.transforms.append(frame_data)
            
        node_dict = {}
        for node in self.nodes:
            node_dict[node] = node.parent_index + 1
                
        self.nodes.sort(key=lambda x: node_dict[x])
        
        # Make all matrices parent relative
        if not h1:
            for frame_data in self.transforms:
                for node in reversed(self.nodes):
                    if node.parent is None:
                        continue
                    frame_data[node] = frame_data[node.parent].inverted_safe() @ frame_data[node]
                
            
    def to_armature_action(self, armature: bpy.types.Object, action: bpy.types.Action=None):
        bpy.context.scene.frame_set(0)
        if action is None:
            action = bpy.data.actions.new(name=self.name)

        if armature.animation_data is None:
            armature.animation_data_create()
            
        armature.animation_data.action = action
            
        fcurves = cast(bpy.types.ActionFCurves, action.fcurves)
        fcurves.clear()
        
        armature_bone_names = {utils.remove_node_prefix(bone.name): bone for bone in armature.pose.bones}
        
        valid_nodes = []
        
        for node in self.nodes:
            node.pose_bone = armature_bone_names.get(utils.remove_node_prefix(node.name))
            if node.pose_bone is None:
                continue
            node.fc_loc_x = fcurves.new(data_path=f'pose.bones["{node.name}"].location', index=0)
            node.fc_loc_y = fcurves.new(data_path=f'pose.bones["{node.name}"].location', index=1)
            node.fc_loc_z = fcurves.new(data_path=f'pose.bones["{node.name}"].location', index=2)
            node.fc_rot_w = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=0)
            node.fc_rot_x = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=1)
            node.fc_rot_y = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=2)
            node.fc_rot_z = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=3)
            node.fc_sca_x = fcurves.new(data_path=f'pose.bones["{node.name}"].scale', index=0)
            node.fc_sca_y = fcurves.new(data_path=f'pose.bones["{node.name}"].scale', index=1)
            node.fc_sca_z = fcurves.new(data_path=f'pose.bones["{node.name}"].scale', index=2)
            valid_nodes.append(node)
            
        bone_dict = {}
        bones_ordered = [node.pose_bone for node in valid_nodes]
        for bone in bones_ordered:
            if bone.parent:
                bone_dict[bone] = bone_dict[bone.parent] + 1
            else:
                bone_dict[bone] = 0
                
        bones_ordered.sort(key=lambda x: bone_dict[x])
        
        bone_base_matrices = {}
        for bone in armature.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        for bone in bones_ordered:
            if bone.parent:
                bone_base_matrices[bone] = bone.parent.matrix.inverted_safe() @ bone.matrix
            else:
                bone_base_matrices[bone] = bone.matrix
        
        for idx, nodes_transforms in enumerate(self.transforms):
            frame_idx = idx + 1
            for node in valid_nodes:
                node: Node
                matrix = nodes_transforms[node]
                # get diff between base and jma transform
                transform_matrix = bone_base_matrices[node.pose_bone].inverted_safe() @ matrix
                loc, rot, sca = transform_matrix.decompose()
                
                node.fc_loc_x.keyframe_points.insert(frame_idx, loc.x, options={'FAST'})
                node.fc_loc_y.keyframe_points.insert(frame_idx, loc.y, options={'FAST'})
                node.fc_loc_z.keyframe_points.insert(frame_idx, loc.z, options={'FAST'})
                
                node.fc_rot_w.keyframe_points.insert(frame_idx, rot.w, options={'FAST'})
                node.fc_rot_x.keyframe_points.insert(frame_idx, rot.x, options={'FAST'})
                node.fc_rot_y.keyframe_points.insert(frame_idx, rot.y, options={'FAST'})
                node.fc_rot_z.keyframe_points.insert(frame_idx, rot.z, options={'FAST'})
                
                node.fc_sca_x.keyframe_points.insert(frame_idx, sca.x, options={'FAST'})
                node.fc_sca_y.keyframe_points.insert(frame_idx, sca.y, options={'FAST'})
                node.fc_sca_z.keyframe_points.insert(frame_idx, sca.z, options={'FAST'})
                
                
        return action
                