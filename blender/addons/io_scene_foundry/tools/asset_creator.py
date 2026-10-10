

import os
from pathlib import Path
import traceback
import bpy

from ..export.build_sidecar import Sidecar

from ..tools.append_grid_materials import append_grid_materials
from ..tools.rigging.create_rig import add_rig
from ..tools.append_foundry_materials import add_special_materials
from ..icons import get_icon_id
from ..tools.asset_types import asset_type_items_creator
from .. import utils
from ..coordinate_system import FORWARD_ITEMS

protected_folder_names = "models", "export", "animations", "cinematics", "work", "000"

class NWO_OT_NewAsset(bpy.types.Operator):
    bl_idname = "nwo.new_asset"
    bl_label = "New Asset"
    bl_description = "Create an asset folder in data, with a matching tags folder used on export"
    bl_options = set()
    show_advanced_options: bpy.props.BoolProperty(name="Advanced Creation Options", default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.scene and utils.current_project_valid()
    
    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN"},
    )

    use_filter_folder: bpy.props.BoolProperty(default=True)

    filepath: bpy.props.StringProperty(
        name="Asset Location",
        description="Choose a parent folder inside the project's data directory",
        subtype="FILE_PATH",
    )
    
    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN'})

    def update_asset_name(self, context):
        if context.area and context.area.type == 'FILE_BROWSER':
            params = context.space_data.params
            if params and params.filename != self.filename:
                params.filename = self.filename

    filename: bpy.props.StringProperty(
        name='Asset Name', subtype='FILE_NAME', update=update_asset_name,
        description='The name of the asset folder created inside the chosen data folder',
    )

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
            if project and context.area and context.area.type == 'FILE_BROWSER':
                self.directory = project.data_directory + os.sep
                context.space_data.params.directory = bytes(project.data_directory, 'utf-8')
    
    def project_items(self, context):
        items = []
        for i, p in enumerate(utils.get_prefs().projects):
            items.append((p.project_id, p.name, f'Tags: {p.tags_directory}\nData: {p.data_directory}', utils.project_icon(context, p), i))
            
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
        name="Animation Graph Type",
        items=[
            ("first_person", "First Person", "For creating an animation graph for first person. All new animations created are automatically given the first_person mode"),
            ("standalone", "Standalone", "For creating a standalone animation graph not necessarily linked to a model. For example a graph that holds a character's vignette animations"),
        ]
    )
    
    particle_uses_custom_points: bpy.props.BoolProperty(
        name="Has Custom Emitter Shape",
        description="Generates a particle_emitter_custom_points tag for this particle model at export. This can be referenced in an effect tag as a custom emitter shape",
    )
    
    def scale_display_items(self, context):
        items = []
        items.append(('meters', 'Meters', 'Display physical distances in meters; exported size is unchanged', 'DRIVER_DISTANCE', 0))
        items.append(('world_units', 'World Units (WU)', 'Display distances in Halo world units (1 WU = 3.048 meters); exported size is unchanged', get_icon_id('wu_scale'), 1))
        return items
    
    def scale_items(self, context):
        items = []
        items.append(('blender', 'Blender', "One scene unit represents one meter", 'BLENDER', 0))
        items.append(('max', 'Halo', "One scene unit represents 0.03048 meters", get_icon_id("halo_scale"), 1))
        return items
    
    scale: bpy.props.EnumProperty(
        name="Scale",
        options=set(),
        description="Select the scaling for this asset. Scale is applied at export to ensure units displayed in Blender match with in game units",
        items=scale_items,
    )
    
    forward_direction: bpy.props.EnumProperty(
        name="Forward", options=set(), default='y-', items=FORWARD_ITEMS,
        description="Choose the forward axis for this new scene; Halo geometry uses +X forward",
    )

    def asset_location(self, project, directory=None, filename=None):
        """Resolve the asset folder beneath the browser's chosen parent."""
        filename = self.filename if filename is None else filename
        directory = self.directory if directory is None else directory
        path = Path(self.filepath or project.data_directory)
        if filename:
            asset_name = filename
            if directory:
                asset_directory = Path(directory, filename)
            else:
                asset_directory = path if path.name == filename else path / filename
        elif Path(directory or path) != Path(project.data_directory):
            asset_directory = Path(directory or path)
            asset_name = asset_directory.name
        else:
            asset_name = f"new_{self.asset_type}_asset"
            asset_directory = Path(project.data_directory, asset_name)
        return asset_name, asset_directory

    def execute(self, context):
        with utils.busy_cursor(context):
            return self.create_asset(context)

    def create_asset(self, context):
        project = utils.get_project(self.project)
        asset_name, asset_directory = self.asset_location(project)

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
                    self.report({"WARNING"}, "No automatic asset names are available. Enter a unique asset name and try again")
                    return {'CANCELLED'}
                
            asset_directory = Path(project.data_directory, asset_name)
        
        if not asset_directory.exists():
            asset_directory.mkdir(parents=True)
        
        # Create a sidecar file, this serves as a marker to check whether an asset is setup or not
        asset_path = Path(asset_directory, asset_name)
        sidecar_path_full = asset_path.with_suffix(".sidecar.xml")
        sidecar_path = sidecar_path_full.relative_to(project.data_directory)
        scene = context.scene
        scene_nwo = utils.get_scene_props()
        
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
                bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        except:
            print("Failed to save current file")
        
        # Set blender scene settings for new file
        scene.render.fps = 30
        scene.render.image_settings.tiff_codec = 'LZW'
        # Set Foundry scene settings
        utils.set_scene_project(scene_nwo, project)
        scene_nwo.sidecar_path = str(sidecar_path)
        scene_nwo.asset_type = self.asset_type
        if scene_nwo.scale != self.scale:
            scene_nwo.scale = self.scale
        scene_nwo.forward_direction = self.forward_direction
        # Model specific settings
        scene_nwo.output_biped = self.output_biped
        scene_nwo.output_crate = self.output_crate and project.game != 'halo1'
        scene_nwo.output_creature = self.output_creature
        scene_nwo.output_device_control = self.output_device_control
        scene_nwo.output_device_dispenser = self.output_device_dispenser
        scene_nwo.output_device_machine = self.output_device_machine
        scene_nwo.output_device_terminal = self.output_device_terminal and project.game not in {'halo1', 'halo2'}
        scene_nwo.output_effect_scenery = self.output_effect_scenery
        scene_nwo.output_equipment = self.output_equipment
        scene_nwo.output_giant = self.output_giant and project.game not in {'halo1', 'halo2'}
        scene_nwo.output_scenery = self.output_scenery
        scene_nwo.output_vehicle = self.output_vehicle
        scene_nwo.output_weapon = self.output_weapon
        # Animation specific settings
        scene_nwo.asset_animation_type = self.animation_type
        # Particle
        scene_nwo.particle_uses_custom_points = self.particle_uses_custom_points
        # Scenario
        # if self.asset_type == 'scenario' and len(scene_nwo.regions_table) < 2:
        #     utils.add_region('shared')
        
        # Update blend data
        if self.selected_only:
            for ob in bpy.data.objects:
                if not ob.select_get():
                    bpy.data.objects.remove(ob)
                
        if self.append_special_materials:
            add_special_materials('h4' if project.corinth else 'reach', self.asset_type)
            
        if self.append_grid_materials:
            try:
                append_grid_materials()
            except Exception as exc:
                traceback.print_exc()
                self.report({'WARNING'}, f"Could not create Grid Materials; continuing asset creation: {exc}")
        
        if self.generate_halo_skeleton:
            needs_aim_bones = self.output_biped or self.output_vehicle or scene_nwo.output_giant
            add_rig(context, needs_aim_bones)
        
        # Save the file to the asset folder
        if self.save_new_blend_file:
            bpy.ops.wm.save_as_mainfile(filepath=str(blender_filepath), check_existing=False, compress=context.preferences.filepaths.use_file_compression)
            
        sidecar = Sidecar(sidecar_path_full, sidecar_path, asset_path, asset_name, None, scene_nwo, utils.is_corinth(context), context)
        sidecar.build()
        
        self.report({"INFO"}, f"Created {self.asset_type.title()} asset '{asset_name}' for {project.name}")
        
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
        col.label(text='Choose asset location and name')
        col.prop(self, 'filename', text='Asset Name')
        col.separator()
        col.prop(self, "asset_type", text="")
        from ..ui.workflow import draw_text
        name, destination = self.asset_location(project)
        # draw_text(col, f"Data folder: {destination}", context)
        # draw_text(col, f"Asset type: {self.asset_type.replace('_', ' ').title()} · {project.game}", context)
        if not destination.resolve().is_relative_to(Path(project.data_directory).resolve()):
            draw_text(col, "Choose a destination inside this project's data folder.", context, 'ERROR')
        col.prop(self, 'save_new_blend_file')
        col.prop(self, 'selected_only', text=f'Use Only {len(context.selected_objects)} Selected Objects')
        col.prop(self, 'show_advanced_options', icon='TRIA_DOWN' if self.show_advanced_options else 'TRIA_RIGHT', emboss=False)
        if self.show_advanced_options:
            advanced = col.box()
            advanced.label(text='New Scene Convention')
            advanced.prop(self, 'scale')
            advanced.prop(self, 'forward_direction')
            advanced.prop(self, 'append_special_materials')
            advanced.prop(self, 'append_grid_materials')
            if self.asset_type == 'model':
                advanced.prop(self, 'generate_halo_skeleton')
        # draw_text(col, "Output tags determine the game object types created from this asset.", context)
        if self.asset_type == "model":
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
            if project.game != 'halo1':
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
            if project.game not in {'halo1', 'halo2'}:
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
            if project.game not in {'halo1', 'halo2'}:
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
            if project.game not in {'halo1', 'halo2'}:
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
            scene_nwo = utils.get_scene_props()
            col.prop(scene_nwo, 'scenario_type')
            col.prop(scene_nwo, 'scenario_auto_bsp_by_origin')
            
        elif self.asset_type == 'animation':
            col.prop(self, 'animation_type')
            
        elif self.asset_type == 'particle_model':
            col.prop(self, 'particle_uses_custom_points')


    def invoke(self, context, _):
        scene_nwo = utils.get_scene_props()
        self.scale = scene_nwo.scale
        self.forward_direction = scene_nwo.forward_direction
        self.output_biped = scene_nwo.output_biped
        self.output_crate = scene_nwo.output_crate
        self.output_creature = scene_nwo.output_creature
        self.output_giant = scene_nwo.output_giant
        self.output_device_control = scene_nwo.output_device_control
        self.output_device_dispenser = scene_nwo.output_device_dispenser
        self.output_device_machine = scene_nwo.output_device_machine
        self.output_device_terminal = scene_nwo.output_device_terminal
        self.output_effect_scenery = scene_nwo.output_effect_scenery
        self.output_equipment = scene_nwo.output_equipment
        self.output_scenery = scene_nwo.output_scenery
        self.output_weapon = scene_nwo.output_weapon
        self.output_vehicle = scene_nwo.output_vehicle
        
        if scene_nwo.scene_project:
            project = utils.get_project(use_external=False)
            if project is not None:
                self.project = project.project_id
            
        self.asset_type = scene_nwo.asset_type
            
        if self.project:
            project = utils.get_project(self.project)
            if bpy.data.filepath and Path(bpy.data.filepath).is_relative_to(project.data_directory):
                self.filepath = str(Path(bpy.data.filepath).parent) + os.sep
            else:
                self.filepath = project.data_directory + os.sep
            self.directory = self.filepath
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
