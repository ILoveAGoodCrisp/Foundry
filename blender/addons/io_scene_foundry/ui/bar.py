import multiprocessing
from pathlib import Path
import bpy

from ..tools.halo_export import export_quick, export

from .. import managed_blam

from .. import utils
from ..icons import get_icon_id, get_icon_id_in_directory

class NWO_MT_ProjectChooserMenu(bpy.types.Menu):
    bl_label = "Choose Project"
    bl_idname = "NWO_MT_ProjectChooser"

    @classmethod
    def poll(self, context):
        prefs = utils.get_prefs()
        return prefs.projects

    def draw(self, context):
        layout = self.layout
        prefs = utils.get_prefs()
        projects = prefs.projects
        for p in projects:
            name = p.name
            thumbnail = Path(p.project_path, p.image_path)
            if thumbnail.exists():
                icon_id = get_icon_id_in_directory(str(thumbnail))
            elif p.remote_server_name == "bngtoolsql":
                icon_id = get_icon_id("halo_reach")
            elif p.remote_server_name == "metawins":
                icon_id = get_icon_id("halo_4")
            elif p.remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                icon_id = get_icon_id("halo_2amp")
            else:
                icon_id = get_icon_id("tag_test")
            layout.operator("nwo.project_select", text=name, icon_value=icon_id).project_name = name

        if self.bl_idname == "NWO_MT_ProjectChooser":
            layout.operator("nwo.project_add", text="New Project", icon="ADD").set_scene_project = True

class NWO_MT_ProjectChooserMenuDisallowNew(NWO_MT_ProjectChooserMenu):
    bl_idname = "NWO_MT_ProjectChooserDisallowNew"

class NWO_OT_ProjectChooser(bpy.types.Operator):
    bl_label = "Select Project"
    bl_idname = "nwo.project_select"
    bl_description = "Select the project to use for this asset"
    bl_property = "project_name"
    bl_options = set()

    @classmethod
    def poll(self, context):
        prefs = utils.get_prefs()
        return prefs.projects

    project_name : bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        nwo.scene_project = self.project_name
        return {'FINISHED'}
    
class NWO_HaloLauncherExplorerSettings(bpy.types.Panel):
    bl_label = "Explorer Settings"
    bl_idname = "NWO_PT_HaloLauncherExplorerSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

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
        row.prop(scene_nwo_halo_launcher, "explorer_default", expand=True)


class NWO_HaloLauncherGameSettings(bpy.types.Panel):
    bl_label = "Game Settings"
    bl_idname = "NWO_PT_HaloLauncherGameSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

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
        draw_game_launcher_settings(scene_nwo_halo_launcher, col)

def draw_game_launcher_settings(scene_nwo_halo_launcher, col):
    row = col.row()
    row.prop(scene_nwo_halo_launcher, "use_play")
    col.separator()
    col.prop(scene_nwo_halo_launcher, "insertion_point_index")
    col.prop(scene_nwo_halo_launcher, "initial_zone_set")
    if utils.is_corinth():
        col.prop(scene_nwo_halo_launcher, "initial_bsp")
    col.prop(scene_nwo_halo_launcher, "custom_functions")
    
    col.separator()
    col.prop(scene_nwo_halo_launcher, "show_debugging")
    col.separator()

    col.prop(scene_nwo_halo_launcher, "run_game_scripts")
    col.prop(scene_nwo_halo_launcher, "forge")
    col.prop(scene_nwo_halo_launcher, "megalo_variant")
    if utils.is_corinth():
        col.prop(scene_nwo_halo_launcher, "enable_firefight")
        if scene_nwo_halo_launcher.enable_firefight:
            col.prop(scene_nwo_halo_launcher, "firefight_mission")


class NWO_HaloLauncherGamePruneSettings(bpy.types.Panel):
    bl_label = "Pruning"
    bl_idname = "NWO_PT_HaloLauncherGamePruneSettings"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloLauncherGameSettings"
    bl_region_type = "HEADER"

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
        draw_game_launcher_pruning(scene_nwo_halo_launcher, col)
                
def draw_game_launcher_pruning(scene_nwo_halo_launcher, col):
    col.prop(scene_nwo_halo_launcher, "prune_globals")
    col.prop(scene_nwo_halo_launcher, "prune_globals_keep_playable")
    if utils.is_corinth():
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
    col.prop(scene_nwo_halo_launcher, "prune_all_materials_use_gray_shader")
    if utils.is_corinth():
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
    if utils.is_corinth():
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
    col.prop(scene_nwo_halo_launcher, "prune_scenario_for_environment_editing")
    if scene_nwo_halo_launcher.prune_scenario_for_environment_editing:
        col.prop(
            scene_nwo_halo_launcher,
            "prune_scenario_for_environment_editing_keep_cinematics",
        )
        col.prop(
            scene_nwo_halo_launcher,
            "prune_scenario_for_environment_editing_keep_scenery",
        )
        if utils.is_corinth():
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


class NWO_HaloLauncherFoundationSettings(bpy.types.Panel):
    bl_label = "Foundation Settings"
    bl_idname = "NWO_PT_HaloLauncherFoundationSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

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
            if utils.nwo_asset_type() == "model":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_collision_model")
                col.prop(scene_nwo_halo_launcher, "open_physics_model")
                if len(bpy.data.actions) > 0:
                    col.prop(scene_nwo_halo_launcher, "open_model_animation_graph")
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
            elif utils.nwo_asset_type() == "scenario":
                col.prop(scene_nwo_halo_launcher, "open_scenario")
                col.prop(scene_nwo_halo_launcher, "open_scenario_structure_bsp")
                col.prop(scene_nwo_halo_launcher, "open_scenario_lightmap_bsp_data")
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
            elif utils.nwo_asset_type() == "sky":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_scenery")
            elif utils.nwo_asset_type() == "decorator_set":
                col.prop(scene_nwo_halo_launcher, "open_decorator_set")
            elif utils.nwo_asset_type() == "particle_model":
                col.prop(scene_nwo_halo_launcher, "open_particle_model")
            elif utils.nwo_asset_type() == "prefab":
                col.prop(scene_nwo_halo_launcher, "open_prefab")
                col.prop(scene_nwo_halo_launcher, "open_scenario_structure_bsp")
                col.prop(
                    scene_nwo_halo_launcher,
                    "open_scenario_structure_lighting_info",
                )
            elif utils.nwo_asset_type() == "animation":
                col.prop(scene_nwo_halo_launcher, "open_model_animation_graph")
                col.prop(scene_nwo_halo_launcher, "open_frame_event_list")
            elif utils.nwo_asset_type() == "camera_track_set" and scene_nwo_halo_launcher.camera_track_name:
                col.use_property_split = True
                col.prop(scene_nwo_halo_launcher, "camera_track_name", text='Track')
                
class NWO_HaloExportSettings(bpy.types.Panel):
    bl_label = "Quick Export Settings"
    bl_idname = "NWO_PT_HaloExportSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        h4 = utils.is_corinth(context)
        asset_type = scene.nwo.asset_type
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
        if asset_type == 'camera_track_set':
            return
        scenario = asset_type == "scenario"
        render = utils.poll_ui(("model", "sky"))
        if (h4 and render) or scenario:
            if scenario:
                lighting_name = "Light Scenario"
            else:
                lighting_name = "Light Model"

            col.prop(scene_nwo_export, "lightmap_structure", text=lighting_name)
            if scene_nwo_export.lightmap_structure:
                if asset_type == "scenario":
                    if h4:
                        col.prop(scene_nwo_export, "lightmap_quality_h4")
                    else:
                        col.prop(scene_nwo_export, "lightmap_quality")
                    if not scene_nwo_export.lightmap_all_bsps:
                        col.prop(scene_nwo_export, "lightmap_specific_bsp")
                    col.prop(scene_nwo_export, "lightmap_all_bsps")
                    if not h4:
                        col.prop(scene_nwo_export, "lightmap_threads")
                    # if not h4:
                    # NOTE light map regions don't appear to work
                    #     col.prop(scene_nwo_export, "lightmap_region")

class NWO_HaloExportSettingsScope(bpy.types.Panel):
    bl_label = "Scope"
    bl_idname = "NWO_PT_HaloExportSettingsScope"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloExportSettings"
    bl_region_type = "HEADER"

    @classmethod
    def poll(self, context):
        return context.scene.nwo_export.export_gr2_files and utils.poll_ui(('model', 'scenario', 'prefab', 'animation'))

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

        if scene_nwo.asset_type == "model":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")
            col.prop(scene_nwo_export, "export_collision")
            col.prop(scene_nwo_export, "export_physics")
            col.prop(scene_nwo_export, "export_markers")
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "animation":
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "scenario":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_structure")
            col.prop(scene_nwo_export, "export_design", text="Design")
        elif scene_nwo.asset_type != "prefab":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")

        if scene_nwo.asset_type == "scenario":
            col.prop(scene_nwo_export, "export_all_bsps", expand=True)
        if utils.poll_ui(("model", "scenario", "prefab")):
            if scene_nwo.asset_type == "model":
                txt = "Permutations"
            else:
                txt = "Layers"
            col.prop(scene_nwo_export, "export_all_perms", expand=True, text=txt)


class NWO_HaloExportSettingsFlags(bpy.types.Panel):
    bl_label = "Flags"
    bl_idname = "NWO_PT_HaloExportSettingsFlags"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloExportSettings"
    bl_region_type = "HEADER"

    @classmethod
    def poll(self, context):
        return context.scene.nwo_export.export_gr2_files and utils.poll_ui(('model', 'scenario', 'prefab', 'sky', 'particle_model', 'decorator_set', 'animation'))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo = scene.nwo
        scene_nwo_export = scene.nwo_export
        h4 = utils.is_corinth(context)
        scenario = scene_nwo.asset_type == "scenario"
        prefab = scene_nwo.asset_type == "prefab"

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_export, 'triangulate', text="Triangulate")
        col.prop(scene_nwo_export, 'slow_gr2')
        if h4:
            col.prop(scene_nwo_export, "import_force", text="Force full export")
            if scenario or prefab:
                if scenario:
                    col.prop(
                        scene_nwo_export,
                        "import_seam_debug",
                        text="Show more seam debugging info",
                    )
                    col.prop(
                        scene_nwo_export,
                        "import_skip_instances",
                        text="Skip importing instances",
                    )
                col.prop(
                    scene_nwo_export,
                    "import_meta_only",
                    text="Only import structure_meta tag",
                )
                col.prop(
                    scene_nwo_export,
                    "import_lighting",
                    text="Only reimport lighting information",
                )
                col.prop(
                    scene_nwo_export,
                    "import_disable_hulls",
                    text="Skip instance convex hull decomp",
                )
                col.prop(
                    scene_nwo_export,
                    "import_disable_collision",
                    text="Don't generate complex collision",
                )
            else:
                col.prop(
                    scene_nwo_export, "import_no_pca", text="Skip PCA calculations"
                )
                col.prop(
                    scene_nwo_export,
                    "import_force_animations",
                    text="Force import error animations",
                )
        else:
            col.prop(scene_nwo_export, "import_force", text="Force full export")
            # col.prop(scene_nwo_export, "import_verbose", text="Verbose Output")
            col.prop(
                scene_nwo_export,
                "import_suppress_errors",
                text="Don't write errors to VRML",
            )
            if scenario:
                col.prop(
                    scene_nwo_export,
                    "import_seam_debug",
                    text="Show more seam debugging info",
                )
                col.prop(
                    scene_nwo_export,
                    "import_skip_instances",
                    text="Skip importing instances",
                )
                col.prop(
                    scene_nwo_export,
                    "import_decompose_instances",
                    text="Run convex physics decomposition",
                )
            else:
                col.prop(scene_nwo_export, "import_draft", text="Skip PRT generation")


class NWO_HaloExport(bpy.types.Operator):
    bl_idname = "nwo.export_quick"
    bl_label = "Quick Export"
    bl_description = "Exports the current Halo asset and creates tags"

    def execute(self, context):
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        if scene_nwo_export.export_quick and utils.valid_nwo_asset(context):
            return export_quick(bpy.ops.export_scene.nwo)
        else:
            return export(bpy.ops.export_scene.nwo)


class NWO_HaloExportPropertiesGroup(bpy.types.PropertyGroup):
    triangulate: bpy.props.BoolProperty(
        name="Triangulate",
        description="Applies a triangulation modifier to all objects at export if they do not already have one",
        default=False,
        options=set(),
    )
    # fast_animation_export : bpy.props.BoolProperty(
    #     name="Fast Animation Export",
    #     description="Speeds up exports by ignoring everything but the armature during animation exports. Do not use if your animation relies on helper objects. You should ensure animations begin at frame 0 if using this option",
    #     default=False,
    #     options=set(),
    # )
    export_gr2_files: bpy.props.BoolProperty(
        name="Export GR2 Files",
        default=True,
        options=set(),
    )
    slow_gr2: bpy.props.BoolProperty(
        name="Slow GR2 Process",
        description="Runs threads of the the FBX-to-GR2 conversion process one by one, instead of processing them concurrently",
        default=False,
        options=set(),
    )
    # export_hidden: bpy.props.BoolProperty(
    #     name="Hidden",
    #     description="Export visible objects only",
    #     default=True,
    #     options=set(),
    # )
    export_all_bsps: bpy.props.EnumProperty(
        name="BSPs",
        description="Specify whether to export all BSPs, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
        options=set(),
    )
    export_all_perms: bpy.props.EnumProperty(
        name="Perms",
        description="Specify whether to export all permutations, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
        options=set(),
    )
    # export_sidecar_xml: bpy.props.BoolProperty(
    #     name="Build Sidecar",
    #     description="",
    #     default=True,
    #     options=set(),
    # )
    import_to_game: bpy.props.BoolProperty(
        name="Import to Game",
        description="",
        default=True,
        options=set(),
    )
    export_quick: bpy.props.BoolProperty(
        name="Quick Export",
        description="Exports the scene without a file dialog, provided this scene is a Halo asset",
        default=True,
        options=set(),
    )
    import_draft: bpy.props.BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
        options=set(),
    )
    lightmap_structure: bpy.props.BoolProperty(
        name="Burn Lighting",
        default=False,
        options=set(),
    )

    def item_lightmap_quality_h4(self, context):
        items = []
        items.append(
            (
                "__custom__",
                "Custom",
                "Opens a lightmap settings dialog",
            )
        )
        items.append(
            (
                "__asset__",
                "Asset",
                "Uses the asset defined lightmap settings",
            )
        )
        lightmapper_globals_dir = Path(utils.get_tags_path(), "globals", "lightmapper_settings")
        if lightmapper_globals_dir.exists():
            for file in lightmapper_globals_dir.iterdir():
                if file.suffix == ".lightmapper_globals":
                    name = file.with_suffix('').name
                    items.append((name, name.replace('_', ' ').capitalize(), ''))
        return items

    lightmap_quality_h4: bpy.props.EnumProperty(
        name="Quality",
        options=set(),
        items=item_lightmap_quality_h4,
        description="The Lightmap quality you wish to use",
    )

    lightmap_region: bpy.props.StringProperty(
        name="Region",
        description="Lightmap region to use for lightmapping",
        options=set(),
    )
    
    def lightmap_quality_items(self, context: bpy.types.Context) -> list[bpy.types.EnumProperty]:
        items = []
        lightmapper_globals_tag_path = Path(utils.get_tags_path(), r"globals\lightmapper_globals.lightmapper_globals")
        if not lightmapper_globals_tag_path.exists() or not managed_blam.mb_active:
            return [("direct_only", "Direct Only", ""),
                    ("draft", "Draft", ""),
                    ("low", "Low", ""),
                    ("medium", "Medium", ""),
                    ("high", "High", ""),
                    ("super_slow", "Super Slow", ""),
                    ("checkerboard", "Checkboard", ""),
                    ("special_v1", "Special V1", ""),
                    ("special_weekend", "Special Weekend", ""),
                    ]
        
        with managed_blam.Tag(path=lightmapper_globals_tag_path) as lightmapper_globals:
            block_quality_settings = lightmapper_globals.tag.SelectField("Block:quality settings")
            for element in block_quality_settings.Elements:
                name: str = element.Fields[0].GetStringData()
                items.append((name, name.replace('_', ' ').capitalize(), ''))
        
        return items

    lightmap_quality: bpy.props.EnumProperty(
        name="Quality",
        items=lightmap_quality_items,
        options=set(),
        description="The lightmap quality you wish to use. You can change and add to this list by editing your lightmapper globals tag found here:\n\ntags\globals\lightmapper_globals.lightmapper_globals",
    )
    lightmap_all_bsps: bpy.props.BoolProperty(
        name="All BSPs",
        default=True,
        options=set(),
    )
    
    def bsp_items(self, context):
        items = []
        bsps = [region.name for region in context.scene.nwo.regions_table if region.name.lower() != 'shared']
        for bsp in bsps:
            items.append((bsp, bsp, ''))
        
        return items
    
    lightmap_specific_bsp: bpy.props.EnumProperty(
        name="Specific BSP",
        options=set(),
        items=bsp_items,
    )
    
    def get_lightmap_threads(self):
        try:
            cpu_count = multiprocessing.cpu_count()
            if self.get("lightmap_threads", 0):
                if self.lightmap_threads < cpu_count:
                    return self['lightmap_threads']
            return cpu_count
        except:
            return self['lightmap_threads']
    

    def set_lightmap_threads(self, value):
        self['lightmap_threads'] = value
    
    lightmap_threads: bpy.props.IntProperty(
        name="Thread Count",
        description="The number of CPU threads to use when lightmapping",
        get=get_lightmap_threads,
        set=set_lightmap_threads,
        min=1,
        options=set(),
    )
    
    ################################
    # Detailed settings
    ###############################
    export_animations: bpy.props.EnumProperty(
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
    export_skeleton: bpy.props.BoolProperty(
        name="Skeleton",
        description="",
        default=True,
        options=set(),
    )
    export_render: bpy.props.BoolProperty(
        name="Render Models",
        description="",
        default=True,
        options=set(),
    )
    export_collision: bpy.props.BoolProperty(
        name="Collision Models",
        description="",
        default=True,
        options=set(),
    )
    export_physics: bpy.props.BoolProperty(
        name="Physics Models",
        description="",
        default=True,
        options=set(),
    )
    export_markers: bpy.props.BoolProperty(
        name="Markers",
        description="",
        default=True,
        options=set(),
    )
    export_structure: bpy.props.BoolProperty(
        name="Structure",
        description="",
        default=True,
        options=set(),
    )
    export_design: bpy.props.BoolProperty(
        name="Structure Design",
        description="",
        default=True,
        options=set(),
    )
    # use_mesh_modifiers: bpy.props.BoolProperty(
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
    # use_armature_deform_only: bpy.props.BoolProperty(
    #     name="Deform Bones Only",
    #     description="Only export bones with the deform property ticked",
    #     default=True,
    #     options=set(),
    # )
    # meshes_to_empties: bpy.props.BoolProperty(
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
        utils.foundry_output_state = self.show_output

    show_output: bpy.props.BoolProperty(
        name="Toggle Output",
        description="Select whether or not the output console should toggle at export",
        options=set(),
        # get=get_show_output,
        # set=set_show_output,
        update=update_show_output,
    )

    # keep_fbx: bpy.props.BoolProperty(
    #     name="FBX",
    #     description="Keep the source FBX file after GR2 conversion",
    #     default=False,
    #     options=set(),
    # )
    # keep_json: bpy.props.BoolProperty(
    #     name="JSON",
    #     description="Keep the source JSON file after GR2 conversion",
    #     default=False,
    #     options=set(),
    # )

    import_force: bpy.props.BoolProperty(
        name="Force",
        description="Force all files to import even if they haven't changed",
        default=False,
        options=set(),
    )

    import_draft: bpy.props.BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
        options=set(),
    )
    import_seam_debug: bpy.props.BoolProperty(
        name="Seam Debug",
        description="Write extra seam debugging information to the console",
        default=False,
        options=set(),
    )
    import_skip_instances: bpy.props.BoolProperty(
        name="Skip Instances",
        description="Skip importing all instanced geometry",
        default=False,
        options=set(),
    )
    import_decompose_instances: bpy.props.BoolProperty(
        name="Decompose Instances",
        description="Run convex decomposition for instanced geometry physics (very slow)",
        default=False,
        options=set(),
    )
    import_suppress_errors: bpy.props.BoolProperty(
        name="Surpress Errors",
        description="Do not write errors to vrml files",
        default=False,
        options=set(),
    )
    import_lighting: bpy.props.BoolProperty(
        name="Lighting Info Only",
        description="Only the scenario_structure_lighting_info tag will be reimported",
        default=False,
        options=set(),
    )
    import_meta_only: bpy.props.BoolProperty(
        name="Meta Only",
        description="Import only the structure_meta tag",
        default=False,
        options=set(),
    )
    import_disable_hulls: bpy.props.BoolProperty(
        name="Disable Hulls",
        description="Disables the contruction of convex hulls for instance physics and collision",
        default=False,
        options=set(),
    )
    import_disable_collision: bpy.props.BoolProperty(
        name="Disable Collision",
        description="Do not generate complex collision",
        default=False,
        options=set(),
    )
    import_no_pca: bpy.props.BoolProperty(
        name="No PCA",
        description="Skips PCA calculations",
        default=False,
        options=set(),
    )
    import_force_animations: bpy.props.BoolProperty(
        name="Force Animations",
        description="Force import of all animations that had errors during the last import",
        default=False,
        options=set(),
    )
    fix_bone_rotations: bpy.props.BoolProperty(
        name="Fix Bone Rotations",
        description="Sets the rotation of the following bones to match Halo conventions: pedestal, aim_pitch, aim_yaw, gun",
        default=True,
        options=set(),
    )
    
def draw_foundry_nodes_toolbar(self, context):
    #if context.region.alignment == 'RIGHT':
    foundry_nodes_toolbar(self.layout, context)

def foundry_nodes_toolbar(layout, context):
    #layout.label(text=" ")
    row = layout.row()
    export_scene = context.scene.nwo
    icons_only = context.preferences.addons[__package__].preferences.toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not export_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if export_scene.toolbar_expanded:
        error = utils.validate_ek()
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return

def draw_foundry_toolbar(self, context):
    #if context.region.alignment == 'RIGHT':
    foundry_toolbar(self.layout, context)

def foundry_toolbar(layout, context):
    #layout.label(text=" ")
    row = layout.row()
    export_scene = context.scene.nwo
    if export_scene.storage_only:
        row.label(text='Scene is used by Foundry for object storage', icon_value=get_icon_id('foundry'))
        return
    icons_only = utils.get_prefs().toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not export_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if export_scene.toolbar_expanded:
        sub_project = row.row(align=True)
        if managed_blam.mb_active:
            sub_project.enabled = False
        sub_project.menu("NWO_MT_ProjectChooser", text="", icon_value=utils.project_icon(context))
        error = utils.validate_ek()
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            if error.startswith("Tag API"):
                sub_foundry.operator("managed_blam.init", text="Install Tag API")
            sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return
        
        # sub_game_version = row.row(align=True)
        # sub_game_version.label(text="", icon_value=project_game_icon(context))

        sub0 = row.row(align=True)
        if export_scene.is_valid_asset and export_scene.asset_type != 'resource':
            sub0.operator(
                "nwo.export_quick",
                text="" if icons_only else "Export",
                icon_value=get_icon_id("quick_export"),
            )
            sub0.popover(panel="NWO_PT_HaloExportSettings", text="")
        elif export_scene.sidecar_path:
            sub0.operator(
                "nwo.new_asset",
                text=f"Copy {export_scene.asset_name}",
                icon_value=get_icon_id("halo_asset"),
            ) 
        else:
            sub0.operator(
                "nwo.new_asset",
                text=f"New Asset",
                icon_value=get_icon_id("halo_asset"),
            ) 
        sub1 = row.row(align=True)
        sub1.operator(
            "nwo.launch_sapien",
            text="" if icons_only else "Sapien",
            icon_value=get_icon_id("sapien"),
        )
        sub1.operator(
            "nwo.launch_tagtest",
            text="" if icons_only else "Tag Test",
            icon_value=get_icon_id("tag_test"),
        )
        sub1.popover(panel="NWO_PT_HaloLauncherGameSettings", text="")
        sub2 = row.row(align=True)
        sub2.operator(
            "nwo.launch_foundation",
            text="" if icons_only else "Tag Editor",
            icon_value=get_icon_id("foundation"),
        )
        sub2.popover(panel="NWO_PT_HaloLauncherFoundationSettings", text="")
        sub3 = row.row(align=True)
        sub3.operator(
            "nwo.launch_data",
            text="" if icons_only else "Data",
            icon_value=get_icon_id("data"),
        )
        sub3.operator(
            "nwo.launch_tags",
            text="" if icons_only else "Tags",
            icon_value=get_icon_id("tags"),
        )
        sub3.popover(panel="NWO_PT_HaloLauncherExplorerSettings", text="")

        sub_foundry = row.row(align=True)
        sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
        
def menu_func_import(self, context):
    self.layout.operator("nwo.import", text="Halo Foundry Import")