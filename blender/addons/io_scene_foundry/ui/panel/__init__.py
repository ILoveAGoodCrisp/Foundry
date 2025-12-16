'''UI for the main Foundry panel'''
from pathlib import Path
import webbrowser

from ...icons import get_icon_id

from ... import constants
from ... import utils
import bpy

from ...props.object import IgnoreReason

FOUNDRY_DOCS = r"https://c20.reclaimers.net/general/community-tools/foundry"
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry"

BLENDER_TOOLSET = r"https://github.com/General-101/Halo-Asset-Blender-Development-Toolset/releases"
AMF_ADDON = r"https://github.com/Gravemind2401/Reclaimer/blob/master/Reclaimer.Blam/Resources/Blender%20AMF2.py"
RECLAIMER = r"https://github.com/Gravemind2401/Reclaimer/releases"
ANIMATION_REPO = r"https://github.com/77Mynameislol77/HaloAnimationRepository"


from ...managed_blam.connected_material import functions_list
game_functions = {func.name for func in functions_list}
all_change_color_prop_names = ("Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color")
all_change_color_prop_display_names = ("Primary", "Secondary", "Tertiary", "Quaternary")

HOTKEYS = [
    ("show_foundry_panel", "SHIFT+F"),
    ("apply_mesh_type", "CTRL+F"),
    ("apply_marker_type", "ALT+F"),
    ("halo_join", "ALT+J"),
    ("move_to_halo_collection", "ALT+M"),
    ("translate_bone_without_children", "CTRL+SHIFT+G"),
    ("rotate_bone_without_children", "CTRL+SHIFT+R"),
    ("resize_bone_without_children", "CTRL+SHIFT+S"),
]

PANELS_PROPS = [
    "scene_properties",
    "asset_editor",
    "sets_manager",
    "object_properties",
    "material_properties",
    "animation_manager",
    "tools",
    "help",
    "settings"
]

class NWO_FoundryPanelProps(bpy.types.Panel):
    bl_label = "Foundry"
    bl_idname = "NWO_PT_FoundryPanelProps"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    #######################################
    # ADD MENU TOOLS
    
    @classmethod
    def poll(cls, context):
        return utils.get_prefs().projects and utils.get_scene_props().scene_project

    def draw(self, context):
        self.context = context
        layout = self.layout
        self.h4 = utils.is_corinth(context)
        self.scene = context.scene
        self.scene_nwo = utils.get_scene_props()
        self.scene_nwo_export = utils.get_export_props()
        self.asset_type = self.scene_nwo.asset_type
        if self.scene_nwo.instance_proxy_running:    
            box = layout.box()
            ob = context.object
            if ob:
                box.label(text=f"Editing: {ob.name}")
                box2 = box.box()
                box2.label(text="Mesh Properties")
                self.draw_expandable_box(box.box(), self.scene_nwo, "mesh_properties", ob=ob)

            row = box.row()
            row.scale_y = 2
            row.operator("nwo.proxy_instance_cancel", text="Exit Proxy Edit Mode")
            return
        
        row = layout.row(align=True)
        col1 = row.column(align=True)
        col2 = row.column(align=True)

        box = col1.box()
        for p in PANELS_PROPS:
            if p == "help":
                box = col1.box()
            elif p == "animation_manager":
                if not utils.poll_ui(('model', 'animation', 'camera_track_set', 'cinematic')):
                    continue
            elif p in ("material_properties", 'sets_manager'):
                if self.scene_nwo.asset_type in ('camera_track_set', 'animation', 'cinematic', 'single_animation') or (p == "material_properties" and self.scene_nwo.asset_type == "animation"):
                    continue
            elif p == "object_properties":
                if self.scene_nwo.asset_type in ('camera_track_set', 'animation', 'single_animation'):
                    continue
            
            row_icon = box.row(align=True)
            panel_active = getattr(self.scene_nwo, f"{p}_active")
            panel_pinned = getattr(self.scene_nwo, f"{p}_pinned")
            row_icon.scale_x = 1.2
            row_icon.scale_y = 1.2
            row_icon.operator(
                "nwo.panel_set",
                text="",
                icon_value=get_icon_id(f"category_{p}_pinned") if panel_pinned else get_icon_id(f"category_{p}"),
                emboss=panel_active,
                depress=panel_pinned,
            ).panel_str = p

            if panel_active:
                if p == 'animation_manager' and self.asset_type == 'cinematic':
                    panel_display_name = "Cinematic Events"
                else:
                    panel_display_name = f"{p.replace('_', ' ').title()}"
                panel_expanded = getattr(self.scene_nwo, f"{p}_expanded")
                self.box = col2.box()
                row_header = self.box.row(align=True)
                row_header.operator(
                    "nwo.panel_expand",
                    text=panel_display_name,
                    icon="TRIA_DOWN" if panel_expanded else "TRIA_RIGHT",
                    emboss=False,
                ).panel_str = p
                row_header.operator(
                    "nwo.panel_unpin",
                    text="",
                    icon="PINNED" if panel_pinned else "UNPINNED",
                    emboss=False,
                ).panel_str = p

                if panel_expanded:
                    draw_panel = getattr(self, f"draw_{p}")
                    if callable(draw_panel):
                        draw_panel()

    def draw_scene_properties(self):
        box = self.box
        scene = self.scene

        col = box.column()
        row = col.row()
        col.scale_y = 1.5

        col.operator('nwo.scale_scene', text='Transform Scene', icon='MOD_LENGTH')
        col = box.column()
        col.scale_y = 1.25
        col.separator()
        col.label(text="Coordinate System")
        row = col.row()
        row.scale_y = 1.1
        row.prop(self.scene_nwo, 'scale', text='Scale', expand=True)
        row = col.row(heading="Forward")
        row = col.row()
        row.prop(self.scene_nwo, "forward_direction", text="Scene Forward", expand=True)
        row = col.row()
        row.prop(self.scene_nwo, "maintain_marker_axis")
        col.label(text="Units Display")
        row = col.row()
        row.scale_y = 1.1
        row.prop(self.scene_nwo, 'scale_display', text=' ', expand=True)
        if self.scene_nwo.scale_display == 'halo' and scene.unit_settings.length_unit != 'METERS':
            row = col.row()
            row.label(text='World Units only accurate when Unit Length is Meters', icon='ERROR')
        
        col.label(text="Scene Project")
        row = col.row()
        row.scale_y = 1.1
        row.menu("NWO_MT_ProjectChooser", text=self.scene_nwo.scene_project, icon_value=utils.project_icon(bpy.context))
        
        if self.scene_nwo.asset_type == 'scenario':
            col.label(text="BSP Collections")
            row = col.row()
            row.scale_y = 1.1
            row.operator("nwo.file_split", icon='LINKED')
            row.operator("nwo.file_aggregate", icon='UNLINKED')


    def draw_asset_editor(self):
        box = self.box
        nwo = self.scene_nwo
        col = box.column()
        row = col.row()
        row.scale_y = 1.5
        row.prop(nwo, "asset_type", text="")
        col.separator()
        asset_name = nwo.asset_name
        
        row = col.row()
        row.scale_y = 1.5
        if asset_name:
            row.operator("nwo.new_asset", text=f"Copy {asset_name}", icon_value=get_icon_id("halo_asset")) 
            row.operator("nwo.clear_asset", text="", icon='X')
            
        else:
            row.scale_y = 1.5
            row.operator("nwo.new_asset", text="New Asset", icon_value=get_icon_id("halo_asset"))
        
        col.prop(nwo, "is_child_asset", text="Child Asset")
        
        if nwo.is_child_asset:
            col.prop(nwo, "parent_asset")
            col.operator("nwo.open_parent_asset", icon='BLENDER')
            col.prop(nwo, "parent_sidecar")
            if nwo.asset_type == 'single_animation':
                self.draw_rig_ui(self.context, nwo)
                self.draw_single_animation_events(nwo, box)
        elif nwo.asset_type == 'single_animation':
            self.draw_rig_ui(self.context, nwo)
            self.draw_single_animation_events(nwo, box)
        else:
            if nwo.asset_type == 'model':
                self.draw_expandable_box(self.box.box(), nwo, 'output_tags')
                self.draw_expandable_box(self.box.box(), nwo, 'model')
                # self.draw_expandable_box(self.box.box(), nwo, 'model_overrides')
                self.draw_rig_ui(self.context, nwo)
                
            elif nwo.asset_type == 'sky':
                box = self.box.box()
                col = box.column()
                col.use_property_split = True
                col.prop(nwo, "sun_size")
                col.prop(nwo, "sun_as_vmf_light")
                col.separator()
                col.prop(nwo, "sun_bounce_scale")
                col.prop(nwo, "skylight_bounce_scale")
                
            if self.h4 and nwo.asset_type in ('model', 'sky'):
                self.draw_expandable_box(self.box.box(), nwo, 'lighting')
            
            if nwo.asset_type == "animation":
                box = self.box.box()
                col = box.column()
                col.use_property_split = True
                col.prop(nwo, "asset_animation_type")
                self.draw_expandable_box(self.box.box(), nwo, 'animation_graph')
                self.draw_rig_ui(self.context, nwo)
                
            elif nwo.asset_type == "scenario":
                self.draw_expandable_box(self.box.box(), nwo, 'scenario')
                # self.draw_expandable_box(self.box.box(), nwo, 'zone_sets')
                self.draw_expandable_box(self.box.box(), nwo, 'lighting')
                self.draw_expandable_box(self.box.box(), nwo, 'decorators')
                # self.draw_expandable_box(self.box.box(), nwo, 'objects')
                if self.h4:
                    self.draw_expandable_box(self.box.box(), nwo, 'prefabs')
                
            elif nwo.asset_type == 'camera_track_set':
                box = self.box.box()
                col = box.column()
                col.operator('nwo.foundry_import', text="Import Camera Track", icon='IMPORT').scope = 'camera_track'
                col.prop(nwo, 'camera_track_camera', text="Camera")
                
            elif nwo.asset_type == 'particle_model':
                col.prop(nwo, 'particle_uses_custom_points')
                
            elif nwo.asset_type == 'cinematic':
                box = self.box.box()
                box.label(text="Cinematic")
                box.operator("nwo.refresh_cinematic_controls", icon='FILE_REFRESH')
                draw_tag_path(box, nwo, "cinematic_scenario")
                scenario_path = Path(utils.get_tags_path(), utils.relative_path(nwo.cinematic_scenario))
                scenario_exists = scenario_path.exists() and scenario_path.is_absolute() and scenario_path.is_file()
                if scenario_exists:
                    box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Scenario Tag").tag_path = nwo.cinematic_scenario
                col = box.column()
                col.separator()
                row = col.row(align=True)
                row.enabled = scenario_exists
                row.prop(nwo, 'cinematic_zone_set')
                row.operator_menu_enum("nwo.get_zone_sets", "zone_set", icon="DOWNARROW_HLT", text="")
                col.separator()
                box_scene = col.box()
                box_scene.label(text="Cinematic Scenes")
                row = box_scene.row()
                row.template_list(
                    "NWO_UL_CinematicScenes",
                    "",
                    nwo,
                    "cinematic_scenes",
                    nwo,
                    "active_cinematic_scene_index",
                )
                col_cin = row.column(align=True)
                col_cin.operator("nwo.cinematic_scene_new", text="", icon="ADD")
                col_cin.operator("nwo.cinematic_scene_remove", icon="REMOVE", text="")
                col_cin.separator()
                col_cin.operator("nwo.cinematic_scene_move", text="", icon="TRIA_UP").direction = 'up'
                col_cin.operator("nwo.cinematic_scene_move", icon="TRIA_DOWN", text="").direction = 'down'
                col_cin.separator()
                col_cin.operator("nwo.scene_switch", icon="SCENE_DATA", text="")
                col.separator()
                col.label(text="Cinematic Scene Properties")
                col.prop(self.context.scene.nwo, 'cinematic_anchor', text="Anchor") # specifically calling the current scene's nwo props
                col.operator('nwo.cinematic_anchor_offset', icon='PIVOT_CURSOR')
            
            # if nwo.asset_type in {'model', 'sky', 'scenario', 'animation', 'cinematic'}:
            #     self.draw_expandable_box(self.box.box(), nwo, "child_assets", panel_display_name="Child Assets" if nwo.asset_type != 'cinematic' else "Other Cinematic Scenes")
            
    def draw_single_animation_events(self, nwo, box):
        box = box.box()
        row = box.row()
        row.label(text="Animation Events")
        row = box.row()
        rows = 3
        row.template_list(
            "NWO_UL_AnimProps_Events",
            "",
            nwo,
            "animation_events",
            nwo,
            "active_animation_event_index",
            rows=rows,
        )

        col = row.column(align=True)
        col.operator("nwo.single_animation_event_list_add", icon="ADD", text="")
        col.operator("nwo.single_animation_event_list_remove", icon="REMOVE", text="")

        if nwo.animation_events:
            item = nwo.animation_events[nwo.active_animation_event_index]
            # row = layout.row()
            # row.prop(item, "name") # debug only
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            col.use_property_split = True
            col.prop(item, "event_type")
            if item.event_type == '_connected_geometry_animation_event_type_frame':
                row = col.row()
                row.prop(item, "multi_frame", expand=True)
                if item.multi_frame == "range":
                    row = col.row(align=True)
                    row.prop(item, "frame_frame", text="Frame Start")
                    row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                    row = col.row(align=True)
                    row.prop(item, "frame_range", text="Frame End")
                    row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_range"
                else:
                    row = col.row(align=True)
                    row.prop(item, "frame_frame")
                    row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                    
                col.prop(item, "frame_name", text="Event")
                
                
                if item.event_data:
                    box = box.box()
                    row = box.row()
                    row.label(text="Animation Event Data")
                    row = box.row()
                    rows = 3
                    row.template_list(
                        "NWO_UL_AnimProps_EventsData",
                        "",
                        item,
                        "event_data",
                        item,
                        "active_event_data_index",
                        rows=rows,
                    )
                    col = row.column(align=True)
                    col.operator("nwo.add_animation_event_data", icon="ADD", text="")
                    col.operator("nwo.remove_animation_event_data", icon="REMOVE", text="")
                    
                    data = item.event_data[item.active_event_data_index]
                    
                    col = box.column()
                    col.separator()
                    col.use_property_split = True
                    row = col.row()
                    row.use_property_split = False
                    row.prop(data, "data_type", expand=True)
                    col.separator()
                    col.prop(data, "frame_offset")
                    col.separator()
                    if data.data_type == 'DIALOGUE':
                        col.prop(data, "dialogue_event")
                        col.prop(data, "damage_effect_reporting_type")
                    else:
                        if data.data_type == 'EFFECT':
                            draw_tag_path(col, data, "event_effect_tag")
                            col.prop(data, "marker")
                        else:
                            draw_tag_path(col, data, "event_sound_tag")
                            col.prop(data, "marker")
                        col.separator()
                        if self.h4:
                            draw_tag_path(col, data, "event_model")
                            col.prop(data, "variant")
                        col.separator()
                        col.prop(data, "flag_allow_on_player")
                        col.prop(data, "flag_left_arm_only")
                        col.prop(data, "flag_right_arm_only")
                        col.prop(data, "flag_first_person_only")
                        col.prop(data, "flag_third_person_only")
                        col.prop(data, "flag_forward_only")
                        col.prop(data, "flag_reverse_only")
                        col.prop(data, "flag_fp_no_aged_weapons")
                else:
                    box.operator("nwo.add_animation_event_data", icon="ADD", text="Add Event Data")
                
            elif (
                item.event_type
                == "_connected_geometry_animation_event_type_wrinkle_map"
            ):
                row = col.row(align=True)
                col.prop(item, "wrinkle_map_face_region", text="Face Region")
                col.prop(item, "event_value", text="Wrinkle Map Factor")
            elif (
                item.event_type
                == "_connected_geometry_animation_event_type_import"
            ):
                row = col.row(align=True)
                row.prop(item, "frame_frame", text="Frame")
                row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                col.prop(item, "import_name")
            elif item.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                valid_ik_chains = [chain for chain in nwo.ik_chains if chain.start_node and chain.effector_node]
                if not valid_ik_chains:
                    col.label(text='Add IK Chains in the Asset Editor tab', icon='ERROR')
                    return
                col.prop(item, "ik_chain")
                # col.prop(item, "ik_active_tag")
                # col.prop(item, "ik_target_tag")
                col.prop(item, "ik_target_marker", icon_value=get_icon_id('marker'))
                col.prop(item, "ik_target_marker_name_override")
                col.prop(item, "ik_target_usage")
                col.prop(item, 'event_value', text="IK Influence")
                col.prop(item, 'ik_pole_vector')
                # col.prop(item, "ik_proxy_target_id")
                # col.prop(item, "ik_pole_vector_id")
                # col.prop(item, "ik_effector_id")
            elif (
                item.event_type
                == "_connected_geometry_animation_event_type_object_function"
            ):
                col.prop(item, "object_function_name")
                col.prop(item, "event_value", text="Function Value")
            elif (
                item.event_type
                == "_connected_geometry_animation_event_type_import"
            ):
                col.prop(item, "frame_frame")
                col.prop(item, "import_name")
    
    def draw_expandable_box(self, box: bpy.types.UILayout, nwo, name, panel_display_name='', ob=None, material=None):
        if not panel_display_name:
            panel_display_name = f"{name.replace('_', ' ').title()}"
        panel_expanded = getattr(nwo, f"{name}_expanded")
        row_header = box.row(align=True)
        row_header.alignment = 'LEFT'
        row_header.operator(
            "nwo.panel_expand",
            text=panel_display_name,
            icon="TRIA_DOWN" if panel_expanded else "TRIA_RIGHT",
            emboss=False,
        ).panel_str = name

        if panel_expanded:
            draw_panel = getattr(self, f"draw_{name}")
            if callable(draw_panel):
                if ob:
                    draw_panel(box, ob)
                elif material:
                    draw_panel(box, material)
                else:
                    draw_panel(box, nwo)
                    
                return panel_expanded
            
        return False
    
    def draw_scenario(self, box: bpy.types.UILayout, nwo):
        tag_path = utils.get_asset_tag(".scenario")
        if tag_path:
            box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Scenario Tag").tag_path = tag_path
        col = box.column()
        col.use_property_split = True
        draw_tag_path(col, nwo, "template_scenario")
        col.prop(nwo, "scenario_add_globals")
        col.separator()
        col.operator("nwo.new_sky", text="Add New Sky to Scenario", icon_value=get_icon_id('sky'))
        
    def draw_decorators(self, box: bpy.types.UILayout, nwo):
        box_decorators = box.box()
        box_decorators.label(text="Decorators")
        box_decorators.prop(nwo, "decorators_from_blender")
        if self.h4:
            box_decorators.prop(nwo, "decorators_from_blender_child_scenario")
        if not nwo.decorators_from_blender:
            return
        box_decorators.operator("nwo.export_decorators", icon='EXPORT')
        box_decorators.prop(nwo, "decorators_export_on_save")
        
    def draw_lighting(self, box: bpy.types.UILayout, nwo):
        box_lights = box.box()
        box_lights.label(text="Lights")
        scene_nwo_export = self.scene_nwo_export
        _, asset_name = utils.get_asset_info()
        if self.asset_type == 'scenario':
            lighting_name = "Lightmap Scenario"
        else:
            lighting_name = "Lightmap Model"
        
        box_lights.operator("nwo.export_lights", icon='EXPORT')
        box_lights.prop(nwo, "lights_export_on_save")
        box_lights.separator()
        if self.asset_type == 'scenario':
            tag_paths = utils.get_asset_tags(".scenario_structure_lighting_info")
            if tag_paths:
                for path in tag_paths:
                    name = path.with_suffix("").name
                    if name.startswith(asset_name):
                        name = name[len(asset_name) + 1:]
                    box_lights.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text=f"Open {name} Lighting Tag").tag_path = str(path)
        else:
            tag_path = utils.get_asset_tag(".scenario_structure_lighting_info")
            if tag_path:
                box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text=f"Open Lighting Tag").tag_path = tag_path
        
        box_lightmapping = box.box()
        box_lightmapping.label(text="Lightmapping")
        if self.asset_type == "scenario":
            if self.h4:
                box_lightmapping.prop(scene_nwo_export, "lightmap_quality_h4")
            else:
                box_lightmapping.prop(scene_nwo_export, "lightmap_quality")
            if not scene_nwo_export.lightmap_all_bsps:
                box_lightmapping.prop(scene_nwo_export, "lightmap_specific_bsp")
            box_lightmapping.prop(scene_nwo_export, "lightmap_all_bsps")
            if not self.h4:
                box_lightmapping.prop(scene_nwo_export, "lightmap_threads")
                    
        box_lightmapping.operator('nwo.lightmap', text=lighting_name, icon='LIGHT_SUN')
    
    def draw_prefabs(self, box: bpy.types.UILayout, nwo):
        box.operator("nwo.export_prefabs", icon='EXPORT')
        box.prop(nwo, "prefabs_export_on_save")
    
    # def draw_zone_sets(self, box: bpy.types.UILayout, nwo):
    #     row = box.row()
    #     rows = 4
    #     row.template_list(
    #         "NWO_UL_ZoneSets",
    #         "",
    #         nwo,
    #         "zone_sets",
    #         nwo,
    #         "zone_sets_active_index",
    #         rows=rows,
    #     )
    #     col = row.column(align=True)
    #     col.operator("nwo.zone_set_add", text="", icon="ADD")
    #     col.operator("nwo.zone_set_remove", icon="REMOVE", text="")
    #     col.separator()
    #     col.operator("nwo.remove_existing_zone_sets", icon="X", text="")
    #     col.separator()
    #     col.operator("nwo.zone_set_move", text="", icon="TRIA_UP").direction = 'up'
    #     col.operator("nwo.zone_set_move", icon="TRIA_DOWN", text="").direction = 'down'
    #     if not nwo.zone_sets:
    #         return
    #     zone_set = nwo.zone_sets[nwo.zone_sets_active_index]
    #     box.label(text=f"Zone Set BSPs")
    #     if zone_set.name.lower() == "default":
    #         return box.label(text="All BSPs included in Zone Set")
    #     grid = box.grid_flow()
    #     grid.scale_x = 0.8
    #     max_index = 31 if self.h4 else 15
    #     bsps = [region.name for region in nwo.regions_table]
    #     for index, bsp in enumerate(bsps):
    #         if index >= max_index:
    #             break
    #         if bsp.lower() != "shared":
    #             grid.prop(zone_set, f"bsp_{index}", text=bsp)
                
    def draw_child_assets(self, box: bpy.types.UILayout, nwo):
        box.operator("nwo.new_child_asset", text="New Child Asset" if self.asset_type != 'cinematic' else "New Cinematic Scene", icon='NEWFOLDER')
        row = box.row()
        row.template_list(
            "NWO_UL_ChildAsset",
            "",
            nwo,
            "child_assets",
            nwo,
            "active_child_asset_index",
        )
        col = row.column(align=True)
        col.operator("nwo.add_child_asset", text="", icon="ADD")
        col.operator("nwo.remove_child_asset", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.move_child_asset", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.move_child_asset", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.child_assets and nwo.active_child_asset_index > -1:
            row = box.row()
            row.operator("nwo.open_child_asset", icon='BLENDER')
    
    def draw_output_tags(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        if nwo.asset_type == "model":
            col.label(text="Output Tags")
            row = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=True,
                align=True,
            )
            row.scale_x = 0.65
            row.scale_y = 1.3

            row.prop(
                nwo,
                "output_crate",
                # text="",
                icon_value=get_icon_id("crate"),
            )
            row.prop(
                nwo,
                "output_scenery",
                # text="",
                icon_value=get_icon_id("scenery"),
            )
            row.prop(
                nwo,
                "output_effect_scenery",
                text="Effect",
                icon_value=get_icon_id("effect_scenery"),
            )

            row.prop(
                nwo,
                "output_device_control",
                text="Control",
                icon_value=get_icon_id("device_control"),
            )
            row.prop(
                nwo,
                "output_device_machine",
                text="Machine",
                icon_value=get_icon_id("device_machine"),
            )
            row.prop(
                nwo,
                "output_device_terminal",
                text="Terminal",
                icon_value=get_icon_id("device_terminal"),
            )
            if utils.is_corinth(self.context):
                row.prop(
                    nwo,
                    "output_device_dispenser",
                    text="Dispenser",
                    icon_value=get_icon_id("device_dispenser"),
                )

            row.prop(
                nwo,
                "output_biped",
                # text="",
                icon_value=get_icon_id("biped"),
            )
            row.prop(
                nwo,
                "output_creature",
                # text="",
                icon_value=get_icon_id("creature"),
            )
            row.prop(
                nwo,
                "output_giant",
                # text="",
                icon_value=get_icon_id("giant"),
            )

            row.prop(
                nwo,
                "output_vehicle",
                # text="",
                icon_value=get_icon_id("vehicle"),
            )
            row.prop(
                nwo,
                "output_weapon",
                # text="",
                icon_value=get_icon_id("weapon"),
            )
            row.prop(
                nwo,
                "output_equipment",
                # text="",
                icon_value=get_icon_id("equipment"),
            )
            
            col.separator()
            if nwo.output_crate:
                self.draw_expandable_box(col.box(), nwo, 'crate')
            if nwo.output_scenery:
                self.draw_expandable_box(col.box(), nwo, 'scenery')
            if nwo.output_effect_scenery:
                self.draw_expandable_box(col.box(), nwo, 'effect_scenery')
            if nwo.output_device_control:
                self.draw_expandable_box(col.box(), nwo, 'device_control')
            if nwo.output_device_machine:
                self.draw_expandable_box(col.box(), nwo, 'device_machine')
            if nwo.output_device_terminal:
                self.draw_expandable_box(col.box(), nwo, 'device_terminal')
            if utils.is_corinth(self.context) and nwo.output_device_dispenser:
                self.draw_expandable_box(col.box(), nwo, 'device_dispenser')
            if nwo.output_biped:
                self.draw_expandable_box(col.box(), nwo, 'biped')
            if nwo.output_creature:
                self.draw_expandable_box(col.box(), nwo, 'creature')
            if nwo.output_giant:
                self.draw_expandable_box(col.box(), nwo, 'giant')
            if nwo.output_vehicle:
                self.draw_expandable_box(col.box(), nwo, 'vehicle')
            if nwo.output_weapon:
                self.draw_expandable_box(col.box(), nwo, 'weapon')
            if nwo.output_equipment:
                self.draw_expandable_box(col.box(), nwo, 'equipment')
        
    def draw_output_tag(self, box: bpy.types.UILayout, nwo, tag_type: str):
        template_name = f"template_{tag_type}"
        draw_tag_path(box, nwo, template_name)
        if utils.valid_nwo_asset(self.context) and getattr(nwo, template_name):
            box.operator('nwo.load_template', icon='DUPLICATE').tag_type = tag_type
        tag_path = utils.get_asset_tag(tag_type)
        if tag_path:
            box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text=f"Open {tag_type.capitalize()} Tag").tag_path = tag_path
        
    def draw_crate(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'crate')
        
    def draw_scenery(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'scenery')
        
    def draw_crate(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'crate')
        
    def draw_effect_scenery(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag( box, nwo,'effect_scenery')
        
    def draw_device_control(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_control')
        
    def draw_device_machine(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_machine')
        
    def draw_device_terminal(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_terminal')
        
    def draw_device_dispenser(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_dispenser')
        
    def draw_biped(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'biped')
        
    def draw_creature(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'creature')
        
    def draw_giant(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'giant')
        
    def draw_vehicle(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'vehicle')
        
    def draw_weapon(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'weapon')
        box.prop(nwo, "use_as_fp_render_model")
        
    def draw_equipment(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'equipment')
                
    def draw_model(self, box: bpy.types.UILayout, nwo):
        draw_tag_path(box, nwo, "template_model")
        if utils.valid_nwo_asset(self.context) and getattr(nwo, 'template_model'):
            box.operator('nwo.load_template', icon='DUPLICATE').tag_type = 'model'
        tag_path = utils.get_asset_tag(".model")
        if tag_path:
            row = box.row(align=True)
            row.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Model Tag").tag_path = tag_path
        self.draw_expandable_box(box.box(), nwo, 'render_model')
        self.draw_expandable_box(box.box(), nwo, 'collision_model')
        self.draw_expandable_box(box.box(), nwo, 'animation_graph')
        self.draw_expandable_box(box.box(), nwo, 'physics_model')
    
    def draw_render_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        draw_tag_path(col, nwo, "template_render_model")
        tag_path = utils.get_asset_render_model()
        if tag_path:
            col.separator()
            col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Render Model Tag").tag_path = tag_path
    
    def draw_collision_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        draw_tag_path(col, nwo, "template_collision_model")
        tag_path = utils.get_asset_collision_model()
        if tag_path:
            col.separator()
            col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Collision Model Tag").tag_path = tag_path
    
    def draw_animation_graph(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        draw_tag_path(col, nwo, "template_model_animation_graph")
        col.separator()
        draw_tag_path(col, nwo, "parent_animation_graph", set_row_split=True)
        row = col.row()
        row.use_property_split = True
        row.prop(nwo, "default_animation_compression", text="Default Animation Compression")
        row = col.row()
        row.use_property_split = True
        row.prop(nwo, "frame_events_from_blender")
        tag_path = utils.get_asset_animation_graph()
        if tag_path:
            col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Animation Graph Tag").tag_path = tag_path
        frame_events_tag_path = utils.get_asset_tag(".frame_events_list")
        if frame_events_tag_path:
            col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Frame Events List Tag").tag_path = frame_events_tag_path
        self.draw_expandable_box(box.box(), nwo, 'animation_copies')
        # if self.h4:
        #     self.draw_expandable_box(box.box(), nwo, 'animation_composites')

    
    def draw_physics_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        draw_tag_path(col, nwo, "template_physics_model")
        tag_path = utils.get_asset_physics_model()
        if tag_path:
            col.separator()
            col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Physics Model Tag").tag_path = tag_path
    
    # def draw_model_overrides(self, box: bpy.types.UILayout, nwo):
    #     asset_dir, asset_name = utils.get_asset_info()
    #     self_path = str(Path(asset_dir, asset_name))
    #     everything_overidden = nwo.template_render_model and nwo.template_collision_model and nwo.template_model_animation_graph and nwo.template_physics_model
    #     if everything_overidden:
    #         box.alert = True
    #     col = box.column()
    #     row = col.row(align=True)
    #     if nwo.render_model_path and utils.dot_partition(nwo.render_model_path) == self_path:
    #         row.alert = True
    #         row.label(icon='ERROR')
            
    #     row.prop(nwo, "render_model_path", text="Render", icon_value=get_icon_id("tags"))
    #     row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "render_model_path"
    #     row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'render_model_path'
    #     row = col.row(align=True)
    #     row.prop(nwo, "collision_model_path", text="Collision", icon_value=get_icon_id("tags"))
    #     row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "collision_model_path"
    #     row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'collision_model_path'
    #     row = col.row(align=True)
    #     row.prop(nwo, "animation_graph_path", text="Animation", icon_value=get_icon_id("tags"))
    #     row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "animation_graph_path"
    #     row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'animation_graph_path'
    #     row = col.row(align=True)
    #     row.prop(nwo, "physics_model_path", text="Physics", icon_value=get_icon_id("tags"))
    #     row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "physics_model_path"
    #     row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'physics_model_path'
    #     if everything_overidden:
    #         row = col.row(align=True)
    #         row.label(text='All overrides specified', icon='ERROR')
    #         row = col.row(align=True)
    #         row.label(text='Everything exported from this scene will be overwritten')
            
    def draw_model_rig(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.use_property_split = True
        col.prop(nwo, 'main_armature', icon='OUTLINER_OB_ARMATURE')
        # if not nwo.main_armature: return
        # col.separator()
        # arm_count = utils.get_arm_count(self.context)
        # if arm_count > 1 or nwo.support_armature_a:
        #     col.prop(nwo, 'support_armature_a', icon='OUTLINER_OB_ARMATURE')
        #     if nwo.support_armature_a:
        #         row = col.row()
        #         row.prop_search(nwo, 'support_armature_a_parent_bone', nwo.main_armature.data, 'bones')
        #         if not nwo.support_armature_a_parent_bone:
        #             row.operator("nwo.link_armatures", text="", icon='DECORATE_LINKED').support_arm = 0
        #         col.separator()
        # if arm_count > 2 or nwo.support_armature_b:
        #     col.prop(nwo, 'support_armature_b', icon='OUTLINER_OB_ARMATURE')
        #     if nwo.support_armature_b:
        #         row = col.row()
        #         row.prop_search(nwo, 'support_armature_b_parent_bone', nwo.main_armature.data, 'bones')
        #         if not nwo.support_armature_b_parent_bone:
        #             row.operator("nwo.link_armatures", text="", icon='DECORATE_LINKED').support_arm = 1
        # if arm_count > 3 or nwo.support_armature_c:
        #     col.prop(nwo, 'support_armature_c', icon='OUTLINER_OB_ARMATURE')
        #     if nwo.support_armature_c:
        #         row = col.row()
        #         row.prop_search(nwo, 'support_armature_c_parent_bone', nwo.main_armature.data, 'bones')
        #         if not nwo.support_armature_c_parent_bone:
        #             row.operator("nwo.link_armatures", text="", icon='DECORATE_LINKED').support_arm = 2
                
        #col.separator()
                
    # def draw_rig_controls(self, box: bpy.types.UILayout, nwo):
    #     box.use_property_split = True
    #     row = box.row(align=True)
    #     row.prop_search(nwo, 'control_aim', nwo.main_armature.data, 'bones')
    #     if not nwo.control_aim:
    #         row.operator('nwo.add_pose_bones', text='', icon='ADD').skip_invoke = True
    
    def draw_rig_usages(self, box, nwo):
        box.use_property_split = True
        col = box.column()
        if not nwo.main_armature:
            return col.label(text="Set Main Armature to use")
        col.prop_search(nwo, "node_usage_pedestal", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_pose_blend_pitch", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_pose_blend_yaw", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_physics_control", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_camera_control", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_origin_marker", nwo.main_armature.data, "bones")
        if self.h4:
            col.prop_search(nwo, "node_usage_weapon_ik", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_pelvis", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_left_clavicle", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_left_upperarm", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_left_foot", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_right_foot", nwo.main_armature.data, "bones")
        if self.h4:
            col.prop_search(nwo, "node_usage_left_hand", nwo.main_armature.data, "bones")
            col.prop_search(nwo, "node_usage_right_hand", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_gut", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_chest", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_head", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_shoulder", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_arm", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_leg", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_foot", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_shoulder", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_arm", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_leg", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_foot", nwo.main_armature.data, "bones")
        
    def draw_ik_chains(self, box, nwo):
        if not nwo.ik_chains:
            box.operator("nwo.add_ik_chain", text="Add Game IK Chain", icon_value=get_icon_id("ik_chain"))
            return
        row = box.row()
        row.template_list(
            "NWO_UL_IKChain",
            "",
            nwo,
            "ik_chains",
            nwo,
            "ik_chains_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.add_ik_chain", text="", icon="ADD")
        col.operator("nwo.remove_ik_chain", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.move_ik_chain", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.move_ik_chain", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.ik_chains and nwo.ik_chains_active_index > -1:
            chain = nwo.ik_chains[nwo.ik_chains_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop_search(chain, 'start_node', nwo.main_armature.data, 'bones', text='Start Bone')
            col.prop_search(chain, 'effector_node', nwo.main_armature.data, 'bones', text='Effector Bone')
            
    def draw_animation_copies(self, box, nwo):
        if not nwo.animation_copies:
            box.operator("nwo.animation_copy_add", text="New Animation Copy", icon_value=get_icon_id("animation_copy"))
            return
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationCopies",
            "",
            nwo,
            "animation_copies",
            nwo,
            "animation_copies_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.animation_copy_add", text="", icon="ADD")
        col.operator("nwo.animation_copy_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.animation_copy_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.animation_copy_move", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.animation_copies and nwo.animation_copies_active_index > -1:
            item = nwo.animation_copies[nwo.animation_copies_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(item, "source_name")
            col.prop(item, "name")
            
    def draw_animation_composites(self, box: bpy.types.UILayout, item):
        col = box.column()
        col.use_property_split = True
        col.prop(item, "overlay")
        col.prop_search(item, "timing_source", self.scene_nwo, "animations", icon='ANIM')
        box = col.box()
        box.label(text="Blend Axes")
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationBlendAxis",
            "",
            item,
            "blend_axis",
            item,
            "blend_axis_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.animation_blend_axis_add", text="", icon="ADD")
        col.operator("nwo.animation_blend_axis_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.animation_blend_axis_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.animation_blend_axis_move", icon="TRIA_DOWN", text="").direction = 'down'
        
        if not item.blend_axis or item.blend_axis_active_index <= -1:
            return
        
        blend_axis = item.blend_axis[item.blend_axis_active_index]
        
        parent_stack = []
        for idx, axis in enumerate(item.blend_axis):
            rel = axis.relationship

            if idx == 0 or rel == 'PARENT':
                parent_stack = [axis]
            elif rel == 'CHILD':
                parent_stack.append(axis)
            elif rel == 'SIBLING':
                if len(parent_stack) > 1:
                    parent_stack.pop()
                parent_stack.append(axis)
        
        col = box.column()
        col.use_property_split = True

        col.prop(blend_axis, "name")
        if item.blend_axis_active_index > 0:
            col.prop(blend_axis, "relationship")
        col.separator()
        col.prop(blend_axis, "animation_source_bounds_manual")
        if blend_axis.animation_source_bounds_manual:
            col.prop(blend_axis, "animation_source_bounds")
        col.prop(blend_axis, "animation_source_limit")
        col.separator()
        col.prop(blend_axis, "runtime_source_bounds_manual")
        if blend_axis.runtime_source_bounds_manual:
            col.prop(blend_axis, "runtime_source_bounds")
        col.prop(blend_axis, "runtime_source_clamped")
        col.prop(blend_axis, "adjusted")
        col.separator()
        if not blend_axis.dead_zones:
            col.operator("nwo.animation_dead_zone_add", text="Add Dead Zone", icon='CON_OBJECTSOLVER')
        else:
            box = col.box()
            box.label(text="Dead Zones")
            row = box.row()
            row.template_list(
                "NWO_UL_AnimationDeadZone",
                "",
                blend_axis,
                "dead_zones",
                blend_axis,
                "dead_zones_active_index",
            )
            col = row.column(align=True)
            col.operator("nwo.animation_dead_zone_add", text="", icon="ADD")
            col.operator("nwo.animation_dead_zone_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_dead_zone_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_dead_zone_move", icon="TRIA_DOWN", text="").direction = 'down'
            if blend_axis.dead_zones and blend_axis.dead_zones_active_index > -1:
                dead_zone = blend_axis.dead_zones[blend_axis.dead_zones_active_index]
                col = box.column()
                col.use_property_split = True
                col.prop(dead_zone, "bounds")
                col.prop(dead_zone, "rate")
            
        self.draw_animation_leaves(col, blend_axis, False, parent_stack=parent_stack)
        if not blend_axis.phase_sets:
            col.operator("nwo.animation_phase_set_add", text="Add Animation Set", icon='PRESET')
        else:
            box = col.box()
            box.label(text="Sets")
            row = box.row()
            row.template_list(
                "NWO_UL_AnimationPhaseSet",
                "",
                blend_axis,
                "phase_sets",
                blend_axis,
                "phase_sets_active_index",
            )
            col = row.column(align=True)
            col.operator("nwo.animation_phase_set_add", text="", icon="ADD")
            col.operator("nwo.animation_phase_set_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_phase_set_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_phase_set_move", icon="TRIA_DOWN", text="").direction = 'down'
            if blend_axis.phase_sets and blend_axis.phase_sets_active_index > -1:
                phase_set = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
                col = box.column()
                col.use_property_split = True
                col.prop(phase_set, "name")
                col.prop(phase_set, "priority")
                col.label(text="Keys")
                grid = col.grid_flow()
                grid.prop(phase_set, 'key_primary_keyframe')
                grid.prop(phase_set, 'key_secondary_keyframe')
                grid.prop(phase_set, 'key_tertiary_keyframe')
                grid.prop(phase_set, 'key_left_foot')
                grid.prop(phase_set, 'key_right_foot')
                grid.prop(phase_set, 'key_body_impact')
                grid.prop(phase_set, 'key_left_foot_lock')
                grid.prop(phase_set, 'key_left_foot_unlock')
                grid.prop(phase_set, 'key_right_foot_lock')
                grid.prop(phase_set, 'key_right_foot_unlock')
                grid.prop(phase_set, 'key_blend_range_marker')
                grid.prop(phase_set, 'key_stride_expansion')
                grid.prop(phase_set, 'key_stride_contraction')
                grid.prop(phase_set, 'key_ragdoll_keyframe')
                grid.prop(phase_set, 'key_drop_weapon_keyframe')
                grid.prop(phase_set, 'key_match_a')
                grid.prop(phase_set, 'key_match_b')
                grid.prop(phase_set, 'key_match_c')
                grid.prop(phase_set, 'key_match_d')
                grid.prop(phase_set, 'key_jetpack_closed')
                grid.prop(phase_set, 'key_jetpack_open')
                grid.prop(phase_set, 'key_sound_event')
                grid.prop(phase_set, 'key_effect_event')
                
                self.draw_animation_leaves(col, phase_set, True, parent_stack=parent_stack)
                
        if not blend_axis.groups:
            col.operator("nwo.animation_group_add", text="Add Animation Group", icon='GROUP_VERTEX')
        else:
            box = col.box()
            box.label(text="Groups")
            row = box.row()
            row.template_list(
                "NWO_UL_AnimationGroup",
                "",
                blend_axis,
                "groups",
                blend_axis,
                "groups_active_index",
            )
            col = row.column(align=True)
            col.operator("nwo.animation_group_add", text="", icon="ADD")
            col.operator("nwo.animation_group_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_group_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_group_move", icon="TRIA_DOWN", text="").direction = 'down'
            
            group = blend_axis.groups[blend_axis.groups_active_index]
            col = box.column()
            col.use_property_split = True
            for idx, par in enumerate(parent_stack):
                if idx > 9:
                    break
                name, function = blend_axis_name(par.name)
                col.prop(group, f"manual_blend_axis_{idx}", text=f"Manual {name}")
                if getattr(group, f"manual_blend_axis_{idx}"):
                    col.prop(group, f"blend_axis_{idx}", text=f"{function} value")
                
            self.draw_animation_leaves(col, group, in_group=True, parent_stack=parent_stack)
        
        col.separator()
        col = box.column()
        row = col.row()
        if not item.animation_renames:
            row.operator("nwo.animation_rename_add", text="New Rename", icon_value=get_icon_id('animation_rename'))
        else:
            rename_box = box.box()
            col = rename_box.column()
            row = col.row()
            row.label(text="Animation Renames")
            row = col.row()
            rows = 3
            row.template_list(
                "NWO_UL_AnimationRename",
                "",
                item,
                "animation_renames",
                item,
                "active_animation_rename_index",
                rows=rows,
            )
            col = row.column(align=True)
            col.operator("nwo.animation_rename_add", text="", icon="ADD")
            col.operator("nwo.animation_rename_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_rename_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_rename_move", icon="TRIA_DOWN", text="").direction = 'down'
                
            
    def draw_animation_leaves(self, col: bpy.types.UILayout, parent, in_set=False, in_group=False, parent_stack=[]):
        box = col.box()
        if in_set:
            box.label(text="Phase Set Animations")
        elif in_group:
            box.label(text="Group Animations")
        else:
            box.label(text="Blend Axis Animations")
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationLeaf",
            "",
            parent,
            "leaves",
            parent,
            "leaves_active_index",
        )
        col = row.column(align=True)
        add = col.operator("nwo.animation_leaf_add", text="", icon="ADD")
        add.phase_set = in_set
        add.group = in_group
        remove = col.operator("nwo.animation_leaf_remove", icon="REMOVE", text="")
        remove.phase_set = in_set
        remove.group = in_group
        col.separator()
        move_up = col.operator("nwo.animation_leaf_move", text="", icon="TRIA_UP")
        move_up.direction = 'up'
        move_up.phase_set = in_set
        move_up.group = in_group
        move_down = col.operator("nwo.animation_leaf_move", icon="TRIA_DOWN", text="")
        move_down.direction = 'down'
        move_down.phase_set = in_set
        move_down.group = in_group
        if parent.leaves and parent.leaves_active_index > -1:
            leaf = parent.leaves[parent.leaves_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop_search(leaf, "animation", self.scene_nwo, "animations", icon='ANIM', results_are_suggestions=True)
            
            for idx, par in enumerate(parent_stack):
                if idx > 9:
                    break
                name, function = blend_axis_name(par.name)
                col.prop(leaf, f"manual_blend_axis_{idx}", text=f"Manual {name}")
                if getattr(leaf, f"manual_blend_axis_{idx}"):
                    col.prop(leaf, f"blend_axis_{idx}", text=f"{function} value")
    
    def draw_rig_ui(self, context, nwo):
        box = self.box.box()
        if self.draw_expandable_box(box, nwo, 'model_rig') and nwo.main_armature:
            # self.draw_expandable_box(box.box(), nwo, 'rig_controls', 'Bone Controls')
            self.draw_expandable_box(box.box(), nwo, 'rig_usages', 'Node Usages')
            self.draw_expandable_box(box.box(), nwo, 'ik_chains', panel_display_name='IK Chains')

    def draw_sets_manager(self):
        self.box.operator('nwo.update_sets', icon='FILE_REFRESH')
        box = self.box
        nwo = self.scene_nwo
        if not nwo.regions_table:
            return
        is_scenario = nwo.asset_type == 'scenario'
        self.draw_object_visibility(box.box(), nwo)
        self.draw_expandable_box(box.box(), nwo, "regions_table", "BSPs" if is_scenario else "Regions")
        self.draw_expandable_box(box.box(), nwo, "permutations_table", "Layers" if is_scenario else "Permutations")
        
    def draw_object_visibility(self, box: bpy.types.UILayout, nwo):
        asset_type = nwo.asset_type
        # box.label(text="Mesh")
        grid = box.grid_flow(align=True, even_columns=True)
        default_icon_name = "render_geometry"
        default_icon_off_name = "render_geometry_off"
        if utils.poll_ui(('scenario', 'prefab')):
            default_icon_name = "instance"
            default_icon_off_name = "instance_off"
        elif asset_type == 'decorator_set':
            default_icon_name = "decorator"
            default_icon_off_name = "decorator_off"
            
        grid.prop(nwo, "connected_geometry_mesh_type_default_visible", text="", icon_value=get_icon_id(default_icon_name) if nwo.connected_geometry_mesh_type_default_visible else get_icon_id(default_icon_off_name), emboss=False)
        if utils.poll_ui(('scenario', 'model', 'prefab')):
            grid.prop(nwo, "connected_geometry_mesh_type_collision_visible", text="", icon_value=get_icon_id("collider") if nwo.connected_geometry_mesh_type_collision_visible else get_icon_id("collider_off"), emboss=False)
        if asset_type == 'model':
            grid.prop(nwo, "connected_geometry_mesh_type_physics_visible", text="", icon_value=get_icon_id("physics") if nwo.connected_geometry_mesh_type_physics_visible else get_icon_id("physics_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_object_instance_visible", text="", icon_value=get_icon_id("instance") if nwo.connected_geometry_mesh_type_object_instance_visible else get_icon_id("instance_off"), emboss=False)
        if asset_type == 'scenario':
            grid.prop(nwo, "connected_geometry_mesh_type_structure_visible", text="", icon_value=get_icon_id("structure") if nwo.connected_geometry_mesh_type_structure_visible else get_icon_id("structure_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_seam_visible", text="", icon_value=get_icon_id("seam") if nwo.connected_geometry_mesh_type_seam_visible else get_icon_id("seam_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_portal_visible", text="", icon_value=get_icon_id("portal") if nwo.connected_geometry_mesh_type_portal_visible else get_icon_id("portal_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_water_surface_visible", text="", icon_value=get_icon_id("water") if nwo.connected_geometry_mesh_type_water_surface_visible else get_icon_id("water_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_planar_fog_volume_visible", text="", icon_value=get_icon_id("fog") if nwo.connected_geometry_mesh_type_planar_fog_volume_visible else get_icon_id("fog_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_lightmap_region_visible", text="", icon_value=get_icon_id("lightmap") if nwo.connected_geometry_mesh_type_lightmap_region_visible else get_icon_id("lightmap_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_boundary_surface_visible", text="", icon_value=get_icon_id("soft_ceiling") if nwo.connected_geometry_mesh_type_boundary_surface_visible else get_icon_id("soft_ceiling_off"), emboss=False)
            if self.h4:
                grid.prop(nwo, "connected_geometry_mesh_type_obb_volume_visible", text="", icon_value=get_icon_id("streaming") if nwo.connected_geometry_mesh_type_obb_volume_visible else get_icon_id("streaming_off"), emboss=False)
            else:
                grid.prop(nwo, "connected_geometry_mesh_type_cookie_cutter_visible", text="", icon_value=get_icon_id("cookie_cutter") if nwo.connected_geometry_mesh_type_cookie_cutter_visible else get_icon_id("cookie_cutter_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_mesh_type_poop_vertical_rain_sheet_visible", text="", icon_value=get_icon_id("rain_sheet") if nwo.connected_geometry_mesh_type_poop_vertical_rain_sheet_visible else get_icon_id("rain_sheet_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_mesh_type_poop_rain_blocker_visible", text="", icon_value=get_icon_id("rain_blocker") if nwo.connected_geometry_mesh_type_poop_rain_blocker_visible else get_icon_id("rain_blocker_off"), emboss=False)

        grid.prop(nwo, "connected_geometry_marker_type_model_visible", text="", icon_value=get_icon_id("marker") if nwo.connected_geometry_marker_type_model_visible else get_icon_id("marker_off"), emboss=False)
        if utils.poll_ui(('model', 'sky')):
            grid.prop(nwo, "connected_geometry_marker_type_effects_visible", text="", icon_value=get_icon_id("effects") if nwo.connected_geometry_marker_type_effects_visible else get_icon_id("effects_off"), emboss=False)
        if asset_type == 'model':
            grid.prop(nwo, "connected_geometry_marker_type_garbage_visible", text="", icon_value=get_icon_id("garbage") if nwo.connected_geometry_marker_type_garbage_visible else get_icon_id("garbage_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_hint_visible", text="", icon_value=get_icon_id("hint") if nwo.connected_geometry_marker_type_hint_visible else get_icon_id("hint_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_pathfinding_sphere_visible", text="", icon_value=get_icon_id("pathfinding_sphere") if nwo.connected_geometry_marker_type_pathfinding_sphere_visible else get_icon_id("pathfinding_sphere_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_physics_constraint_visible", text="", icon_value=get_icon_id("physics_constraint") if nwo.connected_geometry_marker_type_physics_constraint_visible else get_icon_id("physics_constraint_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_target_visible", text="", icon_value=get_icon_id("target") if nwo.connected_geometry_marker_type_target_visible else get_icon_id("target_off"), emboss=False)
                
        if utils.poll_ui(('model', 'scenario')) and self.h4:
            grid.prop(nwo, "connected_geometry_marker_type_airprobe_visible", text="", icon_value=get_icon_id("airprobe") if nwo.connected_geometry_marker_type_airprobe_visible else get_icon_id("airprobe_off"), emboss=False)
        if asset_type == 'scenario':
            grid.prop(nwo, "connected_geometry_marker_type_game_instance_visible", text="", icon_value=get_icon_id("game_object") if nwo.connected_geometry_marker_type_game_instance_visible else get_icon_id("game_object_off"), emboss=False)
            if self.h4:
                grid.prop(nwo, "connected_geometry_marker_type_envfx_visible", text="", icon_value=get_icon_id("environment_effect") if nwo.connected_geometry_marker_type_envfx_visible else get_icon_id("environment_effect_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_marker_type_lightCone_visible", text="", icon_value=get_icon_id("light_cone") if nwo.connected_geometry_marker_type_lightCone_visible else get_icon_id("light_cone_off"), emboss=False)
        # box.label(text="Other")
        # grid = box.grid_flow(align=False, even_columns=True)
        grid.prop(nwo, "connected_geometry_object_type_frame_visible", text="", icon_value=get_icon_id("frame") if nwo.connected_geometry_object_type_frame_visible else get_icon_id("frame_off"), emboss=False)
        grid.prop(nwo, "connected_geometry_object_type_light_visible", text="", icon_value=get_icon_id("light") if nwo.connected_geometry_object_type_light_visible else get_icon_id("light_off"), emboss=False)
        
    def draw_regions_table(self, box, nwo):
        row = box.row()
        region = nwo.regions_table[nwo.regions_table_active_index]
        rows = 4
        row.template_list(
            "NWO_UL_Regions",
            "",
            nwo,
            "regions_table",
            nwo,
            "regions_table_active_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.region_add", text="", icon="ADD").set_object_prop = False
        col.operator("nwo.region_remove", icon="REMOVE", text="")
        if self.asset_type == 'scenario':
            col.separator()
            col.menu('NWO_MT_BSPContextMenu', text="", icon='DOWNARROW_HLT')
        col.separator()
        col.operator("nwo.region_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.region_move", icon="TRIA_DOWN", text="").direction = 'down'

        row = box.row()

        sub = row.row(align=True)
        sub.operator("nwo.region_assign", text="Assign").name = region.name

        sub = row.row(align=True)
        sub.operator("nwo.region_select", text="Select").select = True
        sub.operator("nwo.region_select", text="Deselect").select = False  
    
    def draw_permutations_table(self, box, nwo):
        row = box.row()
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        rows = 4
        row.template_list(
            "NWO_UL_Permutations",
            "",
            nwo,
            "permutations_table",
            nwo,
            "permutations_table_active_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.permutation_add", text="", icon="ADD").set_object_prop = False
        col.operator("nwo.permutation_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.permutation_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.permutation_move", icon="TRIA_DOWN", text="").direction = 'down'

        row = box.row()

        sub = row.row(align=True)
        sub.operator("nwo.permutation_assign", text="Assign").name = permutation.name

        sub = row.row(align=True)
        sub.operator("nwo.permutation_select", text="Select").select = True
        sub.operator("nwo.permutation_select", text="Deselect").select = False
        
        if self.h4 and nwo.asset_type in {'model', 'sky'}:
            if not permutation.clones:
                row = box.row()
                return row.operator("nwo.add_permutation_clone", text="New Permutation Clone", icon='ADD')
            
            box.label(text="Clones")
            row = box.row()
            rows = 4
            row.template_list(
                "NWO_UL_PermutationClones",
                "",
                permutation,
                "clones",
                permutation,
                "active_clone_index",
                rows=rows,
            )
            col = row.column(align=True)
            col.operator("nwo.add_permutation_clone", text="", icon="ADD")
            col.operator("nwo.remove_permutation_clone", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.move_permutation_clone", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.move_permutation_clone", icon="TRIA_DOWN", text="").direction = 'down'
            clone = permutation.clones[permutation.active_clone_index]
            if not clone.material_overrides:
                row = box.row()
                return row.operator("nwo.add_material_override", text="New Material Override", icon='ADD')
            
            box.label(text="Material Overrides")
            row = box.row()
            rows = 4
            row.template_list(
                "NWO_UL_MaterialOverrides",
                "",
                clone,
                "material_overrides",
                clone,
                "active_material_override_index",
                rows=rows,
            )
            col = row.column(align=True)
            col.operator("nwo.add_material_override", text="", icon="ADD")
            col.operator("nwo.remove_material_override", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.move_material_override", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.move_material_override", icon="TRIA_DOWN", text="").direction = 'down'
            
            override = clone.material_overrides[clone.active_material_override_index]
            col = box.column()
            col.use_property_split = True
            col.prop(override, "source_material")
            col.prop(override, "destination_material")
            col.separator()
            col.operator("nwo.swap_material", icon='UV_SYNC_SELECT')
            

    def draw_object_properties(self):
        box = self.box
        row = box.row()
        context = self.context
        ob = context.object
        h4 = self.h4
        if ob is None:
            row.label(text="No Active Object")
            return
        
        def draw_custom_props():
            custom_props = [k for k in ob.keys() if not k.startswith("_")]
            
            change_colors_props = [k for k in custom_props if k in all_change_color_prop_names]
            weapon_props = [k for k in custom_props if k in ("Ammo", "Tether Distance")]
            function_props = [k for k in custom_props if k in game_functions]
            built_in_props = set(change_colors_props + weapon_props + function_props)
            tag_props = [k for k in custom_props if k.lower() == k and k not in built_in_props]
            
            if change_colors_props or weapon_props or function_props:
                custom_box = box.box()
                custom_box.label(text="Custom Properties")
                custom_box.use_property_split = True
                if change_colors_props:
                    change_colors_box = custom_box.box()
                    change_colors_box.label(text="Change Colors")
                    change_colors_box.separator()
                    for key, display in zip(all_change_color_prop_names, all_change_color_prop_display_names):
                        if key in change_colors_props:
                            change_colors_box.prop(ob, f'["{key}"]', text=display)
                        
                if weapon_props:
                    weapon_box = custom_box.box()
                    weapon_box.label(text="Weapon")
                    weapon_box.separator()
                    for key in sorted(weapon_props):
                        weapon_box.prop(ob, f'["{key}"]')
                        
                if function_props:
                    function_box = custom_box.box()
                    function_box.label(text="Built In Functions")
                    function_box.separator()
                    for key in sorted(function_props):
                        function_box.prop(ob, f'["{key}"]', text="Engine RPM" if key.endswith("_rpm") else utils.formalise_string(key))
                        
                if tag_props:
                    tag_box = custom_box.box()
                    tag_box.label(text="Object Tag Functions")
                    tag_box.separator()
                    for key in sorted(tag_props):
                        tag_box.prop(ob, f'["{key}"]', text=utils.formalise_string(key))

        is_cinematic = self.asset_type == 'cinematic'
        nwo = ob.nwo
        col1 = row.column()
        col1.template_ID(context.view_layer.objects, "active", filter="AVAILABLE")
        if ob.type == 'CAMERA' and is_cinematic:
            markers = utils.get_timeline_markers(self.scene)
            camera_shots = [str(idx + 1) for idx, marker in enumerate(markers) if marker.camera == ob]
            if len(camera_shots) == 1:
                box.label(text=f"Camera Shot: {camera_shots[0]}")
            elif camera_shots:
                box.label(text=f"Camera Shots: {', '.join(camera_shots)}")
            row = box.row(heading='Camera Actors')
            row.use_property_split = False
            row.prop(nwo, "actors_type", text=" ", expand=True)
            row = box.row(align=True)
            row.template_list(
                "NWO_UL_CameraActors",
                "",
                nwo,
                "actors",
                nwo,
                "active_actor_index",
            )
            col = row.column(align=True)
            col.operator("nwo.camera_actor_add", text="", icon='ADD')
            col.operator("nwo.camera_actor_remove", text="", icon='REMOVE')
            col.separator()
            col.operator("nwo.camera_actor_clear", text="", icon='CANCEL')
            if nwo.actors and nwo.active_actor_index > -1:
                row = box.row(align=True)
                row.prop(nwo.actors[nwo.active_actor_index], "actor", icon='OUTLINER_OB_ARMATURE')
            row = box.row(align=True)
            row.operator("nwo.camera_actors_select", icon='RESTRICT_SELECT_OFF')
            return
        
        col2 = row.column()
        col2.alignment = "RIGHT"
        col2.prop(nwo, "export_this", text="Export")

        if not nwo.export_this:
            box.label(text="Object is excluded from export")
            if ob.type == 'ARMATURE':
                draw_custom_props()
            return
        
        elif nwo.ignore_for_export:
            txt = "Object is excluded from export. "
            col2.enabled = False
            match IgnoreReason(ob.nwo.ignore_for_export):
                case IgnoreReason.invalid_type:
                    txt += "Object is an unsupported type"
                case IgnoreReason.view_layer:
                    txt += "Object is not in the view layer"
                case IgnoreReason.exclude:
                    txt += "Object is in an exclude collection"
                case IgnoreReason.parent:
                    txt += "Object's parent is set to not export"
                    
            box.label(text=txt)
            return
        
        instanced = ob.is_instancer and ob.instance_collection and ob.instance_collection.all_objects
        if instanced:
            box.prop(nwo, "marker_instance")
            if not ob.nwo.marker_instance:
                box.label(text=f"Object is derived from Instanced Collection: {ob.instance_collection.name}")
                return box.label(text="This object will be made real at export")

        elif ob.type == "ARMATURE":
            box.label(text='Frame' if self.asset_type != 'cinematic' else "Cinematic Actor")
            col = box.column()
            col.operator("nwo.select_child_objects", icon='CON_CHILDOF')
            if is_cinematic:
                col.separator()
                box = col.box()
                box.label(text="Cinematic Properties")
                draw_tag_path(col, nwo, "cinematic_object")
                    
            elif utils.poll_ui(("model", "sky", "animation")):
                col.separator()
                box = col.box()
                box.prop(nwo, "node_order_source", icon_value=get_icon_id("tags"))
                
            draw_custom_props()
            
            box_rigging = box.box()
            box_rigging.label(text="Armature Controls")
            box_rigging.use_property_split = True
            row = box_rigging.row(align=True)
            row.prop_search(nwo, 'control_aim', ob.pose, 'bones')
            if not nwo.control_aim:
                row.operator('nwo.add_pose_bones', text='', icon='ADD').skip_invoke = True
                
            box_rigging.operator("nwo.invert_aim_control", icon='CONSTRAINT_BONE', depress=nwo.invert_control_aim)
            box_rigging.separator()
            if not any(b for b in ob.pose.bones if b.name.startswith("FK_")):
                box_rigging.operator("nwo.build_control_rig", icon='BONE_DATA')
            box_rigging.operator("nwo.invert_control_rig", icon='CONSTRAINT_BONE', depress=nwo.invert_control_rig)
            box_rigging.separator()
            box_rigging.operator("nwo.bake_to_control", icon='POSE_HLT')
            
            return
        
        if is_cinematic:
            return

        row = box.row(align=True)
        row.scale_x = 0.5
        row.scale_y = 1.3
        data = ob.data

        halo_light = ob.type == 'LIGHT'
        has_mesh_types = utils.is_mesh(ob) and utils.poll_ui(('model', 'scenario'))

        if halo_light:
            row.prop(data, "type", expand=True)
            col = box.column()
            col.use_property_split = True
            self.draw_table_menus(col, nwo, ob)
            
            nwo = data.nwo
            ob_nwo = ob.nwo
            
            box_ins = box.box()
            box_ins.use_property_split = True
            box_ins.label(text="Light Instance Properties")
            col = box_ins.column()
            if self.h4:
                col.prop(ob_nwo, "light_mode", expand=True)
            else:
                col.prop(ob_nwo, "light_game_type", text="Light Type")
                col.prop(ob_nwo, "light_screenspace_has_specular")
                col.prop(ob_nwo, "light_bounce_ratio", text="Light Bounce Ratio")
                col.separator()
                col.prop(ob_nwo, "light_volume_distance")
                col.prop(ob_nwo, "light_volume_intensity")
                col.separator()
                col.prop(ob_nwo, "light_fade_start_distance")
                col.prop(ob_nwo, "light_fade_end_distance")
                col.separator()
                draw_tag_path(col, ob_nwo, "light_tag_override")
                draw_tag_path(col, ob_nwo, "light_shader_reference")
                draw_tag_path(col, ob_nwo, "light_gel_reference")
                draw_tag_path(col, ob_nwo, "light_lens_flare_reference")
            
            col.separator()
            box_def = box.box()
            box_def.use_property_split = True
            box_def.label(text="Light Definition Properties")

            col = box_def.column()
            col.prop(data, "color")
            col.prop(data, "energy")
            if data.type != 'SUN':
                col.prop(nwo, 'light_intensity', text="Intensity")
            scaled_energy = data.energy * utils.get_export_scale(context)
            if scaled_energy < 11 and data.type != 'SUN':
                # Warn user about low light power. Need the light scaled to Halo proportions
                col.label(text="Light itensity is very low", icon='ERROR')
                col.label(text="For best results match the power of the light in")
                col.label(text="Cycles to how you'd like it to appear in game")
                
            if data.type == 'AREA':
                # Area lights use emissive settings, as they will be converted to lightmap only emissive planes at export
                col.separator()
                col.prop(data, "shape")
                if data.shape in {'SQUARE', 'DISK'}:
                    col.prop(data, "size")
                elif data.shape in {'RECTANGLE', 'ELLIPSE'}:
                    col.prop(data, "size", text="Size X")
                    col.prop(data, "size_y", text="Y")
                col.separator()
                col.prop(nwo, "light_quality")
                col.prop(nwo, "light_focus")
                col.prop(ob.nwo, "light_bounce_ratio")
                col.separator()
                col.prop(nwo, "light_far_attenuation_start", text="Light Falloff")
                col.prop(nwo, "light_far_attenuation_end", text="Light Cutoff")
                col.separator()
                col.prop(nwo, "light_use_shader_gel")
                col.prop(data, "normalize")
                return

            if data.type == 'SPOT':
                col.separator()
                col.prop(data, "spot_size", text="Cone Size")
                col.prop(data, "spot_blend", text="Cone Blend", slider=True)
                col.prop(data, "show_cone")

            col.separator()
            if self.h4:
                row = col.row()
                col.prop(nwo, "is_sun")
                if data.type == "SPOT":
                    col.separator()
                    row = col.row()
                    row.prop(nwo, "light_cone_projection_shape", expand=True)

                col.separator()
                col.prop(nwo, "light_physically_correct")
                if not nwo.light_physically_correct:
                    col.prop(nwo, "light_far_attenuation_start", text='Light Falloff')
                    col.prop(nwo, "light_far_attenuation_end", text='Light Cutoff')
                
                col.separator()

                if ob_nwo.light_mode == "_connected_geometry_light_mode_dynamic":
                    row = col.row()
                    row.prop(nwo, "light_cinema", expand=True)
                    col.separator()

                    col.prop(nwo, "light_shadows")
                    if nwo.light_shadows:
                        # col.prop(nwo, "light_shadow_color")
                        row = col.row()
                        row.prop(nwo, "light_dynamic_shadow_quality", expand=True)
                        col.prop(nwo, "light_shadow_near_clipplane")
                        col.prop(nwo, "light_shadow_far_clipplane")
                        col.prop(nwo, "light_shadow_bias_offset")
                    if data.type == 'SPOT':
                        col.prop(nwo, "light_cinema_objects_only")
                    col.prop(nwo, "light_specular_contribution")
                    col.prop(nwo, "light_diffuse_contribution")
                    col.prop(nwo, "light_ignore_dynamic_objects")
                    col.prop(nwo, "light_screenspace")
                    if nwo.light_screenspace:
                        col.prop(nwo, "light_specular_power")
                        col.prop(nwo, "light_specular_intensity")

                else:
                    row = col.row()
                    row.prop(nwo, "light_jitter_quality", expand=True)
                    col.prop(nwo, "light_jitter_angle")
                    col.prop(nwo, "light_jitter_sphere_radius")

                    col.separator()

                    col.prop(nwo, "light_amplification_factor")

                    col.separator()
                    col.prop(nwo, "light_indirect_only")
                    col.prop(nwo, "light_static_analytic")

            else:
                col.prop(nwo, "light_shape", text="Shape")

                col.separator()

                col.prop(nwo, "light_falloff_shape", text="Falloff Shape")
                col.prop(nwo, "light_aspect", text="Light Aspect")

                col.separator()

                # col_box.prop(nwo, "light_frustum_width", text="Frustum Width")
                # col_box.prop(nwo, "light_frustum_height", text="Frustum Height")

                # col_box.separator()

                # col.prop(nwo, "light_volume_distance", text="Light Volume Distance")
                # col.prop(nwo, "light_volume_intensity", text="Light Volume Intensity")

                col.separator()
                
                col.prop(data, "shadow_soft_size", text="Radius")

                # col_box.prop(
                #     nwo,
                #     "light_near_attenuation_start",
                #     text="Light Activation Start",
                # )
                # col_box.prop(
                #     nwo,
                #     "light_near_attenuation_end",
                #     text="Light Activation End",
                # )

                col.separator()

                col.prop(nwo, "light_far_attenuation_start", text="Light Falloff")
                col.prop(nwo, "light_far_attenuation_end", text="Light Cutoff")


                # col.separator() # commenting out light clipping for now.

                # col.prop(nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
                # col.prop(nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
                # col.prop(nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
                # col.prop(nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
                # col.prop(nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
                # col.prop(nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')

        elif utils.is_mesh(ob):
            if has_mesh_types:
                display_name, icon_id = utils.get_mesh_display(nwo.mesh_type)
                row.menu('NWO_MT_MeshTypes', text=display_name, icon_value=icon_id)
                
            # SPECIFIC MESH PROPS
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            mesh_nwo = ob.data.nwo
            col = flow.column()
            row = col.row()
            row.scale_y = 1.25
            row.emboss = "NORMAL"
            # row.menu(NWO_MeshMenu.bl_idname, text=mesh_type_name, icon_value=get_icon_id(mesh_type_icon))
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            col.use_property_split = True
            if self.asset_type == 'decorator_set':
                col.label(text="Decorator")
                col.prop(nwo, "decorator_lod", text="Level of Detail", expand=True)
                return
            elif self.asset_type == 'particle_model':
                col.label(text="Particle Model")
                return
            
            if nwo.mesh_type == '_connected_geometry_mesh_type_object_instance':
                row = col.row()
                row.use_property_split = False
                row.prop(nwo, "marker_uses_regions", text='Region', icon_value=get_icon_id("collection_creator") if nwo.region_name_locked else 0)
                if nwo.marker_uses_regions:
                    col.menu("NWO_MT_Regions", text=utils.true_region(nwo), icon_value=get_icon_id("region"))
                    col.separator()
                    rows = 3
                    row = col.row(heading='Permutations')
                    row.use_property_split = False
                    row.prop(nwo, "marker_permutation_type", text=" ", expand=True)
                    row = col.row()
                    row.template_list(
                        "NWO_UL_MarkerPermutations",
                        "",
                        nwo,
                        "marker_permutations",
                        nwo,
                        "marker_permutations_index",
                        rows=rows,
                    )
                    col_perm = row.column(align=True)
                    col_perm.menu("NWO_MT_MarkerPermutations", text="", icon="ADD")
                    col_perm.operator("nwo.marker_perm_remove", icon="REMOVE", text="")
                    if nwo.marker_permutation_type == "include" and not nwo.marker_permutations:
                        row = col.row()
                        row.label(text="No permutations in include list", icon="ERROR")
            else:
                self.draw_table_menus(col, nwo, ob)

            if nwo.mesh_type == "_connected_geometry_mesh_type_physics":
                row = col.row(align=True)
                row.prop(nwo, "global_material", text="Physics Material")
                row.menu("NWO_MT_AddGlobalMaterial", text="", icon='DOWNARROW_HLT')
                col.prop(nwo, "mesh_primitive_type", text="Primitive Type")
                if self.h4:
                    col.prop(nwo, "mopp_physics")

            elif nwo.mesh_type == "_connected_geometry_mesh_type_portal":
                row = col.row()
                row.prop(
                    nwo,
                    "portal_type",
                    text="Portal Type",
                    expand=True,
                )

                col.separator()

                col = col.column(heading="Flags")

                col.prop(
                    nwo,
                    "portal_ai_deafening",
                    text="AI Deafening",
                )
                col.prop(
                    nwo,
                    "portal_blocks_sounds",
                    text="Blocks Sounds",
                )
                col.prop(nwo, "portal_is_door", text="Is Door")

            elif (
                nwo.mesh_type
                == "_connected_geometry_mesh_type_planar_fog_volume"
            ):
                draw_tag_path(col, nwo, "fog_appearance_tag")
                col.prop(
                    nwo,
                    "fog_volume_depth",
                    text="Fog Volume Depth",
                )
                
            elif (
                nwo.mesh_type
                == "_connected_geometry_mesh_type_lightmap_region"
            ):
                return
            elif (
                nwo.mesh_type
                == "_connected_geometry_mesh_type_boundary_surface"
            ):
                col.prop(
                    mesh_nwo,
                    "boundary_surface_type",
                    icon_value=get_icon_id(mesh_nwo.boundary_surface_type.lower())
                )
            elif (
                nwo.mesh_type
                == "_connected_geometry_mesh_type_obb_volume"
            ):
                col.prop(
                    mesh_nwo,
                    "obb_volume_type",
                    icon_value=get_icon_id("streaming" if mesh_nwo.obb_volume_type == "STREAMING_VOLUME" else "lightmap_exclude")
                )

            elif (
                nwo.mesh_type == "_connected_geometry_mesh_type_water_surface"
            ):
                col.prop(
                    nwo,
                    "water_volume_depth",
                    text="Water Depth",
                )
                if nwo.water_volume_depth:
                    col.prop(
                        nwo,
                        "water_volume_flow_direction",
                        text="Water Flow Direction",
                    )
                    col.prop(
                        nwo,
                        "water_volume_flow_velocity",
                        text="Water Flow Velocity",
                    )
                    col.prop(
                        nwo,
                        "water_volume_fog_color",
                        text="Underwater Fog Color",
                    )
                    col.prop(
                        nwo,
                        "water_volume_fog_murkiness",
                        text="Underwater Fog Murkiness",
                    )
                    col.separator()
                    col.operator("nwo.show_water_direction", depress=self.scene_nwo.show_water_direction, icon='MATFLUID')

            elif nwo.mesh_type in (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_structure",
            ) and utils.poll_ui(('scenario', 'prefab')):
                if h4 and nwo.mesh_type == "_connected_geometry_mesh_type_structure" and utils.poll_ui(('scenario',)):
                    row = col.row()
                    row.use_property_split = False
                    picon = 'CHECKBOX_HLT' if nwo.proxy_instance else 'CHECKBOX_DEHLT'
                    row.prop(nwo, "proxy_instance", text="Instanced Structure", icon=picon)
                if nwo.mesh_type == "_connected_geometry_mesh_type_default" or (
                    nwo.mesh_type == "_connected_geometry_mesh_type_structure"
                    and h4
                    and nwo.proxy_instance
                ):
                    col.prop(nwo, "poop_lighting", text="Lighting Policy")

                    if h4:
                        col.prop(nwo, "poop_lightmap_resolution_scale")

                    col.prop(
                        nwo,
                        "poop_pathfinding",
                        text="Pathfinding Policy",
                    )

                    col.prop(
                        nwo,
                        "poop_imposter_policy",
                        text="Imposter Policy",
                    )
                    if (
                        nwo.poop_imposter_policy
                        != "never"
                    ):
                        sub = col.row(heading="Imposter Transition")
                        sub.prop(
                            nwo,
                            "poop_imposter_transition_distance_auto",
                            text="Automatic",
                        )
                        if not nwo.poop_imposter_transition_distance_auto:
                            sub.prop(
                                nwo,
                                "poop_imposter_transition_distance",
                                text="Distance",
                            )
                        if h4:
                            col.prop(nwo, "poop_imposter_brightness")

                    if h4:
                        col.prop(nwo, "poop_streaming_priority")
                        col.prop(nwo, "poop_cinematic_properties")

                    col.separator()

                    col = col.column(heading="Instance Flags")
                    col.prop(
                        nwo,
                        "poop_render_only",
                        text="Render Only",
                    )
                    col.prop(
                        nwo,
                        "poop_chops_portals",
                        text="Chops Portals",
                    )
                    col.prop(
                        nwo,
                        "poop_does_not_block_aoe",
                        text="Does Not Block AOE",
                    )
                    col.prop(
                        nwo,
                        "poop_excluded_from_lightprobe",
                        text="Excluded From Lightprobe",
                    )
                    col.prop(nwo, "poop_decal_spacing", text='Decal Spacing')
                    if h4:
                        col.prop(nwo, "poop_remove_from_shadow_geometry")
                        col.prop(nwo, "poop_disallow_lighting_samples")
                        # col.prop(nwo, "poop_rain_occluder")

            # MESH LEVEL / FACE LEVEL PROPERTIES

        elif utils.is_marker(ob) and utils.poll_ui(
            ("model", "scenario", "sky", "prefab")
        ):
            # MARKER PROPERTIES
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=False,
                even_rows=False,
                align=False,
            )
            flow.use_property_split = False
            col = flow.column()
            row = col.row()
            row.scale_y = 1.25
            row.emboss = "NORMAL"
            display_name, icon_id = utils.get_marker_display(nwo.marker_type, ob)
            row.menu('NWO_MT_MarkerTypes', text=display_name, icon_value=icon_id)

            col.separator()

            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=False,
                even_rows=False,
                align=False,
            )
            flow.use_property_split = False
            col = flow.column()
            
            #col.prop(nwo, "frame_override")

            if utils.poll_ui(("scenario",)):
                col.use_property_split = True
                self.draw_table_menus(col, nwo, ob)

            if nwo.marker_type in (
                "_connected_geometry_marker_type_model",
                "_connected_geometry_marker_type_garbage",
                "_connected_geometry_marker_type_effects",
                "_connected_geometry_marker_type_target",
                "_connected_geometry_marker_type_hint",
                "_connected_geometry_marker_type_pathfinding_sphere",
            ):
                if utils.poll_ui(("model", "sky")):
                    if nwo.marker_type in ('_connected_geometry_marker_type_model', '_connected_geometry_marker_type_garbage', '_connected_geometry_marker_type_effects'):
                        col.prop(nwo, 'marker_model_group', text="Marker Group")
                    row = col.row()
                    row.use_property_split = False
                    row.prop(nwo, "marker_uses_regions", text='Region', icon_value=get_icon_id("collection_creator") if nwo.region_name_locked else 0)
                    if nwo.marker_uses_regions:
                        col.menu("NWO_MT_Regions", text=utils.true_region(nwo), icon_value=get_icon_id("region"))
                    
                    # marker perm ui
                    if nwo.marker_uses_regions:
                        col.separator()
                        rows = 3
                        row = col.row(heading='Permutations')
                        row.use_property_split = False
                        # row.label(text="Marker Permutations")
                        row.prop(nwo, "marker_permutation_type", text=" ", expand=True)
                        row = col.row()
                        row.template_list(
                            "NWO_UL_MarkerPermutations",
                            "",
                            nwo,
                            "marker_permutations",
                            nwo,
                            "marker_permutations_index",
                            rows=rows,
                        )
                        col_perm = row.column(align=True)
                        col_perm.menu("NWO_MT_MarkerPermutations", text="", icon="ADD")
                        col_perm.operator("nwo.marker_perm_remove", icon="REMOVE", text="")
                        if nwo.marker_permutation_type == "include" and not nwo.marker_permutations:
                            row = col.row()
                            row.label(text="No permutations in include list", icon="ERROR")


            elif nwo.marker_type == "_connected_geometry_marker_type_game_instance":
                draw_tag_path(col, nwo, "marker_game_instance_tag_name")
                tag_name = Path(nwo.marker_game_instance_tag_name).suffix.lower()
                if tag_name == ".decorator_set":
                    row = col.row(align=True)
                    row.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name",
                        text="Decorator Type",
                    )
                    if bpy.ops.nwo.get_decorator_types.poll():
                        row.operator_menu_enum("nwo.get_decorator_types", "decorator_type", icon="DOWNARROW_HLT", text="")
                    col.separator()
                    col.prop(nwo, "decorator_motion_scale")
                    col.prop(nwo, "decorator_ground_tint")
                    col.prop(nwo, "decorator_tint")
                elif not tag_name in (".prefab", ".cheap_light", ".light", ".leaf"):
                    row = col.row(align=True)
                    row.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name",
                        text="Tag Variant",
                    )
                    if bpy.ops.nwo.get_model_variants.poll():
                        row.operator_menu_enum("nwo.get_model_variants", "variant", icon="DOWNARROW_HLT", text="")
                    if h4:
                        col.prop(nwo, "marker_always_run_scripts")
                        
                elif tag_name == ".prefab":
                    col.separator()
                    tip(col, "Prefab Overrides", "Prefab overrides will override the default properties of the referenced prefab tag for this specific prefab instance")
                    col.prop(nwo, "prefab_lighting")
                    col.prop(nwo, "prefab_lightmap_res")
                    col.prop(nwo, "prefab_pathfinding")
                    col.prop(nwo, "prefab_imposter_policy")
                    if nwo.prefab_imposter_policy != "never":
                        sub = col.row(heading="Imposter Transition")
                        sub.prop(
                            nwo,
                            "prefab_imposter_transition_distance_auto",
                            text="Automatic",
                        )
                        if not nwo.prefab_imposter_transition_distance_auto:
                            sub.prop(
                                nwo,
                                "prefab_imposter_transition_distance",
                                text="Distance",
                            )
                            
                    col.prop(nwo, "prefab_imposter_brightness")

                    col.prop(nwo, "prefab_streaming_priority")
                    col.prop(nwo, "prefab_cinematic_properties")
                    col.separator()
                    col = col.column(heading="Prefab Flags")
                    col.prop(nwo, "prefab_render_only")
                    col.prop(nwo, "prefab_does_not_block_aoe")
                    col.prop(nwo, "prefab_decal_spacing")
                    col.prop(nwo, "prefab_remove_from_shadow_geometry")
                    col.prop(nwo, "prefab_disallow_lighting_samples")
                    col.prop(nwo, "prefab_excluded_from_lightprobe")
                    
                col.operator("nwo.import_game_instance_tag", icon='IMPORT')
                    
            if nwo.marker_type == "_connected_geometry_marker_type_hint":
                col.operator("nwo.set_hint_name", icon='GREASEPENCIL')

            elif nwo.marker_type == "_connected_geometry_marker_type_garbage":
                col.prop(nwo, "marker_velocity", text="Marker Velocity")

            elif (
                nwo.marker_type
                == "_connected_geometry_marker_type_pathfinding_sphere"
            ):
                col = col.column(heading="Flags")
                col.prop(
                    nwo,
                    "marker_pathfinding_sphere_vehicle",
                    text="Vehicle Only",
                )
                col.prop(
                    nwo,
                    "pathfinding_sphere_remains_when_open",
                    text="Remains When Open",
                )
                col.prop(
                    nwo,
                    "pathfinding_sphere_with_sectors",
                    text="With Sectors",
                )
                # if ob.type != "MESH":
                #     col.prop(nwo, "marker_sphere_radius")

            elif (
                nwo.marker_type
                == "_connected_geometry_marker_type_physics_constraint"
            ):
                col.prop(
                    nwo,
                    "physics_constraint_parent",
                    text="Constraint Parent",
                )
                parent = nwo.physics_constraint_parent
                if parent is not None and parent.type == "ARMATURE":
                    col.prop_search(
                        nwo,
                        "physics_constraint_parent_bone",
                        parent.data,
                        "bones",
                        text="Bone",
                    )
                col.prop(
                    nwo,
                    "physics_constraint_child",
                    text="Constraint Child",
                )
                child = nwo.physics_constraint_child
                if child is not None and child.type == "ARMATURE":
                    col.prop_search(
                        nwo,
                        "physics_constraint_child_bone",
                        child.data,
                        "bones",
                        text="Bone",
                    )
                row = col.row()
                row.prop(
                    nwo,
                    "physics_constraint_type",
                    text="Constraint Type",
                    expand=True,
                )
                col.prop(
                    nwo,
                    "physics_constraint_uses_limits",
                    text="Uses Limits",
                )

                if nwo.physics_constraint_uses_limits:
                    if (
                        nwo.physics_constraint_type
                        == "_connected_geometry_marker_type_physics_hinge_constraint"
                    ):
                        col.prop(
                            nwo,
                            "hinge_constraint_minimum",
                            text="Minimum",
                        )
                        col.prop(
                            nwo,
                            "hinge_constraint_maximum",
                            text="Maximum",
                        )

                    elif (
                        nwo.physics_constraint_type
                        == "_connected_geometry_marker_type_physics_socket_constraint"
                    ):
                        col.prop(
                            nwo,
                            "twist_constraint_start",
                            text="Twist Start",
                        )
                        col.prop(
                            nwo,
                            "twist_constraint_end",
                            text="Twist End",
                        )
                        col.separator()
                        col.prop(nwo, "cone_angle", text="Cone Angle")
                        col.separator()
                        col.prop(
                            nwo,
                            "plane_constraint_minimum",
                            text="Plane Minimum",
                        )
                        col.prop(
                            nwo,
                            "plane_constraint_maximum",
                            text="Plane Maximum",
                        )


            # elif (
            #     nwo.marker_type
            #     == "_connected_geometry_marker_type_target"
            # ):
            #     # if ob.type != "MESH":
            #     #     col.prop(nwo, "marker_sphere_radius")

            elif nwo.marker_type == "_connected_geometry_marker_type_envfx" and h4:
                draw_tag_path(col, nwo, "marker_looping_effect")
                if nwo.marker_looping_effect.strip() and Path(utils.get_tags_path(), utils.relative_path(nwo.marker_looping_effect)).exists():
                    row.operator("nwo.open_foundation_tag", text="", icon_value=get_icon_id("foundation")).tag_path = nwo.marker_looping_effect

            elif (
                nwo.marker_type == "_connected_geometry_marker_type_lightCone" and h4
            ):
                draw_tag_path(col, nwo, "marker_light_cone_tag")
                if nwo.marker_light_cone_tag.strip() and Path(utils.get_tags_path(), utils.relative_path(nwo.marker_light_cone_tag)).exists():
                    row.operator("nwo.open_foundation_tag", text="", icon_value=get_icon_id("foundation")).tag_path = nwo.marker_light_cone_tag
                col.prop(nwo, "marker_light_cone_color", text='Color')
                # col.prop(nwo, "marker_light_cone_alpha", text='Alpha')
                col.prop(nwo, "marker_light_cone_intensity", text='Intensity')
                col.prop(nwo, "marker_light_cone_width", text='Width')
                col.prop(nwo, "marker_light_cone_length", text='Length')
                draw_tag_path(col, nwo, "marker_light_cone_curve")
                if nwo.marker_light_cone_curve.strip() and Path(utils.get_tags_path(), utils.relative_path(nwo.marker_light_cone_curve)).exists():
                    row.operator("nwo.open_foundation_tag", text="", icon_value=get_icon_id("foundation")).tag_path = nwo.marker_light_cone_curve
                
        elif utils.is_frame(ob) and utils.poll_ui(
            ("model", "scenario", "sky", "animation", "prefab")):
            col = box.column()
            col.label(text='Frame', icon_value=get_icon_id('frame'))
            col.operator("nwo.select_child_objects", icon='CON_CHILDOF')
            return
                

        if not utils.has_mesh_props(ob) or (h4 and not nwo.proxy_instance and utils.poll_ui(('scenario',)) and nwo.mesh_type == "_connected_geometry_mesh_type_structure"):
            return

        if utils.has_face_props(ob):
            self.draw_expandable_box(self.box.box(), self.scene_nwo, "mesh_properties", ob=ob)
  
        nwo = ob.data.nwo
        # Instance Proxy Operators
        if ob.type != 'MESH' or ob.nwo.mesh_type != "_connected_geometry_mesh_type_default" or not utils.poll_ui(('scenario', 'prefab')):
            return
        
        col.separator()
        self.draw_expandable_box(self.box.box(), self.scene_nwo, "instance_proxies", ob=ob)
        
    def draw_mesh_properties(self, box, ob):
        self.draw_face_material_properties(box, ob, False)
        
    def draw_material_attributes(self, box, ob):
        self.draw_face_material_properties(box, ob, True)

    def draw_face_material_properties(self, box, id, for_material):
        op_prefix = "nwo.material" if for_material else "nwo.face"
        nwo = id.nwo if for_material  else id.data.nwo
        props = nwo.material_props if for_material else nwo.face_props
        active_prop_index = nwo.material_props_active_index if for_material else nwo.face_props_active_index
        
        context = self.context
        if not for_material and id.type == 'MESH':
            box.label(text=f"Face Count: {utils.human_number(len(id.data.polygons))}", icon='FACE_MAPS')
            row = box.row()
            row.operator(f"nwo.face_attribute_count_refresh", text="Refresh Face Counts", icon='FILE_REFRESH')
            row.operator(f"nwo.face_attribute_consolidate", icon='AREA_JOIN_UP')
        
        row = box.row()
        
        if for_material:
            row.template_list(
                "NWO_UL_MaterialPropList",
                "",
                nwo,
                "material_props",
                nwo,
                "material_props_active_index",
            )
        else:
            row.template_list(
                "NWO_UL_FacePropList",
                "",
                nwo,
                "face_props",
                nwo,
                "face_props_active_index",
            )

        col = row.column(align=True)
        edit_mode = context.mode == 'EDIT_MESH'
        if for_material:
            col.menu("NWO_MT_MaterialAttributeAddMenu", text="", icon="ADD")
        else:
            col.menu("NWO_MT_FaceAttributeAddMenu", text="", icon="ADD")
            
        col.operator(f"{op_prefix}_attribute_delete", icon="REMOVE", text="")
        col.separator()
        if not for_material:
            col.operator("nwo.face_attribute_color_all", text="", icon="SHADING_RENDERED", depress=id.data.nwo.highlight).enable_highlight = not id.data.nwo.highlight
            col.separator()
        # col.operator(f"{op_prefix}_attribute_move", icon="TRIA_UP", text="").direction = "UP"
        # col.operator(f"{op_prefix}_attribute_move", icon="TRIA_DOWN", text="").direction = "DOWN"
        if not for_material:
            col.separator()
            col.menu("NWO_MT_FacePropOperatorsMenu", text="", icon='DOWNARROW_HLT')

        row = box.row()

        if not for_material:
            if id.type == 'MESH':
                if edit_mode:
                    sub = row.row(align=True)
                    sub.enabled = bool(props)
                    sub.operator("nwo.face_attribute_assign", text="Assign")
                    sub.operator("nwo.face_attribute_remove", text="Remove")
                    sub = row.row(align=True)
                    sub.enabled = bool(props)
                    sub.operator("nwo.face_attribute_select", text="Select").select = True
                    sub.operator("nwo.face_attribute_select", text="Deselect").select = False

                else:
                    sub = row.row(align=False)
                    sub.operator("nwo.face_attribute_assign", text="Assign To All Faces", icon='MESH_CUBE')
                    sub.operator("nwo.edit_face_attributes", text="Enter Edit Mode", icon="EDITMODE_HLT")

        col = box.column()
        col.use_property_split = True
        if props:
            item = props[active_prop_index]
            col.separator()
            match item.type:
                case 'face_sides':
                    col.prop(item, 'two_sided')
                    if self.h4:
                        col.prop(item, 'face_sides_type')
                case 'region':
                    row = box.row()
                    row.label(text='Region')
                    row = box.row()
                    if for_material:
                        row.menu("NWO_MT_MaterialRegions", text=item.region, icon_value=get_icon_id("region"))
                    else:
                        row.menu("NWO_MT_FaceRegions", text=item.region, icon_value=get_icon_id("region"))
                case 'global_material':
                    row = box.row(align=True)
                    row.prop(item, "global_material")
                    if utils.poll_ui(('scenario', 'prefab')):
                        if for_material:
                            row.operator("nwo.global_material_globals",text="", icon="VIEWZOOM").type = 'MATERIAL'
                        else:
                            row.operator("nwo.global_material_globals",text="", icon="VIEWZOOM").type = 'FACE'
                    else:
                        if for_material:
                            row.menu("NWO_MT_AddGlobalMaterialMaterial", text="", icon="DOWNARROW_HLT")
                        else:
                            row.menu("NWO_MT_AddGlobalMaterialFace", text="", icon="DOWNARROW_HLT")
                case 'emissive':
                    box = col.box()
                    row = box.row()
                    row.label(text="Emissive Settings")
                    row = box.row()
                    row.prop(item, "material_lighting_emissive_color", text="Color")
                    row = box.row()
                    row.prop(item, "material_lighting_emissive_power", text="Power")
                    row = box.row(align=True)
                    row.prop(item, "light_intensity", text="Intensity")
                    row = box.row()
                    row.prop(item, "material_lighting_emissive_quality", text="Quality")
                    row = box.row()
                    row.prop(item, "material_lighting_emissive_focus", text="Focus")
                    row = box.row()
                    row.prop(item, "material_lighting_attenuation_falloff", text="Light Falloff")
                    row = box.row()
                    row.prop(item, "material_lighting_attenuation_cutoff", text="Light Cutoff")
                    row = box.row()
                    row.prop(item, "material_lighting_bounce_ratio", text="Bounce Ratio",)
                    row = box.row()
                    row.prop(item, "material_lighting_use_shader_gel", text="Shader Gel")
                    row = box.row()
                    row.prop(item, "material_lighting_emissive_per_unit")
                case _:
                    col.prop(item, item.type)
            
            if not for_material:
                col: bpy.types.UILayout
                col.separator()
                col.operator("nwo.change_attribute", icon='MESH_DATA')
                
    def draw_instance_proxies(self, box, ob):
        nwo = ob.data.nwo
        collision = nwo.proxy_collision
        physics = [getattr(nwo, f"proxy_physics{i}", None) for i in range(200)]
        all_physics_slots_used = all(physics)
        cookie_cutter = nwo.proxy_cookie_cutter

        if collision:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Collision", icon_value=get_icon_id("collider")).proxy = collision.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = collision.name


        for idx, item in enumerate(physics):
            if item is not None:
                row = box.row(align=True)
                row.operator("nwo.proxy_instance_edit", text=f"Edit Proxy Physics [{idx}]", icon_value=get_icon_id("physics")).proxy = item.name
                row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = item.name

        if not self.h4 and cookie_cutter:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Cookie Cutter", icon_value=get_icon_id("cookie_cutter")).proxy = cookie_cutter.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = cookie_cutter.name

        if not (collision and all_physics_slots_used and (self.h4 or cookie_cutter)):
            row = box.row()
            row.scale_y = 1.3
            row.operator("nwo.proxy_instance_new", text="New Instance Proxy", icon="ADD")
    
    def draw_material_properties(self):
        box = self.box
        row = box.row()
        context = self.context
        ob = context.object
        h4 = self.h4
        if not ob:
            row.label(text="No active object")
            return
        ob_type = ob.type
        if ob_type not in ("MESH", "CURVE", "SURFACE", "META", "FONT"):
            row.label(text="Active object does not support materials")
            return

        mat = ob.active_material
        col1 = row.column()
        col1.template_ID(ob, "active_material", new="nwo.duplicate_material")
        if mat:
            txt = "Halo Material" if h4 else "Halo Shader"
            nwo = mat.nwo

        is_sortable = len(ob.material_slots) > 1
        rows = 3
        if is_sortable:
            rows = 5

        row = box.row()

        row.template_list(
            "MATERIAL_UL_matslots",
            "",
            ob,
            "material_slots",
            ob,
            "active_material_index",
            rows=rows,
        )

        col = row.column(align=True)
        col.operator("object.material_slot_add", icon="ADD", text="")
        col.operator("object.material_slot_remove", icon="REMOVE", text="")

        col.separator()

        col.menu("MATERIAL_MT_context_menu", icon="DOWNARROW_HLT", text="")

        if is_sortable:
            col.separator()

            col.operator(
                "object.material_slot_move", icon="TRIA_UP", text=""
            ).direction = "UP"
            col.operator(
                "object.material_slot_move", icon="TRIA_DOWN", text=""
            ).direction = "DOWN"

        row = box.row()

        if ob.mode == "EDIT":
            row = box.row(align=True)
            row.operator("object.material_slot_assign", text="Assign")
            row.operator("object.material_slot_select", text="Select")
            row.operator("object.material_slot_deselect", text="Deselect")
        if mat:
            tag_type = "Material" if h4 else "Shader"
            col = box.column()
            if nwo.SpecialMaterial:
                if mat.name.startswith('+seamsealer'):
                    col.label(text=f'SeamSealer Material applied')
                elif mat.name.startswith('+seam'):
                    col.label(text=f'Seam Material applied')
                else:
                    col.label(text=f'Sky Material applied')
                    sky_perm = utils.get_sky_perm(mat)
                    if sky_perm > -1:
                        if sky_perm > 31:
                            col.label(text='Maximum Sky Permutation Index is 31', icon='ERROR')
                        else:
                            col.label(text=f"Sky Permutation {str(sky_perm)}")
                    if not h4:
                        col.operator("nwo.set_sky", text="Set Sky Permutation")
                return
            elif nwo.ConventionMaterial:
                return col.label(text=f'Non-Rendered {tag_type} applied')
            else:
                col.label(text=f"{txt} Path")
                row = col.row(align=True)
                row.prop(nwo, "shader_path", text="", icon_value=get_icon_id("tags"))
                row.operator("nwo.shader_finder_single", icon_value=get_icon_id("material_finder"), text="")
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "shader_path"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'shader_path'
                has_valid_path = nwo.shader_path and Path(utils.get_tags_path(), utils.relative_path(nwo.shader_path)).exists()
                if has_valid_path:
                    col.separator()
                    # row.scale_y = 1.5
                    col.operator(
                        "nwo.open_halo_material",
                        icon_value=get_icon_id("foundation"),
                        text=f"Open {txt} Tag"
                    )
                    shader_path = mat.nwo.shader_path
                    full_path = Path(utils.get_tags_path(), shader_path)
                    if full_path.exists():
                        col.operator('nwo.shader_to_nodes', text=f"Convert {txt} to Blender Material", icon='NODE_MATERIAL').mat_name = mat.name
                    col.separator()
                    
                    col.separator()
                    col = box.column()
                    col.label(text=f'{txt} Export Tools')
                    col.operator("nwo.shader_duplicate", icon='DUPLICATE')
                    if utils.material_read_only(nwo.shader_path):
                        col.label(text=f"{txt} is read only")
                        return
                    col.prop(nwo, "uses_blender_nodes", text=f"Link Tag to Nodes", icon='NODETREE')
                    if nwo.uses_blender_nodes:
                        col.operator("nwo.build_shader_single", text=f"Update {tag_type} Tag", icon_value=get_icon_id("material_exporter")).linked_to_blender = True
                        col.separator()
                        if h4:
                            row = col.row(align=True)
                            row.prop(nwo, "material_shader", text="Default Shader")
                            row.operator("nwo.get_material_shaders", icon="VIEWZOOM", text="").batch_panel = False
                        else:
                            col.prop(nwo, "shader_type", text="Shader Type")

                else:
                    if nwo.shader_path:
                        col.label(text=f"{txt} Tag Not Found", icon="ERROR")
                    else:
                        col.separator()
                        col.label(text=f'{txt} Export Tools')
                        row = col.row()
                        row.operator("nwo.build_shader_single", text=f"New Empty {tag_type} Tag", icon_value=get_icon_id("material_exporter")).linked_to_blender = False
                        row.operator("nwo.build_shader_single", text=f"New Linked {tag_type} Tag", icon_value=get_icon_id("material_exporter")).linked_to_blender = True
                        col.separator()
                        col_props = col.column()
                        col_props.use_property_split = True
                        if h4:
                            row = col_props.row(align=True)
                            row.prop(nwo, "material_shader", text="Default Shader")
                            row.operator("nwo.get_material_shaders", icon="VIEWZOOM", text="")
                        else:
                            col_props.prop(nwo, "shader_type", text="Shader Type")

            # TEXTURE PROPS
            # First validate if Material has images
            if mat.node_tree:
                if utils.recursive_image_search(mat):
                    self.draw_expandable_box(self.box.box(), self.scene_nwo, "image_properties", material=mat)
            
            self.draw_expandable_box(self.box.box(), self.scene_nwo, "material_attributes", material=mat)

                
    def draw_image_properties(self, box, mat):
        box.use_property_split = False
        nwo = mat.nwo
        col = box.column()
        image = nwo.active_image
        col.template_ID_preview(nwo, "active_image")
        if not image:
            return
        bitmap = image.nwo
        editor = self.context.preferences.filepaths.image_editor
        if editor and image.filepath and Path(image.filepath_from_user()).exists():
            col.separator()
            end_part = utils.os_sep_partition(editor.lower(), True).strip("\"'")
            if "photoshop" in end_part:
                editor_name = "Photoshop"
                editor_icon = "photoshop"
            elif "gimp" in end_part:
                editor_name = "Gimp"
                editor_icon = "paint" # gimp
            elif "paint" in end_part:
                editor_name = "Paint"
                editor_icon = "paint"
            elif "affinity" in end_part:
                editor_name = "Affinity"
                editor_icon = "affinity"
            else:
                editor_name = "Image Editor"
                editor_icon = ""
            col.operator("nwo.open_image_editor", text=f"Open in {editor_name}", icon_value=get_icon_id(editor_icon))

        tags_dir = utils.get_tags_path()
        data_dir = utils.get_data_path()
        if bitmap.filepath:
            bitmap_path = str(Path(bitmap.filepath).with_suffix(".bitmap"))
            if not Path(tags_dir, bitmap_path).exists():
                bitmap_path = utils.dot_partition(image.filepath_from_user().lower().replace(data_dir, "")) + '.bitmap'
        else:
            bitmap_path = utils.dot_partition(image.filepath_from_user().lower().replace(data_dir, "")) + '.bitmap'

        if not Path(tags_dir, bitmap_path).exists():
            col.separator()
            col.label(text='Bitmap Export Tools')
            col.operator("nwo.export_bitmaps_single", text="Export Bitmap", icon_value=get_icon_id("texture_export"))
            col.separator()
            col_props = col.column()
            col_props.use_property_split = True
            col_props.prop(bitmap, "bitmap_type", text="Type")
            return
        col.separator()
        col.operator("nwo.open_foundation_tag", text="Open Bitmap Tag", icon_value=get_icon_id("foundation")).tag_path = bitmap_path
        col.separator()
        col.label(text='Bitmap Export Tools')
        col.prop(bitmap, "export", text="Link Bitmap to Blender Image", icon="TEXTURE")
        if bitmap.export:
            col.operator("nwo.export_bitmaps_single", text="Update Bitmap", icon_value=get_icon_id("texture_export"))
            col.separator()
            col_props = col.column()
            col_props.use_property_split = True
            col_props.prop(bitmap, "bitmap_type", text="Type")
            col_props.prop(bitmap, "reexport_tiff", text="Always Export Image")
            
    def draw_cinematic_events(self, nwo, ob, box):
        row = box.row()
        row.template_list(
            "NWO_UL_CinematicEvents",
            "",
            nwo,
            "cinematic_events",
            nwo,
            "active_cinematic_event_index",
        )
        col = row.column(align=True)
        col.operator("nwo.cinematic_event_add", icon="ADD", text="")
        col.operator("nwo.cinematic_event_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.cinematic_events_clear", icon="CANCEL", text="")
        
        if not (nwo.cinematic_events and nwo.active_cinematic_event_index > -1):
            return
        
        col = box.column()
        col.use_property_split = True
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        row = col.row()
        row.use_property_split = False
        row.prop(event, "type", expand=True)
        row = col.row(align=True)
        row.prop(event, "frame", text="Fallback Frame" if event.type == 'DIALOGUE' and event.sound_strip else "Frame")
        row.operator("nwo.cinematic_event_set_frame", text="", icon="KEYFRAME_HLT")
        match event.type:
            case 'DIALOGUE':
                draw_tag_path(col, event, "sound_tag")
                draw_tag_path(col, event, "female_sound_tag")
                col.prop(event, "sound_scale")
                col.prop(event, "lipsync_actor")
                row = col.row(align=True)
                row.prop(event, "default_sound_effect")
                row.operator_menu_enum("nwo.get_sound_effects", "fx", icon="DOWNARROW_HLT", text="")
                col.prop(event, "subtitle")
                col.prop(event, "female_subtitle")
                col.prop(event, "subtitle_character")
                col.prop_search(
                    event,
                    "sound_strip",
                    self.scene.sequence_editor,
                    "strips_all",
                    text="Sound Strip",
                    icon='PLAY_SOUND'
                )
            case 'EFFECT':
                draw_tag_path(col, event, "effect")
                col.prop(event, "marker")
                col.prop(event, "marker_name")
                if self.h4:
                    col.prop(event, "function_a")
                    col.prop(event, "function_b")
                    col.prop(event, "looping")
            case 'SCRIPT':
                col.prop(event, "script_type")
                get_item_available = False
                ob = event.script_object
                if ob is not None:
                    tag_path = ob.nwo.cinematic_object
                    if tag_path.strip():
                        path = Path(utils.get_tags_path(), utils.relative_path(tag_path))
                        get_item_available = path.exists() and path.is_file()
                        
                match event.script_type:
                    case 'CUSTOM':
                        row = col.row()
                        row.prop(event, "script")
                        row.enabled = event.text is None
                        col.prop(event, "text")
                    case 'WEAPON_TRIGGER_START' | 'WEAPON_TRIGGER_STOP':
                        col.prop(event, "script_object", text="Weapon")
                    case 'SET_VARIANT':
                        col.prop(event, "script_object", text="Object")
                        row = col.row()
                        row.prop(event, "script_variant", text="Variant")
                        if get_item_available:
                            row.operator_menu_enum("nwo.get_cinematic_variant", "item", icon="DOWNARROW_HLT", text="")
                    case 'SET_PERMUTATION':
                        col.prop(event, "script_object", text="Object")
                        row = col.row()
                        row.prop(event, "script_region", text="Region")
                        if get_item_available:
                            row.operator_menu_enum("nwo.get_cinematic_region", "item", icon="DOWNARROW_HLT", text="")
                        row = col.row()
                        row.prop(event, "script_permutation", text="Permutation")
                        if get_item_available:
                            row.operator_menu_enum("nwo.get_cinematic_permutation", "item", icon="DOWNARROW_HLT", text="")
                    case 'SET_REGION_STATE':
                        col.prop(event, "script_object", text="Object")
                        row = col.row()
                        row.prop(event, "script_region", text="Region")
                        if get_item_available:
                            row.operator_menu_enum("nwo.get_cinematic_region", "item", icon="DOWNARROW_HLT", text="")
                        col.prop(event, "script_state", text="State")
                    case 'SET_MODEL_STATE_PROPERTY':
                        col.prop(event, "script_object", text="Object")
                        col.prop(event, "script_state_property", text="State Property")
                        col.prop(event, "script_bool", text="On")
                    case 'HIDE' | 'UNHIDE' | 'DESTROY' | 'OBJECT_CANNOT_DIE' | 'OBJECT_CAN_DIE' | 'OBJECT_PROJECTILE_COLLISION_ON' | 'OBJECT_PROJECTILE_COLLISION_OFF':
                        col.prop(event, "script_object", text="Object")
                    case 'DAMAGE_OBJECT':
                        col.prop(event, "script_object", text="Object")
                        row = col.row()
                        row.prop(event, "script_region", text="Region")
                        if get_item_available:
                            row.operator_menu_enum("nwo.get_cinematic_region", "item", icon="DOWNARROW_HLT", text="")
                        col.prop(event, "script_damage", text="Damage")
                    case 'FADE_IN' | 'FADE_OUT':
                        col.prop(event, "script_color", text="Color")
                        col.prop(event, "script_seconds", text="Seconds")
                    case 'SET_TITLE':
                        col.prop(event, "script_text", text="Title String ID")
                    case 'PLAY_SOUND':
                        draw_tag_path(col, event, "sound_tag")
                        col.prop(event, "script_object", text="Object")
                        col.prop(event, "script_factor", text="Sound Scale")

    def draw_animation_manager(self):
        box = self.box
        
        context = self.context
        ob = context.object
        scene_nwo = utils.get_scene_props()
        
        if self.asset_type == 'cinematic':
            return self.draw_cinematic_events(self.context.scene.nwo, ob, box) # cinematic events are scene specific
        
        row = box.row()
        if not scene_nwo.animations:
            box.operator("nwo.new_animation", icon="ANIM", text="New Animation")
            box.operator("nwo.select_armature", text="Select Armature", icon='OUTLINER_OB_ARMATURE')
            box.operator("nwo.animations_from_actions", icon='UV_SYNC_SELECT')
            box.operator("nwo.animations_from_blend", icon='IMPORT')
            return

        row.template_list(
            "NWO_UL_AnimationList",
            "",
            scene_nwo,
            "animations",
            scene_nwo,
            "active_animation_index",
        )
        
        col = row.column(align=True)
        col.operator("nwo.new_animation", icon="ADD", text="")
        col.operator("nwo.delete_animation", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.unlink_animation", icon="X", text="")
        col.separator()
        col.operator("nwo.set_timeline", text="", icon='TIME')
        if not ob or ob.type != "ARMATURE":
            col.separator()
            col.operator("nwo.select_armature", text="", icon='OUTLINER_OB_ARMATURE')
            
        col.separator()
        col.menu("NWO_MT_AnimationTools", text="", icon='DOWNARROW_HLT')
        
        col = box.column()
        row = col.row()
        
        if scene_nwo.active_animation_index < 0:
            col.label(text="No Animation Selected")
            return
        
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        
        col = box.column()
        row = col.row()
        row.use_property_split = True
        row.prop(animation, "animation_type")
        
        is_composite = animation.animation_type == 'composite'
        
        if is_composite:
            if self.h4:
                return self.draw_animation_composites(box, animation)
            else:
                return col.label(text="Composite animations not valid for Reach")
        
        elif animation.animation_type != 'world':
            row = col.row()
            row.use_property_split = True
            if animation.animation_type == 'base':
                row.prop(animation, 'animation_movement_data')     
            elif animation.animation_type == 'replacement':
                row.prop(animation, 'animation_space', expand=True)
            row = col.row()
            row.use_property_split = True
            row.prop(animation, "compression", text="Compression")
            col.separator()
            row = col.row(align=False)
            row.use_property_split = False
            row.prop(animation, "frame_start", text='Start Frame', icon='KEYFRAME_HLT')
            row.prop(animation, "frame_end", text='End Frame', icon='KEYFRAME_HLT')
            tokens = utils.tokenise(animation.name)
            if tokens[0] == "suspension":
                col.separator()
                row = col.row()
                row.use_property_split = True
                row.prop(animation, "suspension_marker", icon='OUTLINER_OB_EMPTY')
                col.separator()
                row = col.row()
                row.use_property_split = True
                row.prop(animation, "suspension_contact_marker", icon='OUTLINER_OB_EMPTY')
                col.separator()
                row = col.row()
                row.use_property_split = True
                row.prop_search(animation, "suspension_destroyed_region_name", scene_nwo, "regions_table")
                if animation.suspension_destroyed_region_name:
                    col.separator()
                    row = col.row()
                    row.use_property_split = True
                    row.prop(animation, "suspension_destroyed_contact_marker", icon='OUTLINER_OB_EMPTY')
                
            col.separator()
            row = col.row()
            row.use_property_split = True
            if animation.animation_type == 'overlay':
                col.operator('nwo.generate_poses', text='Generate Poses', icon='ANIM')
                
        col.separator()
        if animation.external:
            col.prop(animation, "external")
            col.prop(animation, "pose_overlay")
            col.prop(animation, "gr2_path")
            col.operator("nwo.open_external_animation_blend", icon='BLENDER')
        else:
            row = col.row()
            row.label(text="Action Tracks")
            row = col.row()
            rows = 3
            row.template_list(
                "NWO_UL_ActionTrack",
                "",
                animation,
                "action_tracks",
                animation,
                "active_action_group_index",
                rows=rows,
            )
            if ob is not None:
                col.label(text=f"Current Action: {ob.name} -> {ob.animation_data.action.name if ob.animation_data and ob.animation_data.action else 'NONE'}")
                if ob.type == 'MESH' and ob.data.shape_keys:
                    col.label(text=f"Current Shape Key Action: {ob.name} -> {ob.data.shape_keys.animation_data.action.name if ob.data.shape_keys.animation_data and ob.data.shape_keys.animation_data.action else 'NONE'}")
            col = row.column(align=True)
            col.operator("nwo.action_track_add", text="", icon="ADD")
            col.operator("nwo.action_track_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.action_track_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.action_track_move", icon="TRIA_DOWN", text="").direction = 'down'
            
            col = box.column(align=True)
            col.separator()
            row = col.row()
            row.operator("nwo.animation_move_to_own_blend", icon='BLENDER')
            row.operator("nwo.animation_link_to_gr2", icon='LINKED')
            col.separator()
            row = col.row()
            row.operator("nwo.animation_frames_sync_to_keyframes", text="Sync Frame Range to Keyframes", icon='FILE_REFRESH', depress=scene_nwo.keyframe_sync_active)
            row.operator("nwo.action_tracks_set_active", icon='ACTION_TWEAK')
            col.separator()
            col.separator()
            
        row = col.row()
        # ANIMATION RENAMES
        if not animation.animation_renames:
            row.operator("nwo.animation_rename_add", text="New Rename", icon_value=get_icon_id('animation_rename'))
        else:
            rename_box = box.box()
            col = rename_box.column()
            row = col.row()
            row.label(text="Animation Renames")
            row = col.row()
            rows = 3
            row.template_list(
                "NWO_UL_AnimationRename",
                "",
                animation,
                "animation_renames",
                animation,
                "active_animation_rename_index",
                rows=rows,
            )
            col = row.column(align=True)
            col.operator("nwo.animation_rename_add", text="", icon="ADD")
            col.operator("nwo.animation_rename_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_rename_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_rename_move", icon="TRIA_DOWN", text="").direction = 'down'

        # ANIMATION EVENTS
        if not animation.animation_events:
            if animation.animation_renames:
                row = box.row()
            row.operator("nwo.animation_event_list_add", text="New Event", icon_value=get_icon_id('animation_event'))
            if bpy.ops.nwo.paste_events.poll():
                row.operator("nwo.paste_events", icon="PASTEDOWN")
        else:
            box = box.box()
            row = box.row()
            row.label(text="Animation Events")
            row = box.row()
            rows = 3
            row.template_list(
                "NWO_UL_AnimProps_Events",
                "",
                animation,
                "animation_events",
                animation,
                "active_animation_event_index",
                rows=rows,
            )

            col = row.column(align=True)
            col.operator("nwo.animation_event_list_add", icon="ADD", text="")
            col.operator("nwo.animation_event_list_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_event_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_event_move", icon="TRIA_DOWN", text="").direction = 'down'
            
            row = box.row()
            row.operator("nwo.copy_events", icon="COPYDOWN")
            row.operator("nwo.paste_events", icon="PASTEDOWN")
            row = box.row()
            row.operator("nwo.export_animation_frame_events", icon="EXPORT")

            if animation.animation_events:
                item = animation.animation_events[animation.active_animation_event_index]
                # row = layout.row()
                # row.prop(item, "name") # debug only
                flow = box.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=True,
                    even_rows=False,
                    align=False,
                )
                col = flow.column()
                col.use_property_split = True
                col.prop(item, "event_type")
                if item.event_type == '_connected_geometry_animation_event_type_frame':
                    row = col.row()
                    row.prop(item, "multi_frame", expand=True)
                    if item.multi_frame == "range":
                        row = col.row(align=True)
                        row.prop(item, "frame_frame", text="Frame Start")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                        row = col.row(align=True)
                        row.prop(item, "frame_range", text="Frame End")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_range"
                    else:
                        row = col.row(align=True)
                        row.prop(item, "frame_frame")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                        
                    col.prop(item, "frame_name", text="Event")
                    
                    
                    if item.event_data:
                        box = box.box()
                        row = box.row()
                        row.label(text="Animation Event Data")
                        row = box.row()
                        rows = 3
                        row.template_list(
                            "NWO_UL_AnimProps_EventsData",
                            "",
                            item,
                            "event_data",
                            item,
                            "active_event_data_index",
                            rows=rows,
                        )
                        col = row.column(align=True)
                        col.operator("nwo.add_animation_event_data", icon="ADD", text="")
                        col.operator("nwo.remove_animation_event_data", icon="REMOVE", text="")
                        
                        data = item.event_data[item.active_event_data_index]
                        
                        col = box.column()
                        col.separator()
                        col.use_property_split = True
                        row = col.row()
                        row.use_property_split = False
                        row.prop(data, "data_type", expand=True)
                        col.separator()
                        col.prop(data, "frame_offset")
                        col.separator()
                        if data.data_type == 'DIALOGUE':
                            col.prop(data, "dialogue_event")
                            col.prop(data, "damage_effect_reporting_type")
                        else:
                            if data.data_type == 'EFFECT':
                                draw_tag_path(col, data, "event_effect_tag")
                                col.prop(data, "marker")
                            else:
                                draw_tag_path(col, data, "event_sound_tag")
                                col.prop(data, "marker")
                            col.separator()
                            if self.h4:
                                draw_tag_path(col, data, "event_model")
                                col.prop(data, "variant")
                            col.separator()
                            col.prop(data, "flag_allow_on_player")
                            col.prop(data, "flag_left_arm_only")
                            col.prop(data, "flag_right_arm_only")
                            col.prop(data, "flag_first_person_only")
                            col.prop(data, "flag_third_person_only")
                            col.prop(data, "flag_forward_only")
                            col.prop(data, "flag_reverse_only")
                            col.prop(data, "flag_fp_no_aged_weapons")
                        
                        
                        
                    else:
                        box.operator("nwo.add_animation_event_data", icon="ADD", text="Add Event Data")
                    
                elif (
                    item.event_type
                    == "_connected_geometry_animation_event_type_wrinkle_map"
                ):
                    row = col.row(align=True)
                    col.prop(item, "wrinkle_map_face_region", text="Face Region")
                    col.prop(item, "event_value", text="Wrinkle Map Factor")
                elif (
                    item.event_type
                    == "_connected_geometry_animation_event_type_import"
                ):
                    row = col.row(align=True)
                    row.prop(item, "frame_frame", text="Frame")
                    row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                    col.prop(item, "import_name")
                elif item.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                    valid_ik_chains = [chain for chain in scene_nwo.ik_chains if chain.start_node and chain.effector_node]
                    if not valid_ik_chains:
                        col.label(text='Add IK Chains in the Asset Editor tab', icon='ERROR')
                        return
                    col.prop(item, "ik_chain")
                    # col.prop(item, "ik_active_tag")
                    # col.prop(item, "ik_target_tag")
                    col.prop(item, "ik_target_marker", icon_value=get_icon_id('marker'))
                    col.prop(item, "ik_target_marker_name_override")
                    col.prop(item, "ik_target_usage")
                    col.prop(item, 'event_value', text="IK Influence")
                    col.prop(item, 'ik_pole_vector')
                    # col.prop(item, "ik_proxy_target_id")
                    # col.prop(item, "ik_pole_vector_id")
                    # col.prop(item, "ik_effector_id")
                elif (
                    item.event_type
                    == "_connected_geometry_animation_event_type_object_function"
                ):
                    col.prop(item, "object_function_name")
                    col.prop(item, "event_value", text="Function Value")
                elif (
                    item.event_type
                    == "_connected_geometry_animation_event_type_import"
                ):
                    col.prop(item, "frame_frame")
                    col.prop(item, "import_name")

    def draw_tools(self):
        nwo = self.scene_nwo
        shader_type = "Material" if self.h4 else "Shader"
        self.draw_expandable_box(self.box.box(), nwo, "asset_shaders", f"Asset {shader_type}s")
        self.draw_expandable_box(self.box.box(), nwo, "importer")
        self.draw_expandable_box(self.box.box(), nwo, "camera_sync")
        self.draw_expandable_box(self.box.box(), nwo, "animation_tools")
        if utils.poll_ui(('model', 'animation', 'sky', 'resource')):
            self.draw_expandable_box(self.box.box(), nwo, "rig_tools")
        self.draw_expandable_box(self.box.box(), nwo, "scenario_tools", "Scenario Tools")
        self.draw_expandable_box(self.box.box(), nwo, "cache_tools", "MCC Tools")
            
    def draw_scenario_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        # col.operator('nwo.auto_seam', text='Auto-Seam', icon_value=get_icon_id('seam'))
        col.operator('nwo.cubemap', text='Cubemap Farm', icon_value=get_icon_id("cubemap"))
        col.operator('nwo.instance_imposter_generate', text='Imposter Farm', icon_value=get_icon_id('imposter'))
        col.operator('nwo.generate_wetness_data', text='Generate Wetness Data', icon='MOD_FLUIDSIM')
        
    def draw_cache_tools(self, box, nwo):
        col = box.column()
        col.operator("nwo.cache_build", icon_value=get_icon_id("excession"))
        col.operator("nwo.launch_mcc", icon_value=get_icon_id("tag_test"))
        if bpy.ops.nwo.open_mod_folder.poll():
            col.operator("nwo.open_mod_folder", icon='FILE_FOLDER')
        
    def draw_camera_sync(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        if self.scene_nwo.camera_sync_active:
            col.operator("nwo.camera_sync", icon="PAUSE", depress=True).cancel_sync = True
        else:
            col.operator("nwo.camera_sync", icon="PLAY")
            
        if self.h4:
            col.operator("nwo.launch_sapien", text="Launch Sapien", icon_value=get_icon_id("sapien")).ignore_play = True
        else:
            col.operator("nwo.launch_tagtest", text="Launch Game", icon_value=get_icon_id("tag_test")).ignore_play = True
        
    def draw_importer(self, box, nwo):
        row = box.row()
        col = row.column()
        if self.self.scene_nwo.asset_type == 'cinematic':
            col.operator('nwo.foundry_import', text="Import Cinematic Objects", icon='IMPORT').scope = 'object'
            col.operator('nwo.foundry_import', text="Import Cinematic Scenarios", icon='IMPORT').scope = 'scenario'
        else:
            amf_installed = utils.amf_addon_installed()
            toolset_installed = utils.blender_toolset_installed()
            col.operator('nwo.foundry_import', text="Import Models & Animations", icon='IMPORT').scope = 'amf,jma,jms,model,render_model,scenario,scenario_structure_bsp,particle_model,animation,prefab,structure_design,polyart_asset,decorator_set,cinematic'
            if not toolset_installed:
                col.label(text="Halo Blender Toolset required for import of JMS/JMA/ASS files")
                col.operator("nwo.open_url", text="Download", icon="BLENDER").url = BLENDER_TOOLSET
            if not amf_installed:
                col.label(text="AMF Importer required to import amf files")
                col.operator("nwo.open_url", text="Download", icon_value=get_icon_id("amf")).url = AMF_ADDON
                
            col.operator('nwo.foundry_import', text="Import Bitmaps", icon='IMAGE_DATA').scope = 'bitmap'
            col.operator('nwo.rename_import', text="Import Animation Renames & Copies", icon_value=get_icon_id("animation_rename"))
            col.operator("nwo.convert_scene", text="Convert Scene", icon='RIGHTARROW')
        
    def draw_rig_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        col.use_property_split = True
        col.operator('nwo.validate_rig', text='Validate Rig', icon='ARMATURE_DATA')
        if nwo.multiple_root_bones:
            col.label(text='Multiple Root Bones', icon='ERROR')
        if nwo.armature_has_parent:
            col.label(text='Armature is parented', icon='ERROR')
        if nwo.armature_bad_transforms:
            col.label(text='Armature has bad transforms', icon='ERROR')
            col.operator('nwo.fix_armature_transforms', text='Fix Armature Transforms', icon='SHADERFX')
        if nwo.invalid_root_bone:
            col.label(text='Root Bone has non-standard transforms', icon='QUESTION')
            col.operator('nwo.fix_root_bone', text='Fix Root Bone', icon='SHADERFX')
        # if nwo.needs_pose_bones:
        #     col.label(text='Rig not setup for pose overlay animations', icon='ERROR')
        #     col.operator('nwo.add_pose_bones', text='Fix for Pose Overlays', icon='SHADERFX')
        if nwo.pose_bones_bad_transforms:
            col.label(text='Pose bones have bad transforms', icon='ERROR')
            col.operator('nwo.fix_pose_bones', text='Fix Pose Bones', icon='SHADERFX')
        if nwo.too_many_bones:
            col.label(text='Rig exceeds the maxmimum number of bones', icon='ERROR')
        if nwo.bone_names_too_long:
            col.label(text='Rig has bone names that exceed 31 characters', icon='ERROR')
            
    def draw_animation_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        col.use_property_split = True
        col.operator("nwo.movement_data_transfer", icon='GRAPH')
        col.operator("nwo.convert_legacy_pose_overlays", icon='GRAPH', text="Convert Legacy Pose Overlays")
        self.draw_expandable_box(box.box(), nwo, "game_animation_copy_settings")
        
    def draw_game_animation_copy_settings(self, box, nwo):
        row = box.row()
        col = row.column()
        col.use_property_split = True
        col.prop(nwo, "animation_cmd_object_type")
        if nwo.animation_cmd_object_type != "player":
            col.prop(nwo, "animation_cmd_expression")
        col.prop(nwo, "animation_cmd_loop")
        
        draw_tag_path(col, nwo, "animation_cmd_path", set_row_split=True)
        if nwo.animation_cmd_path.strip() and Path(utils.get_tags_path(), utils.relative_path(nwo.animation_cmd_path)).exists():
            row.operator("nwo.open_foundation_tag", text="", icon_value=get_icon_id("foundation")).tag_path = nwo.animation_cmd_path
            row = col.row(align=True)
            row.use_property_split = True
            row.prop(nwo, "animation_cmd_name")
            row.operator("nwo.animation_name_search", text="", icon="VIEWZOOM")
        else:
            col.prop(nwo, "animation_cmd_name")
        
        col.operator("nwo.play_game_animation", icon='COPYDOWN')

    def draw_asset_shaders(self, box, nwo):
        h4 = self.h4
        count, total = utils.get_halo_material_count()
        shader_type = "Material" if h4 else "Shader"
        # if total:
        row = box.row()
        col = row.column()
        col.use_property_split = True
        # col.separator()
        col.label(
            text=f"{count}/{total} {shader_type} tag paths found",
            icon='CHECKMARK' if total == count else 'ERROR'
        )
        row = col.row(align=True)
        col.operator("nwo.shader_finder", text=f"Find Missing {shader_type}s", icon_value=get_icon_id("material_finder"))
        col.operator("nwo.shader_farm", text=f"Batch Build {shader_type}s", icon_value=get_icon_id("material_exporter"))
        col.separator()
        col.operator("nwo.shader_to_nodes_bulk", text=f"Convert {shader_type}s to Blender Materials", icon='NODE_MATERIAL')
        col.operator("nwo.build_shader_templates", text=f"Generate Missing Shader Templates", icon='VIEWZOOM')
        col.separator()
        col.operator("nwo.stomp_materials", text=f"Remove Duplicate Materials", icon='X')
        col.operator("nwo.clear_shader_paths", text=f"Clear {shader_type} Paths", icon='X')
        col.separator()
        col.operator("nwo.append_foundry_materials", text="Append Special Materials", icon_value=get_icon_id("special_material"))
        col.operator("nwo.append_grid_materials", text="Append Grid Materials", icon_value=get_icon_id("grid_material"))
        if h4:
            col.separator()
            col.operator("nwo.open_matman", text="Open Material Tag Viewer", icon_value=get_icon_id("foundation"))

    def draw_help(self):
        self.box.operator("extensions.userpref_show_for_update", text="Check for Update", icon_value=get_icon_id("foundry"))
        box_websites = self.box.box()
        box_websites.label(text="Foundry Documentation")
        col = box_websites.column()
        col.operator("nwo.open_url", text="Documentation", icon_value=get_icon_id("c20_reclaimers")).url = FOUNDRY_DOCS
        col.operator("nwo.open_url", text="Github", icon_value=get_icon_id("github")).url = FOUNDRY_GITHUB

        box_hotkeys = self.box.box()
        box_hotkeys.label(text="Keyboard Shortcuts")
        col = box_hotkeys.column()
        col.direction
        for shortcut in HOTKEYS:
            col.operator("nwo.describe_hotkey", emboss=False, text=shortcut[0].replace("_", " ").title() + " : " + shortcut[1]).hotkey = shortcut[0]

        box_downloads = self.box.box()
        box_downloads.label(text="Other Resources")
        col = box_downloads.column()
        col.operator("nwo.open_url", text="Halo Blender Toolset", icon="BLENDER").url = BLENDER_TOOLSET
        col.operator("nwo.open_url", text="AMF Importer", icon_value=get_icon_id("amf")).url = AMF_ADDON
        col.operator("nwo.open_url", text="Reclaimer", icon_value=get_icon_id("marathon")).url = RECLAIMER
        col.operator("nwo.open_url", text="Animation Repository", icon_value=get_icon_id("github")).url = ANIMATION_REPO
        self.box.operator('nwo.register_icons', icon='FILE_REFRESH')

    def draw_settings(self):
        prefs = utils.get_prefs()
        # box = self.box.box()
        context = self.context
        # box.label(text=update_str, icon_value=get_icon_id("foundry"))
        # if update_needed:
        #     box.operator("nwo.open_url", text="Get Latest", icon_value=get_icon_id("github")).url = FOUNDRY_GITHUB

        box = self.box.box()
        row = box.row()
        row.label(text="Projects")
        row = box.row()
        rows = 5
        row.template_list(
            "NWO_UL_Projects",
            "",
            prefs,
            "projects",
            prefs,
            "current_project_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.project_add", text="", icon="ADD")
        col.operator("nwo.project_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.project_edit", icon="SETTINGS", text="")
        col.separator()
        col.operator("nwo.project_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.project_move", icon="TRIA_DOWN", text="").direction = 'down'
        row = box.row(align=True, heading="Tool Version")
        row.prop(prefs, "tool_type", expand=True)
        # row = box.row(align=True, heading="Default Scene Matrix")
        # row.prop(prefs, "scene_matrix", expand=True)
        row = box.row(align=True, heading="Default Object Prefixes")
        row.prop(prefs, "apply_prefix", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "apply_materials", text="Update Materials on Object Type Change")
        row = box.row(align=True)
        row.prop(prefs, "apply_empty_display")
        row = box.row(align=True)
        row.prop(prefs, "toolbar_icons_only", text="Foundry Toolbar Icons Only")
        row = box.row(align=True)
        row.prop(prefs, "protect_materials")
        row = box.row(align=True)
        row.prop(prefs, "update_materials_on_shader_path")
        row = box.row(align=True)
        row.prop(prefs, "sync_timeline_range")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_export")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_launch")
        row = box.row(align=True)
        row.prop(prefs, "import_shaders_with_time_period")
        row = box.row(align=True)
        row.prop(prefs, "allow_tool_patches")
        row = box.row(align=True)
        row.prop(prefs, "granny_viewer_path")
        blend_prefs = context.preferences
        if blend_prefs.use_preferences_save and (not bpy.app.use_userpref_skip_save_on_exit):
            return
        row = box.row()
        row.operator("wm.save_userpref", text=("Save Foundry Settings") + (" *" if blend_prefs.is_dirty else ""))


    def draw_table_menus(self, col, nwo, ob):
        perm_name = "Permutation"
        region_name = "Region"
        is_mesh = utils.is_mesh(ob)
        is_seam = nwo.mesh_type == "_connected_geometry_mesh_type_seam" and utils.is_mesh(ob)
        if utils.poll_ui(("scenario",)):
            perm_name = "Layer"
            if is_seam:
                region_name = "Frontfacing BSP"
            else:
                region_name = "BSP"
        elif utils.poll_ui(('model',)) and utils.is_mesh(ob):
            if ob.data.nwo.face_props and nwo.mesh_type in ('_connected_geometry_mesh_type_object_structure', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default'):
                for prop in ob.data.nwo.face_props:
                    if prop.type == 'region':
                        region_name += '*'
                        break

        row = col.row()
        split = row.split()
        col1 = split.column()
        col2 = split.column()
        if is_seam and not nwo.seam_back_manual:
            col3 = split.column()
        col1.enabled = not nwo.region_name_locked
        if is_seam and not nwo.seam_back_manual:
            col3.enabled = not nwo.permutation_name_locked
        else:
            col2.enabled = not nwo.permutation_name_locked
        col1.label(text=region_name, icon_value=get_icon_id("collection_creator") if nwo.region_name_locked else 0)
        if is_seam and not nwo.seam_back_manual:
            col2.label(text="Backfacing BSP", icon_value=get_icon_id("collection_creator") if nwo.permutation_name_locked else 0)
            col3.label(text=perm_name, icon_value=get_icon_id("collection_creator") if nwo.permutation_name_locked else 0)
        else:
            col2.label(text=perm_name, icon_value=get_icon_id("collection_creator") if nwo.permutation_name_locked else 0)
        col1.menu("NWO_MT_Regions", text=utils.true_region(nwo), icon_value=get_icon_id("region"))
        if is_seam and not nwo.seam_back_manual:
            if utils.true_region(nwo) == nwo.seam_back:
                col2.menu("NWO_MT_SeamBackface", text="", icon='ERROR')
            else:
                col2.menu("NWO_MT_SeamBackface", text=nwo.seam_back, icon_value=get_icon_id("region"))
            col3.menu("NWO_MT_Permutations", text=utils.true_permutation(nwo), icon_value=get_icon_id("permutation"))
        else:
            col2.menu("NWO_MT_Permutations", text=utils.true_permutation(nwo), icon_value=get_icon_id("permutation"))
        col.separator()
        
        if is_seam:
            row = col.row()
            row.use_property_split = False
            row.prop(nwo, "seam_back_manual")
            
class NWO_FoundryPanelPopover(bpy.types.Operator, NWO_FoundryPanelProps):
    bl_label = "Foundry"
    bl_idname = "nwo.show_foundry_panel"
    bl_description = "Loads the Foundry Panel at the position of the mouse cursor"
    bl_icon = 'MESH'
    
    def execute(self, context):
        return context.window_manager.invoke_popup(self, width=450)
    
class NWO_HotkeyDescription(bpy.types.Operator):
    bl_label = "Keyboard Shortcut Description"
    bl_idname = "nwo.describe_hotkey"
    bl_description = "Provides a description of this keyboard shortcut"

    hotkey : bpy.props.StringProperty()

    def execute(self, context):
        return {'FINISHED'}
    
    @classmethod
    def description(cls, context, properties) -> str:
        match properties.hotkey:
            case "apply_mesh_type":
                return "Opens a pie menu with a set of possible mesh types to apply to selected mesh objects. Applying a type through this menu will apply special materials if the type selected is not one that supports textures in game"
            case "apply_marker_type":
                return "Opens a pie menu with a set of possible marker types to apply to selected mesh and empty objects"
            case "halo_join":
                return "Joins two or more mesh objects and merges Halo Face Properties"
            case "move_to_halo_collection":
                return "Opens a dialog to specify a new halo collection to create, and then moves the selected objects into this collection"
            case "show_foundry_panel":
                return "Opens the Foundry Panel at the current mouse cursor position"
                

    @staticmethod
    def hotkey_info(self, context):
        layout = self.layout
        layout.label(text=NWO_HotkeyDescription.description(context, self.hotkey))

class NWO_OpenURL(bpy.types.Operator):
    bl_label = "Open URL"
    bl_idname = "nwo.open_url"
    bl_description = "Opens a URL"

    url : bpy.props.StringProperty()

    def execute(self, context):
        webbrowser.open_new_tab(self.url)
        return {'FINISHED'}
    
    @classmethod
    def description(cls, context, properties) -> str:
        if properties.url == FOUNDRY_DOCS:
            return "Opens documentation for Foundry on the c20 Reclaimers site in a new tab"
        elif properties.url == FOUNDRY_GITHUB:
            return "Opens the github page for Foundry in a new tab"
        elif properties.url == BLENDER_TOOLSET:
            return "Opens the github releases page for the Halo Blender Development Toolset, a blender addon supporting H1/H2/H3/ODST. Opens in a new tab"
        elif properties.url == AMF_ADDON:
            return "Opens the download page for the AMF importer blender addon. This addon allows blender to import AMF files extracted from the Halo Tool - Reclaimer."
        elif properties.url == RECLAIMER:
            return "Opens the download page for Reclaimer, a tool for extracting render models, BSPs, and textures for Halo games"
        elif properties.url == ANIMATION_REPO:
            return "Opens the github page for a repository containing a collection of Halo animations stored in the legacy Halo animation format"
        
class NWO_OT_FoundryTip(bpy.types.Operator):
    bl_idname = "nwo.show_tip"
    bl_label = ""
    bl_description = ""
    bl_options = {"UNDO"}
    
    tip: bpy.props.StringProperty({'HIDDEN'})

    def execute(self, context):
        # self.report({"INFO"}, self.tip)
        return {"FINISHED"}
    
    @classmethod
    def description(cls, context, properties) -> str:
        return properties.tip
    
def tip(ui: bpy.types.UILayout, label: str, desc: str):
    """Adds a button in the UI which displays the given text when pressed and hovered over. Requires the UI element to render the button in to be passed as the first argument"""
    ui.operator("nwo.show_tip", text=label, emboss=False).tip = desc
    
class NWO_OT_PanelUnpin(bpy.types.Operator):
    bl_idname = "nwo.panel_unpin"
    bl_label = "Pin/Unpin Panel"
    bl_options = {"UNDO"}

    panel_str : bpy.props.StringProperty()

    def execute(self, context):
        nwo = utils.get_scene_props()
        prop_pin = f"{self.panel_str}_pinned"
        setattr(nwo, prop_pin, not getattr(nwo, prop_pin))

        return {"FINISHED"}

class NWO_OT_PanelSet(bpy.types.Operator):
    """Toggles a Foundry panel on/off"""

    bl_idname = "nwo.panel_set"
    bl_label = ""
    bl_options = {"UNDO"}

    panel_str : bpy.props.StringProperty()
    keep_enabled : bpy.props.BoolProperty()
    pin : bpy.props.BoolProperty()

    def execute(self, context):
        nwo = utils.get_scene_props()
        prop = f"{self.panel_str}_active"
        prop_pin = f"{self.panel_str}_pinned"
        pinned = getattr(nwo, prop_pin)
        if self.pin and not pinned:
            setattr(nwo, prop_pin, True)
            setattr(nwo, prop, True)
        elif self.pin and pinned:
            setattr(nwo, prop_pin, False)
            setattr(nwo, prop, False)
        elif self.multi and getattr(nwo, prop):
            setattr(nwo, prop, False)
        else:
            setattr(nwo, prop, True)

        # toggle all others off
        if not self.keep_enabled:
            for p in PANELS_PROPS:
                p_name = f"{p}_active"
                if p_name != prop and not getattr(nwo, f"{p}_pinned"):
                    setattr(nwo, p_name, False)

        return {"FINISHED"}
    
    def invoke(self, context, event):
        self.keep_enabled = event.shift or event.ctrl
        self.pin = event.ctrl
        self.multi = event.shift
        return self.execute(context)
        
    
    @classmethod
    def description(cls, context, properties):
        name = properties.panel_str.title().replace("_", " ")
        descr = "Shift+Click to select multiple\nCtrl+Click to pin"
        full_descr = f'{name}\n\n{descr}'
        return full_descr


class NWO_OT_PanelExpand(bpy.types.Operator):
    """Expands or contracts Foundry panel on/off"""

    bl_idname = "nwo.panel_expand"
    bl_label = ""
    bl_options = set()
    bl_description = "Expand a panel"

    panel_str: bpy.props.StringProperty()

    def execute(self, context):
        nwo = self.scene_nwo
        prop = f"{self.panel_str}_expanded"
        setattr(nwo, prop, not getattr(nwo, prop))
        return {"FINISHED"}
    
    @classmethod
    def description(cls, context, properties):
        match properties.panel_str:
            # Main panel descriptions
            case "scene_properties":
                return "Settings for tweaking the coordinate system (forward direction and scale) of the Blender scene and how units are displayed. This also gives access to the Transform Scene Tool to transform the full scene to the desired coordinate system"
            case "asset_editor":
                return "Describes the type of asset you are building, as well as giving access to many tools and properties to edit the tags for this asset"
            case "sets_manager":
                return "Lets you manage the halo regions, permutations, and BSPs of your asset. This panel allows you to bulk assign objects to different sets as well as manage the Blender viewport visibility of sets and object types"
            case "object_properties":
                return "Allows you set the various Halo specific properties of the active object, and its underlying mesh (if it has one)"
            case "material_properties":
                return "Panel for viewing and setting the properties of the materials on the active object. This is also the place to generate tags from a specific blender material"
            case "animation_manager":
                return "Describes the full list of animations (actions) in this blend file. Use this to manage which animations should export and the properties of these animations. Clicking on an animation in the list will load it"
            case "tools":
                return "Contains a collection of miscellaneous tools to aid in asset development"
            case "help":
                return "Provides resources and links to help with asset creation. If you've installed Foundry as a remote repository you can check for updates here. If you've noticed any of Foundry's custom icons are not loading, you can refresh them here"
            case "settings":
                return "These are Foundry's preferences. You this to manage your different Halo projects (editing kits) and set various behaviors for the addon"
            
            # Asset editor descriptions
            case "rig_usages":
                return "A list of special bones that unique properties used by Halo's animation system. Any bones you set here will be added to the animation graph tag for you automatically whenever you export the asset. Leave all these fields blank to if you'd prefer to set the values in the tag yourself, or do not need them"

def blend_axis_name(name):
    blend_axis_name = "NAME_ERROR"
    blend_axis_function = "FUNCTION_ERROR"
    match name:
        case 'movement_angles':
            blend_axis_name = "Movement Angle"
            blend_axis_function = "get_move_angle"
        case 'movement_speed':
            blend_axis_name = "Movement Speed"
            blend_axis_function = "get_move_speed"
        case 'turn_rate':
            blend_axis_name = "Turn Rate"
            blend_axis_function = "get_turn_rate"
        case 'turn_angle':
            blend_axis_name = "Turn Angle"
            blend_axis_function = "get_turn_angle"
        case 'vertical':
            blend_axis_name = "Vertical"
            blend_axis_function = "get_destination_vertical"
        case 'horizontal':
            blend_axis_name = "Horizontal"
            blend_axis_function = "get_destination_forward"
        case "aim_pitch":
            blend_axis_name = "Aim Pitch"
            blend_axis_function = "get_aim_pitch"
        case "aim_yaw":
            blend_axis_name = "Aim Yaw"
            blend_axis_function = "get_aim_yaw"
        case "aim_yaw_from_start":
            blend_axis_name = "Aim Yaw From Start"
            blend_axis_function = "get_aim_yaw_from_start"
            
    return blend_axis_name, blend_axis_function

def draw_tag_path(ui, prop_group, prop_name, override_name=None, set_row_split=False):
    
    row = ui.row(align=True)
    
    if set_row_split:
        row.use_property_split = True
    
    attr = getattr(prop_group, prop_name)
    
    row.alert = prop_path_should_alert(attr)
    row.prop(prop_group, prop_name, icon_value=get_icon_id("tags"))
    
    if override_name is not None:
        prop_name = override_name
    
    row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = prop_name
    row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = prop_name
    if attr.strip() and not row.alert:
        row.operator("nwo.open_foundation_tag", text="", icon_value=get_icon_id("foundation")).tag_path = attr

def prop_path_should_alert(value, data=False):
    if value.strip():
        return not utils.project_file_exists(value, data)
    
    return False