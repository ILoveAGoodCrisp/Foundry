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

import bpy


class NWO_JoinHalo(bpy.types.Operator):
    bl_idname = "nwo.join_halo"
    bl_label = "Join two or more halo mesh objects"
    bl_description = "Joins objects and face layer properties"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        active = context.object
        non_active_objects = (ob for ob in context.selected_objects if ob != active and ob.type == 'MESH')
        face_layers = yield_face_layers(non_active_objects)
        for old_layer in face_layers:
            new_layer = active.data.nwo.face_props.add()
            update_layer_props(new_layer, old_layer)

        bpy.ops.object.join()

        return {"FINISHED"}
    
def yield_face_layers(objects):
    for ob in objects:
        for layer in ob.data.nwo.face_props:
            yield layer

def update_layer_props(new_layer, old_layer):
    for k,v in old_layer.items():
        new_layer.__setattr__(k, v)