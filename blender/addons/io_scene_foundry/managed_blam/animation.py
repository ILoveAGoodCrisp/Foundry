

from collections import defaultdict
from contextlib import nullcontext
from enum import Enum
from pathlib import Path
from typing import cast
import bpy
from mathutils import Matrix, Quaternion, Vector

from .frame_event_list import AnimationEvent, DialogueEvent, EffectEvent, FrameEventListTag, Reference, SoundEvent

from .Tags import TagFieldBlockElement

from .animation_resource import (
    AnimationCodecType,
    AnimationResourceData,
    BinaryReader,
    CurveCodec,
    DefaultAnimationNode,
    ExpandedAnimation,
    FrameInfoType as ResourceFrameInfoType,
    RevisedCurveCodec,
    SharedStaticCodecData,
    apply_movement_data,
    apply_shared_static_codec,
    build_expanded_animation,
    compose_overlay_animation,
    compose_replacement_animation,
    default_frame_channels,
)
from .source_tag_resource import read_model_animation_graph_resources
from .render_model import RenderModelTag
from . import Tag
from ..legacy.jma import Node
from .. import utils

tolerance = 1e-6

EVENT_TYPE_FRAME = "_connected_geometry_animation_event_type_frame"
EVENT_TYPE_OBJECT_FUNCTION = "_connected_geometry_animation_event_type_object_function"
EVENT_TYPE_IMPORT = "_connected_geometry_animation_event_type_import"
EVENT_TYPE_WRINKLE_MAP = "_connected_geometry_animation_event_type_wrinkle_map"
EVENT_TYPE_IK_ACTIVE = "_connected_geometry_animation_event_type_ik_active"
EVENT_TYPE_IK_PASSIVE = "_connected_geometry_animation_event_type_ik_passive"

RESOURCE_SECTION_ORDER = (
    "static_node_flags",
    "animated_node_flags",
    "movement_data",
    "pill_offset_data",
    "default_data",
    "uncompressed_data",
    "compressed_data",
    "blend_screen_data",
    "object_space_offset_data",
    "ik_chain_event_data",
    "ik_chain_control_data",
    "ik_chain_proxy_data",
    "ik_chain_pole_vector_data",
    "uncompressed_object_space_data",
    "fik_anchor_data",
    "uncompressed_object_space_node_flags",
    "compressed_event_curve",
    "shared_static_data_size",
)

WRINKLE_FACE_REGION_MAP = {
    "upper_brow": "Upper Brow",
    "center_brow": "Center Brow",
    "left_squint": "Left Squint",
    "right_squint": "Right Squint",
    "left_smile": "Left Smile",
    "right_smile": "Right Smile",
    "left_sneer": "Left Sneer",
    "right_sneer": "Right Sneer",
}

IK_TARGET_USAGE_MAP = {
    "self": "self",
    "primary_weapon": "primary_weapon",
    "secondary_weapon": "secondary_weapon",
    "parent": "parent",
    "assassination": "assassination",
}

damage_states = "h_ping", "s_ping", "h_kill", "s_kill"
directions = "front", "left", "right", "back"
regions = "gut", "chest", "head", "l_arm", "l_hand", "l_leg", "l_foot", "r_arm", "r_hand", "r_leg", "r_foot"

class AnimationType(Enum):
    none = 0
    base = 1
    overlay = 2
    replacement = 3
    
class FrameInfoType(Enum):
    none = 0
    dx_dy = 1
    dx_dy_dyaw = 2
    dx_dy_dz_dyaw = 3
    dx_dy_dz_dangle_axis = 4
    
class Compression(Enum):
    medium_compression = 0
    rough_compression = 1
    uncompressed = 2
    old_codec = 3

class Animation:
    def __init__(self):
        self.name = ""
        self.index = -1
        self.parent_animation: Animation = None
        self.next_animation: Animation = None
        self.frame_count = 0
        self.animation_type = AnimationType.none
        self.frame_info_type = FrameInfoType.none
        self.compression = Compression.medium_compression
        self.resource_group = -1
        self.resource_group_member = -1
        self.element: TagFieldBlockElement = None
        self.state_types = set()
        
    def from_element(self, element: TagFieldBlockElement):
        self.name = element.Fields[0].GetStringData()
        self.index = element.ElementIndex
        self.frame_count = element.SelectField("Block:shared animation data[0]/ShortInteger:frame count").Data
        
    def __repr__(self):
        return self.name
        

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
        self.block_sound_references = self.tag.SelectField("Struct:definitions[0]/Block:sound references")
        self.block_effect_references = self.tag.SelectField("Struct:definitions[0]/Block:effect references")
        
    def get_frame_event_list(self) -> str:
        '''Returns the animation graph's frame event list filepath'''
        file = self.tag.SelectField("Struct:definitions[0]/Reference:imported events").Path
        if not file:
            return ""
        
        return file.Filename
        
        
    def get_animation_names(self, filter="") -> list[str]:
        """Returns a list of all animation names"""
        if filter:
            return [element.Fields[0].GetStringData() for element in self.block_animations.Elements if filter in element.Fields[0].GetStringData()]
        else:
            return [element.Fields[0].GetStringData() for element in self.block_animations.Elements]
        
    def get_animations(self, filter="") -> list[str]:
        """Returns a list of all animation"""
        def make_animation(element):
            anim = Animation()
            anim.from_element(element)
            return anim
        
        if filter:
            return [make_animation(element) for element in self.block_animations.Elements if filter in element.Fields[0].GetStringData()]
        else:
            return [make_animation(element) for element in self.block_animations.Elements]
        
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
                
        node_usage_dict = _node_usage_dict(self.scene_nwo)
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

    def _select_field_candidates(self, container, *paths):
        if container is None:
            return None
        for path in paths:
            if not path:
                continue
            variants = [path]
            underscore_variant = path.replace(" ", "_")
            if underscore_variant not in variants:
                variants.append(underscore_variant)
            space_variant = path.replace("_", " ")
            if space_variant not in variants:
                variants.append(space_variant)
            for variant in variants:
                try:
                    field = container.SelectField(variant)
                except Exception:
                    field = None
                if field is not None:
                    return field
        return None

    def _field_int(self, container, *paths, default=None):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return default
        for attr in ("Value", "Data"):
            try:
                return int(getattr(field, attr))
            except Exception:
                pass
        try:
            return int(field.GetStringData())
        except Exception:
            return default

    def _field_string(self, container, *paths, default=""):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return default
        try:
            return field.GetStringData()
        except Exception:
            pass
        try:
            return str(field.Data)
        except Exception:
            return default

    def _field_enum_string(self, container, *paths, default=""):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return default
        try:
            items = field.Items
            index = int(field.Value)
            try:
                count = int(items.Count)
            except Exception:
                count = len(items)
            if 0 <= index < count:
                return str(items[index].EnumName)
        except Exception:
            pass
        try:
            return field.GetStringData()
        except Exception:
            return default

    def _field_float(self, container, *paths, default=None):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return default
        for attr in ("Data", "Value"):
            try:
                return float(getattr(field, attr))
            except Exception:
                pass
        try:
            return float(field.GetStringData())
        except Exception:
            return default

    def _field_data_bytes(self, container, *paths):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return None
        try:
            return bytes(field.GetData())
        except Exception:
            return None

    def _field_vector(self, container, *paths, default=None):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return default.copy() if hasattr(default, "copy") else default
        for attr in ("Data", "Value"):
            try:
                values = tuple(float(component) for component in getattr(field, attr))
                if len(values) == 3:
                    return Vector(values)
            except Exception:
                pass
        try:
            values = tuple(float(component.strip()) for component in field.GetStringData().split(","))
            if len(values) == 3:
                return Vector(values)
        except Exception:
            pass
        return default.copy() if hasattr(default, "copy") else default

    def _field_quaternion(self, container, *paths, default=None):
        field = self._select_field_candidates(container, *paths)
        if field is None:
            return default.copy() if hasattr(default, "copy") else default
        for attr in ("Data", "Value"):
            try:
                values = tuple(float(component) for component in getattr(field, attr))
                if len(values) == 4:
                    return Quaternion((values[3], values[0], values[1], values[2]))
            except Exception:
                pass
        try:
            values = tuple(float(component.strip()) for component in field.GetStringData().split(","))
            if len(values) == 4:
                return Quaternion((values[3], values[0], values[1], values[2]))
        except Exception:
            pass
        return default.copy() if hasattr(default, "copy") else default

    def _normalized_field_name(self, value):
        if not value:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        text = text.rsplit("/", 1)[-1]
        text = text.rsplit(":", 1)[-1]
        return text.replace(" ", "_").lower()

    def _iter_sequence(self, value):
        if value is None:
            return
        try:
            count = value.Count
        except Exception:
            count = None
        if count is not None:
            for index in range(count):
                try:
                    yield value[index]
                except Exception:
                    continue
            return
        try:
            for item in value:
                yield item
        except Exception:
            return

    def _iter_resource_structs(self, container):
        pending = [container]
        seen = set()
        while pending:
            current = pending.pop(0)
            if current is None:
                continue
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)

            has_fields = False
            try:
                if current.Fields is not None:
                    has_fields = True
            except Exception:
                has_fields = False
            if has_fields:
                yield current

            for attr in ("Element", "Value", "Data", "Reference"):
                try:
                    child = getattr(current, attr)
                except Exception:
                    child = None
                if child is not None:
                    pending.append(child)

            try:
                structs = current.Structs
            except Exception:
                structs = None
            if structs is not None:
                for struct in self._iter_sequence(structs):
                    pending.append(struct)

    def _find_direct_child_field(self, container, *names):
        field = self._select_field_candidates(container, *names)
        if field is not None:
            return field

        targets = {self._normalized_field_name(name) for name in names if name}
        targets.discard("")
        if not targets:
            return None

        for struct in self._iter_resource_structs(container):
            try:
                fields = struct.Fields
            except Exception:
                continue
            for field in self._iter_sequence(fields):
                for attr in ("FieldName", "DisplayName", "FieldPathWithoutindices", "FieldPath"):
                    try:
                        candidate = getattr(field, attr)
                    except Exception:
                        candidate = None
                    if self._normalized_field_name(candidate) in targets:
                        return field
        return None

    def _block_element_count(self, block_field):
        if block_field is None:
            return 0
        try:
            elements = block_field.Elements
        except Exception:
            return 0
        try:
            return int(elements.Count)
        except Exception:
            try:
                return len(elements)
            except Exception:
                return 0

    def _block_element_at(self, block_field, index):
        if block_field is None or index < 0:
            return None
        try:
            elements = block_field.Elements
        except Exception:
            return None
        try:
            return elements[index]
        except Exception:
            try:
                return list(elements)[index]
            except Exception:
                return None

    def _get_shared_animation_element(self, animation_element: TagFieldBlockElement) -> TagFieldBlockElement | None:
        shared_block = animation_element.SelectField("Block:shared animation data")
        if shared_block is not None and shared_block.Elements.Count:
            return shared_block.Elements[0]
        
        graph_reference = animation_element.SelectField("Struct:shared animation reference[0]/Reference:graph reference")
        reference_index = animation_element.SelectField("Struct:shared animation reference[0]/ShortInteger:shared animation index")

        if reference_index < 0 or reference_index >= self.block_animations.Elements.Count:
            return None

        if graph_reference is not None:
            try:
                ref_path = graph_reference.Path
            except Exception:
                ref_path = None
            if ref_path is not None and ref_path.RelativePathWithExtension != self.tag_path.RelativePathWithExtension:
                return None

        reference_element = self.block_animations.Elements[reference_index]
        shared_block = reference_element.SelectField("Block:shared animation data")
        if shared_block is not None and shared_block.Elements.Count:
            return shared_block.Elements[0]

    def _build_default_animation_nodes(self, graph_node_names: list[str], model: RenderModelTag | None = None):
        identity_translation = Vector((0.0, 0.0, 0.0))
        identity_rotation = Quaternion((1.0, 0.0, 0.0, 0.0))

        parent_indices = []
        for index, _ in enumerate(graph_node_names):
            skeleton_element = self.block_skeleton_nodes.Elements[index]
            parent_index = skeleton_element.SelectField("parent node index").Value
            if parent_index is None or parent_index < 0 or parent_index >= len(graph_node_names):
                parent_index = -1
            parent_indices.append(parent_index)

        graph_nodes = {}
        stripped_graph_nodes = {}
        indexed_graph_nodes = []
        graph_name_mismatches = []
        if self.block_additional_node_dat is not None:
            for index, element in enumerate(self.block_additional_node_dat.Elements):
                name = element.Fields[0].GetStringData()
                translation = self._to_vector(element.SelectField("default translation").Data)
                rotation = self._to_quaternion(element.SelectField("default rotation").Data)
                scale = element.SelectField("default scale").Data
                node_data = (translation * 100.0, rotation, scale)
                indexed_graph_nodes.append(node_data)

                if name:
                    graph_nodes[name] = node_data
                    stripped_graph_nodes.setdefault(utils.remove_node_prefix(name), node_data)

                    if index < len(graph_node_names):
                        expected_name = graph_node_names[index]
                        if name != expected_name and utils.remove_node_prefix(name) != utils.remove_node_prefix(expected_name):
                            graph_name_mismatches.append((expected_name, name))

        render_nodes = {}
        stripped_render_nodes = {}
        if model is not None:
            for element in model.block_nodes.Elements:
                name = element.SelectField("name").GetStringData()
                translation = Vector((*element.SelectField("default translation").Data,)) * 100
                rotation = element.SelectField("default rotation").Data
                quaternion = Quaternion((rotation[3], rotation[0], rotation[1], rotation[2]))
                render_nodes[name] = (translation, quaternion, 1.0)
                stripped_render_nodes.setdefault(utils.remove_node_prefix(name), (translation, quaternion, 1.0))

        defaults: list[DefaultAnimationNode] = []
        overlay_defaults: list[DefaultAnimationNode] = []
        nodes: list[Node] = []
        graph_fallback_nodes = []
        missing_nodes = []

        for index, name in enumerate(graph_node_names):
            parent_index = parent_indices[index]
            node_data = None
            if model is not None:
                node_data = render_nodes.get(name)
                if node_data is None:
                    node_data = stripped_render_nodes.get(utils.remove_node_prefix(name))
            if node_data is None and index < len(indexed_graph_nodes):
                node_data = indexed_graph_nodes[index]
            if node_data is None:
                node_data = graph_nodes.get(name)
            if node_data is None:
                node_data = stripped_graph_nodes.get(utils.remove_node_prefix(name))
            if node_data is None:
                missing_nodes.append(name)
                translation = identity_translation.copy()
                quaternion = identity_rotation.copy()
                scale = 1.0
            else:
                if model is not None and (name not in render_nodes and utils.remove_node_prefix(name) not in stripped_render_nodes):
                    graph_fallback_nodes.append(name)
                translation, quaternion, scale = node_data

            overlay_node_data = indexed_graph_nodes[index] if index < len(indexed_graph_nodes) else None
            if overlay_node_data is None:
                overlay_node_data = graph_nodes.get(name)
            if overlay_node_data is None:
                overlay_node_data = stripped_graph_nodes.get(utils.remove_node_prefix(name))

            if overlay_node_data is None:
                overlay_translation = translation.copy()
                overlay_quaternion = quaternion.copy()
                overlay_scale = scale
            else:
                overlay_translation, overlay_quaternion, overlay_scale = overlay_node_data

            defaults.append(DefaultAnimationNode(name, parent_index, translation.copy(), quaternion.copy(), scale))
            overlay_defaults.append(
                DefaultAnimationNode(
                    name,
                    parent_index,
                    overlay_translation.copy(),
                    overlay_quaternion.copy(),
                    overlay_scale,
                )
            )
            nodes.append(Node(name, parent_index))

        for node in nodes:
            if node.parent_index > -1:
                node.parent = nodes[node.parent_index]

        if model is not None and graph_fallback_nodes:
            utils.print_warning(f"Native animation import could not match {len(graph_fallback_nodes)} graph nodes to render model defaults. Falling back to additional node data for those nodes.")
        if graph_name_mismatches:
            utils.print_warning(f"Native animation import found {len(graph_name_mismatches)} additional node data entries whose names do not match the skeleton node at the same index. Using index order for graph defaults.")
        if missing_nodes:
            source = "render model or additional node data" if model is not None else "additional node data"
            utils.print_warning(f"Native animation import could not match {len(missing_nodes)} graph nodes to {source} defaults. Missing nodes will use identity transforms.")

        return defaults, nodes, overlay_defaults

    def _read_shared_static_codec(self):
        rotations_block = self.tag.SelectField("Struct:codec data[0]/Struct:shared static codec[0]/Block:rotations")
        if rotations_block is None:
            return None

        translations_block = self._select_field_candidates(
            self.tag,
            "Struct:codec data[0]/Struct:shared static codec[0]/Block:translations",
            "codec data[0]/shared static codec[0]/translations",
            "codec data/shared static codec/translations",
        )
        scales_block = self._select_field_candidates(
            self.tag,
            "Struct:codec data[0]/Struct:shared static codec[0]/Block:scale",
            "codec data[0]/shared static codec[0]/scale",
            "codec data/shared static codec/scale",
        )

        rotations = []
        for element in rotations_block.Elements:
            rotations.append(
                (
                    self._field_int(element, "ShortInteger:i", "i", default=0),
                    self._field_int(element, "ShortInteger:j", "j", default=0),
                    self._field_int(element, "ShortInteger:k", "k", default=0),
                    self._field_int(element, "ShortInteger:w", "w", default=0),
                )
            )

        translations = []
        if translations_block is not None:
            for element in translations_block.Elements:
                translations.append(
                    Vector(
                        (
                            self._field_float(element, "Real:x", "x", default=0.0),
                            self._field_float(element, "Real:y", "y", default=0.0),
                            self._field_float(element, "Real:z", "z", default=0.0),
                        )
                    )
                )

        scales = []
        if scales_block is not None:
            for element in scales_block.Elements:
                scales.append(self._field_float(element, "Real:scale", "scale", default=1.0))

        return SharedStaticCodecData(rotations, translations, scales)

    def _read_animation_resource_indices(self, *containers):
        group_paths = (
            "ShortBlockIndex:resource group index",
            "resource group index",
            "ShortInteger:resource group index",
            "ShortBlockIndex:resource group",
            "ShortInteger:resource group",
            "resource group",
        )
        member_paths = (
            "ShortBlockIndex:resource group member index",
            "resource group member index",
            "ShortInteger:resource group member index",
            "ShortBlockIndex:resource group member",
            "ShortInteger:resource group member",
            "resource group member",
        )
        for container in containers:
            if container is None:
                continue
            group_index = self._field_int(container, *group_paths, default=-1)
            member_index = self._field_int(container, *member_paths, default=-1)
            if group_index >= 0 and member_index >= 0:
                return group_index, member_index
        return -1, -1

    def _serialized_tag_bytes(self):
        cache = getattr(self, "_native_serialized_tag_bytes", None)
        if cache is not None:
            return cache

        try:
            with open(self.system_path, "rb") as handle:
                cache = handle.read()
        except Exception as exc:
            raise ValueError(f"Failed to read source tag bytes for native animation decode: {exc}") from exc

        self._native_serialized_tag_bytes = cache
        return cache

    def _load_source_animation_resource_groups(self):
        cache = getattr(self, "_native_source_resource_groups", None)
        if cache is not None:
            return cache

        self._native_anim_debug("Reading source animation resource groups from model_animation_graph")
        cache = read_model_animation_graph_resources(self._serialized_tag_bytes())
        self._native_anim_debug(f"Loaded {len(cache)} source animation resource groups")
        self._native_source_resource_groups = cache
        return cache

    def _get_source_animation_resource_member(self, group_index, member_index):
        groups = self._load_source_animation_resource_groups()
        if group_index < 0 or group_index >= len(groups):
            raise ValueError(f"Animation resource group index {group_index} is out of range")

        members = groups[group_index]
        if member_index < 0 or member_index >= len(members):
            raise ValueError(f"Animation resource group member index {member_index} is out of range")

        return members[member_index]

    def _native_anim_debug(self, message):
        return
        print(f"[Foundry Native Animation] {message}")

    def _select_animation_resource_group_members(self, container, _depth=0):
        if container is None or _depth > 4:
            return None

        group_members = self._find_direct_child_field(
            container,
            "group_members",
            "resource_group_members",
        )
        if group_members is not None:
            return group_members

        for resource_name in ("tag_resource", "resource_data", "pageable resource"):
            resource_field = self._find_direct_child_field(container, resource_name)
            if resource_field is None:
                continue
            nested_group_members = self._select_animation_resource_group_members(resource_field, _depth + 1)
            if nested_group_members is not None:
                return nested_group_members

        return None

    def _resolve_animation_resource_member(self, group_index, member_index):
        candidate_groups = []

        resource_groups = self._select_field_candidates(self.tag, "Block:tag resource groups", "tag resource groups")
        if resource_groups is not None and group_index < resource_groups.Elements.Count:
            candidate_groups.append(resource_groups.Elements[group_index])

        if 0 <= group_index < self.block_animations.Elements.Count:
            candidate_groups.append(self.block_animations.Elements[group_index])

        if not candidate_groups:
            raise ValueError(f"Animation resource group index {group_index} is out of range")

        for group_element in candidate_groups:
            group_members = self._select_animation_resource_group_members(group_element)
            if group_members is None or member_index >= self._block_element_count(group_members):
                continue
            member = self._block_element_at(group_members, member_index)
            if member is not None:
                return member

        raise ValueError(f"Animation resource group member index {member_index} is out of range")

    def _resolve_animation_payload_member(self, member, member_index):
        animation_data = self._field_data_bytes(member, "Data:animation_data", "animation_data")
        if animation_data:
            return member, animation_data

        nested_group_members = self._select_animation_resource_group_members(member)
        if nested_group_members is not None and member_index < self._block_element_count(nested_group_members):
            nested_member = self._block_element_at(nested_group_members, member_index)
            animation_data = self._field_data_bytes(nested_member, "Data:animation_data", "animation_data")
            if animation_data:
                return nested_member, animation_data

        raise ValueError("Animation resource member has no animation data payload")

    def _read_animation_resource_data(self, animation_element, shared_data_element, shared_static_codec):
        animation_name = self._field_string(animation_element, "String:name", "name", default=f"animation[{animation_element.ElementIndex}]")
        group_index, member_index = self._read_animation_resource_indices(shared_data_element, animation_element)
        if group_index < 0 or member_index < 0:
            raise ValueError("Animation resource group indices are missing")

        animation_data = None
        frame_count = self._field_int(shared_data_element, "ShortInteger:frame count", "frame count", default=0)
        node_count = len(self.get_nodes())
        checksum = 0
        movement_type = self._field_int(shared_data_element, "CharEnum:frame info type", "frame info type", default=0)
        static_flags_size = 0
        animated_flags_size = 0
        movement_data_size = 0
        static_data_size = 0
        shared_static_size = 0

        source_member_error = None
        try:
            source_member = self._get_source_animation_resource_member(group_index, member_index)
        except Exception as exc:
            source_member_error = exc
            source_member = None

        if source_member is not None:
            animation_data = source_member.animation_data
            frame_count = source_member.frame_count or frame_count
            node_count = source_member.node_count or node_count
            checksum = source_member.animation_checksum
            movement_type = source_member.movement_data_type
            flag_triplet_size = ((node_count + 31) // 32) * 4
            static_codec_size = source_member.static_flags_size
            animated_codec_size = source_member.animated_flags_size
            static_flags_size = flag_triplet_size
            animated_flags_size = flag_triplet_size
            movement_data_size = source_member.movement_data_size
            static_data_size = source_member.static_data_size
            shared_static_size = source_member.shared_static_data_size
            self._native_anim_debug(
                f"{animation_name}: source resource group={group_index} member={member_index} "
                f"frames={frame_count} nodes={node_count} static_codec={static_codec_size} "
                f"animated_codec={animated_codec_size} flag_triplet={flag_triplet_size} "
                f"movement={movement_data_size} raw_bytes={len(animation_data)}"
            )
        else:
            static_codec_size = 0
            animated_codec_size = 0
            member = self._resolve_animation_resource_member(group_index, member_index)
            payload_member, animation_data = self._resolve_animation_payload_member(member, member_index)

            frame_count = self._field_int(
                payload_member,
                "ShortInteger:frame count",
                "frame count",
                default=frame_count,
            )
            node_count = self._field_int(payload_member, "CharInteger:node count", "node count", default=node_count)
            checksum = self._field_int(
                payload_member,
                "LongInteger:animation checksum",
                "animation checksum",
                "LongInteger:checksum",
                "checksum",
                default=0,
            )
            movement_type = self._field_int(
                payload_member,
                "CharEnum:movement data type",
                "movement data type",
                default=movement_type,
            )
            static_flags_size = self._field_int(
                payload_member,
                "Struct:data sizes[0]/LongInteger:static node flags",
                "data sizes[0]/static node flags",
                "Struct:packed data sizes reach[0]/LongInteger:static node flags",
                "packed data sizes reach[0]/static node flags",
                "Struct:packed data sizes[0]/CharInteger:static node flags",
                "packed data sizes[0]/static node flags",
                default=0,
            )
            animated_flags_size = self._field_int(
                payload_member,
                "Struct:data sizes[0]/LongInteger:animated node flags",
                "data sizes[0]/animated node flags",
                "Struct:packed data sizes reach[0]/LongInteger:animated node flags",
                "packed data sizes reach[0]/animated node flags",
                "Struct:packed data sizes[0]/CharInteger:animated node flags",
                "packed data sizes[0]/animated node flags",
                default=0,
            )
            movement_data_size = self._field_int(
                payload_member,
                "Struct:data sizes[0]/LongInteger:movement data",
                "data sizes[0]/movement data",
                "Struct:packed data sizes reach[0]/LongInteger:movement data",
                "packed data sizes reach[0]/movement data",
                "Struct:packed data sizes[0]/ShortInteger:movement data",
                "packed data sizes[0]/movement data",
                default=0,
            )
            static_data_size = self._field_int(
                payload_member,
                "Struct:data sizes[0]/LongInteger:static data size",
                "data sizes[0]/static data size",
                "Struct:packed data sizes reach[0]/LongInteger:static data size",
                "packed data sizes reach[0]/static data size",
                "Struct:packed data sizes[0]/ShortInteger:static data size",
                "packed data sizes[0]/static data size",
                "Struct:data sizes[0]/LongInteger:default data",
                "data sizes[0]/default data",
                "Struct:packed data sizes reach[0]/LongInteger:default data",
                "packed data sizes reach[0]/default data",
                "Struct:packed data sizes[0]/ShortInteger:default data",
                "packed data sizes[0]/default data",
                default=0,
            )
            shared_static_size = self._field_int(
                payload_member,
                "Struct:data sizes[0]/LongInteger:shared static data size",
                "data sizes[0]/shared static data size",
                default=0,
            )
            self._native_anim_debug(
                f"{animation_name}: legacy resource fallback group={group_index} member={member_index} "
                f"frames={frame_count} nodes={node_count} static_flags={static_flags_size} "
                f"animated_flags={animated_flags_size} movement={movement_data_size} raw_bytes={len(animation_data)}"
            )

        if not animation_data:
            if source_member_error is not None:
                raise ValueError(f"Animation resource payload is missing ({source_member_error})") from source_member_error
            raise ValueError("Animation resource payload is missing")

        try:
            frame_info_type = ResourceFrameInfoType(movement_type)
        except ValueError:
            frame_info_type = ResourceFrameInfoType.NONE

        resource_data = AnimationResourceData(
            frame_count,
            node_count,
            checksum,
            frame_info_type,
            static_flags_size,
            animated_flags_size,
            static_data_size,
            movement_data_size=movement_data_size,
            shared_static_data_size=shared_static_size,
            static_codec_size=static_codec_size,
            animated_codec_size=animated_codec_size,
            debug_name=animation_name,
        )
        resource_data.read(BinaryReader(animation_data))
        if shared_static_size:
            if shared_static_codec is None:
                raise ValueError("Animation uses shared static data but the graph codec data could not be read")
            apply_shared_static_codec(resource_data, animation_data, shared_static_codec)
        return resource_data

    def _scene_event_action(self):
        scene = getattr(self.scene_nwo, "id_data", None)
        if scene is None:
            return None
        animation_data = getattr(scene, "animation_data", None)
        if animation_data is None:
            return None
        return animation_data.action

    def _animation_event_action(self, blender_animation):
        for track in getattr(blender_animation, "action_tracks", ()):
            action = getattr(track, "action", None)
            if action is not None:
                return action
        return None

    def _ensure_scene_event_slot(self, action, create=False):
        scene = getattr(self.scene_nwo, "id_data", None)
        if scene is None or action is None:
            return None, None, None

        animation_data = getattr(scene, "animation_data", None)
        if animation_data is None:
            if not create:
                return scene, None, None
            scene.animation_data_create()
            animation_data = scene.animation_data

        slot = None
        if animation_data.action == action and animation_data.last_slot_identifier:
            slot = action.slots.get(animation_data.last_slot_identifier)

        if slot is None and create:
            try:
                slot = action.slots.new("SCENE", scene.name)
            except Exception:
                slot = None

        if slot is not None:
            animation_data.last_slot_identifier = slot.identifier
            animation_data.action = action

        return scene, animation_data, slot

    def _clear_event_value_fcurves(self, blender_animation):
        action = self._animation_event_action(blender_animation)
        if action is None:
            return

        _, _, slot = self._ensure_scene_event_slot(action, create=False)
        if slot is None:
            return

        prefix = f"{blender_animation.path_from_id()}.animation_events["
        fcurves = utils.get_fcurves(action, slot)
        if not fcurves:
            return
        stale_curves = [
            fcurve
            for fcurve in fcurves
            if fcurve.data_path.startswith(prefix) and fcurve.data_path.endswith(".event_value")
        ]
        for fcurve in stale_curves:
            fcurves.remove(fcurve)

    def _iter_block_elements(self, container, *paths):
        block = self._select_field_candidates(container, *paths)
        if block is None:
            return []
        try:
            return list(self._iter_sequence(block.Elements))
        except Exception:
            return []

    def _resolve_object_function_name(self, name):
        normalized = self._normalized_field_name(name)
        if not normalized:
            return ""
        if normalized.startswith("animation_event_function_"):
            return normalized
        if len(normalized) == 1 and normalized.isalpha():
            return f"animation_event_function_{normalized}"
        if normalized in {"left_grip", "right_grip"}:
            return f"animation_event_function_{normalized}"
        return ""

    def _remove_animation_events(self, blender_animation, predicate):
        for index in range(len(blender_animation.animation_events) - 1, -1, -1):
            event = blender_animation.animation_events[index]
            if predicate(event):
                blender_animation.animation_events.remove(index)

    def _new_tag_event(self, blender_animation, event_type, name, start_frame, frame_count):
        blender_event = blender_animation.animation_events.add()
        blender_event.name = name
        blender_event.event_type = event_type
        blender_event.event_id = AnimationEvent().unique_id
        blender_event.frame_frame = blender_animation.frame_start + utils.blender_frame(start_frame)
        if frame_count > 1:
            blender_event.multi_frame = 'range'
            blender_event.frame_range = blender_animation.frame_start + utils.blender_frame(start_frame + frame_count - 1)
        return blender_event

    def _event_values_for_range(self, values, start_frame, frame_count):
        if not values:
            return []

        sample_count = max(int(frame_count), 1)
        if len(values) <= sample_count:
            return [float(values[min(index, len(values) - 1)]) for index in range(sample_count)]

        last_index = len(values) - 1
        result = []
        for frame_offset in range(sample_count):
            index = start_frame + frame_offset
            if index <= 0:
                index = 0
            elif index > last_index:
                index = last_index
            result.append(float(values[index]))

        return result

    def _apply_event_value(self, blender_animation, blender_event, default_value, values, start_frame, frame_count):
        event_values = self._event_values_for_range(values, start_frame, frame_count)

        if not event_values:
            blender_event.event_value = default_value
            return

        first_value = event_values[0]
        if all(abs(value - first_value) <= tolerance for value in event_values[1:]):
            blender_event.event_value = first_value
            return

        blender_event.event_value = first_value
        action = self._animation_event_action(blender_animation)
        _, _, scene_slot = self._ensure_scene_event_slot(action, create=True)
        fcurve = None
        if scene_slot is not None:
            blender_animation.scene_action_slot_identifier = scene_slot.identifier
            fcurves = utils.get_fcurves(action, scene_slot)
            data_path = f"{blender_event.path_from_id()}.event_value"
            if fcurves:
                try:
                    fcurve = fcurves.find(data_path, index=0)
                except TypeError:
                    fcurve = fcurves.find(data_path)
                if fcurve is None:
                    try:
                        fcurve = fcurves.new(data_path=data_path, index=0)
                    except TypeError:
                        fcurve = fcurves.new(data_path)

        if fcurve is not None:
            while fcurve.keyframe_points:
                fcurve.keyframe_points.remove(fcurve.keyframe_points[-1])

            for frame_offset, value in enumerate(event_values):
                frame = blender_animation.frame_start + utils.blender_frame(start_frame + frame_offset)
                keyframe = fcurve.keyframe_points.insert(frame, value)
                keyframe.interpolation = "LINEAR"
            fcurve.update()
        else:
            for frame_offset, value in enumerate(event_values):
                blender_event.event_value = value
                blender_event.keyframe_insert(
                    data_path="event_value",
                    frame=blender_animation.frame_start + utils.blender_frame(start_frame + frame_offset),
                )
        blender_event.event_value = first_value

    def _resource_section_boundaries_from_payload_member(self, payload_member):
        data_sizes = self._find_direct_child_field(
            payload_member,
            "data sizes",
            "packed data sizes",
            "packed data sizes reach",
        )
        if data_sizes is None:
            return {}

        aliases = {
            "static_node_flags": (
                "LongInteger:static node flags",
                "CharInteger:static node flags",
                "static node flags",
            ),
            "animated_node_flags": (
                "LongInteger:animated node flags",
                "CharInteger:animated node flags",
                "animated node flags",
            ),
            "movement_data": (
                "LongInteger:movement data",
                "ShortInteger:movement data",
                "movement data",
            ),
            "pill_offset_data": ("LongInteger:pill offset data", "pill offset data"),
            "default_data": (
                "LongInteger:default data",
                "ShortInteger:default data",
                "LongInteger:static data size",
                "ShortInteger:static data size",
                "default data",
                "static data size",
            ),
            "uncompressed_data": ("LongInteger:uncompressed data", "uncompressed data"),
            "compressed_data": ("LongInteger:compressed data", "compressed data"),
            "blend_screen_data": ("LongInteger:blend screen data", "blend screen data"),
            "object_space_offset_data": ("LongInteger:object space offset data", "object space offset data"),
            "ik_chain_event_data": ("LongInteger:ik chain event data", "ik chain event data"),
            "ik_chain_control_data": ("LongInteger:ik chain control data", "ik chain control data"),
            "ik_chain_proxy_data": ("LongInteger:ik chain proxy data", "ik chain proxy data"),
            "ik_chain_pole_vector_data": ("LongInteger:ik chain pole vector data", "ik chain pole vector data"),
            "uncompressed_object_space_data": (
                "LongInteger:uncompressed object space data",
                "uncompressed object space data",
            ),
            "fik_anchor_data": ("LongInteger:fik anchor data", "fik anchor data"),
            "uncompressed_object_space_node_flags": (
                "LongInteger:uncompressed object space node flags",
                "uncompressed object space node flags",
            ),
            "compressed_event_curve": ("LongInteger:compressed event curve", "compressed event curve"),
            "shared_static_data_size": ("LongInteger:shared static data size", "shared static data size"),
        }

        boundaries = {}
        for name, names in aliases.items():
            value = self._field_int(data_sizes, *names, default=None)
            if value is not None and value >= 0:
                boundaries[name] = int(value)
        return boundaries

    def _resource_section_slice(self, animation_data, boundaries, section_name):
        if not animation_data or not boundaries or section_name not in RESOURCE_SECTION_ORDER:
            return b""

        offset = 0
        sequential_slice = b""
        for current_name in RESOURCE_SECTION_ORDER:
            size = int(boundaries.get(current_name, 0))
            if current_name == section_name:
                end = offset + size
                if size > 0 and 0 <= offset < end <= len(animation_data):
                    sequential_slice = animation_data[offset:end]
                break
            offset += max(size, 0)

        positive_values = [max(int(boundaries.get(name, 0)), 0) for name in RESOURCE_SECTION_ORDER if name in boundaries]
        total_size = sum(positive_values)
        is_non_decreasing = all(next_value >= current_value for current_value, next_value in zip(positive_values, positive_values[1:]))
        looks_like_sizes = bool(sequential_slice) and (
            total_size == len(animation_data)
            or (0 < total_size <= len(animation_data) and not is_non_decreasing)
        )
        if looks_like_sizes:
            return sequential_slice

        section_index = RESOURCE_SECTION_ORDER.index(section_name)
        end = int(boundaries.get(section_name, -1))
        if end >= 0:
            start = 0
            for previous_name in reversed(RESOURCE_SECTION_ORDER[:section_index]):
                if previous_name in boundaries:
                    start = int(boundaries[previous_name])
                    break
            if 0 <= start < end <= len(animation_data):
                return animation_data[start:end]

        if sequential_slice:
            return sequential_slice

        return b""

    def _curve_tangent_component(self, tangent_component, p1, p2):
        tangent = tangent_component / 7.0
        return abs(tangent) * (tangent * 0.300000011920929) + (p2 - p1)

    def _curve_position_scalar(self, time, tangent_1, tangent_2, p1, p2):
        term_1 = (2.0 * (time ** 3.0)) - (3.0 * (time ** 2.0)) + 1.0
        term_2 = (time ** 3.0) - (2.0 * (time ** 2.0)) + time
        term_3 = (3.0 * (time ** 2.0)) - (2.0 * (time ** 3.0))
        term_4 = (time ** 3.0) - (time ** 2.0)
        return (term_1 * p1) + (term_2 * tangent_1) + (term_3 * p2) + (term_4 * tangent_2)

    def _read_scalar_event_curve_track(self, reader, frame_count, key_count, flags, offset, scale):
        values = []
        p1 = 0.0
        p2 = 0.0
        tangent_byte = 0
        current_keyframe = 0
        keyframe_index = 0
        next_keyframe = 0
        keyframes = []

        if (flags & 1) == 0:
            keyframes = [0]
            total = 0
            for _ in range(key_count):
                total += reader.read_u8()
                keyframes.append(total)

        for frame_index in range(frame_count):
            if flags & 1:
                normalized_value = reader.read_s16() / float(0x7FFF)
            else:
                if keyframes and keyframe_index < len(keyframes) and keyframes[keyframe_index] == frame_index and frame_index < frame_count - 1:
                    p1 = reader.read_s16() / float(0x7FFF)
                    tangent_byte = reader.read_u8()
                    p2 = reader.read_s16() / float(0x7FFF)
                    current_keyframe = keyframes[keyframe_index]
                    next_keyframe = keyframes[keyframe_index + 1] if keyframe_index + 1 < len(keyframes) else current_keyframe
                    keyframe_index += 1
                    reader.skip(-2)

                if next_keyframe <= current_keyframe:
                    normalized_value = p2
                else:
                    tangent_1 = self._curve_tangent_component((tangent_byte >> 4) - 7, p1, p2)
                    tangent_2 = self._curve_tangent_component((tangent_byte & 15) - 7, p1, p2)
                    normalized_value = self._curve_position_scalar(
                        (frame_index - current_keyframe) / float(next_keyframe - current_keyframe),
                        tangent_1,
                        tangent_2,
                        p1,
                        p2,
                    )

            values.append(float((normalized_value * scale) + offset))

        return values

    def _decode_embedded_scalar_event_curve(self, curve_data, data_index, expected_frame_count=0):
        if not curve_data or data_index is None or data_index < 0 or len(curve_data) < 20:
            return None

        reader = BinaryReader(curve_data)
        try:
            version = reader.read_u8()
            curve_count = reader.read_u8()
            reader.read_u16()
            metadata_offset = reader.read_u32()
            record_offsets_offset = reader.read_u32()
        except Exception:
            return None

        if curve_count <= 0:
            curve_count = version
        if curve_count <= 0 or data_index >= curve_count:
            return None

        metadata_entry_offset = metadata_offset + (data_index * 2)
        record_offset_entry = record_offsets_offset + (data_index * 4)
        if metadata_entry_offset + 2 > len(curve_data) or record_offset_entry + 4 > len(curve_data):
            return None

        try:
            reader.seek(metadata_entry_offset)
            metadata_frame_count = reader.read_u16()
            reader.seek(record_offset_entry)
            record_offset = reader.read_u32()
        except Exception:
            return None

        frame_count_candidates = []
        if metadata_frame_count > 0:
            frame_count_candidates.append(metadata_frame_count)
        if metadata_frame_count >= 0:
            frame_count_candidates.append(metadata_frame_count + 1)

        if expected_frame_count and frame_count_candidates:
            frame_count = min(
                frame_count_candidates,
                key=lambda candidate: (abs(candidate - expected_frame_count), 0 if candidate == expected_frame_count else 1),
            )
        elif expected_frame_count:
            frame_count = expected_frame_count
        elif frame_count_candidates:
            frame_count = max(frame_count_candidates)
        else:
            frame_count = 0

        if frame_count <= 0 or record_offset < 0 or record_offset + 16 > len(curve_data):
            return None

        try:
            reader.seek(record_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_u16()
            offset = reader.read_f32()
            scale = reader.read_f32()
        except Exception:
            return None

        return self._read_scalar_event_curve_track(reader, frame_count, key_count, flags, offset, scale)

    def _decode_scalar_event_curve(self, animation_element, shared_data_element, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        group_index, member_index = self._read_animation_resource_indices(shared_data_element, animation_element)
        if group_index < 0 or member_index < 0:
            return None

        frame_count = self._field_int(shared_data_element, "ShortInteger:frame count", "frame count", default=0)
        animation_data = None
        boundaries = {}

        try:
            source_member = self._get_source_animation_resource_member(group_index, member_index)
        except Exception:
            source_member = None

        if source_member is not None:
            animation_data = source_member.animation_data
            frame_count = source_member.frame_count or frame_count
            boundaries = getattr(source_member, "section_boundaries", {}) or {}
        else:
            member = self._resolve_animation_resource_member(group_index, member_index)
            payload_member, animation_data = self._resolve_animation_payload_member(member, member_index)
            frame_count = self._field_int(payload_member, "ShortInteger:frame count", "frame count", default=frame_count)
            boundaries = self._resource_section_boundaries_from_payload_member(payload_member)

        curve_data = self._resource_section_slice(animation_data, boundaries, "compressed_event_curve")
        if not curve_data:
            return None

        embedded_values = self._decode_embedded_scalar_event_curve(curve_data, data_index, expected_frame_count)
        if embedded_values:
            return embedded_values

        if frame_count <= 0:
            return None

        try:
            codec_type = AnimationCodecType(curve_data[0])
        except Exception:
            return None

        if codec_type == AnimationCodecType.CURVE:
            codec = CurveCodec(frame_count)
        elif codec_type == AnimationCodecType.REVISED_CURVE:
            codec = RevisedCurveCodec(frame_count)
        else:
            return None

        try:
            codec.read(BinaryReader(curve_data))
        except Exception:
            return None

        if 0 <= data_index < len(codec.scales):
            values = codec.scales[data_index]
            if values:
                return [float(value) for value in values]

        if 0 <= data_index < len(codec.translations):
            values = codec.translations[data_index]
            if values:
                return [float(value.x) for value in values]

        return None

    def _collect_regular_animation_events(self, animation_element):
        shared_data_element = self._get_shared_animation_element(animation_element) or animation_element
        valid_ik_chain_names = {
            chain.name
            for chain in self.scene_nwo.ik_chains
            if getattr(chain, "start_node", "") and getattr(chain, "effector_node", "")
        }
        scalar_curve_cache = {}

        def curve_values(data_index, frame_count):
            if data_index < 0:
                return None
            cache_key = (data_index, max(int(frame_count), 0))
            if cache_key not in scalar_curve_cache:
                scalar_curve_cache[cache_key] = self._decode_scalar_event_curve(
                    animation_element,
                    shared_data_element,
                    data_index,
                    cache_key[1],
                )
            return scalar_curve_cache[cache_key]

        tag_events = []

        for element in self._iter_block_elements(shared_data_element, "Block:extended data events", "extended data events"):
            function_name = self._field_string(element, "StringId:name", "name", default="") or "Extended Data"
            frame_count = max(self._field_int(element, "ShortInteger:frame count", "frame count", default=1), 1)
            data_index = self._field_int(element, "ShortInteger:data index", "CharInteger:data index", "data index", default=-1)
            tag_events.append(
                {
                    "event_type": EVENT_TYPE_OBJECT_FUNCTION,
                    "name": function_name,
                    "start_frame": self._field_int(element, "ShortInteger:start frame", "start frame", default=0),
                    "frame_count": frame_count,
                    "default_value": self._field_float(element, "Real:default value", "default value", default=1.0),
                    "values": curve_values(data_index, frame_count),
                    "object_function_name": self._resolve_object_function_name(function_name),
                }
            )

        for element in self._iter_block_elements(shared_data_element, "Block:import events", "import events"):
            import_name = self._field_string(element, "StringId:import name", "import name", default="") or "Wrapped Left"
            start_frame = self._field_int(
                element,
                "ShortInteger:frame",
                "ShortInteger:import frame",
                "ShortInteger:start frame",
                "frame",
                "import frame",
                "start frame",
                default=0,
            )
            tag_events.append(
                {
                    "event_type": EVENT_TYPE_IMPORT,
                    "name": import_name,
                    "start_frame": start_frame,
                    "frame_count": 1,
                    "import_name": import_name,
                }
            )

        for element in self._iter_block_elements(shared_data_element, "Block:ik chain events", "ik chain events"):
            event_type_name = self._normalized_field_name(self._field_enum_string(element, "CharEnum:event type", "event type", default=""))
            if "passive" in event_type_name:
                event_type = EVENT_TYPE_IK_PASSIVE
            elif "active" in event_type_name:
                event_type = EVENT_TYPE_IK_ACTIVE
            else:
                continue

            chain_name = self._field_string(element, "StringId:chain name", "chain name", default="")
            usage_name = IK_TARGET_USAGE_MAP.get(
                self._normalized_field_name(self._field_enum_string(element, "CharEnum:chain usage", "chain usage", default=""))
            )
            frame_count = max(self._field_int(element, "ShortInteger:frame count", "frame count", default=1), 1)
            data_index = self._field_int(
                element,
                "ShortInteger:effector weight data index",
                "CharInteger:effector weight data index",
                "effector weight data index",
                default=-1,
            )
            tag_events.append(
                {
                    "event_type": event_type,
                    "name": chain_name or "IK Chain Event",
                    "start_frame": self._field_int(element, "ShortInteger:start frame", "start frame", default=0),
                    "frame_count": frame_count,
                    "default_value": self._field_float(element, "Real:default value", "default value", default=1.0),
                    "values": curve_values(data_index, frame_count),
                    "ik_chain": chain_name if chain_name in valid_ik_chain_names else "",
                    "ik_target_usage": usage_name or "",
                    "ik_target_marker_name_override": self._field_string(
                        element,
                        "StringId:proxy marker",
                        "proxy marker",
                        default="",
                    ),
                }
            )

        for element in self._iter_block_elements(shared_data_element, "Block:facial wrinkle events", "facial wrinkle events"):
            wrinkle_name = self._field_string(element, "StringId:wrinkle name", "wrinkle name", default="") or "Wrinkle"
            region_name = WRINKLE_FACE_REGION_MAP.get(
                self._normalized_field_name(self._field_enum_string(element, "CharEnum:region", "region", default=""))
            )
            frame_count = max(self._field_int(element, "ShortInteger:frame count", "frame count", default=1), 1)
            data_index = self._field_int(
                element,
                "ShortInteger:wrinkle data index",
                "CharInteger:wrinkle data index",
                "wrinkle data index",
                default=-1,
            )
            tag_events.append(
                {
                    "event_type": EVENT_TYPE_WRINKLE_MAP,
                    "name": wrinkle_name,
                    "start_frame": self._field_int(element, "ShortInteger:start frame", "start frame", default=0),
                    "frame_count": frame_count,
                    "default_value": self._field_float(element, "Real:default value", "default value", default=0.0),
                    "values": curve_values(data_index, frame_count),
                    "wrinkle_map_face_region": region_name or "",
                }
            )

        tag_events.sort(key=lambda event: (event["start_frame"], event["name"]))
        return tag_events

    def _apply_regular_animation_events(self, animation_element, blender_animation):
        tag_events = self._collect_regular_animation_events(animation_element)
        if not tag_events:
            return 0

        self._clear_event_value_fcurves(blender_animation)
        self._remove_animation_events(blender_animation, lambda event: getattr(event, "event_type", "") != EVENT_TYPE_FRAME)

        for event in tag_events:
            blender_event = self._new_tag_event(
                blender_animation,
                event["event_type"],
                event["name"],
                event["start_frame"],
                event["frame_count"],
            )

            if event["event_type"] == EVENT_TYPE_OBJECT_FUNCTION and event["object_function_name"]:
                blender_event.object_function_name = event["object_function_name"]
                self._apply_event_value(
                    blender_animation,
                    blender_event,
                    event["default_value"],
                    event["values"],
                    event["start_frame"],
                    event["frame_count"],
                )
            elif event["event_type"] == EVENT_TYPE_IMPORT:
                blender_event.import_name = event["import_name"]
            elif event["event_type"] in {EVENT_TYPE_IK_ACTIVE, EVENT_TYPE_IK_PASSIVE}:
                if event["ik_chain"]:
                    blender_event.ik_chain = event["ik_chain"]
                if event["ik_target_usage"]:
                    blender_event.ik_target_usage = event["ik_target_usage"]
                blender_event.ik_target_marker_name_override = event["ik_target_marker_name_override"]
                self._apply_event_value(
                    blender_animation,
                    blender_event,
                    event["default_value"],
                    event["values"],
                    event["start_frame"],
                    event["frame_count"],
                )
            elif event["event_type"] == EVENT_TYPE_WRINKLE_MAP:
                if event["wrinkle_map_face_region"]:
                    blender_event.wrinkle_map_face_region = event["wrinkle_map_face_region"]
                self._apply_event_value(
                    blender_animation,
                    blender_event,
                    event["default_value"],
                    event["values"],
                    event["start_frame"],
                    event["frame_count"],
                )

        return len(tag_events)

    def _get_base_animation_candidates(self, graph: dict, name: str):
        tokens = name.split(":")
        if tokens[-1].startswith("var"):
            tokens.pop(-1)
        if tokens:
            tokens[-1] = "idle"
        return self.find_animation(graph, tokens, ["actions"])

    def _build_native_expanded_animation(self, element, defaults, overlay_defaults, graph, shared_static_codec, resource_cache, expanded_cache):
        index = element.ElementIndex
        if index in expanded_cache:
            return expanded_cache[index]

        shared_data_element = self._get_shared_animation_element(element)
        if shared_data_element is None:
            raise ValueError("Animation has no local shared animation data")

        resource_data = resource_cache.get(index)
        if resource_data is None:
            self._native_anim_debug(f"Building native resource data for {element.SelectField('name').GetStringData()}")
            resource_data = self._read_animation_resource_data(element, shared_data_element, shared_static_codec)
            resource_cache[index] = resource_data

        anim_type = self._field_int(shared_data_element, "CharEnum:animation type", "animation type", default=0)
        self._native_anim_debug(
            f"Expanding {element.SelectField('name').GetStringData()} as anim_type={anim_type} "
            f"frame_count={resource_data.frame_count}"
        )
        expanded = build_expanded_animation(resource_data, defaults, "default" if anim_type in (0, 1) else "neutral")
        if anim_type in (0, 1) and resource_data.movement_data is not None:
            self._native_anim_debug(
                f"Applying movement data from {element.SelectField('name').GetStringData()} to pedestal"
            )
            apply_movement_data(expanded, resource_data.movement_data)
        if anim_type in (2, 3):
            base_candidates = self._get_base_animation_candidates(graph, element.SelectField("name").GetStringData())
            if base_candidates:
                base_element = self.block_animations.Elements[base_candidates[0].index]
                base_animation = self._build_native_expanded_animation(
                    base_element,
                    defaults,
                    overlay_defaults,
                    graph,
                    shared_static_codec,
                    resource_cache,
                    expanded_cache,
                )
                base_frame = base_animation.first_frame()
            else:
                base_frame = default_frame_channels(defaults)

            if anim_type == 2:
                expanded = compose_overlay_animation(expanded, base_frame)
            else:
                expanded = compose_replacement_animation(expanded, base_frame)

        expanded_cache[index] = expanded
        return expanded

    def _native_animation_transforms(self, element, defaults, overlay_defaults, nodes, graph, shared_static_codec, resource_cache, expanded_cache):
        self._native_anim_debug(f"Generating native transforms for {element.SelectField('name').GetStringData()}")
        expanded = self._build_native_expanded_animation(
            element,
            defaults,
            overlay_defaults,
            graph,
            shared_static_codec,
            resource_cache,
            expanded_cache,
        )
        transforms = {}
        for frame_index, frame_matrices in enumerate(expanded.frame_matrices(), start=1):
            transforms[frame_index] = {node: matrix for node, matrix in zip(nodes, frame_matrices)}
        self._native_anim_debug(
            f"Generated {len(transforms)} native frames for {element.SelectField('name').GetStringData()}"
        )
        return transforms
        
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
                elif "defense" in state:
                    yaw_source_value = "defense yaw"
                    pitch_source_value = "defense pitch"
                    weight_source_value = "defense"
                    interpolation_rate = "0.25"
                    
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
                
    def to_blender(self, render_model: str, armature, filter: str, import_pca=False):
        actions = []
        animations = []
        if self.block_animations.Elements.Count < 1:
            return print("No animations found in graph")

        graph = self.to_dict()
        pca_animations = {}
        node_names = self.get_nodes()

        model_context = nullcontext(None)
        if render_model:
            render_model_path = Path(render_model)
            if render_model_path.exists():
                model_context = RenderModelTag(path=render_model_path)
            else:
                utils.print_warning(f"Render model [{render_model_path}] was not found. Falling back to animation graph additional node data for native defaults.")

        with model_context as model:
            defaults, native_nodes, overlay_defaults = self._build_default_animation_nodes(node_names, model)
            shared_static_codec = self._read_shared_static_codec() if self.corinth else None
            native_resource_cache = {}
            native_expanded_cache = {}
            exporter = None
            animation_nodes = None
            nodes_count = len(node_names)

            def ensure_exporter():
                nonlocal exporter, animation_nodes, nodes_count
                if exporter is not None:
                    return True
                if model is None:
                    return False
                exporter = self._AnimationExporter()
                ready = exporter.UseTags(self.tag, model.tag)
                if not ready:
                    return False
                nodes_count = exporter.GetGraphNodeCount()
                from System import Array  # type: ignore

                animation_nodes = [self._GameAnimationNode() for _ in range(nodes_count)]
                animation_nodes = Array[self._GameAnimationNodeType()](animation_nodes)
                return True

            if armature.animation_data is None:
                armature.animation_data_create()

            for element in self.block_animations.Elements:
                name = element.SelectField("name").GetStringData()
                if filter and filter not in name:
                    continue

                index = element.ElementIndex
                shared_data_element = self._get_shared_animation_element(element)
                anim_type = self._field_int(shared_data_element, "CharEnum:animation type", "animation type", default=0)
                frame_info = self._field_int(shared_data_element, "CharEnum:frame info type", "frame info type", default=0)
                overlay = anim_type == 2

                frame_count = self._field_int(shared_data_element, "ShortInteger:frame count", "frame count", default=0)
                if frame_count < 1 and ensure_exporter():
                    frame_count = exporter.GetAnimationFrameCount(index)

                new_name = name.replace(":", " ")
                action = bpy.data.actions.new(new_name)
                slot = action.slots.new("OBJECT", armature.name)
                armature.animation_data.last_slot_identifier = slot.identifier
                armature.animation_data.action = action
                utils.print_step(action.name)
                animation = self.scene_nwo.animations.add()
                animation.name = action.name
                animation.scene_action_slot_identifier = ""
                action.use_frame_range = True
                animation.frame_start = 1
                animation.frame_end = frame_count
                animations.append(animation.name)

                if self.corinth:
                    composite_index = self._field_int(element, "ShortBlockIndex:composite", "composite", default=-1)
                    if composite_index > -1:
                        animation.animation_type = "composite"
                        self._import_composite(animation, composite_index)
                        continue

                    internal_flags = self._select_field_candidates(shared_data_element, "WordFlags:internal flags", "internal flags")
                    if internal_flags is not None and internal_flags.TestBit("contains pca data"):
                        pca_animations[name] = new_name

                match anim_type:
                    case 0 | 1:
                        internal_flags = self._select_field_candidates(shared_data_element, "WordFlags:internal flags", "internal flags")
                        if internal_flags is not None and internal_flags.TestBit("world relative"):
                            animation.animation_type = "world"
                        else:
                            animation.animation_type = "base"
                        match frame_info:
                            case 0:
                                animation.animation_movement_data = "none"
                            case 1:
                                animation.animation_movement_data = "xy"
                            case 2:
                                animation.animation_movement_data = "xyyaw"
                            case 3:
                                animation.animation_movement_data = "xyzyaw"
                            case 4:
                                animation.animation_movement_data = "full"
                    case 2:
                        animation.animation_type = "overlay"
                        offset_nodes = self._select_field_candidates(
                            shared_data_element,
                            "Block:object space offset nodes",
                            "object space offset nodes",
                        )
                        if offset_nodes is not None:
                            for node_element in offset_nodes.Elements:
                                n_index = node_element.Fields[0].Value
                                if n_index < 0 or n_index >= nodes_count:
                                    continue
                                a_node = animation.animation_nodes.add()
                                a_node.name = node_names[n_index]
                                a_node.node_type = "object_space_offset_node"
                                animation.active_animation_node_index = len(animation.animation_nodes) - 1
                    case 3:
                        animation.animation_type = "replacement"
                        parent_nodes = self._select_field_candidates(
                            shared_data_element,
                            "Block:object-space parent nodes",
                            "object-space parent nodes",
                        )
                        if parent_nodes is not None:
                            for node_element in parent_nodes.Elements:
                                n_index = node_element.Fields[0].Value
                                if n_index < 0 or n_index >= nodes_count:
                                    continue
                                a_node = animation.animation_nodes.add()
                                a_node.name = node_names[n_index]
                                a_node.node_type = "replacement_correction_node"
                                animation.active_animation_node_index = len(animation.animation_nodes) - 1

                fik_anchor_nodes = self._select_field_candidates(
                    shared_data_element,
                    "Block:forward-invert kinetic anchor nodes",
                    "forward-invert kinetic anchor nodes",
                )
                if fik_anchor_nodes is not None:
                    for node_element in fik_anchor_nodes.Elements:
                        n_index = node_element.Fields[0].Value
                        if n_index < 0 or n_index >= nodes_count:
                            continue
                        a_node = animation.animation_nodes.add()
                        a_node.name = node_names[n_index]
                        a_node.node_type = "fik_anchor_node"
                        animation.active_animation_node_index = len(animation.animation_nodes) - 1

                self._apply_regular_animation_events(element, animation)

                track = animation.action_tracks.add()
                track.object = armature
                track.action = action
                native_success = False
                imported = False
                if shared_data_element is not None:
                    try:
                        transforms = self._native_animation_transforms(
                            element,
                            defaults,
                            overlay_defaults,
                            native_nodes,
                            graph,
                            shared_static_codec,
                            native_resource_cache,
                            native_expanded_cache,
                        )
                        self._to_armature_action(transforms, armature, action, native_nodes, {}, set())
                        native_success = True
                        imported = True
                    except Exception as ex:
                        utils.print_warning(f"Native animation decode failed for {name}. Falling back to ManagedBlam ({ex})")

                if not native_success:
                    if overlay:
                        utils.print_warning(f"{name} is an overlay, rotations will not be imported")

                    if not ensure_exporter():
                        if model is None:
                            utils.print_warning(
                                f"ManagedBlam fallback is unavailable for {name} because no render model was provided"
                            )
                        else:
                            utils.print_warning(f"Failed to use ManagedBlam animation exporter for {name}")
                        continue

                    if exporter.GetRenderModelBasePose(animation_nodes, nodes_count):
                        nodes = [Node(n.Name, n.ParentIndex) for n in animation_nodes]
                        for node in nodes:
                            if node.parent_index > -1:
                                node.parent = nodes[node.parent_index]

                        node_base_matrices = {}
                        self._get_base_pose(animation_nodes, nodes, node_base_matrices)
                        transforms = {}
                        base_transforms = {}
                        nodes_with_animations = set()
                        for frame in range(frame_count):
                            if exporter.GetAnimationFrame(index, frame, animation_nodes, nodes_count):
                                nodes_with_animations.update(
                                    self._add_transforms(animation_nodes, nodes, frame + 1, overlay, node_base_matrices, transforms)
                                )

                        if anim_type == 3:
                            replacement_base_animations = self._get_base_animation_candidates(graph, name)
                            if replacement_base_animations:
                                for frame in range(frame_count):
                                    if exporter.GetAnimationFrame(replacement_base_animations[0].index, frame, animation_nodes, nodes_count):
                                        self._add_base_transforms(animation_nodes, nodes, frame + 1, node_base_matrices, base_transforms)

                        self._to_armature_action(transforms, armature, action, nodes, base_transforms, nodes_with_animations)
                        imported = True

                if imported:
                    actions.append(action)
                    action.frame_end = frame_count
                else:
                    utils.print_warning(f"Failed to import animation {name}")

        if self.corinth and import_pca:
            pca_groups = []
            pca_path = None
            if pca_animations:
                pca_tagpath = self.tag.SelectField("Struct:definitions[0]/Struct:pca data[0]/Reference:pca animation").Path
                if self.path_exists(pca_tagpath):
                    
                    pca_groups = {}
                    mesh_count = 0
                    for element in self.tag.SelectField("Struct:definitions[0]/Struct:pca data[0]/Block:PCA Groups").Elements:
                        c = element.Fields[1].Data
                        if c < 1:
                            continue
                        pca_groups[mesh_count] = element.Fields[0].GetStringData()
                        mesh_count += c
                        
                    pca_path = pca_tagpath
                    
            return actions, animations, pca_animations, pca_groups, pca_path
        
        return actions, animations
    
    def _to_armature_action(self, transforms, armature: bpy.types.Object, action: bpy.types.Action, nodes: list[Node], base_transforms: dict, nodes_with_animations):
        fcurves = utils.get_fcurves(action, armature.animation_data.last_slot_identifier)
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
                parent = bone_dict.get(bone.parent)
                if parent is None:
                    bone_dict[bone] = 0
                else:
                    bone_dict[bone] = parent + 1
            else:
                bone_dict[bone] = 0
                
        bones_ordered.sort(key=lambda x: bone_dict[x])
        
        bone_base_matrices = {}
        for bone in bones_ordered:
            if bone.parent:
                bone_base_matrices[bone] = bone.parent.matrix.inverted_safe() @ bone.matrix
            else:
                bone_base_matrices[bone] = bone.matrix
        
        base_repeats = 0
        
        for frame_idx, nodes_transforms in transforms.items():
            for node in valid_nodes:
                bind_inv = bone_base_matrices[node.pose_bone].inverted_safe()
                repl_matrix = nodes_transforms[node]
                transform_matrix = bind_inv @ repl_matrix
                base_matrix = Matrix.Identity(4)
                if base_transforms:
                    base_frame_idx = frame_idx - (len(base_transforms) * base_repeats)
                    if base_frame_idx > len(base_transforms):
                        base_repeats += 1
                        base_frame_idx = frame_idx - (len(base_transforms) * base_repeats)
                    base_nodes_transforms = base_transforms[base_frame_idx]
                    if base_nodes_transforms is not None:
                        if node not in nodes_with_animations:
                            base_matrix = base_nodes_transforms[node]
                            
                            delta_base = bind_inv @ base_matrix

                            transform_matrix = delta_base @ transform_matrix

                # decompose the orthogonal result
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
        nodes_with_animations = set()
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            
            if any((an.Translation.X, an.Translation.Y, an.Translation.Z, an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z)) or scale != 1.0:
                nodes_with_animations.add(node)
                
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
                
            rot_is_zero = all(abs(c) < tolerance for c in (an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
                
            if rot_is_zero:
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
        
        return nodes_with_animations
                    
    def _add_base_transforms(self, animation_nodes, nodes, frame, node_base_matrices: dict, base_transforms: dict):
        frame_data = {}
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            base_matrix = cast(Matrix, node_base_matrices[node])
            base_translation, base_rotation, base_scale = base_matrix.decompose()
            if translation.magnitude < tolerance:
                translation = base_translation
            if rotation.magnitude < tolerance:
                rotation = base_rotation

            matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
                
            frame_data[node] = matrix
        
        base_transforms[frame] = frame_data
        
    def _import_composite(self, blender_animation, composite_index: int):
        return # TODO
        composites_block = self.tag.SelectField("Struct:definitions[0]/Block:composites")
        if composites_block.Elements.Count == 0 or composite_index >= composites_block.Elements.Count:
            return
        
        composite = composites_block.Elements[composite_index]

        name = composite.SelectField("StringId:name").GetStringData()
        state = utils.space_partition(name, True)
        axis_1 = composite.SelectField("Block:axes[0]")
        axis_2 = composite.SelectField("Block:axes[1]")
        
        use_groups = state == "locomote"
        
        if axis_1 is None:
            return
        
        blend_axis_1 = blender_animation.blend_axes.add()
        blend_axis_1.name = axis_1.SelectField("name")
        blend_axis_1.animation_source_bounds_manual = True
        blend_axis_1.animation_source_bounds = (*axis_1.SelectField("animation bounds").Data,)
        blend_axis_1.runtime_source_bounds_manual = True
        blend_axis_1.runtime_source_bounds = (*axis_1.SelectField("input bounds").Data,)
        blend_axis_1.runtime_source_clamped = axis_1.SelectField("flags").TestBit("clamped")
        blend_axis_1.animation_source_limit = axis_1.SelectField("blend limit").Data
        
        for dead_zone in axis_1.SelectField("Block:dead zones").Elements:
            blender_dead_zone = blend_axis_1.dead_zones.add()
            blender_dead_zone.bounds = (*dead_zone.SelectField("RealBounds:bounds").Data,)
            blender_dead_zone.rate = 360 / dead_zone.SelectField("Real:rate").Data
            
        if use_groups:
            blender_group = blend_axis_1.groups.add()
        
            
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
            
            blender_ik_chains = self.scene_nwo.ik_chains
            
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
        real_animations = {anim.name.replace(" ", ":"): anim for anim in self.scene_nwo.animations}
        if filter:
            real_animations = {k: v for k, v in real_animations.items() if filter in k}

        graph_dict = self.to_dict()
        renames = detect_renames(graph_dict)
        # renames, copies = detect_copies_from_graph(graph_dict, renames)
        copies = []
        
        for src, dst in renames:
            print(f'renamed "{src}" ==> "{dst}"')

        for src, dst in copies:
            print(f'copied all "{src}" to "{dst}"')
        
        animations_with_renames_count = 0
        renames_count = 0
        
        # add renames to animations
        for src, dst in renames:
            blender_animation = real_animations.get(src)
            if blender_animation is None:
                continue
            
            animations_with_renames_count += 1
            if dst not in {r.name for r in blender_animation.animation_renames}:
                blender_animation.animation_renames.add().name = dst.replace(":", " ")
                
                
        # Add copies
        for src, dst in copies:
            for copy in self.scene_nwo.animation_copies:
                if copy.source_name.replace(":", " ") == src.replace(":", " ") and copy.name.replace(":", " ") == dst.replace(":", " "):
                    break
                
            else:
                new_copy = self.scene_nwo.animation_copies.add()
                new_copy.source_name = src.replace(":", " ")
                new_copy.name = dst.replace(":", " ")
                
        print(f"\Generated {len(renames)} renames from tag and applied these to {animations_with_renames_count} blender animations\nCreated {len(copies)} animation copies")
        
    def _animation_from_index(self, index, state_type="") -> Animation:
        element = self.block_animations.Elements[index]
        animation = Animation()
        animation.from_element(element)
        if state_type:
            animation.state_types.add(state_type)
        return animation
        
    
    def to_dict(self) -> dict:
        '''Parses the mode n state graph and turns it into a dict'''
        graph = {}
        for mode in self.block_modes.Elements:
            mode_label = mode.Fields[0].GetStringData()
            graph[mode_label] = {}
            
            for weapon_class in mode.Fields[4].Elements:
                weapon_class_label = weapon_class.Fields[0].GetStringData()
                graph[mode_label][weapon_class_label] = {}
                
                for weapon_type in weapon_class.Fields[3].Elements:
                    weapon_type_label = weapon_type.Fields[0].GetStringData()
                    graph[mode_label][weapon_class_label][weapon_type_label] = {}
                    
                    for set in weapon_type.Fields[3].Elements:
                        set_label = set.Fields[0].GetStringData()
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label] = {}
                        
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["actions"] = {action.Fields[0].GetStringData(): self._animation_from_index(action.Fields[3].Elements[0].Fields[1].Value, "action") for action in set.Fields[4].Elements if action.Fields[3].Elements[0].Fields[1].Value > -1}
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["overlay_animations"] = {overlay.Fields[0].GetStringData(): self._animation_from_index(overlay.Fields[3].Elements[0].Fields[1].Value, "overlay") for overlay in set.Fields[5].Elements if overlay.Fields[3].Elements[0].Fields[1].Value > -1}
                        
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"] = {}
                        for death_and_damage in set.Fields[6].Elements:
                            death_and_damage_label = death_and_damage.Fields[0].GetStringData()
                            graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"][death_and_damage_label] = {}
                            for direction in death_and_damage.Fields[1].Elements:
                                direction_label = directions[direction.ElementIndex]
                                graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"][death_and_damage_label][direction_label] = {regions[region.ElementIndex]: self._animation_from_index(region.Fields[0].Elements[0].Fields[1].Value, "death and damage") for region in direction.Fields[0].Elements if region.Fields[0].Elements[0].Fields[1].Value > -1}
                                
                            
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["transitions"] = {}
                        
                        for transition in set.Fields[7].Elements:
                            transition_state = transition.Fields[0].GetStringData()
                            graph[mode_label][weapon_class_label][weapon_type_label][set_label]["transitions"][transition_state] = {f"2:{destination.Fields[0].GetStringData()}:{destination.Fields[1].GetStringData()}": self._animation_from_index(destination.Fields[2].Elements[0].Fields[1].Value, "transition") for destination in transition.Fields[1].Elements if destination.Fields[2].Elements[0].Fields[1].Value > -1}
                            
                            
        return graph
    
    def find_animation(self, graph: dict, tokens: list | str, categories: list[str] | None = None):
        '''Finds animations given tokens'''
        if isinstance(tokens, str):
            if ":2:" in tokens:
                p1, p2 = tokens.split(":2:")
                tokens = p1.replace(" ", ":").split(":") + [p2]
            else:
                tokens = tokens.replace(" ", ":").split(":")

        *path_tokens, state_token = tokens

        def walk_tree(level, remaining_tokens, depth=0):
            if not remaining_tokens:
                if any(isinstance(v, dict) for v in level.values()) and not all(
                    k in ("actions", "overlay_animations", "death_and_damage", "transitions") for k in level.keys()
                ):
                    results = []
                    for sublevel in level.values():
                        if isinstance(sublevel, dict):
                            results += walk_tree(sublevel, [], depth + 1)
                    return results

                results = []
                search_categories = categories or ("actions", "overlay_animations", "death_and_damage", "transitions")

                for category in search_categories:
                    cat_data = level.get(category)
                    if not cat_data:
                        continue

                    if category in ("actions", "overlay_animations"):
                        anim = cat_data.get(state_token)
                        if anim:
                            results.append(anim)

                    elif category == "death_and_damage":
                        damage_group = cat_data.get(state_token)
                        if damage_group:
                            for direction in damage_group.values():
                                for animation in direction.values():
                                    results.append(animation)

                    elif category == "transitions":
                        trans_group = cat_data.get(state_token)
                        if trans_group:
                            results.extend(trans_group.values())

                return results

            token = remaining_tokens[0]
            next_tokens = remaining_tokens[1:]

            exact_matches = []
            fallback_matches = []

            if token == "any":
                fallback_matches = [v for v in level.values() if isinstance(v, dict)]
            else:
                if token in level:
                    exact_matches.append(level[token])
                if "any" in level:
                    fallback_matches.append(level["any"])

            results = []
            for branch in exact_matches:
                results += walk_tree(branch, next_tokens, depth + 1)

            if not results:
                for branch in fallback_matches:
                    results += walk_tree(branch, next_tokens, depth + 1)

            return results


        return walk_tree(graph, path_tokens)

    def test_find_animation(self, tokens: list | str, categories=[], graph_dict={}):
        if not graph_dict:
            graph_dict = self.to_dict()
        print("")
        for animation in self.find_animation(graph_dict, tokens):
            print(animation.name, sorted(list(animation.state_types)))
        print("+++++++++++++++++++++++++++++++")
        
    def events_from_blender(self):
        frame_event_list_path = Path(self.tag_path.RelativePath).with_suffix(".frame_event_list")
        with FrameEventListTag(path=frame_event_list_path) as events:
            events.from_blender(self.get_animations())
            
            event_list_tag_ref = self.tag.SelectField("Struct:definitions[0]/Reference:imported events")
            if event_list_tag_ref.Path.RelativePathWithExtension != events.tag_path.RelativePathWithExtension:
                event_list_tag_ref.Path = events.tag_path
                self.tag_has_changes = True
        
    def events_to_blender(self) -> int:
        '''Create frame AnimationEvents from graph and frame_event_list data'''
        event_list_events = {}
        frame_event_list_path = self.get_frame_event_list()
        if not frame_event_list_path:
            utils.print_warning("Animation graph contains no reference to a frame event list")
        elif not Path(frame_event_list_path).exists():
            utils.print_warning(f"Frame events list tag does not exist: {frame_event_list_path}")
        else:
            with FrameEventListTag(path=frame_event_list_path) as events:
                event_list_events = events.collect_events()

        unique_sounds = []
        for element in self.block_sound_references.Elements:
            ref = Reference()
            ref.from_element(element, self.corinth)
            unique_sounds.append(ref)

        unique_effects = []
        for element in self.block_effect_references.Elements:
            ref = Reference()
            ref.from_element(element, self.corinth)
            unique_effects.append(ref)

        blender_animations = {a.name.replace(":", " "): a for a in self.scene_nwo.animations if a.export_this}
        blender_markers = {ob.nwo.marker_model_group: ob for ob in bpy.data.objects if ob.type == 'EMPTY'}
        event_count = 0

        def apply_flags(blender_data_event, reference: Reference):
            blender_data_event.flag_allow_on_player = reference.allow_on_player
            blender_data_event.flag_left_arm_only = reference.left_arm_only
            blender_data_event.flag_right_arm_only = reference.right_arm_only
            blender_data_event.flag_first_person_only = reference.first_person_only
            blender_data_event.flag_third_person_only = reference.third_person_only
            blender_data_event.flag_forward_only = reference.forward_only
            blender_data_event.flag_reverse_only = reference.reverse_only
            blender_data_event.flag_fp_no_aged_weapons = reference.fp_no_aged_weapons

        def collapse_events(animation_events):
            animation_events.sort(key=lambda event: event.frame, reverse=True)
            result = []
            group_end_frame = animation_events[0].frame

            for current, next_event in zip(animation_events, animation_events[1:] + [None]):
                if next_event:
                    if (
                        next_event.frame == current.frame - 1
                        and current.type == next_event.type
                        and not (current.sound_events or current.effect_events or current.dialogue_events)
                    ):
                        continue

                current.end_frame = group_end_frame
                group_end_frame = next_event.frame if next_event else 0
                result.append(current)

            return result

        for animation in self.block_animations.Elements:
            name = self._field_string(animation, "StringId:name", "name", default="")
            if not name:
                continue

            name_with_spaces = name.replace(":", " ")
            blender_animation = blender_animations.get(name_with_spaces)
            if blender_animation is None:
                blender_animation = blender_animations.get(name)
                if blender_animation is None:
                    continue

            utils.print_bullet(f"Getting events for {blender_animation.name}")

            shared_data_element = self._get_shared_animation_element(animation) or animation
            animation_events: list[AnimationEvent] = []

            for element in self._iter_block_elements(shared_data_element, "Block:frame events", "frame events"):
                event = AnimationEvent()
                event.from_element(element, True)
                animation_events.append(event)

            none_event = None

            def make_none_event():
                event = AnimationEvent()
                animation_events.append(event)
                return event

            for element in self._iter_block_elements(shared_data_element, "Block:sound events", "sound events"):
                sound_index = self._field_int(element, "ShortBlockIndex:sound", "sound", default=-1)
                if sound_index < 0:
                    continue

                sound_event = SoundEvent()
                sound_event.from_element(element, unique_sounds, True)
                if sound_event.sound_reference is None:
                    continue

                if none_event is None:
                    none_event = make_none_event()
                none_event.sound_events.append(sound_event)

            for element in self._iter_block_elements(shared_data_element, "Block:effect events", "effect events"):
                effect_index = self._field_int(element, "ShortBlockIndex:effect", "effect", default=-1)
                if effect_index < 0:
                    continue

                effect_event = EffectEvent()
                effect_event.from_element(element, unique_effects, True)
                if effect_event.effect_reference is None:
                    continue

                if none_event is None:
                    none_event = make_none_event()
                none_event.effect_events.append(effect_event)

            for element in self._iter_block_elements(shared_data_element, "Block:dialogue events", "dialogue events"):
                dialogue_event = DialogueEvent()
                dialogue_event.from_element(element, True)

                if none_event is None:
                    none_event = make_none_event()
                none_event.dialogue_events.append(dialogue_event)

            if len(animation_events) > 1:
                animation_events = collapse_events(animation_events)

            list_events = event_list_events.get(name)
            if list_events is not None:
                graph_events = animation_events
                if not graph_events:
                    animation_events = list_events
                else:
                    valid_graph_events = []
                    for graph_event in animation_events:
                        for list_event in list_events:
                            if list_event == graph_event:
                                break
                        else:
                            valid_graph_events.append(graph_event)

                    animation_events = list_events + valid_graph_events

            self._remove_animation_events(blender_animation, lambda event: getattr(event, "event_type", "") == EVENT_TYPE_FRAME)
            if not animation_events:
                continue

            for event in sorted(animation_events, key=lambda value: value.frame):
                blender_event = blender_animation.animation_events.add()
                blender_event.name = event.name
                blender_event.event_type = EVENT_TYPE_FRAME
                blender_event.frame_frame = blender_animation.frame_start + event.frame
                if event.end_frame > event.frame:
                    blender_event.multi_frame = 'range'
                    blender_event.frame_range = blender_animation.frame_start + event.end_frame
                blender_event.frame_name = event.type
                blender_event.event_id = event.unique_id

                data_events = event.sound_events + event.effect_events + event.dialogue_events
                data_events.sort(key=lambda data_event: data_event.frame_offset)

                for data_event in data_events:
                    blender_data_event = blender_event.event_data.add()
                    blender_data_event.frame_offset = data_event.frame_offset
                    if isinstance(data_event, SoundEvent):
                        blender_data_event.data_type = 'SOUND'
                        blender_data_event.marker = blender_markers.get(data_event.marker_name)
                        blender_data_event.event_sound_tag = data_event.sound_reference.tag
                        apply_flags(blender_data_event, data_event.sound_reference)
                    elif isinstance(data_event, EffectEvent):
                        blender_data_event.data_type = 'EFFECT'
                        blender_data_event.marker = blender_markers.get(data_event.marker_name)
                        blender_data_event.event_effect_tag = data_event.effect_reference.tag
                        apply_flags(blender_data_event, data_event.effect_reference)
                        blender_data_event.damage_effect_reporting_type = data_event.damage_effect_reporting_type
                    else:
                        blender_data_event.data_type = 'DIALOGUE'
                        blender_data_event.dialogue_event = data_event.dialogue_type

            event_count += len(animation_events)

        return event_count

def detect_renames(graph):
    name_to_paths = defaultdict(list)

    def walk(path_tokens, node):
        # Categories that hold Animation objects
        for cat in ("actions", "overlay_animations", "transitions", "death_and_damage"):
            if cat not in node:
                continue

            if cat in ("actions", "overlay_animations"):
                for state, anim in node[cat].items():
                    name_to_paths[anim.name].append(":".join(path_tokens + [state]))

            elif cat == "transitions":
                for state, dests in node[cat].items():
                    for key, anim in dests.items():
                        name_to_paths[anim.name].append(":".join(path_tokens + [state, key]))

            elif cat == "death_and_damage":
                for dmg_state, dirs in node[cat].items():
                    for dir_label, regions in dirs.items():
                        for reg_label, anim in regions.items():
                            name_to_paths[anim.name].append(
                                ":".join(path_tokens + [dmg_state, dir_label, reg_label])
                            )

        # Recurse into structural layers
        for k, sub in node.items():
            if isinstance(sub, dict) and k not in (
                "actions",
                "overlay_animations",
                "transitions",
                "death_and_damage",
            ):
                walk(path_tokens + [k], sub)

    walk([], graph)

    renames = []
    for anim_name, paths in name_to_paths.items():
        if len(paths) < 2:
            continue  # unique ⇒ no rename
        canonical_src = ":".join(minimal_path(anim_name.split(":")))
        for p in paths:
            short_p = ":".join(minimal_path(p.split(":")))
            if short_p != canonical_src:
                renames.append((anim_name, short_p))
    return renames


def _strip_trailing_any(toks):
    while toks and toks[-1] == "any":
        toks.pop()
    return toks

def minimal_path(toks):

    # Strip variant markers (…:varX)
    toks = [t for t in toks if not (t.startswith("var") and t[3:].isdigit())]

    # Transition pattern …:state:2:mode:new_state
    if len(toks) >= 5 and toks[-3] == "2":
        base, tail = toks[:-4], toks[-4:]
        return _strip_trailing_any(base) + tail

    # Death & damage …:h_ping:back:gut
    if (
        len(toks) >= 5
        and toks[-3] in damage_states
        and toks[-2] in directions
        and toks[-1] in regions
    ):
        base, tail = toks[:-3], toks[-3:]
        return _strip_trailing_any(base) + tail

    # Normal action / overlay
    head, state = toks[:-1], [toks[-1]]
    return _strip_trailing_any(head) + state
