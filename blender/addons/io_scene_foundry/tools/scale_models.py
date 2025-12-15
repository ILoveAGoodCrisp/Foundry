

import bpy
from bpy_extras.object_utils import object_data_add
import os
import zipfile

from ..utils import add_auto_smooth, get_scene_props, rotation_diff_from_forward, transform_scene
from ..tools.barebones_model_format import BarebonesModelFormat
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
            ("Chip", "Chip", ""),
            ("Frag Grenade", "Frag Grenade", ""),
            ("Magnum", "Magnum", ""),
            ("Assault Rifle", "Assault Rifle", ""),
            ("Energy Sword", "Energy Sword", ""),
            ("Grunt", "Grunt", ""),
            ("UNSC Army Trooper", "UNSC Army Trooper", ""),
            ("Spartan III", "Spartan III", ""),
            ("Spartan II", "Spartan II", ""),
            ("Elite", "Elite", ""),
            ("Hunter", "Hunter", ""),
            ("Barrel", "Barrel", ""),
            ("Short Jersey Barrier", "Short Jersey Barrier", ""),
            ("Jersey Barrier", "Jersey Barrier", ""),
            ("Tech Crate", "Tech Crate", ""),
            ("Packing Crate", "Packing Crate", ""),
            ("Giant Crate", "Giant Crate", ""),
            ("Ghost", "Ghost", ""),
            ("Warthog", "Warthog", ""),
            ("Pelican Dropship", "Pelican Dropship", ""),
            ("Scarab", "Scarab", ""),
            ("UNSC Frigate", "UNSC Frigate", ""),
            ("Covenant Corvette", "Covenant Corvette", ""),
            ("UNSC Cruiser", "UNSC Cruiser", ""),
            ("Covenant Battlecruiser", "Covenant Battlecruiser", ""),
            ("Covenant Supercarrier", "Covenant Supercarrier", ""),
            ("Forerunner Keyship", "Forerunner Keyship", ""),
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
        ob.nwo.scale_model = True
        scale_factor = 1
        scene_nwo = get_scene_props()
        if scene_nwo.scale == 'max':
            scale_factor = 1 / 0.03048
            
        add_auto_smooth(context, ob, apply_mod=True)
        old_loc = ob.location.copy()
        transform_scene(context, scale_factor, rotation_diff_from_forward('x', scene_nwo.forward_direction), 'x', scene_nwo.forward_direction, keep_marker_axis=False, objects=[ob], actions=[], apply_rotation=True)
        ob.location = old_loc
        
    