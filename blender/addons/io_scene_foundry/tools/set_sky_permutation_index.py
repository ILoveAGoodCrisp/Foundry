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

import os
import bpy
from io_scene_foundry.utils import nwo_utils
from io_scene_foundry.managed_blam.scenario import ScenarioTag

def set_default_sky(context, report, sky_index):
    active_bsp = context.scene.nwo.regions_table[context.scene.nwo.regions_table_active_index].name
    with ScenarioTag() as scenario:
        sky_name = scenario.set_bsp_default_sky(active_bsp, sky_index)
        if sky_name is None:
            report({'WARNING'}, f"BSP {active_bsp} not found. Could not set sky")
            return {"CANCELLED"}
        else:
            scenario.save()
        
    report({'INFO'}, f"Set sky for bsp {active_bsp} to {sky_name}")
    return {"FINISHED"}

def new_sky_material(context, report, sky_index, sky_name=None):
    if sky_index > -1:
        mat_name = '+sky' + str(sky_index)
    else:
        mat_name = '+sky'
    mat = bpy.data.materials.get(mat_name, 0)
    if not mat:
        mat = bpy.data.materials.new(mat_name)
    context.object.active_material = mat
    if sky_name is None:
        report({'INFO'}, f"Updated sky permutation index for active material")
    else:
        report({'INFO'}, f"Added new sky to scenario and updated sky permutation index for active material. Name={sky_name}, Index={str(sky_index)}")
    return {"FINISHED"}

class NWO_NewSky(bpy.types.Operator):
    bl_idname = "nwo.new_sky"
    bl_label = "New Sky"
    bl_description = "Adds a new sky to the scenario skies palette"
    
    filter_glob: bpy.props.StringProperty(
        default="*.scenery",
        options={"HIDDEN"},
    )

    filepath: bpy.props.StringProperty(
        name="filepath",
        description="Path to scenery sky",
        subtype="FILE_PATH",
    )
    
    type: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    
    @classmethod
    def poll(cls, context):
        return nwo_utils.poll_ui('SCENARIO') and nwo_utils.valid_nwo_asset(context)
    
    def execute(self, context):
        # Read the skies block
        rel_path = nwo_utils.relative_path(self.filepath)
        if not os.path.exists(nwo_utils.get_tags_path() + rel_path):
            self.report({'WARNING'}, f"Failed to add Sky. Given path is not located inside of project tags folder\nProject: {nwo_utils.get_project_path()}\nSky Tag Path: {self.filepath}")
            return {'CANCELLED'}
        with ScenarioTag() as scenario:
            sky_name, sky_index = scenario.add_new_sky(rel_path)
            scenario.save()
        if self.type == 'material' and NWO_SetSky.poll(context):
            return new_sky_material(context, self.report, sky_index, sky_name)
        elif self.type == 'bsp':
            return set_default_sky(context, self.report, sky_index)
        
        self.report({'INFO'}, f"Added new sky to scenario. Name={sky_name}, Index={str(sky_index)}")
        return {"FINISHED"}
    
    def invoke(self, context, _):
        self.filepath = nwo_utils.get_tags_path()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NWO_SetSky(bpy.types.Operator):
    bl_idname = "nwo.set_sky"
    bl_label = "Set Sky"
    bl_description = "Selects the sky to use for this material"
    bl_options = {"UNDO"}
    
    def skies_items(self, context):
        items = []
        if self.type == 'material':
            items.append(("-1", "Default", "", "", 0))
        else:
            items.append(("-1", "None", "", "", 0))
        # Read the skies block
        with ScenarioTag() as scenario:
            skies = scenario.get_skies_mapping()
        for idx, sky in enumerate(skies):
            items.append((str(idx), f'{sky} ({str(idx)})', '', idx + 1))
        
        return items
    
    scenario_skies: bpy.props.EnumProperty(
        name="Sky",
        items=skies_items,
        options={'SKIP_SAVE'}
    )
    
    type: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'}, default='material')

    @classmethod
    def poll(cls, context):
        return nwo_utils.poll_ui('SCENARIO') and nwo_utils.valid_nwo_asset(context) and context.object and context.object.active_material and context.object.active_material.name.startswith('+sky')

    def execute(self, context):
        sky_index = int(self.scenario_skies)
        return new_sky_material(context, self.report, sky_index)

    def invoke(self, context, _):
        self.sky_names = []
        if not nwo_utils.managed_blam_active():
            bpy.ops.managed_blam.init()
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'scenario_skies', text="Sky")
        layout.operator('nwo.new_sky').type = self.type
        
class NWO_SetDefaultSky(NWO_SetSky):
    bl_idname = "nwo.set_default_sky"
    bl_label = "Set BSP Sky"
    bl_description = "Sets the sky for this BSP"
    bl_options = set()
    
    type: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'}, default='bsp')

    @classmethod
    def poll(cls, context):
        return nwo_utils.poll_ui('SCENARIO') and nwo_utils.valid_nwo_asset(context) and nwo_utils.is_corinth(context)
    
    def execute(self, context):
        if self.scenario_skies == 'none':
            sky_index = -1
        else:
            sky_index = int(self.scenario_skies)
        return set_default_sky(context, self.report, sky_index)