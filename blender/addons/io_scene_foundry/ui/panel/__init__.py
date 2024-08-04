'''UI for the main Foundry panel'''
from pathlib import Path
import webbrowser

from ...icons import get_icon_id

from ... import constants
from ... import utils
import bpy

FOUNDRY_DOCS = r"https://c20.reclaimers.net/general/community-tools/foundry"
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"

BLENDER_TOOLSET = r"https://github.com/General-101/Halo-Asset-Blender-Development-Toolset/releases"
AMF_ADDON = r"https://github.com/Gravemind2401/Reclaimer/blob/master/Reclaimer.Blam/Resources/Blender%20AMF2.py"
RECLAIMER = r"https://github.com/Gravemind2401/Reclaimer/releases"
ANIMATION_REPO = r"https://github.com/77Mynameislol77/HaloAnimationRepository"

HOTKEYS = [
    ("show_foundry_panel", "SHIFT+F"),
    ("apply_mesh_type", "CTRL+F"),
    ("apply_marker_type", "ALT+F"),
    ("halo_join", "ALT+J"),
    ("move_to_halo_collection", "ALT+M"),
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
        return not context.scene.nwo.storage_only

    def draw(self, context):
        self.context = context
        layout = self.layout
        self.h4 = utils.is_corinth(context)
        self.scene = context.scene
        nwo = self.scene.nwo
        self.asset_type = nwo.asset_type
        if context.scene.nwo.instance_proxy_running:    
            box = layout.box()
            ob = context.object
            if ob:
                row = box.row()
                row.label(text=f"Editing: {ob.name}")
                row = box.row()
                row.use_property_split = True
                row.prop(
                    ob.data.nwo,
                    "face_global_material",
                    text="Collision Material",
                )
                row.operator(
                    "nwo.global_material_globals",
                    text="",
                    icon="VIEWZOOM",
                )
                # proxy face props
                self.draw_expandable_box(box.box(), context.scene.nwo, "face_properties", ob=ob)

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
                if not utils.poll_ui(('model', 'animation', 'camera_track_set')):
                    continue
            elif p in ("object_properties", "material_properties", 'sets_manager'):
                if nwo.asset_type in ('animation', 'camera_track_set'):
                    continue
            
            row_icon = box.row(align=True)
            panel_active = getattr(nwo, f"{p}_active")
            panel_pinned = getattr(nwo, f"{p}_pinned")
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
                panel_display_name = f"{p.replace('_', ' ').title()}"
                panel_expanded = getattr(nwo, f"{p}_expanded")
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
        nwo = self.scene.nwo
        scene = self.scene

        col = box.column()
        row = col.row()
        col.scale_y = 1.5

        col.operator('nwo.scale_scene', text='Transform Scene', icon='MOD_LENGTH')
        col = box.column()
        col.scale_y = 1.25
        col.separator()
        row = col.row()
        row.scale_y = 1.1
        row.prop(scene.nwo, 'scale', text='Scale', expand=True)
        row = col.row()
        row.scale_y = 1.1
        row.prop(scene.nwo, 'scale_display', text='Scale Display', expand=True)
        if scene.nwo.scale_display == 'halo' and scene.unit_settings.length_unit != 'METERS':
            row = col.row()
            row.label(text='World Units only accurate when Unit Length is Meters', icon='ERROR')
        row = col.row()
        row.prop(nwo, "forward_direction", text="Scene Forward", expand=True)
        row = col.row()
        row.prop(nwo, "maintain_marker_axis")

    def draw_asset_editor(self):
        box = self.box
        nwo = self.scene.nwo
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
            return
        
        if nwo.asset_type == 'model':
            self.draw_expandable_box(self.box.box(), nwo, 'output_tags')
            self.draw_expandable_box(self.box.box(), nwo, 'model')
            # self.draw_expandable_box(self.box.box(), nwo, 'model_overrides')
            self.draw_rig_ui(self.context, nwo)
            
        if self.h4 and nwo.asset_type in ('model', 'sky'):
            self.draw_expandable_box(self.box.box(), nwo, 'lighting')
        
        if nwo.asset_type == "animation":
            box = self.box.box()
            col = box.column()
            col.use_property_split = True
            col.prop(nwo, "asset_animation_type")
            if nwo.asset_animation_type == 'first_person':
                row = col.row(align=True)
                row.prop(nwo, "fp_model_path", text="FP Render Model", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "fp_model_path"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'fp_model_path'
                row = col.row(align=True)
                row.prop(nwo, "gun_model_path", text="Gun Render Model", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "gun_model_path"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'gun_model_path'
            self.draw_expandable_box(self.box.box(), nwo, 'animation_graph')
            self.draw_rig_ui(self.context, nwo)
            
        elif nwo.asset_type == "scenario":
            self.draw_expandable_box(self.box.box(), nwo, 'scenario')
            self.draw_expandable_box(self.box.box(), nwo, 'zone_sets')
            self.draw_expandable_box(self.box.box(), nwo, 'lighting')
            # self.draw_expandable_box(self.box.box(), nwo, 'objects')
            if self.h4:
                self.draw_expandable_box(self.box.box(), nwo, 'prefabs')
            
        elif nwo.asset_type == 'camera_track_set':
            box = self.box.box()
            col = box.column()
            col.operator('nwo.import', text="Import Camera Track", icon='IMPORT').scope = 'camera_track'
            col.prop(nwo, 'camera_track_camera', text="Camera")
            
        elif nwo.asset_type == 'particle_model':
            col.prop(nwo, 'particle_uses_custom_points')
    
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
        col.prop(nwo, "scenario_type")
        col.separator()
        col.operator("nwo.new_sky", text="Add New Sky to Scenario", icon_value=get_icon_id('sky'))
        
    def draw_lighting(self, box: bpy.types.UILayout, nwo):
        box_lights = box.box()
        box_lights.label(text="Lights")
        scene_nwo_export = self.scene.nwo_export
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
    
    def draw_zone_sets(self, box: bpy.types.UILayout, nwo):
        row = box.row()
        rows = 4
        row.template_list(
            "NWO_UL_ZoneSets",
            "",
            nwo,
            "zone_sets",
            nwo,
            "zone_sets_active_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.zone_set_add", text="", icon="ADD")
        col.operator("nwo.zone_set_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.remove_existing_zone_sets", icon="X", text="")
        col.separator()
        col.operator("nwo.zone_set_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.zone_set_move", icon="TRIA_DOWN", text="").direction = 'down'
        if not nwo.zone_sets:
            return
        zone_set = nwo.zone_sets[nwo.zone_sets_active_index]
        box.label(text=f"Zone Set BSPs")
        if zone_set.name.lower() == "all":
            return box.label(text="All BSPs included in Zone Set")
        grid = box.grid_flow()
        grid.scale_x = 0.8
        max_index = 31 if self.h4 else 15
        bsps = [region.name for region in nwo.regions_table]
        for index, bsp in enumerate(bsps):
            if index >= max_index:
                break
            if bsp.lower() != "shared":
                grid.prop(zone_set, f"bsp_{index}", text=bsp)
        
    
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
        row = box.row(align=True)
        row.prop(nwo, f'template_{tag_type}', icon_value=get_icon_id(tag_type), text="Template")
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = f"template_{tag_type}"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = f'template_{tag_type}'
        if utils.valid_nwo_asset(self.context) and getattr(nwo, f'template_{tag_type}'):
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
        
    def draw_equipment(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'equipment')
                
    def draw_model(self, box: bpy.types.UILayout, nwo):
        row = box.row(align=True)
        row.prop(nwo, 'template_model', icon_value=get_icon_id("model"), text="Template")
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_model"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_model'
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
        col.prop(nwo, "render_model_from_blend")
        if nwo.render_model_from_blend:
            tag_path = utils.get_asset_render_model()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Render Model Tag").tag_path = tag_path
        else:
            row = col.row(align=True)
            row.prop(nwo, "render_model_path", text="Render", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "render_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'render_model_path'
    
    def draw_collision_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "collision_model_from_blend")
        if nwo.collision_model_from_blend:
            tag_path = utils.get_asset_collision_model()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Collision Model Tag").tag_path = tag_path
        else:
            row = col.row(align=True)
            row.prop(nwo, "collision_model_path", text="Collision", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "collision_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'collision_model_path'
    
    def draw_animation_graph(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "animation_graph_from_blend")
        if nwo.animation_graph_from_blend:
            row = col.row(align=True)
            row.use_property_split = True
            row.prop(nwo, "parent_animation_graph", text="Parent Animation Graph")
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "parent_animation_graph"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'parent_animation_graph'
            row = col.row()
            row.use_property_split = True
            row.prop(nwo, "default_animation_compression", text="Default Animation Compression")
            tag_path = utils.get_asset_animation_graph()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Animation Graph Tag").tag_path = tag_path
            frame_events_tag_path = utils.get_asset_tag(".frame_events_list")
            if frame_events_tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Frame Events List Tag").tag_path = frame_events_tag_path
            self.draw_expandable_box(box.box(), nwo, 'rig_usages', 'Node Usages')
            self.draw_expandable_box(box.box(), nwo, 'ik_chains', panel_display_name='IK Chains')
            self.draw_expandable_box(box.box(), nwo, 'animation_copies')
            if self.h4:
                self.draw_expandable_box(box.box(), nwo, 'animation_composites')
        else:
            row = col.row(align=True)
            row.prop(nwo, "animation_graph_path", text="Animation", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "animation_graph_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'animation_graph_path'
    
    def draw_physics_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "physics_model_from_blend")
        if nwo.physics_model_from_blend:
            tag_path = utils.get_asset_physics_model()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Physics Model Tag").tag_path = tag_path
        else:
            row = col.row(align=True)
            row.prop(nwo, "physics_model_path", text="Physics", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "physics_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'physics_model_path'
    
    def draw_model_overrides(self, box: bpy.types.UILayout, nwo):
        asset_dir, asset_name = utils.get_asset_info()
        self_path = str(Path(asset_dir, asset_name))
        everything_overidden = nwo.render_model_path and nwo.collision_model_path and nwo.animation_graph_path and nwo.physics_model_path
        if everything_overidden:
            box.alert = True
        col = box.column()
        row = col.row(align=True)
        if nwo.render_model_path and utils.dot_partition(nwo.render_model_path) == self_path:
            row.alert = True
            row.label(icon='ERROR')
            
        row.prop(nwo, "render_model_path", text="Render", icon_value=get_icon_id("tags"))
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "render_model_path"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'render_model_path'
        row = col.row(align=True)
        row.prop(nwo, "collision_model_path", text="Collision", icon_value=get_icon_id("tags"))
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "collision_model_path"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'collision_model_path'
        row = col.row(align=True)
        row.prop(nwo, "animation_graph_path", text="Animation", icon_value=get_icon_id("tags"))
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "animation_graph_path"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'animation_graph_path'
        row = col.row(align=True)
        row.prop(nwo, "physics_model_path", text="Physics", icon_value=get_icon_id("tags"))
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "physics_model_path"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'physics_model_path'
        if everything_overidden:
            row = col.row(align=True)
            row.label(text='All overrides specified', icon='ERROR')
            row = col.row(align=True)
            row.label(text='Everything exported from this scene will be overwritten')
            
    def draw_model_rig(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.use_property_split = True
        col.prop(nwo, 'main_armature', icon='OUTLINER_OB_ARMATURE')
        if not nwo.main_armature: return
        col.separator()
        arm_count = utils.get_arm_count(self.context)
        if arm_count > 1 or nwo.support_armature_a:
            col.prop(nwo, 'support_armature_a', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_a:
                col.prop_search(nwo, 'support_armature_a_parent_bone', nwo.main_armature.data, 'bones')
                col.separator()
        if arm_count > 2 or nwo.support_armature_b:
            col.prop(nwo, 'support_armature_b', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_b:
                col.prop_search(nwo, 'support_armature_b_parent_bone', nwo.main_armature.data, 'bones')
                col.separator()
        if arm_count > 3 or nwo.support_armature_c:
            col.prop(nwo, 'support_armature_c', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_c:
                col.prop_search(nwo, 'support_armature_c_parent_bone', nwo.main_armature.data, 'bones')
                
        #col.separator()
                
    def draw_rig_controls(self, box: bpy.types.UILayout, nwo):
        box.use_property_split = True
        row = box.row(align=True)
        row.prop_search(nwo, 'control_aim', nwo.main_armature.data, 'bones')
        if not nwo.control_aim:
            row.operator('nwo.add_pose_bones', text='', icon='ADD').skip_invoke = True
            
    def draw_rig_object_controls(self, box: bpy.types.UILayout, nwo):
        box.use_property_split = True
        row = box.row()
        row.template_list(
            "NWO_UL_ObjectControls",
            "",
            nwo,
            "object_controls",
            nwo,
            "object_controls_active_index",
        )
        row = box.row(align=True)
        row.operator('nwo.batch_add_object_controls', text='Add')
        row.operator('nwo.batch_remove_object_controls', text='Remove')
        row.operator('nwo.select_object_control', text='Select').select = True
        row.operator('nwo.select_object_control', text='Deselect').select = False
    
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
        if self.h4:
            col.prop_search(nwo, "node_usage_left_hand", nwo.main_armature.data, "bones")
            col.prop_search(nwo, "node_usage_right_foot", nwo.main_armature.data, "bones")
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
            box.operator("nwo.add_ik_chain", text="Add Game IK Chain", icon="CON_SPLINEIK")
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
            
    def draw_animation_composites(self, box: bpy.types.UILayout, nwo):
        if not nwo.animation_composites:
            box.operator("nwo.animation_composite_add", text="New Composite Animation", icon_value=get_icon_id("animation_composite"))
            return
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationComposites",
            "",
            nwo,
            "animation_composites",
            nwo,
            "animation_composites_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.animation_composite_add", text="", icon="ADD")
        col.operator("nwo.animation_composite_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.animation_composite_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.animation_composite_move", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.animation_composites and nwo.animation_composites_active_index > -1:
            item = nwo.animation_composites[nwo.animation_composites_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(item, "overlay")
            col.prop(item, "timing_source")
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
            col = box.column()
            col.use_property_split = True
            col.prop(blend_axis, "animation_source_bounds")
            col.prop(blend_axis, "animation_source_limit")
            col.prop(blend_axis, "runtime_source_bounds")
            col.prop(blend_axis, "runtime_source_clamped")
            col.prop(blend_axis, "adjusted")
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
                
            self.draw_animation_leaves(col, blend_axis, False)
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
                    
                    self.draw_animation_leaves(col, phase_set, True)
            
            
    def draw_animation_leaves(self,col: bpy.types.UILayout, parent, in_set):
        box = col.box()
        name = "Set Animations" if in_set else "Blend Axis Animations"
        box.label(text=name)
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
        col.operator("nwo.animation_leaf_add", text="", icon="ADD").phase_set = in_set
        col.operator("nwo.animation_leaf_remove", icon="REMOVE", text="").phase_set = in_set
        col.separator()
        move_up = col.operator("nwo.animation_leaf_move", text="", icon="TRIA_UP")
        move_up.direction = 'up'
        move_up.phase_set = in_set
        move_down = col.operator("nwo.animation_leaf_move", icon="TRIA_DOWN", text="")
        move_down.direction = 'down'
        move_down.phase_set = in_set
        if parent.leaves and parent.leaves_active_index > -1:
            leaf = parent.leaves[parent.leaves_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(leaf, "animation")
            col.prop(leaf, "uses_move_speed")
            if leaf.uses_move_speed:
                col.prop(leaf, "move_speed")
            col.prop(leaf, "uses_move_angle")
            if leaf.uses_move_angle:
                col.prop(leaf, "move_angle")
    
    def draw_rig_ui(self, context, nwo):
        box = self.box.box()
        if self.draw_expandable_box(box, nwo, 'model_rig') and nwo.main_armature:
            self.draw_expandable_box(box.box(), nwo, 'rig_controls', 'Bone Controls')
            self.draw_expandable_box(box.box(), nwo, 'rig_object_controls', 'Object Controls')

    def draw_sets_manager(self):
        self.box.operator('nwo.update_sets', icon='FILE_REFRESH')
        box = self.box
        nwo = self.scene.nwo
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
            grid.prop(nwo, "connected_geometry_mesh_type_lightmap_only_visible", text="", icon_value=get_icon_id("lightmap") if nwo.connected_geometry_mesh_type_lightmap_only_visible else get_icon_id("lightmap_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_water_surface_visible", text="", icon_value=get_icon_id("water") if nwo.connected_geometry_mesh_type_water_surface_visible else get_icon_id("water_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_planar_fog_volume_visible", text="", icon_value=get_icon_id("fog") if nwo.connected_geometry_mesh_type_planar_fog_volume_visible else get_icon_id("fog_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_soft_ceiling_visible", text="", icon_value=get_icon_id("soft_ceiling") if nwo.connected_geometry_mesh_type_soft_ceiling_visible else get_icon_id("soft_ceiling_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_soft_kill_visible", text="", icon_value=get_icon_id("soft_kill") if nwo.connected_geometry_mesh_type_soft_kill_visible else get_icon_id("soft_kill_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_slip_surface_visible", text="", icon_value=get_icon_id("slip_surface") if nwo.connected_geometry_mesh_type_slip_surface_visible else get_icon_id("slip_surface_off"), emboss=False)
            if self.h4:
                grid.prop(nwo, "connected_geometry_mesh_type_streaming_visible", text="", icon_value=get_icon_id("streaming") if nwo.connected_geometry_mesh_type_streaming_visible else get_icon_id("streaming_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_mesh_type_lightmap_exclude_visible", text="", icon_value=get_icon_id("lightmap_exclude") if nwo.connected_geometry_mesh_type_lightmap_exclude_visible else get_icon_id("lightmap_exclude_off"), emboss=False)
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

    def draw_object_properties(self):
        box = self.box
        row = box.row()
        context = self.context
        ob = context.object
        h4 = self.h4
        if not ob:
            row.label(text="No Active Object")
            return
        elif not utils.is_halo_object(ob):
            row.label(text="Not a Halo Object")
            return

        nwo = ob.nwo
        col1 = row.column()
        col1.template_ID(context.view_layer.objects, "active", filter="AVAILABLE")
        col2 = row.column()
        col2.alignment = "RIGHT"
        col2.prop(nwo, "export_this", text="Export")

        if not nwo.export_this:
            box.label(text="Object is excluded from export")
            return

        elif ob.type == "ARMATURE":
            box.label(text='Frame')
            return

        row = box.row(align=True)
        row.scale_x = 0.5
        row.scale_y = 1.3
        data = ob.data

        halo_light = ob.type == 'LIGHT'
        has_mesh_types = utils.is_mesh(ob) and utils.poll_ui(('model', 'scenario', 'prefab'))

        # Check if this is a linked collection
        if utils.library_instanced_collection(ob):
            row.label(text='Instanced Collection', icon='OUTLINER_OB_GROUP_INSTANCE')
            row = box.row()
            row.label(text=f'{ob.name} will be unpacked at export')
            return

        elif halo_light:
            row.prop(data, "type", expand=True)
            col = box.column()
            col.use_property_split = True
            self.draw_table_menus(col, nwo, ob)
            flow = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )

            nwo = data.nwo
            col = flow.column()
            col.prop(data, "color")
            col.prop(data, "energy")
            # col.prop(nwo, 'light_intensity', text="Intensity")
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
                col.prop(nwo, "light_bounce_ratio")
                col.separator()
                col.prop(nwo, "light_far_attenuation_start", text="Light Falloff")
                col.prop(nwo, "light_far_attenuation_end", text="Light Cutoff")
                col.separator()
                col.prop(nwo, "light_use_shader_gel")
                col.prop(nwo, "light_per_unit")
                return

            if data.type == 'SPOT' and h4:
                col.separator()
                col.prop(data, "spot_size", text="Cone Size")
                col.prop(data, "spot_blend", text="Cone Blend", slider=True)
                col.prop(data, "show_cone")

            col.separator()
            if utils.is_corinth(context):
                row = col.row()
                row.prop(nwo, "light_mode", expand=True)
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

                if nwo.light_mode == "_connected_geometry_light_mode_dynamic":
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

                col.prop(nwo, "light_game_type", text="Light Type")
                col.prop(nwo, "light_shape", text="Shape")

                col.separator()

                col.prop(nwo, "light_falloff_shape", text="Falloff Shape")
                col.prop(nwo, "light_aspect", text="Light Aspect")

                col.separator()

                # col.prop(nwo, "light_frustum_width", text="Frustum Width")
                # col.prop(nwo, "light_frustum_height", text="Frustum Height")

                # col.separator()

                col.prop(nwo, "light_volume_distance", text="Light Volume Distance")
                col.prop(nwo, "light_volume_intensity", text="Light Volume Intensity")

                col.separator()

                col.prop(nwo, "light_bounce_ratio", text="Light Bounce Ratio")

                col.separator()

                col = col.column(heading="Flags")
                sub = col.column(align=True)

                col = flow.column()

                col.prop(
                    nwo,
                    "light_near_attenuation_start",
                    text="Light Activation Start",
                )
                col.prop(
                    nwo,
                    "light_near_attenuation_end",
                    text="Light Activation End",
                )

                col.separator()

                col.prop(nwo, "light_far_attenuation_start", text="Light Falloff")
                col.prop(nwo, "light_far_attenuation_end", text="Light Cutoff")

                col.separator()
                row = col.row()
                row.prop(nwo, "light_tag_override", text="Light Tag Override", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_tag_override"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_tag_override'
                row = col.row()
                row.prop(nwo, "light_shader_reference", text="Shader Tag Reference", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_shader_reference"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_shader_reference'
                row = col.row()
                row.prop(nwo, "light_gel_reference", text="Gel Tag Reference", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_gel_reference"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_gel_reference'
                row = col.row()
                row.prop(
                    nwo,
                    "light_lens_flare_reference",
                    text="Lens Flare Tag Reference",
                    icon_value=get_icon_id("tags")
                )
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_lens_flare_reference"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_lens_flare_reference'

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
                row = col.row()
                row.prop(
                    nwo,
                    "fog_appearance_tag",
                    text="Fog Appearance Tag",
                    icon_value=get_icon_id('tags')
                )
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "fog_appearance_tag"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'fog_appearance_tag'
                col.prop(
                    nwo,
                    "fog_volume_depth",
                    text="Fog Volume Depth",
                )
                
            elif (
                nwo.mesh_type
                == "_connected_geometry_mesh_type_water_physics_volume"
            ):
                col.prop(
                    nwo,
                    "water_volume_depth",
                    text="Water Depth",
                )
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

            elif (
                nwo.mesh_type == "_connected_geometry_mesh_type_water_surface"
            ):
                col.prop(nwo, "mesh_tessellation_density", text="Tessellation Density")
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

            elif nwo.mesh_type in (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_structure",
            ) and utils.poll_ui(('scenario', 'prefab')):
                if h4 and nwo.mesh_type == "_connected_geometry_mesh_type_structure" and utils.poll_ui(('scenario',)):
                    col.prop(nwo, "proxy_instance")
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
                        != "_connected_poop_instance_imposter_policy_never"
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
                    # col.prop(
                    #     nwo,
                    #     "poop_chops_portals",
                    #     text="Chops Portals",
                    # )
                    col.prop(
                        nwo,
                        "poop_render_only",
                        text="Render Only",
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
            
            col.prop(nwo, "frame_override")

            if utils.poll_ui("scenario"):
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
                row = col.row(align=True)
                row.prop(
                    nwo,
                    "marker_game_instance_tag_name",
                    text="Tag Path",
                    icon_value=get_icon_id('tags')
                )
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_game_instance_tag_name"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_game_instance_tag_name'
                tag_name = Path(nwo.marker_game_instance_tag_name).suffix.lower()
                if tag_name == ".decorator_set":
                    col.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name",
                        text="Decorator Type",
                    )
                elif not tag_name in (".prefab", ".cheap_light", ".light", ".leaf"):
                    row = col.row(align=True)
                    row.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name",
                        text="Tag Variant",
                    )
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
                    if nwo.prefab_imposter_policy != "_connected_poop_instance_imposter_policy_never":
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
                    
            if nwo.marker_type == "_connected_geometry_marker_type_hint":
                row = col.row(align=True)
                row.prop(nwo, "marker_hint_type")
                if nwo.marker_hint_type == "corner":
                    row = col.row(align=True)
                    row.prop(nwo, "marker_hint_side", expand=True)
                elif nwo.marker_hint_type in (
                    "vault",
                    "mount",
                    "hoist",
                ):
                    row = col.row(align=True)
                    row.prop(nwo, "marker_hint_height", expand=True)
                # if h4:
                #     col.prop(nwo, "marker_hint_length")

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
                row = col.row()
                row.prop(nwo, "marker_looping_effect", icon_value=get_icon_id('tags'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_looping_effect"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_looping_effect'

            elif (
                nwo.marker_type == "_connected_geometry_marker_type_lightCone" and h4
            ):
                row = col.row()
                row.prop(nwo, "marker_light_cone_tag", text='Cone Tag Path', icon_value=get_icon_id('tags'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_light_cone_tag"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_light_cone_tag'
                col.prop(nwo, "marker_light_cone_color", text='Color')
                # col.prop(nwo, "marker_light_cone_alpha", text='Alpha')
                col.prop(nwo, "marker_light_cone_intensity", text='Intensity')
                col.prop(nwo, "marker_light_cone_width", text='Width')
                col.prop(nwo, "marker_light_cone_length", text='Length')
                row = col.row()
                row.prop(nwo, "marker_light_cone_curve", text='Curve Tag Path', icon_value=get_icon_id('tags'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_light_cone_curve"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_light_cone_curve'
                
        elif utils.is_frame(ob) and utils.poll_ui(
            ("model", "scenario", "sky")):
            col = box.column()
            col.label(text='Frame', icon_value=get_icon_id('frame'))
            if not ob.children:
                col.prop(nwo, "frame_override")
            # TODO Add button that selects child objects
            return
                

        if not utils.has_mesh_props(ob) or (h4 and not nwo.proxy_instance and utils.poll_ui(('scenario',)) and nwo.mesh_type == "_connected_geometry_mesh_type_structure"):
            return

        self.draw_expandable_box(self.box.box(), context.scene.nwo, "mesh_properties", ob=ob)
        if utils.has_face_props(ob):
            self.draw_expandable_box(self.box.box(), context.scene.nwo, "face_properties", ob=ob)
  
        nwo = ob.data.nwo
        # Instance Proxy Operators
        if ob.type != 'MESH' or ob.nwo.mesh_type != "_connected_geometry_mesh_type_default" or not utils.poll_ui(('scenario', 'prefab')) or mesh_nwo.render_only:
            return
        
        col.separator()
        self.draw_expandable_box(self.box.box(), context.scene.nwo, "instance_proxies", ob=ob)

    def draw_face_properties(self, box, ob):
        context = self.context
        flow = box.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        flow.use_property_split = True

        nwo = ob.data.nwo

        box.label(text="Face Properties", icon='FACE_MAPS')
        if nwo.face_props:
            box.operator('nwo.update_layers_face_count', text="Refresh Face Counts", icon='FILE_REFRESH')
        if len(nwo.face_props) <= 0 and context.mode != "EDIT_MESH":
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            col.scale_y = 1.3
            col.operator(
                "nwo.edit_face_layers",
                text="Add Face Properties",
                icon="EDITMODE_HLT",
            )
        else:
            rows = 5
            row = box.row()
            row.template_list(
                "NWO_UL_FacePropList",
                "",
                nwo,
                "face_props",
                nwo,
                "face_props_active_index",
                rows=rows,
            )

            col = row.column(align=True)
            edit_mode = context.mode == 'EDIT_MESH'
            if edit_mode:
                if context.scene.nwo.instance_proxy_running or (ob.nwo.mesh_type == "_connected_geometry_mesh_type_collision" and utils.poll_ui(('scenario', 'prefab'))):
                    col.operator("nwo.face_layer_add", text="", icon="ADD").options = "face_global_material"
                else:
                    col.menu("NWO_MT_FacePropAdd", text="", icon="ADD")
                
            col.operator("nwo.face_layer_remove", icon="REMOVE", text="")
            col.separator()
            if edit_mode:
                col.operator(
                    "nwo.face_layer_color_all",
                    text="",
                    icon="SHADING_RENDERED",
                    depress=nwo.highlight,
                ).enable_highlight = not nwo.highlight
                col.separator()
            col.operator(
                "nwo.face_layer_move", icon="TRIA_UP", text=""
            ).direction = "UP"
            col.operator(
                "nwo.face_layer_move", icon="TRIA_DOWN", text=""
            ).direction = "DOWN"

            row = box.row()

            if nwo.face_props and edit_mode:
                sub = row.row(align=True)
                sub.operator("nwo.face_layer_assign", text="Assign").assign = True
                sub.operator("nwo.face_layer_assign", text="Remove").assign = False
                sub = row.row(align=True)
                sub.operator("nwo.face_layer_select", text="Select").select = True
                sub.operator(
                    "nwo.face_layer_select", text="Deselect"
                ).select = False

            else:
                box.operator(
                    "nwo.edit_face_layers",
                    text="Edit Mode",
                    icon="EDITMODE_HLT",
                )

            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            row = col.row()
            col.use_property_split = True
            if nwo.face_props:
                item = nwo.face_props[nwo.face_props_active_index]

                if item.region_name_override:
                    box = col.box()
                    row = box.row()
                    row.label(text='Region')
                    row = box.row()
                    row.menu("NWO_MT_FaceRegions", text=item.region_name, icon_value=get_icon_id("region"))
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "region"
                if item.face_two_sided_override:
                    if utils.is_corinth(context):
                        col.separator()
                        box = col.box()
                        row = box.row()
                        row.label(text="Two Sided")
                        row = box.row()
                        row.prop(item, "face_two_sided_type", text="Backside Normals")
                    else:
                        row = col.row()
                        row.label(text="Two Sided")
                if item.render_only_override:
                    row = col.row()
                    row.label(text='Render Only')
                    
                if item.collision_only_override:
                    row = col.row()
                    row.label(text='Collision Only')
                    
                if item.sphere_collision_only_override:
                    row = col.row()
                    row.label(text='Sphere Collision Only')
                    
                if item.player_collision_only_override:
                    row = col.row()
                    row.label(text='Player Collision Only')
                    
                if item.bullet_collision_only_override:
                    row = col.row()
                    row.label(text='Bullet Collision Only')

                if item.face_transparent_override:
                    row = col.row()
                    row.label(text="Transparent Faces")
                if item.face_draw_distance_override:
                    row = col.row()
                    row.prop(item, "face_draw_distance")
                if item.face_global_material_override:
                    row = col.row()
                    row.prop(item, "face_global_material")
                    if utils.poll_ui(('scenario', 'prefab')):
                        row.operator(
                            "nwo.global_material_globals",
                            text="",
                            icon="VIEWZOOM",
                        ).face_level = True
                    else:
                        row.menu(
                            "NWO_MT_AddGlobalMaterialFace",
                            text="",
                            icon="DOWNARROW_HLT",
                        )
                if item.precise_position_override:
                    row = col.row()
                    row.label(text='Uncompressed')
                if item.ladder_override:
                    row = col.row()
                    row.label(text='Ladder')
                if item.slip_surface_override:
                    row = col.row()
                    row.label(text='Slip Surface')
                if item.breakable_override:
                    row = col.row()
                    row.label(text='Breakable')
                if item.decal_offset_override:
                    row = col.row()
                    row.label(text='Decal Offset')
                if item.no_shadow_override:
                    row = col.row()
                    row.label(text='No Shadow')
                if item.no_lightmap_override:
                    row = col.row()
                    row.label(text="No Lightmap")
                if item.no_pvs_override:
                    row = col.row()
                    row.label(text="No Visibility Culling")
                # lightmap
                if item.lightmap_additive_transparency_override:
                    row = col.row()
                    row.prop(item, "lightmap_additive_transparency", text="Additive Transparency")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_additive_transparency"
                if item.lightmap_resolution_scale_override:
                    row = col.row()
                    row.prop(item, "lightmap_resolution_scale")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_resolution_scale"
                if item.lightmap_type_override:
                    row = col.row()
                    row.prop(item, "lightmap_type")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_type"
                if item.lightmap_analytical_bounce_modifier_override:
                    row = col.row()
                    row.prop(item, "lightmap_analytical_bounce_modifier")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_analytical_bounce_modifier"
                if item.lightmap_general_bounce_modifier_override:
                    row = col.row()
                    row.prop(item, "lightmap_general_bounce_modifier")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_general_bounce_modifier"
                if item.lightmap_translucency_tint_color_override:
                    row = col.row()
                    row.prop(item, "lightmap_translucency_tint_color")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_translucency_tint_color"
                if item.lightmap_lighting_from_both_sides_override:
                    row = col.row()
                    row.label(text="Lightmap Lighting From Both Sides")
                # material lighting
                if item.emissive_override:
                    col.separator()
                    box = col.box()
                    row = box.row()
                    row.label(text="Emissive Settings")
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_color",
                        text="Color",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_power",
                        text="Power",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_quality",
                        text="Quality",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_focus",
                        text="Focus",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_attenuation_falloff",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_attenuation_cutoff",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_bounce_ratio",
                        text="Bounce Ratio",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_use_shader_gel",
                        text="Shader Gel",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_per_unit",
                        text="Emissive Per Unit",
                    )
                # if not (is_proxy or ob.nwo.mesh_type == "_connected_geometry_mesh_type_collision"):
                #     col.separator()
                #     col.menu(NWO_MT_FacePropAddMenu.bl_idname, text="Add Face Layer Property", icon="PLUS")

    def draw_mesh_properties(self, box, ob):
        nwo = ob.nwo
        mesh = ob.data
        mesh_nwo = mesh.nwo
        has_collision = utils.has_collision_type(ob)
        if utils.poll_ui(("model", "sky", "scenario", "prefab")) and nwo.mesh_type != '_connected_geometry_mesh_type_physics':
            if self.h4 and (not nwo.proxy_instance and nwo.mesh_type == "_connected_geometry_mesh_type_structure" and utils.poll_ui(('scenario',))):
                return
            row = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=True,
                align=True,
            )
            row.scale_x = 0.8
            if nwo.mesh_type in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_lightmap_only", '_connected_geometry_mesh_type_object_instance'):
                row.prop(mesh_nwo, "precise_position", text="Uncompressed")
            if nwo.mesh_type in constants.TWO_SIDED_MESH_TYPES:
                row.prop(mesh_nwo, "face_two_sided", text="Two Sided")
                if nwo.mesh_type in constants.RENDER_MESH_TYPES:
                    row.prop(mesh_nwo, "face_transparent", text="Transparent")
                    # if h4 and utils.poll_ui(('model', 'sky')):
                    #     row.prop(mesh_nwo, "uvmirror_across_entire_model_ui", text="Mirror UVs")
            if nwo.mesh_type in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", '_connected_geometry_mesh_type_object_instance', "_connected_geometry_mesh_type_lightmap_only"):
                row.prop(mesh_nwo, "decal_offset", text="Decal Offset") 
            if utils.poll_ui(("scenario", "prefab")):
                if not self.h4:
                    if nwo.mesh_type in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_lightmap_only"):
                        row.prop(mesh_nwo, "no_shadow", text="No Shadow")
                else:
                    # row.prop(mesh_nwo, "group_transparents_by_plane_ui", text="Transparents by Plane")
                    if nwo.mesh_type in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_lightmap_only"):
                        row.prop(mesh_nwo, "no_shadow", text="No Shadow")
                        if self.h4 and nwo.mesh_type != "_connected_geometry_mesh_type_lightmap_only":
                            row.prop(mesh_nwo, "no_lightmap", text="No Lightmap")
                            row.prop(mesh_nwo, "no_pvs", text="No Visibility Culling")
                            
            if not self.h4 and utils.poll_ui(('scenario',)) and nwo.mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_structure'):
                row.prop(mesh_nwo, 'render_only')
                if not mesh_nwo.render_only:
                    row.prop(mesh_nwo, "ladder", text="Ladder")
                    row.prop(mesh_nwo, "slip_surface", text="Slip Surface")
                    row.prop(mesh_nwo, 'breakable', text='Breakable')
                    if nwo.mesh_type == '_connected_geometry_mesh_type_structure':
                        row.prop(mesh_nwo, 'collision_only', text='Collision Only')
                        row.prop(mesh_nwo, 'sphere_collision_only', text='Sphere Collision')
                
            elif not self.h4 and nwo.mesh_type == '_connected_geometry_mesh_type_collision':
                if utils.poll_ui(('scenario', 'model')):
                    row.prop(mesh_nwo, 'sphere_collision_only', text='Sphere Collision')
                    row.prop(mesh_nwo, "ladder", text="Ladder")
                    row.prop(mesh_nwo, "slip_surface", text="Slip Surface")
                
            elif self.h4 and has_collision and nwo.mesh_type != '_connected_geometry_mesh_type_collision':
                row.prop(mesh_nwo, 'render_only')

            if self.h4 and nwo.mesh_type in constants.RENDER_MESH_TYPES and mesh_nwo.face_two_sided:
                row = box.row()
                row.use_property_split = True
                row.prop(mesh_nwo, "face_two_sided_type", text="Backside Normals")
                
        if nwo.mesh_type in constants.RENDER_MESH_TYPES and not self.asset_type in ('scenario', 'prefab'):
            row = box.row()
            row.use_property_split = True
            row.prop(mesh_nwo, "face_draw_distance")
                
        if utils.poll_ui(("model", "scenario", "prefab")):
            if has_collision and utils.poll_ui(("scenario", "prefab")) and not (mesh_nwo.render_only and utils.is_instance_or_structure_proxy(ob)):
                if self.h4:
                    row = box.row()
                    row.use_property_split = True
                    row.prop(mesh_nwo, 'poop_collision_type', text='Collision Type')
                        
            if (self.h4 and (nwo.mesh_type in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                "_connected_geometry_mesh_type_structure",
                "_connected_geometry_mesh_type_default",
                )
                and (nwo.proxy_instance or nwo.mesh_type != "_connected_geometry_mesh_type_structure"))) or (not self.h4 and nwo.mesh_type in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                )):
                    if not (nwo.mesh_type in ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default") and mesh_nwo.render_only):
                        if not (self.asset_type == 'model' and nwo.mesh_type == '_connected_geometry_mesh_type_default'):
                            row = box.row()
                            row.use_property_split = True
                            coll_mat_text = 'Collision Material'
                            if ob.data.nwo.face_props and nwo.mesh_type in ('_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default'):
                                for prop in ob.data.nwo.face_props:
                                    if prop.face_global_material_override:
                                        coll_mat_text += '*'
                                        break
                            row.prop(
                                mesh_nwo,
                                "face_global_material",
                                text=coll_mat_text,
                            )
                            if utils.poll_ui(('scenario', 'prefab')):
                                row.operator(
                                    "nwo.global_material_globals",
                                    text="",
                                    icon="VIEWZOOM",
                                )
                            else:
                                row.menu(
                                    "NWO_MT_AddGlobalMaterial",
                                    text="",
                                    icon="DOWNARROW_HLT",
                            )

        if nwo.mesh_type in (
            "_connected_geometry_mesh_type_structure",
            # "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_lightmap_only",
        ):
            if utils.poll_ui(("scenario", "prefab")) and (not self.h4 or nwo.proxy_instance or nwo.mesh_type != "_connected_geometry_mesh_type_structure"):
                # col.separator()
                col_ob = box.column()
                col_ob.use_property_split = True
                # lightmap
                has_lightmap_props = mesh_nwo.mesh_type != "_connected_geometry_mesh_type_lightmap_only"
                if has_lightmap_props:
                    if mesh_nwo.lightmap_additive_transparency_active:
                        row = col_ob.row(align=True)
                        row.prop(
                            mesh_nwo,
                            "lightmap_additive_transparency",
                            text="Additive Transparency",
                        )
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_additive_transparency"
                    if mesh_nwo.lightmap_resolution_scale_active:
                        row = col_ob.row(align=True)
                        row.prop(
                            mesh_nwo,
                            "lightmap_resolution_scale",
                            text="Resolution Scale",
                        )
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_resolution_scale"
                    if mesh_nwo.lightmap_type_active:
                        row = col_ob.row(align=True)
                        row.prop(mesh_nwo, "lightmap_type", text="Lightmap Type")
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_type"
                    if mesh_nwo.lightmap_analytical_bounce_modifier_active:
                        row = col_ob.row(align=True)
                        row.prop(
                            mesh_nwo,
                            "lightmap_analytical_bounce_modifier",
                            text="Analytical Bounce Modifier",
                        )
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_analytical_bounce_modifier"
                    if mesh_nwo.lightmap_general_bounce_modifier_active:
                        row = col_ob.row(align=True)
                        row.prop(
                            mesh_nwo,
                            "lightmap_general_bounce_modifier",
                            text="General Bounce Modifier",
                        )
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_general_bounce_modifier"
                    if mesh_nwo.lightmap_translucency_tint_color_active:
                        row = col_ob.row(align=True)
                        row.prop(
                            mesh_nwo,
                            "lightmap_translucency_tint_color",
                            text="Translucency Tint Color",
                        )
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_translucency_tint_color"
                    if mesh_nwo.lightmap_lighting_from_both_sides_active:
                        row = col_ob.row(align=True)
                        row.prop(
                            mesh_nwo,
                            "lightmap_lighting_from_both_sides",
                            text="Lighting From Both Sides",
                        )
                        row.operator(
                            "nwo.remove_mesh_property", text="", icon="X"
                        ).options = "lightmap_lighting_from_both_sides"
                if mesh_nwo.emissive_active:
                    col_ob.separator()
                    box_ob = col_ob.box()
                    row = box_ob.row(align=True)
                    row.label(text="Emissive Settings", icon='LIGHT_DATA')
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "emissive"
                    row = box_ob.row(align=True)
                    row.prop(mesh_nwo, "material_lighting_emissive_color", text="Color")
                    row = box_ob.row(align=True)
                    row.prop(mesh_nwo, "material_lighting_emissive_power", text="Power")
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_emissive_quality",
                        text="Quality",
                    )
                    row = box_ob.row(align=True)
                    row.prop(mesh_nwo, "material_lighting_emissive_focus", text="Focus")
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_bounce_ratio",
                        text="Bounce Ratio",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_attenuation_falloff",
                        text="Light Falloff",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_attenuation_cutoff",
                        text="Light Cutoff",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_use_shader_gel",
                        text="Shader Gel",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_emissive_per_unit",
                        text="Emissive Per Unit",
                    )

                col_ob.separator()
                row_add_prop = col_ob.row()
                if not mesh_nwo.emissive_active:
                    row_add_prop.operator("nwo.add_mesh_property", text="Emissive", icon='LIGHT_DATA').options = "emissive"
                
                if has_lightmap_props:
                    row_add_prop.operator_menu_enum("nwo.add_mesh_property_lightmap", property="options", text="Lightmap Settings", icon='OUTLINER_DATA_LIGHTPROBE')
    
    def draw_instance_proxies(self, box, ob):
        nwo = ob.data.nwo
        collision = nwo.proxy_collision
        physics = nwo.proxy_physics
        cookie_cutter = nwo.proxy_cookie_cutter

        if collision:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Collision", icon_value=get_icon_id("collider")).proxy = collision.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = collision.name

        if physics:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Physics", icon_value=get_icon_id("physics")).proxy = physics.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = physics.name

        if not self.h4 and cookie_cutter:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Cookie Cutter", icon_value=get_icon_id("cookie_cutter")).proxy = cookie_cutter.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = cookie_cutter.name

        if not (collision and physics and (self.h4 or cookie_cutter)):
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
                if mat.name == '+invisible':
                    col.label(text=f'Invisible {tag_type} applied')
                elif mat.name == '+invalid':
                    col.label(text=f'Default Invalid {tag_type} applied')
                elif mat.name == '+missing':
                    col.label(text=f'Default Missing {tag_type} applied')
                elif mat.name == '+seamsealer':
                    col.label(text=f'SeamSealer Material applied')
                elif mat.name == '+collision':
                    col.label(text=f'Collision Material applied')
                elif mat.name == '+sphere_collision':
                    col.label(text=f'Sphere Collision Material applied')
                else:
                    col.label(text=f'Sky Material applied')
                    sky_perm = utils.get_sky_perm(mat)
                    if sky_perm > -1:
                        if sky_perm > 31:
                            col.label(text='Maximum Sky Permutation Index is 31', icon='ERROR')
                        else:
                            col.label(text=f"Sky Permutation {str(sky_perm)}")
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
                    if full_path.exists() and shader_path.endswith(('.shader', '.material')):
                        col.operator('nwo.shader_to_nodes', text=f"Convert {txt} to Blender Material", icon='NODE_MATERIAL').mat_name = mat.name
                    col.separator()
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
                        col.label(text="Shader Tag Not Found", icon="ERROR")
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
            if not mat.node_tree:
                return
            if not utils.recursive_image_search(mat):
                return
            
            self.draw_expandable_box(self.box.box(), context.scene.nwo, "image_properties", material=mat)

                
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
        bitmap_path = utils.dot_partition(bitmap.filepath) + '.bitmap'
        if not Path(tags_dir, bitmap_path).exists():
            bitmap_path = utils.dot_partition(image.filepath_from_user().lower().replace(data_dir, "")) + '.bitmap'
        if not Path(tags_dir, bitmap_path).exists():
            col.separator()
            col.label(text='Bitmap Export Tools')
            col.operator("nwo.export_bitmaps_single", text="Export Bitmap", icon_value=get_icon_id("texture_export"))
            col.separator()
            col_props = col.column()
            col_props.use_property_split = True
            col_props.prop(bitmap, "bitmap_dir", text="Tiff Directory")
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
            col_props.prop(bitmap, "reexport_tiff", text="Always Export TIFF")

    def draw_animation_manager(self):
        box = self.box.box()
        row = box.row()
        context = self.context
        ob = context.object
        scene_nwo = context.scene.nwo
            
        if not bpy.data.actions:
            box.operator("nwo.new_animation", icon="ANIM", text="New Animation")
            box.operator("nwo.select_armature", text="Select Armature", icon='OUTLINER_OB_ARMATURE')
            return

        row.template_list(
            "NWO_UL_AnimationList",
            "",
            bpy.data,
            "actions",
            scene_nwo,
            "active_action_index",
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
        
        col = box.column()
        row = col.row()
        
        
        if scene_nwo.active_action_index < 0:
            col.label(text="No Animation Selected")
            return
        
        action = bpy.data.actions[scene_nwo.active_action_index]
        
        if not action.use_frame_range:
            col.label(text="Animation excluded from export", icon='ERROR')
            col.separator()
            
        if not action.use_fake_user:
            col.label(text="Fake User Not Set, Animation may be lost on Blender close", icon='ERROR')
            col.prop(action, 'use_fake_user', text="Enable Fake User", icon='FAKE_USER_OFF')
            col.separator()
        
        nwo = action.nwo
        col.separator()
        col.operator("nwo.animation_frames_sync_to_keyframes", text="Sync Frame Range to Keyframes", icon='FILE_REFRESH', depress=scene_nwo.keyframe_sync_active)
        col.separator()
        row = col.row()
        row.use_property_split = True
        row.prop(action, "frame_start", text='Start Frame')
        row = col.row()
        row.use_property_split = True
        row.prop(action, "frame_end", text='End Frame')
        col.separator()
        row = col.row()
        row.use_property_split = True
        row.prop(nwo, "animation_type")
        if nwo.animation_type != 'world':
            row = col.row()
            row.use_property_split = True
            if nwo.animation_type == 'base':
                row.prop(nwo, 'animation_movement_data')
            elif nwo.animation_type == 'overlay':
                row.prop(nwo, 'animation_is_pose')
                if nwo.animation_is_pose:
                    no_aim_pitch = not scene_nwo.node_usage_pose_blend_pitch
                    no_aim_yaw = not scene_nwo.node_usage_pose_blend_yaw
                    no_pedestal = not scene_nwo.node_usage_pedestal
                    if no_aim_pitch or no_aim_yaw or no_pedestal:
                        col.label(text='Pose Overlay needs Node Usages defined for:', icon='ERROR')
                        missing = []
                        if no_pedestal:
                            missing.append('Pedestal')
                        if no_aim_pitch:
                            missing.append('Pose Blend Pitch')
                        if no_aim_yaw:
                            missing.append('Pose Blend Yaw')
                        
                        col.label(text=', '.join(missing))
                        col.operator('nwo.add_pose_bones', text='Setup Rig for Pose Overlays', icon='SHADERFX')
                        col.separator()
                    else:
                        col.operator('nwo.add_aim_animation', text='Add/Change Aim Bones Animation', icon='ANIM')
                            
            elif nwo.animation_type == 'replacement':
                row.prop(nwo, 'animation_space', expand=True)
            col.separator()
            row = col.row()
            row.use_property_split = True
            row.prop(nwo, "compression", text="Compression")
            col.separator()
            row = col.row()
            row.use_property_split = True
            row.prop(nwo, "name_override")
            col.separator()
            row = col.row()
            # ANIMATION RENAMES
            if not nwo.animation_renames:
                row.operator("nwo.animation_rename_add", text="New Rename", icon_value=get_icon_id('animation_rename'))
            else:
                row = col.row()
                row.label(text="Animation Renames")
                row = col.row()
                rows = 3
                row.template_list(
                    "NWO_UL_AnimationRename",
                    "",
                    nwo,
                    "animation_renames",
                    nwo,
                    "animation_renames_index",
                    rows=rows,
                )
                col = row.column(align=True)
                col.operator("nwo.animation_rename_add", text="", icon="ADD")
                col.operator("nwo.animation_rename_remove", icon="REMOVE", text="")
                col.separator()
                col.operator("nwo.animation_rename_move", text="", icon="TRIA_UP").direction = 'up'
                col.operator("nwo.animation_rename_move", icon="TRIA_DOWN", text="").direction = 'down'

            # ANIMATION EVENTS
            if not nwo.animation_events:
                if nwo.animation_renames:
                    row = box.row()
                row.operator("animation_event.list_add", text="New Event", icon_value=get_icon_id('animation_event'))
            else:
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
                    "animation_events_index",
                    rows=rows,
                )

                col = row.column(align=True)
                col.operator("animation_event.list_add", icon="ADD", text="")
                col.operator("animation_event.list_remove", icon="REMOVE", text="")
                col.separator()
                col.operator("nwo.animation_event_move", text="", icon="TRIA_UP").direction = 'up'
                col.operator("nwo.animation_event_move", icon="TRIA_DOWN", text="").direction = 'down'

                if len(nwo.animation_events) > 0:
                    item = nwo.animation_events[nwo.animation_events_index]
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
                            row.prop(item, "frame_frame", text="Event Frame Start")
                            row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                            row = col.row(align=True)
                            row.prop(item, "frame_range", text="Event Frame End")
                            row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_range"
                        else:
                            row = col.row(align=True)
                            row.prop(item, "frame_frame")
                            row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"

                        col.prop(item, "frame_name")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_wrinkle_map"
                    ):
                        row = col.row(align=True)
                        row.prop(item, "frame_frame", text="Event Frame Start")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                        row = col.row(align=True)
                        row.prop(item, "frame_range", text="Event Frame End")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_range"
                        col.prop(item, "wrinkle_map_face_region")
                        col.prop(item, "wrinkle_map_effect")
                    elif item.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                        valid_ik_chains = [chain for chain in scene_nwo.ik_chains if chain.start_node and chain.effector_node]
                        if not valid_ik_chains:
                            col.label(text='Add IK Chains in the Asset Editor tab', icon='ERROR')
                            return
                        col.prop(item, "ik_chain")
                        # col.prop(item, "ik_active_tag")
                        # col.prop(item, "ik_target_tag")
                        col.prop(item, "ik_target_marker", icon_value=get_icon_id('marker'))
                        col.prop(item, "ik_target_usage")
                        col.prop(item, 'ik_influence')
                        # col.prop(item, "ik_proxy_target_id")
                        # col.prop(item, "ik_pole_vector_id")
                        # col.prop(item, "ik_effector_id")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_object_function"
                    ):
                        col.prop(item, "frame_frame")
                        col.prop(item, "frame_range")
                        col.prop(item, "object_function_name")
                        col.prop(item, "object_function_effect")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_import"
                    ):
                        col.prop(item, "import_frame")
                        col.prop(item, "import_name")
            col = box.column()

    def draw_tools(self):
        nwo = self.scene.nwo
        shader_type = "Material" if self.h4 else "Shader"
        self.draw_expandable_box(self.box.box(), nwo, "asset_shaders", f"Asset {shader_type}s")
        self.draw_expandable_box(self.box.box(), nwo, "importer")
        self.draw_expandable_box(self.box.box(), nwo, "camera_sync")
        if utils.poll_ui(('model', 'animation', 'sky', 'resource')):
            self.draw_expandable_box(self.box.box(), nwo, "rig_tools")
        if utils.poll_ui(('scenario', 'resource')):
            self.draw_expandable_box(self.box.box(), nwo, "bsp_tools", "BSP Tools")
            
    def draw_bsp_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        col.operator('nwo.auto_seam', text='Auto-Seam', icon_value=get_icon_id('seam'))
        col.operator('nwo.cubemap', text='Cubemap Farm', icon_value=get_icon_id("cubemap"))
        
    def draw_camera_sync(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        if self.scene.nwo.camera_sync_active:
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
        amf_installed = utils.amf_addon_installed()
        toolset_installed = utils.blender_toolset_installed()
        if amf_installed or toolset_installed:
            col.operator('nwo.import', text="Import Models & Animations", icon='IMPORT').scope = 'amf,jma,jms,model'
        if not toolset_installed:
            col.label(text="Halo Blender Toolset required for import of legacy model and animation files")
            col.operator("nwo.open_url", text="Download", icon="BLENDER").url = BLENDER_TOOLSET
        if not amf_installed:
            col.label(text="AMF Importer required to import amf files")
            col.operator("nwo.open_url", text="Download", icon_value=get_icon_id("amf")).url = AMF_ADDON
            
        col.operator('nwo.import', text="Import Bitmaps", icon='IMAGE_DATA').scope = 'bitmap'
        col.operator('nwo.rename_import', text="Import Animation Renames & Copies", icon_value=get_icon_id("animation_rename"))
        col.operator("nwo.convert_scene", text="Convert Scene", icon='RIGHTARROW')
        
    def draw_rig_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        nwo = self.scene.nwo
        col.use_property_split = True
        col.operator("nwo.fcurve_transfer", icon='GRAPH')
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
        if nwo.needs_pose_bones:
            col.label(text='Rig not setup for pose overlay animations', icon='ERROR')
            col.operator('nwo.add_pose_bones', text='Fix for Pose Overlays', icon='SHADERFX')
        if nwo.pose_bones_bad_transforms:
            col.label(text='Pose bones have bad transforms', icon='ERROR')
            col.operator('nwo.fix_pose_bones', text='Fix Pose Bones', icon='SHADERFX')
        if nwo.too_many_bones:
            col.label(text='Rig exceeds the maxmimum number of bones', icon='ERROR')
        if nwo.bone_names_too_long:
            col.label(text='Rig has bone names that exceed 31 characters', icon='ERROR')
            

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
        col.operator("nwo.stomp_materials", text=f"Remove Duplicate Materials", icon='X')
        col.operator("nwo.clear_shader_paths", text=f"Clear {shader_type} paths", icon='X')
        col.separator()
        col.operator("nwo.append_foundry_materials", text="Append Special Materials", icon_value=get_icon_id("special_material"))
        col.operator("nwo.append_grid_materials", text="Append Grid Materials", icon_value=get_icon_id("grid_material"))
        if h4:
            col.separator()
            col.operator("nwo.open_matman", text="Open Material Tag Viewer", icon_value=get_icon_id("foundation"))


    def draw_help(self):
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
        row.prop(prefs, "apply_materials", text="Apply Types Operator Updates Materials")
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
                    if prop.region_name_override:
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
        nwo = context.scene.nwo
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
        nwo = context.scene.nwo
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
        nwo = context.scene.nwo
        prop = f"{self.panel_str}_expanded"
        setattr(nwo, prop, not getattr(nwo, prop))
        return {"FINISHED"}
    
    @classmethod
    def description(cls, context, properties):
        pass
