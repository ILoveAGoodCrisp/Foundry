"""UI for the asset editor sub-panel"""

import os
from pathlib import Path
import bpy

from ...tags.scenario import ScenarioMetadataTag

from ...icons import get_icon_id
from ... import utils
from ...props.scene import scene_specific_props

import xml.etree.ElementTree as ET
    
# class NWO_UL_ChildAsset(bpy.types.UIList):
#     def draw_item(
#         self,
#         context,
#         layout,
#         data,
#         item,
#         icon,
#         active_data,
#         active_propname,
#         index,
#     ):
#         name = item.asset_path
                
#         layout.label(text=name, icon='FILE')
#         layout.prop(item, "enabled", icon='CHECKBOX_HLT' if item.enabled else 'CHECKBOX_DEHLT', text="", emboss=False)

class NWO_OT_CopyScenario(bpy.types.Operator):
    bl_idname = "nwo.copy_scenario"
    bl_label = "Copy Scenario"
    bl_description = "Copies the referenced scenario beside the original, updates the scenario reference, sets the copy to solo, and removes its new split resources"
    bl_options = set()
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.asset_type == 'cinematic' and scene_nwo.cinematic_scenario
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        scenario = Path(utils.get_tags_path(), utils.relative_path(scene_nwo.cinematic_scenario))
        scenario_rel = utils.relative_path(scenario)
        
        if not scenario.exists():
            self.report({'WARNING'}, f"Scenario does not exist: {scenario}")
            return {'CANCELLED'}
        
        new_scenario = scenario.with_name(Path(utils.get_asset_tag(".scenario", True, True)).name)
        if new_scenario.resolve() == scenario.resolve():
            new_scenario = scenario.with_stem(f'{scenario.stem}_cinematic')
        new_scenario_rel = utils.relative_path(new_scenario)
        
        if not new_scenario.parent.exists():
            new_scenario.parent.mkdir(parents=True, exist_ok=True)
            
        with ScenarioMetadataTag(path=scenario) as scen:
            scen.save_copy_as_solo(new_scenario)
        
        if new_scenario.exists():
            scene_nwo.cinematic_scenario = str(new_scenario)
            self.report({'INFO'}, f"Copied [{scenario_rel}] to: {new_scenario_rel}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"Failed to copy [{scenario_rel}] to: {new_scenario_rel}")
            return {'CANCELLED'}
    

class NWO_OT_ImportCinematicScenario(bpy.types.Operator):
    bl_idname = "nwo.import_cinematic_scenario"
    bl_label = "Import Cinematic Scenario"
    bl_description = "Imports the cinematic scenario using the existing scenario importer options"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.asset_type != 'cinematic' or not scene_nwo.cinematic_scenario.strip():
            return False

        scenario_path = Path(utils.get_tags_path(), utils.relative_path(scene_nwo.cinematic_scenario))
        return scenario_path.exists() and scenario_path.is_file() and utils.current_project_valid()

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        from ...tools import importer as importer_module

        scene_nwo = utils.get_scene_props()
        scenario_path = Path(utils.get_tags_path(), utils.relative_path(scene_nwo.cinematic_scenario))
        if not scenario_path.exists() or not scenario_path.is_file():
            self.report({'WARNING'}, f"Scenario does not exist: {scenario_path}")
            return {'CANCELLED'}

        with ScenarioMetadataTag(path=scenario_path) as scenario:
            zone_sets = scenario.get_zone_sets_dict()

        importer_module.zone_set_items = zone_sets
        zone_set = scene_nwo.cinematic_zone_set.strip()
        if not zone_set or zone_set not in zone_sets:
            zone_set = "all_zone_sets"

        return bpy.ops.nwo.import_from_drop(
            'INVOKE_DEFAULT',
            filepath=str(scenario_path),
            tag_zone_set=zone_set,
            setup_as_asset=False,
            force_no_setup_as_asset=True,
        )

class NWO_OT_SceneSwitch(bpy.types.Operator):
    bl_idname = "nwo.scene_switch"
    bl_label = "Switch Cinematic Scene"
    bl_description = "Changes the active blender scene to the selected cinematic scene"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return len(bpy.data.scenes) > 1 and scene_nwo.cinematic_scenes

    def execute(self, context):
        nwo = utils.get_scene_props()
        cinematic_scene = nwo.cinematic_scenes[nwo.active_cinematic_scene_index]
        scene = cinematic_scene.scene
        if scene is not None:
            context.window.scene = scene
            self.report({'INFO'}, f"Scene switched to {((nwo.active_cinematic_scene_index + 1) * 10):03d} [{scene.name}]")
        return {"FINISHED"}

class NWO_OT_CinematicSceneNew(bpy.types.Operator):
    bl_idname = "nwo.cinematic_scene_new"
    bl_label = "New Cinematic Scene"
    bl_description = "Creates a new cinematic scene"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return len(scene_nwo.cinematic_scenes) < 33
    
    existing_scene: bpy.props.StringProperty(
        name="Link to Existing Scene",
        description="Links to the selected Blender scene rather than creating a new one"
    )
    
    def execute(self, context):
        existing_scene = None
        if self.existing_scene:
            existing_scene = bpy.data.scenes.get(self.existing_scene)

        nwo = utils.get_scene_props()
        cin_scene = nwo.cinematic_scenes.add()
        new_index = len(nwo.cinematic_scenes) - 1
        scene_id = f"{(new_index + 1) * 10:03d}"
        cin_scene.name = scene_id
        if existing_scene is None:
            cin_scene.scene = bpy.data.scenes.new(f"Scene {scene_id}")
        else:
            cin_scene.scene = existing_scene
            
        nwo.active_cinematic_scene_index = new_index
            
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def draw(self, context):
        self.layout.prop_search(self, "existing_scene", search_data=bpy.data, search_property="scenes")

class NWO_OT_CinematicSceneRemove(bpy.types.Operator):
    bl_idname = "nwo.cinematic_scene_remove"
    bl_label = "Remove Cinematic Scene"
    bl_description = "Remove a cinematic scene and optionally delete the blender scene"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return len(scene_nwo.cinematic_scenes) > 1 and scene_nwo.active_cinematic_scene_index < len(scene_nwo.cinematic_scenes)
    
    delete_scene: bpy.props.BoolProperty(
        name="Delete Blender Scene"
    )
    
    def execute(self, context):
        nwo = utils.get_scene_props()
        index = nwo.active_cinematic_scene_index
        
        cin_scene = nwo.cinematic_scenes[index]
        
        if self.delete_scene and cin_scene.scene and cin_scene.scene.name in bpy.data.scenes:
            bpy.data.scenes.remove(cin_scene.scene)
        
        nwo.cinematic_scenes.remove(index)
        if nwo.active_cinematic_scene_index > len(nwo.cinematic_scenes) - 1:
            nwo.active_cinematic_scene_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "delete_scene")
        
class NWO_OT_CinematicSceneMove(bpy.types.Operator):
    bl_idname = "nwo.cinematic_scene_move"
    bl_label = "Move"
    bl_description = "Moves the cinematic scene up/down the list"
    bl_options = {"UNDO"}
    
    direction: bpy.props.StringProperty()
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return len(scene_nwo.cinematic_scenes) > 1 and scene_nwo.active_cinematic_scene_index < len(scene_nwo.cinematic_scenes)

    def execute(self, context):
        nwo = utils.get_scene_props()
        cin_scenes = nwo.cinematic_scenes
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.active_cinematic_scene_index
        to_index = (current_index + delta) % len(cin_scenes)
        cin_scenes.move(current_index, to_index)
        nwo.active_cinematic_scene_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}

class NWO_UL_CinematicScenes(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        layout.alignment = 'LEFT'
        layout.label(text=f'{item.name} [{"NONE" if item.scene is None else item.scene.name}]', icon='SCENE_DATA')
        
class NWO_OT_SetMainScene(bpy.types.Operator):
    bl_idname = "nwo.set_main_scene"
    bl_label = "Set Scene as Main"
    bl_description = "Marks this scene as the main scene. The main scene holds the majority of Foundry properties. The only exceptions to this are certain cinematic properties which can be scene specific (such as the cinematic anchor and cinematic events). You only need to use this if you want to delete the current main scene without breaking Foundry properties"
    bl_options = {"UNDO"}
    
    def execute(self, context):

        main_scene_props = utils.get_scene_props()
        current_scene_props = context.scene.nwo
        
        if main_scene_props == current_scene_props:
            self.report({'INFO'}, f"Current scene [{current_scene_props.id_data.name}] is already the main scene")
        else:
            self.report({'INFO'}, f"Main scene is now {current_scene_props.id_data.name}")
            for k, v in main_scene_props.items():
                if k in scene_specific_props:
                    continue
                current_scene_props[k] = v
            
        for s in bpy.data.scenes:
            s.nwo.is_main_scene = False
            
        current_scene_props.is_main_scene = True
        
        return {'FINISHED'}
        
class NWO_OT_OpenParentAsset(bpy.types.Operator):
    bl_idname = "nwo.open_parent_asset"
    bl_label = "Open Parent Blend"
    bl_description = "Opens the parent blend file"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.parent_asset.strip()
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        asset_path = Path(scene_nwo.parent_asset)
        if asset_path.suffix != '.blend':
            asset_path = asset_path.with_suffix(".blend")
            
        relative_blend_path = utils.relative_path(asset_path)
        
        full_blend_path = Path(utils.get_data_path(), relative_blend_path)
        if not full_blend_path.exists():
            self.report({'WARNING'}, f"Blend file does not exist: {full_blend_path}")
            return {'CANCELLED'}
        
        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        bpy.ops.wm.open_mainfile(filepath=str(full_blend_path))
        return {'FINISHED'}
    
class NWO_UL_IKChain(bpy.types.UIList):
    # Called for each drawn item.
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        layout.alignment = 'LEFT'
        layout.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("ik_chain"))
        if item.start_node and item.effector_node:
            layout.label(text=f'{item.start_node} >>> {item.effector_node}')
        else:
            layout.label(text='IK Chain Bones Not Set', icon='ERROR')
        # row.prop_search(item, 'start_node', data.main_armature.data, 'bones', text='')
        # row.prop_search(item, 'effector_node', data.main_armature.data, 'bones', text='')
        
class NWO_OT_AddIKChain(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    bl_idname = 'nwo.add_ik_chain'
    bl_label = "Add"
    bl_description = "Add a new Game IK Chain"
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.main_armature

    def execute(self, context):
        nwo = utils.get_scene_props()
        chain = nwo.ik_chains.add()
        nwo.ik_chains_active_index = len(nwo.ik_chains) - 1
        chain.name = f"ik_chain_{len(nwo.ik_chains)}"
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_RemoveIKChain(bpy.types.Operator):
    bl_idname = "nwo.remove_ik_chain"
    bl_label = "Remove"
    bl_description = "Remove an IK Chain from the list."
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.ik_chains and scene_nwo.ik_chains_active_index > -1

    def execute(self, context):
        nwo = utils.get_scene_props()
        index = nwo.ik_chains_active_index
        nwo.ik_chains.remove(index)
        if nwo.ik_chains_active_index > len(nwo.ik_chains) - 1:
            nwo.ik_chains_active_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_MoveIKChain(bpy.types.Operator):
    bl_idname = "nwo.move_ik_chain"
    bl_label = "Move"
    bl_description = "Moves the IK Chain up/down the list"
    bl_options = {"UNDO"}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = utils.get_scene_props()
        chains = nwo.ik_chains
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.ik_chains_active_index
        to_index = (current_index + delta) % len(chains)
        chains.move(current_index, to_index)
        nwo.ik_chains_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}

class NWO_OT_AddBlendScreen(bpy.types.Operator):
    bl_idname = 'nwo.add_blend_screen'
    bl_label = 'Add Blend Screen'
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = utils.get_scene_props()
        screen = nwo.blend_screens.add()
        screen.name = f'blend_screen_{len(nwo.blend_screens)}'
        nwo.blend_screens_active_index = len(nwo.blend_screens) - 1
        return {'FINISHED'}

class NWO_OT_RemoveBlendScreen(bpy.types.Operator):
    bl_idname = 'nwo.remove_blend_screen'
    bl_label = 'Remove Blend Screen'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        nwo = utils.get_scene_props()
        return 0 <= nwo.blend_screens_active_index < len(nwo.blend_screens)

    def execute(self, context):
        nwo = utils.get_scene_props()
        nwo.blend_screens.remove(nwo.blend_screens_active_index)
        nwo.blend_screens_active_index = min(nwo.blend_screens_active_index,
                                             len(nwo.blend_screens) - 1)
        return {'FINISHED'}
        
class NWO_OT_ClearAsset(bpy.types.Operator):
    bl_idname = "nwo.clear_asset"
    bl_label = "Unlink Asset"
    bl_description = "Unlinks the Asset from this blend"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.sidecar_path

    def execute(self, context):
        nwo = utils.get_scene_props()
        _, asset_name = utils.get_asset_info(nwo.sidecar_path)
        nwo.sidecar_path = ""
        self.report({'INFO'}, f"Asset [{asset_name}] unlinked from file")
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, event):
        return context.window_manager.invoke_confirm(self, event)
    
# class NWO_OT_RegisterIcons(bpy.types.Operator):
#     bl_idname = "nwo.register_icons"
#     bl_label = "Reload Icons"
#     bl_description = "Reloads the Foundry icons if any failed to load at startup"
#     bl_options = {"UNDO"}

#     def execute(self, context):
#         from ... import icons
#         if icons.icons_active:
#             icons.unregister()
#         icons.register()
#         if not icons.icons_active:
#             icons.icons_activate()
            
#         return {"FINISHED"}
