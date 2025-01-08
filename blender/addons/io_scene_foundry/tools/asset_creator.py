

import os
from pathlib import Path
import bpy

from ..export.build_sidecar import Sidecar

from .. import managed_blam
from ..tools.append_grid_materials import append_grid_materials
from ..tools.rigging.create_rig import add_rig
from ..tools.append_foundry_materials import add_special_materials
from ..icons import get_icon_id
from ..tools.asset_types import asset_type_items_creator
from .. import utils

protected_folder_names = "models", "export", "animations", "cinematics", "work"

class NWO_OT_NewChildAsset(bpy.types.Operator):
    bl_idname = "nwo.new_child_asset"
    bl_label = "New Child Asset"
    bl_description = "Creates a new child asset linked to this blend"
    bl_options = set()
    
    @classmethod
    def poll(cls, context):
        return context.scene and utils.valid_nwo_asset(context)
    
    name: bpy.props.StringProperty(
        name="Name",
        description="Name of the child asset. This name will be given to both the directory and blend created"
    )
    
    child_type: bpy.props.IntProperty(options={'HIDDEN'}) # int enum representing the AssetType class
    
    copy_type: bpy.props.EnumProperty(
        name="Objects to Copy",
        description="Select which objects to copy over to the new blend",
        items=[
            ('ALL', "All", "An exact copy of this scene is made and copied to the new blend"),
            ('SELECTED', "Selected", "Only selected objects (and their associated data) are copied to the new blend"),
            ('NONE', "None", "The new blend is a clean slate, albeit adopting the asset settings from the current file"),
        ]
    )
    
    load: bpy.props.BoolProperty(
        name="Load New Blend",
        description="Will open the new blend instead of staying with the current one",
    )
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "name")
        layout.prop(self, "copy_type", expand=True)
        layout.prop(self, "load")
    
    def execute(self, context):
        asset_directory = Path(utils.get_asset_path_full())
        sidecar_path = Path(utils.relative_path(Path(asset_directory, f"{asset_directory.name}.sidecar.xml")))
        name = self.name
        if not name:
            name = "010"
        child_asset_dir = Path(asset_directory, name)
        asset_num = 0
        while child_asset_dir.exists():
            asset_num += 10
            name = f"{asset_num:03}"
            child_asset_dir = Path(asset_directory, name)
            if asset_num > 999:
                self.report({"WARNING"}, f"Failed to create child asset. What have you done")
                return {'CANCELLED'}
        
        
        child_asset_dir.mkdir()
            
        child_asset_blend = Path(child_asset_dir, f"{name}.blend")
        current_file = bpy.data.filepath
        
        child_sidecar_path = Path(child_asset_dir, f"{name}.sidecar.xml")
        child_sidecar_path_relative = Path(utils.relative_path(child_sidecar_path))
        
        child_assets = context.scene.nwo.child_assets
        new_asset = child_assets.add()
        new_asset.sidecar_path = str(child_sidecar_path_relative)
        
        bpy.ops.wm.save_mainfile()
        
        bpy.ops.wm.save_as_mainfile(filepath=str(child_asset_blend), copy=False)
        
        if not child_asset_blend.exists():
            if bpy.data.filepath == current_file:
                child_assets.remove(len(child_assets) - 1)
            self.report({"WARNING"}, f"Failed to create new blend: {child_asset_blend}")
            return {'CANCELLED'}
        
        # We're now in the new file
        while context.scene.nwo.child_assets:
            context.scene.nwo.child_assets.remove(0)
            
        context.scene.nwo.is_child_asset = True
        context.scene.nwo.parent_asset = str(sidecar_path.with_suffix(""))
        
        sidecar = Sidecar(child_sidecar_path, child_sidecar_path_relative, child_asset_dir, child_asset_dir.name, None, context.scene.nwo, utils.is_corinth(context), context)
        sidecar.build()

        match self.copy_type:
            case 'SELECTED':
                for ob in bpy.data.objects:
                    if not ob.select_get():
                        bpy.data.objects.remove(ob)
                bpy.ops.outliner.orphans_purge(do_recursive=True)
                
            case 'NONE':
                for ob in bpy.data.objects:
                    bpy.data.objects.remove(ob)
                bpy.ops.outliner.orphans_purge(do_recursive=True)
        
        bpy.ops.wm.save_mainfile()
        
        if self.load:
            context.area.tag_redraw()
        else:
            # hop back to the original file unless the user selected to stay
            bpy.ops.wm.open_mainfile(filepath=current_file)
        
        self.report({'INFO'}, f"Created new child asset: {child_asset_blend}")
        return {'FINISHED'}

class NWO_OT_NewAsset(bpy.types.Operator):
    bl_idname = "nwo.new_asset"
    bl_label = "New Asset"
    bl_description = "Creates a new asset. Allows exporting the asset to the game"
    bl_options = set()

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

    # work_dir: bpy.props.BoolProperty( # Removed 08/01/2025. Asset philosophy is that the blend exists in the asset root as it IS the asset. Work dir should be for files that contribute to the asset
    #     description="Set whether blend file should be saved to a work directory within the asset folder"
    # )
    
    selected_only: bpy.props.BoolProperty(
        name="From Selection Only",
        description="Creates a new asset using only the currently selected objects"
    )
    
    asset_type: bpy.props.EnumProperty(
        name="Asset Type",
        options=set(),
        description="Asset type determines what tags are exported from the blend scene, and the options and tools accessible",
        items=asset_type_items_creator,
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
    
    save_new_blend_file: bpy.props.BoolProperty(
        name="Save new Blend File",
        description="Saves the blend as a new file in the asset directory",
        default=True,
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
            
        if asset_directory == Path(project.data_directory):
            asset_num = 0
            asset_name = f"asset_{asset_num:03}"
            while Path(project.data_directory, asset_name).exists():
                asset_num += 1
                asset_name = f"asset_{asset_num:03}"
                if asset_num > 999:
                    self.report({"WARNING"}, f"Failed to create asset. What have you done")
                    return {'CANCELLED'}
                
            asset_directory = Path(project.data_directory, asset_name)
        
        if not asset_directory.exists():
            asset_directory.mkdir(parents=True)
        
        # Create a sidecar file, this serves as a marker to check whether an asset is setup or not
        asset_path = Path(asset_directory, asset_name)
        sidecar_path_full = asset_path.with_suffix(".sidecar.xml")
        sidecar_path = sidecar_path_full.relative_to(project.data_directory)
        scene_settings = context.scene
        
        # if self.work_dir:
        #     blender_filepath = Path(asset_directory, "models", "work", asset_name).with_suffix(".blend")
        # else:
        blender_filepath = Path(asset_directory, asset_name).with_suffix(".blend")
            
        parent_directory = blender_filepath.parent
        if not parent_directory.exists():
            parent_directory.mkdir(parents=True)
            
        # # Save a copy of the original blend if possible
        try:
            if bpy.data.filepath and bpy.data.filepath != str(blender_filepath):
                bpy.ops.wm.save_mainfile()
        except:
            print("Failed to save current file")
        
        # Set blender scene settings for new file
        scene_settings.render.fps = 30
        scene_settings.render.image_settings.tiff_codec = 'LZW'
        # Set Foundry scene settings
        scene_settings.nwo.scene_project = project.name
        scene_settings.nwo.sidecar_path = str(sidecar_path)
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
        # if self.asset_type == 'scenario' and len(scene_settings.nwo.regions_table) < 2:
        #     utils.add_region('shared')
        
        # Update blend data
        if self.selected_only:
            for ob in bpy.data.objects:
                if not ob.select_get():
                    bpy.data.objects.remove(ob)
                
        if self.append_special_materials:
            add_special_materials('h4' if project.corinth else 'reach', self.asset_type)
            
        if self.append_grid_materials:
            append_grid_materials()
        
        if self.generate_halo_skeleton:
            needs_aim_bones = self.output_biped or self.output_vehicle or self.output_giant
            add_rig(context, needs_aim_bones, True)
        
        # Save the file to the asset folder
        if self.save_new_blend_file:
            bpy.ops.wm.save_as_mainfile(filepath=str(blender_filepath), check_existing=False)
            
        sidecar = Sidecar(sidecar_path_full, sidecar_path, asset_path, asset_name, None, scene_settings.nwo, utils.is_corinth(context), context)
        sidecar.build()
        
        self.report({"INFO"}, f"Created new {self.asset_type.title()} asset for {self.project}. Asset Name = {asset_name}")
        
        # Restart Blender if the currently loaded Managedblam dll is incompatiable
        mb_path = managed_blam.mb_path
        if mb_path:
            if not Path(mb_path).is_relative_to(Path(project.project_path)):
                utils.restart_blender()
        
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
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
        col.prop(self, 'save_new_blend_file')
        # col.prop(self, "work_dir", text="Save to work directory")
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
            
        elif self.asset_type == 'scenario':
            col.prop(context.scene.nwo, 'scenario_type')
            
        elif self.asset_type == 'animation':
            col.prop(self, 'animation_type')
            
        elif self.asset_type == 'particle_model':
            col.prop(self, 'particle_uses_custom_points')


    def invoke(self, context, _):
        self.scale = context.scene.nwo.scale
        self.forward_direction = context.scene.nwo.forward_direction
        self.output_biped = context.scene.nwo.output_biped
        self.output_crate = context.scene.nwo.output_crate
        self.output_creature = context.scene.nwo.output_creature
        self.output_giant = context.scene.nwo.output_giant
        self.output_device_control = context.scene.nwo.output_device_control
        self.output_device_dispenser = context.scene.nwo.output_device_dispenser
        self.output_device_machine = context.scene.nwo.output_device_machine
        self.output_device_terminal = context.scene.nwo.output_device_terminal
        self.output_effect_scenery = context.scene.nwo.output_effect_scenery
        self.output_equipment = context.scene.nwo.output_equipment
        self.output_scenery = context.scene.nwo.output_scenery
        self.output_weapon = context.scene.nwo.output_weapon
        self.output_vehicle = context.scene.nwo.output_vehicle
        
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