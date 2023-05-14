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

import bpy
import os
import random
from bl_ui.generic_ui_list import draw_ui_list

from bpy.types import (
        Context,
        Operator,
        Panel,
        UIList,
        PropertyGroup,
        Menu
        )

from bpy.props import (
        IntProperty,
        BoolProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        PointerProperty,
        FloatVectorProperty,
        CollectionProperty,
        )

from ..utils.nwo_utils import (
    formalise_game_version,
    frame_prefixes,
    get_data_path,
    is_linked,
    managed_blam_active,
    marker_prefixes,
    mesh_object,
    run_ek_cmd,
    poop_render_only_prefixes,
    get_prop_from_collection,
    is_design,
    get_ek_path,
    not_bungie_game,
    clean_tag_path,
    get_tags_path,
    shortest_string,
    dot_partition,
    valid_nwo_asset,
    package,
)

from io_scene_foundry.icons import get_icon_id

class NWO_SceneProps(Panel):
    bl_label = "Halo Scene"
    bl_idname = "NWO_PT_ScenePropertiesPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_global = scene.nwo_global
        scene_nwo = context.scene.nwo
        mb_active = managed_blam_active()
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        if mb_active:
            flow.enabled = False
        row = flow.row()
        row.prop(scene_nwo_global, "game_version", text='')
        row.scale_y = 1.5
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
        if mb_active or scene_nwo_global.mb_startup:
            col.prop(scene_nwo_global, 'mb_startup')
        col.separator()
        col = col.row()
        col.scale_y = 1.5
        if not valid_nwo_asset(context):
            col.operator("nwo.make_asset")
        if mb_active:
            col.label(text="ManagedBlam Active")
        elif os.path.exists(os.path.join(bpy.app.tempdir, 'blam_new.txt')):
            col.label(text="Blender Restart Required for ManagedBlam")
        else:
            col.operator("managed_blam.init", text="Initialise ManagedBlam")

        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column(heading="Asset Type")
        col.scale_y = 1.5
        col.prop(scene_nwo, 'asset_type', text='')
        col = col.column(heading="Model Forward")
        #col.prop(scene_nwo, 'default_mesh_type_ui')
        if scene_nwo.asset_type in ('MODEL', 'FP ANIMATION'):
            col.prop(scene_nwo, 'forward_direction', text='')
        if scene_nwo.asset_type == 'MODEL':
            col.label(text="Output Tags")
            row = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=True, align=True)
            row.scale_x = 1.3
            row.scale_y = 1.3

            row.prop(scene_nwo, "output_crate", text='',icon_value=get_icon_id('crate'))
            row.prop(scene_nwo, "output_scenery",text='',icon_value=get_icon_id('scenery'))
            row.prop(scene_nwo, "output_effect_scenery",text='',icon_value=get_icon_id('effect_scenery'))

            row.prop(scene_nwo, "output_device_control",text='',icon_value=get_icon_id('device_control'))
            row.prop(scene_nwo, "output_device_machine", text='',icon_value=get_icon_id('device_machine'))
            row.prop(scene_nwo, "output_device_terminal", text='',icon_value=get_icon_id('device_terminal'))
            if context.scene.nwo_global.game_version in ('h4', 'h2a'):
                row.prop(scene_nwo, "output_device_dispenser",text='',icon_value=get_icon_id('device_dispenser'))

            row.prop(scene_nwo, "output_biped", text='', icon_value=get_icon_id('biped'))
            row.prop(scene_nwo, "output_creature",text='',icon_value=get_icon_id('creature'))
            row.prop(scene_nwo, "output_giant", text='', icon_value=get_icon_id('giant'))
            
            row.prop(scene_nwo, "output_vehicle", text='',icon_value=get_icon_id('vehicle'))
            row.prop(scene_nwo, "output_weapon", text='',icon_value=get_icon_id('weapon'))
            row.prop(scene_nwo, "output_equipment",text='',icon_value=get_icon_id('equipment'))

class NWO_SetUnitScale(Operator):
    """Sets up the scene for Halo: Sets the unit scale to match Halo's and sets the frame rate to 30fps"""
    bl_idname = 'nwo.set_unit_scale'
    bl_label = 'Set Halo Scene'
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Set the frame rate to 30
        context.scene.render.fps = 30
        # define the Halo scale
        halo_scale = 0.03048
        # Apply scale to clipping in all windows if halo_scale has not already been set
        if round(context.scene.unit_settings.scale_length, 5) != halo_scale:
            for workspace in bpy.data.workspaces:
                for screen in workspace.screens:
                    for area in screen.areas:
                        if area.type == 'VIEW_3D':
                            for space in area.spaces:
                                if space.type == 'VIEW_3D':
                                    space.clip_start = space.clip_start / halo_scale
                                    space.clip_end = space.clip_end / halo_scale
        # Set halo scale
        context.scene.unit_settings.scale_length = halo_scale
        return {'FINISHED'}
    
class NWO_AssetMaker(Operator):
    """Creates an asset"""
    bl_idname = "nwo.make_asset"
    bl_label = "Create New Asset"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="",
        options={'HIDDEN'},
        )

    use_filter_folder : BoolProperty(default = True)

    filepath: StringProperty(
        name="asset_path",
        description="Set the location of your asset",
        subtype="FILE_PATH"
    )

    asset_name : StringProperty(default = 'new_asset')

    work_dir : BoolProperty(description="Set whether blend file should be saved to a work directory within the asset folder")

    managed_blam : BoolProperty(description="When set asset will use ManagedBlam on startup", default=True)

    def execute(self, context):
        scene = context.scene
        nwo_scene = scene.nwo_global
        nwo_asset = scene.nwo
        asset_name = self.filepath.rpartition(os.sep)[2]
        asset_name_clean = dot_partition(asset_name)
        # check folder location valid
        if not self.filepath.startswith(get_data_path()):
            # try to fix it...
            prefs = context.preferences.addons[package].preferences
            if self.filepath.startswith(prefs.hrek_path):
                self.filepath = self.filepath.replace(os.path.join(prefs.hrek_path, 'data' + os.sep), get_data_path())
            elif self.filepath.startswith(prefs.h4ek_path):
                self.filepath = self.filepath.replace(os.path.join(prefs.h4ek_path, 'data' + os.sep), get_data_path())
            elif self.filepath.startswith(prefs.h2aek_path):
                self.filepath = self.filepath.replace(os.path.join(prefs.h2aek_path, 'data' + os.sep), get_data_path())
            else:
                self.report({'INFO'}, f"Invalid asset location. Please ensure your file is saved to your data {formalise_game_version(nwo_scene.game_version)} directory")
                return {'CANCELLED'}
        
        os.makedirs(self.filepath, True)
        sidecar_path_full = os.path.join(self.filepath, asset_name_clean + 'sidecar.xml')
        open(sidecar_path_full, 'x')
        scene.nwo_halo_launcher.sidecar_path = sidecar_path_full.replace(get_data_path(),'')

        if self.work_dir:
            blend_save_path = os.path.join(self.filepath, 'models', 'work', asset_name_clean + '.blend')
            os.makedirs(os.path.dirname(blend_save_path), True)
        else:
            blend_save_path = os.path.join(self.filepath, asset_name_clean + '.blend')

        bpy.ops.wm.save_as_mainfile(filepath=blend_save_path)

        if self.managed_blam:
            bpy.ops.managed_blam.init()
            nwo_scene.mb_startup = True

        self.report({'INFO'}, f"Created new {nwo_asset.asset_type.title()} asset for {formalise_game_version(nwo_scene.game_version)}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nwo_scene = scene.nwo_global
        nwo_asset = scene.nwo
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
        col = flow.column(heading="Asset Settings")
        col.prop(nwo_scene, "game_version", text='', expand=True)
        col.separator()
        col.prop(nwo_asset, "asset_type", text='')
        col.separator()
        col.prop(self, "work_dir", text="Save to work directory")
        col.prop(self, "managed_blam", text="Enable ManagedBlam")
        if nwo_asset.asset_type == 'MODEL':
            col.separator()
            col.label(text="Model Output Tags")
            flow = col.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=False, align=True)
            flow.scale_x = 1.25
            flow.scale_y = 1.25
            flow.prop(nwo_asset, "output_crate", text='',icon_value=get_icon_id('crate'))
            flow.prop(nwo_asset, "output_scenery",text='',icon_value=get_icon_id('scenery'))
            flow.prop(nwo_asset, "output_effect_scenery",text='',icon_value=get_icon_id('effect_scenery'))

            flow.prop(nwo_asset, "output_device_control",text='',icon_value=get_icon_id('device_control'))
            flow.prop(nwo_asset, "output_device_machine", text='',icon_value=get_icon_id('device_machine'))
            flow.prop(nwo_asset, "output_device_terminal", text='',icon_value=get_icon_id('device_terminal'))
            if context.scene.nwo_global.game_version in ('h4', 'h2a'):
                flow.prop(nwo_asset, "output_device_dispenser",text='',icon_value=get_icon_id('device_dispenser'))

            flow.prop(nwo_asset, "output_biped", text='', icon_value=get_icon_id('biped'))
            flow.prop(nwo_asset, "output_creature",text='',icon_value=get_icon_id('creature'))
            flow.prop(nwo_asset, "output_giant", text='', icon_value=get_icon_id('giant'))
            
            flow.prop(nwo_asset, "output_vehicle", text='',icon_value=get_icon_id('vehicle'))
            flow.prop(nwo_asset, "output_weapon", text='',icon_value=get_icon_id('weapon'))
            flow.prop(nwo_asset, "output_equipment",text='',icon_value=get_icon_id('equipment'))

    
    def invoke(self, context, event):
        self.filepath = get_data_path() + self.asset_name
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

def game_version_warning(self, context):
    self.layout.label(text=f"Please set your editing kit path for {context.scene.nwo_global.game_version.upper()} in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset]")

def prefab_warning(self, context):
    self.layout.label(text=f"Halo Reach does not support prefab assets")

class NWO_ScenePropertiesGroup(PropertyGroup):
    def check_paths_update_scene(self, context):
        ek_path = get_ek_path()
        if ek_path is None or ek_path == '':
            context.window_manager.popup_menu(game_version_warning, title="Warning", icon='ERROR')

        # store this value in a txt file so we can retrive it when changing scene
        temp_file_path = os.path.join(bpy.app.tempdir, 'game_version.txt')
        with open(temp_file_path, 'w') as temp_file:
            temp_file.write(f'{self.game_version}')

        scene = context.scene
        nwo_asset = scene.nwo
        if nwo_asset.asset_type == '' and self.game_version == 'reach':
            nwo_asset.asset_type = 'SCENARIO'

    def game_version_items(self, context):
        items = [ ('reach', "Halo Reach", "Halo Reach", get_icon_id("halo_reach"), 0),
                ('h4', "Halo 4", "Halo 4", get_icon_id("halo_4"), 1),
                ('h2a', "Halo 2AMP", "Halo 2 Anniversary Multiplayer", get_icon_id("halo_2amp"), 2),
               ]
        return items
                
    game_version: EnumProperty(
        name="Game",
        options=set(),
        update=check_paths_update_scene,
        items=game_version_items,
    )
    
    mb_startup: BoolProperty(
        name="Run ManagedBlam on Startup",
        description="Runs ManagedBlam.dll on Blender startup, this will lock the selected game on startup. Disable and and restart blender if you wish to change the selected game.",
        )
    
    def get_temp_settings(self):
        scene = bpy.context.scene
        temp_file_path = os.path.join(bpy.app.tempdir, 'nwo_scene_settings.txt')
        if os.path.exists(temp_file_path):
            with open(temp_file_path, 'r') as temp_file:
                settings = temp_file.readlines()

            settings = [line.strip() for line in settings]
            scene.nwo_halo_launcher.sidecar_path = settings[0]
            scene.nwo_global.game_version = settings[1]
            scene.nwo.asset_type = settings[2]
            scene.nwo.output_biped = True if settings[3] == 'True' else False
            scene.nwo.output_crate = True if settings[4] == 'True' else False
            scene.nwo.output_creature = True if settings[5] == 'True' else False
            scene.nwo.output_device_control = True if settings[6] == 'True' else False
            scene.nwo.output_device_dispenser = True if settings[7] == 'True' else False
            scene.nwo.output_device_machine = True if settings[8] == 'True' else False
            scene.nwo.output_device_terminal = True if settings[9] == 'True' else False
            scene.nwo.output_effect_scenery = True if settings[10] == 'True' else False
            scene.nwo.output_equipment = True if settings[11] == 'True' else False
            scene.nwo.output_giant = True if settings[12] == 'True' else False
            scene.nwo.output_scenery = True if settings[13] == 'True' else False
            scene.nwo.output_vehicle = True if settings[14] == 'True' else False
            scene.nwo.output_weapon = True if settings[15] == 'True' else False
            scene.nwo_export.show_output = True if settings[16] == 'True' else False

            os.remove(temp_file_path)

        return False

    temp_file_watcher: BoolProperty(
        name = "",
        default = False,
        get=get_temp_settings,
        )

##################################################################################################################
####################################### NWO PROPERTIES ##########################################################
##################################################################################################################

# ----- OBJECT PROPERTIES -------
# -------------------------------

# ------------------------------------------------------------------------
# TAG PATH BUTTONS
# ------------------------------------------------------------------------

class NWO_GameInstancePath(Operator):
    """Set the path to a game instance tag"""
    bl_idname = "nwo.game_instance_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.biped;*.crate;*.creature;*.device_*;*.effect_*;*.equipment;*.giant;*.scenery;*.vehicle;*.weapon;*.prefab;*.cheap_l*;*.light",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="game_instance_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.marker_game_instance_tag_name = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_FogPath(Operator):
    """Set the path to a fog tag"""
    bl_idname = "nwo.fog_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.atmosphere_",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="fog_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.fog_appearance_tag = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}
    
class NWO_EffectPath(Operator):
    """Set the path to an effect tag"""
    bl_idname = "nwo.effect_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.effect",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="fog_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.marker_looping_effect = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightConePath(Operator):
    """Set the path to a light cone tag"""
    bl_idname = "nwo.light_cone_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.light_",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="fog_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.marker_light_cone_tag = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightConeCurvePath(Operator):
    """Set the path to a light cone curve tag"""
    bl_idname = "nwo.light_cone_curve_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.curve_",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="fog_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.marker_light_cone_curve = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightTagPath(Operator):
    """Set the path to a light tag"""
    bl_idname = "nwo.light_tag_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.light",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="light_tag_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.light_tag_override = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightShaderPath(Operator):
    """Set the path to a light shader tag"""
    bl_idname = "nwo.light_shader_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.render_",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="light_shader_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.light_shader_reference = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightGelPath(Operator):
    """Set the path to a gel bitmap"""
    bl_idname = "nwo.light_gel_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.bitmap",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="light_gel_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.light_gel_reference = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LensFlarePath(Operator):
    """Set the path to a lens flare bitmap"""
    bl_idname = "nwo.lens_flare_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.lens_",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="lens_flare_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_object = context.active_object
        active_object.nwo.light_lens_flare_reference = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_ShaderPath(Operator):
    """Set the path to a material / shader tag"""
    bl_idname = "nwo.shader_path"
    bl_label = "Find"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.material;*.shader*",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="shader_path",
        description="Set the path to the tag",
        subtype="FILE_PATH"
    )

    def execute(self, context):
        active_material = context.active_object.active_material
        active_material.nwo.shader_path = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

# ------------------------------------------------------------------------('?'
# MAIN UI
# ------------------------------------------------------------------------

def poll_ui(selected_types):
    scene_nwo = bpy.context.scene.nwo
    type = scene_nwo.asset_type

    return type in selected_types

class NWO_ObjectProps(Panel):
    bl_label = "Halo Object Properties"
    bl_idname = "NWO_PT_ObjectDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob.type not in ('ARMATURE', 'LATTICE', 'LIGHT_PROBE', 'SPEAKER', 'CAMERA') and not (ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE') and poll_ui(('MODEL', 'SCENARIO', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'PREFAB'))
    
    def draw_header(self, context):
        self.layout.prop(context.object.nwo, "export_this", text='')
    
    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        ob = context.object
        ob_nwo = ob.nwo
        h4 = not_bungie_game()

        if not ob_nwo.export_this:
            layout.label(text="Object is excluded from export")
            layout.active = False
        else:
            col = flow.column()
            row = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
            row.scale_x = 1.3
            row.scale_y = 1.3
            row.prop(ob_nwo, "object_type_ui", text='', expand=True)
            # if CheckType.frame(ob) and h4:
            #     col.prop(ob_nwo, 'is_pca')

            if ob_nwo.object_type_ui == '_connected_geometry_object_type_light':
                flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
                col = flow.column()
                col.use_property_split = True
                if poll_ui('SCENARIO'):
                    if ob_nwo.permutation_name_locked != '':
                        col.prop(ob_nwo, 'permutation_name_locked', text='Permutation')
                    else:
                        col.prop(ob_nwo, 'permutation_name', text='Permutation')

                    if ob_nwo.bsp_name_locked != '':
                        col.prop(ob_nwo, 'bsp_name_locked', text='BSP')
                    else:
                        col.prop(ob_nwo, 'bsp_name', text='BSP')

                    col.separator()

                col.label(text="See the Object Data Properties panel for Halo Light Properties")

            elif ob_nwo.object_type_ui == '_connected_geometry_object_type_mesh':
                # SPECIFIC MESH PROPS
                flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

                col = flow.column()
                row = col.row()
                row.scale_y = 1.25
                row.emboss = 'NORMAL'
                row.prop(ob_nwo, "mesh_type_ui", text="")
                # row.menu(NWO_MeshMenu.bl_idname, text=mesh_type_name, icon_value=get_icon_id(mesh_type_icon))

                col.separator()
                flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
                col = flow.column()
                col.use_property_split = True

                if poll_ui(('MODEL', 'SCENARIO')):
                    if poll_ui('MODEL') and ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_object_instance':
                        pass
                    elif ob_nwo.permutation_name_locked != '':
                        col.prop(ob_nwo, 'permutation_name_locked', text='Permutation')
                    else:
                        col.prop(ob_nwo, 'permutation_name', text='Permutation')

                if poll_ui('SCENARIO'):
                    if is_design(ob):
                        if ob_nwo.bsp_name_locked != '':
                            col.prop(ob_nwo, 'bsp_name_locked', text='Design Group')
                        else:
                            col.prop(ob_nwo, 'bsp_name', text='Design Group')
                    else:
                        if ob_nwo.bsp_name_locked != '':
                            col.prop(ob_nwo, 'bsp_name_locked', text='BSP')
                        else:
                            col.prop(ob_nwo, 'bsp_name', text='BSP')

                col.separator()

                if ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_decorator':
                    col.prop(ob_nwo, "decorator_lod")

                elif ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_physics':
                    col.prop(ob_nwo, "mesh_primitive_type", text='Primitive Type')

                elif ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_plane':
                    row = col.row()
                    row.scale_y = 1.25
                    row.prop(ob_nwo, "plane_type_ui")

                    if ob_nwo.plane_type_ui == '_connected_geometry_plane_type_portal':
                        row = col.row()
                        row.prop(ob_nwo, "portal_type", text='Portal Type', expand=True)

                        col.separator()

                        col = col.column(heading="Flags")

                        col.prop(ob_nwo, "portal_ai_deafening", text='AI Deafening')
                        col.prop(ob_nwo, "portal_blocks_sounds", text='Blocks Sounds')
                        col.prop(ob_nwo, "portal_is_door", text='Is Door')

                    elif ob_nwo.plane_type_ui == '_connected_geometry_plane_type_planar_fog_volume':
                        col.prop(ob_nwo, "fog_name", text='Fog Name')
                        row = col.row()
                        row.prop(ob_nwo, "fog_appearance_tag", text='Fog Appearance Tag')
                        row.operator('nwo.fog_path')
                        col.prop(ob_nwo, "fog_volume_depth", text='Fog Volume Depth')

                    elif ob_nwo.plane_type_ui == '_connected_geometry_plane_type_water_surface':
                        col.prop(ob_nwo, "mesh_tessellation_density")

                elif ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_volume':
                    row = col.row()
                    row.scale_y = 1.25
                    row.prop(ob_nwo, "volume_type_ui")

                    if ob_nwo.volume_type_ui == '_connected_geometry_volume_type_water_physics':
                        col.separator()
                        col.prop(ob_nwo, "water_volume_depth", text='Water Volume Depth')
                        col.prop(ob_nwo, "water_volume_flow_direction", text='Flow Direction')
                        col.prop(ob_nwo, "water_volume_flow_velocity", text='Flow Velocity')
                        col.prop(ob_nwo, "water_volume_fog_color", text='Underwater Fog Color')
                        col.prop(ob_nwo, "water_volume_fog_murkiness", text='Underwater Fog Murkiness')

                elif ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop_collision':
                    col.prop(ob_nwo, "poop_collision_type")

                elif ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop':
                    col.prop(ob_nwo, "poop_lighting_override", text='Lighting Policy')
                    
                    if h4:
                        col.prop(ob_nwo, "poop_lightmap_resolution_scale")
                        
                    col.prop(ob_nwo, "poop_pathfinding_override", text='Pathfinding Policy')

                    col.prop(ob_nwo, "poop_imposter_policy", text='Imposter Policy')
                    if ob_nwo.poop_imposter_policy != '_connected_poop_instance_imposter_policy_never':
                        sub = col.row(heading="Imposter Transition")
                        sub.prop(ob_nwo, 'poop_imposter_transition_distance_auto', text='Automatic')
                        if not ob_nwo.poop_imposter_transition_distance_auto:
                            sub.prop(ob_nwo, 'poop_imposter_transition_distance', text='Distance')
                        if h4:
                            col.prop(ob_nwo, 'poop_imposter_brightness')

                    if h4:
                        col.prop(ob_nwo, 'poop_streaming_priority')
                        col.prop(ob_nwo, 'poop_cinematic_properties')

                    col.separator()

                    col = col.column(heading="Flags")

                    col.prop(ob_nwo, "poop_render_only", text='Render Only')

                    col.prop(ob_nwo, "poop_chops_portals", text='Chops Portals')
                    col.prop(ob_nwo, "poop_does_not_block_aoe", text='Does Not Block AOE')
                    col.prop(ob_nwo, "poop_excluded_from_lightprobe", text='Excluded From Lightprobe')
                    col.prop(ob_nwo, "poop_decal_spacing", text='Decal Spacing')
                    if h4:
                        col.prop(ob_nwo, "poop_remove_from_shadow_geometry")
                        col.prop(ob_nwo, "poop_disallow_lighting_samples",)
                        # col.prop(ob_nwo, "poop_rain_occluder")

            elif ob_nwo.object_type_ui == '_connected_geometry_object_type_marker' and poll_ui(('MODEL', 'SCENARIO', 'SKY')):
                # MARKER PROPERTIES
                flow = layout.grid_flow(row_major=True, columns=0, even_columns=False, even_rows=False, align=False)
                flow.use_property_split = False
                col = flow.column()
                row = col.row()
                row.scale_y = 1.25
                row.emboss = 'NORMAL'
                row.prop(ob_nwo, "marker_type_ui", text="")

                col.separator()

                flow = layout.grid_flow(row_major=True, columns=0, even_columns=False, even_rows=False, align=False)
                flow.use_property_split = True
                col = flow.column()

                if poll_ui('SCENARIO'):
                    if ob_nwo.permutation_name_locked != '':
                        col.prop(ob_nwo, 'permutation_name_locked', text='Permutation')
                    else:
                        col.prop(ob_nwo, 'permutation_name', text='Permutation')

                    if is_design(ob):
                        if ob_nwo.bsp_name_locked != '':
                            col.prop(ob_nwo, 'bsp_name_locked', text='Design Group')
                        else:
                            col.prop(ob_nwo, 'bsp_name', text='Design Group')
                    else:
                        if ob_nwo.bsp_name_locked != '':
                            col.prop(ob_nwo, 'bsp_name_locked', text='BSP')
                        else:
                            col.prop(ob_nwo, 'bsp_name', text='BSP')
                            
                    col.separator()

                if ob_nwo.marker_type_ui == '_connected_geometry_marker_type_model':
                    col.prop(ob_nwo, "marker_group_name", text='Marker Group')
                    if poll_ui(('MODEL', 'SKY')):
                        row = col.row()
                        sub = col.row(align=True)
                        if not ob_nwo.marker_all_regions:
                            if ob_nwo.region_name_locked != '':
                                col.prop(ob_nwo, 'region_name_locked', text='Region')
                            else:
                                col.prop(ob_nwo, "region_name", text='Region')
                        sub.prop(ob_nwo, 'marker_all_regions', text='All Regions')

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_game_instance':
                    row = col.row()
                    row.prop(ob_nwo, "marker_game_instance_tag_name", text='Tag Path')
                    row.operator('nwo.game_instance_path')
                    if not ob_nwo.marker_game_instance_tag_name.endswith(('.prefab', '.cheap_light', '.light','.leaf')):
                        col.prop(ob_nwo, "marker_game_instance_tag_variant_name", text='Tag Variant')
                        if h4:
                            col.prop(ob_nwo, 'marker_game_instance_run_scripts') 
                        
                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_hint':
                    row = col.row(align=True)
                    row.prop(ob_nwo, "marker_hint_type")
                    if ob_nwo.marker_hint_type == 'corner':
                        row = col.row(align=True)
                        row.prop(ob_nwo, "marker_hint_side", expand=True)
                    elif ob_nwo.marker_hint_type in ('vault', 'mount', 'hoist'):
                        row = col.row(align=True)
                        row.prop(ob_nwo, "marker_hint_height", expand=True)
                    if h4:
                        col.prop(ob_nwo, 'marker_hint_length')

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_effects':
                    col.prop(ob_nwo, "marker_group_name", text='Marker Group')

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_garbage':
                    col.prop(ob_nwo, "marker_group_name", text='Marker Group')
                    col.prop(ob_nwo, "marker_velocity", text='Marker Velocity')

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_pathfinding_sphere':
                    col = col.column(heading="Flags")
                    col.prop(ob_nwo, "marker_pathfinding_sphere_vehicle", text='Vehicle Only')
                    col.prop(ob_nwo, "pathfinding_sphere_remains_when_open", text='Remains When Open')
                    col.prop(ob_nwo, "pathfinding_sphere_with_sectors", text='With Sectors')
                    if ob.type != 'MESH':
                        col.prop(ob_nwo, "marker_sphere_radius")

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_physics_constraint':
                    col.prop(ob_nwo, "physics_constraint_parent", text='Constraint Parent')
                    col.prop(ob_nwo, "physics_constraint_child", text='Constraint Child')
                    row = col.row()
                    row.prop(ob_nwo, "physics_constraint_type", text='Constraint Type', expand=True)
                    col.prop(ob_nwo, 'physics_constraint_uses_limits', text='Uses Limits')

                    if ob_nwo.physics_constraint_uses_limits:
                        if ob_nwo.physics_constraint_type == '_connected_geometry_marker_type_physics_hinge_constraint':
                            col.prop(ob_nwo, "hinge_constraint_minimum", text='Minimum')
                            col.prop(ob_nwo, "hinge_constraint_maximum", text='Maximum')

                        elif ob_nwo.physics_constraint_type == '_connected_geometry_marker_type_physics_socket_constraint':
                            col.prop(ob_nwo, "cone_angle", text='Cone Angle')

                            col.prop(ob_nwo, "plane_constraint_minimum", text='Plane Minimum')
                            col.prop(ob_nwo, "plane_constraint_maximum", text='Plane Maximum')
                            
                            col.prop(ob_nwo, "twist_constraint_start", text='Twist Start')
                            col.prop(ob_nwo, "twist_constraint_end", text='Twist End')

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_target':
                    col.prop(ob_nwo, "marker_group_name", text='Marker Group')
                    if ob.type != 'MESH':
                        col.prop(ob_nwo, "marker_sphere_radius")

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_airprobe' and h4:
                    col.prop(ob_nwo, "marker_group_name", text='Air Probe Group')

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_envfx' and h4:
                    row = col.row()
                    row.prop(ob_nwo, "marker_looping_effect")
                    row.operator('nwo.effect_path') 

                elif ob_nwo.marker_type_ui == '_connected_geometry_marker_type_lightCone' and h4:
                    row = col.row()
                    row.prop(ob_nwo, "marker_light_cone_tag")
                    row.operator('nwo.light_cone_path') 
                    col.prop(ob_nwo, "marker_light_cone_color")
                    col.prop(ob_nwo, "marker_light_cone_alpha") 
                    col.prop(ob_nwo, "marker_light_cone_intensity")
                    col.prop(ob_nwo, "marker_light_cone_width")
                    col.prop(ob_nwo, "marker_light_cone_length")
                    row = col.row()
                    row.prop(ob_nwo, "marker_light_cone_curve")
                    row.operator('nwo.light_cone_curve_path')

# MESH FACE PROPS
class NWO_MeshFaceProps(Panel):
    bl_label = "Mesh Properties"
    bl_idname = "NWO_PT_MeshPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_parent_id = "NWO_PT_ObjectDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object
        valid_mesh_types = ('_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_render', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_physics')
        return ob and ob.nwo.export_this and ob.type == 'MESH' and ob.nwo.object_type_ui == '_connected_geometry_object_type_mesh' and ob.nwo.mesh_type_ui in valid_mesh_types

    def draw(self, context):
        layout = self.layout
        ob = context.object
        ob_nwo = ob.nwo
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
        col.use_property_split = True
        if poll_ui(('MODEL', 'SKY', 'DECORATOR SET')):
            if ob_nwo.region_name_locked != '':
                col.prop(ob_nwo, 'region_name_locked', text='Region')
            else:
                row = col.row(align=True)
                row.prop(ob_nwo, "region_name", text='Region')
                if ob.nwo_face.face_props and ob_nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_render', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics'):
                    for prop in ob.nwo_face.face_props:
                        if prop.region_name_override:
                            row.label(text='*')
                            break
        if poll_ui(('MODEL', 'SCENARIO', 'PREFAB')):
            if ob_nwo.mesh_type_ui in ('_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_poop_collision', '_connected_geometry_mesh_type_structure'):
                col.prop(ob_nwo, "face_global_material", text='Global Material')
                if ob.nwo_face.face_props and ob_nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_poop', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_object_structure'):
                    for prop in ob.nwo_face.face_props:
                        if prop.face_global_material_override:
                            row.label(text='*')
                            break

        if poll_ui(('MODEL', 'SCENARIO', 'PREFAB')):
            if ob_nwo.mesh_type_ui in ('_connected_geometry_mesh_type_render', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_structure'):
                col2 = col.column(heading="Flags")
                flow2 = col2.grid_flow()
                flow2.prop(ob_nwo, "precise_position")


        # if poll_ui(('SCENARIO', 'PREFAB')):
        #     layout.operator_menu_enum("nwo_face.add_face_property_face_type_new",
        #                             property="options",
        #                             text="Type",
        #                             )
        #     layout.operator_menu_enum("nwo_face.add_face_property_face_mode_new",
        #                             property="options",
        #                             text="Mode",
        #                             )
        #     layout.operator_menu_enum("nwo_face.add_face_property_flags_new",
        #                             property="options",
        #                             text="Flags",
        #                             )
        #     layout.operator_menu_enum("nwo_face.add_face_property_lightmap_new",
        #                             property="options",
        #                             text="Lightmap",
        #                             )
        #     layout.operator_menu_enum("nwo_face.add_face_property_material_lighting_new",
        #                             property="options",
        #                             text="Emissive",
        #                             )

# MATERIAL PROPERTIES
class NWO_ShaderProps(Panel):
    bl_label = "Halo Shader Path"
    bl_idname = "NWO_PT_ShaderPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material and not not_bungie_game()

    def draw_header(self, context):
        current_material = context.material
        material_nwo = current_material.nwo
        self.layout.prop(material_nwo, "rendered", text='')

    def draw(self, context):
        layout = self.layout
        current_material = context.material
        material_nwo = current_material.nwo
        if not material_nwo.rendered:
            if self.bl_idname == 'NWO_PT_MaterialPanel':
                layout.label(text="Not a Halo Material")
            else:
                layout.label(text="Not a Halo Shader")

            layout.enabled = False

        else:
            # layout.use_property_split = True
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            # fun setup to display the correct fields
            if self.bl_idname == 'NWO_PT_MaterialPanel':
                row = col.row()
                row.prop(material_nwo, "shader_path", text='')
                row.operator('nwo.shader_path')

            else:
                row = col.row()
                row.prop(material_nwo, "shader_path", text='')
                row.operator('nwo.shader_path')
                # col.prop(material_nwo, "shader_type")

            if material_nwo.shader_path != '':
                col.separator()
                row = col.row()
                row.scale_y = 1.5
                row.operator('nwo.open_halo_material')

class NWO_MaterialProps(NWO_ShaderProps):
    bl_label = "Halo Material Path"
    bl_idname = "NWO_PT_MaterialPanel"

    @classmethod
    def poll(cls, context):
        return context.material and not_bungie_game()

class NWO_MaterialOpenTag(Operator):
    """Opens the active material's Halo Shader/Material in Foundation"""
    bl_idname = 'nwo.open_halo_material'
    bl_label = 'Open in Foundation'
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tag_path = get_tags_path() + context.object.active_material.nwo.shader_path
        if os.path.exists(tag_path):
            run_ek_cmd(['foundation', '/dontloadlastopenedwindows', tag_path])
        else:
            if not_bungie_game():
                self.report({'ERROR_INVALID_INPUT'}, 'Material tag does not exist')
            else:
                self.report({'ERROR_INVALID_INPUT'}, 'Shader tag does not exist')

        return {'FINISHED'}
                        
# LIGHT PROPERTIES
class NWO_LightProps(Panel):
    bl_label = "Halo Light Properties"
    bl_idname = "NWO_PT_LightPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "DATA_PT_EEVEE_light"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        data = context.object.data
        ob_nwo = data.nwo

        col = flow.column()

        scene = context.scene
        scene_nwo = scene.nwo_global

        if scene_nwo.game_version in ('h4','h2a'):
            # col.prop(ob_nwo, 'Light_Color', text='Color')
            row = col.row()
            row.prop(ob_nwo, 'light_mode', expand=True)
            row = col.row()
            row.prop(ob_nwo, 'light_lighting_mode', expand=True)
            # col.prop(ob_nwo, 'light_type_h4')
            if data.type == 'SPOT':

                col.separator()
                row = col.row()
                row.prop(ob_nwo, 'light_cone_projection_shape', expand=True)
                # col.prop(ob_nwo, 'light_inner_cone_angle')
                # col.prop(ob_nwo, 'light_outer_cone_angle')

            col.separator()
            # col.prop(ob_nwo, 'Light_IntensityH4')
            if ob_nwo.light_lighting_mode == '_connected_geometry_lighting_mode_artistic':
                col.prop(ob_nwo, 'light_near_attenuation_starth4')
                col.prop(ob_nwo, 'light_near_attenuation_endh4')
            
            col.separator()
                
            if ob_nwo.light_mode == '_connected_geometry_light_mode_dynamic':
                col.prop(ob_nwo, 'light_far_attenuation_starth4')
                col.prop(ob_nwo, 'light_far_attenuation_endh4')

                col.separator()

                row = col.row()
                row.prop(ob_nwo, 'light_cinema', expand=True)
                col.prop(ob_nwo, 'light_destroy_after')

                col.separator()
                
                col.prop(ob_nwo, "light_shadows")
                if ob_nwo.light_shadows:
                    col.prop(ob_nwo, 'light_shadow_color')
                    row = col.row()
                    row.prop(ob_nwo, 'light_dynamic_shadow_quality', expand=True)
                    col.prop(ob_nwo, 'light_shadow_near_clipplane')
                    col.prop(ob_nwo, 'light_shadow_far_clipplane')
                    col.prop(ob_nwo, 'light_shadow_bias_offset')
                col.prop(ob_nwo, 'light_cinema_objects_only')
                col.prop(ob_nwo, "light_specular_contribution")
                col.prop(ob_nwo, "light_diffuse_contribution")
                col.prop(ob_nwo, "light_ignore_dynamic_objects")
                col.prop(ob_nwo, "light_screenspace")
                if ob_nwo.light_screenspace:
                    col.prop(ob_nwo, 'light_specular_power')
                    col.prop(ob_nwo, 'light_specular_intensity')

                # col = layout.column(heading="Flags")
                # sub = col.column(align=True)
            else:
                row = col.row()
                row.prop(ob_nwo, 'light_jitter_quality', expand=True)
                col.prop(ob_nwo, 'light_jitter_angle')
                col.prop(ob_nwo, 'light_jitter_sphere_radius')

                col.separator()

                col.prop(ob_nwo, 'light_amplification_factor')

                col.separator()
                # col.prop(ob_nwo, 'light_attenuation_near_radius')
                # col.prop(ob_nwo, 'light_attenuation_far_radius')
                # col.prop(ob_nwo, 'light_attenuation_power')
                # col.prop(ob_nwo, 'light_tag_name')
                col.prop(ob_nwo, "light_indirect_only")
                col.prop(ob_nwo, "light_static_analytic")

            # col.prop(ob_nwo, 'light_intensity_off', text='Light Intensity Set Via Tag')
            # if ob_nwo.light_lighting_mode == '_connected_geometry_lighting_mode_artistic':
            #     col.prop(ob_nwo, 'near_attenuation_end_off', text='Near Attenuation Set Via Tag')
            # if ob_nwo.light_type_h4 == '_connected_geometry_light_type_spot':
            #     col.prop(ob_nwo, 'outer_cone_angle_off', text='Outer Cone Angle Set Via Tag')

                # col.prop(ob_nwo, 'Light_Fade_Start_Distance')
                # col.prop(ob_nwo, 'Light_Fade_End_Distance')
            

        else:
            col.prop(ob_nwo, "light_type_override", text='Type')

            col.prop(ob_nwo, 'light_game_type', text='Game Type')
            col.prop(ob_nwo, 'light_shape', text='Shape')
            # col.prop(ob_nwo, 'Light_Color', text='Color') 
            col.prop(ob_nwo, 'light_intensity', text='Intensity')

            col.separator()

            col.prop(ob_nwo, 'light_fade_start_distance', text='Fade Out Start Distance')
            col.prop(ob_nwo, 'light_fade_end_distance', text='Fade Out End Distance')

            col.separator()

            col.prop(ob_nwo, 'light_hotspot_size', text='Hotspot Size')
            col.prop(ob_nwo, 'light_hotspot_falloff', text='Hotspot Falloff')
            col.prop(ob_nwo, 'light_falloff_shape', text='Falloff Shape')
            col.prop(ob_nwo, 'light_aspect', text='Light Aspect')

            col.separator()

            col.prop(ob_nwo, 'light_frustum_width', text='Frustum Width')
            col.prop(ob_nwo, 'light_frustum_height', text='Frustum Height')

            col.separator()

            col.prop(ob_nwo, 'light_volume_distance', text='Light Volume Distance')
            col.prop(ob_nwo, 'light_volume_intensity', text='Light Volume Intensity')

            col.separator()

            col.prop(ob_nwo, 'light_bounce_ratio', text='Light Bounce Ratio')

            col.separator()

            col = layout.column(heading="Flags")
            sub = col.column(align=True)

            sub.prop(ob_nwo, 'light_ignore_bsp_visibility', text='Ignore BSP Visibility') 
            sub.prop(ob_nwo, 'light_dynamic_has_bounce', text='Light Has Dynamic Bounce')
            if ob_nwo.light_sub_type == '_connected_geometry_lighting_sub_type_screenspace':
                sub.prop(ob_nwo, 'light_screenspace_has_specular', text='Screenspace Light Has Specular')

            col = flow.column()

            col.prop(ob_nwo, 'light_near_attenuation_start', text='Near Attenuation Start')
            col.prop(ob_nwo, 'light_near_attenuation_end', text='Near Attenuation End')

            col.separator()

            col.prop(ob_nwo, 'light_far_attenuation_start', text='Far Attenuation Start')
            col.prop(ob_nwo, 'light_far_attenuation_end', text='Far Attenuation End')

            col.separator()
            row = col.row()
            row.prop(ob_nwo, 'light_tag_override', text='Light Tag Override')
            row.operator('nwo.light_tag_path')
            row = col.row()
            row.prop(ob_nwo, 'light_shader_reference', text='Shader Tag Reference')
            row.operator('nwo.light_shader_path')
            row = col.row()
            row.prop(ob_nwo, 'light_gel_reference', text='Gel Tag Reference')
            row.operator('nwo.light_gel_path')
            row = col.row()
            row.prop(ob_nwo, 'light_lens_flare_reference', text='Lens Flare Tag Reference')
            row.operator('nwo.lens_flare_path')

            # col.separator() # commenting out light clipping for now.

            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')

class NWO_LightPropsCycles(NWO_LightProps):
    bl_idname = "NWO_PT_LightPanel_Cycles"
    bl_parent_id = "CYCLES_LIGHT_PT_light"

# BONE PROPERTIES
class NWO_BoneProps(Panel):
    bl_label = "Halo Bone Properties"
    bl_idname = "NWO_PT_BoneDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global
        return scene_nwo.game_version in ('reach','h4','h2a') and context.bone
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        
        bone = context.bone
        bone_nwo = bone.nwo
        scene = context.scene
        scene_nwo = scene.nwo

        # layout.enabled = scene_nwo.expert_mode
        
        col = flow.column()
        col.prop(bone_nwo, "name_override")

        col.separator()

        col.prop(bone_nwo, "frame_id1", text='Frame ID 1')
        col.prop(bone_nwo, "frame_id2", text='Frame ID 2')

        col.separator()

        col.prop(bone_nwo, "object_space_node", text='Object Space Offset Node')
        col.prop(bone_nwo, "replacement_correction_node", text='Replacement Correction Node')
        col.prop(bone_nwo, "fik_anchor_node", text='Forward IK Anchor Node')

# ACTION PROPERTIES
class NWO_ActionProps(Panel):
    bl_label = "Halo Animation Properties"
    bl_idname = "NWO_PT_ActionDetailsPanel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = "UI"
    bl_context = "Action"
    bl_parent_id = "DOPESHEET_PT_action"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global
        return scene_nwo.game_version in ('reach','h4','h2a')
    
    def draw_header(self, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        self.layout.prop(action_nwo, "export_this", text='')
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        
        action = context.object.animation_data.action
        action_nwo = action.nwo

        if not action_nwo.export_this:
            layout.label(text="Animation is excluded from export")
            layout.active = False
        
        else:
            col = flow.column()
            col.prop(action_nwo, 'name_override')
            col.prop(action_nwo, 'animation_type')

mesh_type_items = [
    ('_connected_geometry_mesh_type_boundary_surface', "Boundary Surface", "Used in structure_design tags for soft_kill, soft_ceiling, and slip_sufaces. Only use when importing to a structure_design tag. Can be forced on with the prefixes: '+soft_ceiling', 'soft_kill', 'slip_surface'"), # 0
    ('_connected_geometry_mesh_type_collision', "Collision", "Sets this mesh to have collision geometry only. Can be forced on with the prefix: '@'"), #1
    ('_connected_geometry_mesh_type_cookie_cutter', "Cookie Cutter", "Defines an area which ai will pathfind around. Can be forced on with the prefix: '+cookie'"), # 2
    ('_connected_geometry_mesh_type_decorator', "Decorator", "Use this when making a decorator. Allows for different LOD levels to be set"), # 3
    ('_connected_geometry_mesh_type_default', "Default", "By default this mesh type will be treated as render only geometry in models, and render + bsp collision geometry in structures"), #4
    ('_connected_geometry_mesh_type_poop', "Instanced Geometry", "Writes this mesh to a json file as instanced geometry. Can be forced on with the prefix: '%'"), # 5
    ('_connected_geometry_mesh_type_poop_marker', "Instanced Marker", ""), # 6
    ('_connected_geometry_mesh_type_poop_rain_blocker', "Rain Occluder",'Rain is not rendered in the the volume this mesh occupies.'), # 7
    ('_connected_geometry_mesh_type_poop_vertical_rain_sheet', "Vertical Rain Sheet", ''), # 8
    ('_connected_geometry_mesh_type_lightmap_region', "Lightmap Region", "Defines an area of a structure which should be lightmapped. Can be referenced when lightmapping"), # 9
    ('_connected_geometry_mesh_type_object_instance', "Object Instance", "Writes this mesh to the json as an instanced object. Can be forced on with the prefix: '+flair'"), # 10
    ('_connected_geometry_mesh_type_physics', "Physics", "Sets this mesh to have physics geometry only. Can be forced on with the prefix: '$'"), # 11
    ('_connected_geometry_mesh_type_planar_fog_volume', "Planar Fog Volume", "Defines an area for a fog volume. The same logic as used for portals should be applied to these.  Can be forced on with the prefix: '+fog'"), # 12
    ('_connected_geometry_mesh_type_portal', "Portal", "Cuts up a bsp and defines clusters. Can be forced on with the prefix '+portal'"), # 13
    ('_connected_geometry_mesh_type_seam', "Seam", "Defines where two bsps meet. Its name should match the name of the bsp its in. Can be forced on with the prefix '+seam'"), # 14
    ('_connected_geometry_mesh_type_water_physics_volume', "Water Physics Volume", "Defines an area where water physics should apply. Only use when importing to a structure_design tag. Can be forced on with the prefix: '+water'"), # 15
    ('_connected_geometry_mesh_type_water_surface', "Water Surface", "Defines a mesh as a water surface. Can be forced on with the prefix: '"), # 16
    ('_connected_geometry_mesh_type_obb_volume', 'OBB Volume', ''), # 17
    ('_connected_geometry_mesh_type_volume', 'Volume', ''),
    # These go unused in menus, and are instead set at export
    ('_connected_geometry_mesh_type_poop_collision', 'Poop Collision', ''),
    ('_connected_geometry_mesh_type_poop_physics', 'Poop Physics', ''),
    ('_connected_geometry_mesh_type_render', 'Render', ''),
    ('_connected_geometry_mesh_type_structure', 'Structure', ''),
    ('_connected_geometry_mesh_type_default', 'Default', ''),

]

volume_type_items = [
    ('_connected_geometry_volume_type_soft_ceiling', 'Soft Celing', ''),
    ('_connected_geometry_volume_type_soft_kill', 'Soft Kill', ''),
    ('_connected_geometry_volume_type_slip_surface', 'Slip Surface', ''),
    ('_connected_geometry_volume_type_water_physics', 'Water Physics', ''),
    ('_connected_geometry_volume_type_lightmap_exclude', 'Lightmap Exclusion', ''),
    ('_connected_geometry_volume_type_lightmap_region', 'Lightmap Region', ''),
    ('_connected_geometry_volume_type_streaming', 'Streaming', ''),
]

marker_type_items = [ 
            ('_connected_geometry_marker_type_model', "Model", "Default marker type. Defines render_model markers for models, and structure markers for bsps"),
            ('_connected_geometry_marker_type_effects', "Effects", "Marker for effects only."),
            ('_connected_geometry_marker_type_game_instance', "Game Object", "Game Instance marker. Used to create an instance of a tag in the bsp. Can be set with the prefix: ?"),
            ('_connected_geometry_marker_type_garbage', "Garbage", "marker to define position that garbage pieces should be created"),
            ('_connected_geometry_marker_type_hint', "Hint", "Used for ai hints"),
            ('_connected_geometry_marker_type_pathfinding_sphere', "Pathfinding Sphere", "Used to create ai pathfinding spheres"),
            ('_connected_geometry_marker_type_physics_constraint', "Physics Constraint", "Used to define various types of physics constraints"),
            ('_connected_geometry_marker_type_physics_hinge_constraint', "Hinge Constraint", "Used to define various types of physics constraints"),
            ('_connected_geometry_marker_type_physics_socket_constraint', "Socket Constraint", "Used to define various types of physics constraints"),
            ('_connected_geometry_marker_type_target', "Target", "Defines the markers used in a model's targets'"),
            ('_connected_geometry_marker_type_water_volume_flow', "Water Volume Flow", "Used to define water flow for water physics volumes. For structure_design tags only"),
            ('_connected_geometry_marker_type_airprobe', "Airprobe", "Airprobes tell the game how to handle static lighting on dynamic objects"),
            ('_connected_geometry_marker_type_envfx', "Environment Effect", "Plays an effect on this point in the structure"),
            ('_connected_geometry_marker_type_lightCone', "Light Cone", "Creates a light cone with the defined parameters"),
            ('_connected_geometry_marker_type_prefab', "Prefab", ""),
            ('_connected_geometry_marker_type_cheap_light', "Cheap Light", ""),
            ('_connected_geometry_marker_type_light', "Light", ""),
            ('_connected_geometry_marker_type_falling_leaf', "Falling Leaf", ""),
            ]

#==============================##############------=======================

# NWO PROPERTY GROUPS
class NWO_ObjectPropertiesGroup(PropertyGroup):
    #OBJECT PROPERTIES
    
    #########################################################################################################################
    # OBJECT TYPE UI ####################################################################################################
    #########################################################################################################################

    def items_object_type_ui(self, context):
        """Function to handle context for object enum lists"""
        ob = context.object
        items = []

        # context: any light object
        if ob.type == 'LIGHT':
            items.append(('_connected_geometry_object_type_light', 'Light', 'Light', get_icon_id("light_cone"), 0))
        
        # context: any 3D object type i.e. a blender mesh or an object that can convert to mesh
        elif mesh_object(ob):
            items.append(('_connected_geometry_object_type_mesh', 'Mesh', "Mesh", get_icon_id("render_geometry"), 0))
            items.append(('_connected_geometry_object_type_marker', 'Marker', "Marker", get_icon_id("marker"), 1))
            items.append(('_connected_geometry_object_type_frame', 'Frame', "Frame", get_icon_id("frame"), 2))
        
        # context: any empty object
        else:
            items.append(('_connected_geometry_object_type_marker', 'Marker', "Marker", get_icon_id("marker"), 0))
            items.append(('_connected_geometry_object_type_frame', 'Frame', "Frame", get_icon_id("frame"), 1))
        
        return items
        
        
    def get_object_type_ui(self):
        max_int = 2
        ob = bpy.context.object
        if ob.type == 'EMPTY':
            max_int = 1
        if self.object_type_ui_help > max_int:
            return 0
        return self.object_type_ui_help

    def set_object_type_ui(self, value):
        self["object_type_ui"] = value

    def update_object_type_ui(self, context):
        self.object_type_ui_help = self["object_type_ui"]

    object_type_ui : EnumProperty(
        name = 'Object Type',
        items=items_object_type_ui,
        update=update_object_type_ui,
        get=get_object_type_ui,
        set=set_object_type_ui,
    )

    object_type_ui_help : IntProperty()

    #########################################################################################################################
    # MESH TYPE UI ####################################################################################################
    #########################################################################################################################

    def items_mesh_type_ui(self, context):
        """Function to handle context for mesh enum lists"""
        h4 = not_bungie_game()
        items = []

        if poll_ui('DECORATOR SET'):
            items.append(('_connected_geometry_mesh_type_decorator', 'Decorator', 'Decorator mesh type. Supports up to 4 level of detail variants', get_icon_id("decorator"), 0))
        elif poll_ui(('MODEL', 'SKY', 'PARTICLE MODEL')):
            items.append(('_connected_geometry_mesh_type_render', 'Render', 'Render only geometry', get_icon_id("render_geometry"), 0))
            if poll_ui('MODEL'):
                items.append(('_connected_geometry_mesh_type_collision', 'Collision', 'Collision only geometry. Acts as bullet collision and for scenery also provides player collision', get_icon_id("collider"), 1))
                items.append(('_connected_geometry_mesh_type_physics', 'Physics', 'Physics only geometry. Uses havok physics to interact with static and dynamic meshes', get_icon_id("physics"), 2))
                if not h4:
                    items.append(('_connected_geometry_mesh_type_object_instance', 'Flair', 'Instanced mesh for models. Can be instanced across mutliple permutations', get_icon_id("flair"), 3))
        elif poll_ui('SCENARIO'):
            items.append(('_connected_geometry_mesh_type_structure', 'Structure', 'Structure bsp geometry. By default provides render and bullet/player collision', get_icon_id("structure"), 0))
            items.append(('_connected_geometry_mesh_type_poop', 'Instance', 'Instanced geometry. Geometry capable of cutting through structure mesh', get_icon_id("instance"), 1))
            items.append(('_connected_geometry_mesh_type_poop_collision', 'Collision', 'Non rendered geometry which provides collision only', get_icon_id("collider"), 2))
            items.append(('_connected_geometry_mesh_type_plane', 'Plane', 'Non rendered geometry which provides various utility functions in a bsp. The planes can cut through bsp geometry. Supports portals, fog planes, and water surfaces', get_icon_id("surface"), 3))
            items.append(('_connected_geometry_mesh_type_volume', 'Volume', 'Non rendered geometry which defines regions for special properties', get_icon_id("volume"), 4))
        elif poll_ui('PREFAB'):
            items.append(('_connected_geometry_mesh_type_poop', 'Instance', 'Instanced geometry. Geometry capable of cutting through structure mesh', get_icon_id("instance"), 0))
            items.append(('_connected_geometry_mesh_type_poop_collision', 'Collision', 'Non rendered geometry which provides collision only', get_icon_id("collider"), 1))
            items.append(('_connected_geometry_mesh_type_cookie_cutter', 'Cookie Cutter', 'Non rendered geometry which cuts out the region it defines from the pathfinding grid', get_icon_id("cookie_cutter"), 2))
        
        return items
        
    def get_mesh_type_ui(self):
        max_int = 0
        if poll_ui('MODEL'):
            max_int = 2
            if not not_bungie_game():
                max_int = 3
        elif poll_ui('SCENARIO'):
            max_int = 4
        elif poll_ui('PREFAB'):
            max_int = 2
        if self.mesh_type_ui_help > max_int:
            return 0
        return self.mesh_type_ui_help

    def set_mesh_type_ui(self, value):
        self["mesh_type_ui"] = value

    def update_mesh_type_ui(self, context):
        self.mesh_type_ui_help = self["mesh_type_ui"]
        
    mesh_type_ui : EnumProperty(
        name = 'Mesh Type',
        items=items_mesh_type_ui,
        update=update_mesh_type_ui,
        get=get_mesh_type_ui,
        set=set_mesh_type_ui,
    )

    mesh_type_ui_help : IntProperty()

    #########################################################################################################################
    # PLANE TYPE UI ####################################################################################################
    #########################################################################################################################

    def items_plane_type_ui(self, context):
        """Function to handle context for plane enum lists"""
        h4 = not_bungie_game()
        items = []

        items.append(('_connected_geometry_plane_type_portal', 'Portal', 'Planes that cut through structure geometry to define clusters. Used for defining visiblity between different clusters', get_icon_id("portal"), 0))
        items.append(('_connected_geometry_plane_type_planar_fog_volume', 'Fog Plane', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("fog"), 1))
        items.append(('_connected_geometry_plane_type_water_surface', 'Water Surface', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("water"), 2))
        if not h4:
            items.append(('_connected_geometry_plane_type_poop_vertical_rain_sheet', 'Rain Sheet', 'A plane which blocks all rain particles that hit it. Regions under this plane will not render rain', get_icon_id("rain_sheet"), 3))
        
        return items
        
    def get_plane_type_ui(self):
        max_int = 2
        if not not_bungie_game():
            max_int = 3
        if self.plane_type_ui_help > max_int:
            return 0
        return self.plane_type_ui_help

    def set_plane_type_ui(self, value):
        self["plane_type_ui"] = value

    def update_plane_type_ui(self, context):
        self.plane_type_ui_help = self["plane_type_ui"]

    plane_type_ui : EnumProperty(
        name = 'Plane Type',
        items=items_plane_type_ui,
        update=update_plane_type_ui,
        get=get_plane_type_ui,
        set=set_plane_type_ui,
    )

    plane_type_ui_help : IntProperty()

    #########################################################################################################################
    # VOLUME TYPE UI ####################################################################################################
    #########################################################################################################################

    def items_volume_type_ui(self, context):
        """Function to handle context for plane enum lists"""
        h4 = not_bungie_game()
        items = []

        items.append(('_connected_geometry_volume_type_soft_ceiling', 'Soft Ceiling', 'Soft barrier that blocks the player and player camera', get_icon_id("soft_ceiling"), 0))
        items.append(('_connected_geometry_volume_type_soft_kill', 'Soft Kill', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("soft_kill"), 1))
        items.append(('_connected_geometry_volume_type_slip_surface', 'Slip Surface', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("slip_surface"), 2))
        items.append(('_connected_geometry_volume_type_cookie_cutter', 'Cookie Cutter', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("cookie_cutter"), 3))
        items.append(('_connected_geometry_volume_type_poop_rain_blocker', 'Rain Blocker', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("rain_sheet"), 4))
        if h4:
            items.append(('_connected_geometry_volume_type_lightmap_exclude', 'Lightmap Exclude', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("lightmap_exclude"), 5))
            items.append(('_connected_geometry_volume_type_streaming', 'Streaming Volume', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("streaming"), 6))
        else:
            items.append(('_connected_geometry_volume_type_lightmap_region', 'Lightmap Region', 'A plane which blocks all rain particles that hit it. Regions under this plane will not render rain', get_icon_id("lightmap_region"), 5))
        
        return items
        
    def get_volume_type_ui(self):
        max_int = 5
        if not_bungie_game():
            max_int = 6
        if self.volume_type_ui_help > max_int:
            return 0
        return self.volume_type_ui_help

    def set_volume_type_ui(self, value):
        self["volume_type_ui"] = value

    def update_volume_type_ui(self, context):
        self.volume_type_ui_help = self["volume_type_ui"]

    volume_type_ui : EnumProperty(
        name = 'Volume Type',
        options=set(),
        update=update_volume_type_ui,
        items=items_volume_type_ui,
        get=get_volume_type_ui,
        set=set_volume_type_ui,
    )

    volume_type_ui_help : IntProperty()

    def items_marker_type_ui(self, context):
        """Function to handle context for marker enum lists"""
        h4 = not_bungie_game()
        items = []

        if poll_ui(('MODEL','SKY')):
            items.append(('_connected_geometry_marker_type_model', 'Model Marker', 'Soft barrier that blocks the player and player camera', get_icon_id("marker"), 0))
            if poll_ui('MODEL'):
                items.append(('_connected_geometry_marker_type_effects', 'Effects', 'Soft barrier that blocks the player and player camera', get_icon_id("effects"), 1))
                items.append(('_connected_geometry_marker_type_garbage', 'Garbage', 'Soft barrier that blocks the player and player camera', get_icon_id("garbage"), 2))
                items.append(('_connected_geometry_marker_type_hint', 'Hint', 'Soft barrier that blocks the player and player camera', get_icon_id("hint"), 3))
                items.append(('_connected_geometry_marker_type_pathfinding_sphere', 'Pathfinding Sphere', 'Soft barrier that blocks the player and player camera', get_icon_id("pathfinding_sphere"), 4))
                items.append(('_connected_geometry_marker_type_physics_constraint', 'Physics Constraint', 'Soft barrier that blocks the player and player camera', get_icon_id("physics_constraint"), 5))
                items.append(('_connected_geometry_marker_type_target', 'Target', 'Soft barrier that blocks the player and player camera', get_icon_id("target"), 6))
        elif poll_ui('SCENARIO'):
            items.append(('_connected_geometry_marker_type_model', 'Structure Marker', 'Soft barrier that blocks the player and player camera', get_icon_id("marker"), 0))
            if self.marker_game_instance_tag_name.endswith('.prefab'):
                items.append(('_connected_geometry_marker_type_game_instance', 'Prefab', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("prefab"), 1))
            elif self.marker_game_instance_tag_name.endswith('.light'):
                items.append(('_connected_geometry_marker_type_game_instance', 'Light', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("light_cone"), 1))
            elif self.marker_game_instance_tag_name.endswith('.cheap_light'):
                items.append(('_connected_geometry_marker_type_game_instance', 'Cheap Light', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("light_cone"), 1))
            elif self.marker_game_instance_tag_name.endswith('.leaf'):
                items.append(('_connected_geometry_marker_type_game_instance', 'Falling Leaf', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("soft_kill"), 1))
            else:
                items.append(('_connected_geometry_marker_type_game_instance', 'Game Tag', 'Defines an area in a cluster which renders fog defined in the scenario tag', get_icon_id("game_object"), 1))

            if h4:
                items.append(('_connected_geometry_marker_type_airprobe', 'Airprobe', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("airprobe"), 2))
                items.append(('_connected_geometry_marker_type_envfx', 'Environment Effect', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("environment_effect"), 3))
                items.append(('_connected_geometry_marker_type_lightCone', 'Light Cone', 'Plane which can cut through structure geometry to define a water surface. Supports tesselation', get_icon_id("light_cone"), 4))
        
        return items
        
    def get_marker_type_ui(self):
        max_int = 0
        if poll_ui('MODEL'):
            max_int = 6
        elif poll_ui('SCENARIO'):
            max_int = 4
            if not not_bungie_game():
                max_int = 1
        if self.marker_type_ui_help > max_int:
            return 0
        return self.marker_type_ui_help

    def set_marker_type_ui(self, value):
        self["marker_type_ui"] = value

    def update_marker_type_ui(self, context):
        self.marker_type_ui_help = self["marker_type_ui"]

    marker_type_ui : EnumProperty(
        name = 'Marker Type',
        options=set(),
        items=items_marker_type_ui,
        update=update_marker_type_ui,
        get=get_marker_type_ui,
        set=set_marker_type_ui,
    )

    marker_type_ui_help : IntProperty()

    export_this : BoolProperty(
        name = 'Export',
        default=True,
        description="Controls whether this object is exported or not",
        options=set(),
    )

    def get_objecttype_enum(self):
        if self.id_data.name.startswith(frame_prefixes):
            return 0
        elif self.id_data.name.startswith(marker_prefixes) or (self.id_data.type == 'EMPTY' and self.id_data.name.startswith('$')):
            return 1
        else:
            return 2

    def get_objecttype_enum_no_mesh(self):
        if self.id_data.name.startswith(frame_prefixes) or (not self.id_data.name.startswith(marker_prefixes) and len(self.id_data.children) > 0):
            return 0
        else:
            return 1

    def object_type_items_all(self, context):
        object_type_items_all = [
            ('_connected_geometry_object_type_mesh', 'Mesh', "Mesh", get_icon_id("render_geometry"), 0),
            ('_connected_geometry_object_type_marker', 'Marker', "Marker", get_icon_id("marker"), 1),
            ('_connected_geometry_object_type_frame', 'Frame', "Frame", get_icon_id("frame"), 2),
        ]
        return object_type_items_all

    def object_type_items_no_mesh(self, context):
        object_type_items_no_mesh = [
            ('_connected_geometry_object_type_marker', "Marker", "Marker", get_icon_id("marker"), 0),
            ('_connected_geometry_object_type_frame', "Frame", "Frame", get_icon_id("frame"), 1),
        ]
        return object_type_items_no_mesh

    object_type_items = [
        ('_connected_geometry_object_type_mesh', 'Mesh', "Mesh"),
        ('_connected_geometry_object_type_marker', 'Marker', "Marker"),
        ('_connected_geometry_object_type_frame', 'Frame', "Frame"),
        ('_connected_geometry_object_type_light', 'Light', ''),
        ('_connected_geometry_object_type_animation_control', 'Control', ''),
        ('_connected_geometry_object_type_animation_camera', 'Camera', ''),
        ('_connected_geometry_object_type_animation_event', 'Event', ''),
        ('_connected_geometry_object_type_frame_pca', 'PCA', ''),
    ]

    object_type_all: EnumProperty(
        name="Object Type",
        options=set(),
        items=object_type_items_all,
    )

    object_type_no_mesh: EnumProperty(
        name="Object Type",
        options=set(),
        items=object_type_items_no_mesh,
    )

    def object_type_light(self, context):
        object_type_item_light = [('_connected_geometry_object_type_light', 'Light', '', get_icon_id("light_cone"), 0)]
        return object_type_item_light

    object_type_light: EnumProperty(
        name="Light",
        options=set(),
        items=object_type_light,
    )

    compress_verts: BoolProperty(
        name="Compress Vertices",
        options=set(),
        default = False,
    )

    uvmirror_across_entire_model: BoolProperty(
        name="UV Mirror Across Model",
        options=set(),
        default = False,
    )

    bsp_name: StringProperty(
        name="BSP Name",
        default='000',
        description="Set bsp name for this object. Only valid for scenario exports",
    )

    def get_bsp_from_collection(self):
        bsp = get_prop_from_collection(self.id_data, ('+bsp:', '+design:'))
        return bsp

    bsp_name_locked: StringProperty(
        name="BSP Name",
        default='',
        description="Set bsp name for this object. Only valid for scenario exports",
        get=get_bsp_from_collection,
    )
    
    # EXPORT PROPS
    object_type : EnumProperty(
        items=object_type_items,
    )

    mesh_type : EnumProperty(
        default='_connected_geometry_mesh_type_default',
        items=mesh_type_items
    )

    volume_type : EnumProperty(
        default='_connected_geometry_volume_type_soft_ceiling',
        items=volume_type_items
    )

    marker_type : EnumProperty(
        items=marker_type_items
    )
    ################

    mesh_primitive_type : EnumProperty(
        name="Mesh Primitive Type",
        options=set(),
        description="Select the primtive type of this mesh",
        default = "_connected_geometry_primitive_type_none",
        items=[ ('_connected_geometry_primitive_type_none', "None", "None"),
                ('_connected_geometry_primitive_type_box', "Box", "Box"),
                ('_connected_geometry_primitive_type_pill', "Pill", "Pill"),
                ('_connected_geometry_primitive_type_sphere', "Sphere", "Sphere"),
                ('_connected_geometry_primitive_type_mopp', "MOPP", ""),
               ]
        )

    mesh_tessellation_density : EnumProperty(
        name="Mesh Tessellation Density",
        options=set(),
        description="Select the tesselation density you want applied to this mesh",
        default = "_connected_geometry_mesh_tessellation_density_none",
        items=[ ('_connected_geometry_mesh_tessellation_density_none', "None", ""),
                ('_connected_geometry_mesh_tessellation_density_4x', "4x", "4 times"),
                ('_connected_geometry_mesh_tessellation_density_9x', "9x", "9 times"),
                ('_connected_geometry_mesh_tessellation_density_36x', "36x", "36 times"),
               ]
        )
    mesh_compression : EnumProperty(
        name="Mesh Compression",
        options=set(),
        description="Select if you want additional compression forced on/off to this mesh",
        default = "_connected_geometry_mesh_additional_compression_default",
        items=[ ('_connected_geometry_mesh_additional_compression_default', "Default", "Default"),
                ('_connected_geometry_mesh_additional_compression_force_off', "Force Off", "Force Off"),
                ('_connected_geometry_mesh_additional_compression_force_on', "Force On", "Force On"),
               ]
        )

    #FACE PROPERTIES
    face_type : EnumProperty(
        name="Face Type",
        options=set(),
        description="Sets the face type for this mesh. Note that any override shaders will override the face type selected here for relevant materials",
        default = '_connected_geometry_face_type_normal',
        items=[ ('_connected_geometry_face_type_normal', "Normal", "This face type has no special properties"),
                ('_connected_geometry_face_type_seam_sealer', "Seam Sealer", "Set mesh faces to have the special seam sealer property. Collsion only geometry"),
                ('_connected_geometry_face_type_sky', "Sky", "Set mesh faces to render the sky"),
               ]
        )

    face_mode : EnumProperty(
        name="Face Mode",
        options=set(),
        description="Sets face mode for this mesh",
        default = '_connected_geometry_face_mode_normal',
        items=[ ('_connected_geometry_face_mode_normal', "Normal", "This face mode has no special properties"),
                ('_connected_geometry_face_mode_render_only', "Render Only", "Faces set to render only"),
                ('_connected_geometry_face_mode_collision_only', "Collision Only", "Faces set to collision only"),
                ('_connected_geometry_face_mode_sphere_collision_only', "Sphere Collision Only", "Faces set to sphere collision only. Only objects with physics models can collide with these faces"),
                ('_connected_geometry_face_mode_shadow_only', "Shadow Only", "Faces set to only cast shadows"),
                ('_connected_geometry_face_mode_lightmap_only', "Lightmap Only", "Faces set to only be used during lightmapping. They will otherwise have no render / collision geometry"),
                ('_connected_geometry_face_mode_breakable', "Breakable", "Faces set to be breakable"),
               ]
        )

    face_sides : EnumProperty(
        name="Face Sides",
        options=set(),
        description="Sets the face sides for this mesh",
        default = '_connected_geometry_face_sides_one_sided',
        items=[ ('_connected_geometry_face_sides_one_sided', "One Sided", "Faces set to only render on one side (the direction of face normals)"),
                ('_connected_geometry_face_sides_one_sided_transparent', "One Sided Transparent", "Faces set to only render on one side (the direction of face normals), but also render geometry behind them"),
                ('_connected_geometry_face_sides_two_sided', "Two Sided", "Faces set to render on both sides"),
                ('_connected_geometry_face_sides_two_sided_transparent', "Two Sided Transparent", "Faces set to render on both sides and are transparent"),
                ('_connected_geometry_face_sides_mirror', "Mirror", "H4+ only"),
                ('_connected_geometry_face_sides_mirror_transparent', "Mirror Transparent", "H4+ only"),
                ('_connected_geometry_face_sides_keep', "Keep", "H4+ only"),
                ('_connected_geometry_face_sides_keep_transparent', "Keep Transparent", "H4+ only"),
               ]
        )

    face_draw_distance : EnumProperty(
        name="Face Draw Distance",
        options=set(),
        description="Select the draw distance for faces on this mesh",
        default = "_connected_geometry_face_draw_distance_normal",
        items=[ ('_connected_geometry_face_draw_distance_normal', "Normal", ""),
                ('_connected_geometry_face_draw_distance_detail_mid', "Mid", ""),
                ('_connected_geometry_face_draw_distance_detail_close', "Close", ""),
               ]
        ) 

    texcoord_usage : EnumProperty(
        name="Texture Coordinate Usage",
        options=set(),
        description="",
        default = '_connected_material_texcoord_usage_default',
        items=[ ('_connected_material_texcoord_usage_default', "Default", ""),
                ('_connected_material_texcoord_usage_none', "None", ""),
                ('_connected_material_texcoord_usage_anisotropic', "Ansiotropic", ""),
               ]
        )

    region_name: StringProperty(
        name="Face Region",
        default='',
        description="Define the name of the region these faces should be associated with",
    )

    def get_region_from_collection(self):
        region = get_prop_from_collection(self.id_data, ('+region:', '+reg:'))
        return region

    region_name_locked: StringProperty(
        name="Face Region",
        description="Define the region for this mesh",
        get=get_region_from_collection,
    )

    permutation_name: StringProperty(
        name="Permutation",
        default='',
        description="Define the permutation of this object. Permutations get exported to seperate files in scenario exports, or in model exports if the mesh type is one of render/collision/physics",
    )

    def get_permutation_from_collection(self):
        permutation = get_prop_from_collection(self.id_data, ('+perm:', '+permuation:'))
        return permutation

    permutation_name_locked: StringProperty(
        name="Permutation",
        description="Define the permutation of this object. Leave blank for default",
        get=get_permutation_from_collection,
    )

    is_pca: BoolProperty(
        name="Frame PCA",
        options=set(),
        description="",
        default=False,
    )

    face_global_material: StringProperty(
        name="Global Material",
        default='',
        description="Set the global material of this mesh. If the global material name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct global material response type, otherwise, the global material override can be manually defined in the .model tag",
    )

    sky_permutation_index: IntProperty(
        name="Sky Permutation Index",
        options=set(),
        description="Set the sky permutation index of this mesh. Only valid if the face type is sky",
        min=0,
    )

    conveyor: BoolProperty(
        name ="Conveyor",
        options=set(),
        description = "Enables the conveyor property",
        default = False,
        )

    ladder: BoolProperty(
        name ="Ladder",
        options=set(),
        description = "Makes faces climbable",
        default = False,
    )

    slip_surface: BoolProperty(
        name ="Slip Surface",
        options=set(),
        description = "Makes faces slippery for units",
        default = False,
    )

    decal_offset: BoolProperty(
        name ="Decal Offset",
        options=set(),
        description = "Enable to offset these faces so that they appear to be layered on top of another face",
        default = False,
    )

    group_transparents_by_plane: BoolProperty(
        name ="Group Transparents By Plane",
        options=set(),
        description = "Enable to group transparent geometry by fitted planes",
        default = False,
    )

    no_shadow: BoolProperty(
        name ="No Shadow",
        options=set(),
        description = "Enable to prevent faces from casting shadows",
        default = False,
    )

    precise_position: BoolProperty(
        name ="Precise Position",
        options=set(),
        description = "Enable to prevent faces from being altered during the import process",
        default = False,
    )

    no_lightmap: BoolProperty(
        name ="Exclude From Lightmap",
        options=set(),
        description = "",
        default = False,
    )

    no_pvs: BoolProperty(
        name ="Invisible To PVS",
        options=set(),
        description = "",
        default = False,
    )
    
    #PRIMITIVE PROPERTIES
    # Box_Length: FloatProperty(
    #     name="Box Length",
    #     options=set(),
    #     description="Set the length of the primitive box",
    # )

    # Box_Width: FloatProperty(
    #     name="Box Width",
    #     options=set(),
    #     description="Set the width of the primitive box",
    # )

    # Box_Height: FloatProperty(
    #     name="Box Height",
    #     options=set(),
    #     description="Set the height of the primitive box",
    # )

    # Pill_Radius: FloatProperty(
    #     name="Pill Radius",
    #     options=set(),
    #     description="Set the radius of the primitive pill",
    # )

    # Pill_Height: FloatProperty(
    #     name="Pill Height",
    #     options=set(),
    #     description="Set the height of the primitive pill",
    # )

    # Sphere_Radius: FloatProperty(
    #     name="Sphere Radius",
    #     options=set(),
    #     description="Set the radius of the primitive sphere",
    # )
    
    #BOUNDARY SURFACE PROPERTIES
    def get_boundary_surface_name(self):
        name = self.id_data.name
        name = name.removeprefix('+soft_ceiling')
        name = name.removeprefix('+soft_kill')
        name = name.removeprefix('+slip_surface')
        name = name.strip(' :"')

        return shortest_string(name, name.rpartition('.')[0]).lower()

    boundary_surface_name: StringProperty(
        name="Boundary Surface Name",
        description="Define the name of the boundary surface. This will be referenced in the structure_design tag.",
        get=get_boundary_surface_name,
        maxlen=32,
    )

    boundary_surface_items = [  ('_connected_geometry_boundary_surface_type_soft_ceiling', "Soft Ceiling", "Defines this mesh as soft ceiling"),
                                ('_connected_geometry_boundary_surface_type_soft_kill', "Soft Kill", "Defines this mesh as soft kill barrier"),
                                ('_connected_geometry_boundary_surface_type_slip_surface', "Slip Surface", "Defines this mesh as a slip surface"),
                                ]

    boundary_surface_type : EnumProperty(
        name="Boundary Surface Type",
        options=set(),
        description="Set the type of boundary surface you want to create. You should only import files with this mesh type as struture_design tags",
        default = '_connected_geometry_boundary_surface_type_soft_ceiling',
        items=boundary_surface_items,
        )

    def get_boundary_surface(self):
        a_ob = bpy.context.active_object

        if a_ob.name.startswith('+soft_ceiling'):
            return 0
        elif a_ob.name.startswith('+soft_kill'):
            return 1
        elif a_ob.name.startswith('+slip_surface'):
            return 2
        else:
            return 0

    boundary_surface_type_locked : EnumProperty(
        name="Boundary Surface Type",
        options=set(),
        get=get_boundary_surface,
        description="Set the type of boundary surface you want to create. You should only import files with this mesh type as struture_design tags",
        default = '_connected_geometry_boundary_surface_type_soft_ceiling',
        items=boundary_surface_items,
        )
    

    poop_lighting_items = [ ('_connected_geometry_poop_lighting_default', "Automatic", "Sets the lighting policy automatically"),
                            ('_connected_geometry_poop_lighting_per_pixel', "Per Pixel", "Sets the lighting policy to per pixel. Can be forced on with the prefix: '%?'"),
                            ('_connected_geometry_poop_lighting_per_vertex', "Per Vertex", "Sets the lighting policy to per vertex. Can be forced on with the prefix: '%!'"),
                            ('_connected_geometry_poop_lighting_single_probe', "Single Probe", "Sets the lighting policy to single probe. Can be forced on with the prefix: '%>'"),
                            ('_connected_geometry_poop_lighting_per_vertex_ao', "Per Vertex AO", "H4+ only. Sets the lighting policy to per vertex ambient occlusion."),
                            ]


    #POOP PROPERTIES
    poop_lighting_override : EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Sets the lighting policy for this instanced geometry",
        default = '_connected_geometry_poop_lighting_per_pixel',
        items=poop_lighting_items,
        )

    def get_poop_lighting_policy(self):
        if bpy.context.active_object.name.startswith(('%!',     '%-!','%+!','%*!',     '%-*!','%+*!',     '%*-!','%*+!')):
            return 1
        elif bpy.context.active_object.name.startswith(('%?',     '%-?','%+?','%*?',     '%-*?','%+*?',     '%*-?','%*+?')):
            return 2
        elif bpy.context.active_object.name.startswith(('%>',     '%->','%+>','%*>',     '%-*>','%+*>',     '%*->','%*+>')):
            return 3
        else:
            return 0 # else won't ever be hit, but adding it stops errors

    poop_lighting_override_locked : EnumProperty(
        name="Lighting Policy",
        options=set(),
        get=get_poop_lighting_policy,
        description="Sets the lighting policy for this instanced geometry",
        default = '_connected_geometry_poop_lighting_default',
        items=poop_lighting_items,
        )

    poop_lightmap_resolution_scale : FloatProperty( # H4+ only
        name="Lightmap Resolution Scale",
        options=set(),
        description="Sets lightmap resolutions scale for this instance",
        default = 1.0,
        min = 0.0
    )

    poop_pathfinding_items = [  ('_connected_poop_instance_pathfinding_policy_cutout', "Cutout", "Sets the pathfinding policy to cutout. AI will be able to pathfind around this mesh, but not on it."),
                                ('_connected_poop_instance_pathfinding_policy_none', "None", "Sets the pathfinding policy to none. This mesh will be ignored during pathfinding generation. Can be forced on with the prefix: '%-'"),
                                ('_connected_poop_instance_pathfinding_policy_static', "Static", "Sets the pathfinding policy to static. AI will be able to pathfind around and on this mesh. Can be forced on with the prefix: '%+'"),
                                ]

    poop_pathfinding_override : EnumProperty(
        name="Instanced Geometry Pathfinding Override",
        options=set(),
        description="Sets the pathfinding policy for this instanced geometry",
        default = '_connected_poop_instance_pathfinding_policy_cutout',
        items=poop_pathfinding_items,
        )

    def get_poop_pathfinding_policy(self):
        if bpy.context.active_object.name.startswith(('%-',     '%!-','%?-','%>-','%*-',     '%!*-','%?*-','%>*-',     '%*!-','%*?-','%*>-')):
            return 1
        elif bpy.context.active_object.name.startswith(('%+',     '%!+','%?+','%>+','%*+',     '%!*+','%?*+','%>*+',     '%*!+','%*?+','%*>+')):
            return 2
        else:
            return 0 # else won't ever be hit, but adding it stops errors

    poop_pathfinding_override_locked : EnumProperty(
        name="Instanced Geometry Pathfinding Override",
        options=set(),
        get=get_poop_pathfinding_policy,
        description="Sets the pathfinding policy for this instanced geometry",
        default = '_connected_poop_instance_pathfinding_policy_cutout',
        items=poop_pathfinding_items,
        )

    poop_imposter_policy : EnumProperty(
        name="Instanced Geometry Imposter Policy",
        options=set(),
        description="Sets the imposter policy for this instanced geometry",
        default = "_connected_poop_instance_imposter_policy_never",
        items=[ ('_connected_poop_instance_imposter_policy_polygon_default', "Polygon Default", ""),
                ('_connected_poop_instance_imposter_policy_polygon_high', "Polygon High", ""),
                ('_connected_poop_instance_imposter_policy_card_default', "Card Default", ""),
                ('_connected_poop_instance_imposter_policy_card_high', "Card High", ""),
                ('_connected_poop_instance_imposter_policy_none', "None", ""),
                ('_connected_poop_instance_imposter_policy_never', "Never", ""),
               ]
        )

    poop_imposter_brightness: FloatProperty( # h4+
        name="Imposter Brightness",
        options=set(),
        description="Sets the brightness of the imposter variant of this instance",
        default=0.0,
        min=0.0
    )

    poop_imposter_transition_distance: FloatProperty(
        name="Instanced Geometry Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=50,
    )

    poop_imposter_transition_distance_auto: BoolProperty(
        name="Instanced Geometry Imposter Transition Automatic",
        options=set(),
        description="Enable to let the engine set the imposter transition distance by object size",
        default=True,
    )

    poop_streaming_priority : EnumProperty( # h4+
        name="Streaming Priority",
        options=set(),
        description="Sets the streaming priority for this instance",
        default = "_connected_geometry_poop_streamingpriority_default",
        items=[ ('_connected_geometry_poop_streamingpriority_default', "Default", ""),
                ('_connected_geometry_poop_streamingpriority_higher', "Higher", ""),
                ('_connected_geometry_poop_streamingpriority_highest', "Highest", ""),
               ]
        )

    # Poop_Imposter_Fade_Range_Start: IntProperty(
    #     name="Instanced Geometry Fade Start",
    #     options=set(),
    #     description="Start to fade in this instanced geometry when its bounding sphere is more than or equal to X pixels on the screen",
    #     default=36,
    #     subtype='PIXEL',
    # )

    # Poop_Imposter_Fade_Range_End: IntProperty(
    #     name="Instanced Geometry Fade End",
    #     options=set(),
    #     description="Renders this instanced geometry fully when its bounding sphere is more than or equal to X pixels on the screen",
    #     default=30,
    #     subtype='PIXEL',
    # )

    # Poop_Decomposition_Hulls: FloatProperty(
    #     name="Instanced Geometry Decomposition Hulls",
    #     options=set(),
    #     description="",
    #     default= 4294967295,
    # )
    
    # Poop_Predominant_Shader_Name: StringProperty(
    #     name="Instanced Geometry Predominant Shader Name",
    #     description="I have no idea what this does, but we'll write whatever you put here into the json file. The path should be relative and contain the shader extension (e.g. shader_relative_path\shader_name.shader)",
    #     maxlen=1024,
    # )

    poop_render_only: BoolProperty(
        name ="Render Only",
        options=set(),
        description = "Instanced geometry set to render only",
        default = False,
    )

    def get_poop_render_only(self):
        if bpy.context.active_object.name.startswith(poop_render_only_prefixes):
            return True
        else:
            return False

    poop_render_only_locked: BoolProperty(
        name ="Render Only",
        options=set(),
        get=get_poop_render_only,
        description = "Instanced geometry set to render only",
        default = False,
    )

    poop_chops_portals: BoolProperty(
        name ="Chops Portals",
        options=set(),
        description = "Instanced geometry set to chop portals",
        default = False,
    )

    poop_does_not_block_aoe: BoolProperty(
        name ="Does Not Block AOE",
        options=set(),
        description = "Instanced geometry set to not block area of effect forces",
        default = False,
    )

    poop_excluded_from_lightprobe: BoolProperty(
        name ="Excluded From Lightprobe",
        options=set(),
        description = "Sets this instanced geometry to be exlcuded from any lightprobes",
        default = False,
    )

    poop_decal_spacing: BoolProperty(
        name ="Decal Spacing",
        options=set(),
        description = "Instanced geometry set to have decal spacing (like decal_offset)",
        default = False,
    )

    poop_precise_geometry: BoolProperty(
        name ="Precise Geometry",
        options=set(),
        description = "Instanced geometry set to not have its geometry altered in the BSP pass",
        default = False,
    )

    poop_remove_from_shadow_geometry: BoolProperty( # H4+
        name ="Remove From Shadow Geo",
        options=set(),
        description = "",
        default = False,
    )

    poop_disallow_lighting_samples: BoolProperty( # H4+
        name ="Disallow Lighting Samples",
        options=set(),
        description = "",
        default = False,
    )

    poop_rain_occluder: BoolProperty( # H4+
        name ="Rain Occluder",
        options=set(),
        description = "",
        default = False,
    )

    poop_cinematic_properties : EnumProperty( # h4+
        name="Cinematic Properties",
        options=set(),
        description="Sets whether the instance should render only in cinematics, only outside of cinematics, or in both environments",
        default = "_connected_geometry_poop_cinema_default",
        items=[ ('_connected_geometry_poop_cinema_default', "Default", "Include both in cinematics and outside of them"),
                ('_connected_geometry_poop_cinema_only', "Cinematic Only", "Only render in cinematics"),
                ('_connected_geometry_poop_cinema_exclude', "Exclude From Cinematics", "Do not render in cinematics"),
               ]
        )

    # poop light channel flags. Not included for now   

    poop_collision_type: EnumProperty(
        name ="Instanced Collision Type",
        options=set(),
        description = "Set the instanced collision type. Only used when exporting a scenario",
        default = '_connected_geometry_poop_collision_type_default',
        items=[ ('_connected_geometry_poop_collision_type_default', 'Default', 'Collision mesh that interacts with the physics objects and with projectiles'),
                ('_connected_geometry_poop_collision_type_play_collision', 'Player Collision', 'The collision mesh affects physics objects, but not projectiles'),
                ('_connected_geometry_poop_collision_type_bullet_collision', 'Bullet Collision', 'The collision mesh only interacts with projectiles'),
                ('_connected_geometry_poop_collision_type_invisible_wall', 'Invisible Wall', "Projectiles go through this but the physics objects can't. You cannot directly place objects on wall collision mesh in Sapien"),
            ]
    )

    #portal PROPERTIES
    portal_type : EnumProperty(
        name="Portal Type",
        options=set(),
        description="Sets the type of portal this mesh should be",
        default = "_connected_geometry_portal_type_two_way",
        items=[ ('_connected_geometry_portal_type_no_way', "No Way", "Sets the portal to block all visibility"),
                ('_connected_geometry_portal_type_one_way', "One Way", "Sets the portal to block visibility from one direction"),
                ('_connected_geometry_portal_type_two_way', "Two Way", "Sets the portal to have visiblity from both sides"),
               ]
        )

    portal_ai_deafening: BoolProperty(
        name ="AI Deafening",
        options=set(),
        description = "Stops AI hearing through this portal",
        default = False,
    )

    portal_blocks_sounds: BoolProperty(
        name ="Blocks Sounds",
        options=set(),
        description = "Stops sound from travelling past this portal",
        default = False,
    )

    portal_is_door: BoolProperty(
        name ="Is Door",
        options=set(),
        description = "Portal visibility is attached to a device machine state",
        default = False,
    )

    #DECORATOR PROPERTIES

    def get_decorator_name(self):
        name = self.id_data.name
        name = name.removeprefix('+decorator')
        name = name.strip(' :"')

        return shortest_string(name, name.rpartition('.')[0]).lower()

    decorator_name: StringProperty(
        name="Decorator Name",
        description="Name of your decorator",
        get=get_decorator_name,
    )

    decorator_lod: IntProperty(
        name="Decorator Level of Detail",
        options=set(),
        description="Level of detail objects to create expressed in an integer range of 1-4",
        default=1,
        min=1,
        max=4,
    )

    #SEAM PROPERTIES # commented out 03-11-2022 as seam name is something that can be infered at export
    # Seam_Name: StringProperty(
    #     name="Seam BSP Name",
    #     description="Name of the bsp associated with this seam", 
    #     maxlen=32,
    # )

    # def get_seam_name(self):
    #     a_ob = bpy.context.active_object
        
    #     var =  a_ob.name.rpartition(':')[2]
    #     return var[0:31]

    # Seam_Name_Locked: StringProperty(
    #     name="Seam BSP Name",
    #     description="Name of the bsp associated with this seam",
    #     get=get_seam_name,
    #     maxlen=32,
    # )

    #WATER VOLUME PROPERTIES
    water_volume_depth: FloatProperty( # this something which can probably be automated?
        name="Water Volume Depth",
        options=set(),
        description="Set the depth of this water volume mesh",
        default=20,
    )
    water_volume_flow_direction: FloatProperty( # this something which can probably be automated?
        name="Water Volume Flow Direction",
        options=set(),
        description="Set the flow direction of this water volume mesh",
        min=-180,
        max=180,
    )

    water_volume_flow_velocity: FloatProperty(
        name="Water Volume Flow Velocity",
        options=set(),
        description="Set the flow velocity of this water volume mesh",
        default=20,
    )

    water_volume_fog_color: FloatVectorProperty(
        name="Water Volume Fog Color",
        options=set(),
        description="Set the fog color of this water volume mesh",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    water_volume_fog_murkiness: FloatProperty(
        name="Water Volume Fog Murkiness",
        options=set(),
        description="Set the fog murkiness of this water volume mesh",
        default=0.5,
        subtype='FACTOR',
        min=0.0,
        max=1.0
    )
    
    def get_fog_name(self):
        name = self.id_data.name
        name = name.removeprefix('+fog')
        name = name.strip(' :"')

        return shortest_string(name, name.rpartition('.')[0]).lower()

    #FOG PROPERTIES
    fog_name: StringProperty(
        name="Fog Name",
        description="Name of this fog volume",
        get=get_fog_name,
    )

    def fog_clean_tag_path(self, context):
        self['Fog_Appearance_Tag'] = clean_tag_path(self['Fog_Appearance_Tag']).strip('"')

    fog_appearance_tag: StringProperty(
        name="Fog Appearance Tag",
        description="Name of the tag defining the fog volumes appearance",
        update=fog_clean_tag_path,
    )

    fog_volume_depth: FloatProperty(
        name="Fog Volume Depth",
        options=set(),
        description="Set the depth of the fog volume",
        default=20,
    )

    # OBB PROPERTIES (H4+)
    obb_volume_type : EnumProperty(
        name="OBB Type",
        options=set(),
        description="",
        default = "_connected_geometry_mesh_obb_volume_type_streamingvolume",
        items=[ ('_connected_geometry_mesh_obb_volume_type_streamingvolume', "Streaming", ""),
                ('_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume', "Lightmap Exclusion", ""),
               ]
        )
    #LIGHTMAP PROPERTIES

    lightmap_additive_transparency_active : BoolProperty()
    lightmap_additive_transparency: FloatVectorProperty(
        name="lightmap Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint colour will override the alpha blend settings in the shader.",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    lightmap_ignore_default_resolution_scale: BoolProperty(
        name ="Lightmap Resolution Scale",
        options=set(),
        description = "",
        default = False,
    )

    lightmap_resolution_scale_active : BoolProperty()
    lightmap_resolution_scale: IntProperty(
        name="Lightmap Resolution Scale",
        options=set(),
        description="",
        default=3,
        min=1,
    )

    lightmap_photon_fidelity : EnumProperty(
        name="Photon Fidelity",
        options=set(),
        description="H4+ only",
        default = "_connected_material_lightmap_photon_fidelity_normal",
        items=[ ('_connected_material_lightmap_photon_fidelity_normal', "Normal", ""),
                ('_connected_material_lightmap_photon_fidelity_medium', "Medium", ""),
                ('_connected_material_lightmap_photon_fidelity_high', "High", ""),
                ('_connected_material_lightmap_photon_fidelity_none', "None", ""),
               ]
        )

    # Lightmap_Chart_Group: IntProperty(
    #     name="Lightmap Chart Group",
    #     options=set(),
    #     description="",
    #     default=3,
    #     min=1,
    # )
    lightmap_type_active : BoolProperty()
    lightmap_type : EnumProperty(
        name="Lightmap Type",
        options=set(),
        description="Sets how this should be lit while lightmapping",
        default = "_connected_material_lightmap_type_per_pixel",
        items=[ ('_connected_material_lightmap_type_per_pixel', "Per Pixel", ""),
                ('_connected_material_lightmap_type_per_vertex', "Per Vetex", ""),
               ]
        )

    lightmap_transparency_override: BoolProperty(
        name ="Lightmap Transparency Override",
        options=set(),
        description = "",
        default = False,
    )

    lightmap_analytical_bounce_modifier_active : BoolProperty()
    lightmap_analytical_bounce_modifier: FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="",
        default=1,
    )
    
    lightmap_general_bounce_modifier_active : BoolProperty()
    lightmap_general_bounce_modifier: FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="",
        default=1,
    )
    lightmap_translucency_tint_color_active : BoolProperty()
    lightmap_translucency_tint_color: FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    lightmap_lighting_from_both_sides_active : BoolProperty()
    lightmap_lighting_from_both_sides: BoolProperty(
        name ="Lightmap Lighting From Both Sides",
        options=set(),
        description = "",
        default = False,
    )

    #MATERIAL LIGHTING PROPERTIES
    material_lighting_attenuation_active : BoolProperty()
    material_lighting_attenuation_cutoff: FloatProperty(
        name="Material Lighting Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops",
        min=0,
        default=200,
    ) 

    lighting_attenuation_enabled: BoolProperty(
        name="Use Attenuation",
        options=set(),
        description="Enable / Disable use of attenuation",
        default=True,
    )

    lighting_frustum_blend: FloatProperty(
        name="Frustum blend",
        options=set(),
        description="",
        min=0,
        default=0,
    )

    lighting_frustum_cutoff: FloatProperty(
        name="Frustum cutoff",
        options=set(),
        description="",
        min=0,
        default=0,
    )

    lighting_frustum_falloff: FloatProperty(
        name="Frustum Falloff",
        options=set(),
        description="",
        min=0,
        default=0,
    )

    material_lighting_attenuation_falloff: FloatProperty(
        name="Material Lighting Attenuation Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=100,
    )

    material_lighting_emissive_focus_active : BoolProperty()
    material_lighting_emissive_focus: FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="",
    )

    material_lighting_emissive_color_active : BoolProperty()
    material_lighting_emissive_color: FloatVectorProperty(
        name="Material Lighting Emissive Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit_active : BoolProperty()
    material_lighting_emissive_per_unit: BoolProperty(
        name ="Material Lighting Emissive Per Unit",
        options=set(),
        description = "",
        default = False,
    )

    material_lighting_emissive_power_active : BoolProperty()
    material_lighting_emissive_power: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="",
        min=0,
        default=100,
    )

    material_lighting_emissive_quality_active : BoolProperty()
    material_lighting_emissive_quality: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel_active : BoolProperty()
    material_lighting_use_shader_gel: BoolProperty(
        name ="Material Lighting Use Shader Gel",
        options=set(),
        description = "",
        default = False,
    )

    material_lighting_bounce_ratio_active : BoolProperty()
    material_lighting_bounce_ratio: FloatProperty(
        name="Material Lighting Bounce Ratio",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    def get_markertype_enum(self):
        if self.id_data.name.startswith('?'):
            return 2
        elif self.id_data.name.startswith('$'):
            return 6
        else:
            return 0

    marker_types = [ ('_connected_geometry_marker_type_model', "Model", "Default marker type. Defines render_model markers for models, and structure markers for bsps"),
                ('_connected_geometry_marker_type_effects', "Effects", "Marker for effects only."),
                ('_connected_geometry_marker_type_game_instance', "Game Object", "Game Instance marker. Used to create an instance of a tag in the bsp. Can be set with the prefix: ?"),
                ('_connected_geometry_marker_type_garbage', "Garbage", "marker to define position that garbage pieces should be created"),
                ('_connected_geometry_marker_type_hint', "Hint", "Used for ai hints"),
                ('_connected_geometry_marker_type_pathfinding_sphere', "Pathfinding Sphere", "Used to create ai pathfinding spheres"),
                ('_connected_geometry_marker_type_physics_constraint', "Physics Constraint", "Used to define various types of physics constraints"),
                ('_connected_geometry_marker_type_target', "Target", "Defines the markers used in a model's targets'"),
                ('_connected_geometry_marker_type_water_volume_flow', "Water Volume Flow", "Used to define water flow for water physics volumes. For structure_design tags only"),
               ]

    #MARKER PROPERTIES
    objectmarker_type : EnumProperty(
        name="Marker Type",
        options=set(),
        description="Select the marker type",
        default = "_connected_geometry_marker_type_model",
        items=marker_types,
        )

    objectmarker_type_locked : EnumProperty(
        name="Marker Type",
        options=set(),
        description="Select the marker type",
        default = "_connected_geometry_marker_type_model",
        get=get_markertype_enum,
        items=marker_types,
        )
    
    # h4 versions
    marker_types_h4 = [ ('_connected_geometry_marker_type_model', "Model", "Default marker type. Defines render_model markers for models, and structure markers for bsps"),
                ('_connected_geometry_marker_type_effects', "Effects", "Marker for effects only."),
                ('_connected_geometry_marker_type_game_instance', "Game Object", "Game Instance marker. Used to create an instance of a tag in the bsp. Can be set with the prefix: ?"),
                ('_connected_geometry_marker_type_garbage', "Garbage", "marker to define position that garbage pieces should be created"),
                ('_connected_geometry_marker_type_hint', "Hint", "Used for ai hints"),
                ('_connected_geometry_marker_type_pathfinding_sphere', "Pathfinding Sphere", "Used to create ai pathfinding spheres"),
                ('_connected_geometry_marker_type_physics_constraint', "Physics Constraint", "Used to define various types of physics constraints"),
                ('_connected_geometry_marker_type_target', "Target", "Defines the markers used in a model's targets'"),
                ('_connected_geometry_marker_type_water_volume_flow', "Water Volume Flow", "Used to define water flow for water physics volumes. For structure_design tags only"),
                ('_connected_geometry_marker_type_airprobe', "Airprobe", "Airprobes tell the game how to handle static lighting on dynamic objects"),
                ('_connected_geometry_marker_type_envfx', "Environment Effect", "Plays an effect on this point in the structure"),
                ('_connected_geometry_marker_type_lightCone', "Light Cone", "Creates a light cone with the defined parameters"),
               ]

    objectmarker_type_h4 : EnumProperty(
        name="Marker Type",
        options=set(),
        description="Select the marker type",
        default = "_connected_geometry_marker_type_model",
        items=marker_types_h4,
        )

    objectmarker_type_locked_h4 : EnumProperty(
        name="Marker Type",
        options=set(),
        description="Select the marker type",
        default = "_connected_geometry_marker_type_model",
        get=get_markertype_enum,
        items=marker_types_h4,
        )
    
    def get_marker_group_name(self):
        name = self.id_data.name
        name = name.removeprefix('#')
        if name.startswith('('):
            name = shortest_string(name, name.rpartition(')')[2])
        name = name.strip(' :_"')

        return shortest_string(name, name.rpartition('.')[0]).lower()

    marker_group_name: StringProperty(
        name="Marker Group",
        description="Displays the name of the marker group. Marker groups equal the object name minus the '#' prefix and text after the last '.', allowing for multiple markers to share the same group",
        get=get_marker_group_name,
    )

    marker_region: StringProperty(
        name="Marker Group",
        description="Define the name of marker region. This should match a face region name. Leave blank for the 'default' region",
    )

    marker_all_regions: BoolProperty(
        name="Marker All Regions",
        options=set(),
        description="Associate this marker with all regions rather than a specific one",
        default=True,
    )

    def game_instance_clean_tag_path(self, context):
        self['marker_game_instance_tag_name'] = clean_tag_path(self['marker_game_instance_tag_name']).strip('"')

    marker_game_instance_tag_name: StringProperty(
        name="Marker Game Instance Tag",
        description="Define the name of the marker game instance tag",
        update=game_instance_clean_tag_path,
    )

    marker_game_instance_tag_variant_name: StringProperty(
        name="Marker Game Instance Tag Variant",
        description="Define the name of the marker game instance tag variant",
    )

    marker_game_instance_run_scripts: BoolProperty(
        name="Always Run Scripts",
        options=set(),
        description="Tells this game instance object to always run scripts if it has any",
        default=True
    )

    marker_hint_length: FloatProperty(
        name="Hint Length",
        options=set(),
        description="",
        default=0.0,
        min=0.0,
    )

    marker_hint_type: EnumProperty(
        name="Type",
        options=set(),
        description="",
        default='bunker',
        items=[
            ('bunker', 'Bunker', ''),
            ('corner', 'Corner', ''),
            ('vault', 'Vault', ''),
            ('mount', 'Mount', ''),
            ('hoist', 'Hoist', ''),
        ]
    )

    marker_hint_side: EnumProperty(
        name="Side",
        options=set(),
        description="",
        default='right',
        items=[
            ('right', 'Right', ''),
            ('left', 'Left', ''),
        ]
    )

    marker_hint_height: EnumProperty(
        name="Height",
        options=set(),
        description="",
        default='step',
        items=[
            ('step', 'Step', ''),
            ('crouch', 'Crouch', ''),
            ('stand', 'Stand', ''),
        ]
    )

    marker_sphere_radius: FloatProperty(
        name="Sphere Radius",
        options=set(),
        description="Manually define the sphere radius for this marker. Alternatively, create a marker out of a mesh to have this radius set based on mesh dimensions",
        default=0.0,
        min=0.0,
    )

    marker_velocity: FloatVectorProperty(
        name="Marker Velocity",
        options=set(),
        description="",
        subtype='VELOCITY',
    )

    marker_pathfinding_sphere_vehicle: BoolProperty(
        name="Vehicle Only Pathfinding Sphere",
        options=set(),
        description="This pathfinding sphere only affects vehicles",
    )

    pathfinding_sphere_remains_when_open: BoolProperty(
        name="Pathfinding Sphere Remains When Open",
        options=set(),
        description="Pathfinding sphere remains even when a machine is open",
    )

    pathfinding_sphere_with_sectors: BoolProperty(
        name="Pathfinding Sphere With Sectors",
        options=set(),
        description="Not sure",
    )

    physics_constraint_parent: PointerProperty( #need to make this into an object picker at some point
        name="Physics Constraint Parent",
        description="Enter the name of the object that is this marker's parent",
        type=bpy.types.Object
    )

    physics_constraint_child: PointerProperty( #need to make this into an object picker at some point
        name="Physics Constraint Child",
        description="Enter the name of the object that is this marker's child",
        type=bpy.types.Object
    )

    physics_constraint_type : EnumProperty(
        name="Constraint Type",
        options=set(),
        description="Select the physics constraint type",
        default = "_connected_geometry_marker_type_physics_hinge_constraint",
        items=[ ('_connected_geometry_marker_type_physics_hinge_constraint', "Hinge", ""),
                ('_connected_geometry_marker_type_physics_socket_constraint', "Socket", ""),
               ]
        )

    physics_constraint_uses_limits: BoolProperty(
        name="Physics Constraint Uses Limits",
        options=set(),
        description="Set whether the limits of this physics constraint should be constrained or not",
    )

    hinge_constraint_minimum: FloatProperty(
        name="Hinge Constraint Minimum",
        options=set(),
        description="Set the minimum rotation of a physics hinge",
        default=-180,
        min=-180,
        max=180,
    )

    hinge_constraint_maximum: FloatProperty(
        name="Hinge Constraint Maximum",
        options=set(),
        description="Set the maximum rotation of a physics hinge",
        default=180,
        min=-180,
        max=180,
    )

    cone_angle: FloatProperty(
        name="Cone Angle",
        options=set(),
        description="Set the cone angle",
        default=90,
        min=0,
        max=180,
    )

    plane_constraint_minimum: FloatProperty(
        name="Plane Constraint Minimum",
        options=set(),
        description="Set the minimum rotation of a physics plane",
        default=-90,
        min=-90,
        max=0,
    )

    plane_constraint_maximum: FloatProperty(
        name="Plane Constraint Maximum",
        options=set(),
        description="Set the maximum rotation of a physics plane",
        default=90,
        min=-0,
        max=90,

    )

    twist_constraint_start: FloatProperty(
        name="Twist Constraint Minimum",
        options=set(),
        description="Set the starting angle of a twist constraint",
        default=-180,
        min=-180,
        max=180,
    )

    twist_constraint_end: FloatProperty(
        name="Twist Constraint Maximum",
        options=set(),
        description="Set the ending angle of a twist constraint",
        default=180,
        min=-180,
        max=180,
    )

    def effect_clean_tag_path(self, context):
        self['marker_looping_effect'] = clean_tag_path(self['marker_looping_effect']).strip('"')

    marker_looping_effect: StringProperty(
        name="Effect Path",
        description="Tag path to an effect",
        update=effect_clean_tag_path
    )

    def light_cone_clean_tag_path(self, context):
        self['marker_light_cone_tag'] = clean_tag_path(self['marker_light_cone_tag']).strip('"')

    marker_light_cone_tag: StringProperty(
        name="Light Cone Tag Path",
        description="Tag path to a light cone",
        update=light_cone_clean_tag_path,
    )

    marker_light_cone_color: FloatVectorProperty(
        name="Light Cone Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    marker_light_cone_alpha: FloatProperty(
        name="Light Cone Alpha",
        options=set(),
        description="",
        default=1.0,
        subtype='FACTOR',
        min=0.0,
        max=1.0,
    )

    marker_light_cone_width: FloatProperty(
        name="Light Cone Width",
        options=set(),
        description="",
        default=5,
        min=0,
    )

    marker_light_cone_length: FloatProperty(
        name="Light Cone Length",
        options=set(),
        description="",
        default=10,
        min=0,
    )

    marker_light_cone_intensity: FloatProperty(
        name="Light Cone Intensity",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    def light_cone_curve_clean_tag_path(self, context):
        self['marker_light_cone_curve'] = clean_tag_path(self['marker_light_cone_curve']).strip('"')

    marker_light_cone_curve: StringProperty(
        name="Light Cone Curve Tag Path",
        description="",
        update=light_cone_curve_clean_tag_path,
    )

# ANIMATION EVENTS
    event_id: IntProperty()

    event_type: EnumProperty(
        name='Type',
        default='_connected_geometry_animation_event_type_frame',
        options=set(),
        items = [
            ('_connected_geometry_animation_event_type_custom', 'Custom', ''),
            ('_connected_geometry_animation_event_type_loop', 'Loop', ''),
            ('_connected_geometry_animation_event_type_sound', 'Sound', ''),
            ('_connected_geometry_animation_event_type_effect', 'Effect', ''),
            ('_connected_geometry_animation_event_type_ik_active', 'IK Active', ''),
            ('_connected_geometry_animation_event_type_ik_passive', 'IK Passive', ''),
            ('_connected_geometry_animation_event_type_text', 'Text', ''),
            ('_connected_geometry_animation_event_type_wrinkle_map', 'Wrinkle Map', ''),
            ('_connected_geometry_animation_event_type_footstep', 'Footstep', ''),
            ('_connected_geometry_animation_event_type_cinematic_effect', 'Cinematic Effect', ''),
            ('_connected_geometry_animation_event_type_object_function', 'Object Function', ''),
            ('_connected_geometry_animation_event_type_frame', 'Frame', ''),
            ('_connected_geometry_animation_event_type_import', 'Import', ''),
        ]
    )

    frame_start: FloatProperty(
        name='Frame Start',
        default=0,
        options=set(),
    )

    frame_end: FloatProperty(
        name='Frame End',
        default=0,
        options=set(),
    )

    wrinkle_map_face_region: StringProperty(
        name='Wrinkle Map Face Region',
        default='',
        options=set(),
    )

    wrinkle_map_effect: IntProperty(
        name='Wrinkle Map Effect',
        default=0,
        options=set(),
    )

    footstep_type: StringProperty(
        name='Footstep Type',
        default='',
        options=set(),
    )

    footstep_effect: IntProperty(
        name='Footstep Effect',
        default=0,
        options=set(),
    )

    ik_chain: StringProperty(
        name='IK Chain',
        default='',
        options=set(),
    )

    ik_active_tag: StringProperty(
        name='IK Active Tag',
        default='',
        options=set(),
    )

    ik_target_tag: StringProperty(
        name='IK Target Tag',
        default='',
        options=set(),
    )

    ik_target_marker: StringProperty(
        name='IK Target Marker',
        default='',
        options=set(),
    )

    ik_target_usage: StringProperty(
        name='IK Target Usage',
        default='',
        options=set(),
    )

    ik_proxy_target_id: IntProperty(
        name='IK Proxy Target ID',
        default=0,
        options=set(),
    )

    ik_pole_vector_id: IntProperty(
        name='IK Pole Vector ID',
        default=0,
        options=set(),
    )

    ik_effector_id: IntProperty(
        name='IK Effector ID',
        default=0,
        options=set(),
    )

    cinematic_effect_tag: StringProperty(
        name='Cinematic Effect Tag',
        default='',
        options=set(),
    )

    cinematic_effect_effect: IntProperty(
        name='Cinematic Effect',
        default=0,
        options=set(),
    )

    cinematic_effect_marker: StringProperty(
        name='Cinematic Effect Marker',
        default='',
        options=set(),
    )

    object_function_name: StringProperty(
        name='Object Function Name',
        default='',
        options=set(),
    )

    object_function_effect: IntProperty(
        name='Object Function Effect',
        default=0,
        options=set(),
    )

    frame_frame: IntProperty(
        name='Event Frame',
        default=0,
        options=set(),
    )

    frame_name: EnumProperty(
        name='Frame Name',
        default='none',
        options=set(),
        items = [
                ('none', 'None', ''),
                ('primary keyframe', 'Primary Keyframe', ''),
                ('secondary keyframe', 'Secondary Keyframe', ''),
                ('tertiary keyframe', 'Tertiary Keyframe', ''),
                ('left foot', 'Left Foot', ''),
                ('right foot', 'Right Foot', ''),
                ('allow interruption', 'Allow Interruption', ''),
                ('do not allow interruption', 'Do Not Allow Interruption', ''),
                ('both-feet shuffle', 'Both-Feet Shuffle', ''),
                ('body impact', 'Body Impact', ''),
                ('left foot lock', 'Left Foot Lock', ''),
                ('left foot unlock', 'Left Foot Unlock', ''),
                ('right foot lock', 'Right Foot Lock', ''),
                ('right foot unlock', 'Right Foot Unlock', ''),
                ('blend range marker', 'Blend Range Marker', ''),
                ('stride expansion', 'Stride Expansion', ''),
                ('stride contraction', 'Stride Contraction', ''),
                ('ragdoll keyframe', 'Ragdoll Keyframe', ''),
                ('drop weapon keyframe', 'Drop Weapon Keyframe', ''),
                ('match a', 'Match A', ''),
                ('match b', 'Match B', ''),
                ('match c', 'Match C', ''),
                ('match d', 'Match D', ''),
                ('jetpack closed', 'Jetpack Closed', ''),
                ('jetpack open', 'Jetpack Open', ''),
                ('sound event', 'Sound Event', ''),
                ('effect event', 'Effect Event', ''),
            ]
    )

    # frame_name_sound: EnumProperty(
    #     name='Frame Type',
    #     default='none',
    #     options=set(),
    #     items = [
    #             ('left foot', 'Left Foot', ''),
    #             ('right foot', 'Right Foot', ''),
    #             ('both-feet shuffle', 'Both-Feet Shuffle', ''),
    #             ('body impact', 'Body Impact', ''),
    #         ]
    # )

    # frame_name_sync: EnumProperty(
    #     name='Frame Type',
    #     default='none',
    #     options=set(),
    #     items = [
    #             ('allow interruption', 'Allow Interruption', ''),
    #             ('blend range marker', 'Blend Range Marker', ''),
    #             ('ragdoll keyframe', 'Ragdoll Keyframe', ''),
    #             ('drop weapon keyframe', 'Drop Weapon Keyframe', ''),
    #         ]
    # )

    # frame_name_navigation: EnumProperty(
    #     name='Frame Type',
    #     default='none',
    #     options=set(),
    #     items = [
    #             ('match a', 'Match A', ''),
    #             ('match b', 'Match B', ''),
    #             ('match c', 'Match C', ''),
    #             ('match d', 'Match D', ''),
    #             ('stride expansion', 'Stride Expansion', ''),
    #             ('stride contraction', 'Stride Contraction', ''),
    #             ('left foot lock', 'Left Foot Lock', ''),
    #             ('left foot unlock', 'Left Foot Unlock', ''),
    #             ('right foot lock', 'Right Foot Lock', ''),
    #             ('right foot unlock', 'Right Foot Unlock', ''),
    #         ]
    # )

    frame_trigger: BoolProperty(
        name='Frame Trigger',
        default=False,
        options=set(),
    )

    import_frame: IntProperty(
        name='Import Frame',
        default=0,
        options=set(),
    )

    import_name: StringProperty(
        name='Import Name',
        default='',
        options=set(),
    )

    text: StringProperty(
        name='Text',
        default='',
        options=set(),
    )

    is_animation_event: BoolProperty()

class NWO_LightPropertiesGroup(PropertyGroup):
# LIGHTS #
    light_type_override: EnumProperty(
        name = "Light Type",
        options=set(),
        description = "Displays the light type. Use the blender light types to change the value of this field",
        default = "_connected_geometry_light_type_omni",
        items=[ ('_connected_geometry_light_type_spot', "Spot", ""),
                ('_connected_geometry_light_type_directional', "Directional", ""),
                ('_connected_geometry_light_type_omni', "Point", ""),
               ]
        )

    light_game_type: EnumProperty(
        name = "Light Game Type",
        options=set(),
        description = "",
        default = "_connected_geometry_bungie_light_type_default",
        items=[ ('_connected_geometry_bungie_light_type_default', "Default", ""),
                ('_connected_geometry_bungie_light_type_inlined', "Inlined", ""),
                ('_connected_geometry_bungie_light_type_rerender', "Rerender", ""),
                ('_connected_geometry_bungie_light_type_screen_space', "Screen Space", ""),
                ('_connected_geometry_bungie_light_type_uber', "Uber", ""),
               ]
        )

    light_shape: EnumProperty(
        name = "Light Shape",
        options=set(),
        description = "",
        default = "_connected_geometry_light_shape_circle",
        items=[ ('_connected_geometry_light_shape_circle', "Circle", ""),
                ('_connected_geometry_light_shape_rectangle', "Rectangle", ""),
               ]
        )

    light_near_attenuation: BoolProperty(
        name="Light Uses Near Attenuation",
        options=set(),
        description="",
        default=True,
    )

    light_far_attenuation: BoolProperty(
        name="Light Uses Far Attenuation",
        options=set(),
        description="",
        default=True,
    )

    light_near_attenuation_start: FloatProperty(
        name="Light Near Attenuation Start Distance",
        options=set(),
        description="The power of the light remains zero up until this point",
        default=0,
        min=0,
    )

    light_near_attenuation_end: FloatProperty(
        name="Light Near Attenuation End Distance",
        options=set(),
        description="From the starting near attenuation, light power gradually increases up until the end point",
        default=0,
        min=0,
    )

    light_far_attenuation_start: FloatProperty(
        name="Light Near Attenuation Start Distance",
        options=set(),
        description="After this point, the light will begin to lose power",
        default=500,
        min=0,
    )

    light_far_attenuation_end: FloatProperty(
        name="Light Near Attenuation Start Distance",
        options=set(),
        description="From the far attenuation start, the light will gradually lose power until it reaches zero by the end point",
        default=1000,
        min=0,
    )

    light_volume_distance: FloatProperty(
        name="Light Volume Distance",
        options=set(),
        description="",
    )

    light_volume_intensity: FloatProperty(
        name="Light Volume Intensity",
        options=set(),
        description="",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        subtype='FACTOR',
    )

    light_fade_start_distance: FloatProperty(
        name="Light Fade Out Start",
        options=set(),
        description="The light starts to fade out when the camera is x world units away",
        default=100.0,
    )

    light_fade_end_distance: FloatProperty(
        name="Light Fade Out End",
        options=set(),
        description="The light completely fades out when the camera is x world units away",
        default=150.0,
    )

    light_ignore_bsp_visibility: BoolProperty(
        name="Light Ignore BSP Visibility",
        options=set(),
        description="",
        default=False,
    )

    # def get_blend_light_color(self):
    #     ob = self.id_data
    #     if ob.type == 'LIGHT':
    #         return self.Light_Color
    #     else:
    #         return (1.0, 1.0, 1.0)

    # Light_Color: FloatVectorProperty(
    #     name="Light Color",
    #     options=set(),
    #     description="",
    #     default=(1.0, 1.0, 1.0),
    #     subtype='COLOR',
    #     min=0.0,
    #     max=1.0,
    #     get=get_blend_light_color,
    # )

    light_intensity: FloatProperty(
        name="Light Intensity",
        options=set(),
        description="",
        default=1,
        min=0.0,
        soft_max=10.0,
        subtype='FACTOR',
    )

    light_use_clipping: BoolProperty(
        name="Light Uses Clipping",
        options=set(),
        description="",
        default=False,
    )

    light_clipping_size_x_pos: FloatProperty(
        name="Light Clipping Size X Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_y_pos: FloatProperty(
        name="Light Clipping Size Y Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_z_pos: FloatProperty(
        name="Light Clipping Size Z Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_x_neg: FloatProperty(
        name="Light Clipping Size X Backward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_y_neg: FloatProperty(
        name="Light Clipping Size Y Backward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_z_neg: FloatProperty(
        name="Light Clipping Size Z Backward",
        options=set(),
        description="",
        default=100,
    )

    light_hotspot_size: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=25,
    )

    light_hotspot_falloff: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=80,
    )

    light_falloff_shape: FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="",
        default=1,
        min=0.0,
        soft_max=10.0,
        subtype='FACTOR',
    )

    light_aspect: FloatProperty(
        name="Light Aspect",
        options=set(),
        description="",
        default=1,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    light_frustum_width: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=1.0,
    )

    light_frustum_height: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=1.0,
    )

    light_bounce_ratio: FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="",
        default=1,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    light_dynamic_has_bounce: BoolProperty(
        name="Light Has Dynamic Bounce",
        options=set(),
        description="",
        default=False,
    )

    light_screenspace_has_specular: BoolProperty(
        name="Screenspace Light Has Specular",
        options=set(),
        description="",
        default=False,
    )

    def light_tag_clean_tag_path(self, context):
        self['Light_Tag_Override'] = clean_tag_path(self['Light_Tag_Override']).strip('"')

    light_tag_override: StringProperty(
        name="Light Tag Override",
        options=set(),
        description="",
        update=light_tag_clean_tag_path,
    )

    def light_shader_clean_tag_path(self, context):
        self['Light_Shader_Reference'] = clean_tag_path(self['Light_Shader_Reference']).strip('"')

    light_shader_reference: StringProperty(
        name="Light Shader Reference",
        options=set(),
        description="",
        update=light_shader_clean_tag_path,
    )

    def light_gel_clean_tag_path(self, context):
        self['Light_Gel_Reference'] = clean_tag_path(self['Light_Gel_Reference']).strip('"')

    light_gel_reference: StringProperty(
        name="Light Gel Reference",
        options=set(),
        description="",
        update=light_gel_clean_tag_path,
    )

    def light_lens_flare_clean_tag_path(self, context):
        self['Light_Lens_Flare_Reference'] = clean_tag_path(self['Light_Lens_Flare_Reference']).strip('"')

    light_lens_flare_reference: StringProperty(
        name="Light Lens Flare Reference",
        options=set(),
        description="",
        update=light_lens_flare_clean_tag_path,
    )

    # H4 LIGHT PROPERTIES
    light_dynamic_shadow_quality: EnumProperty(
        name = "Shadow Quality",
        options=set(),
        description = "",
        default = "_connected_geometry_dynamic_shadow_quality_normal",
        items=[ ('_connected_geometry_dynamic_shadow_quality_normal', "Normal", ""),
                ('_connected_geometry_dynamic_shadow_quality_expensive', "Expensive", ""),
               ]
        )

    light_specular_contribution: BoolProperty(
        name="Specular Contribution",
        options=set(),
        description="",
        default=False,
    )

    light_amplification_factor: FloatProperty(
        name="Indirect Amplification",
        options=set(),
        description="",
        default=0.5,
        subtype='FACTOR',
        min=0.0,
        soft_max=10.0
    )

    light_attenuation_near_radius: FloatProperty(
        name="Near Attenuation Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_attenuation_far_radius: FloatProperty(
        name="Far Attenuation Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_attenuation_power: FloatProperty(
        name="Attenuation Power",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_cinema_objects_only: BoolProperty( 
        name="Only Light Cinematic Objects",
        options=set(),
        description="",
        default=False,
    )

    light_tag_name: StringProperty(
        name="Light Tag Name",
        options=set(),
        description="",
    )

    # def get_light_type_h4(self):
    #     light_type = self.id_data.data.type
    #     if light_type == 'SUN':
    #         return 2
    #     elif light_type == 'POINT':
    #         return 0
    #     else:
    #         return 1
    
    # # def set_light_type_h4(self, value):
    # #     self["light_type_h4"] = value

    # light_type_h4: EnumProperty(
    #     name = "Light Type",
    #     options=set(),
    #     description = "",
    #     get=get_light_type_h4,
    #     # set=set_light_type_h4,
    #     default = "_connected_geometry_light_type_point",
    #     items=[ ('_connected_geometry_light_type_point', "Point", ""),
    #             ('_connected_geometry_light_type_spot', "Spot", ""),
    #             # ('_connected_geometry_light_type_directional', "Directional", ""),
    #             ('_connected_geometry_light_type_sun', "Sun", ""),
    #            ]
    #     )

    # def get_light_outer_cone_angle(self):
    #     return max(160, radians(self.id_data.data.spot_size))

    # light_outer_cone_angle: FloatProperty(
    #     name="Outer Cone Angle",
    #     options=set(),
    #     description="",
    #     default=80,
    #     min=0.0,
    #     max=160.0,
    #     get=get_light_outer_cone_angle,
    # )

    light_lighting_mode: EnumProperty(
        name = "Lighting Mode",
        options=set(),
        description = "",
        default = "_connected_geometry_lighting_mode_artistic",
        items=[ ('_connected_geometry_lighting_mode_artistic', "Artistic", ""),
                ('_connected_geometry_lighting_physically_correct', "Physically Correct", ""),
               ]
        )

    light_specular_power: FloatProperty(
        name="Specular Power",
        options=set(),
        description="",
        default=32,
        min=0.0,
    )

    light_specular_intensity: FloatProperty(
        name="Specular Intensity",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    # def get_light_inner_cone_angle(self):
    #     return max(160, radians(self.id_data.data.spot_size))

    # light_inner_cone_angle: FloatProperty(
    #     name="Inner Cone Angle",
    #     options=set(),
    #     description="",
    #     default=50,
    #     min=0.0,
    #     max=160,
    #     get=get_light_inner_cone_angle,
    # )

    light_cinema: EnumProperty(
        name="Cinematic Render",
        options=set(),
        description="Define whether this light should only render in cinematics, outside of cinematics, or always render",
        default='_connected_geometry_lighting_cinema_default',
        items=[ ('_connected_geometry_lighting_cinema_default', "Always", ""),
                ('_connected_geometry_lighting_cinema_only', "Cinematics Only", ""),
                ('_connected_geometry_lighting_cinema_exclude', "Exclude", ""),
               ]
        )

    light_cone_projection_shape: EnumProperty(
        name="Cone Projection Shape",
        options=set(),
        description = "",
        default = "_connected_geometry_cone_projection_shape_cone",
        items=[ ('_connected_geometry_cone_projection_shape_cone', "Cone", ""),
                ('_connected_geometry_cone_projection_shape_frustum', "Frustum", ""),
               ]
        )

    light_shadow_near_clipplane: FloatProperty(
        name="Shadow Near Clip Plane",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_jitter_sphere_radius: FloatProperty(
        name="Light Jitter Sphere Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_far_clipplane: FloatProperty(
        name="Shadow Far Clip Plane",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_bias_offset: FloatProperty(
        name="Shadow Bias Offset",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_color: FloatVectorProperty(
        name="Shadow Color",
        options=set(),
        description="",
        default=(0.0, 0.0, 0.0),
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    light_shadows: BoolProperty(
        name="Has Shadows",
        options=set(),
        description="",
        default=True,
    )

    light_sub_type: EnumProperty(
        name="Light Sub-Type",
        options=set(),
        description="",
        default='_connected_geometry_lighting_sub_type_default',
        items=[ ('_connected_geometry_lighting_sub_type_default', "Default", ""),
                ('_connected_geometry_lighting_sub_type_screenspace', "Screenspace", ""),
                ('_connected_geometry_lighting_sub_type_uber', "Uber", ""),
               ]
        )  

    light_ignore_dynamic_objects: BoolProperty(
        name="Ignore Dynamic Objects",
        options=set(),
        description="",
        default=False,
    )

    light_diffuse_contribution: BoolProperty(
        name="Diffuse Contribution",
        options=set(),
        description="",
        default=True,
    )

    light_destroy_after: FloatProperty(
        name="Destroy After (seconds)",
        options=set(),
        description="Destroy the light after x seconds. 0 means the light is never destroyed",
        subtype='TIME',
        unit='TIME',
        step=100,
        default=0,
        min=0.0,
    )

    light_jitter_angle: FloatProperty(
        name="Light Jitter Angle",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_jitter_quality: EnumProperty(
        name="Light Jitter Quality",
        options=set(),
        description="",
        default='_connected_geometry_light_jitter_quality_high',
        items=[ ('_connected_geometry_light_jitter_quality_low', "Low", ""),
                ('_connected_geometry_light_jitter_quality_medium', "Medium", ""),
                ('_connected_geometry_light_jitter_quality_high', "High", ""),
               ]
        )

    light_indirect_only: BoolProperty(
        name="Indirect Only",
        options=set(),
        description="",
        default=False,
    )

    light_screenspace: BoolProperty(
        name="Screenspace Light",
        options=set(),
        description="",
        default=False,
    )

    light_intensity_off: BoolProperty(
        name="Set Via Tag",
        options=set(),
        description="Stops this value being passed to the game. Use if you want to set the intensity manually in the tag (such as if you want to make use of functions for lights)",
        default=False,
    )

    near_attenuation_end_off: BoolProperty(
        name="Set Via Tag",
        options=set(),
        description="Stops this value being passed to the game. Use if you want to set the near attenuation end manually in the tag (such as if you want to make use of functions for lights)",
        default=False,
    )

    outer_cone_angle_off: BoolProperty(
        name="Set Via Tag",
        options=set(),
        description="Stops this value being passed to the game. Use if you want to set the outer cone angle manually in the tag (such as if you want to make use of functions for lights)",
        default=False,
    )

    manual_fade_distance: BoolProperty(
        name="Specify Fade Out Distance",
        options=set(),
        description="Reveals fade out distance settings",
        default=False,
    )

    light_static_analytic: BoolProperty(
        name="Static Analytic",
        options=set(),
        description="",
        default=False,
    )

    light_mode: EnumProperty(
        name="Light Mode",
        options=set(),
        description="",
        default='_connected_geometry_light_mode_static',
        items=[ ('_connected_geometry_light_mode_static', "Static", "Lights used in lightmapping"),
                ('_connected_geometry_light_mode_dynamic', "Dynamic", "Lights that appear regardless of whether the map has been lightmapped"),
                ('_connected_geometry_light_mode_analytic', "Analytic", ""),
               ]
        )

    light_near_attenuation_starth4: FloatProperty(
        name="Attenuation Start Distance",
        options=set(),
        description="",
        default=0.2,
        min=0,
    )

    light_near_attenuation_endh4: FloatProperty(
        name="Attenuation End Distance",
        options=set(),
        description="",
        default=10,
        min=0,
    )

    light_far_attenuation_starth4: FloatProperty(
        name="Camera Distance Fade Start",
        options=set(),
        description="",
        default=0,
        min=0,
    )

    light_far_attenuation_endh4: FloatProperty(
        name="Camera Distance Fade End",
        options=set(),
        description="",
        default=0,
        min=0,
    )

    # def update_blend_light_intensity_h4(self, context):
    #     print("updooting")
    #     ob = self.id_data
    #     if ob.type == 'LIGHT':
    #         if ob.data.type == 'SUN':
    #             ob.data.energy = self.Light_IntensityH4
    #         else:
    #             ob.data.energy = self.Light_IntensityH4 * 10 * context.scene.unit_settings.scale_length ** -2 # mafs. Gets around unit scale altering the light intensity to unwanted values

    # def get_light_intensity_h4(self):
    #     if  self.id_data.type == 'LIGHT':
    #         return (self.id_data.data.energy / 0.03048 ** -2) / 10
    #     else:
    #         50
    
    # # def set_light_intensity_h4(self, value):
    # #     self["Light_IntensityH4"] = value

    # Light_IntensityH4: FloatProperty(
    #     name="Light Intensity",
    #     options=set(),
    #     description="",
    #     default=50,
    #     min=0.0,
    #     # get=get_light_intensity_h4,
    #     # set=set_light_intensity_h4,
    #     get=get_light_intensity_h4
    # )

class NWO_MaterialPropertiesGroup(PropertyGroup):
    
    def update_shader(self, context):
        self['shader_path'] = clean_tag_path(self['shader_path']).strip('"')

    shader_path: StringProperty(
        name = "Shader Path",
        description = "Define the path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Including the file extension will automatically update the shader type",
        default = "",
        update=update_shader,
        )

    rendered : BoolProperty(default = True)

class NWO_BonePropertiesGroup(PropertyGroup):

    name_override: StringProperty(
        name="Name Override",
        description="Set the Halo export name for this bone. Allowing you to use blender friendly naming conventions for bones while rigging/animating",
        default=""
    )

    frame_id1: StringProperty(
        name = "Frame ID 1",
        description = "The Frame ID 1 for this bone. Leave blank for automatic assignment of a Frame ID. Can be manually edited when using expert mode, but don't do this unless you know what you're doing",
        default = "",
        )
    frame_id2: StringProperty(
        name = "Frame ID 2",
        description = "The Frame ID 2 for this bone. Leave blank for automatic assignment of a Frame ID. Can be manually edited when using expert mode, but don't do this unless you know what you're doing",
        default = "",
        )
    object_space_node: BoolProperty(
        name = "Object Space Offset Node",
        description = "",
        default = False,
        options=set(),
        )
    replacement_correction_node: BoolProperty(
        name = "Replacement Correction Node",
        description = "",
        default = False,
        options=set(),
        )
    fik_anchor_node: BoolProperty(
        name = "Forward IK Anchor Node",
        description = "",
        default = False,
        options=set(),
        )
    
#############################################################
# ANIMATION EVENTS
#############################################################
class NWO_UL_AnimProps_Events(UIList):
    # use_name_reverse: BoolProperty(
    #     name="Reverse Name",
    #     default=False,
    #     options=set(),
    #     description="Reverse name sort order",
    # )

    # use_order_name: BoolProperty(
    #     name="Name",
    #     default=False,
    #     options=set(),
    #     description="Sort groups by their name (case-insensitive)",
    # )

    # filter_string: StringProperty(
    #     name="filter_string",
    #     default = "",
    #     description="Filter string for name"
    # )

    # filter_invert: BoolProperty(
    #     name="Invert",
    #     default = False,
    #     options=set(),
    #     description="Invert Filter"
    # )


    # def filter_items(self, _context, data, property):
    #     attributes = getattr(data, property)
    #     flags = []
    #     indices = [i for i in range(len(attributes))]

    #     # Filtering by name
    #     if self.filter_name:
    #         flags = bpy.types.UI_UL_list.filter_items_by_name(
    #             self.filter_name, self.bitflag_filter_item, attributes, "name", reverse=self.use_filter_invert)
    #     if not flags:
    #         flags = [self.bitflag_filter_item] * len(attributes)

    #     # Filtering internal attributes
    #     for idx, item in enumerate(attributes):
    #         flags[idx] = 0 if item.is_internal else flags[idx]

    #     return flags, indices      

    # def draw_filter(self, context,
    #                 layout
    #     ):

    #     row = layout.row(align=True)
    #     row.prop(self, "filter_string", text="Filter", icon="VIEWZOOM")
    #     row.prop(self, "filter_invert", text="", icon="ARROW_LEFTRIGHT")


    #     row = layout.row(align=True)
    #     row.label(text="Order by:")
    #     row.prop(self, "use_order_name", toggle=True)

    #     icon = 'TRIA_UP' if self.use_name_reverse else 'TRIA_DOWN'
    #     row.prop(self, "use_name_reverse", text="", icon=icon)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        animation = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if animation:
                layout.prop(animation, "name", text="", emboss=False, icon_value=495)
            else:
                layout.label(text="", translate=False, icon_value=icon)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)

    # def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
    #     if self.layout_type in {'DEFAULT', 'COMPACT'}:
    #         layout.prop(item, "name", text="", emboss=False, icon='GROUP_UVS')
    #         icon = 'RESTRICT_RENDER_OFF' if item.active_render else 'RESTRICT_RENDER_ON'
    #         layout.prop(item, "active_render", text="", icon=icon, emboss=False)
    #     elif self.layout_type == 'GRID':
    #         layout.alignment = 'CENTER'
    #         layout.label(text="", icon_value=icon)
            
class NWO_AnimProps_Events(Panel):
    bl_label = "Animation Events"
    bl_idname = "NWO_PT_AnimPropsPanel_Events"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = "UI"
    bl_context = "Action"
    bl_parent_id = "NWO_PT_ActionDetailsPanel"

    @classmethod
    def poll(cls, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        return action_nwo.export_this

    def draw(self, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        layout = self.layout
        row = layout.row()

        # layout.template_list("NWO_UL_AnimProps_Events", "", action_nwo, "animation_events", action_nwo, 'animation_events_index')
        row.template_list("NWO_UL_AnimProps_Events", "", action_nwo, "animation_events", action_nwo, "animation_events_index", rows=2)

        col = row.column(align=True)
        col.operator("animation_event.list_add", icon='ADD', text="")
        col.operator("animation_event.list_remove", icon='REMOVE', text="")
        
        if len(action_nwo.animation_events) > 0:
            item = action_nwo.animation_events[action_nwo.animation_events_index]
            # row = layout.row()
            # row.prop(item, "name") # debug only
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            row = col.row()
            row.prop(item, "multi_frame", expand=True)
            col.prop(item, "frame_frame")
            if item.multi_frame == 'range':
                col.prop(item, "frame_range")
            col.prop(item, "frame_name")
            col.prop(item, "event_type")
            if item.event_type == '_connected_geometry_animation_event_type_wrinkle_map':
                col.prop(item, "wrinkle_map_face_region")
                col.prop(item, "wrinkle_map_effect")
            elif item.event_type == '_connected_geometry_animation_event_type_footstep':
                col.prop(item, "footstep_type")
                col.prop(item, "footstep_effect")
            elif item.event_type in ('_connected_geometry_animation_event_type_ik_active', '_connected_geometry_animation_event_type_ik_passive'):
                col.prop(item, "ik_chain")
                col.prop(item, "ik_active_tag")
                col.prop(item, "ik_target_tag")
                col.prop(item, "ik_target_marker")
                col.prop(item, "ik_target_usage")
                col.prop(item, "ik_proxy_target_id")
                col.prop(item, "ik_pole_vector_id")
                col.prop(item, "ik_effector_id")
            elif item.event_type == '_connected_geometry_animation_event_type_cinematic_effect':
                col.prop(item, "cinematic_effect_tag")
                col.prop(item, "cinematic_effect_effect")
                col.prop(item, "cinematic_effect_marker")
            elif item.event_type == '_connected_geometry_animation_event_type_object_function':
                col.prop(item, "object_function_name")
                col.prop(item, "object_function_effect")
            elif item.event_type == '_connected_geometry_animation_event_type_frame':
                col.prop(item, "frame_trigger")
            elif item.event_type == '_connected_geometry_animation_event_type_import':
                col.prop(item, "import_frame")
                col.prop(item, "import_name")
            elif item.event_type == '_connected_geometry_animation_event_type_text':
                col.prop(item, "text")

class NWO_List_Add_Animation_Event(Operator):
    """ Add an Item to the UIList"""
    bl_idname = "animation_event.list_add"
    bl_label = "Add"
    bl_description = "Add a new animation event to the list."
    filename_ext = ''
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return context.active_object.animation_data.action
    
    def execute(self, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        event = action_nwo.animation_events.add()
        event.frame_frame = context.scene.frame_current
        event.name = self.name
        event.event_id = random.randint(-2147483647, 2147483647)

        action_nwo.animation_event_index = len(action_nwo.animation_events) - 1
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)

        return {'RUNNING_MODAL'}

class NWO_List_Remove_Animation_Event(Operator):
    """ Remove an Item from the UIList"""
    bl_idname = "animation_event.list_remove"
    bl_label = "Remove"
    bl_description = "Remove an animation event from the list."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        return action_nwo and len(action_nwo.animation_events) > 0
    
    def execute(self, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        index = action_nwo.animation_events_index
        action_nwo.animation_events.remove(index)
        return {'FINISHED'}

class NWO_Animation_ListItems(PropertyGroup):
    event_id: IntProperty()
    
    multi_frame: EnumProperty(
        name='Usage',
        description='Toggle whether this animation event should trigger on a single frame, or occur over a range',
        default='single',
        options=set(),
        items= [('single', 'Single', ''), ('range', 'Range', '')]
    )

    frame_range: IntProperty(
        name='Frame Range',
        description='Enter the number of frames this event should last',
        default=1,
        min=1,
        soft_max=10
    )

    name: StringProperty(
        name="Event Name",
        default='new_event',
    )

    event_type: EnumProperty(
        name='Type',
        default='_connected_geometry_animation_event_type_frame',
        options=set(),
        items = [
            ('_connected_geometry_animation_event_type_custom', 'Custom', ''),
            ('_connected_geometry_animation_event_type_loop', 'Loop', ''),
            ('_connected_geometry_animation_event_type_sound', 'Sound', ''),
            ('_connected_geometry_animation_event_type_effect', 'Effect', ''),
            ('_connected_geometry_animation_event_type_ik_active', 'IK Active', ''),
            ('_connected_geometry_animation_event_type_ik_passive', 'IK Passive', ''),
            ('_connected_geometry_animation_event_type_text', 'Text', ''),
            ('_connected_geometry_animation_event_type_wrinkle_map', 'Wrinkle Map', ''),
            ('_connected_geometry_animation_event_type_footstep', 'Footstep', ''),
            ('_connected_geometry_animation_event_type_cinematic_effect', 'Cinematic Effect', ''),
            ('_connected_geometry_animation_event_type_object_function', 'Object Function', ''),
            ('_connected_geometry_animation_event_type_frame', 'Frame', ''),
            ('_connected_geometry_animation_event_type_import', 'Import', ''),
        ]
    )

    frame_start: FloatProperty(
        name='Frame Start',
        default=0,
        options=set(),
    )

    frame_end: FloatProperty(
        name='Frame End',
        default=0,
        options=set(),
    )

    wrinkle_map_face_region: StringProperty(
        name='Wrinkle Map Face Region',
        default='',
        options=set(),
    )

    wrinkle_map_effect: IntProperty(
        name='Wrinkle Map Effect',
        default=0,
        options=set(),
    )

    footstep_type: StringProperty(
        name='Footstep Type',
        default='',
        options=set(),
    )

    footstep_effect: IntProperty(
        name='Footstep Effect',
        default=0,
        options=set(),
    )

    ik_chain: StringProperty(
        name='IK Chain',
        default='',
        options=set(),
    )

    ik_active_tag: StringProperty(
        name='IK Active Tag',
        default='',
        options=set(),
    )

    ik_target_tag: StringProperty(
        name='IK Target Tag',
        default='',
        options=set(),
    )

    ik_target_marker: StringProperty(
        name='IK Target Marker',
        default='',
        options=set(),
    )

    ik_target_usage: StringProperty(
        name='IK Target Usage',
        default='',
        options=set(),
    )

    ik_proxy_target_id: IntProperty(
        name='IK Proxy Target ID',
        default=0,
        options=set(),
    )

    ik_pole_vector_id: IntProperty(
        name='IK Pole Vector ID',
        default=0,
        options=set(),
    )

    ik_effector_id: IntProperty(
        name='IK Effector ID',
        default=0,
        options=set(),
    )

    cinematic_effect_tag: StringProperty(
        name='Cinematic Effect Tag',
        default='',
        options=set(),
    )

    cinematic_effect_effect: IntProperty(
        name='Cinematic Effect',
        default=0,
        options=set(),
    )

    cinematic_effect_marker: StringProperty(
        name='Cinematic Effect Marker',
        default='',
        options=set(),
    )

    object_function_name: StringProperty(
        name='Object Function Name',
        default='',
        options=set(),
    )

    object_function_effect: IntProperty(
        name='Object Function Effect',
        default=0,
        options=set(),
    )

    frame_frame: IntProperty(
        name='Event Frame',
        default=0,
        options=set(),
    )

    frame_name: EnumProperty(
        name='Frame Name',
        default='primary keyframe',
        options=set(),
        items = [
                ('none', 'None', ''),
                ('primary keyframe', 'Primary Keyframe', ''),
                ('secondary keyframe', 'Secondary Keyframe', ''),
                ('tertiary keyframe', 'Tertiary Keyframe', ''),
                ('left foot', 'Left Foot', ''),
                ('right foot', 'Right Foot', ''),
                ('allow interruption', 'Allow Interruption', ''),
                ('do not allow interruption', 'Do Not Allow Interruption', ''),
                ('both-feet shuffle', 'Both-Feet Shuffle', ''),
                ('body impact', 'Body Impact', ''),
                ('left foot lock', 'Left Foot Lock', ''),
                ('left foot unlock', 'Left Foot Unlock', ''),
                ('right foot lock', 'Right Foot Lock', ''),
                ('right foot unlock', 'Right Foot Unlock', ''),
                ('blend range marker', 'Blend Range Marker', ''),
                ('stride expansion', 'Stride Expansion', ''),
                ('stride contraction', 'Stride Contraction', ''),
                ('ragdoll keyframe', 'Ragdoll Keyframe', ''),
                ('drop weapon keyframe', 'Drop Weapon Keyframe', ''),
                ('match a', 'Match A', ''),
                ('match b', 'Match B', ''),
                ('match c', 'Match C', ''),
                ('match d', 'Match D', ''),
                ('jetpack closed', 'Jetpack Closed', ''),
                ('jetpack open', 'Jetpack Open', ''),
                ('sound event', 'Sound Event', ''),
                ('effect event', 'Effect Event', ''),
            ]
    )

    frame_trigger: BoolProperty(
        name='Frame Trigger',
        default=False,
        options=set(),
    )

    import_frame: IntProperty(
        name='Import Frame',
        default=0,
        options=set(),
    )

    import_name: StringProperty(
        name='Import Name',
        default='',
        options=set(),
    )

    text: StringProperty(
        name='Text',
        default='',
        options=set(),
    )

class NWO_ActionPropertiesGroup(PropertyGroup):
    def update_name_override(self, context):
        if self.name_override.rpartition('.')[2] != self.animation_type:
            match self.name_override.rpartition('.')[2].upper():
                case 'JMA':
                    self.animation_type = 'JMA'
                case 'JMT':
                    self.animation_type = 'JMT'
                case 'JMZ':
                    self.animation_type = 'JMZ'
                case 'JMV':
                    self.animation_type = 'JMV'
                case 'JMO':
                    self.animation_type = 'JMO'
                case 'JMOX':
                    self.animation_type = 'JMOX'
                case 'JMR':
                    self.animation_type = 'JMR'
                case 'JMRX':
                    self.animation_type = 'JMRX'
                case _:
                    self.animation_type = 'JMM'

    name_override: StringProperty(
        name = "Name Override",
        update=update_name_override,
        description = "Overrides the action name when setting exported animation name. Use this if the action field is too short for your animation name",
        default = '',
        )
    
    export_this : BoolProperty(
        name = 'Export',
        default=True,
        description="Controls whether this animation is exported or not",
        options=set(),
    )
    
    def update_animation_type(self, context):
        action_name = str(self.id_data.name) if self.id_data.nwo.name_override == '' else str(self.id_data.nwo.name_override)
        action_name = dot_partition(action_name)
        action_name = f'{action_name}.{self.animation_type}'
        if self.id_data.nwo.name_override != '':
            self.id_data.nwo.name_override = action_name
        else:
            if self.id_data.name.rpartition('.')[0] != '':
                self.id_data.name = action_name
        # Set the name override if the action name is out of characters
        if dot_partition(action_name) != dot_partition(self.id_data.name) and self.id_data.nwo.name_override == '':
            self.id_data.nwo.name_override = action_name
            self.id_data.name = dot_partition(self.id_data.name)
    
    animation_type: EnumProperty(
        name = "Type",
        update=update_animation_type,
        description = "Set the type of Halo animation you want this action to be.",
        default = 'JMM',
        items = [   ('JMM', "Base (JMM)", "Full skeleton animation. Has no physics movement. Examples: enter, exit, idle"),
                    ('JMA', "Base - Horizontal Movement (JMA)", "Full skeleton animation with physics movement on the X-Y plane. Examples: move_front, walk_left, h_ping front gut"),
                    ('JMT', "Base - Yaw Rotation (JMT)", "Full skeleton animation with physics rotation on the yaw axis. Examples: turn_left, turn_right"),
                    ('JMZ', "Base - Full Movement / Yaw Rotation (JMZ)", "Full skeleton animation with physics movement on the X-Y-Z axis and yaw rotation. Examples: climb, jump_down_long, jump_forward_short"),
                    ('JMV', "Base - Full Movement & Rotation (JMV)", "Full skeleton animation for vehicles. Has full roll / pitch / yaw rotation and angular velocity. Do not use for bipeds. Examples: vehicle roll_left, vehicle roll_right_short"),
                    ('JMO', "Overlay - Keyframe (JMO)", "Overlays animation on top of others. Use on animations that aren't controlled by a function. Use this type for animating device_machines. Examples: fire_1, reload_1, device position"),
                    ('JMOX', "Overlay - Pose (JMOX)", "Overlays animation on top of others. Use on animations that rely on functions like aiming / steering / accelaration. These animations require pitch & yaw bones to be animated and defined in the animation graph. Examples: aim_still_up, acc_up_down, vehicle steering"),
                    ('JMR', "Replacement - Object Space (JMR)", "Replaces animation only on the bones animated in the replacement animation. Examples: combat pistol hp melee_strike_2, revenant_p sword put_away"), 
                    ('JMRX', "Replacement - Local Space (JMRX)", "Replaces animation only on the bones animated in the replacement animation. Examples: combat pistol any grip, combat rifle sr grip"), 
                ]
    )

    animation_events: CollectionProperty(
        type=NWO_Animation_ListItems,
    )

    animation_events_index: IntProperty(
        name='Index for Animation Event',
        default=0,
        min=0,
    )

# FACE LEVEL PROPERTIES

class NWO_UL_FaceMapProps(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if item:
                layout.prop(item, "name", text="", emboss=False, icon_value=495)
            else:
                layout.label(text="", translate=False, icon_value=icon)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class NWO_FaceMapProps(Panel):
    bl_label = "Face Properties"
    bl_idname = "NWO_PT_MeshFaceDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_parent_id = "NWO_PT_ObjectDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object
        valid_mesh_types = ('_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_render', '_connected_geometry_mesh_type_poop')
        return ob and ob.nwo.export_this and ob.type == 'MESH' and ob.nwo.object_type_ui == '_connected_geometry_object_type_mesh' and ob.nwo.mesh_type_ui in valid_mesh_types
    
    def draw_header(self, context):
        self.layout.label(text='')
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        ob = context.object
        ob_nwo = ob.nwo
        ob_nwo_face = ob.nwo_face
        is_poop = ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop'
    
        # Master Instance button since facemaps aren't stored in mesh data
        if is_linked(ob):
            row = layout.row()
            if ob.data.nwo.master_instance == ob:
                row.label(text=f"Object is the Master Instance for mesh: {ob.data.name}")
            else:
                row.operator("nwo.master_instance")
                row = layout.row()
                row.label(text=f"Object is Child Instance for mesh: {ob.data.name}")

        if is_poop:
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            op_bullet_collision = True
            op_player_collision = True
            op_cookie_cutter = True
            for item in ob_nwo_face.face_props:
                if item.instanced_collision_override:
                    op_bullet_collision = False
                    break
            for item in ob_nwo_face.face_props:
                if item.instanced_physics_override:
                    op_player_collision = False
                    break
            for item in ob_nwo_face.face_props:
                if item.cookie_cutter_override:
                    op_cookie_cutter = False
                    break
            
            row = col.grid_flow()
            if op_bullet_collision:
                row.operator("nwo_face.add_face_property_new", text="Collision", icon='ADD').options = "instanced_collision"
            if op_player_collision:
                row.operator("nwo_face.add_face_property_new", text="Physics", icon='ADD').options = "instanced_physics"
            if op_cookie_cutter:
                row.operator("nwo_face.add_face_property_new", text="Cookie Cutter", icon='ADD').options = "cookie_cutter"

        if len(ob.face_maps) <= 0:
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            col.scale_y = 1.3
            col.menu(NWO_FacePropAddMenuNew.bl_idname, text='New Face Property', icon='ADD')
        else:

            facemap = ob.face_maps.active

            rows = 2
            if facemap:
                rows = 5

            row = layout.row()
            row.template_list("MESH_UL_fmaps", "", ob, "face_maps", ob.face_maps, "active_index", rows=rows)

            col = row.column(align=True)
            col.menu(NWO_FacePropAddMenuNew.bl_idname, text='', icon='ADD')
            col.operator("object.face_map_remove", icon='REMOVE', text="")

            col.separator()

            col.operator("nwo_face.edit_face_map", text='', icon='EDITMODE_HLT')

            if facemap:
                col.separator()
                col.operator("object.face_map_move", icon='TRIA_UP', text="").direction = 'UP'
                col.operator("object.face_map_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            if ob.face_maps and (ob.mode == 'EDIT' and ob.type == 'MESH'):
                row = layout.row()

                sub = row.row(align=True)
                sub.operator("object.face_map_assign", text="Assign")
                sub.operator("object.face_map_remove_from", text="Remove")

                sub = row.row(align=True)
                sub.operator("object.face_map_select", text="Select")
                sub.operator("object.face_map_deselect", text="Deselect")
            
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            row = col.row()
            if facemap:
                item = ob_nwo_face.face_props[ob.face_maps.active.name]
                # row.prop(item, 'name')
                # if not (item.region_name_override and item.face_type_override and item.face_mode_override and item.face_sides_override and item.face_draw_distance_override and item.texcoord_usage_override
                #          and item.face_global_material_override and item.ladder_override and item.slip_surface_override and item.decal_offset_override and item.group_transparents_by_plane_override
                #            and item.no_shadow_override and item.precise_position_override and item.no_lightmap_override and item.no_pvs_override
                #         ):

                if (is_poop and (item.instanced_collision_override or item.instanced_physics_override or item.cookie_cutter_override)):
                    if item.instanced_collision_override:
                        col.label(text="Current FaceMap is used for this mesh's bullet collision")
                    if item.instanced_physics_override:
                        col.label(text="Current FaceMap is used for this mesh's player collision")
                    if item.cookie_cutter_override:
                        col.label(text="Current FaceMap is used for this mesh's cookie cutter")

                else:

                    if item.instanced_collision_override:
                        row = col.row()
                        row.prop(item, "instanced_collision")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'instanced_collision'
                    if item.instanced_physics_override:
                        row = col.row()
                        row.prop(item, "instanced_physics")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'instanced_physics'
                    if item.cookie_cutter_override:
                        row = col.row()
                        row.prop(item, "cookie_cutter")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'cookie_cutter'
                    if item.region_name_override:
                        row = col.row()
                        row.prop(item, "region_name")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'region'
                    if item.face_type_override:
                        row = col.row()
                        row.prop(item, "face_type")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'face_type'
                        if item.face_type == '_connected_geometry_face_type_sky':
                            row = col.row()
                            row.prop(item, "sky_permutation_index")
                    if item.face_mode_override:
                        row = col.row()
                        row.prop(item, "face_mode")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'face_mode'
                    if item.face_sides_override:
                        row = col.row()
                        row.prop(item, "face_sides")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'face_sides'
                    if item.face_draw_distance_override:
                        row = col.row()
                        row.prop(item, "face_draw_distance")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'face_draw_distance'
                    if item.texcoord_usage_override:
                        row = col.row()
                        row.prop(item, 'texcoord_usage')
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'texcoord_usage'
                    if item.face_global_material_override:
                        row = col.row()
                        row.prop(item, "face_global_material")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'face_global_material'
                    if item.ladder_override:
                        row = col.row()
                        row.prop(item, "ladder")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'ladder'
                    if item.slip_surface_override:
                        row = col.row()
                        row.prop(item, "slip_surface")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'slip_surface'
                    if item.decal_offset_override:
                        row = col.row()
                        row.prop(item, "decal_offset")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'decal_offset'
                    if item.group_transparents_by_plane_override:
                        row = col.row()
                        row.prop(item, "group_transparents_by_plane")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'group_transparents_by_plane'
                    if item.no_shadow_override:
                        row = col.row()
                        row.prop(item, "no_shadow")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'no_shadow'
                    if item.precise_position_override:
                        row = col.row()
                        row.prop(item, "precise_position")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'precise_position'
                    if item.no_lightmap_override:
                        row = col.row()
                        row.prop(item, "no_lightmap")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'no_lightmap'
                    if item.no_pvs_override:
                        row = col.row()
                        row.prop(item, "no_pvs")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'no_pvs'
                    # lightmap
                    if item.lightmap_additive_transparency_override:
                        row = col.row()
                        row.prop(item, "lightmap_additive_transparency")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_additive_transparency'
                    if item.lightmap_resolution_scale_override:
                        row = col.row()
                        row.prop(item, "lightmap_resolution_scale")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_resolution_scale'
                    if item.lightmap_type_override:
                        row = col.row()
                        row.prop(item, "lightmap_type")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_type'
                    if item.lightmap_analytical_bounce_modifier_override:
                        row = col.row()
                        row.prop(item, "lightmap_analytical_bounce_modifier")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_analytical_bounce_modifier'
                    if item.lightmap_general_bounce_modifier_override:
                        row = col.row()
                        row.prop(item, "lightmap_general_bounce_modifier")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_general_bounce_modifier'
                    if item.lightmap_translucency_tint_color_override:
                        row = col.row()
                        row.prop(item, "lightmap_translucency_tint_color")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_translucency_tint_color'
                    if item.lightmap_lighting_from_both_sides_override:
                        row = col.row()
                        row.prop(item, "lightmap_lighting_from_both_sides")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'lightmap_lighting_from_both_sides'
                    # material lighting
                    if item.material_lighting_attenuation_override:
                        row = col.row()
                        row.prop(item, "material_lighting_attenuation_falloff")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_attenuation'
                        row = col.row()
                        row.prop(item, "material_lighting_attenuation_cutoff")
                    if item.material_lighting_emissive_focus_override:
                        row = col.row()
                        row.prop(item, "material_lighting_emissive_focus")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_emissive_focus'
                    if item.material_lighting_emissive_color_override:
                        row = col.row()
                        row.prop(item, "material_lighting_emissive_color")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_emissive_color'
                    if item.material_lighting_emissive_per_unit_override:
                        row = col.row()
                        row.prop(item, "material_lighting_emissive_per_unit")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_emissive_per_unit'
                    if item.material_lighting_emissive_power_override:
                        row = col.row()
                        row.prop(item, "material_lighting_emissive_power")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_emissive_power'
                    if item.material_lighting_emissive_quality_override:
                        row = col.row()
                        row.prop(item, "material_lighting_emissive_quality")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_emissive_quality'
                    if item.material_lighting_use_shader_gel_override:
                        row = col.row()
                        row.prop(item, "material_lighting_use_shader_gel")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_use_shader_gel'
                    if item.material_lighting_bounce_ratio_override:
                        row = col.row()
                        row.prop(item, "material_lighting_bounce_ratio")
                        row.operator("nwo_face.remove_face_property", text='', icon='X').options = 'material_lighting_bounce_ratio'

                    col.menu(NWO_FacePropAddMenu.bl_idname, text='', icon='PLUS')

def toggle_override(context, option, bool_var):
    ob = context.object
    ob_nwo_face = ob.nwo_face
    try:
        item = ob_nwo_face.face_props[ob.face_maps.active.name]
    except:
        item = ob_nwo_face.face_props[ob.face_maps.active_index]
        
    match option:
        case 'region':
            item.region_name_override = bool_var
        case 'face_type':
            item.face_type_override = bool_var
        case 'face_mode':
            item.face_mode_override = bool_var
        case 'face_sides':
            item.face_sides_override = bool_var
        case '_connected_geometry_face_type_sky':
            item.face_type_override = bool_var
            item.face_type = '_connected_geometry_face_type_sky'
        case '_connected_geometry_face_type_seam_sealer':
            item.face_type_override = bool_var
            item.face_type = '_connected_geometry_face_type_seam_sealer'
        case '_connected_geometry_face_mode_render_only':
            item.face_mode_override = bool_var
            item.face_mode = '_connected_geometry_face_mode_render_only'
        case '_connected_geometry_face_mode_collision_only':
            item.face_mode_override = bool_var
            item.face_mode = '_connected_geometry_face_mode_collision_only'
        case '_connected_geometry_face_mode_sphere_collision_only':
            item.face_mode_override = bool_var
            item.face_mode = '_connected_geometry_face_mode_sphere_collision_only'
        case '_connected_geometry_face_mode_shadow_only':
            item.face_mode_override = bool_var
            item.face_mode = '_connected_geometry_face_mode_shadow_only'
        case '_connected_geometry_face_mode_lightmap_only':
            item.face_mode_override = bool_var
            item.face_mode = '_connected_geometry_face_mode_lightmap_only'
        case '_connected_geometry_face_mode_breakable':
            item.face_mode_override = bool_var
            item.face_mode = '_connected_geometry_face_mode_breakable'
        case '_connected_geometry_face_sides_one_sided_transparent':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_one_sided_transparent'
        case '_connected_geometry_face_sides_two_sided':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_two_sided'
        case '_connected_geometry_face_sides_two_sided_transparent':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_two_sided_transparent'
        case '_connected_geometry_face_sides_mirror':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_mirror'
        case '_connected_geometry_face_sides_mirror_transparent':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_mirror_transparent'
        case '_connected_geometry_face_sides_keep':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_keep'
        case '_connected_geometry_face_sides_keep_transparent':
            item.face_sides_override = bool_var
            item.face_sides = '_connected_geometry_face_sides_keep_transparent'
        case 'face_draw_distance':
            item.face_draw_distance_override = bool_var
        case 'texcoord_usage':
            item.texcoord_usage_override = bool_var
        case 'face_global_material':
            item.face_global_material_override = bool_var
        case 'ladder':
            item.ladder_override = bool_var
        case 'slip_surface':
            item.slip_surface_override = bool_var
        case 'decal_offset':
            item.decal_offset_override = bool_var
        case 'group_transparents_by_plane':
            item.group_transparents_by_plane_override = bool_var
        case 'no_shadow':
            item.no_shadow_override = bool_var
        case 'precise_position':
            item.precise_position_override = bool_var
        case 'no_lightmap':
            item.no_lightmap_override = bool_var
        case 'no_pvs':
            item.no_pvs_override = bool_var
        # instances
        case 'instanced_collision':
            item.instanced_collision_override = bool_var
        case 'instanced_physics':
            item.instanced_physics_override = bool_var
        case 'cookie_cutter':
            item.cookie_cutter_override = bool_var
        # lightmap
        case 'lightmap_additive_transparency':
            item.lightmap_additive_transparency_override = bool_var
        case 'lightmap_resolution_scale':
            item.lightmap_resolution_scale_override = bool_var
        case 'lightmap_type':
            item.lightmap_type_override = bool_var
        case 'lightmap_analytical_bounce_modifier':
            item.lightmap_analytical_bounce_modifier_override = bool_var
        case 'lightmap_general_bounce_modifier':
            item.lightmap_general_bounce_modifier_override = bool_var
        case 'lightmap_translucency_tint_color':
            item.lightmap_translucency_tint_color_override = bool_var
        case 'lightmap_lighting_from_both_sides':
            item.lightmap_lighting_from_both_sides_override = bool_var
        # material lighting
        case 'material_lighting_attenuation':
            item.material_lighting_attenuation_override = bool_var
        case 'material_lighting_emissive_focus':
            item.material_lighting_emissive_focus_override = bool_var
        case 'material_lighting_emissive_color':
            item.material_lighting_emissive_color_override = bool_var
        case 'material_lighting_emissive_per_unit':
            item.material_lighting_emissive_per_unit_override = bool_var
        case 'material_lighting_emissive_power':
            item.material_lighting_emissive_power_override = bool_var
        case 'material_lighting_emissive_quality':
            item.material_lighting_emissive_quality_override = bool_var
        case 'material_lighting_use_shader_gel':
            item.material_lighting_use_shader_gel_override = bool_var
        case 'material_lighting_bounce_ratio':
            item.material_lighting_bounce_ratio_override = bool_var

class NWO_FacePropAddMenu(Menu):
    bl_label = "Add Face Property"
    bl_idname = "NWO_MT_FacePropAdd"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        ob_nwo = ob.nwo
        if poll_ui(('MODEL', 'SKY')):
            layout.operator("nwo_face.add_face_property", text='Region Override').options = 'region'
        if ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_collision' or ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_physics' or ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop' or (ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_default' and poll_ui('SCENARIO')):
            layout.operator("nwo_face.add_face_property", text='Global Material Override').options = 'face_global_material'
        if poll_ui(('MODEL', 'SKY', 'DECORATOR SET')):
            layout.operator("nwo_face.add_face_property", text='Precise').options = 'precise_position'
            layout.operator_menu_enum("nwo_face.add_face_property_face_sides",
                                    property="options",
                                    text="Sides",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_misc",
                                    property="options",
                                    text="Other",
                                    )

        if poll_ui(('SCENARIO', 'PREFAB')):
            layout.operator_menu_enum("nwo_face.add_face_property_face_sides",
                                    property="options",
                                    text="Sides",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_face_type",
                                    property="options",
                                    text="Type",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_face_mode",
                                    property="options",
                                    text="Mode",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_flags",
                                    property="options",
                                    text="Flags",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_lightmap",
                                    property="options",
                                    text="Lightmap",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_material_lighting",
                                    property="options",
                                    text="Emissive",
                                    )

class NWO_FacePropAddMenuNew(Menu):
    bl_label = "Add Face Property"
    bl_idname = "NWO_MT_FacePropAddNew"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        ob_nwo = ob.nwo
        if poll_ui(('MODEL', 'SKY')):
            layout.operator("nwo_face.add_face_property_new", text='Region Override').options = 'region'
        if ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_collision' or ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_physics' or ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop' or (ob_nwo.mesh_type_ui == '_connected_geometry_mesh_type_default' and poll_ui('SCENARIO')):
            layout.operator("nwo_face.add_face_property_new", text='Global Material Override').options = 'face_global_material'
        if poll_ui(('MODEL', 'SKY', 'DECORATOR SET')):
            layout.operator("nwo_face.add_face_property_new", text='Precise').options = 'precise_position'
            layout.operator_menu_enum("nwo_face.add_face_property_face_sides_new",
                                    property="options",
                                    text="Sides",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_misc_new",
                                    property="options",
                                    text="Other",
                                    )

        if poll_ui(('SCENARIO', 'PREFAB')):
            layout.operator_menu_enum("nwo_face.add_face_property_face_sides_new",
                                    property="options",
                                    text="Sides",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_face_type_new",
                                    property="options",
                                    text="Type",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_face_mode_new",
                                    property="options",
                                    text="Mode",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_flags_new",
                                    property="options",
                                    text="Flags",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_lightmap_new",
                                    property="options",
                                    text="Lightmap",
                                    )
            layout.operator_menu_enum("nwo_face.add_face_property_material_lighting_new",
                                    property="options",
                                    text="Emissive",
                                    )
            

            
class NWO_MasterInstance(Operator):
    """Sets the current object as the master instance for all linked objects. Linked objects will use this objects face properties"""
    bl_idname = "nwo.master_instance"
    bl_label = "Set Master Instance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT') and is_linked(context.object)
    
    def execute(self, context):
        ob = context.object

        # Set this object to the master instance
        ob.data.nwo.master_instance = ob

        return {'FINISHED'}

class NWO_FaceDefaultsToggle(Operator):
    """Toggles the default Face Properties display"""
    bl_idname = "nwo_face.toggle_defaults"
    bl_label = "Toggle Defaults"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')

    def execute(self, context):
        
        context.object.nwo_face.toggle_face_defaults = not context.object.nwo_face.toggle_face_defaults

        return {'FINISHED'}

class NWO_FaceMapAdd(Operator):
    """Adds a facemap and assigns all faces to it"""
    bl_idname = "nwo_face.add_face_map"
    bl_label = "Add Face Properties"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')

    def execute(self, context):
        ob = context.object
        bpy.ops.object.face_map_add()
        ob.face_maps[ob.face_maps.active_index].name = 'default'

        return {'FINISHED'}
    
class NWO_EditMode(Operator):
    """Toggles Edit Mode for face map editing"""
    bl_idname = "nwo_face.edit_face_map"
    bl_label = "Enter Edit Mode"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=True)

        return {'FINISHED'}

class NWO_FacePropAdd(Operator):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property"
    bl_label = "Add"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')
    
    new : BoolProperty()

    options: EnumProperty(
        default="region",
        items=[
        ('region', 'Region', ''),
        ('face_global_material', 'Global Material', ''),
        ('precise_position', 'Precise Position', ''),
        ('instanced_collision', 'Bullet Collision', ''),
        ('instanced_physics', 'Player Collision', ''),
        ('cookie_cutter', 'Cookie Cutter', ''),
        ]
        )

    def execute(self, context):
        ob = context.object
        ob_nwo_face = ob.nwo_face
        # if no face maps, make one and assign all faces to it
        if self.new:
            is_object_mode = ob.mode == 'OBJECT'
            if is_object_mode:
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                if self.options in ('instanced_collision', 'instanced_physics', 'cookie_cutter'):
                    # bpy.ops.mesh.select_all(action='DESELECT')
                    #bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
                    # new_mesh = ob.copy()
                    # new_mesh.data = ob.data.copy()
                    # context.scene.collection.objects.link(new_mesh)
                    # set_active_object(new_mesh)
                    #bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                    bpy.ops.mesh.select_all(action='SELECT')
                    # bpy.ops.object.face_map_add()
                    # bpy.ops.object.face_map_assign()
                    # fm_name = 'default'
                    # match self.options:
                    #     case 'instanced_collision':
                    #         fm_name = 'bullet_collision'
                    #     case 'instanced_physics':
                    #         fm_name = 'player_collision'
                    #     case 'cookie_cutter':
                    #         fm_name = 'cookie_cutter'
                    #set_active_object(ob)
                    #bpy.ops.object.join()
                    # bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                    
                else:
                    if len(ob.face_maps) < 1:
                        bpy.ops.mesh.select_all(action='SELECT')

            bpy.ops.object.face_map_add()
            bpy.ops.object.face_map_assign()
            fm_name = 'default'
            match self.options:
                case 'region':
                    fm_name = 'default'
                case 'face_global_material':
                    fm_name = 'global_material'
                case 'precise_position':
                    fm_name = 'precise'

                case '_connected_geometry_face_type_sky':
                    fm_name = 'sky'
                case '_connected_geometry_face_type_seam_sealer':
                    fm_name = 'seam_sealer'
                case '_connected_geometry_face_mode_render_only':
                    fm_name = 'render_only'
                case '_connected_geometry_face_mode_collision_only':
                    fm_name = 'collision_only'
                case '_connected_geometry_face_mode_sphere_collision_only':
                    fm_name = 'sphere_collision_only'
                case '_connected_geometry_face_mode_shadow_only':
                    fm_name = 'shadow_only'
                case '_connected_geometry_face_mode_lightmap_only':
                    fm_name = 'lightmap_only'
                case '_connected_geometry_face_mode_breakable':
                    fm_name = 'breakable'
                case '_connected_geometry_face_sides_one_sided_transparent':
                    fm_name = 'one_side_transparent'
                case '_connected_geometry_face_sides_two_sided':
                    fm_name = 'two_side'
                case '_connected_geometry_face_sides_two_sided_transparent':
                    fm_name = 'two_side_transparent'
                case '_connected_geometry_face_sides_mirror':
                    fm_name = 'mirror'
                case '_connected_geometry_face_sides_mirror_transparent':
                    fm_name = 'mirror_transparent'
                case '_connected_geometry_face_sides_keep':
                    fm_name = 'keep'
                case '_connected_geometry_face_sides_keep_transparent':
                    fm_name = 'keep_transparent'
                case 'ladder':
                    fm_name = 'ladder'
                case 'slip_surface':
                    fm_name = 'slip_surface'
                case 'decal_offset':
                    fm_name = 'decal_offset'
                case 'group_transparents_by_plane':
                    fm_name = 'group_transparents_by_plane'
                case 'no_shadow':
                    fm_name = 'no_shadow'
                case 'no_lightmap':
                    fm_name = 'no_lightmap'
                case 'no_pvs':
                    fm_name = 'no_pvs'
                case 'face_draw_distance':
                    fm_name = 'draw_distance'
                case 'texcoord_usage':
                    fm_name = 'texcoord_usage'
                # instances
                case 'instanced_collision':
                    fm_name = 'projectile_collision'
                case 'instanced_physics':
                    fm_name = 'sphere_collision'
                case 'cookie_cutter':
                    fm_name = 'cookie_cutter'
                # lightmap
                case 'lightmap_additive_transparency':
                    fm_name = 'lightmap_additive_transparency'
                case 'lightmap_resolution_scale':
                    fm_name = 'lightmap_resolution_scale'
                case 'lightmap_type':
                    fm_name = 'lightmap_type'
                case 'lightmap_analytical_bounce_modifier':
                    fm_name = 'lightmap_analytical_bounce_modifier'
                case 'lightmap_general_bounce_modifier':
                    fm_name = 'lightmap_general_bounce_modifier'
                case 'lightmap_translucency_tint_color':
                    fm_name = 'lightmap_translucency_tint_color'
                case 'lightmap_lighting_from_both_sides':
                    fm_name = 'lightmap_lighting_from_both_sides'
                # material lighting
                case 'material_lighting_attenuation':
                    fm_name = 'emissive_attenuation'
                case 'material_lighting_emissive_focus':
                    fm_name = 'emissive_focus'
                case 'material_lighting_emissive_color':
                    fm_name = 'emissive_color'
                case 'material_lighting_emissive_per_unit':
                    fm_name = 'emissive_per_unit'
                case 'material_lighting_emissive_power':
                    fm_name = 'emissive_power'
                case 'material_lighting_emissive_quality':
                    fm_name = 'emissive_quality'
                case 'material_lighting_use_shader_gel':
                    fm_name = 'emissive_use_shader_gel'
                case 'material_lighting_bounce_ratio':
                    fm_name = 'emissive_bounce_ratio'

            ob.face_maps.active.name = fm_name
            bpy.ops.uilist.entry_add(list_path="object.nwo_face.face_props", active_index_path="object.face_maps.active_index")
            if is_object_mode:
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        toggle_override(context, self.options, True)
        item = ob_nwo_face.face_props[ob.face_maps.active_index]
        item.name = ob.face_maps.active.name
        if self.options in ('region', 'face_global_material'):
            r_name = item.name.split(' ')
            if self.options == 'region':
                item.region_name = r_name[-1].lower()
            else:
                item.face_global_material = r_name[-1].lower()
        context.area.tag_redraw()

        return {'FINISHED'}

class NWO_FacePropRemove(Operator):
    """Removes a face property"""
    bl_idname = "nwo_face.remove_face_property"
    bl_label = "Remove"
    bl_options = {"REGISTER", "UNDO"}

    options: EnumProperty(
        default="region",
        items=[
        ('region', 'Region', ''),
        ('face_type', 'Face Type', ''),
        ('face_mode', 'Face Mode', ''),
        ('face_sides', 'Face Sides', ''),
        ('face_draw_distance', 'Draw Distance', ''),
        ('texcoord_usage', 'Texcord Usage', ''),
        ('face_global_material', 'Global Material', ''),
        ('ladder', 'Ladder', ''),
        ('slip_surface', 'Slip Surface', ''),
        ('decal_offset', 'Decal Offset', ''),
        ('group_transparents_by_plane', 'Group Transparents by Plane', ''),
        ('no_shadow', 'No Shadow', ''),
        ('precise_position', 'Precise Position', ''),
        ('no_lightmap', 'No Lightmap', ''),
        ('no_pvs', 'No PVS', ''),
        ('instanced_collision', 'Bullet Collision', ''),
        ('instanced_physics', 'Player Collision', ''),
        ('cookie_cutter', 'Cookie Cutter', ''),
        ('lightmap_additive_transparency', 'Transparency', ''),
        ('lightmap_resolution_scale', 'Resolution Scale', ''),
        ('lightmap_type', 'Lightmap Type', ''),
        ('lightmap_analytical_bounce_modifier', 'Analytical Light Bounce Modifier', ''),
        ('lightmap_general_bounce_modifier', 'General Light Bounce Modifier', ''),
        ('lightmap_translucency_tint_color', 'Translucency Tint Colour', ''),
        ('lightmap_lighting_from_both_sides', 'Lighting from Both Sides', ''),
        ('material_lighting_attenuation', 'Attenuation', ''),
        ('material_lighting_emissive_focus', 'Focus', ''),
        ('material_lighting_emissive_color', 'Colour', ''),
        ('material_lighting_emissive_per_unit', 'Emissive per Unit', ''),
        ('material_lighting_emissive_power', 'Power', ''),
        ('material_lighting_emissive_quality', 'Quality', ''),
        ('material_lighting_use_shader_gel', 'Use Shader Gel', ''),
        ('material_lighting_bounce_ratio', 'Lighting Bounce Ratio', ''),
        ]
        )


    def execute(self, context):
        ob = context.object
        ob_nwo_face = ob.nwo_face
        toggle_override(context, self.options, False)
        context.area.tag_redraw()

        match self.options:
            case 'instanced_collision':
                ob_nwo_face.instanced_collision = False
            case 'instanced_physics':
                ob_nwo_face.instanced_physics = False
            case 'cookie_cutter':
                ob_nwo_face.cookie_cutter = False

        return {'FINISHED'}

class NWO_FacePropAddNew(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

    # options : EnumProperty()
    
class NWO_FacePropAddFaceType(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_face_type"
    bl_label = "Add"

    options: EnumProperty(
        items=[
        ('_connected_geometry_face_type_sky', 'Sky', ''),
        ('_connected_geometry_face_type_seam_sealer', 'Seam Sealer', ''),
        ]
        )
class NWO_FacePropAddFaceTypeNew(NWO_FacePropAddFaceType):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_face_type_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )
    
class NWO_FacePropAddFaceMode(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_face_mode"
    bl_label = "Add"

    options: EnumProperty(
        items=[
        ('_connected_geometry_face_mode_render_only', 'Render Only', ''),
        ('_connected_geometry_face_mode_collision_only', 'Collision Only', ''),
        ('_connected_geometry_face_mode_sphere_collision_only', 'Sphere Collision Only', ''),
        ('_connected_geometry_face_mode_shadow_only', 'Shadow Only', ''),
        ('_connected_geometry_face_mode_lightmap_only', 'Lightmap Only', ''),
        ('_connected_geometry_face_mode_breakable', 'Breakable', ''),
        ]
        )
    
class NWO_FacePropAddFaceModeNew(NWO_FacePropAddFaceMode):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_face_mode_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

class NWO_FacePropAddFaceSides(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_face_sides"
    bl_label = "Add"

    options: EnumProperty(
        items=[
        ('_connected_geometry_face_sides_one_sided_transparent', 'Transparent', ''),
        ('_connected_geometry_face_sides_two_sided', 'Two Side', ''),
        ('_connected_geometry_face_sides_two_sided_transparent', 'Two Side Transparent', ''),
        ('_connected_geometry_face_sides_mirror', 'Mirror', ''),
        ('_connected_geometry_face_sides_mirror_transparent', 'Mirror Transparent', ''),
        ('_connected_geometry_face_sides_keep', 'Keep', ''),
        ('_connected_geometry_face_sides_keep_transparent', 'Keep Transparent', ''),
        ]
        )
    
class NWO_FacePropAddFaceSidesNew(NWO_FacePropAddFaceSides):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_face_sides_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

class NWO_FacePropAddFlags(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_flags"
    bl_label = "Add"

    options : EnumProperty(
        items=[
        ('ladder', 'Ladder', ''),
        ('slip_surface', 'Slip Surface', ''),
        ('decal_offset', 'Decal Offset', ''),
        ('group_transparents_by_plane', 'Group Transparents by Plane', ''),
        ('no_shadow', 'No Shadow', ''),
        ('no_lightmap', 'No Lightmap', ''),
        ('no_pvs', 'No PVS', ''),
        ]
    )

class NWO_FacePropAddLightmap(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_lightmap"
    bl_label = "Add"

    options : EnumProperty(
        items=[
        ('lightmap_additive_transparency', 'Transparency', ''),
        ('lightmap_resolution_scale', 'Resolution Scale', ''),
        ('lightmap_type', 'Lightmap Type', ''),
        # ('lightmap_analytical_bounce_modifier', 'Analytical Light Bounce Modifier', ''),
        # ('lightmap_general_bounce_modifier', 'General Light Bounce Modifier', ''),
        ('lightmap_translucency_tint_color', 'Translucency Tint Colour', ''),
        ('lightmap_lighting_from_both_sides', 'Lighting from Both Sides', ''),
        ]
    )

class NWO_FacePropAddMaterialLighting(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_material_lighting"
    bl_label = "Add"

    options : EnumProperty(
        items=[
        ('material_lighting_attenuation', 'Attenuation', ''),
        ('material_lighting_emissive_focus', 'Focus', ''),
        ('material_lighting_emissive_color', 'Colour', ''),
        ('material_lighting_emissive_per_unit', 'Emissive per Unit', ''),
        ('material_lighting_emissive_power', 'Power', ''),
        ('material_lighting_emissive_quality', 'Quality', ''),
        ('material_lighting_use_shader_gel', 'Use Shader Gel', ''),
        ('material_lighting_bounce_ratio', 'Lighting Bounce Ratio', ''),
        ]
    )

class NWO_FacePropAddFlagsNew(NWO_FacePropAddFlags):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_flags_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

class NWO_FacePropAddMisc(NWO_FacePropAdd):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_misc"
    bl_label = "Add"

    options : EnumProperty(
        items=[
        ('face_draw_distance', 'Draw Distance', ''),
        ('texcoord_usage', 'Texcord Usage', ''),
        ]
    )

class NWO_FacePropAddMiscNew(NWO_FacePropAddMisc):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_misc_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

class NWO_FacePropAddLightmapNew(NWO_FacePropAddLightmap):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_lightmap_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

class NWO_FacePropAddMaterialLightingNew(NWO_FacePropAddMaterialLighting):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property_material_lighting_new"
    bl_label = "Add"

    new : BoolProperty(
        default=True
    )

class NWO_FaceProperties_ListItems(PropertyGroup):

    name : StringProperty()

    face_type_override : BoolProperty()
    face_mode_override : BoolProperty()
    face_sides_override : BoolProperty()
    face_draw_distance_override : BoolProperty()
    texcoord_usage_override : BoolProperty()
    region_name_override : BoolProperty()
    is_pca_override : BoolProperty()
    face_global_material_override : BoolProperty()
    sky_permutation_index_override : BoolProperty()
    ladder_override : BoolProperty()
    slip_surface_override : BoolProperty()
    decal_offset_override : BoolProperty()
    group_transparents_by_plane_override : BoolProperty()
    no_shadow_override : BoolProperty()
    precise_position_override : BoolProperty()
    no_lightmap_override : BoolProperty()
    no_pvs_override : BoolProperty()
    # instances
    instanced_collision_override : BoolProperty()
    instanced_physics_override : BoolProperty()
    cookie_cutter_override : BoolProperty()
    # lightmap
    lightmap_additive_transparency_override : BoolProperty()
    lightmap_resolution_scale_override : BoolProperty()
    lightmap_type_override : BoolProperty()
    lightmap_analytical_bounce_modifier_override : BoolProperty()
    lightmap_general_bounce_modifier_override : BoolProperty()
    lightmap_translucency_tint_color_override : BoolProperty()
    lightmap_lighting_from_both_sides_override : BoolProperty()
    # material lighting
    material_lighting_attenuation_override : BoolProperty()
    material_lighting_emissive_focus_override : BoolProperty()
    material_lighting_emissive_color_override : BoolProperty()
    material_lighting_emissive_per_unit_override : BoolProperty()
    material_lighting_emissive_power_override : BoolProperty()
    material_lighting_emissive_quality_override : BoolProperty()
    material_lighting_use_shader_gel_override : BoolProperty()
    material_lighting_bounce_ratio_override : BoolProperty()

    face_type : EnumProperty(
        name="Face Type",
        options=set(),
        description="Sets the face type for this mesh. Note that any override shaders will override the face type selected here for relevant materials",
        items=[ 
                ('_connected_geometry_face_type_seam_sealer', "Seam Sealer", "Used on faces that will not be seen by the player, however are required to make a mesh manifold or to properly block light.  Seam sealer faces use no lightmap space.  Can also be used on render only meshes"),
                ('_connected_geometry_face_type_sky', "Sky", "Assigned faces will act as a window into the sky assigned to the level in the .scenario tag"),
               ]
        )

    face_mode : EnumProperty(
        name="Face Mode",
        options=set(),
        description="Sets face mode for this mesh",
        items=[ 
                ('_connected_geometry_face_mode_render_only', "Render Only", "Assigned faces will render in game and properly respect lighting, however they will have no collision or path finding interaction"),
                ('_connected_geometry_face_mode_collision_only', "Collision Only", "Faces set to collision only"),
                ('_connected_geometry_face_mode_sphere_collision_only', "Sphere Collision Only", "Assigned faces provide physics (player) collision only in game.  The faces will not visually render on screen or provide raycast (bullet) collision"),
                ('_connected_geometry_face_mode_shadow_only', "Shadow Only", "Faces set to only cast shadows"),
                ('_connected_geometry_face_mode_lightmap_only', "Lightmap Only", "Faces set to only be used during lightmapping. They will otherwise have no render / collision geometry"),
                ('_connected_geometry_face_mode_breakable', "Breakable", "Faces set to be breakable"),
               ]
        )

    face_sides : EnumProperty(
        name="Face Sides",
        options=set(),
        description="Sets the face sides for this mesh",
        items=[ 
                ('_connected_geometry_face_sides_one_sided_transparent', "One Sided Transparent", "Faces set to only render on one side (the direction of face normals), but also render geometry behind them"),
                ('_connected_geometry_face_sides_two_sided', "Two Sided", "Faces set to render on both sides"),
                ('_connected_geometry_face_sides_two_sided_transparent', "Two Sided Transparent", "Faces set to render on both sides and are transparent"),
                ('_connected_geometry_face_sides_mirror', "Mirror", "H4+ only"),
                ('_connected_geometry_face_sides_mirror_transparent', "Mirror Transparent", "H4+ only"),
                ('_connected_geometry_face_sides_keep', "Keep", "H4+ only"),
                ('_connected_geometry_face_sides_keep_transparent', "Keep Transparent", "H4+ only"),
               ]
        )

    face_draw_distance : EnumProperty(
        name="Face Draw Distance",
        options=set(),
        description="Controls the distance at which the assigned faces will stop rendering",
        default = "_connected_geometry_face_draw_distance_normal",
        items=[ ('_connected_geometry_face_draw_distance_normal', "Normal", ""),
                ('_connected_geometry_face_draw_distance_detail_mid', "Mid", ""),
                ('_connected_geometry_face_draw_distance_detail_close', "Close", ""),
               ]
        ) 

    texcoord_usage : EnumProperty(
        name="Texture Coordinate Usage",
        options=set(),
        description="",
        default = '_connected_material_texcoord_usage_default',
        items=[ ('_connected_material_texcoord_usage_default', "Default", ""),
                ('_connected_material_texcoord_usage_none', "None", ""),
                ('_connected_material_texcoord_usage_anisotropic', "Ansiotropic", ""),
               ]
        )

    region_name: StringProperty(
        name="Region",
        default='default',
        description="Define the name of the region these faces should be associated with",
    )

    face_global_material: StringProperty(
        name="Global Material",
        default='',
        description="Set the global material of this mesh. If the global material name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct global material response type, otherwise, the global material override can be manually defined in the .model tag",
    )

    sky_permutation_index: IntProperty(
        name="Sky Permutation Index",
        options=set(),
        description="The sky permutation index of the sky faces",
        min=0,
    )

    conveyor: BoolProperty( # UNSUPORTED
        name ="Conveyor",
        options=set(),
        description = "Enables the conveyor property",
        default = True,
        )

    ladder: BoolProperty(
        name ="Ladder",
        options=set(),
        description = "Makes faces climbable",
        default = True,
    )

    slip_surface: BoolProperty(
        name ="Slip Surface",
        options=set(),
        description = "Assigned faces will be non traversable by the player. Used to ensure the player can not climb a surface regardless of slope angle",
        default = True,
    )

    decal_offset: BoolProperty(
        name ="Decal Offset",
        options=set(),
        description = "Provides a Z bias to the faces that will not be overridden by the plane build.  If placing a face coplanar against another surface, this flag will prevent Z fighting",
        default = True,
    )

    group_transparents_by_plane: BoolProperty(
        name ="Group Transparents By Plane",
        options=set(),
        description = "Determines if objects will sort based on center point or by plane.  Provides more accurate sorting of large alpha'd objects, but is very expensive",
        default = True,
    )

    no_shadow: BoolProperty(
        name ="No Shadow",
        options=set(),
        description = "Prevents faces from casting shadows",
        default = True,
    )

    precise_position: BoolProperty(
        name ="Precise Position",
        options=set(),
        description = "Provides more accurate render and collision geometry",
        default = True,
    )

    no_lightmap: BoolProperty(
        name ="Exclude From Lightmap",
        options=set(),
        description = "",
        default = True,
    )

    no_pvs: BoolProperty(
        name ="Invisible To PVS",
        options=set(),
        description = "",
        default = True,
    )

    # INSTANCED GEOMETRY ONLY

    instanced_collision : BoolProperty(
        name="Bullet Collision",
        default=True,
    )
    instanced_physics : BoolProperty(
        name="Player Collision",
        default=True,
    )

    cookie_cutter : BoolProperty(
        name="Cookie Cutter",
        default=True,
    )

    #########

    # LIGHTMAP

    lightmap_additive_transparency: FloatVectorProperty(
        name="lightmap Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint colour will override the alpha blend settings in the shader.",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    lightmap_ignore_default_resolution_scale: BoolProperty( # SET THIS AUTOMATICALLY
        name ="Lightmap Resolution Scale",
        options=set(),
        description = "",
        default = False,
    )

    lightmap_resolution_scale: IntProperty(
        name="Lightmap Resolution Scale",
        options=set(),
        description="Determines how much texel space the faces will be given on the lightmap.  1 means less space for the faces, while 7 means more space for the faces.  The relationships can be tweaked in the .scenario tag",
        default=3,
        min=0,
        max=7,
    )

    lightmap_photon_fidelity : EnumProperty( # DONT SET THIS
        name="Photon Fidelity",
        options=set(),
        description="H4+ only",
        default = "_connected_material_lightmap_photon_fidelity_normal",
        items=[ ('_connected_material_lightmap_photon_fidelity_normal', "Normal", ""),
                ('_connected_material_lightmap_photon_fidelity_medium', "Medium", ""),
                ('_connected_material_lightmap_photon_fidelity_high', "High", ""),
                ('_connected_material_lightmap_photon_fidelity_none', "None", ""),
               ]
        )

    # Lightmap_Chart_Group: IntProperty(
    #     name="Lightmap Chart Group",
    #     options=set(),
    #     description="",
    #     default=3,
    #     min=1,
    # )

    lightmap_type : EnumProperty(
        name="Lightmap Type",
        options=set(),
        description="Sets how this should be lit while lightmapping",
        default = "_connected_material_lightmap_type_per_pixel",
        items=[ ('_connected_material_lightmap_type_per_pixel', "Per Pixel", ""),
                ('_connected_material_lightmap_type_per_vertex', "Per Vetex", ""),
               ]
        )

    lightmap_transparency_override: BoolProperty( # SET THIS AUTOMATICALLY
        name ="Lightmap Transparency Override",
        options=set(),
        description = "",
        default = False,
    )

    lightmap_analytical_bounce_modifier: FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="0 will bounce no energy.  1 will bounce full energy.  Any value greater than 1 will exaggerate the amount of bounced light.  Affects 1st bounce only",
        default=1,
        soft_max=1,
        min=0,
        subtype='FACTOR',
    )
    
    lightmap_general_bounce_modifier: FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="0 will bounce no energy.  1 will bounce full energy.  Any value greater than 1 will exaggerate the amount of bounced light.  Affects 1st bounce only",
        default=1,
        soft_max=1,
        min=0,
        subtype='FACTOR',
    )

    lightmap_translucency_tint_color: FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    lightmap_lighting_from_both_sides: BoolProperty(
        name ="Lightmap Lighting From Both Sides",
        options=set(),
        description = "",
        default = True,
    )

    # MATERIAL LIGHTING

    material_lighting_attenuation_cutoff: FloatProperty(
        name="Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops",
        min=0,
        default=200,
    ) 

    lighting_attenuation_enabled: BoolProperty( #SET AUTOMATICALLY
        name="Use Attenuation",
        options=set(),
        description="Enable / Disable use of attenuation",
        default=True,
    )

    lighting_frustum_blend: FloatProperty( # DON'T SET
        name="Frustum blend",
        options=set(),
        description="",
        min=0,
        default=0,
    )

    lighting_frustum_cutoff: FloatProperty( # DON'T SET
        name="Frustum cutoff",
        options=set(),
        description="",
        min=0,
        default=0,
    )

    lighting_frustum_falloff: FloatProperty( # DON'T SET
        name="Frustum Falloff",
        options=set(),
        description="",
        min=0,
        default=0,
    )

    material_lighting_attenuation_falloff: FloatProperty(
        name="Attenuation Falloff",
        options=set(),
        description="For use on emissive surfaces. The distance in game units at which the light intensity will begin to fall off until reaching zero at the attenuation cutoff value",
        min=0,
        default=100,
    )

    material_lighting_emissive_focus: FloatProperty(
        name="Emissive Focus",
        options=set(),
        description="Controls the spread of the light emitting from this surface. 0 will emit light in a 180 degrees hemisphere from each point, 1 will emit light nearly perpendicular to the surface",
        min=0,
        max=1,
        subtype='FACTOR',

    )

    material_lighting_emissive_color: FloatVectorProperty(
        name="Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit: BoolProperty(
        name ="Emissive Per Unit",
        options=set(),
        description = "When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default = False,
    )

    material_lighting_emissive_power: FloatProperty(
        name="Emissive Power",
        options=set(),
        description="The intensity of the emissive surface",
        min=0,
        default=2,
    )

    material_lighting_emissive_quality: FloatProperty(
        name="Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel: BoolProperty(
        name ="Use Shader Gel",
        options=set(),
        description = "",
        default = False,
    )

    material_lighting_bounce_ratio: FloatProperty(
        name="Lighting Bounce Ratio",
        options=set(),
        description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
        default=1,
        min=0,
    )

class NWO_FacePropertiesGroup(PropertyGroup):

    # INSTANCED GEOMETRY ONLY

    instanced_collision : BoolProperty(
        name="Bullet Collision",
    )
    instanced_physics : BoolProperty(
        name="Player Collision",
    )

    cookie_cutter : BoolProperty(
        name="Cookie Cutter",
    )

    #########


    toggle_face_defaults : BoolProperty()

    face_props : CollectionProperty(
        type=NWO_FaceProperties_ListItems,
    )

    face_props_index : IntProperty(
        name='Index for Face Property',
        default=0,
        min=0,
    )

    def get_face_props_hack(self):
        context = bpy.context
        if context.object.data:
            if not context.object.face_maps:
                index = 0
                for item in context.object.nwo_face.face_props:
                    context.object.nwo_face.face_props.remove(index)
                    index +=1
            elif len(context.object.face_maps) > len(context.object.nwo_face.face_props):
                bpy.ops.uilist.entry_add(list_path="object.nwo_face.face_props", active_index_path="object.face_maps.active_index")
                context.area.tag_redraw()
            elif len(context.object.face_maps) < len(context.object.nwo_face.face_props):
                face_map_names = []
                for face_map in context.object.face_maps:
                    face_map_names.append(face_map.name)
                index = 0
                for item in context.object.nwo_face.face_props:
                    if item.name not in face_map_names:
                        context.object.nwo_face.face_props.remove(index)

                    index +=1

                context.area.tag_redraw()

            elif len(context.object.face_maps) == len(context.object.nwo_face.face_props):
                item = context.object.nwo_face.face_props[context.object.face_maps.active_index]
                if context.object.face_maps.active and item.name != context.object.face_maps.active.name:
                        face_map_names = []
                        for face_map in context.object.face_maps:
                            face_map_names.append(face_map.name)
                        if item.name not in face_map_names:
                            item.name = context.object.face_maps.active.name
                            context.area.tag_redraw()
                elif context.object.face_maps.active and item.region_name_override and item.region_name not in context.object.face_maps.active.name:
                    context.object.face_maps.active.name = item.region_name
                    context.area.tag_redraw()

        return False

    face_props_hack : BoolProperty(
        get=get_face_props_hack,
    )

class NWO_MeshPropertiesGroup(PropertyGroup):
    master_instance : PointerProperty(type=bpy.types.Object)

##################################################
    
def draw_filepath(self, context):
    layout = self.layout
    row = layout.row(align=True)
    row.scale_x = 0.01
    row.scale_y = 0.01
    # this is beyond hacky... and I'm not proud... but it works!
    row.prop(context.scene.nwo_global, 'temp_file_watcher')
    if context.object:
        row.prop(context.object.nwo_face, 'face_props_hack')

classeshalo = (
    NWO_ScenePropertiesGroup,
    NWO_FacePropAddNew,
    NWO_FacePropAddFaceTypeNew,
    NWO_FacePropAddFaceModeNew,
    NWO_FacePropAddFaceSidesNew,
    NWO_FacePropAddFlagsNew,
    NWO_FacePropAddMiscNew,
    NWO_FacePropAddLightmapNew,
    NWO_FacePropAddMaterialLightingNew,
    NWO_LightPropsCycles,
    NWO_SceneProps,
    NWO_SetUnitScale,
    NWO_AssetMaker,
    NWO_GameInstancePath,
    NWO_FogPath,
    NWO_EffectPath,
    NWO_LightConePath,
    NWO_LightConeCurvePath,
    NWO_LightTagPath,
    NWO_LightShaderPath,
    NWO_LightGelPath,
    NWO_LensFlarePath,
    NWO_ShaderPath,
    NWO_ObjectProps,
    # NWO_ObjectMeshProps,
    # NWO_ObjectMarkerProps,
    NWO_MaterialProps,
    NWO_ShaderProps,
    NWO_MaterialOpenTag,
    NWO_ObjectPropertiesGroup,
    NWO_LightPropertiesGroup,
    NWO_MaterialPropertiesGroup,
    NWO_LightProps,
    NWO_BoneProps,
    NWO_BonePropertiesGroup,
    NWO_ActionProps,
    NWO_UL_AnimProps_Events,
    NWO_AnimProps_Events,
    NWO_List_Add_Animation_Event,
    NWO_List_Remove_Animation_Event,
    NWO_Animation_ListItems,
    NWO_ActionPropertiesGroup,
    NWO_UL_FaceMapProps,
    NWO_FacePropAddFaceType,
    NWO_FacePropAddFaceMode,
    NWO_FacePropAddFaceSides,
    NWO_FacePropAddFlags,
    NWO_FacePropAddMisc,
    NWO_FacePropAddLightmap,
    NWO_FacePropAddMaterialLighting,
    NWO_FacePropAdd,
    NWO_FacePropRemove,
    NWO_FaceMapAdd,
    NWO_EditMode,
    NWO_MasterInstance,
    NWO_FaceDefaultsToggle,
    NWO_FaceProperties_ListItems,
    NWO_MeshFaceProps,
    NWO_FaceMapProps,
    # NWO_ObjectMeshMaterialLightingProps,
    # NWO_ObjectMeshLightmapProps,
    NWO_FacePropAddMenu,
    NWO_FacePropAddMenuNew,
    NWO_MeshPropertiesGroup,
    NWO_FacePropertiesGroup,
)

def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)

    bpy.types.Scene.nwo_global = PointerProperty(type=NWO_ScenePropertiesGroup, name="Halo Scene Properties", description="Set properties for your scene")
    bpy.types.Object.nwo = PointerProperty(type=NWO_ObjectPropertiesGroup, name="Halo NWO Properties", description="Set Halo Object Properties")
    bpy.types.Light.nwo = PointerProperty(type=NWO_LightPropertiesGroup, name="Halo NWO Properties", description="Set Halo Object Properties")
    bpy.types.Material.nwo = PointerProperty(type=NWO_MaterialPropertiesGroup, name="Halo NWO Properties", description="Set Halo Material Properties") 
    bpy.types.Bone.nwo = PointerProperty(type=NWO_BonePropertiesGroup, name="Halo NWO Properties", description="Set Halo Bone Properties")
    bpy.types.Action.nwo = PointerProperty(type=NWO_ActionPropertiesGroup, name="Halo NWO Properties", description="Set Halo Animation Properties")
    bpy.types.Mesh.nwo = PointerProperty(type=NWO_MeshPropertiesGroup, name="Halo Mesh Properties", description="Set Halo Properties")
    bpy.types.Object.nwo_face = PointerProperty(type=NWO_FacePropertiesGroup, name="Halo Face Properties", description="Set Halo Face Properties")
    bpy.types.TOPBAR_HT_upper_bar.prepend(draw_filepath)

def unregister():
    del bpy.types.Scene.nwo_global
    del bpy.types.Object.nwo
    del bpy.types.Light.nwo
    del bpy.types.Material.nwo
    del bpy.types.Bone.nwo
    del bpy.types.Action.nwo
    del bpy.types.Mesh.nwo
    del bpy.types.Object.nwo_face
    bpy.types.TOPBAR_HT_upper_bar.remove(draw_filepath)
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)