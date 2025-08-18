from pathlib import Path
import bpy

from ...patches import ToolPatcher
from ... import utils
import os
import time

def generate_wetness(scenario_path, bsp="all"):
    os.system("cls")
    if bpy.context.scene.nwo_export.show_output:
        bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
        print(f"►►► WETNESS FARM ◄◄◄")
    
    tool_path = Path(utils.get_project_path(), "tool.exe")
    patcher = ToolPatcher(tool_path)
    patcher.reach_wetness_data()

    utils.run_tool(["wet-mask-generate", scenario_path, bsp], force_tool=True)

class NWO_OT_GenerateWetnessData(bpy.types.Operator):
    bl_idname = "nwo.generate_wetness_data"
    bl_label = "Generate Wetness Data"
    bl_description = "Generates wetness data for BSPs"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(
        name='Scenario Filepath',
        subtype='FILE_PATH',
        description="Path to the scenario tag to generate a imposters for",
        options={"HIDDEN"},
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.scenario",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    bsps: bpy.props.StringProperty(
        name="BSPs",
        description="BSPs to generate wetness data for, comma delimited. use 'all' for all BSPs",
        default="all"
    )

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()

    def execute(self, context):
        if not self.filepath or Path(self.filepath).suffix.lower() != ".scenario":
            self.report({"WARNING"}, "No scenario path given. Operation cancelled")
            return {'CANCELLED'}
        
        generate_wetness(utils.relative_path(Path(self.filepath).with_suffix("")), self.bsps)
        
        return {"FINISHED"}
    
    def invoke(self, context, event):
        tags_dir = utils.get_tags_path() + os.sep
        self.filepath = tags_dir
        if utils.valid_nwo_asset() and context.scene.nwo.asset_type == "scenario":
            asset_path, asset_name = utils.get_asset_info()
            if asset_path and asset_name:
                self.filepath = str(Path(tags_dir, asset_path, asset_name).with_suffix(".scenario"))
            
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bsps")
