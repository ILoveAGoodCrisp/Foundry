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
from bpy_extras.object_utils import object_data_add
import os
import zipfile

from io_scene_foundry.utils.nwo_utils import add_auto_smooth, rotation_diff_from_forward, transform_scene
from io_scene_foundry.utils.barebones_model_format import BarebonesModelFormat
from bpy_extras.object_utils import AddObjectHelper

class NWO_OT_AddScaleModel(bpy.types.Operator, AddObjectHelper):
    bl_idname = "nwo.add_scale_model"
    bl_label = "Add Halo Scale Model"
    bl_description = "Adds a Halo scale model to the scene"
    bl_options = {"REGISTER", "UNDO"}
    
    model_name: bpy.props.EnumProperty(
        name="Name",
        default="Spartan III",
        items=[
            ("Data Crystal Chip", "Data Crystal Chip", ""),
            ("M9 Fragmentation Grenade", "M9 Fragmentation Grenade", ""),
            ("M6G Magnum", "M6G Magnum", ""),
            ("MA37 Assault Rifle", "MA37 Assault Rifle", ""),
            ("Energy Sword", "Energy Sword", ""),
            ("Unggoy (Grunt)", "Unggoy (Grunt)", ""),
            ("UNSC Army Trooper", "UNSC Army Trooper", ""),
            ("Spartan III", "Spartan III", ""),
            ("Spartan II", "Spartan II", ""),
            ("Sangheili (Elite)", "Sangheili (Elite)", ""),
            ("Mgalekgolo (Hunter)", "Mgalekgolo (Hunter)", ""),
            ("Karo'etba-Pattern Ghost", "Karo'etba-Pattern Ghost", ""),
            ("M12 Warthog", "M12 Warthog", ""),
            ("D77-TC Pelican", "D77-TC Pelican", ""),
            ("Deutoros-Pattern Scarab", "Deutoros-Pattern Scarab", ""),
            ("Stalwart-Class Light Frigate", "Stalwart-Class Light Frigate", ""),
            ("Ceudar-Pattern Heavy Corvette", "Ceudar-Pattern Heavy Corvette", ""),
            ("Halcyon-Class Light Cruiser", "Halcyon-Class Light Cruiser", ""),
            ("Ket-Pattern Battlecruiser", "Ket-Pattern Battlecruiser", ""),
            ("Sh'wada-Pattern Supercarrier", "Sh'wada-Pattern Supercarrier", ""),
            ("Supernal Spiral-Class Keyship", "Supernal Spiral-Class Keyship", ""),
            ("Planet Reach", "Planet Reach", ""),    
        ]
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        self.add_scale_model(context)
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "model_name", text="Model")
        layout.separator()
        layout.prop(self, "align")
        layout.prop(self, "location")
        layout.prop(self, "rotation")
    
    def add_scale_model(self, context):
        script_file = os.path.realpath(__file__)
        addon_dir = os.path.dirname(os.path.dirname(script_file))
        resources_zip = os.path.join(addon_dir, "resources.zip")

        filepath = os.path.join(addon_dir, "resources", "scale_models", self.model_name + '.bmf')
        print(filepath)
        if os.path.exists(filepath):
            self.write_data(context, filepath)
        elif os.path.exists(resources_zip):
            os.chdir(addon_dir)
            file_relative = f"scale_models/{self.model_name}.bmf"
            with zipfile.ZipFile(resources_zip, "r") as zip:
                filepath = zip.extract(file_relative)
                self.write_data(context, filepath)

            os.remove(filepath)
            os.rmdir(os.path.dirname(filepath))
        else:
            print("Resources not found")
            return {"CANCELLED"}

        return {"FINISHED"}

    def write_data(self, context, filepath):
        name = self.model_name
        model = BarebonesModelFormat()
        model.from_file(filepath)
        ob = object_data_add(context, model.to_mesh(name), operator=self, name=name)
        ob.nwo.export_this = False
        scale_factor = 1
        if context.scene.nwo.scale == 'max':
            scale_factor = 1 / 0.03048
            
        add_auto_smooth(context, ob, apply_mod=True)
        old_loc = ob.location.copy()
        transform_scene(context, scale_factor, rotation_diff_from_forward('x', context.scene.nwo.forward_direction), 'x', context.scene.nwo.forward_direction, keep_marker_axis=False, objects=[ob], actions=[], apply_rotation=True)
        ob.location = old_loc
        
    