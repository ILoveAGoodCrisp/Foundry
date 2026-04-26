

from collections import defaultdict
from contextlib import nullcontext
from enum import Enum, IntEnum
from math import degrees
from pathlib import Path
import traceback
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
    FrameInfoType,
    RevisedCurveCodec,
    SharedStaticCodecData,
    apply_movement_data,
    apply_shared_static_codec,
    append_final_frame,
    build_animation,
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

BLEND_SCREEN_CONNECTION_LINEAR_SEGMENT = 0
BLEND_SCREEN_CONNECTION_DELAUNAY_TRIANGLE = 1
BLEND_SCREEN_CONNECTION_SAMPLE_SPHERE_TRIANGLE = 2

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

FINAL_FRAME_MOVEMENT_STATES = (
    "move",
    "jog",
    "run",
    "walk",
    "turn",
    "locomote",
)

FINAL_FRAME_SOFT_TRANSITIONS = (
    "juke",
    "enter",
    "exit",
    "ping",
    "open",
    "close",
    "brace",
    "jump",
    "land",
    "put_away",
    "ready",
    "ejection",
)

FINAL_FRAME_LOOPERS = (
    "idle",
    "melee",
    "go_berserk",
    "evade",
    "airborne",
    "dive",
    "evade",
    "grip",
    "fire_",
    "point",
    "shakefist",
    "smash",
    "surprise",
    "taunt",
    "throw_grenade",
    "warn",
    "advance",
)

WRINKLE_FACE_REGION_MAP = [
    "upper_brow",
    "center_brow",
    "left_squint",
    "right_squint",
    "left_smile",
    "right_smile",
    "left_sneer",
    "right_sneer",
]

IK_TARGET_USAGE_MAP = [
    "none",
    "world",
    "self",
    "parent",
    "primary_weapon",
    "secondary_weapon",
    "assassination",
]

damage_states = "h_ping", "s_ping", "h_kill", "s_kill"
directions = "front", "left", "right", "back"
regions = "gut", "chest", "head", "l_arm", "l_hand", "l_leg", "l_foot", "r_arm", "r_hand", "r_leg", "r_foot"

class AnimationType(IntEnum):
    NONE = 0
    BASE = 1
    OVERLAY = 2
    REPLACEMENT = 3
    
class Compression(Enum):
    medium_compression = 0
    rough_compression = 1
    uncompressed = 2
    old_codec = 3
    reach_medium_compression = 4
    reach_rough_compression = 5

class Animation:
    def __init__(self):
        self.name = ""
        self.index = -1
        self.parent_animation: Animation = None
        self.next_animation: Animation = None
        self.frame_count = 0
        self.animation_type = AnimationType.NONE
        self.frame_info_type = FrameInfoType.NONE
        self.compression = Compression.medium_compression
        self.resource_group = -1
        self.resource_group_member = -1
        self.element: TagFieldBlockElement = None
        self.shared_element: TagFieldBlockElement = None
        self.state_types = set()
        self.world_relative = False
        self.contains_pca_data = False
        self.pca_group = ""
        self.composite_index = -1
        self.is_pose_overlay = False
        
    def from_element(self, element: TagFieldBlockElement, shared_element: TagFieldBlockElement, corinth: bool):
        self.name = utils.AnimationName(element.Fields[0].GetStringData())
        self.index = element.ElementIndex
        self.frame_count = shared_element.SelectField("frame count").Data
        self.animation_type = AnimationType(shared_element.SelectField("animation type").Value)
        self.frame_info_type = FrameInfoType(shared_element.SelectField("frame info type").Value)
        self.compression = Compression(shared_element.SelectField("current compression").Value)
        self.resource_group = shared_element.SelectField("resource_group").Data
        self.resource_group_member = shared_element.SelectField("resource_group_member").Data
        self.element = element
        self.shared_element = shared_element
        
        internal_flags = shared_element.SelectField("internal flags")
        self.world_relative = internal_flags.TestBit("world relative")
        
        self.is_pose_overlay = self.animation_type == AnimationType.OVERLAY and shared_element.SelectField("object-space parent nodes").Elements.Count > 0
        
        if corinth:
            self.composite_index = element.SelectField("composite").Value
            if internal_flags.TestBit("contains pca data"):
                self.contains_pca_data = True
                self.pca_group = element.SelectField("pca group name").GetStringData()
        
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
        
    def get_animations(self) -> list[Animation]:
        """Returns a list of all animations"""
        def make_animation(element):
            shared_animation_element = self._get_shared_animation_element(element)
            if shared_animation_element is not None:
                anim = Animation()
                anim.from_element(element, shared_animation_element, self.corinth)
                return anim
        
        animations = []
        
        for element in self.block_animations.Elements:        
            anim = make_animation(element)
            if anim is not None:
                animations.append(anim)
                
        return animations
        
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

    # def _select_field_candidates(self, container, *paths):
    #     if container is None:
    #         return None
    #     for path in paths:
    #         if not path:
    #             continue
    #         variants = [path]
    #         underscore_variant = path.replace(" ", "_")
    #         if underscore_variant not in variants:
    #             variants.append(underscore_variant)
    #         space_variant = path.replace("_", " ")
    #         if space_variant not in variants:
    #             variants.append(space_variant)
    #         for variant in variants:
    #             try:
    #                 field = container.SelectField(variant)
    #             except Exception:
    #                 field = None
    #             if field is not None:
    #                 return field
    #     return None

    # def _field_int(self, container, *paths, default=None):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return default
    #     for attr in ("Value", "Data"):
    #         try:
    #             return int(getattr(field, attr))
    #         except Exception:
    #             pass
    #     try:
    #         return int(field.GetStringData())
    #     except Exception:
    #         return default

    # def _field_string(self, container, *paths, default=""):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return default
    #     try:
    #         return field.GetStringData()
    #     except Exception:
    #         pass
    #     try:
    #         return str(field.Data)
    #     except Exception:
    #         return default

    # def _field_enum_string(self, container, *paths, default=""):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return default
    #     try:
    #         items = field.Items
    #         index = int(field.Value)
    #         try:
    #             count = int(items.Count)
    #         except Exception:
    #             count = len(items)
    #         if 0 <= index < count:
    #             return str(items[index].EnumName)
    #     except Exception:
    #         pass
    #     try:
    #         return field.GetStringData()
    #     except Exception:
    #         return default

    # def _field_float(self, container, *paths, default=None):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return default
    #     for attr in ("Data", "Value"):
    #         try:
    #             return float(getattr(field, attr))
    #         except Exception:
    #             pass
    #     try:
    #         return float(field.GetStringData())
    #     except Exception:
    #         return default

    # def _field_data_bytes(self, container, *paths):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return None
    #     try:
    #         return bytes(field.GetData())
    #     except Exception:
    #         return None

    # def _field_vector(self, container, *paths, default=None):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return default.copy() if hasattr(default, "copy") else default
    #     for attr in ("Data", "Value"):
    #         try:
    #             values = tuple(float(component) for component in getattr(field, attr))
    #             if len(values) == 3:
    #                 return Vector(values)
    #         except Exception:
    #             pass
    #     try:
    #         values = tuple(float(component.strip()) for component in field.GetStringData().split(","))
    #         if len(values) == 3:
    #             return Vector(values)
    #     except Exception:
    #         pass
    #     return default.copy() if hasattr(default, "copy") else default

    # def _field_quaternion(self, container, *paths, default=None):
    #     field = self._select_field_candidates(container, *paths)
    #     if field is None:
    #         return default.copy() if hasattr(default, "copy") else default
    #     for attr in ("Data", "Value"):
    #         try:
    #             values = tuple(float(component) for component in getattr(field, attr))
    #             if len(values) == 4:
    #                 return Quaternion((values[3], values[0], values[1], values[2]))
    #         except Exception:
    #             pass
    #     try:
    #         values = tuple(float(component.strip()) for component in field.GetStringData().split(","))
    #         if len(values) == 4:
    #             return Quaternion((values[3], values[0], values[1], values[2]))
    #     except Exception:
    #         pass
    #     return default.copy() if hasattr(default, "copy") else default

    # def _normalized_field_name(self, value):
    #     if not value:
    #         return ""
    #     text = str(value).strip()
    #     if not text:
    #         return ""
    #     text = text.rsplit("/", 1)[-1]
    #     text = text.rsplit(":", 1)[-1]
    #     return text.replace(" ", "_").lower()

    # def _iter_sequence(self, value):
    #     if value is None:
    #         return
    #     try:
    #         count = value.Count
    #     except Exception:
    #         count = None
    #     if count is not None:
    #         for index in range(count):
    #             try:
    #                 yield value[index]
    #             except Exception:
    #                 continue
    #         return
    #     try:
    #         for item in value:
    #             yield item
    #     except Exception:
    #         return

    # def _iter_resource_structs(self, container):
    #     pending = [container]
    #     seen = set()
    #     while pending:
    #         current = pending.pop(0)
    #         if current is None:
    #             continue
    #         current_id = id(current)
    #         if current_id in seen:
    #             continue
    #         seen.add(current_id)

    #         has_fields = False
    #         try:
    #             if current.Fields is not None:
    #                 has_fields = True
    #         except Exception:
    #             has_fields = False
    #         if has_fields:
    #             yield current

    #         for attr in ("Element", "Value", "Data", "Reference"):
    #             try:
    #                 child = getattr(current, attr)
    #             except Exception:
    #                 child = None
    #             if child is not None:
    #                 pending.append(child)

    #         try:
    #             structs = current.Structs
    #         except Exception:
    #             structs = None
    #         if structs is not None:
    #             for struct in self._iter_sequence(structs):
    #                 pending.append(struct)

    # def _find_direct_child_field(self, container, *names):
    #     field = self._select_field_candidates(container, *names)
    #     if field is not None:
    #         return field

    #     targets = {self._normalized_field_name(name) for name in names if name}
    #     targets.discard("")
    #     if not targets:
    #         return None

    #     for struct in self._iter_resource_structs(container):
    #         try:
    #             fields = struct.Fields
    #         except Exception:
    #             continue
    #         for field in self._iter_sequence(fields):
    #             for attr in ("FieldName", "DisplayName", "FieldPathWithoutindices", "FieldPath"):
    #                 try:
    #                     candidate = getattr(field, attr)
    #                 except Exception:
    #                     candidate = None
    #                 if self._normalized_field_name(candidate) in targets:
    #                     return field
    #     return None

    # def _block_element_count(self, block_field):
    #     if block_field is None:
    #         return 0
    #     try:
    #         elements = block_field.Elements
    #     except Exception:
    #         return 0
    #     try:
    #         return int(elements.Count)
    #     except Exception:
    #         try:
    #             return len(elements)
    #         except Exception:
    #             return 0

    # def _block_element_at(self, block_field, index):
    #     if block_field is None or index < 0:
    #         return None
    #     try:
    #         elements = block_field.Elements
    #     except Exception:
    #         return None
    #     try:
    #         return elements[index]
    #     except Exception:
    #         try:
    #             return list(elements)[index]
    #         except Exception:
    #             return None

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
            world_graph_nodes = []
            world_graph_names = []

            for index, element in enumerate(self.block_additional_node_dat.Elements):
                name = element.Fields[0].GetStringData()
                translation = self._to_vector(element.SelectField("default translation").Data) * 100.0
                rotation = self._to_quaternion(element.SelectField("default rotation").Data)
                scale = element.SelectField("default scale").Data

                node_data = (translation, rotation, scale)

                world_graph_nodes.append(node_data)
                world_graph_names.append(name)

                if index < len(graph_node_names):
                    expected_name = graph_node_names[index]
                    if name and name != expected_name and utils.remove_node_prefix(name) != utils.remove_node_prefix(expected_name):
                        graph_name_mismatches.append((expected_name, name))

            def world_to_local(child, parent):
                c_t, c_r, c_s = child
                p_t, p_r, p_s = parent

                p_r_inv = p_r.inverted()

                local_t = p_r_inv @ ((c_t - p_t) / p_s)
                local_r = p_r_inv @ c_r
                local_s = c_s / p_s

                return local_t, local_r, local_s

            for index, node in enumerate(world_graph_nodes):
                name = world_graph_names[index]

                if self.corinth:
                    parent_index = parent_indices[index] if index < len(parent_indices) else -1

                    if parent_index == -1 or parent_index >= len(world_graph_nodes):
                        local_node = node
                    else:
                        parent_node = world_graph_nodes[parent_index]
                        local_node = world_to_local(node, parent_node)

                else:
                    local_node = node

                indexed_graph_nodes.append(local_node)

                if name:
                    graph_nodes[name] = local_node
                    stripped_graph_nodes.setdefault(utils.remove_node_prefix(name), local_node)
                    
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

        # if model is not None and graph_fallback_nodes:
        #     utils.print_warning(f"Animation import could not match {len(graph_fallback_nodes)} graph nodes to render model defaults. Falling back to additional node data for those nodes.")
        if graph_name_mismatches:
            utils.print_warning(f"Animation import found {len(graph_name_mismatches)} additional node data entries whose names do not match the skeleton node at the same index. Using index order for graph defaults.")
        if missing_nodes:
            source = "render model or additional node data" if model is not None else "additional node data"
            utils.print_warning(f"Animation import could not match {len(missing_nodes)} graph nodes to {source} defaults. Missing nodes will use identity transforms.")

        return defaults, nodes, overlay_defaults

    def _read_shared_static_codec(self):
        rotations_block = self.tag.SelectField("Struct:codec data[0]/Struct:shared_static_codec[0]/Block:rotations")
        if rotations_block is None:
            return None
        
        translations_block = self.tag.SelectField("Struct:codec data[0]/Struct:shared_static_codec[0]/Block:translations")
        scales_block = self.tag.SelectField("Struct:codec data[0]/Struct:shared_static_codec[0]/Block:scale")

        rotations = []
        for element in rotations_block.Elements:
            rotations.append(
                (
                    element.Fields[0].Data,
                    element.Fields[1].Data,
                    element.Fields[2].Data,
                    element.Fields[3].Data,
                )
            )

        translations = []
        if translations_block is not None:
            for element in translations_block.Elements:
                translations.append(
                    Vector(
                        (
                            element.Fields[0].Data,
                            element.Fields[1].Data,
                            element.Fields[2].Data,
                        )
                    )
                )

        scales = []
        if scales_block is not None:
            for element in scales_block.Elements:
                scales.append(element.Fields[0].Data)

        return SharedStaticCodecData(rotations, translations, scales)

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

        cache = read_model_animation_graph_resources(self._serialized_tag_bytes())
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

    def _read_animation_resource_data(self, tag_animation: Animation, shared_static_codec):
        if tag_animation.resource_group < 0 or tag_animation.resource_group_member < 0:
            raise ValueError("Animation resource group indices are missing")

        def build_resource_data(
            current_frame_count,
            current_node_count,
            current_checksum,
            current_movement_type,
            current_static_flags_size,
            current_animated_flags_size,
            current_static_data_size,
            current_movement_data_size,
            current_shared_static_size,
            current_static_codec_size,
            current_animated_codec_size,
            current_revised_curve_rotation_layout,
        ):
            resource_data = AnimationResourceData(
                current_frame_count,
                current_node_count,
                current_checksum,
                current_movement_type,
                current_static_flags_size,
                current_animated_flags_size,
                current_static_data_size,
                movement_data_size=current_movement_data_size,
                shared_static_data_size=current_shared_static_size,
                static_codec_size=current_static_codec_size,
                animated_codec_size=current_animated_codec_size,
                revised_curve_rotation_layout=current_revised_curve_rotation_layout,
                debug_name=tag_animation.name.tag_name,
            )
            resource_data.read(BinaryReader(animation_data))
            if current_shared_static_size:
                if shared_static_codec is None:
                    raise ValueError("Animation uses shared static data but the graph codec data could not be read")
                apply_shared_static_codec(resource_data, animation_data, shared_static_codec)
            return resource_data

        def track_count(codec, attr_name):
            if codec is None:
                return 0
            try:
                values = getattr(codec, attr_name)
            except Exception:
                return 0
            return len(values or ())

        def flag_count(flags):
            return sum(1 for flag in (flags or ()) if flag)

        def resource_tracks_match_flags(resource_data):
            static_codec = resource_data.static_data
            animated_codec = resource_data.animation_data
            checks = (
                (flag_count(resource_data.static_rotated_node_flags), track_count(static_codec, "rotations")),
                (flag_count(resource_data.static_translated_node_flags), track_count(static_codec, "translations")),
                (flag_count(resource_data.static_scaled_node_flags), track_count(static_codec, "scales")),
                (flag_count(resource_data.animated_rotated_node_flags), track_count(animated_codec, "rotations")),
                (flag_count(resource_data.animated_translated_node_flags), track_count(animated_codec, "translations")),
                (flag_count(resource_data.animated_scaled_node_flags), track_count(animated_codec, "scales")),
            )
            return all(flag_total <= track_total for flag_total, track_total in checks)

        animation_data = None
        frame_count = tag_animation.frame_count
        node_count = self.nodes_count
        checksum = 0
        movement_type = tag_animation.frame_info_type
        static_flags_size = 0
        animated_flags_size = 0
        movement_data_size = 0
        static_data_size = 0
        shared_static_size = 0
        revised_curve_rotation_layout = "cache"

        source_member = self._get_source_animation_resource_member(tag_animation.resource_group, tag_animation.resource_group_member)
        source_layout_version = 3
        source_section_boundaries = {}

        if source_member is not None:
            animation_data = source_member.animation_data
            frame_count = source_member.frame_count or frame_count
            node_count = source_member.node_count or node_count
            checksum = source_member.animation_checksum
            movement_type = source_member.movement_data_type
            source_layout_version = getattr(source_member, "layout_version", 3)
            source_section_boundaries = getattr(source_member, "section_boundaries", {}) or {}
            if source_layout_version >= 4:
                revised_curve_rotation_layout = "h4_source"
                # H4 source tags serialize the cache-side PackedDataSizesStructActual,
                # but the exposed source field names are shifted from their real meaning.
                static_data_size = int(source_section_boundaries.get("static_node_flags", 0) or 0)
                static_codec_size = static_data_size
                animated_codec_size = int(source_section_boundaries.get("animated_node_flags", 0) or 0)
                static_flags_size = int(source_section_boundaries.get("movement_data", 0) or 0)
                animated_flags_size = int(source_section_boundaries.get("pill_offset_data", 0) or 0)
                movement_data_size = int(source_section_boundaries.get("default_data", 0) or 0)
            else:
                # Reach source tags expose boundary-style values here instead.
                flag_word_size = ((node_count + 31) // 32) * 4
                static_codec_size = source_member.static_flags_size
                animated_codec_size = source_member.animated_flags_size
                static_flags_size = flag_word_size * 3 if source_member.static_flags_size else 0
                animated_flags_size = flag_word_size * 3 if source_member.animated_flags_size else 0
                movement_data_size = source_member.movement_data_size
                static_data_size = source_member.static_data_size
            shared_static_size = source_member.shared_static_data_size

        if not animation_data:
            raise ValueError("Animation resource data is missing")

        if source_member is not None and source_layout_version >= 4:
            try:
                resource_data = build_resource_data(
                    frame_count,
                    node_count,
                    checksum,
                    movement_type,
                    static_flags_size,
                    animated_flags_size,
                    static_data_size,
                    movement_data_size,
                    shared_static_size,
                    static_codec_size,
                    animated_codec_size,
                    revised_curve_rotation_layout,
                )
                if resource_tracks_match_flags(resource_data):
                    return resource_data
            except Exception as exc:
                last_error = exc

            flag_candidates = []
            for candidate in (
                source_section_boundaries.get("uncompressed_data", 0),
                source_section_boundaries.get("compressed_data", 0),
                source_section_boundaries.get("blend_screen_data", 0),
                source_section_boundaries.get("pill_offset_data", 0),
                source_section_boundaries.get("movement_data", 0),
            ):
                candidate = int(candidate or 0)
                if candidate > 0 and candidate not in flag_candidates:
                    flag_candidates.append(candidate)

            attempts = []
            for candidate in flag_candidates:
                attempts.append(
                    (
                        int(source_section_boundaries.get("movement_data", 0) or 0),
                        candidate,
                        int(source_section_boundaries.get("default_data", 0) or 0),
                    )
                )
                attempts.append((candidate, 0, int(source_section_boundaries.get("default_data", 0) or 0)))

            if not attempts:
                attempts.append((static_flags_size, animated_flags_size, movement_data_size))

            last_error = None
            for candidate_static_flags, candidate_animated_flags, candidate_movement_size in attempts:
                try:
                    resource_data = build_resource_data(
                        frame_count,
                        node_count,
                        checksum,
                        movement_type,
                        candidate_static_flags,
                        candidate_animated_flags,
                        static_data_size,
                        candidate_movement_size,
                        shared_static_size,
                        static_codec_size,
                        animated_codec_size,
                        revised_curve_rotation_layout,
                    )
                except Exception as exc:
                    last_error = exc
                    continue

                if resource_tracks_match_flags(resource_data):
                    return resource_data

                last_error = ValueError(
                    f"Halo 4 flag mapping did not match decoded track counts for {tag_animation.name.tag_name} "
                    f"(static={candidate_static_flags}, animated={candidate_animated_flags})"
                )

            if last_error is not None:
                raise last_error

        return build_resource_data(
            frame_count,
            node_count,
            checksum,
            movement_type,
            static_flags_size,
            animated_flags_size,
            static_data_size,
            movement_data_size,
            shared_static_size,
            static_codec_size,
            animated_codec_size,
            revised_curve_rotation_layout,
        )

    def _scene_event_action(self):
        scene = getattr(self.scene_nwo, "id_data", None)
        if scene is None:
            return None
        animation_data = getattr(scene, "animation_data", None)
        if animation_data is None:
            return None
        return animation_data.action

    def _animation_event_action(self, blender_animation):
        for track in blender_animation.action_tracks:
            action = track.action
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

    # def _clear_event_value_fcurves(self, blender_animation):
    #     action = self._animation_event_action(blender_animation)
    #     if action is None:
    #         return

    #     _, _, slot = self._ensure_scene_event_slot(action, create=False)
    #     if slot is None:
    #         return

    #     prefix = f"{blender_animation.path_from_id()}.animation_events["
    #     fcurves = utils.get_fcurves(action, slot)
    #     if not fcurves:
    #         return
    #     stale_curves = [
    #         fcurve
    #         for fcurve in fcurves
    #         if fcurve.data_path.startswith(prefix) and fcurve.data_path.endswith(".event_value")
    #     ]
    #     for fcurve in stale_curves:
    #         fcurves.remove(fcurve)

    # def _iter_block_elements(self, container, *paths):
    #     block = self._select_field_candidates(container, *paths)
    #     if block is None:
    #         return []
    #     try:
    #         return list(self._iter_sequence(block.Elements))
    #     except Exception:
    #         return []

    def _remove_animation_events(self, blender_animation, predicate):
        for index in range(len(blender_animation.animation_events) - 1, -1, -1):
            event = blender_animation.animation_events[index]
            if predicate(event):
                blender_animation.animation_events.remove(index)

    def _new_tag_event(self, blender_animation, event_type, name, start_frame, frame_count):
        blender_event = blender_animation.animation_events.add()
        blender_event.event_type = event_type
        blender_event.event_id = AnimationEvent().unique_id
        blender_event.frame_frame = blender_animation.frame_start + start_frame
        if frame_count > 1:
            blender_event.multi_frame = 'range'
            blender_event.frame_range = blender_animation.frame_start + start_frame + frame_count - 1
        return blender_event

    def _blend_screen_for_animation(self, tag_animation: Animation):
        cache = getattr(self, "_blend_screen_animation_map", None)
        if cache is None:
            cache = {}
            for element in self.block_blend_screens.Elements:
                animation_field = element.SelectField("Struct:animation[0]/ShortBlockIndex:animation")
                if animation_field is None:
                    continue
                animation_index = animation_field.Value
                if animation_index > -1:
                    cache[animation_index] = element
            self._blend_screen_animation_map = cache

        return cache.get(tag_animation.index)

    def _field_enum_display_name(self, element: TagFieldBlockElement, field_name: str) -> str:
        field = element.SelectField(field_name)
        if field is None:
            return ""
        try:
            index = field.Value
            items = field.Items
            if 0 <= index < len(items):
                return items[index].DisplayName
        except Exception:
            return ""
        return ""

    def _blend_screen_connection_type(self, tag_animation: Animation):
        blend_screen_data, _ = self._read_animation_resource_section_data(tag_animation, "blend_screen_data")

        if not blend_screen_data:
            return None

        try:
            return blend_screen_data[0]
        except Exception:
            return None

    def _find_animation_node_by_usage(self, nodes: list[Node], usage_name: str):
        if not usage_name:
            return None

        stripped_name = utils.remove_node_prefix(usage_name)
        for node in nodes:
            if node.name == usage_name or utils.remove_node_prefix(node.name) == stripped_name:
                return node

        return None

    def _node_world_matrix(self, node: Node, frame_transforms: dict, world_cache: dict):
        cached = world_cache.get(node)
        if cached is not None:
            return cached

        matrix = frame_transforms.get(node)
        if matrix is None:
            matrix = Matrix.Identity(4)

        if node.parent is not None:
            world_matrix = self._node_world_matrix(node.parent, frame_transforms, world_cache) @ matrix
        else:
            world_matrix = matrix.copy()

        world_cache[node] = world_matrix
        return world_matrix

    def _infer_wrap_events(self, tag_animation: Animation, blender_animation, armature: bpy.types.Object, nodes: list[Node], transforms: dict, node_usages: dict):
        if not tag_animation.is_pose_overlay:
            return 0

        # 3D overlays do not require wrapped import events to represent backwards facing aim directions.
        if self._blend_screen_connection_type(tag_animation) == BLEND_SCREEN_CONNECTION_SAMPLE_SPHERE_TRIANGLE:
            return 0

        pedestal_node_index = node_usages.get("pedestal")
        yaw_node_index = node_usages.get("pose blend yaw")

        if pedestal_node_index is None or yaw_node_index is None:
            return 0
        
        pedestal_node = nodes[pedestal_node_index]
        yaw_node = nodes[yaw_node_index]

        added = 0
        first_frame = blender_animation.frame_start
        reset = True

        for frame_index in sorted(transforms):
            if frame_index == first_frame:
                continue

            frame_transforms = transforms[frame_index]
            world_cache = {}
            pedestal_world = self._node_world_matrix(pedestal_node, frame_transforms, world_cache)
            target_world = self._node_world_matrix(yaw_node, frame_transforms, world_cache)
            relative = pedestal_world.inverted_safe() @ target_world

            euler = relative.to_euler('XYZ')
            raw_yaw = degrees(euler.z)

            if abs(raw_yaw) > 90 + 1e-3:
                if reset:
                    current_name = "Wrapped Left" if raw_yaw > 0.0 else "Wrapped Right"
                    reset = False
                    
                blender_event = self._new_tag_event(
                    blender_animation,
                    EVENT_TYPE_IMPORT,
                    "wrap",
                    frame_index - blender_animation.frame_start,
                    1,
                )
                blender_event.import_name = current_name
                added += 1
            else:
                reset = True

        return added

    def _imported_animation_frame_offset(self, tag_animation: Animation):
        return 1 if tag_animation.animation_type in {AnimationType.OVERLAY, AnimationType.REPLACEMENT} else 0

    def _imported_animation_frame_count(self, tag_animation: Animation):
        return tag_animation.frame_count + self._imported_animation_frame_offset(tag_animation)

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
                frame = blender_animation.frame_start + start_frame + frame_offset
                keyframe = fcurve.keyframe_points.insert(frame, value)
                keyframe.interpolation = "LINEAR"
            fcurve.update()
        else:
            for frame_offset, value in enumerate(event_values):
                blender_event.event_value = value
                blender_event.keyframe_insert(
                    data_path="event_value",
                    frame=blender_animation.frame_start + start_frame + frame_offset
                )
        blender_event.event_value = first_value

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

        metadata_entry_offset = metadata_offset + (data_index * 4)
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

        if expected_frame_count:
            frame_count = expected_frame_count
        elif metadata_frame_count > 0:
            frame_count = metadata_frame_count
        elif metadata_frame_count >= 0:
            frame_count = metadata_frame_count + 1
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

    def _decode_scalar_event_curve(self, tag_animation: Animation, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        if tag_animation.resource_group < 0 or tag_animation.resource_group_member < 0:
            return None

        animation_data = None
        boundaries = {}

        try:
            source_member = self._get_source_animation_resource_member(tag_animation.resource_group, tag_animation.resource_group_member)
        except Exception:
            source_member = None

        if source_member is not None:
            animation_data = source_member.animation_data
            frame_count = source_member.frame_count or frame_count
            boundaries = getattr(source_member, "section_boundaries", {}) or {}

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

    def _read_animation_resource_section_data(self, tag_animation: Animation, section_name):
        if section_name not in RESOURCE_SECTION_ORDER:
            return b"", 0

        if tag_animation.resource_group < 0 or tag_animation.resource_group_member < 0:
            return b"", 0

        frame_count = 0
        animation_data = None
        boundaries = {}

        try:
            source_member = self._get_source_animation_resource_member(tag_animation.resource_group, tag_animation.resource_group_member)
        except Exception:
            source_member = None

        if source_member is not None:
            animation_data = source_member.animation_data
            frame_count = source_member.frame_count or frame_count
            boundaries = getattr(source_member, "section_boundaries", {}) or {}

        return self._resource_section_slice(animation_data, boundaries, section_name), frame_count

    def _decode_embedded_curve_section_info(self, curve_data):
        if not curve_data or len(curve_data) < 20:
            return None

        reader = BinaryReader(curve_data)
        try:
            version = reader.read_u8()
            track_count = reader.read_u8()
            reader.read_u16()
            metadata_offset = reader.read_u32()
            record_offsets_offset = reader.read_u32()
        except Exception:
            return None

        if track_count <= 0:
            track_count = version

        if track_count <= 0:
            return None

        metadata_size = max(record_offsets_offset - metadata_offset, 0)
        available_metadata_entries = metadata_size // 2
        if available_metadata_entries <= 0:
            return None

        track_count = min(track_count, available_metadata_entries)
        if record_offsets_offset + (track_count * 4) > len(curve_data):
            return None

        frame_counts = []
        record_offsets = []
        try:
            for track_index in range(track_count):
                reader.seek(metadata_offset + (track_index * 2))
                frame_counts.append(reader.read_u16())
                reader.seek(record_offsets_offset + (track_index * 4))
                record_offsets.append(reader.read_u32())
        except Exception:
            return None

        return {
            "frame_counts": frame_counts,
            "record_offsets": record_offsets,
            "track_count": track_count,
        }

    def _decode_embedded_rotation_curve_track(self, curve_data, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        info = self._decode_embedded_curve_section_info(curve_data)
        if info is None or data_index >= info["track_count"]:
            return None

        metadata_frame_count = info["frame_counts"][data_index]
        record_offset = info["record_offsets"][data_index]
        frame_count = expected_frame_count or metadata_frame_count or 0
        if frame_count <= 0 or record_offset < 0 or record_offset + 8 > len(curve_data):
            return None

        reader = BinaryReader(curve_data)
        codec = CurveCodec(frame_count)
        try:
            reader.seek(record_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_s16()
            keyframes = codec._read_curve_keyframe_data(key_count, reader) if (flags & 1) == 0 else []
            return [value.copy() for value in codec._read_curve_rotations(reader, keyframes, flags)]
        except Exception:
            return None

    def _decode_embedded_translation_curve_track(self, curve_data, data_index, expected_frame_count=0, apply_scale_100=True):
        if data_index is None or data_index < 0:
            return None

        info = self._decode_embedded_curve_section_info(curve_data)
        if info is None or data_index >= info["track_count"]:
            return None

        metadata_frame_count = info["frame_counts"][data_index]
        record_offset = info["record_offsets"][data_index]
        frame_count = expected_frame_count or metadata_frame_count or 0
        if frame_count <= 0 or record_offset < 0 or record_offset + 24 > len(curve_data):
            return None

        reader = BinaryReader(curve_data)
        codec = CurveCodec(frame_count)
        try:
            reader.seek(record_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_u16()
            offset_x = reader.read_f32()
            offset_y = reader.read_f32()
            offset_z = reader.read_f32()
            scale = reader.read_f32()
            keyframes = codec._read_curve_keyframe_data(key_count, reader) if (flags & 1) == 0 else []
            return [
                value.copy()
                for value in codec._read_curve_translations(
                    reader,
                    keyframes,
                    flags,
                    offset_x,
                    offset_y,
                    offset_z,
                    scale,
                    apply_scale_100,
                )
            ]
        except Exception:
            return None

    def _decode_embedded_scale_curve_track(self, curve_data, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        info = self._decode_embedded_curve_section_info(curve_data)
        if info is None or data_index >= info["track_count"]:
            return None

        metadata_frame_count = info["frame_counts"][data_index]
        record_offset = info["record_offsets"][data_index]
        frame_count = expected_frame_count or metadata_frame_count or 0
        if frame_count <= 0 or record_offset < 0 or record_offset + 16 > len(curve_data):
            return None

        reader = BinaryReader(curve_data)
        codec = CurveCodec(frame_count)
        try:
            reader.seek(record_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_u16()
            offset = reader.read_f32()
            scale = reader.read_f32()
            keyframes = codec._read_curve_keyframe_data(key_count, reader) if (flags & 1) == 0 else []
            return [float(value) for value in codec._read_curve_scales(reader, keyframes, flags, offset, scale)]
        except Exception:
            return None

    def _decode_ik_weight_curve(self, tag_animation, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        curve_data, _ = self._read_animation_resource_section_data(tag_animation, "ik_chain_control_data")
        if not curve_data:
            return None

        return self._decode_embedded_scale_curve_track(curve_data, data_index, expected_frame_count)

    def _decode_ik_effector_transform(self, tag_animation, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        curve_data, _ = self._read_animation_resource_section_data(tag_animation, "ik_chain_event_data")
        if not curve_data:
            return None

        rotations = self._decode_embedded_rotation_curve_track(curve_data, data_index, expected_frame_count)
        translations = self._decode_embedded_translation_curve_track(curve_data, data_index + 1, expected_frame_count)
        scales = self._decode_embedded_scale_curve_track(curve_data, data_index + 2, expected_frame_count)
        if rotations is None and translations is None and scales is None:
            return None

        sample_count = max(
            len(rotations or ()),
            len(translations or ()),
            len(scales or ()),
            max(int(expected_frame_count), 0),
        )
        if sample_count <= 0:
            return None

        if rotations is None:
            rotations = [Quaternion((1.0, 0.0, 0.0, 0.0)) for _ in range(sample_count)]
        if translations is None:
            translations = [Vector((0.0, 0.0, 0.0)) for _ in range(sample_count)]
        if scales is None:
            scales = [1.0 for _ in range(sample_count)]

        transforms = []
        for sample_index in range(sample_count):
            rotation = rotations[min(sample_index, len(rotations) - 1)].copy()
            translation = translations[min(sample_index, len(translations) - 1)].copy()
            scale = float(scales[min(sample_index, len(scales) - 1)])
            transforms.append((translation, rotation, scale))
        return transforms

    def _decode_ik_pole_point(self, tag_animation, data_index, expected_frame_count=0):
        if data_index is None or data_index < 0:
            return None

        curve_data, _ = self._read_animation_resource_section_data(tag_animation, "ik_chain_pole_vector_data")
        if not curve_data:
            return None

        translations = self._decode_embedded_translation_curve_track(curve_data, data_index, expected_frame_count)
        if translations is None:
            return None

        identity = Quaternion((1.0, 0.0, 0.0, 0.0))
        return [(translation.copy(), identity.copy(), 1.0) for translation in translations]

    def _find_ik_chain_object(self, armature: bpy.types.Object, ik_chain_name: str, target_kind: str):
        armature_children = {o.name: o for o in armature.children}
        ob = armature_children.get(f"{armature.name}_{ik_chain_name}_{target_kind}_target")
        if ob is None:
            ob = self._make_ik_chain_object(
                armature,
                armature.users_collection[0] if armature.users_collection else self.context.scene.collection,
                ik_chain_name,
                target_kind=target_kind,
            )
            
        return ob

    def _find_ik_proxy_marker_object(self, armature: bpy.types.Object, ik_chain_name: str, pole=False):
        return self._find_ik_chain_object(armature, ik_chain_name, "pole" if pole else "proxy")

    def _find_ik_chain_definition(self, ik_chain_name: str):
        for chain in self.scene_nwo.ik_chains:
            if chain.name == ik_chain_name:
                return chain
        return None

    def _find_pose_bone_by_name(self, armature: bpy.types.Object, bone_name: str):
        if not bone_name:
            return None

        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone is not None:
            return pose_bone

        stripped_name = utils.remove_node_prefix(bone_name)
        for candidate in armature.pose.bones:
            if utils.remove_node_prefix(candidate.name) == stripped_name:
                return candidate

        return None

    def _matrix_from_transform_sample(self, location: Vector, rotation: Quaternion, scale: float):
        return Matrix.LocRotScale(location, rotation, Vector.Fill(3, float(scale)))

    def _matrix_to_transform_sample(self, matrix: Matrix):
        location, rotation, scale = matrix.decompose()
        scale_value = (scale.x + scale.y + scale.z) / 3.0
        return location.copy(), rotation.copy(), float(scale_value)

    def _object_space_samples_to_local_samples(self, armature: bpy.types.Object, samples):
        parent_inverse = armature.matrix_world.inverted_safe()
        local_samples = []
        for location, rotation, scale in samples:
            world_matrix = self._matrix_from_transform_sample(location, rotation, scale)
            local_matrix = parent_inverse @ world_matrix
            local_samples.append(self._matrix_to_transform_sample(local_matrix))

        return local_samples
    
    def _evaluate_fcurve(self, fcurve, frame: float, default):
        if fcurve is None:
            return default
        try:
            return fcurve.evaluate(frame)
        except Exception:
            return default

    def _action_pose_fcurve_map(self, action: bpy.types.Action, slot_identifier: str | None):
        fcurve_map = {}
        if action is None:
            return fcurve_map

        fcurves = utils.get_fcurves(action, slot_identifier)
        if not fcurves:
            return fcurve_map

        for fcurve in fcurves:
            fcurve_map[(fcurve.data_path, fcurve.array_index)] = fcurve

        return fcurve_map

    def _sample_pose_bone_basis_from_action(
        self,
        pose_bone: bpy.types.PoseBone,
        frame: float,
        fcurve_map,
    ):
        bone_name = pose_bone.name

        loc_defaults = pose_bone.location
        rot_defaults = pose_bone.rotation_quaternion
        scale_defaults = pose_bone.scale

        loc_path = f'pose.bones["{bone_name}"].location'
        rot_path = f'pose.bones["{bone_name}"].rotation_quaternion'
        scale_path = f'pose.bones["{bone_name}"].scale'

        location = Vector((
            self._evaluate_fcurve(fcurve_map.get((loc_path, 0)), frame, loc_defaults.x),
            self._evaluate_fcurve(fcurve_map.get((loc_path, 1)), frame, loc_defaults.y),
            self._evaluate_fcurve(fcurve_map.get((loc_path, 2)), frame, loc_defaults.z),
        ))

        rotation = Quaternion((
            self._evaluate_fcurve(fcurve_map.get((rot_path, 0)), frame, rot_defaults.w),
            self._evaluate_fcurve(fcurve_map.get((rot_path, 1)), frame, rot_defaults.x),
            self._evaluate_fcurve(fcurve_map.get((rot_path, 2)), frame, rot_defaults.y),
            self._evaluate_fcurve(fcurve_map.get((rot_path, 3)), frame, rot_defaults.z),
        ))
        if rotation.magnitude <= tolerance:
            rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
        else:
            rotation.normalize()

        scale = Vector((
            self._evaluate_fcurve(fcurve_map.get((scale_path, 0)), frame, scale_defaults.x),
            self._evaluate_fcurve(fcurve_map.get((scale_path, 1)), frame, scale_defaults.y),
            self._evaluate_fcurve(fcurve_map.get((scale_path, 2)), frame, scale_defaults.z),
        ))

        return Matrix.LocRotScale(location, rotation, scale)

    def _sample_pose_bone_matrix_from_action(
        self,
        pose_bone: bpy.types.PoseBone,
        frame: float,
        fcurve_map,
        matrix_cache,
    ):
        cached = matrix_cache.get(pose_bone.name)
        if cached is not None:
            return cached

        basis_matrix = self._sample_pose_bone_basis_from_action(pose_bone, frame, fcurve_map)
        bone_rest_matrix = pose_bone.bone.matrix_local

        if pose_bone.parent is None:
            pose_matrix = bone_rest_matrix @ basis_matrix
        else:
            parent_pose_matrix = self._sample_pose_bone_matrix_from_action(
                pose_bone.parent,
                frame,
                fcurve_map,
                matrix_cache,
            )
            local_rest_matrix = pose_bone.parent.bone.matrix_local.inverted_safe() @ bone_rest_matrix
            pose_matrix = parent_pose_matrix @ local_rest_matrix @ basis_matrix

        matrix_cache[pose_bone.name] = pose_matrix
        return pose_matrix

    def _reconstruct_ik_proxy_target_samples(self, blender_animation, armature: bpy.types.Object, event, proxy_space_samples, start_frame: int):
        chain = self._find_ik_chain_definition(event.get("ik_chain", ""))
        if chain is None:
            utils.print_warning(f"Could not reconstruct IK proxy target for [{event.get('name', 'unknown')}]: chain [{event.get('ik_chain', '')}] is missing")
            return None

        effector_bone = self._find_pose_bone_by_name(armature, getattr(chain, "effector_node", ""))
        if effector_bone is None:
            utils.print_warning(f"Could not reconstruct IK proxy target for [{event.get('name', 'unknown')}]: effector bone [{getattr(chain, 'effector_node', '')}] is missing")
            return None

        animation_data = armature.animation_data
        action = animation_data.action if animation_data is not None else None
        slot_identifier = animation_data.last_slot_identifier if animation_data is not None else None

        if action is None:
            utils.print_warning(f"Could not reconstruct IK proxy target for [{event.get('name', 'unknown')}]: armature has no active action")
            return None

        fcurve_map = self._action_pose_fcurve_map(action, slot_identifier)
        armature_world_inverse = armature.matrix_world.inverted_safe()
        reconstructed_samples = []

        for sample_index, sample in enumerate(proxy_space_samples):
            frame = blender_animation.frame_start + start_frame + sample_index
            matrix_cache = {}

            effector_pose_matrix = self._sample_pose_bone_matrix_from_action(
                effector_bone,
                frame,
                fcurve_map,
                matrix_cache,
            )
            effector_world = armature.matrix_world @ effector_pose_matrix

            proxy_space_matrix = self._matrix_from_transform_sample(*sample)
            proxy_world = effector_world @ proxy_space_matrix.inverted_safe()
            proxy_local = armature_world_inverse @ proxy_world
            reconstructed_samples.append(self._matrix_to_transform_sample(proxy_local))

        return reconstructed_samples

    def _create_object_action_track(self, blender_animation, obj: bpy.types.Object, action_name: str):
        action = bpy.data.actions.new(action_name)
        slot = action.slots.new("OBJECT", obj.name)
        action.use_frame_range = True
        action.frame_start = blender_animation.frame_start
        action.frame_end = blender_animation.frame_end

        obj.animation_data_create()
        obj.animation_data.last_slot_identifier = slot.identifier
        obj.animation_data.action = action

        track = blender_animation.action_tracks.add()
        track.object = obj
        track.action = action

        return action, slot

    def _apply_object_transform_samples(self, blender_animation, obj: bpy.types.Object, action_name: str, start_frame: int, samples):
        if not samples:
            return None

        action, slot = self._create_object_action_track(blender_animation, obj, action_name)
        fcurves = utils.get_fcurves(action, slot)
        if fcurves:
            fcurves.clear()

        loc_x = fcurves.new(data_path='location', index=0)
        loc_y = fcurves.new(data_path='location', index=1)
        loc_z = fcurves.new(data_path='location', index=2)
        rot_w = fcurves.new(data_path='rotation_quaternion', index=0)
        rot_x = fcurves.new(data_path='rotation_quaternion', index=1)
        rot_y = fcurves.new(data_path='rotation_quaternion', index=2)
        rot_z = fcurves.new(data_path='rotation_quaternion', index=3)
        sca_x = fcurves.new(data_path='scale', index=0)
        sca_y = fcurves.new(data_path='scale', index=1)
        sca_z = fcurves.new(data_path='scale', index=2)

        key_options = {'FAST'}

        for frame_offset, (location, rotation, scale) in enumerate(samples):
            obj.location = location
            obj.rotation_quaternion = rotation
            obj.scale = Vector.Fill(3, scale)
            frame = blender_animation.frame_start + start_frame + frame_offset
            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            obj.keyframe_insert(data_path="scale", frame=frame)

            loc_x.keyframe_points.insert(frame, location.x, options=key_options)
            loc_y.keyframe_points.insert(frame, location.y, options=key_options)
            loc_z.keyframe_points.insert(frame, location.z, options=key_options)
            rot_w.keyframe_points.insert(frame, rotation.w, options=key_options)
            rot_x.keyframe_points.insert(frame, rotation.x, options=key_options)
            rot_y.keyframe_points.insert(frame, rotation.y, options=key_options)
            rot_z.keyframe_points.insert(frame, rotation.z, options=key_options)
            sca_x.keyframe_points.insert(frame, scale, options=key_options)
            sca_y.keyframe_points.insert(frame, scale, options=key_options)
            sca_z.keyframe_points.insert(frame, scale, options=key_options)

        if fcurves:
            for fcurve in fcurves:
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = "LINEAR"

        return action

    def _import_ik_event_controls(self, tag_animation, blender_animation, blender_event, event, armature: bpy.types.Object, imported_actions: list):
        imported_start_frame = event["start_frame"] + self._imported_animation_frame_offset(tag_animation)
        effector_samples = event.get("ik_effector_transforms") or []
        if effector_samples:
            proxy_marker_object = self._find_ik_proxy_marker_object(armature, event["ik_chain"])
            blender_event.ik_target_marker = proxy_marker_object
            reconstructed_proxy_marker_samples = self._reconstruct_ik_proxy_target_samples(
                blender_animation,
                armature,
                event,
                effector_samples,
                imported_start_frame,
            )
            proxy_marker_samples = reconstructed_proxy_marker_samples
            if not proxy_marker_samples:
                utils.print_warning(f"Falling back to raw IK proxy samples for [{event['name']}]; exact roundtrip may not match the source tag")
                proxy_marker_samples = effector_samples
            action = self._apply_object_transform_samples(
                blender_animation,
                proxy_marker_object,
                f"{blender_animation.name}_ik_proxy_{event['name']}",
                imported_start_frame,
                proxy_marker_samples,
            )
            if action is not None:
                imported_actions.append(action)

        pole_samples = event.get("ik_pole_transforms") or []
        if pole_samples:
            pole_target = self._find_ik_proxy_marker_object(armature, event["ik_chain"], pole=True)
            blender_event.ik_pole_vector = pole_target
            pole_target_samples = self._object_space_samples_to_local_samples(armature, pole_samples)
            action = self._apply_object_transform_samples(
                blender_animation,
                pole_target,
                f"{blender_animation.name}_ik_pole_{event['name']}",
                imported_start_frame,
                pole_target_samples,
            )
            if action is not None:
                imported_actions.append(action)

    def _collect_regular_animation_events(self, tag_animation: Animation):
        valid_ik_chain_names = {chain.name for chain in self.scene_nwo.ik_chains if getattr(chain, "start_node", "") and getattr(chain, "effector_node", "")}
        scalar_curve_cache = {}
        ik_weight_curve_cache = {}
        ik_effector_curve_cache = {}
        ik_pole_curve_cache = {}

        def curve_values(data_index, frame_count):
            if data_index < 0:
                return None
            cache_key = data_index
            if cache_key not in scalar_curve_cache:
                scalar_curve_cache[cache_key] = self._decode_scalar_event_curve(tag_animation, data_index, max(int(frame_count), 0))
            return scalar_curve_cache[cache_key]

        def ik_weight_values(data_index, frame_count):
            if data_index < 0:
                return None
            cache_key = (data_index, max(int(frame_count), 0))
            if cache_key not in ik_weight_curve_cache:
                ik_weight_curve_cache[cache_key] = self._decode_ik_weight_curve(tag_animation, data_index, cache_key[1])
                
            # print("IK WEIGHTS", ik_weight_curve_cache[cache_key])
            return ik_weight_curve_cache[cache_key]

        def ik_effector_values(data_index, frame_count):
            if data_index < 0:
                return None
            cache_key = (data_index, max(int(frame_count), 0))
            if cache_key not in ik_effector_curve_cache:
                ik_effector_curve_cache[cache_key] = self._decode_ik_effector_transform(tag_animation, data_index , cache_key[1])
            # print("IK EFFECTOR", ik_weight_curve_cache[cache_key])
            return ik_effector_curve_cache[cache_key]

        def ik_pole_values(data_index, frame_count):
            if data_index < 0:
                return None
            cache_key = (data_index, max(int(frame_count), 0))
            if cache_key not in ik_pole_curve_cache:
                ik_pole_curve_cache[cache_key] = self._decode_ik_pole_point(tag_animation, data_index, cache_key[1])
            # print("IK POLE", ik_weight_curve_cache[cache_key])
            return ik_pole_curve_cache[cache_key]

        tag_events = []
        
        for element in tag_animation.shared_element.SelectField("extended data events").Elements:
            function_name = element.SelectField("name").GetStringData()
            frame_count = element.SelectField("frame count").Data
            data_index = element.SelectField("data index").Data
            tag_events.append(
                {
                    "event_type": EVENT_TYPE_OBJECT_FUNCTION,
                    "name": function_name,
                    "start_frame": element.SelectField("start frame").Data,
                    "frame_count": frame_count,
                    "default_value": element.SelectField("default value").Data,
                    "values": curve_values(data_index, frame_count),
                    "object_function_name": function_name,
                }
            )
            
        for element in tag_animation.shared_element.SelectField("ik chain events").Elements:
            chain_name = element.SelectField("chain name").GetStringData()
            if chain_name not in valid_ik_chain_names:
                continue
            event_type = EVENT_TYPE_IK_PASSIVE if element.SelectField("event type").Value == 1 else EVENT_TYPE_IK_ACTIVE
            usage_name = IK_TARGET_USAGE_MAP[element.SelectField("chain usage").Value]
            data_index = element.SelectField("effector weight data index").Data
            effector_transform_index = element.SelectField("effector transform data index").Data
            pole_point_index = element.SelectField("pole point data index").Data
            frame_count = tag_animation.frame_count
            
            tag_events.append(
                {
                    "event_type": event_type,
                    "name": chain_name,
                    "start_frame": 0,
                    "frame_count": frame_count,
                    "default_value": 1,
                    "values": ik_weight_values(data_index, frame_count),
                    "ik_chain": chain_name,
                    "ik_target_usage": usage_name,
                    "ik_target_marker_name_override": element.SelectField("proxy marker").GetStringData(),
                    "ik_effector_transforms": ik_effector_values(effector_transform_index, frame_count),
                    "ik_pole_transforms": ik_pole_values(pole_point_index, frame_count),
                }
            )
            
            
        for element in tag_animation.shared_element.SelectField("facial wrinkle events").Elements:
            wrinkle_name = element.SelectField("wrinkle name").GetStringData()
            region_name = WRINKLE_FACE_REGION_MAP[element.SelectField("region").Value]
            frame_count = element.SelectField("frame count").Data
            data_index = element.SelectField("wrinkle data index").Data
            tag_events.append(
                {
                    "event_type": EVENT_TYPE_WRINKLE_MAP,
                    "name": wrinkle_name,
                    "start_frame": element.SelectField("start frame").Data,
                    "frame_count": frame_count,
                    "default_value": element.SelectField("default value").Data,
                    "values": curve_values(data_index, frame_count),
                    "wrinkle_map_face_region": utils.formalise_string(region_name),
                }
            )

        tag_events.sort(key=lambda event: (event["start_frame"], event["name"]))
        return tag_events

    def _apply_regular_animation_events(self, tag_animation: Animation, blender_animation, armature: bpy.types.Object, imported_actions: list):
        tag_events = self._collect_regular_animation_events(tag_animation)
        if not tag_events:
            return 0

        # self._clear_event_value_fcurves(blender_animation)
        # self._remove_animation_events(blender_animation, lambda event: getattr(event, "event_type", "") != EVENT_TYPE_FRAME)

        imported_frame_offset = self._imported_animation_frame_offset(tag_animation)
        for event in tag_events:
            imported_start_frame = event["start_frame"] + imported_frame_offset
            blender_event = self._new_tag_event(
                blender_animation,
                event["event_type"],
                event["name"],
                imported_start_frame,
                event["frame_count"],
            )

            if event["event_type"] == EVENT_TYPE_OBJECT_FUNCTION and event["object_function_name"]:
                blender_event.object_function_name = event["object_function_name"]
                self._apply_event_value(
                    blender_animation,
                    blender_event,
                    event["default_value"],
                    event["values"],
                    imported_start_frame,
                    event["frame_count"],
                )
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
                    imported_start_frame,
                    event["frame_count"],
                )
                self._import_ik_event_controls(tag_animation, blender_animation, blender_event, event, armature, imported_actions)
            elif event["event_type"] == EVENT_TYPE_WRINKLE_MAP:
                if event["wrinkle_map_face_region"]:
                    blender_event.wrinkle_map_face_region = event["wrinkle_map_face_region"]
                self._apply_event_value(
                    blender_animation,
                    blender_event,
                    event["default_value"],
                    event["values"],
                    imported_start_frame,
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

    def _seek_best_matching_base_animation(self, animation: Animation, name: utils.AnimationName, all_tag_animations):
        def find_for_mode(mode: str):
            animations = {}
            for next_animation in all_tag_animations:
                if next_animation.index == animation.index:
                    continue
                if next_animation.animation_type not in (AnimationType.NONE, AnimationType.BASE):
                    continue
                next_name = next_animation.name
                if next_name.mode != mode:
                    continue
                if next_name.state != name.state:
                    continue
                if next_name.type != utils.AnimationStateType.ACTION:
                    continue
                matches = 0
                matches += (int(name.weapon_class == next_name.weapon_class) * 100)
                matches += (int(name.weapon_type == next_name.weapon_type) * 10)
                matches += int(name.set == next_name.set)
                animations[next_animation] = matches

            if not animations:
                return None

            priority_animations = sorted(animations, key=animations.get, reverse=True)
            return priority_animations[0]

        return find_for_mode(name.mode) or find_for_mode("any")

    def _soft_transition_final_frame_source(self, animation: Animation, name: utils.AnimationName, all_tag_animations):
        next_animation = None
        ignore_root = False
        ignore_pose = False

        if name.mode == "bunker":
            if name.state == "open":
                idle_name = name.copy()
                idle_name.state = "idle"
                if name.set.endswith("_closed"):
                    idle_name.set = name.set.replace("_closed", "_open")
                    next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            elif name.state == "close":
                idle_name = name.copy()
                idle_name.state = "idle"
                if name.set.endswith("_open"):
                    idle_name.set = name.set.replace("_open", "_closed")
                    next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            elif name.state == "enter":
                idle_name = name.copy()
                idle_name.state = "idle"
                next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            elif name.state == "exit":
                idle_name = name.copy()
                idle_name.state = "idle"
                idle_name.mode = "combat"
                next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)

        elif name.state.startswith("juke_anticipation_"):
            juke_name = name.copy()
            juke_name.state = name.state.replace("_anticipation", "")
            next_animation = self._seek_best_matching_base_animation(animation, juke_name, all_tag_animations)
            ignore_root = True

        elif name.state.startswith("juke_"):
            juke_direction = name.state.replace("juke_", "")
            juke_name = name.copy()
            juke_name.state = f"locomote_run_{juke_direction}"
            next_animation = self._seek_best_matching_base_animation(animation, juke_name, all_tag_animations)
            if next_animation is None:
                juke_name.state = f"move_{juke_direction}"
                next_animation = self._seek_best_matching_base_animation(animation, juke_name, all_tag_animations)
            ignore_root = True

        elif name.state.endswith("_ping"):
            idle_name = name.copy()
            idle_name.state = "idle"
            next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            ignore_root = True

        elif "enter" in name.state:
            idle_name = name.copy()
            idle_name.state = "idle"
            next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            if next_animation is None and "_b_" in idle_name.mode:
                boarding_name = idle_name.copy()
                boarding_name.mode = idle_name.mode.replace("_b_", "_")
                next_animation = self._seek_best_matching_base_animation(animation, boarding_name, all_tag_animations)

        elif "ejection" in name.state:
            next_animation = animation
            ignore_root = True

        elif "exit" in name.state:
            return next_animation, ignore_root
            idle_name = name.copy()
            if name.mode.endswith(("_b", "_d", "_p")) or "_p_" in name.mode:
                return next_animation, ignore_root
            idle_name.state = "idle"
            idle_name.mode = "combat"
            next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            ignore_root = True

        # elif name.state.endswith("exit_patrol"):
        #     idle_name = name.copy()
        #     idle_name.state = "idle"
        #     idle_name.mode = "patrol"
        #     next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)

        elif "put_away" in name.state:
            ready_name = name.copy()
            ready_name.state = "ready"
            next_animation = self._seek_best_matching_base_animation(animation, ready_name, all_tag_animations)
            ignore_root = True

        elif "ready" in name.state:
            put_away_name = name.copy()
            put_away_name.state = "put_away"
            next_animation = self._seek_best_matching_base_animation(animation, put_away_name, all_tag_animations)
            ignore_root = True

        else:
            return next_animation, ignore_root
            # idle_name = name.copy()
            # idle_name.state = "idle"
            # idle_name.mode = "combat"
            # next_animation = self._seek_best_matching_base_animation(animation, idle_name, all_tag_animations)
            # ignore_root = True

        if ignore_pose:
            return None, ignore_root

        return next_animation, ignore_root

    def _base_final_frame_source(self, animation: Animation, all_tag_animations):
        name = animation.name
        if name.type == utils.AnimationStateType.TRANSITION:
            dest_name = name.copy()
            dest_name.mode = name.destination_mode
            dest_name.state = name.destination_state
            return self._seek_best_matching_base_animation(animation, dest_name, all_tag_animations), True

        if any(transition in name.state for transition in FINAL_FRAME_SOFT_TRANSITIONS):
            return self._soft_transition_final_frame_source(animation, name, all_tag_animations)

        looper = name.state.startswith(FINAL_FRAME_LOOPERS)
        movement = name.state.startswith(FINAL_FRAME_MOVEMENT_STATES)
        if looper or movement:
            return animation, True

        return None, False

    def _base_final_frame_pose(
        self,
        tag_animation: Animation,
        animation_data,
        defaults,
        overlay_defaults,
        graph,
        shared_static_codec,
        resource_cache,
        animation_cache,
        all_tag_animations,
        final_frame_stack,
    ):
        source_animation, ignore_root = self._base_final_frame_source(tag_animation, all_tag_animations)
        if source_animation is None:
            return None, False
        if source_animation.index == tag_animation.index:
            return animation_data.first_frame(), ignore_root
        if source_animation.index in final_frame_stack:
            return None, False

        source_data = self._build_animation(
            source_animation,
            defaults,
            overlay_defaults,
            graph,
            shared_static_codec,
            resource_cache,
            animation_cache,
            all_tag_animations,
            final_frame_stack,
        )
        if source_data.frame_count < 1:
            return None, False

        return source_data.first_frame(), ignore_root

    def _build_animation(self, tag_animation: Animation, defaults, overlay_defaults, graph, shared_static_codec, resource_cache, animation_cache, all_tag_animations, final_frame_stack=None):
        index = tag_animation.index
        if index in animation_cache:
            return animation_cache[index]
        if final_frame_stack is None:
            final_frame_stack = set()

        resource_data = resource_cache.get(index)
        if resource_data is None:
            resource_data = self._read_animation_resource_data(tag_animation, shared_static_codec)
            resource_cache[index] = resource_data

        animation_data = build_animation(resource_data, defaults, "default" if tag_animation.animation_type in (0, 1) else "neutral")
        if tag_animation.animation_type in (AnimationType.NONE, AnimationType.BASE):
            final_frame = None
            ignore_root = False
            if index not in final_frame_stack:
                final_frame_stack.add(index)
                try:
                    final_frame, ignore_root = self._base_final_frame_pose(
                        tag_animation,
                        animation_data,
                        defaults,
                        overlay_defaults,
                        graph,
                        shared_static_codec,
                        resource_cache,
                        animation_cache,
                        all_tag_animations,
                        final_frame_stack,
                    )
                finally:
                    final_frame_stack.remove(index)
            append_final_frame(animation_data, final_frame, ignore_root)
            if resource_data.movement_data is not None:
                apply_movement_data(animation_data, resource_data.movement_data)
        if tag_animation.animation_type in (2, 3):
            base_candidates = self._get_base_animation_candidates(graph, tag_animation.name.tag_name)
            if base_candidates:
                base_tag_animation = all_tag_animations[base_candidates[0].index]
                base_animation = self._build_animation(base_tag_animation, defaults, overlay_defaults, graph, shared_static_codec, resource_cache, animation_cache, all_tag_animations, final_frame_stack)
                base_frame = base_animation.first_frame()
            else:
                base_frame = default_frame_channels(defaults)

            if tag_animation.animation_type == 2:
                animation_data = compose_overlay_animation(animation_data, base_frame)
            else:
                animation_data = compose_replacement_animation(animation_data, base_frame)

        animation_cache[index] = animation_data
        return animation_data

    def _animation_transforms(self, tag_animation, defaults, overlay_defaults, nodes, graph, shared_static_codec, resource_cache, animation_cache, all_tag_animations):
        animation_data = self._build_animation(tag_animation, defaults, overlay_defaults, graph, shared_static_codec, resource_cache, animation_cache, all_tag_animations)
        transforms = {}
        for frame_index, frame_matrices in enumerate(animation_data.frame_matrices(), start=1):
            transforms[frame_index] = {node: matrix for node, matrix in zip(nodes, frame_matrices)}
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
    
    def get_blender_tag_animation_dict(self, blender_animations):
        animations = self.get_animations()

        animations_by_name = {anim.name.data_name: anim for anim in animations}

        anim_dict = {}
        for banim in blender_animations:
            key = banim.name.lower().replace(":", " ")
            anim = animations_by_name.get(key)
            if anim is not None:
                anim_dict[banim] = anim
                
        return anim_dict
    
    def set_tag_info(self, blender_animations: set):
        anim_dict = self.get_blender_tag_animation_dict(blender_animations)
        if anim_dict:
            self.tag_has_changes = True
        for blender_animation, tag_animation in anim_dict.items():
            element = tag_animation.element

            element.SelectField("weight").Data = blender_animation.weight
            element.SelectField("loop frame index").Data = blender_animation.loop_frame_index

            flags = element.SelectField("user flags")

            flags.SetBit("disable interpolation in", blender_animation.disable_interpolation_in)
            flags.SetBit("disable interpolation out", blender_animation.disable_interpolation_out)
            flags.SetBit("disable mode ik", blender_animation.disable_mode_ik)
            flags.SetBit("disable weapon ik", blender_animation.disable_weapon_ik)
            flags.SetBit("disable weapon aim\\1st person", blender_animation.disable_weapon_aim)
            flags.SetBit("disable look screen", blender_animation.disable_look_screen)
            flags.SetBit("disable transition adjustment", blender_animation.disable_transition_adjustment)
            flags.SetBit("force weapon ik on", blender_animation.force_weapon_ik_on)
            flags.SetBit("enable animated source interpolation", blender_animation.enable_animated_source_interpolation)
            flags.SetBit("disable ik sets", blender_animation.disable_ik_sets)
            flags.SetBit("disable ik chains", blender_animation.disable_ik_chains)
            flags.SetBit("translate and scale root only", blender_animation.translate_and_scale_root_only)

            flags.SetBit(
                "enable blend-out on replacement anims" if self.corinth else "enable blend out",
                blender_animation.enable_blend_out_on_replacement_anims
            )

            if self.corinth:
                flags.SetBit(
                    "override player input with motion",
                    blender_animation.override_player_input_with_motion
                )
                element.SelectField("pca group name").SetStringData(blender_animation.pca_group_name)
            else:
                flags.SetBit(
                    "disable subframe interp on loop",
                    blender_animation.disable_subframe_interp_on_loop
                )

            use_blend_in_flag = "use custom blend-in time" if self.corinth else "override default blend time"
            use_blend_out_flag = "use custom blend-out time" if self.corinth else "override default blend out time"

            blends_in = blender_animation.override_blend_in_time > 0.0
            flags.SetBit(use_blend_in_flag, blends_in)
            if blends_in:
                element.SelectField("override blend in time").Data = blender_animation.override_blend_in_time
                
            blends_out = blender_animation.override_blend_out_time > 0.0
            flags.SetBit(use_blend_out_flag, blends_out)
            if blends_out:
                element.SelectField("override blend out time").Data = blender_animation.override_blend_out_time
                
            if self.corinth:
                if blender_animation.pca_best_quality:
                    self.quality_pca(tag_animation.name.tag_name, tag_animation.frame_count)
                    element.SelectField("pca group name").SetStringData(tag_animation.name.tag_name)
                else:
                    element.SelectField("pca group name").SetStringData(blender_animation.pca_group_name)
        
    
    def quality_pca(self, name, desired_mesh_count):
        pca_groups = self.tag.SelectField("Struct:definitions[0]/Struct:pca data[0]/Block:PCA Groups")
        labels = {e.ElementIndex: e.Fields[0].GetStringData() for e in pca_groups.Elements}
        index = labels.get(name)
        if index is None:
            element = pca_groups.AddElement()
        else:
            element = pca_groups.Elements[index]
            
        element.Fields[1].Data = desired_mesh_count
        
    
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
                
        functions = {e.Fields[0].GetStringData(): e.ElementIndex for e in self.tag.SelectField("Struct:definitions[0]/Block:functions").Elements}
        
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
                elif "pain" in state:
                    interpolation_rate = "0.333"
                    if state.endswith("gut"):
                        yaw_source_value = "damage gut yaw"
                        pitch_source_value = "damage gut pitch"
                        weight_source_value = "damage gut"
                    elif state.endswith("chest"):
                        yaw_source_value = "damage chest yaw"
                        pitch_source_value = "damage chest pitch"
                        weight_source_value = "damage chest"
                    elif state.endswith("head"):
                        yaw_source_value = "damage head yaw"
                        pitch_source_value = "damage head pitch"
                        weight_source_value = "damage head"
                    elif state.endswith("left_shoulder"):
                        yaw_source_value = "damage left shoulder yaw"
                        pitch_source_value = "damage left shoulder pitch"
                        weight_source_value = "damage left shoulder"
                    elif state.endswith("left_arm"):
                        yaw_source_value = "damage left arm yaw"
                        pitch_source_value = "damage left arm pitch"
                        weight_source_value = "damage left arm"
                    elif state.endswith("left_leg"):
                        yaw_source_value = "damage left leg yaw"
                        pitch_source_value = "damage left leg pitch"
                        weight_source_value = "damage left leg"
                    elif state.endswith("left_foot"):
                        yaw_source_value = "damage left foot yaw"
                        pitch_source_value = "damage left foot pitch"
                        weight_source_value = "damage left foot"
                    elif state.endswith("right_shoulder"):
                        yaw_source_value = "damage right shoulder yaw"
                        pitch_source_value = "damage right shoulder pitch"
                        weight_source_value = "damage right shoulder"
                    elif state.endswith("right_arm"):
                        yaw_source_value = "damage right arm yaw"
                        pitch_source_value = "damage right arm pitch"
                        weight_source_value = "damage right arm"
                    elif state.endswith("right_leg"):
                        yaw_source_value = "damage right leg yaw"
                        pitch_source_value = "damage right leg pitch"
                        weight_source_value = "damage right leg"
                    elif state.endswith("right_foot"):
                        yaw_source_value = "damage right foot yaw"
                        pitch_source_value = "damage right foot pitch"
                        weight_source_value = "damage right foot"
                    
                if state.endswith("_down"):
                    flag_weapon_down = True
                elif state == "aiming":
                    flag_blending = True
                    
                element.SelectField("yaw source").SetValue(yaw_source_value)
                element.SelectField("pitch source").SetValue(pitch_source_value)
                element.SelectField("weight source").SetValue(weight_source_value)
                element.SelectField("interpolation rate").SetStringData(interpolation_rate)
                
                weight_function_index = functions.get(state)
                if weight_function_index is not None:
                    element.SelectField("weight function").Value = weight_function_index
                    
                flags = element.SelectField("flags")
                
                if flag_weapon_down:
                    flags.SetBit("active only when weapon down", True)
                    
                if flag_blending:
                    flags.SetBit("attempt piece-wise blending", True)
                
                if flag_parent_adjust:
                    flags.SetBit("allow parent adjustment", True)
                
                self.tag_has_changes = True
                
    def get_node_usages(self) -> dict:
        usages = {}
        if self.block_node_usages.Elements.Count < 1:
            return usages
        
        items = [i.EnumName for i in self.block_node_usages.Elements[0].Fields[0].Items]
        
        for element in self.block_node_usages.Elements:
            usages[items[element.Fields[0].Value]] = element.Fields[1].Value
            
        return usages
    
    def _add_animation_settings(self, tag_animation: Animation, blender_animation):
        blender_animation.author_type = 'BLENDER'
        blender_animation.weight = tag_animation.element.SelectField("weight").Data
        blender_animation.loop_frame_index = tag_animation.element.SelectField("loop frame index").Data
        
        flags = tag_animation.element.SelectField("user flags")
        blender_animation.disable_interpolation_in = flags.TestBit("disable interpolation in")
        blender_animation.disable_interpolation_out = flags.TestBit("disable interpolation out")
        blender_animation.disable_mode_ik = flags.TestBit("disable mode ik")
        blender_animation.disable_weapon_ik = flags.TestBit("disable weapon ik")
        blender_animation.disable_weapon_aim = flags.TestBit("disable weapon aim\\1st person")
        blender_animation.disable_look_screen = flags.TestBit("disable look screen")
        blender_animation.disable_transition_adjustment = flags.TestBit("disable transition adjustment")
        blender_animation.force_weapon_ik_on = flags.TestBit("force weapon ik on")
        blender_animation.enable_animated_source_interpolation = flags.TestBit("enable animated source interpolation")
        blender_animation.disable_ik_sets = flags.TestBit("disable ik sets")
        blender_animation.disable_ik_chains = flags.TestBit("disable ik chains")
        blender_animation.translate_and_scale_root_only = flags.TestBit("translate and scale root only")
        blender_animation.enable_blend_out_on_replacement_anims = flags.TestBit("enable blend-out on replacement anims" if self.corinth else "enable blend out") 
        if self.corinth:
            blender_animation.override_player_input_with_motion = flags.TestBit("override player input with motion")
            blender_animation.pca_group_name = tag_animation.element.SelectField("pca group name").GetStringData()
        else:
            blender_animation.disable_subframe_interp_on_loop = flags.TestBit("disable subframe interp on loop")
            
        if flags.TestBit("use custom blend-in time" if self.corinth else "override default blend time"):
            blender_animation.override_blend_in_time = tag_animation.element.SelectField("override blend in time").Data
        if flags.TestBit("use custom blend-out time" if self.corinth else "override default blend out time"):
            blender_animation.override_blend_out_time = tag_animation.element.SelectField("override blend out time").Data
        
        # match tag_animation.compression:
        #     case Compression.medium_compression | Compression.reach_medium_compression:
        #         blender_animation.compression = "Medium"
        #     case Compression.rough_compression | Compression.reach_rough_compression:
        #         blender_animation.compression = "Rough"
        #     case Compression.uncompressed:
        
        # NOTE always setting uncompressed, no point the tag animations going through compression twice
        blender_animation.compression = "Uncompressed"
    
    def to_blender(self, render_model: str, armature, filter: str, import_pca=False):
        actions = []
        animations = []
        if self.block_animations.Elements.Count < 1:
            return print("No animations found in graph")

        pca_animations = {}
        node_names = self.get_nodes()
        
        node_usages = self.get_node_usages()

        model_context = nullcontext(None)
        if render_model:
            render_model_path = Path(render_model)
            if render_model_path.exists():
                model_context = RenderModelTag(path=render_model_path)
            else:
                utils.print_warning(f"Render model [{render_model_path}] was not found. Falling back to animation graph additional node data for native defaults.")

        with model_context as model:
            defaults, native_nodes, overlay_defaults = self._build_default_animation_nodes(node_names, model)
            shared_static_codec = self._read_shared_static_codec()
            native_resource_cache = {}
            native_animation_cache = {}
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
            
            self.nodes_count = nodes_count

            if armature.animation_data is None:
                armature.animation_data_create()
                
            tag_animations = self.get_animations()
            graph = self.to_dict(tag_animations)

            for tag_animation in tag_animations:
                if not (filter in tag_animation.name.tag_name or filter.replace(" ", ":") in tag_animation.name.tag_name):
                    continue
                
                overlay = tag_animation.animation_type == AnimationType.OVERLAY
                replacement = tag_animation.animation_type == AnimationType.REPLACEMENT
                imported_frame_count = self._imported_animation_frame_count(tag_animation)

                if tag_animation.frame_count < 1:
                    continue

                animation_name = tag_animation.name.data_name
                utils.print_step(animation_name)
                blender_animation = self.scene_nwo.animations.add()
                blender_animation.name = animation_name
                blender_animation.frame_start = 1
                blender_animation.frame_end = imported_frame_count
                animations.append(blender_animation.name)
                
                if tag_animation.composite_index > -1:
                    blender_animation.animation_type = "composite"
                    self._import_composite(blender_animation, tag_animation.composite_index)
                    continue
                
                action = bpy.data.actions.new(animation_name)
                slot = action.slots.new("OBJECT", armature.name)
                armature.animation_data.last_slot_identifier = slot.identifier
                armature.animation_data.action = action
                action.use_frame_range = True
                
                if tag_animation.contains_pca_data:
                    pca_animations[tag_animation.name.tag_name] = tag_animation.name.data_name

                match tag_animation.animation_type:
                    case AnimationType.NONE | AnimationType.BASE:
                        if tag_animation.world_relative:
                            blender_animation.animation_type = "world"
                        else:
                            blender_animation.animation_type = "base"
                        match tag_animation.frame_info_type:
                            case FrameInfoType.NONE:
                                blender_animation.animation_movement_data = "none"
                            case FrameInfoType.DX_DY:
                                blender_animation.animation_movement_data = "xy"
                            case FrameInfoType.DX_DY_DYAW:
                                blender_animation.animation_movement_data = "xyyaw"
                            case FrameInfoType.DX_DY_DZ_DYAW:
                                blender_animation.animation_movement_data = "xyzyaw"
                            case _:
                                blender_animation.animation_movement_data = "full"
                                
                    case AnimationType.OVERLAY:
                        blender_animation.animation_type = "overlay"
                        parent_nodes = tag_animation.shared_element.SelectField("object-space parent nodes")
                        if parent_nodes.Elements.Count > 0:
                            blender_animation.pose_overlay = True
                        offset_nodes = tag_animation.shared_element.SelectField("object space offset nodes")
                        for node_element in offset_nodes.Elements:
                            n_index = node_element.Fields[0].Value
                            if n_index < 0 or n_index >= nodes_count:
                                continue
                            a_node = blender_animation.animation_nodes.add()
                            a_node.name = node_names[n_index]
                            a_node.node_type = "object_space_offset_node"
                            blender_animation.active_animation_node_index = len(blender_animation.animation_nodes) - 1
                            
                    case AnimationType.REPLACEMENT:
                        blender_animation.animation_type = "replacement"
                        parent_nodes = tag_animation.shared_element.SelectField("object-space parent nodes")
                        for node_element in parent_nodes.Elements:
                            n_index = node_element.Fields[0].Value
                            if n_index < 0 or n_index >= nodes_count:
                                continue
                            a_node = blender_animation.animation_nodes.add()
                            a_node.name = node_names[n_index]
                            a_node.node_type = "replacement_correction_node"
                            blender_animation.active_animation_node_index = len(blender_animation.animation_nodes) - 1

                fik_anchor_nodes = tag_animation.shared_element.SelectField("forward-invert kinetic anchor nodes")
                for node_element in fik_anchor_nodes.Elements:
                    n_index = node_element.Fields[0].Value
                    if n_index < 0 or n_index >= nodes_count:
                        continue
                    a_node = blender_animation.animation_nodes.add()
                    a_node.name = node_names[n_index]
                    a_node.node_type = "fik_anchor_node"
                    blender_animation.active_animation_node_index = len(blender_animation.animation_nodes) - 1

                track = blender_animation.action_tracks.add()
                track.object = armature
                track.action = action
                success = False
                imported = False
                try:
                    transforms = self._animation_transforms(tag_animation, defaults, overlay_defaults, native_nodes, graph, shared_static_codec, native_resource_cache,native_animation_cache, tag_animations)
                    if transforms:
                        blender_animation.frame_end = max(blender_animation.frame_end, max(transforms))
                    self._to_armature_action(transforms, armature, action, native_nodes, {}, set(), blender_animation.pose_overlay)
                    success = True
                    imported = True
                except Exception:
                    utils.print_warning(f"Foundry animation decode failed for {tag_animation.name.data_name}. Falling back to ManagedBlam ({traceback.format_exc()})")

                if not success:
                    # Runs the old ManagedBlam animation extractor
                    if overlay:
                        utils.print_warning(f"{tag_animation.name.data_name} is an overlay, rotations will not be imported")

                    if not ensure_exporter():
                        if model is None:
                            utils.print_warning(
                                f"ManagedBlam fallback is unavailable for {tag_animation.name.data_name} because no render model was provided"
                            )
                        else:
                            utils.print_warning(f"Failed to use ManagedBlam animation exporter for {tag_animation.name.data_name}")
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
                        if overlay or replacement:
                            transforms[1] = {
                                node: cast(Matrix, node_base_matrices[node]).copy()
                                for node in nodes
                            }
                        for frame in range(tag_animation.frame_count):
                            if exporter.GetAnimationFrame(tag_animation.index, frame, animation_nodes, nodes_count):
                                imported_frame = frame + 2 if (overlay or replacement) else frame + 1
                                nodes_with_animations.update(
                                    self._add_transforms(
                                        animation_nodes,
                                        nodes,
                                        imported_frame,
                                        overlay,
                                        node_base_matrices,
                                        transforms,
                                    )
                                )
                        if tag_animation.animation_type == 3:
                            replacement_base_animations = self._get_base_animation_candidates(graph, tag_animation.name.tag_name)
                            if replacement_base_animations:
                                base_transforms[1] = {
                                    node: cast(Matrix, node_base_matrices[node]).copy()
                                    for node in nodes
                                }
                                for frame in range(tag_animation.frame_count):
                                    if exporter.GetAnimationFrame(replacement_base_animations[0].index, frame, animation_nodes, nodes_count):
                                        self._add_base_transforms(animation_nodes, nodes, frame + 2, node_base_matrices, base_transforms)

                        self._to_armature_action(transforms, armature, action, nodes, base_transforms, nodes_with_animations, blender_animation.pose_overlay)
                        imported = True

                if imported:
                    actions.append(action)
                    action.frame_end = blender_animation.frame_end
                    self._apply_regular_animation_events(tag_animation, blender_animation, armature, actions)
                    self._infer_wrap_events(tag_animation, blender_animation, armature, native_nodes if success else nodes, transforms, node_usages)
                    self._add_animation_settings(tag_animation, blender_animation)
                else:
                    utils.print_warning(f"Failed to import animation {tag_animation.name.data_name}")

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
    
    def _to_armature_action(self, transforms, armature: bpy.types.Object, action: bpy.types.Action, nodes: list[Node], base_transforms: dict, nodes_with_animations, pose_overlay=False):
        fcurves = utils.get_fcurves(action, armature.animation_data.last_slot_identifier)
        fcurves.clear()
        
        key_options = {'FAST'} if pose_overlay else {'FAST', 'NEEDED'}
        
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

                loc, rot, sca = transform_matrix.decompose()

                node.fc_loc_x.keyframe_points.insert(frame_idx, loc.x, options=key_options)
                node.fc_loc_y.keyframe_points.insert(frame_idx, loc.y, options=key_options)
                node.fc_loc_z.keyframe_points.insert(frame_idx, loc.z, options=key_options)
                
                node.fc_rot_w.keyframe_points.insert(frame_idx, rot.w, options=key_options)
                node.fc_rot_x.keyframe_points.insert(frame_idx, rot.x, options=key_options)
                node.fc_rot_y.keyframe_points.insert(frame_idx, rot.y, options=key_options)
                node.fc_rot_z.keyframe_points.insert(frame_idx, rot.z, options=key_options)
                
                node.fc_sca_x.keyframe_points.insert(frame_idx, sca.x, options=key_options)
                node.fc_sca_y.keyframe_points.insert(frame_idx, sca.y, options=key_options)
                node.fc_sca_z.keyframe_points.insert(frame_idx, sca.z, options=key_options)

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
        composites_block = self.tag.SelectField("Struct:definitions[0]/Block:composites")
        if composites_block.Elements.Count == 0 or composite_index >= composites_block.Elements.Count:
            return
        
        composite = composites_block.Elements[composite_index]
        axes_block = composite.SelectField("Block:axes")
        if axes_block is None or axes_block.Elements.Count == 0:
            return
        
        anims_block = composite.SelectField("Block:anims")
        adjust_names = ("none", "on_start", "on_loop", "continuous")
        
        def _resolve_animation_name(anim_element: TagFieldBlockElement) -> str:
            animation_name = ""
            anim_index = anim_element.SelectField("animIndex").Data
            if isinstance(anim_index, int) and 0 <= anim_index < self.block_animations.Elements.Count:
                animation_name = self.block_animations.Elements[anim_index].SelectField("name").GetStringData()
            if not animation_name:
                animation_name = anim_element.SelectField("source")
            if not animation_name:
                return ""
            return utils.AnimationName(animation_name).data_name
        
        def _select_timing_source() -> str:
            if anims_block is None:
                return blender_animation.name
            
            best_name = ""
            best_score = None
            for anim_element in anims_block.Elements:
                animation_name = _resolve_animation_name(anim_element)
                if not animation_name:
                    continue
                overridden = anim_element.SelectField("overridden").Data
                slide_axis = anim_element.SelectField("slideAxis").Data
                score = (
                    0 if overridden == 1 else 1,
                    0 if slide_axis == 0 else 1,
                    anim_element.ElementIndex,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best_name = animation_name
            
            return best_name or blender_animation.name
        
        def _leaf_value_from_tag(axis, raw_value: float) -> float:
            axis_name = axis.name
            if axis_name != "movement_angles":
                return raw_value
            
            if not axis.animation_source_bounds_manual:
                return raw_value
            
            axis_min, axis_max = axis.animation_source_bounds
            return axis_min + (raw_value * (axis_max - axis_min))
        
        blender_animation.timing_source = _select_timing_source()
        
        imported_axes = []
        for axis_index, axis in enumerate(axes_block.Elements):
            axis_name = axis.SelectField("name").GetStringData()
            if not axis_name:
                continue
            
            blender_axis = blender_animation.blend_axis.add()
            blender_axis.name = axis_name
            blender_axis.relationship = "PARENT" if axis_index == 0 else "CHILD"
            
            animation_bounds = axis.SelectField("animation bounds").Data
            blender_axis.animation_source_bounds_manual = True
            blender_axis.animation_source_bounds = (*animation_bounds,)
            
            input_bounds = axis.SelectField("input bounds").Data
            blender_axis.runtime_source_bounds_manual = True
            blender_axis.runtime_source_bounds = (*input_bounds,)
            
            blender_axis.animation_source_limit = axis.SelectField("blend limit").Data
            
            flags = axis.SelectField("flags")
            blender_axis.runtime_source_clamped = flags.TestBit("clamped")
            
            adjustment_index = axis.SelectField("update").Data
            if 0 <= adjustment_index < len(adjust_names):
                blender_axis.adjusted = adjust_names[adjustment_index]
            
            dead_zones = axis.SelectField("Block:dead zones")
            for dead_zone_index, dead_zone in enumerate(dead_zones.Elements):
                blender_dead_zone = blender_axis.dead_zones.add()
                blender_dead_zone.name = f"dead_zone{dead_zone_index}"
                bounds = dead_zone.SelectField("bounds").Data
                blender_dead_zone.bounds = (*bounds,)
                blender_dead_zone.rate = dead_zone.SelectField("rate").Data
            
            imported_axes.append(blender_axis)
        
        if not imported_axes:
            return
        
        blender_animation.blend_axis_active_index = 0
        leaf_parent = imported_axes[-1]
        
        if anims_block is None:
            return
        
        for anim_element in anims_block.Elements:
            animation_name = _resolve_animation_name(anim_element)
            if not animation_name:
                continue
            
            blender_leaf = leaf_parent.leaves.add()
            blender_leaf.animation = animation_name
            values_block = anim_element.SelectField("Block:values")
            
            for value_index, value_element in enumerate(values_block.Elements):
                if value_index > 9:
                    break
                raw_value = value_element.SelectField("value").Data
                if value_index < len(imported_axes):
                    raw_value = _leaf_value_from_tag(imported_axes[value_index], raw_value)
                setattr(blender_leaf, f"manual_blend_axis_{value_index}", True)
                setattr(blender_leaf, f"blend_axis_{value_index}", raw_value)
        
        if leaf_parent.leaves:
            leaf_parent.leaves_active_index = 0
        
            
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
                    
        chain_names = set()
        
        for element in self.block_ik_chains.Elements:
            name = element.SelectField("name").GetStringData()
            if name in chain_names:
                continue
            chain_names.add(name)
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
            
            # Let the events create these
            # self._make_ik_chain_object(armature, armatures_collection, name)
            # self._make_ik_chain_object(armature, armatures_collection, name, True) # pole target
            
        print(f"Added / Updated {self.block_ik_chains.Elements.Count} IK Chains")
        
    def _make_ik_chain_object(
        self,
        armature: bpy.types.Object,
        armatures_collection: bpy.types.Collection,
        ik_chain_name: str,
        pole=False,
        target_kind: str | None = None,
    ) -> bpy.types.Object:
        if target_kind is None:
            target_kind = "pole" if pole else "proxy"
        ob = bpy.data.objects.new(f"{armature.name}_{ik_chain_name}_{target_kind}_target", None)
        ob.empty_display_size = utils.blender_scale(0.1)
        ob.parent = armature
        ob.nwo.export_this = False
        ob.nwo.is_frame = True
        ob.rotation_mode = 'QUATERNION'
        armatures_collection.objects.link(ob)
        return ob
            
    def generate_renames(self, filter=""):
        '''Reads current blender animation names and then parses in the mode n state graph to set up renames in blender'''
        # dict with keys as blender animations and values as sets of renames
        real_animations = {anim.name.replace(" ", ":"): anim for anim in self.scene_nwo.animations}
        if filter:
            real_animations = {k: v for k, v in real_animations.items() if filter in k}

        tag_animations = self.get_animations()
        graph_dict = self.to_dict(tag_animations)
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
                
        print(f"Generated {len(renames)} renames from tag and applied these to {animations_with_renames_count} blender animations\nCreated {len(copies)} animation copies")
        
    def _animation_from_index(self, index, state_type="") -> Animation:
        element = self.block_animations.Elements[index]
        shared_animation_element = self._get_shared_animation_element(element)
        if shared_animation_element is not None:
            animation = Animation()
            animation.from_element(element, shared_animation_element, self.corinth)
            if state_type:
                animation.state_types.add(state_type)
            return animation
        
    def to_dict(self, tag_animations: list) -> dict:
        '''Parses the mode n state graph and turns it into a dict'''
        graph = {}
        
        def add_state(animation: Animation, state_name):
            animation.state_types.add(state_name)
            return animation
        
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
                        
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["actions"] = {action.Fields[0].GetStringData(): add_state(tag_animations[action.Fields[3].Elements[0].Fields[1].Value], "action") for action in set.Fields[4].Elements if action.Fields[3].Elements[0].Fields[1].Value > -1}
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["overlay_animations"] = {overlay.Fields[0].GetStringData(): add_state(tag_animations[overlay.Fields[3].Elements[0].Fields[1].Value], "overlay") for overlay in set.Fields[5].Elements if overlay.Fields[3].Elements[0].Fields[1].Value > -1}
                        
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"] = {}
                        for death_and_damage in set.Fields[6].Elements:
                            death_and_damage_label = death_and_damage.Fields[0].GetStringData()
                            graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"][death_and_damage_label] = {}
                            for direction in death_and_damage.Fields[1].Elements:
                                direction_label = directions[direction.ElementIndex]
                                graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"][death_and_damage_label][direction_label] = {regions[region.ElementIndex]: add_state(tag_animations[region.Fields[0].Elements[0].Fields[1].Value], "death and damage") for region in direction.Fields[0].Elements if region.Fields[0].Elements[0].Fields[1].Value > -1}
                                
                            
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["transitions"] = {}
                        
                        for transition in set.Fields[7].Elements:
                            transition_state = transition.Fields[0].GetStringData()
                            graph[mode_label][weapon_class_label][weapon_type_label][set_label]["transitions"][transition_state] = {f"2:{destination.Fields[0].GetStringData()}:{destination.Fields[1].GetStringData()}": add_state(tag_animations[destination.Fields[2].Elements[0].Fields[1].Value], "transition") for destination in transition.Fields[1].Elements if destination.Fields[2].Elements[0].Fields[1].Value > -1}
                            
                            
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
            tag_animations = self.get_animations()
            graph = self.to_dict(tag_animations)
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
        '''Create AnimationEvents from legacy graph events'''
        event_list_events = {}
        frame_event_list_path = self.get_frame_event_list()
        if not frame_event_list_path:
            utils.print_warning(f"Animation graph contains no reference to a frame event list")
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
        
        for animation in self.block_animations.Elements:
            name = animation.SelectField("StringId:name").GetStringData()
            name_with_spaces = name.replace(":", " ")
            blender_animation = blender_animations.get(name_with_spaces)
            if blender_animation is None:
                blender_animation = blender_animations.get(name)
                if not blender_animation:
                    # utils.print_warning(f"--- Animation graph contains animation {name_with_spaces} but Blender does not")
                    continue
                
            utils.print_bullet(f"Getting events for {blender_animation.name}")
            
            animation_events: list[AnimationEvent] = []
            
            for element in animation.SelectField("Block:shared animation data[0]/Block:frame events").Elements:
                event = AnimationEvent()
                event.from_element(element, True)
                animation_events.append(event)
                
            none_event = None
            
            def make_none_event():
                none_event = AnimationEvent()
                animation_events.append(none_event)
                return none_event
            
            for element in animation.SelectField("Block:shared animation data[0]/Block:sound events").Elements:
                if element.SelectField("ShortBlockIndex:sound").Value > -1:
                    sound_event = SoundEvent()
                    sound_event.from_element(element, unique_sounds, True)
                    
                    if sound_event.sound_reference is None:
                        continue
                    
                    if none_event is None:
                        none_event = make_none_event()
                        
                    none_event.sound_events.append(sound_event)
                    
            for element in animation.SelectField("Block:shared animation data[0]/Block:effect events").Elements:
                if element.SelectField("ShortBlockIndex:effect").Value > -1:
                    effect_event = EffectEvent()
                    effect_event.from_element(element, unique_effects, True)
                    
                    if effect_event.effect_reference is None:
                        continue
                    
                    if none_event is None:
                        none_event = make_none_event()
                        
                    none_event.effect_events.append(effect_event)
                        
            for element in animation.SelectField("Block:shared animation data[0]/Block:dialogue events").Elements:
                dialogue_event = DialogueEvent()
                dialogue_event.from_element(element, True)
                
                if none_event is None:
                    none_event = make_none_event()
                    
                none_event.dialogue_events.append(dialogue_event)
                    
            # See if we can make any ranged frame events
            def collapse_events(aes):
                aes.sort(key=lambda x: x.frame, reverse=True)
                result = []
                group_end_frame = aes[0].frame
                
                for curr, next in zip(aes, aes[1:] + [None]):
                    if next:
                        if next.frame == curr.frame - 1 and curr.type == next.type and not (curr.sound_events or curr.effect_events or curr.dialogue_events):
                            continue

                    # Finalize current group
                    curr.end_frame = group_end_frame
                    group_end_frame = next.frame if next else 0
                    result.append(curr)
                        
                return result

            if len(animation_events) > 1:
                animation_events = collapse_events(animation_events)
                    
            # Apply to blender
            def apply_flags(blender_data_event, reference: Reference):
                blender_data_event.flag_allow_on_player = reference.allow_on_player
                blender_data_event.flag_left_arm_only = reference.left_arm_only
                blender_data_event.flag_right_arm_only = reference.right_arm_only
                blender_data_event.flag_first_person_only = reference.first_person_only
                blender_data_event.flag_third_person_only = reference.third_person_only
                blender_data_event.flag_forward_only = reference.forward_only
                blender_data_event.flag_reverse_only = reference.reverse_only
                blender_data_event.flag_fp_no_aged_weapons = reference.fp_no_aged_weapons
                
            # Merge with event list events, frame event list gets priority
            list_events = event_list_events.get(name)
            if list_events is not None:
                graph_events = animation_events
                if not graph_events:
                    animation_events = list_events
                else:
                    valid_graph_events = []
                    for g_event in animation_events:
                        for f_event in list_events:
                            if f_event == g_event:
                                break
                        else:
                            valid_graph_events.append(g_event)
                        
                    animation_events = list_events + valid_graph_events
            
            if animation_events:
                to_remove_event_indices = []
                for idx, b_event in enumerate(blender_animation.animation_events):
                    if b_event.event_type == '_connected_geometry_animation_event_type_frame':
                        to_remove_event_indices.append(idx)
                        
                for i in reversed(to_remove_event_indices):
                    blender_animation.animation_events.remove(i)
                    
                for event in sorted(animation_events, key=lambda x: x.frame):
                    blender_event = blender_animation.animation_events.add()
                    # blender_event.name = event.name
                    blender_event.frame_frame = blender_animation.frame_start + event.frame
                    if event.end_frame > event.frame:
                        blender_event.multi_frame = 'range'
                        blender_event.frame_range = blender_animation.frame_start + event.end_frame
                    blender_event.frame_name = event.type
                    blender_event.event_id = event.unique_id
                    
                    data_events = event.sound_events + event.effect_events + event.dialogue_events
                    data_events.sort(key=lambda x: x.frame_offset)
                    
                    for data_event in data_events:
                        blender_data_event = blender_event.event_data.add()
                        blender_data_event.frame_offset = data_event.frame_offset
                        if isinstance(data_event, SoundEvent):
                            blender_data_event.data_type = 'SOUND'
                            blender_data_event.frame_offset = data_event.frame_offset
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
                    name_to_paths[anim.name.tag_name].append(":".join(path_tokens + [state]))

            elif cat == "transitions":
                for state, dests in node[cat].items():
                    for key, anim in dests.items():
                        name_to_paths[anim.name.tag_name].append(":".join(path_tokens + [state, key]))

            elif cat == "death_and_damage":
                for dmg_state, dirs in node[cat].items():
                    for dir_label, regions in dirs.items():
                        for reg_label, anim in regions.items():
                            name_to_paths[anim.name.tag_name].append(
                                ":".join(path_tokens + [dmg_state, dir_label, reg_label])
                            )

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
            continue
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

    toks = [t for t in toks if not (t.startswith("var") and t[3:].isdigit())]

    if len(toks) >= 5 and toks[-3] == "2":
        base, tail = toks[:-4], toks[-4:]
        return _strip_trailing_any(base) + tail

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
