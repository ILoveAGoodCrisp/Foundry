# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

import os
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

from ..icons import get_icon_id
from ..utils.nwo_utils import clean_tag_path, get_asset_path, get_prefs, is_corinth, poll_ui, reset_to_basis, valid_nwo_asset

class NWO_Permutations_ListItems(PropertyGroup):

    def update_name(self, context):
        if self.old != self.name:
            i = int(self.path_from_id().rpartition('[')[2].strip(']'))
            bpy.ops.nwo.permutation_rename(new_name=self.name, index=i)

    old: StringProperty()

    name: StringProperty(
        name="Name",
        update=update_name,
        )

    def update_hidden(self, context):
        bpy.ops.nwo.permutation_hide(entry_name=self.name)

    hidden: BoolProperty(name="Hidden", update=update_hidden,)

    def update_hide_select(self, context):
        bpy.ops.nwo.permutation_hide_select(entry_name=self.name)

    hide_select: BoolProperty(name="Hide Select", update=update_hide_select,)

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

    old: StringProperty()

    name: StringProperty(
        name="Name",
        update=update_name,
        )

    def update_hidden(self, context):
        bpy.ops.nwo.region_hide(entry_name=self.name)

    hidden: BoolProperty(name="Hidden", update=update_hidden,)

    def update_hide_select(self, context):
        bpy.ops.nwo.region_hide_select(entry_name=self.name)

    hide_select: BoolProperty(name="Hide Select", update=update_hide_select,)

    active: BoolProperty(
        name="Active",
        description="If false, this region will not be active in the model tag except if added to a variant",
        default=True,
    )

class NWO_BSP_ListItems(PropertyGroup):
    name: StringProperty(name="BSP Table")

class NWO_GlobalMaterial_ListItems(PropertyGroup):
    name: StringProperty(name="Global Material Table")

def prefab_warning(self, context):
    self.layout.label(text=f"Halo Reach does not support prefab assets")

class NWO_Asset_ListItems(PropertyGroup):
    def GetSharedAssetName(self):
        name = self.shared_asset_path
        name = name.rpartition("\\")[2]
        name = name.rpartition(".sidecar.xml")[0]

        return name

    shared_asset_name: StringProperty(
        get=GetSharedAssetName,
    )

    shared_asset_path: StringProperty()

    shared_asset_types = [
        ("BipedAsset", "Biped", ""),
        ("CrateAsset", "Crate", ""),
        ("CreatureAsset", "Creature", ""),
        ("Device_ControlAsset", "Device Control", ""),
        ("Device_MachineAsset", "Device Machine", ""),
        ("Device_TerminalAsset", "Device Terminal", ""),
        ("Effect_SceneryAsset", "Effect Scenery", ""),
        ("EquipmentAsset", "Equipment", ""),
        ("GiantAsset", "Giant", ""),
        ("SceneryAsset", "Scenery", ""),
        ("VehicleAsset", "Vehicle", ""),
        ("WeaponAsset", "Weapon", ""),
        ("ScenarioAsset", "Scenario", ""),
        ("Decorator_SetAsset", "Decorator Set", ""),
        ("Particle_ModelAsset", "Particle Model", ""),
    ]

    shared_asset_type: EnumProperty(
        name="Type",
        default="BipedAsset",
        options=set(),
        items=shared_asset_types,
    )


class NWO_ScenePropertiesGroup(PropertyGroup):
    # ANIMATION
    def update_active_action_index(self, context):
        if self.active_action_index > -1:
            for ob in bpy.data.objects:
                if ob.animation_data:
                    reset_to_basis(True)
                    ob.animation_data.action = bpy.data.actions[self.active_action_index]

            if get_prefs().sync_timeline_range:
                bpy.ops.nwo.set_timeline('INVOKE_DEFAULT')
            
    def get_active_action_index(self):
        if not bpy.context.object.animation_data.action:
            return -1
        real_action_index = bpy.data.actions.values().index(bpy.context.object.animation_data.action)
        if self.old_active_action_index != real_action_index:
            self.old_active_action_index = real_action_index
            return real_action_index
        else:
            return self.old_active_action_index
    
    def set_active_action_index(self, value):
        bpy.context.object.animation_data.action = bpy.data.actions[value]
        self.old_active_action_index = value
    
    active_action_index: IntProperty(
        update=update_active_action_index,
        get=get_active_action_index,
        set=set_active_action_index,
    )
    
    old_active_action_index: IntProperty()
    
    # MB
    mb_startup: BoolProperty(
        name="ManagedBlam on Startup",
        description="Runs ManagedBlam.dll on Blender startup, this will lock the selected game on startup. Disable and and restart blender if you wish to change the selected game.",
        options=set(),
    )

    shared_assets: CollectionProperty(
        type=NWO_Asset_ListItems,
    )

    shared_assets_index: IntProperty(
        name="Index for Shared Asset",
        default=0,
        min=0,
    )

    def items_mesh_type_ui(self, context):
        """Function to handle context for mesh enum lists"""
        h4 = is_corinth()
        items = []

        if poll_ui("DECORATOR SET"):
            items.append(
                (
                    "_connected_geometry_mesh_type_decorator",
                    "Decorator",
                    "Decorator mesh type. Supports up to 4 level of detail variants",
                    get_icon_id("decorator"),
                    0,
                )
            )
        elif poll_ui(("MODEL", "SKY", "PARTICLE MODEL")):
            items.append(
                (
                    "_connected_geometry_mesh_type_render",
                    "Render",
                    "Render only geometry",
                    get_icon_id("render_geometry"),
                    0,
                )
            )
            if poll_ui("MODEL"):
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
        elif poll_ui("SCENARIO"):
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
        elif poll_ui("PREFAB"):
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
            ob_nwo = ob.nwo

            if ob_nwo.mesh_type_ui == "":
                if self.asset_type == "DECORATOR SET":
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_decorator"
                elif self.asset_type == "SCENARIO":
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_structure"
                elif self.asset_type == "PREFAB":
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_poop"
                else:
                    ob_nwo.mesh_type_ui = "_connected_geometry_mesh_type_render"

    def asset_type_items(self, context):
        items = []
        items.append(("MODEL", "Model", "", get_icon_id("model"), 0))
        items.append(("SCENARIO", "Scenario", "", get_icon_id("scenario"), 1))
        items.append(("SKY", "Sky", "", get_icon_id("sky"), 2))
        items.append(
            ("DECORATOR SET", "Decorator Set", "", get_icon_id("decorator"), 3)
        )
        items.append(
            (
                "PARTICLE MODEL",
                "Particle Model",
                "",
                get_icon_id("particle_model"),
                4,
            )
        )
        items.append(
            (
                "FP ANIMATION",
                "Animation",
                "",
                get_icon_id("animation"),
                5,
            )
        )
        if is_corinth(context):
            items.append(("PREFAB", "Prefab", "", get_icon_id("prefab"), 6))

        return items

    asset_type: EnumProperty(
        name="Asset Type",
        options=set(),
        description="Define the type of asset you are creating",
        items=asset_type_items,
    )

    forward_direction: EnumProperty(
        name="Model Forward",
        options=set(),
        description="Define the forward direction you are using for this model. By default Halo uses X forward. If you model is not x positive select the correct forward direction",
        default="x",
        items=[
            ("x", "X", "Model is facing X positive"),
            ("x-", "-X", "Model is facing X negative"),
            ("y", "Y", "Model is facing Y positive"),
            ("y-", "-Y", "Model is facing Y negative"),
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
        self["template_weapon"] = clean_tag_path(
            self["template_weapon"],
            "weapon"
        ).strip('"')
    
    template_model: StringProperty(
        name="Model Template",
        description="Tag relative path to the model tag to use as a base if this asset does not already have one",
        update=template_model_clean_tag_path,
    )
    template_biped: StringProperty(
        name="Biped Template",
        description="Tag relative path to the biped tag to use as a base if this asset does not already have one",
        update=template_biped_clean_tag_path,
    )
    template_crate: StringProperty(
        name="Crate Template",
        description="Tag relative path to the crate tag to use as a base if this asset does not already have one",
        update=template_crate_clean_tag_path,
    )
    template_creature: StringProperty(
        name="Creature Template",
        description="Tag relative path to the creature tag to use as a base if this asset does not already have one",
        update=template_creature_clean_tag_path,
    )
    template_device_control: StringProperty(
        name="Device Control Template",
        description="Tag relative path to the device_control tag to use as a base if this asset does not already have one",
        update=template_device_control_clean_tag_path,
    )
    template_device_dispenser: StringProperty(
        name="Device Dispenser Template",
        description="Tag relative path to the device_dispenser tag to use as a base if this asset does not already have one",
        update=template_device_dispenser_clean_tag_path,
    )
    template_device_machine: StringProperty(
        name="Device Machine Template",
        description="Tag relative path to the device_machine tag to use as a base if this asset does not already have one",
        update=template_device_machine_clean_tag_path,
    )
    template_device_terminal: StringProperty(
        name="Device Terminal Template",
        description="Tag relative path to the device_terminal tag to use as a base if this asset does not already have one",
        update=template_device_terminal_clean_tag_path,
    )
    template_effect_scenery: StringProperty(
        name="Effect Scenery Template",
        description="Tag relative path to the effect_scenery tag to use as a base if this asset does not already have one",
        update=template_effect_scenery_clean_tag_path,
    )
    template_equipment: StringProperty(
        name="Equipment Template",
        description="Tag relative path to the equipment tag to use as a base if this asset does not already have one",
        update=template_equipment_clean_tag_path,
    )
    template_giant: StringProperty(
        name="Giant Template",
        description="Tag relative path to the giant tag to use as a base if this asset does not already have one",
        update=template_giant_clean_tag_path,
    )
    template_scenery: StringProperty(
        name="Scenery Template",
        description="Tag relative path to the scenery tag to use as a base if this asset does not already have one",
        update=template_scenery_clean_tag_path,
    )
    template_vehicle: StringProperty(
        name="Vehicle Template",
        description="Tag relative path to the vehicle tag to use as a base if this asset does not already have one",
        update=template_vehicle_clean_tag_path,
    )
    template_weapon: StringProperty(
        name="Weapon Template",
        description="Tag relative path to the weapon tag to use as a base if this asset does not already have one",
        update=template_weapon_clean_tag_path,
    )

    light_tools_active: BoolProperty()
    light_tools_pinned: BoolProperty()
    light_tools_expanded: BoolProperty(default=True)

    object_properties_active: BoolProperty()
    object_properties_pinned: BoolProperty()
    object_properties_expanded: BoolProperty(default=True)

    material_properties_active: BoolProperty()
    material_properties_pinned: BoolProperty()
    material_properties_expanded: BoolProperty(default=True)

    animation_properties_active: BoolProperty()
    animation_properties_pinned: BoolProperty()
    animation_properties_expanded: BoolProperty(default=True)

    scene_properties_active: BoolProperty(default=True)
    scene_properties_pinned: BoolProperty()
    scene_properties_expanded: BoolProperty(default=True)

    asset_editor_active: BoolProperty(default=True)
    asset_editor_pinned: BoolProperty()
    asset_editor_expanded: BoolProperty(default=True)

    sets_manager_active: BoolProperty()
    sets_manager_pinned: BoolProperty()
    sets_manager_expanded: BoolProperty(default=True)

    tools_active : BoolProperty()
    tools_pinned: BoolProperty()
    tools_expanded : BoolProperty(default=True)

    help_active : BoolProperty()
    help_pinned: BoolProperty()
    help_expanded : BoolProperty(default=True)

    settings_active : BoolProperty()
    settings_pinned: BoolProperty()
    settings_expanded : BoolProperty(default=True)

    toolbar_expanded : BoolProperty(
        name="Toggle Foundry Toolbar",
        default=True,
    )

    def render_clean_tag_path(self, context):
        self["render_model_path"] = clean_tag_path(
            self["render_model_path"],
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

    render_model_path : StringProperty(
        name="Render Model Override Path",
        description="Path to an existing render model tag, overrides the tag generated by this asset on import",
        update=render_clean_tag_path,
        )
    
    collision_model_path : StringProperty(
        name="Collision Model Override Path",
        description="Path to an existing collision model tag, overrides the tag generated by this asset on import",
        update=collision_clean_tag_path,
        )
    
    physics_model_path : StringProperty(
        name="Physics Model Override Path",
        description="Path to an existing physics model tag, overrides the tag generated by this asset on import",
        update=physics_clean_tag_path,
        )
    
    animation_graph_path : StringProperty(
        name="Animation Graph Override Path",
        description="Path to an existing model animation graph tag, overrides the tag generated by this asset on import. This also ensures that the imported node order for your render model (and collision/physics) matches that of the nodes in the given graph",
        update=animation_clean_tag_path,
        )
    
    fp_model_path : StringProperty(
        name="FP Render Model Path",
        description="",
        update=fp_model_clean_tag_path,
        )
    
    gun_model_path : StringProperty(
        name="Gun Render Model Path",
        description="",
        update=gun_model_clean_tag_path,
        )
    
    instance_proxy_running : BoolProperty()

    shader_sync_active : BoolProperty(
        name="Shader Sync",
        description="Sync's the active material with the corresponding Halo Shader/Material tag. Only active when the material has been marked as linked to game",
        options=set()
    )
    
    material_sync_rate : bpy.props.FloatProperty(
        name="Sync Rate",
        description="How often Halo Material Sync should refresh",
        min=0.001,
        default=0.1,
        max=3,
        subtype='TIME_ABSOLUTE',
    )

    scene_project : StringProperty(
        name="Project",
    )
    
    storage_only: BoolProperty()

    # TABLES

    regions_table: CollectionProperty(type=NWO_Regions_ListItems)
    regions_table_active_index: IntProperty()
    permutations_table: CollectionProperty(type=NWO_Permutations_ListItems)
    permutations_table_active_index: IntProperty()
    bsp_table: CollectionProperty(type=NWO_BSP_ListItems)
    bsp_active_index: IntProperty()
    global_material_table: CollectionProperty(type=NWO_GlobalMaterial_ListItems)
    global_material_active_index: IntProperty()
    
    # Rig Validation
    
    def poll_armature(self, object: bpy.types.Object):
        return object.type == 'ARMATURE' and object not in (self.main_armature, self.support_armature_a, self.support_armature_b, self.support_armature_c)
    
    armature_has_parent: BoolProperty()
    armature_bad_transforms: BoolProperty()
    multiple_root_bones: BoolProperty()
    invalid_root_bone: BoolProperty()
    needs_pose_bones: BoolProperty()
    too_many_bones: BoolProperty()
    bone_names_too_long: BoolProperty()
    pose_bones_bad_transforms: BoolProperty()
    
    # RIG PROPS
    main_armature: PointerProperty(
        name="Main Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
    )
    support_armature_a: PointerProperty(
        name="Support Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
    )
    support_armature_a_parent_bone : StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the child bone should join to at export')
    support_armature_a_child_bone : StringProperty(name='Child Bone', description='Specify the bone from the support armature to join to the parent bone')
    
    support_armature_b: PointerProperty(
        name="Support Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
    )
    support_armature_b_parent_bone : StringProperty(name='Parent Bone')
    support_armature_b_child_bone : StringProperty(name='Child Bone')
    
    support_armature_c: PointerProperty(
        name="Support Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
    )
    support_armature_c_parent_bone : StringProperty(name='Parent Bone')
    support_armature_c_child_bone : StringProperty(name='Child Bone')
    
    node_usage_physics_control : StringProperty(name="Physics Control")
    node_usage_camera_control : StringProperty(name="Camera Control")
    node_usage_origin_marker : StringProperty(name="Origin Marker")
    node_usage_left_clavicle : StringProperty(name="Left Clavicle")
    node_usage_left_upperarm : StringProperty(name="Left Upperarm")
    node_usage_pose_blend_pitch : StringProperty(name="Pose Blend Pitch")
    node_usage_pose_blend_yaw : StringProperty(name="Pose Blend Yaw")
    node_usage_pedestal : StringProperty(name="Pedestal")
    node_usage_pelvis : StringProperty(name="Pelvis")
    node_usage_left_foot : StringProperty(name="Left Foot")
    node_usage_right_foot : StringProperty(name="Right Foot")
    node_usage_damage_root_gut : StringProperty(name="Damage Root Gut")
    node_usage_damage_root_chest : StringProperty(name="Damage Root Chest")
    node_usage_damage_root_head : StringProperty(name="Damage Root Head")
    node_usage_damage_root_left_shoulder : StringProperty(name="Damage RootLeft Shoulder")
    node_usage_damage_root_left_arm : StringProperty(name="Damage Root Left Arm")
    node_usage_damage_root_left_leg : StringProperty(name="Damage Root Left Leg")
    node_usage_damage_root_left_foot : StringProperty(name="Damage Root Left Foot")
    node_usage_damage_root_right_shoulder : StringProperty(name="Damage Root Right Shoulder")
    node_usage_damage_root_right_arm : StringProperty(name="Damage Root Right Arm")
    node_usage_damage_root_right_leg : StringProperty(name="Damage Root Right Leg")
    node_usage_damage_root_right_foot : StringProperty(name="Damage Root Right Foot")
    node_usage_left_hand : StringProperty(name="Left Hand")
    node_usage_right_hand : StringProperty(name="Right Hand")
    node_usage_weapon_ik : StringProperty(name="Weapon IK")
    
    control_pedestal: StringProperty(name='Pedestal Control')
    control_aim: StringProperty(name='Aim Control')
    
    # Scale
    def scale_update(self, context):
        scene_scale = 1
        world_units = self.scale_display == 'halo'
        match self.scale:
            case 'meters':
                scene_scale = 3.048 if world_units else 1
            case 'halo':
                scene_scale = 1 if world_units else 3.048
            case 'legacy':
                scene_scale = 0.01 if world_units else 0.03048
            
        bpy.ops.nwo.set_unit_scale(scale=scene_scale)
        
        if self.scale_display == 'halo':
            context.scene.unit_settings.system = 'METRIC'
            context.scene.unit_settings.length_unit = 'METERS'
    
    def scale_items(self, context):
        items = []
        items.append(('meters', 'Blender', "1 meter in Blender is equal to 1 meter in game", 'BLENDER', 0))
        items.append(('halo', 'Halo', "1 meter in Blender is equal to 1 in game world unit. Use this when you want the units displayed in blender to match the units shown in Sapien", get_icon_id('halo_scale'), 1))
        items.append(('legacy', '3DS Max', "Scene is exported without accounting for Halo scaling. Use this if you're working with imported 3DS Max Files, or legacy assets such as JMS/ASS files which have not been scaled down", get_icon_id("3ds_max"), 2))
        return items
    
    def scale_display_items(self, context):
        items = []
        unit_length: str = context.scene.unit_settings.length_unit
        items.append(('meters', unit_length.title(), "1 meter in Blender is equal to 1 meter in game", 'MOD_LENGTH', 0))
        items.append(('halo', 'World Units', "1 meter in Blender is equal to 1 in game world unit. Use this when you want the units displayed in blender to match the units shown in Sapien", get_icon_id('wu_scale'), 1))
        return items
    
    scale: EnumProperty(
        name="Scale",
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
    
    export_in_progress: BoolProperty()
