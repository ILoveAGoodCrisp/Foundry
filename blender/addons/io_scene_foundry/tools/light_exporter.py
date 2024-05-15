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

from pathlib import Path
import bpy
from io_scene_foundry.managed_blam.scenario_structure_lighting_info import ScenarioStructureLightingInfoTag
from io_scene_foundry.utils import nwo_utils

class Light:
    def __init__(self, ob, bsp=None, scale=None, rotation=None) -> None:
        self.data = ob.data
        self.bsp = bsp
        matrix = nwo_utils.halo_transforms(ob, scale, rotation)
        self.origin = matrix.translation.copy()
        matrix_3x3 = matrix.to_3x3().normalized()
        self.forward = matrix_3x3.col[1]
        self.up = matrix_3x3.col[2]
        
class NWO_OT_LightSync(bpy.types.Operator):
    bl_idname = "nwo.light_sync"
    bl_label = "Light Sync"
    bl_description = "Updates lighting info tags from Blender in realtime. Runs only on the selected lights"
    bl_options = {'UNDO'}
    
    cancel_sync: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        if self.cancel_sync:
            context.scene.nwo.light_sync_active = False
            return {'CANCELLED'}
        context.scene.nwo.light_sync_active = True
        wm = context.window_manager
        self.timer = wm.event_timer_add(context.scene.nwo.light_sync_rate, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        nwo = context.scene.nwo
        if not nwo.light_sync_active:
            return self.cancel(context)
        ob = context.object
        if not ob:
            return {'PASS_THROUGH'}
        selected_lights = [ob for ob in context.selected_objects if ob.type == 'LIGHT' and ob.data.type != 'AREA' and ob.nwo.exportable]
        if not selected_lights:
            return {'PASS_THROUGH'}
        if event.type == 'TIMER':
            for area in context.screen.areas:
                if area.type in ('VIEW_3D', "PROPERTIES", "OUTLINER") and mouse_in_light_editor_region(context, event.mouse_x, event.mouse_y):
                    export_lights(selected_lights, gather_lights(context))
                    return {'PASS_THROUGH'}
                
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self.timer)
        return {'FINISHED'}

def mouse_in_light_editor_region(context, x, y):
    for area in context.screen.areas:
        if area.type not in ('VIEW_3D', "PROPERTIES", "OUTLINER"):
            continue
        for region in area.regions:
            if region.type == 'WINDOW':
                if (x >= region.x and
                    y >= region.y and
                    x < region.width + region.x and
                    y < region.height + region.y):
                    return True

    return False

class NWO_OT_ExportLights(bpy.types.Operator):
    bl_idname = "nwo.export_lights"
    bl_label = "Export Lights"
    bl_description = "Exports all blender lights to their respective lighting info tags"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return nwo_utils.valid_nwo_asset(context)

    def execute(self, context):
        light_objects = gather_lights(context)
        if not light_objects:
            self.report({'INFO'}, "No lights in scene")
            return {'CANCELLED'}
        export_lights(light_objects)
        return {"FINISHED"}
    
def gather_lights(context):
    return [ob for ob in context.scene.objects if ob.type == 'LIGHT' and ob.data.type != 'AREA' and ob.nwo.exportable]

def export_lights(light_objects, all_lights=None):
    asset_path, asset_name = nwo_utils.get_asset_info()
    lights = [Light(ob, nwo_utils.true_region(ob.nwo)) for ob in light_objects]
    bsps_with_lights = {light.bsp for light in lights}
    bsps = sorted(bsps_with_lights)
    lighting_info_paths = [str(Path(asset_path, f'{asset_name}_{b}.scenario_structure_lighting_info')) for b in bsps]
    for idx, info_path in enumerate(lighting_info_paths):
        with ScenarioStructureLightingInfoTag(path=info_path) as info:
            b = bsps[idx]
            if all_lights is None:
                info.build_tag([light for light in lights if light.bsp == b])
            else:
                every_light = [Light(ob, nwo_utils.true_region(ob.nwo)) for ob in all_lights]
                info.build_tag([light for light in every_light if light.bsp == b], [light for light in lights if light.bsp == b])
