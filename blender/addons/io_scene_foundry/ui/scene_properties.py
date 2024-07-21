# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from math import radians
import os
from pathlib import Path
import bpy
from bpy.props import (
    IntProperty,
    BoolProperty,
    EnumProperty,
    StringProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

from io_scene_foundry.utils.nwo_asset_types import asset_type_items
from io_scene_foundry.managed_blam.scenario import ScenarioTag
from io_scene_foundry.managed_blam.animation import AnimationTag

from ..icons import get_icon_id
from ..utils.nwo_utils import clean_tag_path, get_asset_animation_graph, get_asset_tag, get_prefs, get_project, is_corinth, poll_ui, reset_to_basis

#############################################################
# ANIMATION COPIES
#############################################################

class NWO_AnimationCopiesItems(PropertyGroup):
    name: StringProperty(name="Copy Name", options=set())
    source_name: StringProperty(name="Source Name", options=set())

#############################################################
# ANIMATION COMPOSITES
#############################################################

class NWO_AnimationLeavesItems(PropertyGroup):
    animation: PointerProperty(name="Animation", type=bpy.types.Action)
    uses_move_speed: BoolProperty(name="Uses Move Speed", options=set())
    move_speed: bpy.props.FloatProperty(name="Move Speed", options=set(), min=0, max=1, subtype='FACTOR')
    uses_move_angle: BoolProperty(name="Uses Move Angle", options=set())
    move_angle: bpy.props.FloatProperty(name="Move Angle", options=set(), subtype='ANGLE', min=0, max=radians(360))
    
class NWO_AnimationPhaseSetsItems(PropertyGroup):
    name: StringProperty(name="Name", options=set())
    priority: EnumProperty(
        name="Priority",
        options=set(),
        items=[
            ("default", "Default", ""),
            ("current", "Current", ""),
            ("cycle", "Cycle", ""),
            ("alternate", "Alternate", ""),
        ]
    )
    leaves_active_index: IntProperty(options=set())
    leaves: CollectionProperty(name="Animations", options=set(), type=NWO_AnimationLeavesItems)
    
    key_primary_keyframe: BoolProperty(name="Primary Keyframe", options=set())
    key_secondary_keyframe: BoolProperty(name="Secondary Keyframe", options=set())
    key_tertiary_keyframe: BoolProperty(name="Tertiary Keyframe", options=set())
    key_left_foot: BoolProperty(name="Left Foot", options=set())
    key_right_foot: BoolProperty(name="Right Foot", options=set())
    key_body_impact: BoolProperty(name="Body Impact", options=set())
    key_left_foot_lock: BoolProperty(name="Left Foot Lock", options=set())
    key_left_foot_unlock: BoolProperty(name="Left Foot Unlock", options=set())
    key_right_foot_lock: BoolProperty(name="Right Foot Lock", options=set())
    key_right_foot_unlock: BoolProperty(name="Right Foot Unlock", options=set())
    key_blend_range_marker: BoolProperty(name="Blend Range Marker", options=set())
    key_stride_expansion: BoolProperty(name="Stride Expansion", options=set())
    key_stride_contraction: BoolProperty(name="Stride Contraction", options=set())
    key_ragdoll_keyframe: BoolProperty(name="Ragdoll Keyframe", options=set())
    key_drop_weapon_keyframe: BoolProperty(name="Drop Weapon Keyframe", options=set())
    key_match_a: BoolProperty(name="Match A", options=set())
    key_match_b: BoolProperty(name="Match B", options=set())
    key_match_c: BoolProperty(name="Match C", options=set())
    key_match_d: BoolProperty(name="Match D", options=set())
    key_jetpack_closed: BoolProperty(name="Jetpack Closed", options=set())
    key_jetpack_open: BoolProperty(name="Jetpack Open", options=set())
    key_sound_event: BoolProperty(name="Sound Event", options=set())
    key_effect_event: BoolProperty(name="Effect Event", options=set())

class NWO_AnimationDeadZonesItems(PropertyGroup):
    name: StringProperty(name="Name")
    bounds: bpy.props.FloatVectorProperty(name="Dead Zone Bounds", options=set(), size=2, subtype='COORDINATES', min=0)
    rate: bpy.props.FloatProperty(name="Dead Zone Rate", options=set(), min=0, default=90)

class NWO_AnimationBlendAxisItems(PropertyGroup):
    name: EnumProperty(
        name="Type",
        options=set(),
        items=[
            ("movement_angles", "Movement Angles", ""), # linear_movement_angle get_move_angle
            ("movement_speed", "Movement Speed", ""), # linear_movement_speed get_move_speed
            ("turn_rate", "Turn Rate", ""), # average_angular_rate get_turn_rate
            ("vertical", "Vertical", ""), # translation_offset_z get_destination_vertical
            ("horizontal", "Horizontal", ""), # translation_offset_horizontal get_destination_forward
        ]
    )
    
    animation_source_bounds_manual: BoolProperty(name="Animation Manual Bounds", options=set())
    animation_source_bounds: bpy.props.FloatVectorProperty(name="Animation Source Bounds", options=set(), size=2, subtype='COORDINATES', min=0)
    animation_source_limit: bpy.props.FloatProperty(name="Animation Source Limit", options=set())
    
    runtime_source_bounds_manual: BoolProperty(name="Animation Manual Bounds", options=set())
    runtime_source_bounds: bpy.props.FloatVectorProperty(name="Runtime Source Bounds", options=set(), size=2, subtype='COORDINATES', min=0)
    runtime_source_clamped: BoolProperty(name="Runtime Source Clamped", options=set())
    
    adjusted: bpy.props.EnumProperty(
        name="Adjustment",
        options=set(),
        items=[
            ("none", "None", ""),
            ("on_start", "On Start", ""),
            ("on_loop", "On Loop", ""),
            ("continuous", "Continuous", ""),
        ]
    )

    leaves_active_index: IntProperty(options=set())
    leaves: CollectionProperty(name="Animations", options=set(), type=NWO_AnimationLeavesItems)
    
    dead_zones_active_index: IntProperty(options=set())
    dead_zones: CollectionProperty(name="Blend Axis Dead Zones", options=set(), type=NWO_AnimationDeadZonesItems)
    
    phase_sets_active_index: IntProperty(options=set())
    phase_sets: CollectionProperty(name="Animation Sets", options=set(), type=NWO_AnimationPhaseSetsItems)
    

class NWO_AnimationCompositesItems(PropertyGroup):
    name: StringProperty(name="Name", options=set())
    overlay: BoolProperty(name="Overlay", options=set())
    
    timing_source: PointerProperty(name="Timing Source", type=bpy.types.Action)
    blend_axis_active_index: IntProperty(options=set())
    blend_axis: CollectionProperty(name="Blend Axis", options=set(), type=NWO_AnimationBlendAxisItems)
    
#############################################################
#############################################################

class NWO_ZoneSets_ListItems(PropertyGroup):
    name: StringProperty()
    bsp_0: BoolProperty()
    bsp_1: BoolProperty()
    bsp_2: BoolProperty()
    bsp_3: BoolProperty()
    bsp_4: BoolProperty()
    bsp_5: BoolProperty()
    bsp_6: BoolProperty()
    bsp_7: BoolProperty()
    bsp_8: BoolProperty()
    bsp_9: BoolProperty()
    bsp_10: BoolProperty()
    bsp_11: BoolProperty()
    bsp_12: BoolProperty()
    bsp_13: BoolProperty()
    bsp_14: BoolProperty()
    bsp_15: BoolProperty()
    bsp_16: BoolProperty()
    bsp_17: BoolProperty()
    bsp_18: BoolProperty()
    bsp_19: BoolProperty()
    bsp_20: BoolProperty()
    bsp_21: BoolProperty()
    bsp_22: BoolProperty()
    bsp_23: BoolProperty()
    bsp_24: BoolProperty()
    bsp_25: BoolProperty()
    bsp_26: BoolProperty()
    bsp_27: BoolProperty()
    bsp_28: BoolProperty()
    bsp_29: BoolProperty()
    bsp_30: BoolProperty()
    bsp_31: BoolProperty()

class NWO_Permutations_ListItems(PropertyGroup):

    def update_name(self, context):
        if self.old != self.name:
            i = int(self.path_from_id().rpartition('[')[2].strip(']'))
            bpy.ops.nwo.permutation_rename(new_name=self.name, index=i)

    old: StringProperty(options=set())

    name: StringProperty(
        name="Name",
        update=update_name,
        )

    def update_hidden(self, context):
        bpy.ops.nwo.permutation_hide(entry_name=self.name)

    hidden: BoolProperty(name="Hidden", update=update_hidden, options=set())

    def update_hide_select(self, context):
        bpy.ops.nwo.permutation_hide_select(entry_name=self.name)

    hide_select: BoolProperty(name="Hide Select", update=update_hide_select, options=set())

    active: BoolProperty(
        name="Active",
        description="If false, this region will not be active in the model tag except if added to a variant",
        default=True,
    )

class NWO_Regions_ListItems(PropertyGroup):

    def update_name(self, context):
        if self.old != self.name:
            i = int(self.path_from_id().rpartition('[')[2].strip(']'))
            bpy.ops.nwo.region_rename(new_name=self.name, index=i)

    old: StringProperty(options=set())

    name: StringProperty(
        name="Name",
        update=update_name,
        options=set(),
        )

    def update_hidden(self, context):
        bpy.ops.nwo.region_hide(entry_name=self.name)

    hidden: BoolProperty(name="Hidden", update=update_hidden, options=set())

    def update_hide_select(self, context):
        bpy.ops.nwo.region_hide_select(entry_name=self.name)

    hide_select: BoolProperty(name="Hide Select", update=update_hide_select, options=set())

    active: BoolProperty(
        name="Active",
        description="If false, this region will not be active in the model tag except if added to a variant",
        default=True,
    )

class NWO_BSP_ListItems(PropertyGroup):
    name: StringProperty(name="BSP Table", options=set())

class NWO_GlobalMaterial_ListItems(PropertyGroup):
    name: StringProperty(name="Global Material Table", options=set())
    
class NWO_IKChain(PropertyGroup):
    name: StringProperty(name="Name", options=set())
    start_node: StringProperty(name="Start Bone", options=set())
    effector_node: StringProperty(name="Effector Bone", options=set())
    
class NWO_ControlObjects(PropertyGroup):
    ob: PointerProperty(type=bpy.types.Object, options=set())
    
def prefab_warning(self, context):
    self.layout.label(text=f"Halo Reach does not support prefab assets")

# class NWO_Asset_ListItems(PropertyGroup):
#     def GetSharedAssetName(self):
#         name = self.shared_asset_path
#         name = name.rpartition("\\")[2]
#         name = name.rpartition(".sidecar.xml")[0]

#         return name

#     shared_asset_name: StringProperty(
#         get=GetSharedAssetName,
#     )

#     shared_asset_path: StringProperty()

#     shared_asset_types = [
#         ("BipedAsset", "Biped", ""),
#         ("CrateAsset", "Crate", ""),
#         ("CreatureAsset", "Creature", ""),
#         ("Device_ControlAsset", "Device Control", ""),
#         ("Device_MachineAsset", "Device Machine", ""),
#         ("Device_TerminalAsset", "Device Terminal", ""),
#         ("Effect_SceneryAsset", "Effect Scenery", ""),
#         ("EquipmentAsset", "Equipment", ""),
#         ("GiantAsset", "Giant", ""),
#         ("SceneryAsset", "Scenery", ""),
#         ("VehicleAsset", "Vehicle", ""),
#         ("WeaponAsset", "Weapon", ""),
#         ("ScenarioAsset", "Scenario", ""),
#         ("Decorator_SetAsset", "Decorator Set", ""),
#         ("Particle_ModelAsset", "Particle Model", ""),
#     ]

#     shared_asset_type: EnumProperty(
#         name="Type",
#         default="BipedAsset",
#         options=set(),
#         items=shared_asset_types,
#     )


class NWO_ScenePropertiesGroup(PropertyGroup):
    # ANIMATION
    def update_active_action_index(self, context):
        if self.active_action_index > -1:
            animated_objects = reset_to_basis(context, True)
            for ob in animated_objects:
                if ob.animation_data:
                    ob.animation_data.action = bpy.data.actions[self.active_action_index]

            if get_prefs().sync_timeline_range:
                bpy.ops.nwo.set_timeline()
            
    def get_active_action_index(self):
        ob = getattr(bpy.context, "object", 0)
        if not ob or not ob.animation_data:
            return self.old_active_action_index
        
        if ob.animation_data.action is None:
            return -1
        
        real_action_index = bpy.data.actions.values().index(ob.animation_data.action)
        if self.old_active_action_index != real_action_index:
            self.old_active_action_index = real_action_index
            return real_action_index
        else:
            return self.old_active_action_index
    
    def set_active_action_index(self, value):
        ob = bpy.context.object
        if ob and ob.animation_data:
            ob.animation_data.action = bpy.data.actions[value]
        self.old_active_action_index = value
    
    active_action_index: IntProperty(
        update=update_active_action_index,
        get=get_active_action_index,
        set=set_active_action_index,
        options=set()
    )
    
    old_active_action_index: IntProperty(default=-1, options=set())
    
    exclude_first_frame: BoolProperty(options=set())
    exclude_last_frame: BoolProperty(options=set())

    # shared_assets: CollectionProperty(
    #     type=NWO_Asset_ListItems,
    # )

    # shared_assets_index: IntProperty(
    #     name="Index for Shared Asset",
    #     default=0,
    #     min=0,
    # )
    
    animation_copies_active_index: IntProperty(options=set())
    animation_copies: CollectionProperty(type=NWO_AnimationCopiesItems, options=set())
    
    animation_composites_active_index: IntProperty(options=set())
    animation_composites: CollectionProperty(type=NWO_AnimationCompositesItems, options=set())
    
    zone_sets_active_index: IntProperty(options=set())
    zone_sets: CollectionProperty(type=NWO_ZoneSets_ListItems, options=set())
    
    user_removed_all_zone_set: BoolProperty()

    def items_mesh_type_ui(self, context):
        """Function to handle context for mesh enum lists"""
        h4 = is_corinth()
        items = []

        if poll_ui("decorator_set"):
            items.append(
                (
                    "_connected_geometry_mesh_type_decorator",
                    "Decorator",
                    "Decorator mesh type. Supports up to 4 level of detail variants",
                    get_icon_id("decorator"),
                    0,
                )
            )
        elif poll_ui(("model", "sky", "particle_model")):
            items.append(
                (
                    "_connected_geometry_mesh_type_render",
                    "Render",
                    "Render only geometry",
                    get_icon_id("render_geometry"),
                    0,
                )
            )
            if poll_ui("model"):
                items.append(
                    (
                        "_connected_geometry_mesh_type_collision",
                        "Collision",
                        "Collision only geometry. Acts as bullet collision and for scenery also provides player collision",
                        get_icon_id("collider"),
                        1,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_mesh_type_physics",
                        "Physics",
                        "Physics only geometry. Uses havok physics to interact with static and dynamic meshes",
                        get_icon_id("physics"),
                        2,
                    )
                )
                # if not h4: NOTE removing these for now until I figure out how they work
                #     items.append(('_connected_geometry_mesh_type_object_instance', 'Flair', 'Instanced mesh for models. Can be instanced across mutliple permutations', get_icon_id("flair"), 3))
        elif poll_ui("scenario"):
            items.append(
                (
                    "_connected_geometry_mesh_type_structure",
                    "Structure",
                    "Structure bsp geometry. By default provides render and bullet/player collision",
                    get_icon_id("structure"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_poop",
                    "Instance",
                    "Instanced geometry. Geometry capable of cutting through structure mesh",
                    get_icon_id("instance"),
                    1,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_poop_collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    get_icon_id("collider"),
                    2,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_plane",
                    "Plane",
                    "Non rendered geometry which provides various utility functions in a bsp. The planes can cut through bsp geometry. Supports portals, fog planes, and water surfaces",
                    get_icon_id("surface"),
                    3,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_volume",
                    "Volume",
                    "Non rendered geometry which defines regions for special properties",
                    get_icon_id("volume"),
                    4,
                )
            )
        elif poll_ui("prefab"):
            items.append(
                (
                    "_connected_geometry_mesh_type_poop",
                    "Instance",
                    "Instanced geometry. Geometry capable of cutting through structure mesh",
                    get_icon_id("instance"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_poop_collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    get_icon_id("collider"),
                    1,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_cookie_cutter",
                    "Cookie Cutter",
                    "Non rendered geometry which cuts out the region it defines from the pathfinding grid",
                    get_icon_id("cookie_cutter"),
                    2,
                )
            )

        return items

    default_mesh_type_ui: EnumProperty(
        name="Default Mesh Type",
        options=set(),
        description="Set the default Halo mesh type for new objects",
        items=items_mesh_type_ui,
    )

    def apply_props(self, context):
        for ob in context.scene.objects:
            ob_nwo = ob.data.nwo

            if ob_nwo.mesh_type_ui == "":
                if self.asset_type == "decorator_set":
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_decorator"
                elif self.asset_type == "scenario":
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_structure"
                elif self.asset_type == "prefab":
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_poop"
                else:
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_render"
    
    def update_asset_type(self, context):
        if self.asset_type == 'animation':
            context.scene.nwo_halo_launcher.open_model_animation_graph = True

    asset_type: EnumProperty(
        name="Asset Type",
        options=set(),
        description="The type of asset you are creating",
        items=asset_type_items,
        update=update_asset_type,
    )
    
    asset_animation_type: EnumProperty(
        name="Animation Type",
        options=set(),
        items=[
            ("first_person", "First Person", ""),
            ("standalone", "Standalone / Cinematic", ""),
        ]
    )

    forward_direction: EnumProperty(
        name="Scene Forward",
        options=set(),
        description="The forward direction you are using for the scene. By default Halo uses X forward. Whichever option is set as the forward direction in Blender will be oriented to X forward in game i.e. a model facing -Y in Blender will face X in game",
        default="y-",
        items=[
            ("y-", "-Y", "Model is facing Y negative"),
            ("y", "Y", "Model is facing Y positive"),
            ("x-", "-X", "Model is facing X negative"),
            ("x", "X", "Model is facing X positive"),   
        ],
    )

    output_biped: BoolProperty(
        name="Biped",
        description="",
        default=False,
        options=set(),
    )
    output_crate: BoolProperty(
        name="Crate",
        description="",
        default=False,
        options=set(),
    )
    output_creature: BoolProperty(
        name="Creature",
        description="",
        default=False,
        options=set(),
    )
    output_device_control: BoolProperty(
        name="Device Control",
        description="",
        default=False,
        options=set(),
    )
    output_device_dispenser: BoolProperty(
        name="Device Dispenser",
        description="",
        default=False,
        options=set(),
    )
    output_device_machine: BoolProperty(
        name="Device Machine",
        description="",
        default=False,
        options=set(),
    )
    output_device_terminal: BoolProperty(
        name="Device Terminal",
        description="",
        default=False,
        options=set(),
    )
    output_effect_scenery: BoolProperty(
        name="Effect Scenery",
        description="",
        default=False,
        options=set(),
    )
    output_equipment: BoolProperty(
        name="Equipment",
        description="",
        default=False,
        options=set(),
    )
    output_giant: BoolProperty(
        name="Giant",
        description="",
        default=False,
        options=set(),
    )
    output_scenery: BoolProperty(
        name="Scenery",
        description="",
        default=True,
        options=set(),
    )
    output_vehicle: BoolProperty(
        name="Vehicle",
        description="",
        default=False,
        options=set(),
    )
    output_weapon: BoolProperty(
        name="Weapon",
        description="",
        default=False,
        options=set(),
    )
    
    def template_model_clean_tag_path(self, context):
        self["template_model"] = clean_tag_path(
            self["template_model"],
            "model"
        ).strip('"')
    def template_biped_clean_tag_path(self, context):
        self["template_biped"] = clean_tag_path(
            self["template_biped"],
            "biped"
        ).strip('"')
    def template_crate_clean_tag_path(self, context):
        self["template_crate"] = clean_tag_path(
            self["template_crate"],
            "crate"
        ).strip('"')
    def template_creature_clean_tag_path(self, context):
        self["template_creature"] = clean_tag_path(
            self["template_creature"],
            "creature"
        ).strip('"')
    def template_device_control_clean_tag_path(self, context):
        self["template_device_control"] = clean_tag_path(
            self["template_device_control"],
            "device_control"
        ).strip('"')
    def template_device_dispenser_clean_tag_path(self, context):
        self["template_device_dispenser"] = clean_tag_path(
            self["template_device_dispenser"],
            "device_dispenser"
        ).strip('"')
    def template_device_machine_clean_tag_path(self, context):
        self["template_device_machine"] = clean_tag_path(
            self["template_device_machine"],
            "device_machine"
        ).strip('"')
    def template_device_terminal_clean_tag_path(self, context):
        self["template_device_terminal"] = clean_tag_path(
            self["template_device_terminal"],
            "device_terminal"
        ).strip('"')
    def template_effect_scenery_clean_tag_path(self, context):
        self["template_effect_scenery"] = clean_tag_path(
            self["template_effect_scenery"],
            "effect_scenery"
        ).strip('"')
    def template_equipment_clean_tag_path(self, context):
        self["template_equipment"] = clean_tag_path(
            self["template_equipment"],
            "equipment"
        ).strip('"')
    def template_giant_clean_tag_path(self, context):
        self["template_giant"] = clean_tag_path(
            self["template_giant"],
            "giant"
        ).strip('"')
    def template_scenery_clean_tag_path(self, context):
        self["template_scenery"] = clean_tag_path(
            self["template_scenery"],
            "scenery"
        ).strip('"')
    def template_vehicle_clean_tag_path(self, context):
        self["template_vehicle"] = clean_tag_path(
            self["template_vehicle"],
            "vehicle"
        ).strip('"')
    def template_weapon_clean_tag_path(self, context):
        self["template_weapon"] = clean_tag_path(self["template_weapon"], "weapon").strip('"')
        if get_asset_tag('.weapon'):
            bpy.ops.nwo.update_template().tag_type = 'vehicle'
            
    
    template_model: StringProperty(
        name="Model Template",
        description="Tag relative path to the model tag to use as a base if this asset does not already have one",
        update=template_model_clean_tag_path,
        options=set(),
    )
    template_biped: StringProperty(
        name="Biped Template",
        description="Tag relative path to the biped tag to use as a base if this asset does not already have one",
        update=template_biped_clean_tag_path,
        options=set(),
    )
    template_crate: StringProperty(
        name="Crate Template",
        description="Tag relative path to the crate tag to use as a base if this asset does not already have one",
        update=template_crate_clean_tag_path,
        options=set(),
    )
    template_creature: StringProperty(
        name="Creature Template",
        description="Tag relative path to the creature tag to use as a base if this asset does not already have one",
        update=template_creature_clean_tag_path,
        options=set(),
    )
    template_device_control: StringProperty(
        name="Device Control Template",
        description="Tag relative path to the device_control tag to use as a base if this asset does not already have one",
        update=template_device_control_clean_tag_path,
        options=set(),
    )
    template_device_dispenser: StringProperty(
        name="Device Dispenser Template",
        description="Tag relative path to the device_dispenser tag to use as a base if this asset does not already have one",
        update=template_device_dispenser_clean_tag_path,
        options=set(),
    )
    template_device_machine: StringProperty(
        name="Device Machine Template",
        description="Tag relative path to the device_machine tag to use as a base if this asset does not already have one",
        update=template_device_machine_clean_tag_path,
        options=set(),
    )
    template_device_terminal: StringProperty(
        name="Device Terminal Template",
        description="Tag relative path to the device_terminal tag to use as a base if this asset does not already have one",
        update=template_device_terminal_clean_tag_path,
        options=set(),
    )
    template_effect_scenery: StringProperty(
        name="Effect Scenery Template",
        description="Tag relative path to the effect_scenery tag to use as a base if this asset does not already have one",
        update=template_effect_scenery_clean_tag_path,
        options=set(),
    )
    template_equipment: StringProperty(
        name="Equipment Template",
        description="Tag relative path to the equipment tag to use as a base if this asset does not already have one",
        update=template_equipment_clean_tag_path,
        options=set(),
    )
    template_giant: StringProperty(
        name="Giant Template",
        description="Tag relative path to the giant tag to use as a base if this asset does not already have one",
        update=template_giant_clean_tag_path,
        options=set(),
    )
    template_scenery: StringProperty(
        name="Scenery Template",
        description="Tag relative path to the scenery tag to use as a base if this asset does not already have one",
        update=template_scenery_clean_tag_path,
        options=set(),
    )
    template_vehicle: StringProperty(
        name="Vehicle Template",
        description="Tag relative path to the vehicle tag to use as a base if this asset does not already have one",
        update=template_vehicle_clean_tag_path,
        options=set(),
    )
    template_weapon: StringProperty(
        name="Weapon Template",
        description="Tag relative path to the weapon tag to use as a base if this asset does not already have one",
        update=template_weapon_clean_tag_path,
        options=set(),
    )

    light_tools_active: BoolProperty(options=set())
    light_tools_pinned: BoolProperty(options=set())
    light_tools_expanded: BoolProperty(default=True, options=set())

    object_properties_active: BoolProperty(options=set())
    object_properties_pinned: BoolProperty(options=set())
    object_properties_expanded: BoolProperty(default=True, options=set())

    material_properties_active: BoolProperty(options=set())
    material_properties_pinned: BoolProperty(options=set())
    material_properties_expanded: BoolProperty(default=True, options=set())

    animation_manager_active: BoolProperty(options=set())
    animation_manager_pinned: BoolProperty(options=set())
    animation_manager_expanded: BoolProperty(default=True, options=set())

    scene_properties_active: BoolProperty(default=False, options=set())
    scene_properties_pinned: BoolProperty(options=set())
    scene_properties_expanded: BoolProperty(default=True, options=set())

    asset_editor_active: BoolProperty(default=True, options=set())
    asset_editor_pinned: BoolProperty(options=set())
    output_tags_expanded: BoolProperty(default=True, options=set())
    asset_editor_expanded: BoolProperty(default=True, options=set())
    # model_overrides_expanded: BoolProperty(default=False, options=set())
    scenario_expanded: BoolProperty(default=False, options=set())
    lighting_expanded: BoolProperty(default=False, options=set())
    zone_sets_expanded: BoolProperty(default=False, options=set())
    objects_expanded: BoolProperty(default=False, options=set())
    prefabs_expanded: BoolProperty(default=False, options=set())
    model_expanded: BoolProperty(default=True, options=set())
    render_model_expanded: BoolProperty(default=False, options=set())
    collision_model_expanded: BoolProperty(default=False, options=set())
    animation_graph_expanded: BoolProperty(default=False, options=set())
    physics_model_expanded: BoolProperty(default=False, options=set())
    crate_expanded: BoolProperty(default=False, options=set())
    scenery_expanded: BoolProperty(default=False, options=set())
    effect_scenery_expanded: BoolProperty(default=False, options=set())
    device_control_expanded: BoolProperty(default=False, options=set())
    device_machine_expanded: BoolProperty(default=False, options=set())
    device_terminal_expanded: BoolProperty(default=False, options=set())
    device_dispenser_expanded: BoolProperty(default=False, options=set())
    biped_expanded: BoolProperty(default=False, options=set())
    creature_expanded: BoolProperty(default=False, options=set())
    giant_expanded: BoolProperty(default=False, options=set())
    vehicle_expanded: BoolProperty(default=False, options=set())
    weapon_expanded: BoolProperty(default=False, options=set())
    equipment_expanded: BoolProperty(default=False, options=set())
    
    model_rig_expanded: BoolProperty(default=True, options=set())
    rig_controls_expanded: BoolProperty(default=False, options=set())
    rig_object_controls_expanded: BoolProperty(default=False, options=set())
    rig_usages_expanded: BoolProperty(default=False, options=set())
    ik_chains_expanded: BoolProperty(default=False, options=set())
    animation_copies_expanded: BoolProperty(default=False, options=set())
    animation_composites_expanded: BoolProperty(default=False, options=set())
    
    asset_shaders_expanded: BoolProperty(default=True, options=set())
    importer_expanded: BoolProperty(default=True, options=set())
    camera_sync_expanded: BoolProperty(default=True, options=set())
    rig_tools_expanded: BoolProperty(default=True, options=set())
    bsp_tools_expanded: BoolProperty(default=True, options=set())
    
    regions_table_expanded: BoolProperty(default=True, options=set())
    permutations_table_expanded: BoolProperty(default=True, options=set())
    object_visibility_expanded: BoolProperty(default=True, options=set())

    mesh_properties_expanded: BoolProperty(default=True, options=set())
    face_properties_expanded: BoolProperty(default=True, options=set())
    instance_proxies_expanded: BoolProperty(default=True, options=set())
    
    image_properties_expanded: BoolProperty(default=True, options=set())

    sets_manager_active: BoolProperty(options=set())
    sets_manager_pinned: BoolProperty(options=set())
    sets_manager_expanded: BoolProperty(default=True, options=set())

    tools_active : BoolProperty(options=set())
    tools_pinned: BoolProperty(options=set())
    tools_expanded : BoolProperty(default=True, options=set())

    help_active : BoolProperty(options=set())
    help_pinned: BoolProperty(options=set())
    help_expanded : BoolProperty(default=True, options=set())

    settings_active : BoolProperty(options=set())
    settings_pinned: BoolProperty(options=set())
    settings_expanded : BoolProperty(default=True, options=set())

    toolbar_expanded : BoolProperty(
        name="Toggle Foundry Toolbar",
        default=True,
        options=set(),
    )

    def render_clean_tag_path(self, context):
        self["render_model_path"] = clean_tag_path(self["render_model_path"],
            "render_model"
        ).strip('"')
    def collision_clean_tag_path(self, context):
        self["collision_model_path"] = clean_tag_path(
            self["collision_model_path"],
            "collision_model"
        ).strip('"')
    def physics_clean_tag_path(self, context):
        self["physics_model_path"] = clean_tag_path(
            self["physics_model_path"],
            "physics_model"
        ).strip('"')
    def animation_clean_tag_path(self, context):
        self["animation_graph_path"] = clean_tag_path(
            self["animation_graph_path"],
            "model_animation_graph"
        ).strip('"')
    def fp_model_clean_tag_path(self, context):
        self["fp_model_path"] = clean_tag_path(
            self["fp_model_path"],
            "render_model"
        ).strip('"')
    def gun_model_clean_tag_path(self, context):
        self["gun_model_path"] = clean_tag_path(
            self["gun_model_path"],
            "render_model"
        ).strip('"')

    render_model_from_blend : BoolProperty(name="Render Model built from Blend", default=True)
    render_model_path : StringProperty(
        name="Render Model Override Path",
        description="Path to an existing render model tag, overrides the tag generated by this asset on import. This should not point to any tags generated by this export",
        update=render_clean_tag_path,
        options=set(),
        )
    
    collision_model_from_blend : BoolProperty(name="Collision Model built from Blend", default=True)
    collision_model_path : StringProperty(
        name="Collision Model Override Path",
        description="Path to an existing collision model tag, overrides the tag generated by this asset on import. This should not point to any tags generated by this export",
        update=collision_clean_tag_path,
        options=set(),
        )
    
    physics_model_from_blend : BoolProperty(name="Physics Model built from Blend", default=True)
    physics_model_path : StringProperty(
        name="Physics Model Override Path",
        description="Path to an existing physics model tag, overrides the tag generated by this asset on import. This should not point to any tags generated by this export",
        update=physics_clean_tag_path,
        options=set(),
        )
    
    animation_graph_from_blend : BoolProperty(name="Animation Graph built from Blend", default=True)
    animation_graph_path : StringProperty(
        name="Animation Graph Override Path",
        description="Path to an existing model animation graph tag, overrides the tag generated by this asset on import. This also ensures that the imported node order for your render model (and collision/physics) matches that of the nodes in the given graph. This should not point to any tags generated by this export",
        update=animation_clean_tag_path,
        options=set(),
        )
    
    fp_model_path : StringProperty(
        name="FP Render Model Path",
        description="Path to the first person arms render model used by this animation. Ensures bone order matches the specified FP model",
        update=fp_model_clean_tag_path,
        options=set(),
        )
    
    gun_model_path : StringProperty(
        name="Gun Render Model Path",
        description="Path to the gun render model used by this animation. Ensures bone order matches the specified gun model",
        update=gun_model_clean_tag_path,
        options=set(),
        )
    
    instance_proxy_running : BoolProperty(options=set())

    shader_sync_active : BoolProperty(
        name="Shader Sync",
        description="Sync's the active material with the corresponding Halo Shader/Material tag. Only active when the material has been marked as linked to game",
        options=set()
    )
    
    material_sync_rate : bpy.props.FloatProperty(
        name="Sync Rate",
        description="How often Halo Material Sync should refresh",
        min=0.001,
        default=0.01,
        max=3,
        subtype='TIME_ABSOLUTE',
        options=set(),
    )
    
    light_sync_active : BoolProperty(
        name="Light Sync",
        description="",
        options=set()
    )
    
    light_sync_rate : bpy.props.FloatProperty(
        name="Sync Rate",
        description="How often Light Sync should refresh",
        min=0.001,
        default=0.1,
        max=3,
        subtype='TIME_ABSOLUTE',
        options=set(),
    )
    
    lights_export_on_save : BoolProperty(
        name="Export Lights on Blender Save",
        description="Exports all lights from Blender whenever the Blend file is saved",
    )
    
    prefabs_export_on_save : BoolProperty(
        name="Export Prefabs on Blender Save",
        description="Exports all prefabs from Blender whenever the Blend file is saved",
    )
    
    object_sync_active : BoolProperty(
        name="Object Sync",
        description="",
        options=set()
    )
    
    object_sync_rate : bpy.props.FloatProperty(
        name="Sync Rate",
        description="How often Object Sync should refresh",
        min=0.001,
        default=0.01,
        max=3,
        subtype='TIME_ABSOLUTE',
        options=set(),
    )
    
    camera_sync_active : BoolProperty(
        name="Camera Sync",
        description="",
        options=set()
    )

    scene_project : StringProperty(
        name="Project",
        options=set(),
    )
    
    storage_only: BoolProperty(options=set())

    # TABLES

    regions_table: CollectionProperty(type=NWO_Regions_ListItems, options=set())
    regions_table_active_index: IntProperty(options=set())
    permutations_table: CollectionProperty(type=NWO_Permutations_ListItems, options=set())
    permutations_table_active_index: IntProperty(options=set())
    bsp_table: CollectionProperty(type=NWO_BSP_ListItems, options=set())
    bsp_active_index: IntProperty(options=set())
    global_material_table: CollectionProperty(type=NWO_GlobalMaterial_ListItems, options=set())
    global_material_active_index: IntProperty(options=set())
    
    # Rig Validation
    
    def poll_armature(self, object: bpy.types.Object):
        return object.type == 'ARMATURE' and object not in (self.main_armature, self.support_armature_a, self.support_armature_b, self.support_armature_c)
    
    armature_has_parent: BoolProperty(options=set())
    armature_bad_transforms: BoolProperty(options=set())
    multiple_root_bones: BoolProperty(options=set())
    invalid_root_bone: BoolProperty(options=set())
    needs_pose_bones: BoolProperty(options=set())
    too_many_bones: BoolProperty(options=set())
    bone_names_too_long: BoolProperty(options=set())
    pose_bones_bad_transforms: BoolProperty(options=set())
    
    # RIG PROPS
    main_armature: PointerProperty(
        name="Main Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
        options=set(),
    )
    support_armature_a: PointerProperty(
        name="Support Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
        options=set(),
    )
    support_armature_a_parent_bone : StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the root bone of this support armature should join to at export', options=set())

    
    support_armature_b: PointerProperty(
        name="Support Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
        options=set(),
    )
    support_armature_b_parent_bone : StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the root bone of this support armature should join to at export', options=set())

    
    support_armature_c: PointerProperty(
        name="Support Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
        options=set(),
    )
    support_armature_c_parent_bone : StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the root bone of this support armature should join to at export', options=set())
    
    node_usage_physics_control : StringProperty(name="Physics Control", options=set())
    node_usage_camera_control : StringProperty(name="Camera Control", options=set())
    node_usage_origin_marker : StringProperty(name="Origin Marker", options=set())
    node_usage_left_clavicle : StringProperty(name="Left Clavicle", options=set())
    node_usage_left_upperarm : StringProperty(name="Left Upperarm", options=set())
    node_usage_pose_blend_pitch : StringProperty(name="Pose Blend Pitch", options=set())
    node_usage_pose_blend_yaw : StringProperty(name="Pose Blend Yaw", options=set())
    node_usage_pedestal : StringProperty(name="Pedestal", options=set())
    node_usage_pelvis : StringProperty(name="Pelvis", options=set())
    node_usage_left_foot : StringProperty(name="Left Foot", options=set())
    node_usage_right_foot : StringProperty(name="Right Foot", options=set())
    node_usage_damage_root_gut : StringProperty(name="Damage Root Gut", options=set())
    node_usage_damage_root_chest : StringProperty(name="Damage Root Chest", options=set())
    node_usage_damage_root_head : StringProperty(name="Damage Root Head", options=set())
    node_usage_damage_root_left_shoulder : StringProperty(name="Damage RootLeft Shoulder", options=set())
    node_usage_damage_root_left_arm : StringProperty(name="Damage Root Left Arm", options=set())
    node_usage_damage_root_left_leg : StringProperty(name="Damage Root Left Leg", options=set())
    node_usage_damage_root_left_foot : StringProperty(name="Damage Root Left Foot", options=set())
    node_usage_damage_root_right_shoulder : StringProperty(name="Damage Root Right Shoulder", options=set())
    node_usage_damage_root_right_arm : StringProperty(name="Damage Root Right Arm", options=set())
    node_usage_damage_root_right_leg : StringProperty(name="Damage Root Right Leg", options=set())
    node_usage_damage_root_right_foot : StringProperty(name="Damage Root Right Foot", options=set())
    node_usage_left_hand : StringProperty(name="Left Hand", options=set())
    node_usage_right_hand : StringProperty(name="Right Hand", options=set())
    node_usage_weapon_ik : StringProperty(name="Weapon IK", options=set())
    
    control_pedestal: StringProperty(name='Pedestal Control', options=set())
    control_aim: StringProperty(name='Aim Control', options=set())
    
    # Scale
    def scale_update(self, context):
        scene_scale = 1
        world_units = self.scale_display == 'world_units'
        match self.scale:
            case 'blender':
                scene_scale = (1 / 3.048) if world_units else 1
            case 'max':
                scene_scale = 0.01 if world_units else 0.03048
            
        start = 0.01 * (1 / scene_scale)
        end = 1000 * (1 / scene_scale)
        for workspace in bpy.data.workspaces:
            for screen in workspace.screens:
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        for space in area.spaces:
                            if space.type == "VIEW_3D":
                                space.clip_start = start
                                space.clip_end = end
        
        if self.scale_display == 'world_units':
            context.scene.unit_settings.system = 'METRIC'
            context.scene.unit_settings.length_unit = 'METERS'
            
        context.scene.unit_settings.scale_length = scene_scale
    
    def scale_items(self, context):
        items = []
        items.append(('blender', 'Blender Scale', "For working at a Blender friendly scale. Scene will be appropriately scaled at export to account for Halo's scale", 'BLENDER', 0))
        items.append(('max', 'Halo Scale', "Scene is exported without scaling. Use this if you're working with imported 3DS Max Files, or legacy assets such as JMS/ASS files which have not been scaled down for Blender", get_icon_id("halo_scale"), 1))
        return items
    
    def scale_display_items(self, context):
        items = []
        unit_length: str = context.scene.unit_settings.length_unit
        items.append(('meters', unit_length.title(), "Meters displayed in Blender are equal to 0.328 in game world units", 'DRIVER_DISTANCE', 0))
        items.append(('world_units', 'World Units', "Meters displayed in Blender are equal to in game world units i.e. 1 Meter = 1 World Unit. Use this when you want the units displayed in blender to match the units shown in Sapien", get_icon_id('wu_scale'), 1))
        return items
    
    scale: EnumProperty(
        name="Scale",
        default=0,
        options=set(),
        description="Select the scaling for this asset. Scale is applied at export to ensure units displayed in Blender match with in game units",
        items=scale_items,
        update=scale_update,
    )
    
    scale_display: EnumProperty(
        name="Scale Display",
        options=set(),
        description="Select whether to display scale as meters or world units",
        items=scale_display_items,
        update=scale_update,
    )
    
    maintain_marker_axis: BoolProperty(
        name="Maintain Marker Axis",
        options=set(),
        default=True,
        description="Maintains the forward direction of markers during scene transform. Don't use this if you're re-importing existing assets and rely on marker positions exactly matching",
    )
    
    export_in_progress: BoolProperty(options=set())
    transforming: BoolProperty(options=set())
        
    def poll_camera_track_camera(self, object: bpy.types.Object):
        return object.type == 'CAMERA'
    
    camera_track_camera: PointerProperty(type=bpy.types.Object, poll=poll_camera_track_camera, options=set())
    
    ik_chains: CollectionProperty(
        type=NWO_IKChain,
    )
    
    ik_chains_active_index: IntProperty(options=set())
    
    object_controls: CollectionProperty(
        type=NWO_ControlObjects,
        options=set(),
    )
    
    object_controls_active_index: IntProperty(options=set())
    
    keyframe_sync_active: BoolProperty(options=set())
    
    default_animation_compression: EnumProperty(
        name="Default Animation Compression",
        description="The default animation the game applies to animations",
        options=set(),
        items=[
            ("Automatic", "Automatic", "Compression is determined by the game during animation import"),
            ("Uncompressed", "Uncompressed", "No compression"),
            ("Medium", "Medium", "Medium compression"),
            ("Rough", "Rough", "Highest level of compression"),
        ]
    )
    
    # def get_parent_animation_graph(self):
    #     asset_graph = get_asset_animation_graph()
    #     if asset_graph:
    #         with AnimationTag(path=asset_graph) as animation:
    #             parent_graph = animation.get_parent_graph()
    #             if parent_graph:
    #                 return parent_graph
    #             else:
    #                 return self.parent_animation_graph_helper
    #     else:
    #         return self.parent_animation_graph_helper
                
    # def set_parent_animation_graph(self, value):
    #     asset_graph = get_asset_animation_graph()
    #     if asset_graph and Path(asset_graph).exists():
    #         with AnimationTag(path=asset_graph) as animation:
    #             animation.set_parent_graph(value)
        
    def parent_animation_clean_tag_path(self, context):
        self["parent_animation_graph"] = clean_tag_path(
            self["parent_animation_graph"],
            "model_animation_graph"
        ).strip('"')
        self.parent_animation_graph_helper = self["parent_animation_graph"]
    
    parent_animation_graph: StringProperty(
        name="Parent Animation Graph",
        description="The parent graph of the animations exported from this scene. Allows your animation graph to use and override animations from the parent",
        update=parent_animation_clean_tag_path,
        # get=get_parent_animation_graph,
        # set=set_parent_animation_graph,
        options=set(),
    )
    
    parent_animation_graph_helper: StringProperty(options=set())
    
    def get_scenario_type(self):
        asset_scenario = get_asset_tag(".scenario")
        if asset_scenario:
            print(asset_scenario)
            with ScenarioTag(path=asset_scenario) as scenario:
                type_value = scenario.tag.SelectField("type").Value
                if type_value > 2:
                    return self.scenario_type_helper
                else:
                    return type_value
        else:
            return self.scenario_type_helper
        
    def set_scenario_type(self, context):
        value = self.scenario_type
        asset_scenario = get_asset_tag(".scenario")
        if asset_scenario:
            with ScenarioTag(path=asset_scenario) as scenario:
                scenario.tag.SelectField("type").Value = value
                scenario.tag_has_changes = True
    
    scenario_type: EnumProperty(
        name="Scenario Type",
        description="Select whether this is a Solo, Multiplayer, or Main Menu scenario",
        # get=get_scenario_type,
        update=set_scenario_type,
        options=set(),
        items=[
            ("solo", "Singleplayer", "For campaign levels, but also valid for Firefight & Spartan Ops scenarios"),
            ("multiplayer", "Multiplayer", "For multiplayer maps"),
            ("main menu", "Main Menu", "For main menu maps"),
        ]
    )
    
    def update_connected_geometry_mesh_type_default_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_default')
    def update_connected_geometry_mesh_type_collision_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_collision')
    def update_connected_geometry_mesh_type_physics_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_physics')
    def update_connected_geometry_mesh_type_object_instance_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_object_instance')
    def update_connected_geometry_mesh_type_structure_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_structure')
    def update_connected_geometry_mesh_type_seam_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_seam')
    def update_connected_geometry_mesh_type_portal_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_portal')
    def update_connected_geometry_mesh_type_water_surface_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_water_surface')
    def update_connected_geometry_mesh_type_poop_vertical_rain_sheet_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_poop_vertical_rain_sheet')
    def update_connected_geometry_mesh_type_planar_fog_volume_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_planar_fog_volume')
    def update_connected_geometry_mesh_type_soft_ceiling_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_soft_ceiling')
    def update_connected_geometry_mesh_type_soft_kill_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_soft_kill')
    def update_connected_geometry_mesh_type_slip_surface_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_slip_surface')
    def update_connected_geometry_mesh_type_water_physics_volume_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_water_physics_volume')
    def update_connected_geometry_mesh_type_lightmap_only_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_lightmap_only')
    def update_connected_geometry_mesh_type_streaming_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_streaming')
    def update_connected_geometry_mesh_type_lightmap_exclude_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_lightmap_exclude')
    def update_connected_geometry_mesh_type_cookie_cutter_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_cookie_cutter')
    def update_connected_geometry_mesh_type_poop_rain_blocker_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_poop_rain_blocker')
    
    def update_connected_geometry_marker_type_model_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_model')
    def update_connected_geometry_marker_type_effects_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_effects')
    def update_connected_geometry_marker_type_garbage_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_garbage')
    def update_connected_geometry_marker_type_hint_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_hint')
    def update_connected_geometry_marker_type_pathfinding_sphere_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_pathfinding_sphere')
    def update_connected_geometry_marker_type_physics_constraint_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_physics_constraint')
    def update_connected_geometry_marker_type_target_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_target')
    def update_connected_geometry_marker_type_game_instance_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_game_instance')
    def update_connected_geometry_marker_type_airprobe_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_airprobe')
    def update_connected_geometry_marker_type_envfx_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_envfx')
    def update_connected_geometry_marker_type_lightCone_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_lightCone')

    def update_connected_geometry_object_type_frame_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_object_type_frame')
    def update_connected_geometry_object_type_light_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_object_type_light')
    
    connected_geometry_mesh_type_default_visible: BoolProperty(default=True, options=set(), name="Default", update=update_connected_geometry_mesh_type_default_visible)
    connected_geometry_mesh_type_collision_visible: BoolProperty(default=True, options=set(), name="Collision", update=update_connected_geometry_mesh_type_collision_visible)
    connected_geometry_mesh_type_physics_visible: BoolProperty(default=True, options=set(), name="Physics", update=update_connected_geometry_mesh_type_physics_visible)
    connected_geometry_mesh_type_object_instance_visible: BoolProperty(default=True, options=set(), name="Object Instance", update=update_connected_geometry_mesh_type_object_instance_visible)
    connected_geometry_mesh_type_structure_visible: BoolProperty(default=True, options=set(), name="Structure", update=update_connected_geometry_mesh_type_structure_visible)
    connected_geometry_mesh_type_seam_visible: BoolProperty(default=True, options=set(), name="Seam", update=update_connected_geometry_mesh_type_seam_visible)
    connected_geometry_mesh_type_portal_visible: BoolProperty(default=True, options=set(), name="Portal", update=update_connected_geometry_mesh_type_portal_visible)
    connected_geometry_mesh_type_water_surface_visible: BoolProperty(default=True, options=set(), name="Water Surface", update=update_connected_geometry_mesh_type_water_surface_visible)
    connected_geometry_mesh_type_poop_vertical_rain_sheet_visible: BoolProperty(default=True, options=set(), name="Rain Sheet", update=update_connected_geometry_mesh_type_poop_vertical_rain_sheet_visible)
    connected_geometry_mesh_type_planar_fog_volume_visible: BoolProperty(default=True, options=set(), name="Fog", update=update_connected_geometry_mesh_type_planar_fog_volume_visible)
    connected_geometry_mesh_type_soft_ceiling_visible: BoolProperty(default=True, options=set(), name="Soft Ceiling", update=update_connected_geometry_mesh_type_soft_ceiling_visible)
    connected_geometry_mesh_type_soft_kill_visible: BoolProperty(default=True, options=set(), name="Soft Kill", update=update_connected_geometry_mesh_type_soft_kill_visible)
    connected_geometry_mesh_type_slip_surface_visible: BoolProperty(default=True, options=set(), name="Slip Surface", update=update_connected_geometry_mesh_type_slip_surface_visible)
    connected_geometry_mesh_type_water_physics_volume_visible: BoolProperty(default=True, options=set(), name="Water Physics", update=update_connected_geometry_mesh_type_water_physics_volume_visible)
    connected_geometry_mesh_type_lightmap_only_visible: BoolProperty(default=True, options=set(), name="Lightmap Only", update=update_connected_geometry_mesh_type_lightmap_only_visible)
    connected_geometry_mesh_type_streaming_visible: BoolProperty(default=True, options=set(), name="Streaming Volume", update=update_connected_geometry_mesh_type_streaming_visible)
    connected_geometry_mesh_type_lightmap_exclude_visible: BoolProperty(default=True, options=set(), name="Lightmap Exclusion Volume", update=update_connected_geometry_mesh_type_lightmap_exclude_visible)
    connected_geometry_mesh_type_cookie_cutter_visible: BoolProperty(default=True, options=set(), name="Cookie Cutter", update=update_connected_geometry_mesh_type_cookie_cutter_visible)
    connected_geometry_mesh_type_poop_rain_blocker_visible: BoolProperty(default=True, options=set(), name="Rain Blocker", update=update_connected_geometry_mesh_type_poop_rain_blocker_visible)
    
    connected_geometry_marker_type_model_visible: BoolProperty(default=True, options=set(), name="Model Marker", update=update_connected_geometry_marker_type_model_visible)
    connected_geometry_marker_type_effects_visible: BoolProperty(default=True, options=set(), name="Effects", update=update_connected_geometry_marker_type_effects_visible)
    connected_geometry_marker_type_garbage_visible: BoolProperty(default=True, options=set(), name="Garbage", update=update_connected_geometry_marker_type_garbage_visible)
    connected_geometry_marker_type_hint_visible: BoolProperty(default=True, options=set(), name="Hint", update=update_connected_geometry_marker_type_hint_visible)
    connected_geometry_marker_type_pathfinding_sphere_visible: BoolProperty(default=True, options=set(), name="Pathfinding Sphere", update=update_connected_geometry_marker_type_pathfinding_sphere_visible)
    connected_geometry_marker_type_physics_constraint_visible: BoolProperty(default=True, options=set(), name="Physics Constraint", update=update_connected_geometry_marker_type_physics_constraint_visible)
    connected_geometry_marker_type_target_visible: BoolProperty(default=True, options=set(), name="Target", update=update_connected_geometry_marker_type_target_visible)
    connected_geometry_marker_type_game_instance_visible: BoolProperty(default=True, options=set(), name="Game Object", update=update_connected_geometry_marker_type_game_instance_visible)
    connected_geometry_marker_type_airprobe_visible: BoolProperty(default=True, options=set(), name="Airpobe", update=update_connected_geometry_marker_type_airprobe_visible)
    connected_geometry_marker_type_envfx_visible: BoolProperty(default=True, options=set(), name="Environment Effect", update=update_connected_geometry_marker_type_envfx_visible)
    connected_geometry_marker_type_lightCone_visible: BoolProperty(default=True, options=set(), name="Lightcone", update=update_connected_geometry_marker_type_lightCone_visible)
    
    connected_geometry_object_type_frame_visible: BoolProperty(default=True, options=set(), name="Frame", update=update_connected_geometry_object_type_frame_visible)
    connected_geometry_object_type_light_visible: BoolProperty(default=True, options=set(), name="Light", update=update_connected_geometry_object_type_light_visible)

    sidecar_path: StringProperty()
    
    def get_asset_name(self):
        if not self.sidecar_path.strip(): return ""
        return Path(self.sidecar_path).parent.name

    asset_name: StringProperty(
        get=get_asset_name,
    )
    
    def get_asset_directory(self):
        if not self.sidecar_path.strip(): return ""
        return str(Path(self.sidecar_path).parent)
    
    asset_directory: StringProperty(
        get=get_asset_directory,
    )
    
    def get_is_valid_asset(self):
        project = get_project(self.scene_project)
        is_valid = bool(project and self.sidecar_path.strip() and Path(project.data_directory, self.sidecar_path).exists())
        return is_valid
    
    is_valid_asset: BoolProperty(
        get=get_is_valid_asset,
    )
    
    particle_uses_custom_points: BoolProperty(
        name="Has Custom Emitter Shape",
        description="Generates a particle_emitter_custom_points tag for this particle model. This can be referenced in an effect tag as a custom emitter shape",
    )