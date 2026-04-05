

from pathlib import Path

import bpy
from bpy_extras.object_utils import object_data_add
import os
import zipfile

from ..utils import add_auto_smooth, get_scene_props, rotation_diff_from_forward, transform_scene
from ..tools.barebones_model_format import BarebonesModelFormat
from bpy_extras.object_utils import AddObjectHelper

from .. import utils


class NWO_OT_AddScaleModel(bpy.types.Operator, AddObjectHelper):
    bl_idname = "nwo.add_scale_model"
    bl_label = "Add Halo Scale Model"
    bl_description = "Adds a Halo scale model to the scene"
    bl_options = {"REGISTER", "UNDO"}
    
    def get_model_items(self, context):
        items = []
        scale_models = Path(utils.addon_root(), "resources", "scale_models")
        for file in scale_models.iterdir():
            items.append((str(file), utils.formalise_string(file.with_suffix("").name), ""))
            
        return items
    
    model_name: bpy.props.EnumProperty(
        name="Name",
        items=get_model_items,
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
        filepath = self.model_name
        if os.path.exists(filepath):
            self.write_data(context, filepath)
        else:
            print("File not found")
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
        
    