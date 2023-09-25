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
from bpy.types import Context

class NWO_MaterialSyncStart(bpy.types.Operator):
    bl_idname = "nwo.material_sync_start"
    bl_label = "Halo Material Sync Start"

    def modal(self, context, event):
        nwo = context.scene.nwo
        if not nwo.shader_sync_active:
            return self.cancel(context)
        ob = context.object
        if not ob:
            return {'PASS_THROUGH'}
        material = ob.active_material
        if not material:
            return {'PASS_THROUGH'}
        if not material.nwo.uses_blender_nodes:
            return {'PASS_THROUGH'}
        if event.type == 'TIMER':
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR' and mouse_in_node_editor(context, event.mouse_x, event.mouse_y):
                    bpy.ops.nwo.build_shader_single(linked_to_blender=True)
                    return {'PASS_THROUGH'}
                
        # if material.node_tree.nodes:
        #     # get list of node properties
        #     node_dict = {}
        #     for n in material.node_tree.nodes:
        #         if n.type in ("GROUP", "MAPPING", "TEX_IMAGE") or n.type.startswith("BSDF"):
        #             temp_list = [bool(i.links) for i in n.inputs]
        #             temp_list += [i.default_value for i in n.inputs if i.type == 'VALUE']
        #             temp_list += [i.default_value[0] for i in n.inputs if i.type == 'RGBA']
        #             temp_list += [i.default_value[1] for i in n.inputs if i.type == 'RGBA']
        #             temp_list += [i.default_value[2] for i in n.inputs if i.type == 'RGBA']
        #             if n.type == "TEX_IMAGE":
        #                 temp_list.append(n.image)

        #             node_dict[n.name] = temp_list
                    

        #     if len(self.node_dict) != len(node_dict):
        #         self.node_dict = node_dict
        #         bpy.ops.nwo.build_shader_single(linked_to_blender=True)
        #     else:
        #         for k1 in node_dict.keys():
        #             for k2 in self.node_dict.keys():
        #                 if k1 == k2:
        #                     if node_dict[k1] != self.node_dict[k2]:
        #                         self.node_dict = node_dict
        #                         bpy.ops.nwo.build_shader_single(linked_to_blender=True)
        #                     return {'PASS_THROUGH'}

        #             else:
        #                 self.node_dict = node_dict
        #                 bpy.ops.nwo.build_shader_single(linked_to_blender=True)
        #                 return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.space_data.type != 'NODE_EDITOR':
            self.report({'WARNING'}, "Material Sync must be started from the Node Editor")
            return {'CANCELLED'}
        self.node_dict = {}
        context.scene.nwo.shader_sync_active = True
        wm = context.window_manager
        self._timer = wm.event_timer_add(context.scene.nwo.material_sync_rate, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        return {'FINISHED'}
    
class NWO_MaterialSyncEnd(bpy.types.Operator):
    bl_idname = "nwo.material_sync_end"
    bl_label = "Halo Material Sync End"

    def execute(self, context: Context):
        context.scene.nwo.shader_sync_active = False
        return {'FINISHED'}
    

def mouse_in_node_editor(context, x, y):
    for area in context.screen.areas:
        if area.type not in ('NODE_EDITOR', "PROPERTIES"):
            continue
        for region in area.regions:
            if region.type == 'WINDOW':
                if (x >= region.x and
                    y >= region.y and
                    x < region.width + region.x and
                    y < region.height + region.y):
                    return True

    return False
        