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
from bpy_extras.object_utils import object_data_add
import os
from mathutils import Matrix, Vector # Don't remove this!!
import zipfile


def add_scale_model(self, context):
    if self.unit == "biped":
        if self.game == "reach":
            model = self.biped_model_reach
        elif self.game == "h4":
            model = self.biped_model_h4
        else:
            model = self.biped_model_h2a
    else:
        if self.game == "reach":
            model = self.vehicle_model_reach
        elif self.game == "h4":
            model = self.vehicle_model_h4
        else:
            model = self.vehicle_model_h2a

    script_file = os.path.realpath(__file__)
    addon_dir = os.path.dirname(os.path.dirname(script_file))
    resources_zip = os.path.join(addon_dir, "resources.zip")

    file = os.path.join(addon_dir, "resources", self.game, model + ".txt")
    if os.path.exists(file):
        write_data(self, context, model, file)
    elif os.path.exists(resources_zip):
        os.chdir(addon_dir)
        file_relative = f"{self.game}/{model}.txt"
        with zipfile.ZipFile(resources_zip, "r") as zip:
            file = zip.extract(file_relative)
            write_data(self, context, model, file)

        os.remove(file)
        os.rmdir(os.path.dirname(file))
    else:
        print("Resouces not found")
        return {"CANCELLED"}

    return {"FINISHED"}


def write_data(self, context, model, file):
    with open(file, "r") as f:
        verts_str = f.readline()
        faces_str = f.readline()

    verts = eval(verts_str)
    faces = eval(faces_str)

    mesh = bpy.data.meshes.new(name=model)
    mesh.from_pydata(verts, [], faces)
    if context.scene.nwo.scale == 'blender':
        mesh.transform(Matrix.Scale(0.03048, 4))    
    
    ob = object_data_add(context, mesh, operator=self)
    ob.nwo.export_this = False

# def apply_auto_smooth(ob: bpy.types.Object):
#     mod = ob.modifiers.new(name='auto_smooth', type='NODES')
#     node_tree = bpy.data.node_groups.get('Smooth by Angle')
#     if not node_tree:
#         node_tree = add_smooth_by_angle_nodes()
              
# def add_smooth_by_angle_nodes():
#     node_tree = bpy.data.node_groups.new(name='Smooth by Angle', type='GeometryNodeTree')
#     nodes = node_tree.nodes
#     group_output = nodes.new(type='GROUP_OUTPUT')
    
#     set_shade_smooth_face = nodes.new(type='GeometryNodeInputShadeSmooth')
#     set_shade_smooth_face.domain = 'FACE'
#     set_shade_smooth_face.inputs[2].default_value = True
    
#     node_tree.links.new(group_output, set_shade_smooth)
    
#     set_shade_smooth_edge = nodes.new(type='GeometryNodeInputShadeSmooth')
#     set_shade_smooth_edge.domain = 'EDGE'
    
#     edge_angle = nodes.new(type='NodeGroupInput')
#     group_input_angle = nodes.new(type='GeometryNodeInputMeshEdgeAngle')
#     group_input_angle.outputs[0].
#     is_face_smooth = nodes.new(type='GeometryNodeInputShadeSmooth')
#     group_input_ignore_sharpness = nodes.new(type='NodeGroupInput')
    
    