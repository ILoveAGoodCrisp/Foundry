

from collections import defaultdict
from math import radians
from pathlib import Path
from typing import cast
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .Tags import TagFieldBlock, TagFieldElement

from ..managed_blam.render_model import RenderModelTag
from ..managed_blam import Tag
from ..legacy.jma import Node
from .. import utils

tolerance = 1e-6

directions = "front", "left", "right", "back"
regions = "gut", "chest", "head", "l_arm", "l_hand", "l_leg", "l_foot", "r_arm", "r_hand", "r_leg", "r_foot"

class AnimationTag(Tag):
    tag_ext = 'model_animation_graph'

    def _read_fields(self):
        self.block_animations = self.tag.SelectField("Struct:definitions[0]/Block:animations")
        self.block_skeleton_nodes = self.tag.SelectField("definitions[0]/Block:skeleton nodes")
        self.block_node_usages = self.tag.SelectField("definitions[0]/Block:node usage")
        self.block_modes = self.tag.SelectField("Struct:content[0]/Block:modes")
        self.block_ik_chains = self.tag.SelectField('Struct:definitions[0]/Block:ik chains')
        self.block_blend_screens = self.tag.SelectField('Struct:definitions[0]/Block:NEW blend screens')
        self.block_additional_node_dat = self.tag.SelectField("Block:additional node data")
        
    def get_animation_names(self, filter="") -> list[str]:
        """Returns a list of all animation names"""
        if filter:
            return [element.Fields[0].GetStringData() for element in self.block_animations.Elements if filter in element.Fields[0].GetStringData()]
        else:
            return [element.Fields[0].GetStringData() for element in self.block_animations.Elements]
        
    def _initialize_tag(self):
        self.tag.SelectField('Struct:definitions[0]/ShortInteger:animation codec pack').Data = 6
        
    def _node_index_list(self, bones):
        # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
        node_index_list = [b for b in bones.keys()]
        if self._needs_skeleton_update(node_index_list):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in node_index_list:
                new_node = self.block_skeleton_nodes.AddElement()
                new_node.SelectField('name').SetStringData(n)
                
        return node_index_list
    
    def _node_index_list_granny(self, bones):
        # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
        node_index_list = [b.name for b in bones]
        if self._needs_skeleton_update(node_index_list):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in node_index_list:
                new_node = self.block_skeleton_nodes.AddElement()
                new_node.SelectField('name').SetStringData(n)
                
        return node_index_list
                
    def _needs_skeleton_update(self, node_index_list):
        graph_nodes = [e.SelectField('name').GetStringData() for e in self.block_skeleton_nodes.Elements]
        return set(node_index_list) != set(graph_nodes)
    
    def _node_index_dict(self):
        return {element.Fields[0].Data: element.ElementIndex for element in self.block_skeleton_nodes.Elements}
    
    def set_node_usages(self, bones, granny: bool = False):
        def _node_usage_dict(nwo):
            node_usage_dict = defaultdict(list)
            if nwo.node_usage_pedestal:
                node_usage_dict[nwo.node_usage_pedestal].append("pedestal")
            if nwo.node_usage_physics_control:
                node_usage_dict[nwo.node_usage_physics_control].append("physics control")
            if nwo.node_usage_camera_control:
                node_usage_dict[nwo.node_usage_camera_control].append("camera control")
            if nwo.node_usage_origin_marker:
                node_usage_dict[nwo.node_usage_origin_marker].append("origin marker")
            if nwo.node_usage_left_clavicle:
                node_usage_dict[nwo.node_usage_left_clavicle].append("left clavicle")
            if nwo.node_usage_left_upperarm:
                node_usage_dict[nwo.node_usage_left_upperarm].append("left upperarm")
            if nwo.node_usage_pose_blend_pitch:
                node_usage_dict[nwo.node_usage_pose_blend_pitch].append("pose blend pitch")
            if nwo.node_usage_pose_blend_yaw:
                node_usage_dict[nwo.node_usage_pose_blend_yaw].append("pose blend yaw")
            if nwo.node_usage_pelvis:
                node_usage_dict[nwo.node_usage_pelvis].append("pelvis")
            if nwo.node_usage_left_foot:
                node_usage_dict[nwo.node_usage_left_foot].append("left foot")
            if nwo.node_usage_right_foot:
                node_usage_dict[nwo.node_usage_right_foot].append("right foot")
            if nwo.node_usage_damage_root_gut:
                node_usage_dict[nwo.node_usage_damage_root_gut].append("damage root gut")
            if nwo.node_usage_damage_root_chest:
                node_usage_dict[nwo.node_usage_damage_root_chest].append("damage root chest")
            if nwo.node_usage_damage_root_head:
                node_usage_dict[nwo.node_usage_damage_root_head].append("damage root head")
            if nwo.node_usage_damage_root_left_shoulder:
                node_usage_dict[nwo.node_usage_damage_root_left_shoulder].append("damage root left shoulder")
            if nwo.node_usage_damage_root_left_arm:
                node_usage_dict[nwo.node_usage_damage_root_left_arm].append("damage root left arm")
            if nwo.node_usage_damage_root_left_leg:
                node_usage_dict[nwo.node_usage_damage_root_left_leg].append("damage root left leg")
            if nwo.node_usage_damage_root_left_foot:
                node_usage_dict[nwo.node_usage_damage_root_left_foot].append("damage root left foot")
            if nwo.node_usage_damage_root_right_shoulder:
                node_usage_dict[nwo.node_usage_damage_root_right_shoulder].append("damage root right shoulder")
            if nwo.node_usage_damage_root_right_arm:
                node_usage_dict[nwo.node_usage_damage_root_right_arm].append("damage root right arm")
            if nwo.node_usage_damage_root_right_leg:
                node_usage_dict[nwo.node_usage_damage_root_right_leg].append("damage root right leg")
            if nwo.node_usage_damage_root_right_foot:
                node_usage_dict[nwo.node_usage_damage_root_right_foot].append("damage root right foot")
            if self.corinth:
                if nwo.node_usage_left_hand:
                    node_usage_dict[nwo.node_usage_left_hand].append("left hand")
                if nwo.node_usage_right_hand:
                    node_usage_dict[nwo.node_usage_right_hand].append("right hand")
                if nwo.node_usage_weapon_ik:
                    node_usage_dict[nwo.node_usage_weapon_ik].append("weapon ik")

            return node_usage_dict
        
        if self.block_skeleton_nodes.Elements.Count != len(bones):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in [b.name for b in bones]:
                self.block_skeleton_nodes.AddElement().Fields[0].SetStringData(n)
                
        node_usage_dict = _node_usage_dict(self.context.scene.nwo)
        skeleton_nodes = self._node_index_dict()
        self.block_node_usages.RemoveAllElements()
        node_targets = [n for n in skeleton_nodes.keys() if n in node_usage_dict.keys()]
        for node in node_targets:
            usages = node_usage_dict[node]
            for usage in usages:
                new_element = self.block_node_usages.AddElement()
                usage_field = new_element.SelectField("usage")
                node_field = new_element.SelectField("node to use")
                items = [i.EnumName for i in usage_field.Items]
                usage_field.Value = items.index(usage)
                node_field.Value = skeleton_nodes[node]
        if node_targets:
            self.tag_has_changes = True
    
    def set_world_animations(self, world_animations):
        """Sets the given animations to world animations"""
        target_elements = [e for e in self.block_animations.Elements if e.SelectField('name').GetStringData() in world_animations]
        for e in target_elements:
            flags = e.SelectField('shared animation data[0]/internal flags')
            flags.SetBit('world relative', True)
        if target_elements:
            self.tag_has_changes = True
            
    def get_nodes(self):
        return [e.SelectField('name').GetStringData() for e in self.block_skeleton_nodes.Elements]
    
    def read_all_modes(self):
        print(self.tag.Path.RelativePath)
        print('-'*100)
        for e in self.block_modes.Elements:
            print(e.SelectField('label').GetStringData())
        print('\n\n\n')
        
    def write_ik_chains(self, ik_chains: list, bones: list, granny: bool = False):
        
        if self.block_skeleton_nodes.Elements.Count != len(bones):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in [b.name for b in bones]:
                self.block_skeleton_nodes.AddElement().Fields[0].SetStringData(n)
        
        skeleton_nodes = self._node_index_dict()
        valid_ik_chains = [chain for chain in ik_chains if chain.start_node in skeleton_nodes and chain.effector_node in skeleton_nodes]
        
        if self.block_ik_chains.Elements.Count:
            self.block_ik_chains.RemoveAllElements()
    
        for chain in valid_ik_chains:
            element = self.block_ik_chains.AddElement()
            element.SelectField('name').SetStringData(chain.name)
            element.SelectField('start node').Value = skeleton_nodes[chain.start_node]
            element.SelectField('effector node').Value = skeleton_nodes[chain.effector_node]
            
        self.tag_has_changes = True
        
    def validate_compression(self, animations, default_compression: str):
        # medium = 0
        # rough = 1
        # uncompressed = 2
        game_animations = {animation.name.replace(' ', ':'): animation.compression for animation in animations}
        
        for element in self.block_animations.Elements:
            name = element.Fields[0].GetStringData()
            if element.Fields[0].GetStringData() not in game_animations.keys() or not element.SelectField("shared animation data").Elements.Count:
                continue
            compression = game_animations.get(name)
            if compression == 'Default':
                continue
            compression_enum = 0 # medium
            match compression:
                case "Rough":
                    compression_enum = 1
                case "Uncompressed":
                    compression_enum = 2
                    
            compression_field = element.SelectField("Block:shared animation data[0]/CharEnum:desired compression")
            if compression_field.Value != compression_enum:
                compression_field.Value = compression_enum
                self.tag_has_changes = True
                
    def set_parent_graph(self, parent_graph_path):
        parent_field = self.tag.SelectField("Struct:definitions[0]/Reference:parent animation graph")
        if not parent_graph_path and parent_field.Path:
            parent_field.Path = None
            self.tag_has_changes = True
            return
        parent_path = str(Path(utils.relative_path(parent_graph_path)).with_suffix(".model_animation_graph"))
        full_path = Path(self.tags_dir, parent_path)
        if not full_path.exists():
            print(f"Parent graph does not exist: {full_path}")
        new_tag_path = self._TagPath_from_string(parent_path)
        if parent_field.Path != new_tag_path:
            parent_field.Path = self._TagPath_from_string(parent_path)
            self.tag_has_changes = True
        
    def get_parent_graph(self):
        path = self.tag.SelectField("Struct:definitions[0]/Reference:parent animation graph").Path
        if path:
            return path.RelativePathWithExtension
        
    def _get_animation_name_from_index(self, index):
        if index > self.block_animations.Elements.Count - 1:
            return ""
        element = self.block_animations.Elements[index]
        return element.SelectField("name").GetStringData()
    
    def _get_animation_index_from_name(self, name):
        for element in self.block_animations.Elements:
            if element.SelectField("name").GetStringData() == name:
                return element.ElementIndex
        
        return -1
        
    def setup_blend_screens(self, animation_names: set):
        sorted_animations  = sorted(animation_names)
        blend_screens_to_remove = []
        tag_animation_names = [name.replace(" ", ":") for name in sorted_animations]
        for element in self.block_blend_screens.Elements:
            index = element.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value
            if index > -1:
                animation_name = self._get_animation_name_from_index(index)
                if animation_name and animation_name in tag_animation_names:
                    tag_animation_names.remove(animation_name)
            else:
                blend_screens_to_remove.append(element.ElementIndex)
        
        for screen_index in reversed(blend_screens_to_remove):
            self.block_blend_screens.RemoveElement(screen_index)
            self.tag_has_changes = True
        
        for name in tag_animation_names:
            animation_index = self._get_animation_index_from_name(name)
            if animation_index > -1:
                element = self.block_blend_screens.AddElement()
                element.SelectField("name").SetStringData(name)
                element.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value = animation_index
                state = name.split(":")[-1]
                yaw_source_value = "none"
                pitch_source_value = "none"
                weight_source_value = "none"
                interpolation_rate = "0"
                flag_weapon_down = False
                flag_blending = False
                flag_parent_adjust = False
                if "aim" in state:
                    yaw_source_value = "aim yaw"
                    pitch_source_value = "aim pitch"
                elif "look" in state:
                    yaw_source_value = "look yaw"
                    pitch_source_value = "look pitch"
                    flag_parent_adjust = True
                elif "steer" in state:
                    yaw_source_value = "steering"
                    pitch_source_value = "steering"
                elif "acc" in state:
                    yaw_source_value = "acceleration yaw"
                    pitch_source_value = "acceleration pitch"
                    weight_source_value = "acceleration magnitude"
                    interpolation_rate = "0.333"
                elif "pitch" in state and "turn" in state:
                    yaw_source_value = "first person turn"
                    pitch_source_value = "first person pitch"
                    
                if state.endswith("_down"):
                    flag_weapon_down = True
                elif state == "aiming":
                    flag_blending = True
                    
                element.SelectField("yaw source").SetValue(yaw_source_value)
                element.SelectField("pitch source").SetValue(pitch_source_value)
                element.SelectField("weight source").SetValue(weight_source_value)
                element.SelectField("interpolation rate").SetStringData(interpolation_rate)
                
                flags = element.SelectField("flags")
                
                if flag_weapon_down:
                    flags.SetBit("active only when weapon down", True)
                    
                if flag_blending:
                    flags.SetBit("attempt piece-wise blending", True)
                
                if flag_parent_adjust:
                    flags.SetBit("allow parent adjustment", True)
                
                self.tag_has_changes = True
                
    def to_blender(self, render_model: str, armature, filter: str):
        # Prepare exporter
        print()
        # print(self.resource_info())
        actions = []
        bone_base_matrices = {}
        for bone in armature.pose.bones:
            if bone.parent:
                bone_base_matrices[bone] = bone.parent.matrix.inverted_safe() @ bone.matrix
            else:
                bone_base_matrices[bone] = bone.matrix
        if self.block_animations.Elements.Count < 1: 
            return print("No animations found in graph")
        
        animation_nodes = None
        with RenderModelTag(path=render_model) as model:
            exporter = self._AnimationExporter()
            # exporter.LoadTags(self.tag_path, model.tag_path)
            ready = exporter.UseTags(self.tag, model.tag)
            if not ready:
                return print(f"Failed to use tags: {self.tag_path.RelativePath} & {render_model.tag_path.RelativePath}")
            
            nodes_count = exporter.GetGraphNodeCount()
            import clr
            clr.AddReference('System')
            from System import Array # type: ignore
            animation_nodes = [self._GameAnimationNode() for _ in range(nodes_count)]
            animation_nodes = Array[self._GameAnimationNodeType()](animation_nodes)
            
            if armature.animation_data is None:
                armature.animation_data_create()
            
            for element in self.block_animations.Elements:
                name = element.SelectField("name").GetStringData()
                if filter and filter not in name:
                    continue
                index = element.ElementIndex
                shared_data = element.SelectField("Block:shared animation data")
                anim_type = shared_data.Elements[0].SelectField("animation type").Value
                frame_info = shared_data.Elements[0].SelectField("frame info type").Value
                overlay = anim_type == 2
                if overlay:
                    utils.print_warning(f"{name} is an overlay, rotations will not be imported")
                    continue
                elif anim_type == 1 and frame_info > 0: # base and has movement
                    utils.print_warning(f"{name} has movement data that won't be imported")
                    continue
                frame_count = exporter.GetAnimationFrameCount(index)
                new_name = name.replace(":", " ")
                action = bpy.data.actions.new(new_name)
                slot = action.slots.new('OBJECT', armature.name)
                armature.animation_data.last_slot_identifier = slot.identifier
                armature.animation_data.action = action
                print(f"--- {action.name}")
                animation = self.context.scene.nwo.animations.add()
                animation.name = new_name
                action.use_fake_user = True
                action.use_frame_range = True
                animation.frame_start = 1
                animation.frame_end = frame_count
                match anim_type:
                    case 0 | 1:
                        if shared_data.Elements[0].SelectField("internal flags").TestBit("world relative"):
                            animation.animation_type = 'world'
                        else:
                            animation.animation_type = 'base'
                        match shared_data.Elements[0].SelectField("frame info type").Value:
                            case 0:
                                animation.animation_movement_data = 'none'
                            case 1:
                                animation.animation_movement_data = 'xy'
                            case 2:
                                animation.animation_movement_data = 'xyyaw'
                            case 3:
                                animation.animation_movement_data = 'xyzyaw'
                            case 4:
                                animation.animation_movement_data = 'full'
                    case 2:
                        animation.animation_type = 'overlay'
                    case 3:
                        animation.animation_type = 'replacement'
                track = animation.action_tracks.add()
                track.object = armature
                track.action = action
                if exporter.GetRenderModelBasePose(animation_nodes, nodes_count):
                    nodes = [Node(n.Name, n.ParentIndex) for n in animation_nodes]
                    for node in nodes:
                        if node.parent_index > -1:
                            node.parent = nodes[node.parent_index]
                            
                    node_base_matrices = {}
                    self._get_base_pose(animation_nodes, nodes, node_base_matrices)
                    transforms = {}
                    for frame in range(frame_count):
                        if exporter.GetAnimationFrame(index, frame, animation_nodes, nodes_count):
                            self._add_transforms(animation_nodes, nodes, frame + 1, overlay, node_base_matrices, transforms)
                            
                    self._to_armature_action(transforms, armature, action, nodes)
                    actions.append(action)
                    action.frame_end = frame_count
        
        return actions
    
    def _to_armature_action(self, transforms, armature: bpy.types.Object, action: bpy.types.Action, nodes: list[Node]):
        fcurves = cast(bpy.types.ActionFCurves, action.fcurves)
        fcurves.clear()
        
        armature_bone_names = {utils.remove_node_prefix(bone.name): bone for bone in armature.pose.bones}
        valid_nodes = []
        
        for node in nodes:
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
        for bone in bones_ordered:
            if bone.parent:
                bone_base_matrices[bone] = bone.parent.matrix.inverted_safe() @ bone.matrix
            else:
                bone_base_matrices[bone] = bone.matrix
        
        for frame_idx, nodes_transforms in transforms.items():
            for node in valid_nodes:
                matrix = nodes_transforms[node]
                transform_matrix = bone_base_matrices[node.pose_bone].inverted_safe() @ matrix
                loc, rot, sca = transform_matrix.decompose()
                
                node.fc_loc_x.keyframe_points.insert(frame_idx, loc.x, options={'FAST', 'NEEDED'})
                node.fc_loc_y.keyframe_points.insert(frame_idx, loc.y, options={'FAST', 'NEEDED'})
                node.fc_loc_z.keyframe_points.insert(frame_idx, loc.z, options={'FAST', 'NEEDED'})
                
                node.fc_rot_w.keyframe_points.insert(frame_idx, rot.w, options={'FAST', 'NEEDED'})
                node.fc_rot_x.keyframe_points.insert(frame_idx, rot.x, options={'FAST', 'NEEDED'})
                node.fc_rot_y.keyframe_points.insert(frame_idx, rot.y, options={'FAST', 'NEEDED'})
                node.fc_rot_z.keyframe_points.insert(frame_idx, rot.z, options={'FAST', 'NEEDED'})
                
                node.fc_sca_x.keyframe_points.insert(frame_idx, sca.x, options={'FAST', 'NEEDED'})
                node.fc_sca_y.keyframe_points.insert(frame_idx, sca.y, options={'FAST', 'NEEDED'})
                node.fc_sca_z.keyframe_points.insert(frame_idx, sca.z, options={'FAST', 'NEEDED'})
    
    def _get_base_pose(self, animation_nodes, nodes, node_base_matrices: dict):
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
            node_base_matrices[node] = matrix

    def _add_transforms(self, animation_nodes, nodes, frame, overlay: bool, node_base_matrices: dict, transforms: dict):
        frame_data = {}
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            base_matrix = cast(Matrix, node_base_matrices[node])
            overlay_keyed = False
            translation_keyed = False
            rotation_keyed = False
            base_translation, base_rotation, base_scale = base_matrix.decompose()
            if translation.magnitude < tolerance:
                translation = base_translation
            else:
                overlay_keyed = True
                translation_keyed = True
            if rotation.magnitude < tolerance:
                rotation = base_rotation
            else:
                overlay_keyed = True
                rotation_keyed = True

            if overlay:
                if overlay_keyed:
                    overlay_translation = (translation + base_translation) if translation_keyed else base_translation
                    overlay_rotation = base_rotation.rotate(rotation) if rotation_keyed else base_rotation
                    matrix = Matrix.LocRotScale(overlay_translation, overlay_rotation, Vector.Fill(3, scale))
                else:
                    matrix = base_matrix
            else:
                matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
                
            frame_data[node] = matrix
        
        transforms[frame] = frame_data
            
    def get_play_text(self, animation, loop: bool, unit: bool, game_object: str = "(player_get 0)") -> str:
        hs_func = "custom_animation_loop" if loop else "custom_animation"
        return f"{hs_func} {game_object} {self.tag_path.RelativePath} {animation.name.replace(' ', ':')} FALSE"
    
    def resource_info(self):
        resource_group = self.tag.SelectField("tag resource groups")
        for element in resource_group.Elements:
            resource = element.SelectField("tag_resource")
            group = element.SelectField("group_members")
            print(group)
            
    def ik_chains_to_blender(self, armature: bpy.types.Object):
        node_names = self.get_nodes()
        
        node_bone_dict = {}
        
        for bone in armature.pose.bones:
            for node in node_names:
                if utils.remove_node_prefix(bone.name) == utils.remove_node_prefix(node):
                    node_bone_dict[node] = bone
        
        for element in self.block_ik_chains.Elements:
            name = element.SelectField("name").GetStringData()
            start_node_index = element.SelectField("start node").Value
            effector_node_index = element.SelectField("effector node").Value
            start_node = node_names[start_node_index] if start_node_index > -1 else None
            effector_node = node_names[effector_node_index] if effector_node_index > -1 else None
            
            start_bone = node_bone_dict[start_node] if start_node is not None else ""
            effector_bone = node_bone_dict[effector_node] if effector_node is not None else ""
            
            blender_ik_chains = bpy.context.scene.nwo.ik_chains
            
            chain = blender_ik_chains.get(name)
            if chain is None:
                chain = blender_ik_chains.add()
                
            chain.name = name
            chain.start_node = start_bone.name
            chain.effector_node = effector_bone.name
            
        print(f"Added / Updated {self.block_ik_chains.Elements.Count} IK Chains")
        
            
    def generate_renames(self, filter=""):
        '''Reads current blender animation names and then parses in the mode n state graph to set up renames in blender'''
        # dict with keys as blender animations and values as sets of renames
        real_animations = {anim: [rename.name.lower().replace(":", " ").split() for rename in anim.animation_renames] for anim in bpy.context.scene.nwo.animations}
        if filter:
            real_animations = {k: v for k, v in real_animations.items() if filter in k}
        graph_animation_names = self.get_animation_names(filter)
        
        graph_animations = defaultdict(list) # dict of graph animation names and animation token names
        current_animation = ["any", "any", "any", "any"] # modes, weapon class, weapon type, sets
        for m in self.block_modes.Elements:
            current_animation[0] = m.Fields[0].GetStringData()
            for wc in m.SelectField("Block:weapon class").Elements:
                current_animation[1] = wc.Fields[0].GetStringData()
                for wt in wc.SelectField("Block:weapon type").Elements:
                    current_animation[2] = wt.Fields[0].GetStringData()
                    for s in wt.SelectField("Block:sets").Elements:
                        current_animation[3] = s.Fields[0].GetStringData()
                        
                        for a in s.SelectField("Block:actions").Elements:
                            animation_index = a.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value
                            if animation_index > -1:
                                graph_animations[graph_animation_names[animation_index]].append(current_animation + [a.Fields[0].GetStringData()])
                            
                        for oa in s.SelectField("Block:overlay animations").Elements:
                            animation_index = oa.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value
                            if animation_index > -1:
                                graph_animations[graph_animation_names[animation_index]].append(current_animation + [oa.Fields[0].GetStringData()])
                            
                        for dad in s.SelectField("Block:death and damage").Elements:
                            dad_label = dad.Fields[0].GetStringData()
                            for d in dad.SelectField("Block:directions").Elements:
                                for r in d.SelectField("Block:regions").Elements:
                                    animation_index = r.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value
                                    if animation_index > -1:
                                        graph_animations[graph_animation_names[animation_index]].append(current_animation + [dad_label, directions[d.ElementIndex], regions[r.ElementIndex]])
                                        
                        for t in s.SelectField("Block:transitions").Elements:
                            t_label = t.Fields[0].GetStringData()
                            for td in t.SelectField("Block:destinations").Elements:
                                animation_index = td.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value
                                if animation_index > -1:
                                    graph_animations[graph_animation_names[animation_index]].append(current_animation + [t_label, "2", td.Fields[0].GetStringData(), td.Fields[1].GetStringData()])
        
        
        def is_rename(rename: list, name: list, existing_renames: list):
            rename_no_any = [i for i in rename if i != "any"]
            name_no_any = [j for j in name if j != "any"]
            
            if rename_no_any != name_no_any:
                for existing_rename in existing_renames:
                    if rename_no_any == [k for k in existing_rename if k != "any"]:
                        return False
                    
                return True
            
            return False
        
        animations_with_renames_count = 0
        renames_count = 0
        for blender_animation, renames in real_animations.items():
            import_animation_name = blender_animation.name.lower().replace(" ", ":")
            graph_animation = graph_animations.get(import_animation_name)
            if graph_animation is None:
                continue
            
            for rename in graph_animation:
                if is_rename(rename, import_animation_name.split(":"), renames):
                    renames.append(rename)
                    
            if renames:
                animations_with_renames_count += 1
                renames_count += len(renames)
                blender_animation.animation_renames.clear()
                str_renames =  [' '.join(map(str, l)) for l in renames]
                for verified_rename in sorted(str_renames):
                    blender_animation.animation_renames.add().name = verified_rename
                    
                    
        print(f"Found {animations_with_renames_count} animations with renames out of {len(graph_animation_names)} total animations. {renames_count} total renames generated")
            