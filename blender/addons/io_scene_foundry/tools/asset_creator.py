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
from pathlib import Path
import bpy
from ..tools.append_grid_materials import append_grid_materials
from ..tools.rigging.create_rig import add_rig
from ..tools.append_foundry_materials import add_special_materials
from ..icons import get_icon_id
from ..tools.asset_types import asset_type_items
from .. import utils, globals

class NWO_OT_NewAsset(bpy.types.Operator):
    bl_idname = "nwo.new_asset"
    bl_label = "New Asset"
    bl_description = "Creates a new asset. Allows exporting the asset to the game"

    @classmethod
    def poll(cls, context):
        return context.scene and utils.get_prefs().projects
    
    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN"},
    )

    use_filter_folder: bpy.props.BoolProperty(default=True)

    filepath: bpy.props.StringProperty(
        name="asset_path",
        description="Set the location of your asset",
        subtype="FILE_PATH",
    )
    
    filename: bpy.props.StringProperty()

    work_dir: bpy.props.BoolProperty(
        description="Set whether blend file should be saved to a work directory within the asset folder"
    )
    
    selected_only: bpy.props.BoolProperty(
        name="From Selection Only",
        description="Creates a new asset using only the currently selected objects"
    )
    
    asset_type: bpy.props.EnumProperty(
        name="Asset Type",
        options=set(),
        description="Asset type determines what tags are exported from the blend scene, and the options and tools accessible",
        items=asset_type_items,
    )
    
    def update_file_directory(self, context: bpy.types.Context):
        if self.project:
            project = utils.get_project(self.project)
            if project and context.area.type == 'FILE_BROWSER':
                context.space_data.params.directory = bytes(project.data_directory, 'utf-8')
    
    def project_items(self, context):
        items = []
        for i, p in enumerate(utils.get_prefs().projects):
            items.append((p.name, p.name, '', utils.project_icon(context, p), i))
            
        return items
            
    
    project: bpy.props.EnumProperty(
        name="Project",
        items=project_items,
        update=update_file_directory,
    )
    
    append_special_materials: bpy.props.BoolProperty(
        name="Append Special Materials",
        description="Appends special materials relevant to the current project and asset type to the blend file. Special materials are denoted by their '+' prefix",
        default=True,
    )
    
    append_grid_materials: bpy.props.BoolProperty(
        name="Append Grid Materials",
        description="Adds a set of pre-made grid textures for use",
        default=True,
    )
    
    generate_halo_skeleton: bpy.props.BoolProperty(
        name="Generate Halo Armature",
        description="Builds a new armature ready for Halo. If the output tags include a biped, vehicle, or giant. This armature includes aim deform and control bones"
    )
    
    output_biped: bpy.props.BoolProperty(
        name="Biped",
        description="",
        default=False,
        options=set(),
    )
    output_crate: bpy.props.BoolProperty(
        name="Crate",
        description="",
        default=False,
        options=set(),
    )
    output_creature: bpy.props.BoolProperty(
        name="Creature",
        description="",
        default=False,
        options=set(),
    )
    output_device_control: bpy.props.BoolProperty(
        name="Device Control",
        description="",
        default=False,
        options=set(),
    )
    output_device_dispenser: bpy.props.BoolProperty(
        name="Device Dispenser",
        description="",
        default=False,
        options=set(),
    )
    output_device_machine: bpy.props.BoolProperty(
        name="Device Machine",
        description="",
        default=False,
        options=set(),
    )
    output_device_terminal: bpy.props.BoolProperty(
        name="Device Terminal",
        description="",
        default=False,
        options=set(),
    )
    output_effect_scenery: bpy.props.BoolProperty(
        name="Effect Scenery",
        description="",
        default=False,
        options=set(),
    )
    output_equipment: bpy.props.BoolProperty(
        name="Equipment",
        description="",
        default=False,
        options=set(),
    )
    output_giant: bpy.props.BoolProperty(
        name="Giant",
        description="",
        default=False,
        options=set(),
    )
    output_scenery: bpy.props.BoolProperty(
        name="Scenery",
        description="",
        default=True,
        options=set(),
    )
    output_vehicle: bpy.props.BoolProperty(
        name="Vehicle",
        description="",
        default=False,
        options=set(),
    )
    output_weapon: bpy.props.BoolProperty(
        name="Weapon",
        description="",
        default=False,
        options=set(),
    )
    
    animation_type: bpy.props.EnumProperty(
        name="Animation Type",
        items=[
            ("first_person", "First Person", ""),
            ("standalone", "Standalone / Cinematic", ""),
        ]
    )
    
    particle_uses_custom_points: bpy.props.BoolProperty(
        name="Has Custom Emitter Shape",
        description="Generates a particle_emitter_custom_points tag for this particle model at export. This can be referenced in an effect tag as a custom emitter shape",
    )
    
    def scale_display_items(self, context):
        items = []
        unit_length: str = context.scene.unit_settings.length_unit
        items.append(('meters', unit_length.title(), "Meters displayed in Blender are equal to 0.328 in game world units", 'DRIVER_DISTANCE', 0))
        items.append(('world_units', 'World Units', "Meters displayed in Blender are equal to in game world units i.e. 1 Meter = 1 World Unit. Use this when you want the units displayed in blender to match the units shown in Sapien", get_icon_id('wu_scale'), 1))
        return items
    
    def scale_items(self, context):
        items = []
        items.append(('blender', 'Blender', "For working at a Blender friendly scale. Scene will be appropriately scaled at export to account for Halo's scale", 'BLENDER', 0))
        items.append(('max', 'Halo', "Scene is exported without scaling. Use this if you're working with imported 3DS Max Files, or legacy assets such as JMS/ASS files which have not been scaled down for Blender", get_icon_id("halo_scale"), 1))
        return items
    
    scale: bpy.props.EnumProperty(
        name="Scale",
        options=set(),
        description="Select the scaling for this asset. Scale is applied at export to ensure units displayed in Blender match with in game units",
        items=scale_items,
    )
    
    forward_direction: bpy.props.EnumProperty(
        name="Scene Forward",
        options=set(),
        description="The forward direction you are using for the scene. By default Halo uses X forward. Whichever option is set as the forward direction in Blender will be oriented to X forward in game i.e. a model facing -Y in Blender will face X in game",
        default="y-",
        items=[
            ("y-", "-Y", "Model is facing Y negative. This is the default for Blender"),
            ("y", "Y", "Model is facing Y positive"),
            ("x-", "-X", "Model is facing X negative"),
            ("x", "X", "Model is facing X positive. This is the default for Halo"),   
        ],
    )

    def execute(self, context):
        project = utils.get_project(self.project)
        # Work out asset name / asset directory
        if self.filename:
            asset_name = self.filename
            asset_directory = Path(self.filepath)
        elif Path(self.filepath).relative_to(Path(project.data_directory)) and self.filepath != project.data_directory:
            asset_name = Path(self.filepath).name
            asset_directory = Path(self.filepath)
        else:
            asset_name = f"new_{self.asset_type}_asset"
            asset_directory = Path(project.data_directory, asset_name)
            
        # Check that asset location is valid
        if not asset_directory.is_relative_to(Path(project.data_directory)):
            # User may have selected wrong project for path, attempt to fix
            for p in utils.get_prefs().projects:
                if asset_directory.is_relative_to(p.data_directory):
                    asset_directory = Path(project.data_directory, Path(asset_directory).relative_to(p.data_directory))
                    break
                    
            else:
                self.report({"WARNING"}, f"Invalid asset location. Please ensure your file is saved to your {self.project} data directory: [{project.data_directory}]",)
                return {'CANCELLED'}
        
        if not asset_directory.exists():
            asset_directory.mkdir(parents=True)
        
        # Create a sidecar file, this serves as a marker to check whether an asset is setup or not
        sidecar_path_full = Path(asset_directory, asset_name).with_suffix(".sidecar.xml")
        if not sidecar_path_full.exists():
            with open(sidecar_path_full, 'x') as _: pass
            
        sidecar_path = str(sidecar_path_full.relative_to(project.data_directory))
        
        if self.work_dir:
            blender_filepath = Path(asset_directory, "models", "work", asset_name).with_suffix(".blend")
        else:
            blender_filepath = Path(asset_directory, asset_name).with_suffix(".blend")
            
        parent_directory = blender_filepath.parent
        if not parent_directory.exists():
            parent_directory.mkdir(parents=True)
            
        # # Save a copy of the original blend if possible
        # if bpy.data.filepath and bpy.data.filepath != str(blender_filepath):
        #     bpy.ops.wm.save_mainfile()
        
        # Set blender scene settings for new file
        scene_settings = context.scene
        scene_settings.render.fps = 30
        scene_settings.render.image_settings.tiff_codec = 'LZW'
        # Set Foundry scene settings
        scene_settings.nwo.scene_project = project.name
        scene_settings.nwo.sidecar_path = sidecar_path
        scene_settings.nwo.asset_type = self.asset_type
        if scene_settings.nwo.scale != self.scale:
            scene_settings.nwo.scale = self.scale
        scene_settings.nwo.forward_direction = self.forward_direction
        # Model specific settings
        scene_settings.nwo.output_biped = self.output_biped
        scene_settings.nwo.output_crate = self.output_crate
        scene_settings.nwo.output_creature = self.output_creature
        scene_settings.nwo.output_device_control = self.output_device_control
        scene_settings.nwo.output_device_dispenser = self.output_device_dispenser
        scene_settings.nwo.output_device_machine = self.output_device_machine
        scene_settings.nwo.output_device_terminal = self.output_device_terminal
        scene_settings.nwo.output_effect_scenery = self.output_effect_scenery
        scene_settings.nwo.output_equipment = self.output_equipment
        scene_settings.nwo.output_giant = self.output_giant
        scene_settings.nwo.output_scenery = self.output_scenery
        scene_settings.nwo.output_vehicle = self.output_vehicle
        scene_settings.nwo.output_weapon = self.output_weapon
        # Animation specific settings
        scene_settings.nwo.asset_animation_type = self.animation_type
        # Particle
        scene_settings.nwo.particle_uses_custom_points = self.particle_uses_custom_points
        # Scenario
        if self.asset_type == 'scenario' and len(scene_settings.nwo.regions_table) < 2:
            utils.add_region('shared')
        
        # Update blend data
        if self.selected_only:
            objects_to_remove = [ob for ob in bpy.data.objects if ob not in context.selected_objects]
            for ob in objects_to_remove:
                bpy.data.objects.remove(ob)
                
        if self.append_special_materials:
            add_special_materials('h4' if project.corinth else 'reach', self.asset_type)
            
        if self.append_grid_materials:
            append_grid_materials()
        
        if self.generate_halo_skeleton:
            needs_aim_bones = self.output_biped or self.output_vehicle or self.output_giant
            add_rig(context, needs_aim_bones, True, needs_aim_bones)
        
        # Save the file to the asset folder
        bpy.ops.wm.save_as_mainfile(filepath=str(blender_filepath), check_existing=False)
        
        self.report({"INFO"}, f"Created new {self.asset_type.title()} asset for {self.project}. Asset Name = {asset_name}")
        
        # Restart Blender if the currently loaded Managedblam dll is incompatiable
        mb_path = globals.mb_path
        if mb_path:
            if not Path(mb_path).is_relative_to(Path(project.project_path)):
                utils.restart_blender()
        
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=True,
        )
        col = flow.column()
        col.scale_y = 1.25
        col.prop(self, "project", text='')
        project = utils.get_project(self.project)
        if not project: return
        col.separator()
        col.prop(self, "asset_type", text="")
        col.label(text="Scale")
        col.row().prop(self, 'scale', text=" ", expand=True)
        col.label(text="Scene Forward")
        col.row().prop(self, 'forward_direction', text=" ", expand=True)
        col.separator()
        col.prop(self, "work_dir", text="Save to work directory")
        col.prop(self, "selected_only")
        col.prop(self, 'append_special_materials')
        col.prop(self, 'append_grid_materials')
        if self.asset_type == "model":
            col.prop(self, 'generate_halo_skeleton')
            col.separator()
            col.label(text="Output Tags")
            flow = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=True,
            )
            flow.scale_x = 1
            flow.scale_y = 1
            flow.prop(
                self,
                "output_crate",
                # text="",
                icon_value=get_icon_id("crate"),
            )
            flow.prop(
                self,
                "output_scenery",
                # text="",
                icon_value=get_icon_id("scenery"),
            )
            flow.prop(
                self,
                "output_effect_scenery",
                text="Effect",
                icon_value=get_icon_id("effect_scenery"),
            )

            flow.prop(
                self,
                "output_device_control",
                text="Control",
                icon_value=get_icon_id("device_control"),
            )
            flow.prop(
                self,
                "output_device_machine",
                text="Machine",
                icon_value=get_icon_id("device_machine"),
            )
            flow.prop(
                self,
                "output_device_terminal",
                text="Terminal",
                icon_value=get_icon_id("device_terminal"),
            )
            if project.corinth:
                flow.prop(
                    self,
                    "output_device_dispenser",
                    text="Dispenser",
                    icon_value=get_icon_id("device_dispenser"),
                )

            flow.prop(
                self,
                "output_biped",
                # text="",
                icon_value=get_icon_id("biped"),
            )
            flow.prop(
                self,
                "output_creature",
                # text="",
                icon_value=get_icon_id("creature"),
            )
            flow.prop(
                self,
                "output_giant",
                # text="",
                icon_value=get_icon_id("giant"),
            )

            flow.prop(
                self,
                "output_vehicle",
                # text="",
                icon_value=get_icon_id("vehicle"),
            )
            flow.prop(
                self,
                "output_weapon",
                # text="",
                icon_value=get_icon_id("weapon"),
            )
            flow.prop(
                self,
                "output_equipment",
                # text="",
                icon_value=get_icon_id("equipment"),
            )
            
        elif self.asset_type == 'animation':
            col.prop(self, 'animation_type')
            
        elif self.asset_type == 'particle_model':
            col.prop(self, 'particle_uses_custom_points')


    def invoke(self, context, _):
        self.scale = context.scene.nwo.scale
        self.forward_direction = context.scene.nwo.forward_direction
        
        if context.scene.nwo.scene_project:
            self.project = context.scene.nwo.scene_project
            
        self.asset_type = context.scene.nwo.asset_type
            
        if self.project:
            project = utils.get_project(self.project)
            if bpy.data.filepath and Path(bpy.data.filepath).is_relative_to(project.data_directory):
                self.filepath = str(Path(bpy.data.filepath).parent) + os.sep
            else:
                self.filepath = project.data_directory + os.sep
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}