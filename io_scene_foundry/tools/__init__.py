import bpy
from os.path import exists as file_exists
from os.path import join as path_join
import os

from bpy.types import Panel, Operator, PropertyGroup

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty,
)
from io_scene_foundry.icons import get_icon_id

from io_scene_foundry.utils.nwo_utils import (
    bpy_enum,
    clean_tag_path,
    dot_partition,
    get_data_path,
    get_tags_path,
    managed_blam_active,
    not_bungie_game,
    nwo_asset_type,
    valid_nwo_asset,
)
from bpy_extras.object_utils import AddObjectHelper

is_blender_startup = True

#######################################
# NEW TOOL UI

class NWO_FoundryPanel(Panel):
    bl_label = "Foundry"
    bl_idname = "NWO_PT_FoundryPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry2"

#######################################
# ADD MENU TOOLS


class NWO_ScaleModels_Add(Operator, AddObjectHelper):
    """Create a new Halo Scale Model Object"""

    bl_idname = "mesh.add_halo_scale_model"
    bl_label = "Halo Scale Model"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Create a new Halo Scale Model Object"

    game: EnumProperty(
        default="reach",
        name="Game",
        items=[
            ("reach", "Halo Reach", ""),
            ("h4", "Halo 4", ""),
            ("h2a", "Halo 2AMP", ""),
        ],
    )

    unit: EnumProperty(
        default="biped",
        name="Type",
        items=[
            ("biped", "Biped", ""),
            ("vehicle", "Vehicle", ""),
        ],
    )

    biped_model_reach: EnumProperty(
        default="scale_model_spartan",
        name="",
        items=[
            ("scale_model_brute", "Brute", ""),
            ("scale_model_civilian_female", "Civilian Female", ""),
            ("scale_model_civilian_male", "Civilian Male", ""),
            ("scale_model_cortana", "Cortana", ""),
            ("scale_model_bugger", "Drone", ""),
            ("scale_model_elite", "Elite", ""),
            ("scale_model_engineer", "Engineer", ""),
            ("scale_model_grunt", "Grunt", ""),
            ("scale_model_halsey", "Halsey", ""),
            ("scale_model_hunter", "Hunter", ""),
            ("scale_model_jackal", "Jackal", ""),
            ("scale_model_keyes", "Keyes", ""),
            ("scale_model_marine", "Marine", ""),
            ("scale_model_marine_female", "Marine Female", ""),
            ("scale_model_moa", "Moa", ""),
            ("scale_model_monitor", "Monitor", ""),
            ("scale_model_marine_odst", "ODST", ""),
            ("scale_model_rat", "Rat", ""),
            ("scale_model_skirmisher", "Skirmisher", ""),
            ("scale_model_spartan", "Spartan", ""),
        ],
    )

    biped_model_h4: EnumProperty(
        default="scale_model_chiefsolo",
        name="",
        items=[
            ("scale_model_chiefsolo", "Masterchief", ""),
            ("scale_model_chiefmp", "Spartan", ""),
        ],
    )

    biped_model_h2a: EnumProperty(
        default="scale_model_masterchief",
        name="",
        items=[
            ("scale_model_elite", "Elite", ""),
            ("scale_model_masterchief", "Spartan", ""),
            ("scale_model_monitor", "Monitor", ""),
        ],
    )

    vehicle_model_reach: EnumProperty(
        default="scale_model_warthog",
        name="",
        items=[
            ("scale_model_banshee", "Banshee", ""),
            ("scale_model_corvette", "Corvette", ""),
            ("scale_model_cruiser", "Cruiser", ""),
            ("scale_model_cart_electric", "Electric Cart", ""),
            ("scale_model_falcon", "Falcon", ""),
            ("scale_model_forklift", "Forklift", ""),
            ("scale_model_frigate", "Frigate", ""),
            ("scale_model_ghost", "Ghost", ""),
            ("scale_model_lnos", "Long Night of Solace", ""),
            ("scale_model_mongoose", "Mongoose", ""),
            ("scale_model_oni_van", "Oni Van", ""),
            ("scale_model_pelican", "Pelican", ""),
            ("scale_model_phantom", "Phantom", ""),
            ("scale_model_pickup", "Pickup Truck", ""),
            ("scale_model_poa", "Pillar of Autumn", ""),
            ("scale_model_revenant", "Revenant", ""),
            ("scale_model_sabre", "Sabre", ""),
            ("scale_model_scarab", "Scarab", ""),
            ("scale_model_scorpion", "Scorpion", ""),
            ("scale_model_seraph", "Seraph", ""),
            ("scale_model_spirit", "Spirit", ""),
            ("scale_model_super_carrier", "Super Carrier", ""),
            ("scale_model_warthog", "Warthog", ""),
            ("scale_model_wraith", "Wraith", ""),
        ],
    )

    vehicle_model_h4: EnumProperty(
        default="scale_model_mongoose",
        name="",
        items=[
            ("scale_model_banshee", "Banshee", ""),
            ("scale_model_broadsword", "Broadsword", ""),
            ("scale_model_ghost", "Ghost", ""),
            ("scale_model_mantis", "Mantis", ""),
            ("scale_model_mongoose", "Mongoose", ""),
        ],
    )

    vehicle_model_h2a: EnumProperty(
        default="scale_model_banshee",
        name="",
        items=[
            ("scale_model_banshee", "Banshee", ""),
        ],
    )

    def execute(self, context):
        from .scale_models import add_scale_model

        add_scale_model(self, context)
        return {"FINISHED"}

    # def invoke(self, context, event):
    #     wm = context.window_manager
    #     return wm.invoke_props_dialog(self)

    def Check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        row = col.row(align=True)
        row.prop(self, "game", expand=True)
        row = col.row(align=True)
        row = col.row(align=True)
        row.prop(self, "unit", expand=True)
        row = col.row(align=True)
        row = col.row(align=True)
        if self.unit == "biped":
            if self.game == "reach":
                col.prop(self, "biped_model_reach")
            elif self.game == "h4":
                col.prop(self, "biped_model_h4")
            else:
                col.prop(self, "biped_model_h2a")
        else:
            if self.game == "reach":
                col.prop(self, "vehicle_model_reach")
            elif self.game == "h4":
                col.prop(self, "vehicle_model_h4")
            else:
                col.prop(self, "vehicle_model_h2a")


def add_halo_scale_model_button(self, context):
    self.layout.operator(
        NWO_ScaleModels_Add.bl_idname,
        text="Halo Scale Model",
        icon_value=get_icon_id("biped"),
    )


from .halo_join import NWO_JoinHalo


def add_halo_join(self, context):
    self.layout.operator(NWO_JoinHalo.bl_idname, text="Halo Join")


#######################################
# FRAME IDS TOOL
class NWO_SetFrameIDs(Panel):
    bl_label = "Set Frame IDs"
    bl_idname = "NWO_PT_SetFrameIDs"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("frame_id"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_frame_ids = scene.nwo_frame_ids

        row = layout.row()
        row.label(text="Animation Graph Path")
        row = layout.row()
        row.prop(scene_nwo_frame_ids, "anim_tag_path", text="")
        row.scale_x = 0.25
        row.operator("nwo.graph_path")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("nwo.set_frame_ids", text="Set Frame IDs")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("nwo.reset_frame_ids", text="Reset Frame IDs")


class NWO_GraphPath(Operator):
    """Set the path to a model animation graph tag"""

    bl_idname = "nwo.graph_path"
    bl_label = "Find"

    filter_glob: StringProperty(
        default="*.model_*",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="graph_path",
        description="Set the path to the tag",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        context.scene.nwo_frame_ids.anim_tag_path = self.filepath

        return {"FINISHED"}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class NWO_SetFrameIDsOp(Operator):
    """Set frame IDs using the specified animation graph path"""

    bl_idname = "nwo.set_frame_ids"
    bl_label = "Set Frame IDs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo_frame_ids.anim_tag_path) > 0

    def execute(self, context):
        from .set_frame_ids import set_frame_ids

        return set_frame_ids(context, self.report)


class NWO_ResetFrameIDsOp(Operator):
    """Resets the frame IDs to null values"""

    bl_idname = "nwo.reset_frame_ids"
    bl_label = "Reset Frame IDs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .set_frame_ids import reset_frame_ids

        return reset_frame_ids(context, self.report)


class NWO_SetFrameIDsPropertiesGroup(PropertyGroup):
    def graph_clean_tag_path(self, context):
        self["anim_tag_path"] = clean_tag_path(self["anim_tag_path"]).strip(
            '"'
        )

    anim_tag_path: StringProperty(
        name="Path to Animation Tag",
        description="Specify the full or relative path to a model animation graph",
        default="",
        update=graph_clean_tag_path,
    )


#######################################
# HALO MANAGER TOOL

class NWO_HaloLauncherExplorerSettings(Panel):
    bl_label = "Explorer Settings"
    bl_idname = "NWO_PT_HaloLauncherExplorerSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    # @classmethod
    # def poll(cls, context):
    #     return valid_nwo_asset(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "explorer_default", expand=True)


class NWO_HaloLauncherGameSettings(Panel):
    bl_label = "Game Settings"
    bl_idname = "NWO_PT_HaloLauncherGameSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "game_default", expand=True)
        col.separator()
        col.prop(scene_nwo_halo_launcher, "insertion_point_index")
        col.prop(scene_nwo_halo_launcher, "initial_zone_set")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "initial_bsp")
        col.prop(scene_nwo_halo_launcher, "custom_functions")

        col.prop(scene_nwo_halo_launcher, "run_game_scripts")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "enable_firefight")
            if scene_nwo_halo_launcher.enable_firefight:
                col.prop(scene_nwo_halo_launcher, "firefight_mission")


class NWO_HaloLauncherGamePruneSettings(Panel):
    bl_label = "Pruning"
    bl_idname = "NWO_PT_HaloLauncherGamePruneSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "NWO_PT_HaloLauncherGameSettings"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        col.prop(scene_nwo_halo_launcher, "prune_globals")
        col.prop(scene_nwo_halo_launcher, "prune_globals_keep_playable")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "prune_globals_use_empty")
            col.prop(
                scene_nwo_halo_launcher,
                "prune_models_enable_alternate_render_models",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_keep_scriptable_objects",
            )
        col.prop(scene_nwo_halo_launcher, "prune_scenario_all_lightmaps")
        col.prop(
            scene_nwo_halo_launcher, "prune_all_materials_use_gray_shader"
        )
        if not_bungie_game():
            col.prop(
                scene_nwo_halo_launcher,
                "prune_all_materials_use_default_textures",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_all_materials_use_default_textures_fx_textures",
            )
        col.prop(scene_nwo_halo_launcher, "prune_all_material_effects")
        col.prop(scene_nwo_halo_launcher, "prune_all_dialog_sounds")
        col.prop(scene_nwo_halo_launcher, "prune_all_error_geometry")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "prune_facial_animations")
            col.prop(scene_nwo_halo_launcher, "prune_first_person_animations")
            col.prop(scene_nwo_halo_launcher, "prune_low_quality_animations")
            col.prop(scene_nwo_halo_launcher, "prune_use_imposters")
            col.prop(scene_nwo_halo_launcher, "prune_cinematic_effects")
        else:
            col.prop(scene_nwo_halo_launcher, "prune_scenario_force_solo_mode")
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_force_single_bsp_zone_set",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_force_single_bsp_zones",
            )
            col.prop(scene_nwo_halo_launcher, "prune_keep_scripts")
        col.prop(
            scene_nwo_halo_launcher, "prune_scenario_for_environment_editing"
        )
        if scene_nwo_halo_launcher.prune_scenario_for_environment_editing:
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_for_environment_editing_keep_cinematics",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_for_environment_editing_keep_scenery",
            )
            if not_bungie_game():
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_decals",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_crates",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_creatures",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_pathfinding",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_new_decorator_block",
                )
            else:
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_finishing",
                )


class NWO_HaloLauncherFoundationSettings(Panel):
    bl_label = "Foundation Settings"
    bl_idname = "NWO_PT_HaloLauncherFoundationSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    # @classmethod
    # def poll(cls, context):
    #     return valid_nwo_asset(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "foundation_default", expand=True)
        col = layout.column(heading="Open")
        if scene_nwo_halo_launcher.foundation_default == "asset":
            if nwo_asset_type() == "MODEL":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_collision_model")
                col.prop(scene_nwo_halo_launcher, "open_physics_model")
                if len(bpy.data.actions) > 0:
                    col.prop(
                        scene_nwo_halo_launcher, "open_model_animation_graph"
                    )
                    col.prop(scene_nwo_halo_launcher, "open_frame_event_list")
                col.separator()
                if scene.nwo.output_biped:
                    col.prop(scene_nwo_halo_launcher, "open_biped")
                if scene.nwo.output_crate:
                    col.prop(scene_nwo_halo_launcher, "open_crate")
                if scene.nwo.output_creature:
                    col.prop(scene_nwo_halo_launcher, "open_creature")
                if scene.nwo.output_device_control:
                    col.prop(scene_nwo_halo_launcher, "open_device_control")
                if scene.nwo.output_device_dispenser:
                    col.prop(scene_nwo_halo_launcher, "open_device_dispenser")
                if scene.nwo.output_device_machine:
                    col.prop(scene_nwo_halo_launcher, "open_device_machine")
                if scene.nwo.output_device_terminal:
                    col.prop(scene_nwo_halo_launcher, "open_device_terminal")
                if scene.nwo.output_effect_scenery:
                    col.prop(scene_nwo_halo_launcher, "open_effect_scenery")
                if scene.nwo.output_equipment:
                    col.prop(scene_nwo_halo_launcher, "open_equipment")
                if scene.nwo.output_giant:
                    col.prop(scene_nwo_halo_launcher, "open_giant")
                if scene.nwo.output_scenery:
                    col.prop(scene_nwo_halo_launcher, "open_scenery")
                if scene.nwo.output_vehicle:
                    col.prop(scene_nwo_halo_launcher, "open_vehicle")
                if scene.nwo.output_weapon:
                    col.prop(scene_nwo_halo_launcher, "open_weapon")
            elif nwo_asset_type() == "SCENARIO":
                col.prop(scene_nwo_halo_launcher, "open_scenario")
                col.prop(
                    scene_nwo_halo_launcher, "open_scenario_structure_bsp"
                )
                col.prop(
                    scene_nwo_halo_launcher, "open_scenario_lightmap_bsp_data"
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "open_scenario_structure_lighting_info",
                )
                if any(
                    [
                        scene_nwo_halo_launcher.open_scenario_structure_bsp,
                        scene_nwo_halo_launcher.open_scenario_lightmap_bsp_data,
                        scene_nwo_halo_launcher.open_scenario_structure_lighting_info,
                    ]
                ):
                    col.prop(scene_nwo_halo_launcher, "bsp_name")
            elif nwo_asset_type() == "SKY":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_scenery")
            elif nwo_asset_type() == "DECORATOR SET":
                col.prop(scene_nwo_halo_launcher, "open_decorator_set")
            elif nwo_asset_type() == "PARTICLE MODEL":
                col.prop(scene_nwo_halo_launcher, "open_particle_model")
            elif nwo_asset_type() == "PREFAB":
                col.prop(scene_nwo_halo_launcher, "open_prefab")
                col.prop(
                    scene_nwo_halo_launcher, "open_scenario_structure_bsp"
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "open_scenario_structure_lighting_info",
                )
            elif nwo_asset_type() == "FP ANIMATION":
                col.prop(scene_nwo_halo_launcher, "open_model_animation_graph")
                col.prop(scene_nwo_halo_launcher, "open_frame_event_list")


class NWO_HaloLauncher_Foundation(Operator):
    """Launches Foundation"""

    bl_idname = "nwo.launch_foundation"
    bl_label = "Foundation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .halo_launcher import LaunchFoundation

        return LaunchFoundation(context.scene.nwo_halo_launcher, context)


class NWO_HaloLauncher_Data(Operator):
    """Opens the Data Folder"""

    bl_idname = "nwo.launch_data"
    bl_label = "Data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import open_file_explorer

        return open_file_explorer(
            scene_nwo_halo_launcher.sidecar_path,
            scene_nwo_halo_launcher.explorer_default == "asset"
            and valid_nwo_asset(context),
            False,
        )


class NWO_HaloLauncher_Tags(Operator):
    """Opens the Tags Folder"""

    bl_idname = "nwo.launch_tags"
    bl_label = "Tags"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import open_file_explorer

        return open_file_explorer(
            scene_nwo_halo_launcher.sidecar_path,
            scene_nwo_halo_launcher.explorer_default == "asset"
            and valid_nwo_asset(context),
            True,
        )


class NWO_HaloLauncher_Sapien(Operator):
    """Opens Sapien"""

    bl_idname = "nwo.launch_sapien"
    bl_label = "Sapien   "
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.scenario",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="filepath",
        description="Set path for the scenario",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import launch_game

        return launch_game(True, scene_nwo_halo_launcher, self.filepath)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not valid_nwo_asset(context)
            or nwo_asset_type() != "SCENARIO"
        ):
            self.filepath = get_tags_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)


class NWO_HaloLauncher_TagTest(Operator):
    """Opens Tag Test"""

    bl_idname = "nwo.launch_tagtest"
    bl_label = "Tag Test"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.scenario",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="filepath",
        description="Set path for the scenario",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import launch_game

        return launch_game(False, scene_nwo_halo_launcher, self.filepath)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not valid_nwo_asset(context)
            or nwo_asset_type() != "SCENARIO"
        ):
            self.filepath = get_tags_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)


class NWO_HaloLauncherPropertiesGroup(PropertyGroup):
    sidecar_path: StringProperty(
        name="",
        description="",
        default="",
    )
    asset_name: StringProperty(
        name="",
        description="",
        default="",
    )

    explorer_default: EnumProperty(
        name="Folder",
        description="Select whether to open the root data / tags folder or the one for your asset. When no asset is found, defaults to root",
        default="asset",
        options=set(),
        items=[("default", "Default", ""), ("asset", "Asset", "")],
    )

    foundation_default: EnumProperty(
        name="Tags",
        description="Select whether Foundation should open with the last opended windows, or open to the selected asset tags",
        default="asset",
        options=set(),
        items=[
            ("last", "Default", ""),
            ("asset", "Asset", ""),
            ("material", "Materials", ""),
        ],
    )

    game_default: EnumProperty(
        name="Scenario",
        description="Select whether to open Sapien / Tag Test and select a scenario, or open the current scenario asset if it exists",
        default="asset",
        options=set(),
        items=[("default", "Default", ""), ("asset", "Asset", "")],
    )

    open_model: BoolProperty(
        name="Model",
        default=True,
        options=set(),
    )

    open_render_model: BoolProperty(options=set(), name="Render Model")

    open_collision_model: BoolProperty(options=set(), name="Collision Model")

    open_physics_model: BoolProperty(options=set(), name="Physics Model")

    open_model_animation_graph: BoolProperty(
        options=set(), name="Model Animation Graph"
    )

    open_frame_event_list: BoolProperty(options=set(), name="Frame Event List")

    open_biped: BoolProperty(options=set(), name="Biped")

    open_crate: BoolProperty(options=set(), name="Crate")

    open_creature: BoolProperty(options=set(), name="Creature")

    open_device_control: BoolProperty(options=set(), name="Device Control")

    open_device_dispenser: BoolProperty(options=set(), name="Device Dispenser")

    open_device_machine: BoolProperty(options=set(), name="Device Machine")

    open_device_terminal: BoolProperty(options=set(), name="Device Terminal")

    open_effect_scenery: BoolProperty(options=set(), name="Effect Scenery")

    open_equipment: BoolProperty(options=set(), name="Equipment")

    open_giant: BoolProperty(options=set(), name="Giant")

    open_scenery: BoolProperty(options=set(), name="Scenery")

    open_vehicle: BoolProperty(options=set(), name="Vehicle")

    open_weapon: BoolProperty(options=set(), name="Weapon")

    open_scenario: BoolProperty(options=set(), name="Scenario", default=True)

    open_prefab: BoolProperty(options=set(), name="Prefab", default=True)

    open_particle_model: BoolProperty(
        options=set(), name="Particle Model", default=True
    )

    open_decorator_set: BoolProperty(
        options=set(), name="Decorator Set", default=True
    )

    bsp_name: StringProperty(
        options=set(),
        name="BSP Name(s)",
        description="Input the bsps to open. Comma delimited for multiple bsps. Leave blank to open all bsps",
        default="",
    )

    open_scenario_structure_bsp: BoolProperty(
        options=set(),
        name="BSP",
    )

    open_scenario_lightmap_bsp_data: BoolProperty(
        options=set(),
        name="Lightmap Data",
    )

    open_scenario_structure_lighting_info: BoolProperty(
        options=set(),
        name="Lightmap Info",
    )

    ##### game launch #####

    run_game_scripts: BoolProperty(
        options=set(),
        description="Runs all startup & continuous scripts on map load",
        name="Run Game Scripts",
    )

    prune_globals: BoolProperty(
        options=set(),
        description="Strips all player information, global materials, grenades and powerups from the globals tag, as well as interface global tags. Don't use this if you need the game to be playable",
        name="Globals",
    )

    prune_globals_keep_playable: BoolProperty(
        options=set(),
        description="Strips player information (keeping one single player element), global materials, grenades and powerups. Keeps the game playable.",
        name="Globals (Keep Playable)",
    )

    prune_globals_use_empty: BoolProperty(
        options=set(),
        description="Uses global_empty.globals instead of globals.globals",
        name="Globals Use Empty",
    )

    prune_models_enable_alternate_render_models: BoolProperty(
        options=set(),
        description="Allows tag build to use alternative render models specified in the .model",
        name="Allow Alternate Render Models",
    )

    prune_scenario_keep_scriptable_objects: BoolProperty(
        options=set(),
        description="Attempts to run scripts while pruning",
        name="Keep Scriptable Objects",
    )

    prune_scenario_for_environment_editing: BoolProperty(
        options=set(),
        description="Removes everything but the environment: Weapons, vehicles, bipeds, equipment, cinematics, AI, etc",
        name="Prune for Environment Editing",
    )

    prune_scenario_for_environment_editing_keep_cinematics: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of cutscene flags and cinematics",
        name="Keep Cinematics",
    )

    prune_scenario_for_environment_editing_keep_scenery: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of scenery",
        name="Keep Scenery",
    )

    prune_scenario_for_environment_editing_keep_decals: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decals",
        name="Keep Decals",
    )

    prune_scenario_for_environment_editing_keep_crates: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of crates",
        name="Keep Crates",
    )

    prune_scenario_for_environment_editing_keep_creatures: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of creatures",
        name="Keep Creatures",
    )

    prune_scenario_for_environment_editing_keep_pathfinding: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of pathfinding",
        name="Keep Pathfinding",
    )

    prune_scenario_for_environment_editing_keep_new_decorator_block: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decorators",
        name="Keep Decorators",
    )

    prune_scenario_all_lightmaps: BoolProperty(
        options=set(),
        description="Loads the scenario without lightmaps",
        name="Prune Lightmaps",
    )

    prune_all_materials_use_gray_shader: BoolProperty(
        options=set(),
        description="Replaces all shaders in the scene with a gray shader, allowing designers to load larger zone sets (the game looks gray, but without artifacts)",
        name="Use Gray Shader",
    )

    prune_all_materials_use_default_textures: BoolProperty(
        options=set(),
        description="Replaces all material textures in the scene with the material shader's default, allowing designers to load larger zone sets",
        name="Use Default Textures",
    )

    prune_all_materials_use_default_textures_fx_textures: BoolProperty(
        options=set(),
        description="Loads only material textures related to FX, all other material textures will show up as the shader's default",
        name="Include FX materials",
    )

    prune_all_material_effects: BoolProperty(
        options=set(),
        description="Loads the scenario without material effects",
        name="Prune Material Effects",
    )

    prune_all_dialog_sounds: BoolProperty(
        options=set(),
        description="Removes all dialog sounds referenced in the globals tag",
        name="Prune Material Effects",
    )

    prune_all_error_geometry: BoolProperty(
        options=set(),
        description="If you're working on geometry and don't need to see the (40+ MB of) data that gets loaded in tags then you should enable this command",
        name="Prune Error Geometry",
    )

    prune_facial_animations: BoolProperty(
        options=set(),
        description="Skips loading the PCA data for facial animations",
        name="Prune Facial Animations",
    )

    prune_first_person_animations: BoolProperty(
        options=set(),
        description="Skips laoding the first-person animations",
        name="Prune First Person Animations",
    )

    prune_low_quality_animations: BoolProperty(
        options=set(),
        description="Use low-quality animations if they are available",
        name="Use Low Quality Animations",
    )

    prune_use_imposters: BoolProperty(
        options=set(),
        description="Uses imposters if they available",
        name="Use Imposters only",
    )

    prune_cinematic_effects: BoolProperty(
        options=set(),
        description="Skips loading and player cinematic effects",
        name="Prune Cinematic Effects",
    )
    # REACH Only prunes
    prune_scenario_force_solo_mode: BoolProperty(
        options=set(),
        description="Forces the map to be loaded in solo mode even if it is a multiplayer map. The game will look for a solo map spawn point",
        name="Force Solo Mode",
    )

    prune_scenario_for_environment_finishing: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decals, scenery, crates and decorators",
        name="Prune Finishing",
    )

    prune_scenario_force_single_bsp_zone_set: BoolProperty(
        options=set(),
        description="Removes all but the first BSP from the initial zone set. Ensures that the initial zone set will not crash on load due to low memory",
        name="Prune Zone Sets",
    )

    prune_scenario_force_single_bsp_zones: BoolProperty(
        options=set(),
        description="Add single bsp zone sets (for each BSP) to the debug menu",
        name="Single BSP zone sets",
    )

    prune_keep_scripts: BoolProperty(
        options=set(),
        description="Attempts to run scripts while pruning",
        name="Keep Scripts",
    )
    # Other
    enable_firefight: BoolProperty(options=set(), name="Enable Spartan Ops")

    firefight_mission: StringProperty(
        options=set(),
        name="Spartan Ops Mission",
        description="Set the string that matches the spartan ops mission that should be loaded",
        default="",
    )

    insertion_point_index: IntProperty(
        options=set(),
        name="Insertion Point Index",
        default=-1,
        min=-1,
        soft_max=4,
    )

    initial_zone_set: StringProperty(
        options=set(),
        name="Initial Zone Set",
        description="Opens the scenario to the zone set specified. This should match a zone set defined in the .scenario tag",
    )

    initial_bsp: StringProperty(
        options=set(),
        name="Initial BSP",
        description="Opens the scenario to the bsp specified. This should match a bsp name in your blender scene",
    )

    custom_functions: StringProperty(
        options=set(),
        name="Custom",
        description="Name of Blender blender text editor file to get custom init lines from. If no such text exists, instead looks in the root editing kit for an init.txt with this name. If this doesn't exist, then the actual text is used instead",
        default="",
    )


#######################################
# SHADER FINDER TOOL


class NWO_ShaderFinder(Panel):
    bl_label = "Shader Finder"
    bl_idname = "NWO_PT_ShaderFinder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MaterialTools"

    @classmethod
    def poll(cls, context):
        return not not_bungie_game()

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("material_finder"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col = layout.column(heading="Shaders Directory")
        col.prop(scene_nwo_shader_finder, "shaders_dir", text="")
        col = layout.column(heading="Overwrite")
        sub = col.column(align=True)
        sub.prop(
            scene_nwo_shader_finder, "overwrite_existing", text="Existing"
        )
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.shader_finder")


class NWO_MaterialFinder(NWO_ShaderFinder):
    bl_label = "Material Finder"
    bl_idname = "NWO_PT_MaterialFinder"

    @classmethod
    def poll(cls, context):
        return not_bungie_game()


class NWO_ShaderFinder_Find(Operator):
    """Searches the tags folder for shaders (or the specified directory) and applies all that match blender material names"""

    bl_idname = "nwo.shader_finder"
    bl_label = "Update Shader Paths"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder
        from .shader_finder import find_shaders

        return find_shaders(
            bpy.data.materials,
            self.report,
            scene_nwo_shader_finder.shaders_dir,
            scene_nwo_shader_finder.overwrite_existing,
        )


class NWO_HaloShaderFinderPropertiesGroup(PropertyGroup):
    shaders_dir: StringProperty(
        name="Shaders Directory",
        description="Leave blank to search the entire tags folder for shaders or input a directory path to specify the folder (and sub-folders) to search for shaders",
        default="",
    )
    overwrite_existing: BoolProperty(
        name="Overwrite Shader Paths",
        options=set(),
        description="Overwrite material shader paths even if they're not blank",
        default=False,
    )


#######################################
# HALO EXPORT TOOL

class NWO_HaloExportSettings(Panel):
    bl_label = "Quick Export Settings"
    bl_idname = "NWO_PT_HaloExportSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_icon = "EXPORT"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        h4 = context.scene.nwo.game_version in ("h4", "h2a")
        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_export, "export_quick", text="Quick Export")
        col.prop(scene_nwo_export, "show_output", text="Toggle Output")
        col.prop(scene_nwo_export, "export_gr2_files", text="Export Tags")
        # if scene_nwo_export.import_to_game and not not_bungie_game():
        #     col.prop(scene_nwo_export, "import_draft", text="Draft")
        col.prop(scene_nwo_export, "lightmap_structure", text="Run Lightmapper")
        if scene_nwo_export.lightmap_structure:
            if h4:
                col.prop(scene_nwo_export, "lightmap_quality_h4")
            else:
                col.prop(scene_nwo_export, "lightmap_quality")
            if not scene_nwo_export.lightmap_all_bsps:
                col.prop(scene_nwo_export, "lightmap_specific_bsp")
            col.prop(scene_nwo_export, "lightmap_all_bsps")
            if not h4:
                col.prop(scene_nwo_export, "lightmap_region")


class NWO_HaloExportSettingsScope(Panel):
    bl_label = "Scope"
    bl_idname = "NWO_PT_HaloExportSettingsScope"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_icon = "EXPORT"
    bl_parent_id = "NWO_PT_HaloExportSettings"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        scene_nwo = scene.nwo

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col = layout.column(heading="Include")
        if scene_nwo.asset_type == "MODEL":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")
            col.prop(scene_nwo_export, "export_collision")
            col.prop(scene_nwo_export, "export_physics")
            col.prop(scene_nwo_export, "export_markers")
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "FP ANIMATION":
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "SCENARIO":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_structure")
            col.prop(scene_nwo_export, "export_design", text="Design")
        elif scene_nwo.asset_type != "PREFAB":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")
        if scene_nwo_export.export_gr2_files:
            if scene_nwo.asset_type == "SCENARIO":
                col.prop(scene_nwo_export, "export_all_bsps", expand=True)
            if scene_nwo.asset_type in (("MODEL", "SCENARIO", "PREFAB")):
                if scene_nwo.asset_type == "MODEL":
                    txt = "Permutations"
                else:
                    txt = "Subgroup"
                col.prop(scene_nwo_export, "export_all_perms", expand=True, text=txt)


class NWO_HaloExport(Operator):
    """Runs the GR2 exporter immediately, using the settings definied in quick export settings"""
    bl_idname = "nwo.export_quick"
    bl_label = "Quick Export"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .halo_export import export_quick, export

        scene = context.scene
        scene_nwo_export = scene.nwo_export
        if scene_nwo_export.export_quick and valid_nwo_asset(context):
            return export_quick(
                bpy.ops.export_scene.nwo,
                self.report,
                scene_nwo_export.export_gr2_files,
                scene_nwo_export.export_all_bsps,
                scene_nwo_export.export_all_perms,
                scene_nwo_export.import_to_game,
                scene_nwo_export.import_draft,
                scene_nwo_export.lightmap_structure,
                scene_nwo_export.lightmap_quality_h4,
                scene_nwo_export.lightmap_region,
                scene_nwo_export.lightmap_quality,
                scene_nwo_export.lightmap_specific_bsp,
                scene_nwo_export.lightmap_all_bsps,
                scene_nwo_export.export_animations,
                scene_nwo_export.export_skeleton,
                scene_nwo_export.export_render,
                scene_nwo_export.export_collision,
                scene_nwo_export.export_physics,
                scene_nwo_export.export_markers,
                scene_nwo_export.export_structure,
                scene_nwo_export.export_design,
            )
        else:
            return export(bpy.ops.export_scene.nwo)


class NWO_HaloExportPropertiesGroup(PropertyGroup):
    export_gr2_files: BoolProperty(
        name="Export GR2 Files",
        default=True,
        options=set(),
    )
    # export_hidden: BoolProperty(
    #     name="Hidden",
    #     description="Export visible objects only",
    #     default=True,
    #     options=set(),
    # )
    export_all_bsps: EnumProperty(
        name="BSPs",
        description="Specify whether to export all BSPs, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
        options=set(),
    )
    export_all_perms: EnumProperty(
        name="Perms",
        description="Specify whether to export all permutations, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
        options=set(),
    )
    # export_sidecar_xml: BoolProperty(
    #     name="Build Sidecar",
    #     description="",
    #     default=True,
    #     options=set(),
    # )
    import_to_game: BoolProperty(
        name="Import to Game",
        description="",
        default=True,
        options=set(),
    )
    export_quick: BoolProperty(
        name="Quick Export",
        description="Exports the scene without a file dialog, provided this scene is a Halo asset",
        default=True,
        options=set(),
    )
    import_draft: BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
        options=set(),
    )
    lightmap_structure: BoolProperty(
        name="Run Lightmapper",
        default=False,
        options=set(),
    )

    def item_lightmap_quality_h4(self, context):
        items = []
        items.append(
            (
                "asset",
                "Asset",
                "The user defined lightmap settings. Opens a settings dialog",
                0,
            )
        )
        lightmapper_globals_dir = path_join(
            get_tags_path(), "globals", "lightmapper_settings"
        )
        if file_exists(lightmapper_globals_dir):
            from os import listdir

            index = 1
            for file in listdir(lightmapper_globals_dir):
                if file.endswith(".lightmapper_globals"):
                    file_no_ext = dot_partition(file)
                    items.append(bpy_enum(file_no_ext, index))
                    index += 1
        return items

    lightmap_quality_h4: EnumProperty(
        name="Quality",
        options=set(),
        items=item_lightmap_quality_h4,
        description="Define the lightmap quality you wish to use",
    )

    lightmap_region: StringProperty(
        name="Region",
        description="Lightmap region to use for lightmapping",
    )

    lightmap_quality: EnumProperty(
        name="Quality",
        items=(
            ("DIRECT", "Direct", ""),
            ("DRAFT", "Draft", ""),
            ("LOW", "Low", ""),
            ("MEDIUM", "Medium", ""),
            ("HIGH", "High", ""),
            ("SUPER", "Super (very slow)", ""),
        ),
        default="DIRECT",
        options=set(),
        description="Define the lightmap quality you wish to use",
    )
    lightmap_all_bsps: BoolProperty(
        name="All BSPs",
        default=True,
        options=set(),
    )
    lightmap_specific_bsp: StringProperty(
        name="Specific BSP",
        default="",
        options=set(),
    )
    ################################
    # Detailed settings
    ###############################
    export_animations: EnumProperty(
        name="Animations",
        description="",
        default="ALL",
        items=[
            ("ALL", "All", ""),
            ("ACTIVE", "Active", ""),
            ("NONE", "None", ""),
        ],
        options=set(),
    )
    export_skeleton: BoolProperty(
        name="Skeleton",
        description="",
        default=True,
        options=set(),
    )
    export_render: BoolProperty(
        name="Render Models",
        description="",
        default=True,
        options=set(),
    )
    export_collision: BoolProperty(
        name="Collision Models",
        description="",
        default=True,
        options=set(),
    )
    export_physics: BoolProperty(
        name="Physics Models",
        description="",
        default=True,
        options=set(),
    )
    export_markers: BoolProperty(
        name="Markers",
        description="",
        default=True,
        options=set(),
    )
    export_structure: BoolProperty(
        name="Structure",
        description="",
        default=True,
        options=set(),
    )
    export_design: BoolProperty(
        name="Structure Design",
        description="",
        default=True,
        options=set(),
    )
    # use_mesh_modifiers: BoolProperty(
    #     name="Apply Modifiers",
    #     description="",
    #     default=True,
    #     options=set(),
    # )
    # global_scale: FloatProperty(
    #     name="Scale",
    #     description="",
    #     default=1.0,
    #     options=set(),
    # )
    # use_armature_deform_only: BoolProperty(
    #     name="Deform Bones Only",
    #     description="Only export bones with the deform property ticked",
    #     default=True,
    #     options=set(),
    # )
    # meshes_to_empties: BoolProperty(
    #     name="Markers as Empties",
    #     description="Export all mesh Halo markers as empties. Helps save on export / import time and file size",
    #     default=True,
    #     options=set(),
    # )

    # def get_show_output(self):
    #     global is_blender_startup
    #     if is_blender_startup:
    #         print("Startup check")
    #         is_blender_startup = False
    #         file_path = os.path.join(bpy.app.tempdir, "foundry_output.txt")
    #         if file_exists(file_path):
    #             with open(file_path, "r") as f:
    #                 state = f.read()

    #             if state == "True":
    #                 return True
    #             else:
    #                 return False

    #     return self.get("show_output", False)
        
    # def set_show_output(self, value):
    #     self["show_output"] = value

    def update_show_output(self, context):
        file_path = os.path.join(bpy.app.tempdir, "foundry_output.txt")
        if file_exists(file_path):
            with open(file_path, "w") as f:
                f.write(str(self.show_output))

    show_output: BoolProperty(
        name="Toggle Output",
        description="Select whether or not the output console should toggle at export",
        options=set(),
        # get=get_show_output,
        # set=set_show_output,
        update=update_show_output,
    )


    keep_fbx: BoolProperty(
        name="FBX",
        description="Keep the source FBX file after GR2 conversion",
        default=False,
        options=set(),
    )
    keep_json: BoolProperty(
        name="JSON",
        description="Keep the source JSON file after GR2 conversion",
        default=False,
        options=set(),
    )

#######################################
# PROPERTIES MANAGER TOOL


class NWO_PropertiesManager(Panel):
    bl_label = "Halo Object Tools"
    bl_idname = "NWO_PT_PropertiesManager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        layout = self.layout

        # if context.scene.nwo.asset_type == 'SCENARIO':
        #     layout.operator("nwo.auto_seam", icon_value=get_icon_id("seam"))


class NWO_CollectionManager(Panel):
    bl_label = "Collection Creator"
    bl_idname = "NWO_PT_CollectionManager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(
            text="", icon_value=get_icon_id("collection_creator")
        )

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_collection_manager = scene.nwo_collection_manager

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_collection_manager, "collection_name", text="Name")
        col.prop(scene_nwo_collection_manager, "collection_type", text="Type")
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.collection_create")


class NWO_CollectionManager_Create(Operator):
    """Creates a special collection with the specified name and adds all currently selected objects to it"""

    bl_idname = "nwo.collection_create"
    bl_label = "Create New Collection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo_collection_manager = scene.nwo_collection_manager
        return (
            scene_nwo_collection_manager.collection_name != ""
            and not scene_nwo_collection_manager.collection_name.isspace()
        )

    def execute(self, context):
        scene = context.scene
        scene_nwo_collection_manager = scene.nwo_collection_manager
        from .collection_manager import create_collections

        return create_collections(
            context,
            bpy.ops,
            bpy.data,
            scene_nwo_collection_manager.collection_type,
            scene_nwo_collection_manager.collection_name,
        )


class NWO_HaloCollectionManagerPropertiesGroup(PropertyGroup):
    def collection_type_items(self, context):
        items = []
        asset_type = context.scene.nwo.asset_type
        if asset_type in ('SCENARIO', 'PREFAB'):
            items.append(("PERMUTATION", "Subgroup", ""))
            if asset_type == 'SCENARIO':
                items.insert(0, ("BSP", "BSP", ""))
        elif asset_type in ('MODEL', 'SKY'):
            items.append(("REGION", "Region", ""))
            if asset_type == 'MODEL':
                items.insert(0, ("PERMUTATION", "Permutation", ""))

        items.append(("EXCLUDE", "Exclude", ""))

        return items


    collection_type: EnumProperty(
        name="Collection Type",
        options=set(),
        description="Select the collection property you wish to apply to the selected objects",
        items=collection_type_items,
    )
    collection_name: StringProperty(
        name="Collection Name",
        description="Select the collection name you wish to apply to the selected objects",
        default="",
    )
    collection_special: BoolProperty(
        name="",
        description="Enable this property",
        default=False,
    )


class NWO_ArmatureCreator(Panel):
    bl_label = "Rig Creator"
    bl_idname = "NWO_PT_ArmatureCreator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_AnimationTools"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("rig_creator"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_armature_creator = scene.nwo_armature_creator

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(
            scene_nwo_armature_creator,
            "armature_type",
            text="Type",
            expand=True,
        )
        col = layout.column(heading="Include")
        sub = col.column(align=True)
        sub.prop(scene_nwo_armature_creator, "control_rig", text="Control Rig")
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.armature_create")


class NWO_ArmatureCreator_Create(Operator):
    """Creates the specified armature"""

    bl_idname = "nwo.armature_create"
    bl_label = "Create Armature"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        scene_nwo_armature_creator = scene.nwo_armature_creator
        from .armature_creator import ArmatureCreate

        return ArmatureCreate(
            context,
            scene_nwo_armature_creator.armature_type,
            scene_nwo_armature_creator.control_rig,
        )


class NWO_ArmatureCreatorPropertiesGroup(PropertyGroup):
    armature_type: EnumProperty(
        name="Armature Type",
        options=set(),
        description="Creates a Halo armature of the specified type",
        default="PEDESTAL",
        items=[
            ("PEDESTAL", "Pedestal", "Creates a single bone Halo armature"),
            (
                "UNIT",
                "Unit",
                "Creates a rig consisting of a pedestal bone, and a pitch and yaw bone. For bipeds and vehicles",
            ),
        ],
    )
    control_rig: BoolProperty(
        name="Use Control Rig",
        description="If True, adds a control rig to the specified armature",
        default=True,
        options=set(),
    )


class NWO_CopyHaloProps(Panel):
    bl_label = "Copy Halo Properties"
    bl_idname = "NWO_PT_CopyHaloProps"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.scale_y = 1.5
        col.operator("nwo.props_copy")


class NWO_CopyHaloProps_Copy(Operator):
    """Copies all halo properties from the active object to selected objects"""

    bl_idname = "nwo.props_copy"
    bl_label = "Copy Properties"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = (
        "Copy Halo Properties from the active object to selected objects"
    )

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 1

    def execute(self, context):
        from .copy_props import CopyProps

        return CopyProps(
            self.report,
            context.view_layer.objects.active,
            context.selected_objects,
        )


class NWO_AMFHelper(Panel):
    bl_label = "Object Importer"
    bl_idname = "NWO_PT_AMFHelper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("import_helper"))

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.operator("nwo.amf_assign")


class NWO_AMFHelper_Assign(Operator):
    """Sets regions and permutations for all scene objects which use the AMF naming convention [region:permutation]"""

    bl_idname = "nwo.amf_assign"
    bl_label = "Set Regions/Perms"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Sets regions and permutations for all scene objects which use the AMF naming convention [region:permutation]"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        from .amf_helper import amf_assign

        return amf_assign(context, self.report)


class NWO_JMSHelper(Panel):
    bl_label = "JMS Helper"
    bl_idname = "NWO_PT_JMSHelper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    @classmethod
    def poll(cls, context):
        return False

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        game_version = context.scene.nwo.game_version
        if game_version == "reach":
            col.operator("nwo.jms_assign", text="JMS -> Reach Asset")
        elif game_version == "h4":
            col.operator("nwo.jms_assign", text="JMS -> H4 Asset")
        else:
            col.operator("nwo.jms_assign", text="JMS -> H2AMP Asset")


class NWO_JMSHelper_Assign(Operator):
    """Splits the active object into it's face maps and assigns a new name for each new object to match the AMF naming convention, as well as setting the proper region & permutation. Collision and physics prefixes are retained"""

    bl_idname = "nwo.jms_assign"
    bl_label = "JMS -> NWO Asset"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Splits the active object into it's face maps and assigns a new name for each new object to match the AMF naming convention, as well as setting the proper region & permutation. Collision and physics prefixes are retained"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        from .jms_helper import jms_assign

        return jms_assign(context, self.report)
    
class NWO_AMFHelper(Panel):
    bl_label = "Object Importer"
    bl_idname = "NWO_PT_AMFHelper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("import_helper"))

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.operator("nwo.amf_assign")


class NWO_AutoSeam(Operator):
    bl_idname = "nwo.auto_seam"
    bl_label = "Auto Seam"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Automatically adds bsp seams to the blend scene"

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        from .auto_seam import auto_seam
        return auto_seam(context)


class NWO_AnimationTools(Panel):
    bl_label = "Halo Animation Tools"
    bl_idname = "NWO_PT_AnimationTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        layout = self.layout


class NWO_GunRigMaker(Panel):
    bl_label = "Rig gun to FP Arms"
    bl_idname = "NWO_PT_GunRigMaker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_AnimationTools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.operator("nwo.build_rig")


class NWO_GunRigMaker_Start(Operator):
    """Joins a gun armature to an first person armature and builds an appropriate rig. Ensure both the FP and Gun rigs are selected before use"""

    bl_idname = "nwo.build_rig"
    bl_label = "Rig Gun to FP"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Joins a gun armature to an first person armature and builds an appropriate rig. Ensure both the FP and Gun rigs are selected before use"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.object.type == "ARMATURE"
            and context.object.mode == "OBJECT"
            and len(context.selected_objects) > 1
        )

    def execute(self, context):
        from .rig_gun_to_fp import build_rig

        return build_rig(self.report, context.selected_objects)


class NWO_MaterialsManager(Panel):
    bl_label = "Halo Material Tools"
    bl_idname = "NWO_PT_MaterialTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        layout = self.layout


class NWO_BitmapExport(Panel):
    bl_label = "Bitmap Exporter"
    bl_idname = "NWO_PT_BitmapExport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MaterialTools"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("texture_export"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_bitmap_export = scene.nwo_bitmap_export

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.scale_y = 1.5
        col.operator("nwo.export_bitmaps")
        col.separator()
        col = flow.column(heading="Overwrite")
        col.prop(scene_nwo_bitmap_export, "overwrite", text="Existing")
        row = col.row()
        row.prop(scene_nwo_bitmap_export, "bitmaps_selection", expand=True)
        col.prop(scene_nwo_bitmap_export, "export_type")


class NWO_BitmapExport_Export(Operator):
    """Exports TIFFs for the active material and imports them into the game as bitmaps"""

    bl_idname = "nwo.export_bitmaps"
    bl_label = "Export Bitmaps"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Exports TIFFs for the active material and imports them into the game as bitmaps"

    @classmethod
    def poll(cls, context):
        return managed_blam_active() and (
            context.object.active_material
            or context.scene.nwo_bitmap_export.bitmaps_selection == "all"
        )

    def execute(self, context):
        scene = context.scene
        scene_nwo_bitmap_export = scene.nwo_bitmap_export
        from .export_bitmaps import export_bitmaps

        return export_bitmaps(
            self.report,
            context,
            context.object.active_material,
            context.scene.nwo_halo_launcher.sidecar_path,
            scene_nwo_bitmap_export.overwrite,
            scene_nwo_bitmap_export.export_type,
            scene_nwo_bitmap_export.bitmaps_selection,
        )


class NWO_BitmapExportPropertiesGroup(PropertyGroup):
    overwrite: BoolProperty(
        name="Overwrite TIFFs",
        description="Enable to overwrite tiff files already saved to your asset bitmaps directory",
        options=set(),
    )
    export_type: EnumProperty(
        name="Actions",
        default="both",
        description="Choose whether to just export material image textures as tiffs, or just import the existing ones to the game, or both",
        options=set(),
        items=[
            ("both", "Both", ""),
            (
                "export",
                "Export TIFF",
                "Export blender image textures to tiff only",
            ),
            (
                "import",
                "Make Tags",
                "Import the tiff to the game as a bitmap tag only",
            ),
        ],
    )
    bitmaps_selection: EnumProperty(
        name="Selection",
        default="active",
        description="Choose whether to only export textures attached to the active material, or all scene textures",
        options=set(),
        items=[
            ("active", "Active", "Export the active material only"),
            ("all", "All", "Export all blender textures"),
        ],  # ('bake', 'Bake', 'Bakes textures for the currently selected objects and exports the results')]
    )


class NWO_Shader(Panel):
    bl_label = "Shader Exporter"
    bl_idname = "NWO_PT_Shader"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MaterialTools"

    @classmethod
    def poll(cls, context):
        return not not_bungie_game()

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("material_exporter"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nwo_shader_build = scene.nwo_shader_build
        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.scale_y = 1.5
        if not_bungie_game():
            col.operator("nwo.build_shader", text="Build Materials")
        else:
            col.operator("nwo.build_shader", text="Build Shaders")
        col.separator()
        col = flow.column(heading="Update")
        col.prop(nwo_shader_build, "update", text="Existing")
        row = col.row()
        row.prop(nwo_shader_build, "material_selection", expand=True)


class NWO_Material(NWO_Shader):
    bl_label = "Material Exporter"
    bl_idname = "NWO_PT_Material"

    @classmethod
    def poll(cls, context):
        return not_bungie_game()


class NWO_Shader_Build(Operator):
    """Makes a shader"""

    bl_idname = "nwo.build_shader"
    bl_label = "Build Shader"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Builds empty shader tags for blender materials. Requires ManagedBlam to be active"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        nwo_shader_build = scene.nwo_shader_build
        return (
            context.object
            and context.object.type == "MESH"
            and managed_blam_active()
            and (
                nwo_shader_build.material_selection == "all"
                or context.active_object.active_material
            )
        )

    def execute(self, context):
        scene = context.scene
        nwo_shader_build = scene.nwo_shader_build
        from .shader_builder import build_shaders

        return build_shaders(
            context,
            nwo_shader_build.material_selection,
            nwo_shader_build.update,
        )


class NWO_ShaderPropertiesGroup(PropertyGroup):
    update: BoolProperty(
        name="Update",
        description="Enable to overwrite already existing asset shaders",
        options=set(),
    )
    material_selection: EnumProperty(
        name="Selection",
        default="active",
        description="Choose whether to build a shader for the active material, or build shaders for all appropriate materials",
        options=set(),
        items=[
            (
                "active",
                "Active",
                "Build a shader for the active material only",
            ),
            ("all", "All", "Builds shaders for all appropriate materials"),
        ],
    )

def foundry_toolbar(self, context):
    layout = self.layout
    layout.label(text="                 ")
    row = layout.row()
    row.scale_x = 1
    sub0 = row.row(align=True)
    sub0.operator('nwo.export_quick', text='Tag Export', icon_value=get_icon_id("quick_export"))
    sub0.popover(panel="NWO_PT_HaloExportSettings", text="")
    sub1 = row.row(align=True)
    sub1.operator('nwo.launch_sapien', text='Sapien', icon_value=get_icon_id("sapien"))
    sub1.operator('nwo.launch_tagtest', text='Tag Test', icon_value=get_icon_id("tag_test"))
    sub1.popover(panel="NWO_PT_HaloLauncherGameSettings", text="")
    sub2 = row.row(align=True)
    sub2.operator('nwo.launch_foundation', text='Tag Editor', icon_value=get_icon_id("foundation"))
    sub2.popover(panel="NWO_PT_HaloLauncherFoundationSettings", text="")
    sub3 = row.row(align=True)
    sub3.operator('nwo.launch_data', text='Data', icon_value=get_icon_id("data"))
    sub3.operator('nwo.launch_tags', text='Tags', icon_value=get_icon_id("tags"))
    sub3.popover(panel="NWO_PT_HaloLauncherExplorerSettings", text="")

classeshalo = (
    NWO_HaloExport,
    NWO_HaloExportSettings,
    NWO_HaloExportSettingsScope,
    NWO_HaloExportPropertiesGroup,
    NWO_HaloLauncherExplorerSettings,
    NWO_HaloLauncherGameSettings,
    NWO_HaloLauncherGamePruneSettings,
    NWO_HaloLauncherFoundationSettings,
    NWO_HaloLauncher_Foundation,
    NWO_HaloLauncher_Data,
    NWO_HaloLauncher_Tags,
    NWO_HaloLauncher_Sapien,
    NWO_HaloLauncher_TagTest,
    NWO_HaloLauncherPropertiesGroup,
    NWO_PropertiesManager,
    NWO_CollectionManager,
    NWO_CollectionManager_Create,
    NWO_HaloCollectionManagerPropertiesGroup,
    # NWO_CopyHaloProps,
    # NWO_CopyHaloProps_Copy, #unregistered until this operator is fixed
    NWO_AutoSeam,
    NWO_MaterialsManager,
    NWO_MaterialFinder,
    NWO_ShaderFinder,
    NWO_ShaderFinder_Find,
    NWO_HaloShaderFinderPropertiesGroup,
    NWO_GraphPath,
    NWO_SetFrameIDs,
    NWO_SetFrameIDsOp,
    NWO_ResetFrameIDsOp,
    NWO_SetFrameIDsPropertiesGroup,
    NWO_AMFHelper,
    NWO_AMFHelper_Assign,
    NWO_JMSHelper,
    NWO_JMSHelper_Assign,
    NWO_AnimationTools,
    NWO_ArmatureCreator,
    NWO_ArmatureCreator_Create,
    NWO_ArmatureCreatorPropertiesGroup,
    NWO_BitmapExport,
    NWO_BitmapExport_Export,
    NWO_BitmapExportPropertiesGroup,
    NWO_Material,
    NWO_Shader,
    NWO_Shader_Build,
    NWO_ShaderPropertiesGroup,
    NWO_ScaleModels_Add,
    NWO_JoinHalo,
    # NWO_GunRigMaker,
    # NWO_GunRigMaker_Start,
)


def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)

    bpy.types.VIEW3D_MT_editor_menus.append(foundry_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.append(add_halo_scale_model_button)
    bpy.types.VIEW3D_MT_object.append(add_halo_join)
    bpy.types.Scene.nwo_frame_ids = PointerProperty(
        type=NWO_SetFrameIDsPropertiesGroup,
        name="Halo Frame ID Getter",
        description="Gets Frame IDs",
    )
    bpy.types.Scene.nwo_halo_launcher = PointerProperty(
        type=NWO_HaloLauncherPropertiesGroup,
        name="Halo Launcher",
        description="Launches stuff",
    )
    bpy.types.Scene.nwo_shader_finder = PointerProperty(
        type=NWO_HaloShaderFinderPropertiesGroup,
        name="Shader Finder",
        description="Find Shaders",
    )
    bpy.types.Scene.nwo_export = PointerProperty(
        type=NWO_HaloExportPropertiesGroup, name="Halo Export", description=""
    )
    bpy.types.Scene.nwo_collection_manager = PointerProperty(
        type=NWO_HaloCollectionManagerPropertiesGroup,
        name="Collection Manager",
        description="",
    )
    bpy.types.Scene.nwo_armature_creator = PointerProperty(
        type=NWO_ArmatureCreatorPropertiesGroup,
        name="Halo Armature",
        description="",
    )
    bpy.types.Scene.nwo_bitmap_export = PointerProperty(
        type=NWO_BitmapExportPropertiesGroup,
        name="Halo Bitmap Export",
        description="",
    )
    bpy.types.Scene.nwo_shader_build = PointerProperty(
        type=NWO_ShaderPropertiesGroup,
        name="Halo Shader Export",
        description="",
    )


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(add_halo_scale_model_button)
    bpy.types.VIEW3D_MT_object.remove(add_halo_join)
    bpy.types.VIEW3D_MT_editor_menus.remove(foundry_toolbar)
    del bpy.types.Scene.nwo_frame_ids
    del bpy.types.Scene.nwo_halo_launcher
    del bpy.types.Scene.nwo_shader_finder
    del bpy.types.Scene.nwo_export
    del bpy.types.Scene.nwo_collection_manager
    del bpy.types.Scene.nwo_armature_creator
    del bpy.types.Scene.nwo_bitmap_export
    del bpy.types.Scene.nwo_shader_build
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)
