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
        Operator,
        Panel,
        UIList,
        PropertyGroup
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

class NWO_SceneProps(Panel):
    bl_label = "Halo Scene"
    bl_idname = "NWO_PT_ScenePropertiesPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo = scene.nwo_global
        mb_active = managed_blam_active()
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
        row = col.row()
        if mb_active:
            row.enabled = False
        row.prop(scene_nwo, "game_version", text='Game', expand=True)
        row = col.row()
        if mb_active or scene_nwo.mb_startup:
            col.prop(scene_nwo, 'mb_startup')
        col.separator()
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.set_unit_scale")
        if mb_active:
            col.label(text="ManagedBlam Active")
        elif os.path.exists(os.path.join(bpy.app.tempdir, 'blam_new.txt')):
            col.label(text="Blender Restart Required for ManagedBlam")
        else:
            col.operator("managed_blam.init", text="Initialise ManagedBlam")

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

def GameVersionWarning(self, context):
    self.layout.label(text=f"Please set your editing kit path for {context.scene.nwo_global.game_version.upper()} in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset]")

class NWO_ScenePropertiesGroup(PropertyGroup):
    def CheckEKPaths(self, context):
        if self.game_version in ('reach', 'h4', 'h2a'):
            if get_ek_path() is None or get_ek_path() == '':
                context.window_manager.popup_menu(GameVersionWarning, title="Warning", icon='ERROR')
                
    game_version: EnumProperty(
        name="Game:",
        description="What game will you be exporting for",
        default='reach',
        update=CheckEKPaths,
        items=[ ('reach', "Halo Reach", "Show properties for Halo Reach MCC"),
                ('h4', "Halo 4", "Show properties for Halo 4 MCC"),
                ('h2a', "Halo 2AMP", "Show properties for Halo 2AMP MCC"),
               ]
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
from ..utils.nwo_utils import (
    frame_prefixes,
    get_asset_info,
    managed_blam_active,
    marker_prefixes,
    run_ek_cmd,
    special_prefixes,
    boundary_surface_prefixes,
    poop_lighting_prefixes,
    poop_pathfinding_prefixes,
    poop_render_only_prefixes,
    object_prefix,
    invalid_mesh_types,
    get_prop_from_collection,
    is_design,
    get_ek_path,
    not_bungie_game,
    clean_tag_path,
    get_tags_path,
    shortest_string,
    is_marker,
    is_mesh,
    valid_animation_types,
    dot_partition,
    CheckType
)

# ------------------------------------------------------------------------
# TAG PATH BUTTONS
# ------------------------------------------------------------------------

class NWO_GameInstancePath(Operator):
    """Set the path to a game instance tag"""
    bl_idname = "nwo.game_instance_path"
    bl_label = "Find"

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
        active_object.nwo.Marker_Game_Instance_Tag_Name = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_FogPath(Operator):
    """Set the path to a fog tag"""
    bl_idname = "nwo.fog_path"
    bl_label = "Find"

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
        active_object.nwo.Fog_Appearance_Tag = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}
    
class NWO_EffectPath(Operator):
    """Set the path to an effect tag"""
    bl_idname = "nwo.effect_path"
    bl_label = "Find"

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
        active_object.nwo.Light_Tag_Override = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightShaderPath(Operator):
    """Set the path to a light shader tag"""
    bl_idname = "nwo.light_shader_path"
    bl_label = "Find"

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
        active_object.nwo.Light_Shader_Reference = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LightGelPath(Operator):
    """Set the path to a gel bitmap"""
    bl_idname = "nwo.light_gel_path"
    bl_label = "Find"

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
        active_object.nwo.Light_Gel_Reference = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_LensFlarePath(Operator):
    """Set the path to a lens flare bitmap"""
    bl_idname = "nwo.lens_flare_path"
    bl_label = "Find"

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
        active_object.nwo.Light_Lens_Flare_Reference = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_ShaderPath(Operator):
    """Set the path to a material / shader tag"""
    bl_idname = "nwo.shader_path"
    bl_label = "Find"

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
    filter = scene_nwo.filter_ui
    type = scene_nwo.asset_type

    return not filter or type in selected_types

class NWO_ObjectProps(Panel):
    bl_label = "Halo Object Properties"
    bl_idname = "NWO_PT_ObjectDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global

        return scene_nwo.game_version in ('reach','h4','h2a') and context.object.type != 'ARMATURE'  and poll_ui(('MODEL', 'SCENARIO', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'PREFAB'))
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        
        ob = context.object
        ob_nwo = ob.nwo

        col = flow.column()

        if ob.type == 'LIGHT':
            col.prop(ob_nwo, "Object_Type_Light", text='Object Type')
        elif object_prefix(ob, (marker_prefixes + frame_prefixes)) or (ob.type == 'EMPTY' and (ob.name.startswith('$') or len(ob.children) > 0)) or object_prefix(ob, special_prefixes):
            if ob.type == 'EMPTY':
                col.prop(ob_nwo, "Object_Type_No_Mesh_Locked", text='Object Type')
            else:
                col.prop(ob_nwo, "Object_Type_All_Locked", text='Object Type')
        else:
            row = col.row()
            if ob.type == 'EMPTY':
                row.prop(ob_nwo, "Object_Type_No_Mesh", text='Object Type', expand=True)
            else:
                row.prop(ob_nwo, "Object_Type_All", text='Object Type', expand=True)

        if poll_ui(('SCENARIO')):
            sub = col.row()
            if is_design(ob):
                if ob_nwo.bsp_name_locked != '':
                    sub.prop(ob_nwo, 'bsp_name_locked', text='Design Group')
                else:
                    sub.prop(ob_nwo, 'bsp_name', text='Design Group')
            else:
                if ob_nwo.bsp_name_locked != '':
                    sub.prop(ob_nwo, 'bsp_name_locked', text='BSP')
                else:
                    sub.prop(ob_nwo, 'bsp_name', text='BSP')

        if poll_ui(('MODEL', 'SCENARIO')):
            if ob_nwo.Permutation_Name_Locked != '':
                col.prop(ob_nwo, 'Permutation_Name_Locked', text='Permutation')
            else:
                col.prop(ob_nwo, 'Permutation_Name', text='Permutation')

        if CheckType.frame(ob) and not_bungie_game():
            col.prop(ob_nwo, 'is_pca')

#MESH PROPERTIES
class NWO_ObjectMeshProps(Panel):
    bl_label = "Mesh Properties"
    bl_idname = "NWO_PT_MeshDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_parent_id = "NWO_PT_ObjectDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object

        return is_mesh(ob)


    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        ob = context.active_object
        ob_nwo = ob.nwo

        col = flow.column()

        if not_bungie_game():
            if object_prefix(context.active_object, special_prefixes):
                col.prop(ob_nwo, "ObjectMesh_Type_Locked_H4", text='Mesh Type')
            else:
                col.prop(ob_nwo, "ObjectMesh_Type_H4", text='Mesh Type')
        else:
            if object_prefix(context.active_object, special_prefixes):
                col.prop(ob_nwo, "ObjectMesh_Type_Locked", text='Mesh Type')
            else:
                col.prop(ob_nwo, "ObjectMesh_Type", text='Mesh Type')

        if poll_ui(('MODEL', 'SKY')) and (CheckType.default(ob) or CheckType.collision(ob) or CheckType.physics(ob)):
            if ob_nwo.Region_Name_Locked != '':
                col.prop(ob_nwo, 'Region_Name_Locked', text='Region')
            else:
                col.prop(ob_nwo, "Region_Name", text='Region')

        if not (poll_ui('MODEL') and CheckType.default(ob)) and not (not_bungie_game() and CheckType.default(ob)) and (CheckType.default(ob) or CheckType.poop(ob) or CheckType.water_surface(ob) or CheckType.collision(ob) or CheckType.physics(ob)) and poll_ui(('MODEL', 'SCENARIO', 'PREFAB')):
            col.prop(ob_nwo, "Face_Global_Material", text='Global Material')

        if poll_ui(('DECORATOR SET')) and context.scene.nwo.asset_type == 'DECORATOR SET' and not CheckType.decorator(ob):
            col.label(text="Only the Decorator mesh type is valid for Decorator Set exports", icon='ERROR')

        elif poll_ui(('PARTICLE MODEL')) and context.scene.nwo.asset_type == 'PARTICLE MODEL' and not CheckType.default(ob):
            col.label(text="Only the render mesh type is valid for particle model exports", icon='ERROR')

        elif CheckType.boundary_surface(ob):
            if poll_ui(('SCENARIO')):
                row = col.row()
                if ob.name.startswith(boundary_surface_prefixes):
                    row.prop(ob_nwo, "Boundary_Surface_Type_Locked", text='Type', expand=True)
                else:
                    row.prop(ob_nwo, "Boundary_Surface_Type", text='Type', expand=True)
            else:
                col.label(text="Boundary Surface mesh type only valid for Scenario exports", icon='ERROR')

        elif poll_ui(('SCENARIO', 'PREFAB')) and CheckType.collision(ob) and not_bungie_game():
            col.prop(ob_nwo, "Poop_Collision_Type")

        elif CheckType.decorator(ob):
            if poll_ui(('DECORATOR SET')):
                col.prop(ob_nwo, "Decorator_Name", text='Decorator Name')
                col.prop(ob_nwo, "Decorator_LOD", text='Decorator Level of Detail')
            else:
                col.label(text="Decorator mesh type only valid for Decorator exports", icon='ERROR')

        elif CheckType.poop(ob):
            if poll_ui(('SCENARIO', 'PREFAB')):
                if not_bungie_game():
                    col.prop(ob_nwo, "Poop_Collision_Type")

                if ob.name.startswith(poop_lighting_prefixes):
                    col.prop(ob_nwo, "Poop_Lighting_Override_Locked", text='Lighting Policy')
                else:
                    col.prop(ob_nwo, "Poop_Lighting_Override", text='Lighting Policy')
                
                if not_bungie_game():
                    col.prop(ob_nwo, "poop_lightmap_resolution_scale")
                    
                if ob.name.startswith(poop_pathfinding_prefixes):
                    col.prop(ob_nwo, "Poop_Pathfinding_Override_Locked", text='Pathfinding Policy')
                else:
                    col.prop(ob_nwo, "Poop_Pathfinding_Override", text='Pathfinding Policy')

                col.prop(ob_nwo, "Poop_Imposter_Policy", text='Imposter Policy')
                if ob_nwo.Poop_Imposter_Policy != '_connected_poop_instance_imposter_policy_never':
                    sub = col.row(heading="Imposter Transition")
                    sub.prop(ob_nwo, 'Poop_Imposter_Transition_Distance_Auto', text='Automatic')
                    if not ob_nwo.Poop_Imposter_Transition_Distance_Auto:
                        sub.prop(ob_nwo, 'Poop_Imposter_Transition_Distance', text='Distance')
                    if not_bungie_game():
                        col.prop(ob_nwo, 'poop_imposter_brightness')
                    # col.prop(ob_nwo, "Poop_Imposter_Fade_Range_Start", text='Fade In Start')
                    # col.prop(ob_nwo, "Poop_Imposter_Fade_Range_End", text='Fade In End')
                #col.prop(ob_nwo, "Poop_Decomposition_Hulls", text='Decomposition Hulls') commented out so it can be set automatically. 

                # col.separator()

                # col.prop(ob_nwo, "Poop_Predominant_Shader_Name", text='Predominant Shader Name')

                if not_bungie_game():
                    col.prop(ob_nwo, 'poop_streaming_priority')
                    col.prop(ob_nwo, 'poop_cinematic_properties')

                col.separator()

                col = layout.column(heading="Flags")
                sub = col.column(align=True)

                if ob.name.startswith(poop_render_only_prefixes):
                    sub.prop(ob_nwo, "Poop_Render_Only_Locked", text='Render Only')
                else:
                    sub.prop(ob_nwo, "Poop_Render_Only", text='Render Only')

                sub.prop(ob_nwo, "Poop_Chops_Portals", text='Chops Portals')
                sub.prop(ob_nwo, "Poop_Does_Not_Block_AOE", text='Does Not Block AOE')
                sub.prop(ob_nwo, "Poop_Excluded_From_Lightprobe", text='Excluded From Lightprobe')
                sub.prop(ob_nwo, "Poop_Decal_Spacing", text='Decal Spacing')
                if not_bungie_game():
                    sub.prop(ob_nwo, "poop_remove_from_shadow_geometry")
                    sub.prop(ob_nwo, "poop_disallow_lighting_samples",)
                    sub.prop(ob_nwo, "poop_rain_occluder")

            else:
                col.label(text="Instanced Geometry mesh type only valid for Scenario / Prefab exports", icon='ERROR')

        elif CheckType.portal(ob):
            if poll_ui(('SCENARIO')):
                row = col.row()
                row.prop(ob_nwo, "Portal_Type", text='Portal Type', expand=True)

                col.separator()

                col = layout.column(heading="Flags")
                sub = col.column(align=True)

                sub.prop(ob_nwo, "Portal_AI_Deafening", text='AI Deafening')
                sub.prop(ob_nwo, "Portal_Blocks_Sounds", text='Blocks Sounds')
                sub.prop(ob_nwo, "Portal_Is_Door", text='Is Door')
            else:
                col.label(text="Portal mesh type only valid for Scenario exports", icon='ERROR')

        elif CheckType.water_physics(ob):
            if poll_ui(('SCENARIO')):
                col.prop(ob_nwo, "Water_Volume_Depth", text='Water Volume Depth')
                col.prop(ob_nwo, "Water_Volume_Flow_Direction", text='Flow Direction')
                col.prop(ob_nwo, "Water_Volume_Flow_Velocity", text='Flow Velocity')
                col.prop(ob_nwo, "Water_Volume_Fog_Color", text='Underwater Fog Color')
                col.prop(ob_nwo, "Water_Volume_Fog_Murkiness", text='Underwater Fog Murkiness')
            else:
                col.label(text="Water Physics mesh type only valid for Scenario exports", icon='ERROR')

        elif CheckType.fog(ob):
            if poll_ui(('SCENARIO')):
                col.prop(ob_nwo, "Fog_Name", text='Fog Name')
                row = col.row()
                row.prop(ob_nwo, "Fog_Appearance_Tag", text='Fog Appearance Tag')
                row.operator('nwo.fog_path')
                col.prop(ob_nwo, "Fog_Volume_Depth", text='Fog Volume Depth')
            else:
                col.label(text="Fog mesh type only valid for Scenario exports", icon='ERROR')

        elif CheckType.obb_volume(ob):
            if poll_ui(('SCENARIO')):
                row = col.row()
                row.prop(ob_nwo, "obb_volume_type", expand=True)
            else:
                col.label(text="OBB Volume mesh type only valid for Scenario exports", icon='ERROR')

        elif CheckType.physics(ob) and poll_ui(('MODEL')):
            if poll_ui(('MODEL')) or (poll_ui(('SCENARIO')) and not not_bungie_game()):
                col.prop(ob_nwo, "Mesh_Primitive_Type", text='Primitive Type')
            else:
                col.label(text="Physics mesh type only valid for Model and Reach Scenario exports", icon='ERROR')

class NWO_ObjectMeshMaterialLightingProps(Panel):
    bl_label = "Lighting Properties"
    bl_idname = "NWO_PT_MeshMaterialLightingDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MeshFaceDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object
        ob_nwo = ob.nwo

        if not poll_ui(('SCENARIO', 'PREFAB')):
            return False

        if object_prefix(context.active_object, special_prefixes):
            return ob_nwo.ObjectMesh_Type_Locked not in invalid_mesh_types
        else:
            return ob_nwo.ObjectMesh_Type not in invalid_mesh_types

    def draw_header(self, context):
        ob = context.object
        ob_nwo = ob.nwo
        self.layout.prop(ob_nwo, "Material_Lighting_Enabled", text='')

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        ob = context.object
        ob_nwo = ob.nwo

        col = flow.column()

        layout.enabled = ob_nwo.Material_Lighting_Enabled
        
        col.prop(ob_nwo, "Material_Lighting_Emissive_Color", text='Emissive Color')
        col.prop(ob_nwo, "Material_Lighting_Emissive_Power", text='Emissive Power')
        col.prop(ob_nwo, "Material_Lighting_Emissive_Focus", text='Emissive Focus')
        col.prop(ob_nwo, "Material_Lighting_Emissive_Quality", text='Emissive Quality')

        col.separator()
        
        if not_bungie_game():
            col.prop(ob_nwo, "lighting_frustum_blend")
            col.prop(ob_nwo, "lighting_frustum_cutoff")
            col.prop(ob_nwo, "lighting_frustum_falloff")

        col.separator()

        col.prop(ob_nwo, "Material_Lighting_Bounce_Ratio", text='Bounce Ratio')

        col.separator()

        if not_bungie_game():
            col.prop(ob_nwo, "lighting_attenuation_enabled")
        if ob_nwo.lighting_attenuation_enabled or not not_bungie_game():
            col.prop(ob_nwo, "Material_Lighting_Attenuation_Falloff", text='Attenuation Falloff')
            col.prop(ob_nwo, "Material_Lighting_Attenuation_Cutoff", text='Attenuation Cutoff')
        
        col.separator()

        col = layout.column(heading="Flags")
        sub = col.column(align=True)
        sub.prop(ob_nwo, "Material_Lighting_Emissive_Per_Unit", text='Emissive Per Unit')
        sub.prop(ob_nwo, "Material_Lighting_Use_Shader_Gel", text='Use Shader Gel')

class NWO_ObjectMeshLightmapProps(Panel):
    bl_label = "Lightmap Properties"
    bl_idname = "NWO_PT_MeshLightmapDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MeshFaceDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object
        ob_nwo = ob.nwo

        if not poll_ui(('SCENARIO', 'PREFAB')):
            return False

        if object_prefix(context.active_object, special_prefixes):
            return ob_nwo.ObjectMesh_Type_Locked not in invalid_mesh_types
        else:
            return ob_nwo.ObjectMesh_Type not in invalid_mesh_types

    def draw_header(self, context):
        ob = context.object
        ob_nwo = ob.nwo
        self.layout.prop(ob_nwo, "Lightmap_Settings_Enabled", text='')

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        ob = context.object
        ob_nwo = ob.nwo

        col = flow.column()

        layout.enabled = ob_nwo.Lightmap_Settings_Enabled

        col.prop(ob_nwo, "Lightmap_Type", text='Lightmap Type')

        col.separator()

        col.prop(ob_nwo, "Lightmap_Translucency_Tint_Color", text='Translucency Tint Color')
        col.prop(ob_nwo, "Lightmap_Additive_Transparency", text='Additive Transparency')
        
        col.separator()

        col.prop(ob_nwo, "Lightmap_Resolution_Scale", text='Resolution Scale')
        col.prop(ob_nwo, "lightmap_photon_fidelity")

        # col.prop(ob_nwo, "Lightmap_Chart_Group", text='Chart Group')

        # col.separator()

        # col.prop(ob_nwo, "Lightmap_Analytical_Bounce_Modifier", text='Analytical Bounce Modifier')
        # col.prop(ob_nwo, "Lightmap_General_Bounce_Modifier", text='General Bounce Modifier')
        
        col.separator()

        col = layout.column(heading="Flags")
        sub = col.column(align=True)
        sub.prop(ob_nwo, "Lightmap_Lighting_From_Both_Sides", text='Lighting From Both Sides')
        sub.prop(ob_nwo, "Lightmap_Transparency_Override", text='Transparency Override')
        

# MARKER PROPERTIES
class NWO_ObjectMarkerProps(Panel):
    bl_label = "Marker Properties"
    bl_idname = "NWO_PT_MarkerDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_parent_id = "NWO_PT_ObjectDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object

        return is_marker(ob)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        ob = context.object
        ob_nwo = ob.nwo

        col = flow.column()
        if not_bungie_game():
            if object_prefix(ob, ('?', '$')):
                col.prop(ob_nwo, "ObjectMarker_Type_Locked_H4", text='Marker Type')
            else:
                col.prop(ob_nwo, "ObjectMarker_Type_H4", text='Marker Type')
        else:
            if object_prefix(ob, ('?', '$')):
                col.prop(ob_nwo, "ObjectMarker_Type_Locked", text='Marker Type')
            else:
                col.prop(ob_nwo, "ObjectMarker_Type", text='Marker Type')

        if CheckType.model(ob):
            col.prop(ob_nwo, "Marker_Group_Name", text='Marker Group')
            col.prop(ob_nwo, "Marker_Velocity", text='Marker Velocity')
            sub = col.row(align=True)
            if not ob_nwo.Marker_All_Regions:
                if ob_nwo.Region_Name_Locked != '':
                    col.prop(ob_nwo, 'Region_Name_Locked', text='Region')
                else:
                    col.prop(ob_nwo, "Region_Name", text='Region')
            sub.prop(ob_nwo, 'Marker_All_Regions', text='All Regions')

        elif CheckType.game_instance(ob):
            row = col.row()
            row.prop(ob_nwo, "Marker_Game_Instance_Tag_Name", text='Tag Path')
            row.operator('nwo.game_instance_path')
            col.prop(ob_nwo, "Marker_Game_Instance_Tag_Variant_Name", text='Tag Variant')
            if not_bungie_game():
                col.prop(ob_nwo, 'marker_game_instance_run_scripts') 
                
        elif CheckType.hint(ob) and not_bungie_game():
            col.prop(ob_nwo, "Marker_Group_Name", text='Marker Group')
            col.prop(ob_nwo, 'marker_hint_length')

        elif CheckType.pathfinding_sphere(ob):
            col = layout.column(heading="Flags")
            sub = col.column(align=True)
            sub.prop(ob_nwo, "Marker_Pathfinding_Sphere_Vehicle", text='Vehicle Only')
            sub.prop(ob_nwo, "Pathfinding_Sphere_Remains_When_Open", text='Remains When Open')
            sub.prop(ob_nwo, "Pathfinding_Sphere_With_Sectors", text='With Sectors')
            if ob.type != 'MESH':
                sub.prop(ob_nwo, "marker_sphere_radius")

        elif CheckType.physics_constraint(ob):
            col.prop(ob_nwo, "Physics_Constraint_Parent", text='Constraint Parent')
            col.prop(ob_nwo, "Physics_Constraint_Child", text='Constraint Child')

            sus = col.row(align=True)

            sus.prop(ob_nwo, "Physics_Constraint_Type", text='Constraint Type', expand=True)
            sus.prop(ob_nwo, 'Physics_Constraint_Uses_Limits', text='Uses Limits')

            if ob_nwo.Physics_Constraint_Uses_Limits:
                if ob_nwo.Physics_Constraint_Type == '_connected_geometry_marker_type_physics_hinge_constraint':
                    col.prop(ob_nwo, "Hinge_Constraint_Minimum", text='Minimum')
                    col.prop(ob_nwo, "Hinge_Constraint_Maximum", text='Maximum')

                elif ob_nwo.Physics_Constraint_Type == '_connected_geometry_marker_type_physics_socket_constraint':
                    col.prop(ob_nwo, "Cone_Angle", text='Cone Angle')

                    col.prop(ob_nwo, "Plane_Constraint_Minimum", text='Plane Minimum')
                    col.prop(ob_nwo, "Plane_Constraint_Maximum", text='Plane Maximum')
                    
                    col.prop(ob_nwo, "Twist_Constraint_Start", text='Twist Start')
                    col.prop(ob_nwo, "Twist_Constraint_End", text='Twist End')

        elif CheckType.target(ob):
            col.prop(ob_nwo, "Marker_Group_Name", text='Marker Group')

        elif CheckType.airprobe(ob) and not_bungie_game():
            col.prop(ob_nwo, "Marker_Group_Name", text='Air Probe Group')

        elif CheckType.envfx(ob) and not_bungie_game():
            row = col.row()
            row.prop(ob_nwo, "marker_looping_effect")
            row.operator('nwo.effect_path') 

        elif CheckType.lightCone(ob) and not_bungie_game():
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

# MATERIAL PROPERTIES
class NWO_MaterialProps(Panel):
    bl_label = "Halo Material Properties"
    bl_idname = "NWO_PT_MaterialPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global

        if scene_nwo.game_version in ('reach','h4','h2a'):
            return context.material

    def draw(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        layout = self.layout
        ob = context.active_object
        current_material = ob.active_material
        if current_material is not None:
            material_nwo = current_material.nwo
            layout.use_property_split = True
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            # fun setup to display the correct fields
            if not_bungie_game():
                row = col.row()
                row.prop(material_nwo, "shader_path", text='Material Path')
                row.operator('nwo.shader_path')

            else:
                row = col.row()
                row.prop(material_nwo, "shader_path")
                row.operator('nwo.shader_path')
                col.prop(material_nwo, "Shader_Type")

            if material_nwo.shader_path != '':
                col.separator()
                row = col.row()
                row.scale_y = 1.5
                row.operator('nwo.open_halo_material')

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

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global

        if scene_nwo.game_version in ('reach','h4','h2a'):
            return context.object.type == 'LIGHT'

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
                col.prop(ob_nwo, 'Light_Near_Attenuation_StartH4')
                col.prop(ob_nwo, 'Light_Near_Attenuation_EndH4')
            
            col.separator()
                
            if ob_nwo.light_mode == '_connected_geometry_light_mode_dynamic':
                col.prop(ob_nwo, 'Light_Far_Attenuation_StartH4')
                col.prop(ob_nwo, 'Light_Far_Attenuation_EndH4')

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

            col.prop(ob_nwo, 'Light_Game_Type', text='Game Type')
            col.prop(ob_nwo, 'Light_Shape', text='Shape')
            # col.prop(ob_nwo, 'Light_Color', text='Color') 
            col.prop(ob_nwo, 'Light_Intensity', text='Intensity')

            col.separator()

            col.prop(ob_nwo, 'Light_Fade_Start_Distance', text='Fade Out Start Distance')
            col.prop(ob_nwo, 'Light_Fade_End_Distance', text='Fade Out End Distance')

            col.separator()

            col.prop(ob_nwo, 'Light_Hotspot_Size', text='Hotspot Size')
            col.prop(ob_nwo, 'Light_Hotspot_Falloff', text='Hotspot Falloff')
            col.prop(ob_nwo, 'Light_Falloff_Shape', text='Falloff Shape')
            col.prop(ob_nwo, 'Light_Aspect', text='Light Aspect')

            col.separator()

            col.prop(ob_nwo, 'Light_Frustum_Width', text='Frustum Width')
            col.prop(ob_nwo, 'Light_Frustum_Height', text='Frustum Height')

            col.separator()

            col.prop(ob_nwo, 'Light_Volume_Distance', text='Light Volume Distance')
            col.prop(ob_nwo, 'Light_Volume_Intensity', text='Light Volume Intensity')

            col.separator()

            col.prop(ob_nwo, 'Light_Bounce_Ratio', text='Light Bounce Ratio')

            col.separator()

            col = layout.column(heading="Flags")
            sub = col.column(align=True)

            sub.prop(ob_nwo, 'Light_Ignore_BSP_Visibility', text='Ignore BSP Visibility') 
            sub.prop(ob_nwo, 'Light_Dynamic_Has_Bounce', text='Light Has Dynamic Bounce')
            if ob_nwo.light_sub_type == '_connected_geometry_lighting_sub_type_screenspace':
                sub.prop(ob_nwo, 'Light_Screenspace_Has_Specular', text='Screenspace Light Has Specular')

            col = flow.column()

            col.prop(ob_nwo, 'Light_Near_Attenuation_Start', text='Near Attenuation Start')
            col.prop(ob_nwo, 'Light_Near_Attenuation_End', text='Near Attenuation End')

            col.separator()

            col.prop(ob_nwo, 'Light_Far_Attenuation_Start', text='Far Attenuation Start')
            col.prop(ob_nwo, 'Light_Far_Attenuation_End', text='Far Attenuation End')

            col.separator()
            row = col.row()
            row.prop(ob_nwo, 'Light_Tag_Override', text='Light Tag Override')
            row.operator('nwo.light_tag_path')
            row = col.row()
            row.prop(ob_nwo, 'Light_Shader_Reference', text='Shader Tag Reference')
            row.operator('nwo.light_shader_path')
            row = col.row()
            row.prop(ob_nwo, 'Light_Gel_Reference', text='Gel Tag Reference')
            row.operator('nwo.light_gel_path')
            row = col.row()
            row.prop(ob_nwo, 'Light_Lens_Flare_Reference', text='Lens Flare Tag Reference')
            row.operator('nwo.lens_flare_path')

            # col.separator() # commenting out light clipping for now.

            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')

class NWO_LightPropsCycles(Panel):
    bl_label = "Halo Light Properties"
    bl_idname = "NWO_PT_LightPanel_Cycles"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "CYCLES_LIGHT_PT_light"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global

        if scene_nwo.game_version in ('reach','h4','h2a'):
            return context.object.type == 'LIGHT'

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
                col.prop(ob_nwo, 'Light_Near_Attenuation_StartH4')
                col.prop(ob_nwo, 'Light_Near_Attenuation_EndH4')
            
            col.separator()
                
            if ob_nwo.light_mode == '_connected_geometry_light_mode_dynamic':
                col.prop(ob_nwo, 'Light_Far_Attenuation_StartH4')
                col.prop(ob_nwo, 'Light_Far_Attenuation_EndH4')

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

            col.prop(ob_nwo, 'Light_Game_Type', text='Game Type')
            col.prop(ob_nwo, 'Light_Shape', text='Shape')
            # col.prop(ob_nwo, 'Light_Color', text='Color') 
            col.prop(ob_nwo, 'Light_Intensity', text='Intensity')

            col.separator()

            col.prop(ob_nwo, 'Light_Fade_Start_Distance', text='Fade Out Start Distance')
            col.prop(ob_nwo, 'Light_Fade_End_Distance', text='Fade Out End Distance')

            col.separator()

            col.prop(ob_nwo, 'Light_Hotspot_Size', text='Hotspot Size')
            col.prop(ob_nwo, 'Light_Hotspot_Falloff', text='Hotspot Falloff')
            col.prop(ob_nwo, 'Light_Falloff_Shape', text='Falloff Shape')
            col.prop(ob_nwo, 'Light_Aspect', text='Light Aspect')

            col.separator()

            col.prop(ob_nwo, 'Light_Frustum_Width', text='Frustum Width')
            col.prop(ob_nwo, 'Light_Frustum_Height', text='Frustum Height')

            col.separator()

            col.prop(ob_nwo, 'Light_Volume_Distance', text='Light Volume Distance')
            col.prop(ob_nwo, 'Light_Volume_Intensity', text='Light Volume Intensity')

            col.separator()

            col.prop(ob_nwo, 'Light_Bounce_Ratio', text='Light Bounce Ratio')

            col.separator()

            col = layout.column(heading="Flags")
            sub = col.column(align=True)

            sub.prop(ob_nwo, 'Light_Ignore_BSP_Visibility', text='Ignore BSP Visibility') 
            sub.prop(ob_nwo, 'Light_Dynamic_Has_Bounce', text='Light Has Dynamic Bounce')
            if ob_nwo.light_sub_type == '_connected_geometry_lighting_sub_type_screenspace':
                sub.prop(ob_nwo, 'Light_Screenspace_Has_Specular', text='Screenspace Light Has Specular')

            col = flow.column()

            col.prop(ob_nwo, 'Light_Near_Attenuation_Start', text='Near Attenuation Start')
            col.prop(ob_nwo, 'Light_Near_Attenuation_End', text='Near Attenuation End')

            col.separator()

            col.prop(ob_nwo, 'Light_Far_Attenuation_Start', text='Far Attenuation Start')
            col.prop(ob_nwo, 'Light_Far_Attenuation_End', text='Far Attenuation End')

            col.separator()
            row = col.row()
            row.prop(ob_nwo, 'Light_Tag_Override', text='Light Tag Override')
            row.operator('nwo.light_tag_path')
            row = col.row()
            row.prop(ob_nwo, 'Light_Shader_Reference', text='Shader Tag Reference')
            row.operator('nwo.light_shader_path')
            row = col.row()
            row.prop(ob_nwo, 'Light_Gel_Reference', text='Gel Tag Reference')
            row.operator('nwo.light_gel_path')
            row = col.row()
            row.prop(ob_nwo, 'Light_Lens_Flare_Reference', text='Lens Flare Tag Reference')
            row.operator('nwo.lens_flare_path')

            # col.separator() # commenting out light clipping for now.

            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')

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
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        
        action = context.object.animation_data.action
        action_nwo = action.nwo
        
        col = flow.column()
        # col.prop(action_nwo, "export_this") # this is now only used internally
        col.prop(action_nwo, 'name_override')
        col.prop(action_nwo, 'animation_type') 

# NWO PROPERTY GROUPS
class NWO_ObjectPropertiesGroup(PropertyGroup):
    #OBJECT PROPERTIES
    # object_id: StringProperty(
    #     name="Object ID",
    # )

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


    object_type_items_all = [
        ('_connected_geometry_object_type_frame', 'Frame', "Treat this object as a frame. Can be forced on with the prefixes: 'b_', 'b ', 'frame ', 'frame_'"),
        ('_connected_geometry_object_type_marker', 'Marker', "Sets this object to be written to a json file as a marker. Can be forced on with the prefix: '#'"),
        ('_connected_geometry_object_type_mesh', 'Mesh', "Treats this object as a mesh when writing to a json file"),
    ]

    object_type_items_no_mesh = [
        ('_connected_geometry_object_type_frame', "Frame", "Treat this object as a frame. Can be forced on with the prefixes: 'b_', 'b ', 'frame ', 'frame_'"),
        ('_connected_geometry_object_type_marker', "Marker", "Sets this object to be written to a json file as a marker. Can be forced on with the prefix: '#'"),
    ]

    Object_Type_All: EnumProperty(
        name="Object Type",
        options=set(),
        description="Sets the Halo object type of this object",
        default = '_connected_geometry_object_type_mesh',
        items=object_type_items_all,
    )

    Object_Type_No_Mesh: EnumProperty(
        name="Object Type",
        options=set(),
        description="Sets the object type",
        default = '_connected_geometry_object_type_marker',
        items=object_type_items_no_mesh,
    )

    Object_Type_All_Locked: EnumProperty(
        name="Object Type",
        options=set(),
        get=get_objecttype_enum,
        description="Sets the object type",
        default = '_connected_geometry_object_type_mesh',
        items=object_type_items_all,
    )

    Object_Type_No_Mesh_Locked: EnumProperty(
        name="Object Type",
        options=set(),
        get=get_objecttype_enum_no_mesh,
        description="Sets the object type",
        default = '_connected_geometry_object_type_marker',
        items=object_type_items_no_mesh,
    )

    def LockLight(self):
        return 0

    Object_Type_Light: EnumProperty(
        name="Object Type",
        options=set(),
        get=LockLight,
        description="Sets the object type",
        default = '_connected_geometry_object_type_light',
        items=[('_connected_geometry_object_type_light', 'Light', '')],
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

    def get_meshtype_enum(self):
        a_ob = bpy.context.active_object
        if a_ob.name.startswith(('+soft_ceiling','+soft_kill','+slip_surface')):
            return 0
        elif a_ob.name.startswith('@'):
            return 1
        elif a_ob.name.startswith('+cookie'):
            return 2
        elif a_ob.name.startswith('%'):
            return 5
        elif a_ob.name.startswith('+flair'):
            return 10
        elif a_ob.name.startswith('$'):
            return 11
        elif a_ob.name.startswith('+fog'):
            return 12
        elif a_ob.name.startswith('+portal'):
            return 13
        elif a_ob.name.startswith('+seam'):
            return 14
        elif a_ob.name.startswith('+water'):
            return 15
        elif a_ob.name.startswith('\''):
            return 16
        else:
            return 4

    mesh_type_items = [
        ('_connected_geometry_mesh_type_boundary_surface', "Boundary Surface", "Used in structure_design tags for soft_kill, soft_ceiling, and slip_sufaces. Only use when importing to a structure_design tag. Can be forced on with the prefixes: '+soft_ceiling', 'soft_kill', 'slip_surface'"), # 0
        ('_connected_geometry_mesh_type_collision', "Collision", "Sets this mesh to have collision geometry only. Can be forced on with the prefix: '@'"), #1
        ('_connected_geometry_mesh_type_cookie_cutter', "Cookie Cutter", "Defines an area which ai will pathfind around. Can be forced on with the prefix: '+cookie'"), # 2
        ('_connected_geometry_mesh_type_decorator', "Decorator", "Use this when making a decorator. Allows for different LOD levels to be set"), # 3
        ('_connected_geometry_mesh_type_default', "Render / Structure", "By default this mesh type will be treated as render only geometry in models, and render + bsp collision geometry in structures"), #4
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
    ]

    def get_default_mesh_type(self):
        if bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_boundary_surface':
            return self.get("ObjectMesh_Type", 0)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_collision':
            return self.get("ObjectMesh_Type", 1)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_cookie_cutter':
            return self.get("ObjectMesh_Type", 2)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_decorator':
            return self.get("ObjectMesh_Type", 3)
        if bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_default':
            return self.get("ObjectMesh_Type", 4)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_poop':
            return self.get("ObjectMesh_Type", 5)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_object_instance':
            return self.get("ObjectMesh_Type", 10)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_physics':
            return self.get("ObjectMesh_Type", 11)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_planar_fog_volume':
            return self.get("ObjectMesh_Type", 12)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_portal':
            return self.get("ObjectMesh_Type", 13)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_seam':
            return self.get("ObjectMesh_Type", 14)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_water_physics_volume':
            return self.get("ObjectMesh_Type", 15)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_water_surface':
            return self.get("ObjectMesh_Type", 16)
        else:
            return self.get("ObjectMesh_Type", 4)
    
    def set_default_mesh_type(self, value):
        self["ObjectMesh_Type"] = value

    #MESH PROPERTIES
    ObjectMesh_Type : EnumProperty(
        name="Mesh Type",
        options=set(),
        description="Sets the type of Halo mesh you want to create. This value is overridden by certain object prefixes",
        default = '_connected_geometry_mesh_type_default',
        get=get_default_mesh_type,
        set=set_default_mesh_type,
        items=mesh_type_items,
        )

    ObjectMesh_Type_Locked : EnumProperty(
        name="Mesh Type",
        options=set(),
        get=get_meshtype_enum,
        description="Sets the type of Halo mesh you want to create. This value is overridden by certain object prefixes e.g. $, @, %",
        default = '_connected_geometry_mesh_type_default',
        items=mesh_type_items,
        )

    def get_meshtype_enum_h4(self):
        a_ob = bpy.context.active_object
        if a_ob.name.startswith(('+soft_ceiling','+soft_kill','+slip_surface')):
            return 0
        elif a_ob.name.startswith('@'):
            return 1
        elif a_ob.name.startswith('+cookie'):
            return 2
        elif a_ob.name.startswith('%'):
            return 5
        elif a_ob.name.startswith('+flair'):
            return 6
        elif a_ob.name.startswith('$'):
            return 7
        elif a_ob.name.startswith('+fog'):
            return 8
        elif a_ob.name.startswith('+portal'):
            return 9
        elif a_ob.name.startswith('+seam'):
            return 10
        elif a_ob.name.startswith('+water'):
            return 11
        elif a_ob.name.startswith('\''):
            return 12
        else:
            return 4

    # dupes for h4
    mesh_type_items_h4 = [
        ('_connected_geometry_mesh_type_boundary_surface', "Boundary Surface", "Used in structure_design tags for soft_kill, soft_ceiling, and slip_sufaces. Only use when importing to a structure_design tag. Can be forced on with the prefix: '+'"), # 0
        ('_connected_geometry_mesh_type_collision', "Collision", "Sets this mesh to have collision geometry only. Can be forced on with the prefix: '@'"), #1
        ('_connected_geometry_mesh_type_cookie_cutter', "Cookie Cutter", "Defines an area which ai will pathfind around. Can be forced on with the prefix: '+cookie'"), # 2
        ('_connected_geometry_mesh_type_decorator', "Decorator", "Use this when making a decorator. Allows for different LOD levels to be set"), # 3
        ('_connected_geometry_mesh_type_default', "Render / Structure", "By default this mesh type will be treated as render only geometry in models, and render + bsp collision geometry in structures"), #4
        ('_connected_geometry_mesh_type_poop', "Instanced Geometry", "Writes this mesh to a json file as instanced geometry. Can be forced on with the prefix: '%'"), # 5
        ('_connected_geometry_mesh_type_object_instance', "Object Instance", "Writes this mesh to the json as an instanced object. Can be forced on with the prefix: '+flair'"), # 6
        ('_connected_geometry_mesh_type_physics', "Physics", "Sets this mesh to have physics geometry only. Can be forced on with the prefix: '$'"), # 7
        ('_connected_geometry_mesh_type_planar_fog_volume', "Planar Fog Volume", "Defines an area for a fog volume. The same logic as used for portals should be applied to these.  Can be forced on with the prefix: '+fog'"), # 8
        ('_connected_geometry_mesh_type_portal', "Portal", "Cuts up a bsp and defines clusters. Can be forced on with the prefix '+portal'"), # 9
        ('_connected_geometry_mesh_type_seam', "Seam", "Defines where two bsps meet. Its name should match the name of the bsp its in. Can be forced on with the prefix '+seam'"), # 10
        ('_connected_geometry_mesh_type_water_physics_volume', "Water Physics Volume", "Defines an area where water physics should apply. Only use when importing to a structure_design tag. Can be forced on with the prefix: '+water'"), # 11
        ('_connected_geometry_mesh_type_water_surface', "Water Surface", "Defines a mesh as a water surface. Can be forced on with the prefix: '"), # 12
        ('_connected_geometry_mesh_type_obb_volume', 'OBB Volume', ''), # 13
    ]

    def get_default_mesh_type_h4(self):
        if bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_boundary_surface':
            return self.get("ObjectMesh_Type_H4", 0)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_collision':
            return self.get("ObjectMesh_Type_H4", 1)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_cookie_cutter':
            return self.get("ObjectMesh_Type_H4", 2)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_decorator':
            return self.get("ObjectMesh_Type_H4", 3)
        if bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_default':
            return self.get("ObjectMesh_Type_H4", 4)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_poop':
            return self.get("ObjectMesh_Type_H4", 5)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_object_instance':
            return self.get("ObjectMesh_Type_H4", 6)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_physics':
            return self.get("ObjectMesh_Type_H4", 7)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_planar_fog_volume':
            return self.get("ObjectMesh_Type_H4", 8)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_portal':
            return self.get("ObjectMesh_Type_H4", 9)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_seam':
            return self.get("ObjectMesh_Type_H4", 10)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_water_physics_volume':
            return self.get("ObjectMesh_Type_H4", 11)
        elif bpy.context.scene.nwo.default_mesh_type == '_connected_geometry_mesh_type_water_surface':
            return self.get("ObjectMesh_Type_H4", 12)
        else:
            return self.get("ObjectMesh_Type_H4", 4)
    
    def set_default_mesh_type_h4(self, value):
        self["ObjectMesh_Type_H4"] = value

    ObjectMesh_Type_H4 : EnumProperty(
        name="Mesh Type",
        options=set(),
        description="Sets the type of Halo mesh you want to create. This value is overridden by certain object prefixes",
        default = '_connected_geometry_mesh_type_default',
        get=get_default_mesh_type_h4,
        set=set_default_mesh_type_h4,
        items=mesh_type_items_h4,
        )

    ObjectMesh_Type_Locked_H4 : EnumProperty(
        name="Mesh Type",
        options=set(),
        get=get_meshtype_enum_h4,
        description="Sets the type of Halo mesh you want to create. This value is overridden by certain object prefixes e.g. $, @, %",
        default = '_connected_geometry_mesh_type_default',
        items=mesh_type_items_h4,
        )

    Mesh_Primitive_Type : EnumProperty(
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

    Mesh_Tessellation_Density : EnumProperty(
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
    Mesh_Compression : EnumProperty(
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
    Face_Type : EnumProperty(
        name="Face Type",
        options=set(),
        description="Sets the face type for this mesh. Note that any override shaders will override the face type selected here for relevant materials",
        default = '_connected_geometry_face_type_normal',
        items=[ ('_connected_geometry_face_type_normal', "Normal", "This face type has no special properties"),
                ('_connected_geometry_face_type_seam_sealer', "Seam Sealer", "Set mesh faces to have the special seam sealer property. Collsion only geometry"),
                ('_connected_geometry_face_type_sky', "Sky", "Set mesh faces to render the sky"),
               ]
        )

    Face_Mode : EnumProperty(
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

    Face_Sides : EnumProperty(
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

    Face_Draw_Distance : EnumProperty(
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

    Region_Name: StringProperty(
        name="Face Region",
        default='default',
        description="Define the name of the region these faces should be associated with",
    )

    def get_region_from_collection(self):
        region = get_prop_from_collection(self.id_data, ('+region:', '+reg:'))
        return region

    Region_Name_Locked: StringProperty(
        name="Face Region",
        description="Define the region for this mesh",
        get=get_region_from_collection,
    )

    Permutation_Name: StringProperty(
        name="Permutation",
        default='default',
        description="Define the permutation of this object. Permutations get exported to seperate files in scenario exports, or in model exports if the mesh type is one of render/collision/physics",
    )

    def get_permutation_from_collection(self):
        permutation = get_prop_from_collection(self.id_data, ('+perm:', '+permuation:'))
        return permutation

    Permutation_Name_Locked: StringProperty(
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

    Face_Global_Material: StringProperty(
        name="Global Material",
        default='',
        description="Set the global material of this mesh. If the global material name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct global material response type, otherwise, the global material override can be manually defined in the .model tag",
    )

    Sky_Permutation_Index: IntProperty(
        name="Sky Permutation Index",
        options=set(),
        description="Set the sky permutation index of this mesh. Only valid if the face type is sky",
        min=0,
    )

    Conveyor: BoolProperty(
        name ="Conveyor",
        options=set(),
        description = "Enables the conveyor property",
        default = False,
        )

    Ladder: BoolProperty(
        name ="Ladder",
        options=set(),
        description = "Makes faces climbable",
        default = False,
    )

    Slip_Surface: BoolProperty(
        name ="Slip Surface",
        options=set(),
        description = "Makes faces slippery for units",
        default = False,
    )

    Decal_Offset: BoolProperty(
        name ="Decal Offset",
        options=set(),
        description = "Enable to offset these faces so that they appear to be layered on top of another face",
        default = False,
    )

    Group_Transparents_By_Plane: BoolProperty(
        name ="Group Transparents By Plane",
        options=set(),
        description = "Enable to group transparent geometry by fitted planes",
        default = False,
    )

    No_Shadow: BoolProperty(
        name ="No Shadow",
        options=set(),
        description = "Enable to prevent faces from casting shadows",
        default = False,
    )

    Precise_Position: BoolProperty(
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

    Boundary_Surface_Name: StringProperty(
        name="Boundary Surface Name",
        description="Define the name of the boundary surface. This will be referenced in the structure_design tag.",
        get=get_boundary_surface_name,
        maxlen=32,
    )

    boundary_surface_items = [  ('_connected_geometry_boundary_surface_type_soft_ceiling', "Soft Ceiling", "Defines this mesh as soft ceiling"),
                                ('_connected_geometry_boundary_surface_type_soft_kill', "Soft Kill", "Defines this mesh as soft kill barrier"),
                                ('_connected_geometry_boundary_surface_type_slip_surface', "Slip Surface", "Defines this mesh as a slip surface"),
                                ]

    Boundary_Surface_Type : EnumProperty(
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

    Boundary_Surface_Type_Locked : EnumProperty(
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
    Poop_Lighting_Override : EnumProperty(
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

    Poop_Lighting_Override_Locked : EnumProperty(
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

    Poop_Pathfinding_Override : EnumProperty(
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

    Poop_Pathfinding_Override_Locked : EnumProperty(
        name="Instanced Geometry Pathfinding Override",
        options=set(),
        get=get_poop_pathfinding_policy,
        description="Sets the pathfinding policy for this instanced geometry",
        default = '_connected_poop_instance_pathfinding_policy_cutout',
        items=poop_pathfinding_items,
        )

    Poop_Imposter_Policy : EnumProperty(
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

    Poop_Imposter_Transition_Distance: FloatProperty(
        name="Instanced Geometry Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=50,
    )

    Poop_Imposter_Transition_Distance_Auto: BoolProperty(
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

    Poop_Render_Only: BoolProperty(
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

    Poop_Render_Only_Locked: BoolProperty(
        name ="Render Only",
        options=set(),
        get=get_poop_render_only,
        description = "Instanced geometry set to render only",
        default = False,
    )

    Poop_Chops_Portals: BoolProperty(
        name ="Chops Portals",
        options=set(),
        description = "Instanced geometry set to chop portals",
        default = False,
    )

    Poop_Does_Not_Block_AOE: BoolProperty(
        name ="Does Not Block AOE",
        options=set(),
        description = "Instanced geometry set to not block area of effect forces",
        default = False,
    )

    Poop_Excluded_From_Lightprobe: BoolProperty(
        name ="Excluded From Lightprobe",
        options=set(),
        description = "Sets this instanced geometry to be exlcuded from any lightprobes",
        default = False,
    )

    Poop_Decal_Spacing: BoolProperty(
        name ="Decal Spacing",
        options=set(),
        description = "Instanced geometry set to have decal spacing (like decal_offset)",
        default = False,
    )

    Poop_Precise_Geometry: BoolProperty(
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

    Poop_Collision_Type: EnumProperty(
        name ="Instanced Collision Type",
        options=set(),
        description = "Set the instanced collision type. Only used when exporting a scenario",
        default = '_connected_geometry_poop_collision_type_default',
        items=[ ('_connected_geometry_poop_collision_type_default', 'Default', 'Collision mesh that interacts with the physics objects and with projectiles'),
                ('_connected_geometry_poop_collision_type_play_collision', 'Sphere Collision', 'The collision mesh affects physics objects, but not projectiles'),
                ('_connected_geometry_poop_collision_type_bullet_collision', 'Projectile', 'The collision mesh only interacts with projectiles'),
                ('_connected_geometry_poop_collision_type_invisible_wall', 'Invisible Wall', "Projectiles go through this but the physics objects can't. You cannot directly place objects on wall collision mesh in Sapien"),
            ]
    )

    #PORTAL PROPERTIES
    Portal_Type : EnumProperty(
        name="Portal Type",
        options=set(),
        description="Sets the type of portal this mesh should be",
        default = "_connected_geometry_portal_type_two_way",
        items=[ ('_connected_geometry_portal_type_no_way', "No Way", "Sets the portal to block all visibility"),
                ('_connected_geometry_portal_type_one_way', "One Way", "Sets the portal to block visibility from one direction"),
                ('_connected_geometry_portal_type_two_way', "Two Way", "Sets the portal to have visiblity from both sides"),
               ]
        )

    Portal_AI_Deafening: BoolProperty(
        name ="AI Deafening",
        options=set(),
        description = "Stops AI hearing through this portal",
        default = False,
    )

    Portal_Blocks_Sounds: BoolProperty(
        name ="Blocks Sounds",
        options=set(),
        description = "Stops sound from travelling past this portal",
        default = False,
    )

    Portal_Is_Door: BoolProperty(
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

    Decorator_Name: StringProperty(
        name="Decorator Name",
        description="Name of your decorator",
        get=get_decorator_name,
    )

    Decorator_LOD: IntProperty(
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
    Water_Volume_Depth: FloatProperty( # this something which can probably be automated?
        name="Water Volume Depth",
        options=set(),
        description="Set the depth of this water volume mesh",
        default=20,
    )
    Water_Volume_Flow_Direction: FloatProperty( # this something which can probably be automated?
        name="Water Volume Flow Direction",
        options=set(),
        description="Set the flow direction of this water volume mesh",
        min=-180,
        max=180,
    )

    Water_Volume_Flow_Velocity: FloatProperty(
        name="Water Volume Flow Velocity",
        options=set(),
        description="Set the flow velocity of this water volume mesh",
        default=20,
    )

    Water_Volume_Fog_Color: FloatVectorProperty(
        name="Water Volume Fog Color",
        options=set(),
        description="Set the fog color of this water volume mesh",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    Water_Volume_Fog_Murkiness: FloatProperty(
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
    Fog_Name: StringProperty(
        name="Fog Name",
        description="Name of this fog volume",
        get=get_fog_name,
    )

    def fog_clean_tag_path(self, context):
        self['Fog_Appearance_Tag'] = clean_tag_path(self['Fog_Appearance_Tag']).strip('"')

    Fog_Appearance_Tag: StringProperty(
        name="Fog Appearance Tag",
        description="Name of the tag defining the fog volumes appearance",
        update=fog_clean_tag_path,
    )

    Fog_Volume_Depth: FloatProperty(
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
    Lightmap_Settings_Enabled: BoolProperty(
        name ="Enable to use lightmap settings",
        options=set(),
        description = "",
        default = False,
    )

    Lightmap_Additive_Transparency: FloatProperty(
        name="lightmap Additive Transparency",
        options=set(),
        description="",
        default=0.0,
        subtype='FACTOR',
        min=0.0,
        max=1.0
    )

    Lightmap_Ignore_Default_Resolution_Scale: BoolProperty(
        name ="Lightmap Resolution Scale",
        options=set(),
        description = "",
        default = False,
    )

    Lightmap_Resolution_Scale: IntProperty(
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

    Lightmap_Type : EnumProperty(
        name="Lightmap Type",
        options=set(),
        description="Sets how this should be lit while lightmapping",
        default = "_connected_material_lightmap_type_per_pixel",
        items=[ ('_connected_material_lightmap_type_per_pixel', "Per Pixel", ""),
                ('_connected_material_lightmap_type_per_vertex', "Per Vetex", ""),
               ]
        )

    Lightmap_Transparency_Override: BoolProperty(
        name ="Lightmap Transparency Override",
        options=set(),
        description = "",
        default = False,
    )

    Lightmap_Analytical_Bounce_Modifier: FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="",
        default=9999,
    )
    
    Lightmap_General_Bounce_Modifier: FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="",
        default=9999,
    )

    Lightmap_Translucency_Tint_Color: FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

    Lightmap_Lighting_From_Both_Sides: BoolProperty(
        name ="Lightmap Lighting From Both Sides",
        options=set(),
        description = "",
        default = False,
    )

    #MATERIAL LIGHTING PROPERTIES
    Material_Lighting_Enabled: BoolProperty(
        name="Toggle whether to use material lighting settings",
        options=set(),
        description="",
        default=False,
    )

    Material_Lighting_Attenuation_Cutoff: FloatProperty(
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

    Material_Lighting_Attenuation_Falloff: FloatProperty(
        name="Material Lighting Attenuation Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=100,
    )

    Material_Lighting_Emissive_Focus: FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="",
    )

    Material_Lighting_Emissive_Color: FloatVectorProperty(
        name="Material Lighting Emissive Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype='COLOR',
        min=0.0,
        max=1.0,
    )

    Material_Lighting_Emissive_Per_Unit: BoolProperty(
        name ="Material Lighting Emissive Per Unit",
        options=set(),
        description = "",
        default = False,
    )

    Material_Lighting_Emissive_Power: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="",
        min=0,
        default=100,
    )

    Material_Lighting_Emissive_Quality: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    Material_Lighting_Use_Shader_Gel: BoolProperty(
        name ="Material Lighting Use Shader Gel",
        options=set(),
        description = "",
        default = False,
    )

    Material_Lighting_Bounce_Ratio: FloatProperty(
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
    ObjectMarker_Type : EnumProperty(
        name="Marker Type",
        options=set(),
        description="Select the marker type",
        default = "_connected_geometry_marker_type_model",
        items=marker_types,
        )

    ObjectMarker_Type_Locked : EnumProperty(
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

    ObjectMarker_Type_H4 : EnumProperty(
        name="Marker Type",
        options=set(),
        description="Select the marker type",
        default = "_connected_geometry_marker_type_model",
        items=marker_types_h4,
        )

    ObjectMarker_Type_Locked_H4 : EnumProperty(
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

    Marker_Group_Name: StringProperty(
        name="Marker Group",
        description="Displays the name of the marker group. Marker groups equal the object name minus the '#' prefix and text after the last '.', allowing for multiple markers to share the same group",
        get=get_marker_group_name,
    )

    Marker_Region: StringProperty(
        name="Marker Group",
        description="Define the name of marker region. This should match a face region name. Leave blank for the 'default' region",
    )

    Marker_All_Regions: BoolProperty(
        name="Marker All Regions",
        options=set(),
        description="Associate this marker with all regions rather than a specific one",
        default=True,
    )

    def game_instance_clean_tag_path(self, context):
        self['Marker_Game_Instance_Tag_Name'] = clean_tag_path(self['Marker_Game_Instance_Tag_Name']).strip('"')

    Marker_Game_Instance_Tag_Name: StringProperty(
        name="Marker Game Instance Tag",
        description="Define the name of the marker game instance tag",
        update=game_instance_clean_tag_path,
    )

    Marker_Game_Instance_Tag_Variant_Name: StringProperty(
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

    marker_sphere_radius: FloatProperty(
        name="Sphere Radius",
        options=set(),
        description="Manually define the sphere radius for this marker. Alternatively, create a marker out of a mesh to have this radius set based on mesh dimensions",
        default=0.0,
        min=0.0,
    )

    Marker_Velocity: FloatVectorProperty(
        name="Marker Velocity",
        options=set(),
        description="",
        subtype='VELOCITY',
    )

    Marker_Pathfinding_Sphere_Vehicle: BoolProperty(
        name="Vehicle Only Pathfinding Sphere",
        options=set(),
        description="This pathfinding sphere only affects vehicles",
    )

    Pathfinding_Sphere_Remains_When_Open: BoolProperty(
        name="Pathfinding Sphere Remains When Open",
        options=set(),
        description="Pathfinding sphere remains even when a machine is open",
    )

    Pathfinding_Sphere_With_Sectors: BoolProperty(
        name="Pathfinding Sphere With Sectors",
        options=set(),
        description="Not sure",
    )

    Physics_Constraint_Parent: StringProperty( #need to make this into an object picker at some point
        name="Physics Constraint Parent",
        description="Enter the name of the object that is this marker's parent",
    )

    Physics_Constraint_Child: StringProperty( #need to make this into an object picker at some point
        name="Physics Constraint Child",
        description="Enter the name of the object that is this marker's child",
    )

    Physics_Constraint_Type : EnumProperty(
        name="Constraint Type",
        options=set(),
        description="Select the physics constraint type",
        default = "_connected_geometry_marker_type_physics_hinge_constraint",
        items=[ ('_connected_geometry_marker_type_physics_hinge_constraint', "Hinge", ""),
                ('_connected_geometry_marker_type_physics_socket_constraint', "Socket", ""),
               ]
        )

    Physics_Constraint_Uses_Limits: BoolProperty(
        name="Physics Constraint Uses Limits",
        options=set(),
        description="Set whether the limits of this physics constraint should be constrained or not",
    )

    Hinge_Constraint_Minimum: FloatProperty(
        name="Hinge Constraint Minimum",
        options=set(),
        description="Set the minimum rotation of a physics hinge",
        default=-180,
        min=-180,
        max=180,
    )

    Hinge_Constraint_Maximum: FloatProperty(
        name="Hinge Constraint Maximum",
        options=set(),
        description="Set the maximum rotation of a physics hinge",
        default=180,
        min=-180,
        max=180,
    )

    Cone_Angle: FloatProperty(
        name="Cone Angle",
        options=set(),
        description="Set the cone angle",
        default=90,
        min=0,
        max=180,
    )

    Plane_Constraint_Minimum: FloatProperty(
        name="Plane Constraint Minimum",
        options=set(),
        description="Set the minimum rotation of a physics plane",
        default=-90,
        min=-90,
        max=0,
    )

    Plane_Constraint_Maximum: FloatProperty(
        name="Plane Constraint Maximum",
        options=set(),
        description="Set the maximum rotation of a physics plane",
        default=90,
        min=-0,
        max=90,

    )

    Twist_Constraint_Start: FloatProperty(
        name="Twist Constraint Minimum",
        options=set(),
        description="Set the starting angle of a twist constraint",
        default=-180,
        min=-180,
        max=180,
    )

    Twist_Constraint_End: FloatProperty(
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

    Light_Game_Type: EnumProperty(
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

    Light_Shape: EnumProperty(
        name = "Light Shape",
        options=set(),
        description = "",
        default = "_connected_geometry_light_shape_circle",
        items=[ ('_connected_geometry_light_shape_circle', "Circle", ""),
                ('_connected_geometry_light_shape_rectangle', "Rectangle", ""),
               ]
        )

    Light_Near_Attenuation: BoolProperty(
        name="Light Uses Near Attenuation",
        options=set(),
        description="",
        default=True,
    )

    Light_Far_Attenuation: BoolProperty(
        name="Light Uses Far Attenuation",
        options=set(),
        description="",
        default=True,
    )

    Light_Near_Attenuation_Start: FloatProperty(
        name="Light Near Attenuation Start Distance",
        options=set(),
        description="The power of the light remains zero up until this point",
        default=0,
        min=0,
    )

    Light_Near_Attenuation_End: FloatProperty(
        name="Light Near Attenuation End Distance",
        options=set(),
        description="From the starting near attenuation, light power gradually increases up until the end point",
        default=0,
        min=0,
    )

    Light_Far_Attenuation_Start: FloatProperty(
        name="Light Near Attenuation Start Distance",
        options=set(),
        description="After this point, the light will begin to lose power",
        default=500,
        min=0,
    )

    Light_Far_Attenuation_End: FloatProperty(
        name="Light Near Attenuation Start Distance",
        options=set(),
        description="From the far attenuation start, the light will gradually lose power until it reaches zero by the end point",
        default=1000,
        min=0,
    )

    Light_Volume_Distance: FloatProperty(
        name="Light Volume Distance",
        options=set(),
        description="",
    )

    Light_Volume_Intensity: FloatProperty(
        name="Light Volume Intensity",
        options=set(),
        description="",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        subtype='FACTOR',
    )

    Light_Fade_Start_Distance: FloatProperty(
        name="Light Fade Out Start",
        options=set(),
        description="The light starts to fade out when the camera is x world units away",
        default=100.0,
    )

    Light_Fade_End_Distance: FloatProperty(
        name="Light Fade Out End",
        options=set(),
        description="The light completely fades out when the camera is x world units away",
        default=150.0,
    )

    Light_Ignore_BSP_Visibility: BoolProperty(
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

    Light_Intensity: FloatProperty(
        name="Light Intensity",
        options=set(),
        description="",
        default=1,
        min=0.0,
        soft_max=10.0,
        subtype='FACTOR',
    )

    Light_Use_Clipping: BoolProperty(
        name="Light Uses Clipping",
        options=set(),
        description="",
        default=False,
    )

    Light_Clipping_Size_X_Pos: FloatProperty(
        name="Light Clipping Size X Forward",
        options=set(),
        description="",
        default=100,
    )

    Light_Clipping_Size_Y_Pos: FloatProperty(
        name="Light Clipping Size Y Forward",
        options=set(),
        description="",
        default=100,
    )

    Light_Clipping_Size_Z_Pos: FloatProperty(
        name="Light Clipping Size Z Forward",
        options=set(),
        description="",
        default=100,
    )

    Light_Clipping_Size_X_Neg: FloatProperty(
        name="Light Clipping Size X Backward",
        options=set(),
        description="",
        default=100,
    )

    Light_Clipping_Size_Y_Neg: FloatProperty(
        name="Light Clipping Size Y Backward",
        options=set(),
        description="",
        default=100,
    )

    Light_Clipping_Size_Z_Neg: FloatProperty(
        name="Light Clipping Size Z Backward",
        options=set(),
        description="",
        default=100,
    )

    Light_Hotspot_Size: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=25,
    )

    Light_Hotspot_Falloff: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=80,
    )

    Light_Falloff_Shape: FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="",
        default=1,
        min=0.0,
        soft_max=10.0,
        subtype='FACTOR',
    )

    Light_Aspect: FloatProperty(
        name="Light Aspect",
        options=set(),
        description="",
        default=1,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    Light_Frustum_Width: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=1.0,
    )

    Light_Frustum_Height: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=1.0,
    )

    Light_Bounce_Ratio: FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="",
        default=1,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    Light_Dynamic_Has_Bounce: BoolProperty(
        name="Light Has Dynamic Bounce",
        options=set(),
        description="",
        default=False,
    )

    Light_Screenspace_Has_Specular: BoolProperty(
        name="Screenspace Light Has Specular",
        options=set(),
        description="",
        default=False,
    )

    def light_tag_clean_tag_path(self, context):
        self['Light_Tag_Override'] = clean_tag_path(self['Light_Tag_Override']).strip('"')

    Light_Tag_Override: StringProperty(
        name="Light Tag Override",
        options=set(),
        description="",
        update=light_tag_clean_tag_path,
    )

    def light_shader_clean_tag_path(self, context):
        self['Light_Shader_Reference'] = clean_tag_path(self['Light_Shader_Reference']).strip('"')

    Light_Shader_Reference: StringProperty(
        name="Light Shader Reference",
        options=set(),
        description="",
        update=light_shader_clean_tag_path,
    )

    def light_gel_clean_tag_path(self, context):
        self['Light_Gel_Reference'] = clean_tag_path(self['Light_Gel_Reference']).strip('"')

    Light_Gel_Reference: StringProperty(
        name="Light Gel Reference",
        options=set(),
        description="",
        update=light_gel_clean_tag_path,
    )

    def light_lens_flare_clean_tag_path(self, context):
        self['Light_Lens_Flare_Reference'] = clean_tag_path(self['Light_Lens_Flare_Reference']).strip('"')

    Light_Lens_Flare_Reference: StringProperty(
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

    Light_Near_Attenuation_StartH4: FloatProperty(
        name="Attenuation Start Distance",
        options=set(),
        description="",
        default=0.2,
        min=0,
    )

    Light_Near_Attenuation_EndH4: FloatProperty(
        name="Attenuation End Distance",
        options=set(),
        description="",
        default=10,
        min=0,
    )

    Light_Far_Attenuation_StartH4: FloatProperty(
        name="Camera Distance Fade Start",
        options=set(),
        description="",
        default=0,
        min=0,
    )

    Light_Far_Attenuation_EndH4: FloatProperty(
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
        material_path = self.shader_path.replace('"','')
        if material_path != material_path.rpartition('.')[2]:
            try:
                self.Shader_Type = material_path.rpartition('.')[2]
            except:
                self.Shader_Type = 'shader'

    shader_path: StringProperty(
        name = "Shader Path",
        description = "Define the path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Including the file extension will automatically update the shader type",
        default = "",
        update=update_shader,
        )

    shader_types = [ ('shader', "Shader", ""),
                ('shader_cortana', "Shader Cortana", ""),
                ('shader_custom', "Shader Custom", ""),
                ('shader_decal', "Shader Decal", ""),
                ('shader_foliage', "Shader Foliage", ""),
                ('shader_fur', "Shader Fur", ""),
                ('shader_fur_stencil', "Shader Fur Stencil", ""),
                ('shader_glass', "Shader Glass", ""),
                ('shader_halogram', "Shader Halogram", ""),
                ('shader_mux', "Shader Mux", ""),
                ('shader_mux_material', "Shader Mux Material", ""),
                ('shader_screen', "Shader Screen", ""),
                ('shader_skin', "Shader Skin", ""),
                ('shader_terrain', "Shader Terrain", ""),
                ('shader_water', "Shader Water", ""),
               ]

    Shader_Type: EnumProperty(
        name = "Shader Type",
        options=set(),
        description = "Set by the extension of the shader path. Alternatively this field can be updated manually",
        default = "shader",
        items=shader_types,
        )

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
    bl_parent_id = "NWO_PT_MeshDetailsPanel"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_EEVEE', 'BLENDER_WORKBENCH', 'BLENDER_WORKBENCH_NEXT'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        engine = context.engine
        return (obj and obj.type == 'MESH') and (engine in cls.COMPAT_ENGINES)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        ob = context.object
        ob_nwo = ob.nwo
        ob_nwo_face = ob.nwo_face
        col = flow.column()
        if not ob.nwo_face.toggle_face_defaults:
            col.operator('nwo_face.toggle_defaults', text='Show Defaults')
        else:
            col.operator('nwo_face.toggle_defaults', text='Hide Defaults')
            col = flow.column()
            col.prop(ob_nwo, "Face_Type", text='Face Type')
            if ob_nwo.Face_Type == '_connected_geometry_face_type_sky':
                sub = col.column(align=True)
                sub.prop(ob_nwo, "Sky_Permutation_Index", text='Sky Permutation Index')
                col.separator()

            col.prop(ob_nwo, "Face_Mode", text='Face Mode')
            col.prop(ob_nwo, "Face_Sides", text='Face Sides')
            col.prop(ob_nwo, "Face_Draw_Distance", text='Draw Distance')
            col.prop(ob_nwo, 'texcoord_usage')
            col.prop(ob_nwo, "Mesh_Tessellation_Density", text='Tessellation Density')
            if not_bungie_game():
                col.prop(ob_nwo, "Mesh_Compression", text='Compression')

            col.separator()

            col = layout.column(heading="Flags")
            sub = col.column(align=True)
            # sub.prop(ob_nwo, "Conveyor", text='Conveyor') removed as it seems non-functional. Leaving here in case conveyor functionality is ever fixed/added
            if poll_ui(('SCENARIO', 'PREFAB')):
                sub.prop(ob_nwo, "Ladder", text='Ladder')
                sub.prop(ob_nwo, "Slip_Surface", text='Slip Surface')
            sub.prop(ob_nwo, "Decal_Offset", text='Decal Offset')
            sub.prop(ob_nwo, "Group_Transparents_By_Plane", text='Group Transparents By Plane')
            sub.prop(ob_nwo, "No_Shadow", text='No Shadow')
            sub.prop(ob_nwo, "Precise_Position", text='Precise Position')
            if not_bungie_game():
                if poll_ui(('SCENARIO', 'PREFAB')):
                    sub.prop(ob_nwo, "no_lightmap")
                    sub.prop(ob_nwo, "no_pvs")
                if CheckType.poop(ob) or CheckType.default(ob):
                    sub.prop(ob_nwo, 'compress_verts')
                if CheckType.default(ob):
                    sub.prop(ob_nwo, 'uvmirror_across_entire_model')
    
        if len(ob.face_maps) <= 0:
            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            col = flow.column()
            col.operator('nwo_face.add_face_property', text='', icon='ADD')
        else:
            try:
                facemap = ob.face_maps.active

                rows = 2
                if facemap:
                    rows = 4

                row = layout.row()
                row.template_list("MESH_UL_fmaps", "", ob, "face_maps", ob.face_maps, "active_index", rows=rows)

                col = row.column(align=True)
                col.operator("nwo_face.add_face_map", icon='ADD', text="")
                col.operator("object.face_map_remove", icon='REMOVE', text="")

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
                item = ob_nwo_face.face_props[ob.face_maps.active.name]
                # row.prop(item, 'name')
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
            except:
                pass
            col.operator("nwo_face.add_face_property", text='', icon='ADD')

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


class NWO_FaceDefaultsToggle(Operator):
    """Toggles the default Face Properties display"""
    bl_idname = "nwo_face.toggle_defaults"
    bl_label = "Toggle Defaults"

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

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')

    def execute(self, context):
        ob = context.object
        bpy.ops.object.face_map_add()
        ob.face_maps[ob.face_maps.active_index].name = 'default'

        return {'FINISHED'}
    
class NWO_EditMode(Operator):
    """Switch to Edit Mode and to local view"""
    bl_idname = "nwo_face.add_face_map"
    bl_label = "Add Face Properties"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')

    def execute(self, context):
        ob = context.object
        bpy.ops.object.face_map_add()
        ob.face_maps[ob.face_maps.active_index].name = 'default'

        return {'FINISHED'}



class NWO_FacePropAdd(Operator):
    """Adds a face property that will override face properties set in the mesh"""
    bl_idname = "nwo_face.add_face_property"
    bl_label = "Add"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in ('OBJECT', 'EDIT')

    options: EnumProperty(
        default="region",
        items=[
        ('region', 'Region Override', ''),
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
        ]
        )


    def execute(self, context):
        ob = context.object
        # if no face maps, make one and assign all faces to it
        if len(ob.face_maps) < 1:
            bpy.ops.object.face_map_add()
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            bpy.ops.mesh.select_all()
            bpy.ops.object.face_map_assign()
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            ob.face_maps[0].name = 'default'
            bpy.ops.uilist.entry_add(list_path="object.nwo_face.face_props", active_index_path="object.face_maps.active_index")

        toggle_override(context, self.options, True)
        ob_nwo_face = ob.nwo_face
        item = ob_nwo_face.face_props[ob.face_maps.active_index]
        item.name = ob.face_maps.active.name
        if self.options == 'region':
            r_name = item.name.split(' ')
            item.region_name = r_name[-1].lower()
        context.area.tag_redraw()

        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
        col.prop(self, 'options', expand=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class NWO_FacePropRemove(Operator):
    """Removes a face property"""
    bl_idname = "nwo_face.remove_face_property"
    bl_label = "Remove"

    options: EnumProperty(
        default="region",
        items=[
        ('region', 'Region Override', ''),
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
        ]
        )


    def execute(self, context):
        toggle_override(context, self.options, False)
        context.area.tag_redraw()

        return {'FINISHED'}

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
        name="Region Override",
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
        description="Set the sky permutation index of this mesh. Only valid if the face type is sky",
        min=0,
    )

    conveyor: BoolProperty(
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
        description = "Makes faces slippery for units",
        default = True,
    )

    decal_offset: BoolProperty(
        name ="Decal Offset",
        options=set(),
        description = "Enable to offset these faces so that they appear to be layered on top of another face",
        default = True,
    )

    group_transparents_by_plane: BoolProperty(
        name ="Group Transparents By Plane",
        options=set(),
        description = "Enable to group transparent geometry by fitted planes",
        default = True,
    )

    no_shadow: BoolProperty(
        name ="No Shadow",
        options=set(),
        description = "Enable to prevent faces from casting shadows",
        default = True,
    )

    precise_position: BoolProperty(
        name ="Precise Position",
        options=set(),
        description = "Enable to prevent faces from being altered during the import process",
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

class NWO_FacePropertiesGroup(PropertyGroup):


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

        return False

    face_props_hack : BoolProperty(
        get=get_face_props_hack,
    )

##################################################
    
def draw_filepath(self, context):
    layout = self.layout
    row = layout.row(align=True)
    row.scale_x = 0.01
    row.scale_y = 0.01
    # this is beyond hacky... and I'm not proud... but it works!
    row.prop(context.scene.nwo_global, 'temp_file_watcher')
    row.prop(context.object.nwo_face, 'face_props_hack')

classeshalo = (
    NWO_ScenePropertiesGroup,
    NWO_SceneProps,
    NWO_SetUnitScale,
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
    NWO_ObjectMeshProps,
    NWO_ObjectMarkerProps,
    NWO_MaterialProps,
    NWO_MaterialOpenTag,
    NWO_ObjectPropertiesGroup,
    NWO_LightPropertiesGroup,
    NWO_MaterialPropertiesGroup,
    NWO_LightProps,
    NWO_LightPropsCycles,
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
    NWO_FacePropAdd,
    NWO_FacePropRemove,
    NWO_FaceMapAdd,
    NWO_FaceDefaultsToggle,
    NWO_FaceProperties_ListItems,
    NWO_FaceMapProps,
    NWO_ObjectMeshMaterialLightingProps,
    NWO_ObjectMeshLightmapProps,
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
    bpy.types.Object.nwo_face = PointerProperty(type=NWO_FacePropertiesGroup, name="Halo Face Properties", description="Set Halo Face Properties")
    bpy.types.TOPBAR_HT_upper_bar.prepend(draw_filepath)

def unregister():
    del bpy.types.Scene.nwo
    del bpy.types.Object.nwo
    del bpy.types.Light.nwo
    del bpy.types.Material.nwo
    del bpy.types.Bone.nwo
    del bpy.types.Action.nwo
    del bpy.types.Mesh.nwo
    bpy.types.TOPBAR_HT_upper_bar.remove(draw_filepath)
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)

if __name__ == '__main__':
    register()
