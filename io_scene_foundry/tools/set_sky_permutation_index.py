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
from io_scene_foundry.utils import nwo_utils
from io_scene_foundry.managed_blam.scenario import ScenarioTag

def new_sky_material(context, report, sky_index, sky_name=None):
    mat_name = '+sky' + str(sky_index)
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
    bl_options = {"UNDO"}
    
    filter_glob: bpy.props.StringProperty(
        default="*.scenery",
        options={"HIDDEN"},
    )

    filepath: bpy.props.StringProperty(
        name="filepath",
        description="Path to scenery sky",
        subtype="FILE_PATH",
    )
    
    set_sky_perm: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})
    
    @classmethod
    def poll(cls, context):
        return nwo_utils.poll_ui('SCENARIO') and nwo_utils.valid_nwo_asset(context)
    
    def execute(self, context):
        # Read the skies block
        with ScenarioTag() as tag:
            sky_name, sky_index = tag.add_new_sky(self.filepath)
            tag.save()
        if self.set_sky_perm and NWO_SetSky.poll(context):
            return new_sky_material(context, self.report, sky_index, sky_name)
        self.report({'INFO'}, f"Added new sky to scenario. Name={sky_name}, Index={str(sky_index)}")
        return {"FINISHED"}
    
    def invoke(self, context, _):
        self.filepath = nwo_utils.get_tags_path()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NWO_SetSky(bpy.types.Operator):
    bl_idname = "nwo.set_sky"
    bl_label = "Set Sky"
    bl_description = "Selects the sky to use for this material, adding it to "
    bl_options = {"REGISTER", "UNDO"}
    
    def skies_items(self, context):
        items = [("none", "Use BSP Default Sky", "", "", 0)]
        # Read the skies block
        with ScenarioTag() as tag:
            skies = tag.get_skies_mapping()
            if hasattr(self, 'sky_names'):
                self.sky_names = skies
        for idx, sky in enumerate(skies):
            items.append((str(idx), f'{sky} ({str(idx)})', "", idx + 1))
            
        return items
    
    scenario_skies: bpy.props.EnumProperty(
        name="Sky",
        items=skies_items,
    )

    @classmethod
    def poll(cls, context):
        return nwo_utils.poll_ui('SCENARIO') and nwo_utils.valid_nwo_asset(context) and context.object and context.object.active_material and context.object.active_material.name.startswith('+sky')

    def execute(self, context):
        self.sky_names = []
        sky_index = int(self.scenario_skies)
        return new_sky_material(context, self.report, sky_index)

    def invoke(self, context, _):
        if not nwo_utils.managed_blam_active():
            bpy.ops.managed_blam.init()
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'scenario_skies', text="Sky")
        layout.operator('nwo.new_sky').set_sky_perm = True