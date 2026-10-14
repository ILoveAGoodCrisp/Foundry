

import os
import json
from pathlib import Path
import traceback
import bpy

from ..export.build_sidecar import Sidecar

from ..tools.append_grid_materials import append_grid_materials
from ..tools.rigging.create_rig import add_rig
from ..tools.append_foundry_materials import add_special_materials
from ..icons import get_icon_id
from ..tools.asset_types import OBJECT_TYPE_DESCRIPTIONS, SUPPORTED_ASSETS, asset_type_items_creator
from .asset_creation import (MODEL_OUTPUTS, asset_folders,
                             suggested_parent, name_error, name_suggestion, resolve_parent,
                             existing_asset, reuse_candidate, folder_conflict,
                             template_tag_extensions, resolve_template_tag)
from .. import utils
from ..coordinate_system import FORWARD_ITEMS
from ..project_config import asset_parent_folder

_last_asset_parents = {}
_project_items_cache = []
_preset_items_cache = {}


def default_asset_directory(operator, project):
    prefix = getattr(project, 'default_asset_folder', '')
    key = (operator.project, operator.asset_type, operator.object_type, prefix)
    default = asset_parent_folder(prefix, suggested_parent(operator.asset_type, operator.object_type))
    parent = _last_asset_parents.get(key, default)
    if prefix and not Path(parent).is_relative_to(Path(asset_parent_folder(prefix, ''))):
        parent = default
    return str(Path(project.data_directory, parent))


def _wizard_settings(operator):
    return {name: getattr(operator, name) for name in NWO_OT_NewAsset.__annotations__
            if name not in {'wizard_initialized', 'suggested_directory', 'suggested_template_project'}}


def _reopen_wizard(settings, window, area):
    """Wait for the popup/file browser to close before restoring the wizard."""
    settings['resume_wizard'] = True
    def reopen():
        if not any(item == window for item in bpy.context.window_manager.windows):
            return
        target = next((item for item in window.screen.areas if item == area), None)
        if target is None:
            target = next((item for item in window.screen.areas if item.type == 'VIEW_3D'), None)
        if target is not None:
            with bpy.context.temp_override(window=window, area=target):
                bpy.ops.nwo.new_asset('INVOKE_DEFAULT', **settings)
    bpy.app.timers.register(reopen, first_interval=0.01)

class NWO_OT_NewAsset(bpy.types.Operator):
    bl_idname = "nwo.new_asset"
    bl_label = "New Asset"
    bl_description = "Create an asset folder in data, with a matching tags folder used on export"
    bl_options = set()
    show_advanced_options: bpy.props.BoolProperty(name="Advanced Creation Options", default=False, options={'SKIP_SAVE'})
    resume_wizard: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    wizard_initialized: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    wizard_moved: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    wizard_left: bpy.props.FloatProperty(options={'HIDDEN', 'SKIP_SAVE'})
    wizard_top: bpy.props.FloatProperty(options={'HIDDEN', 'SKIP_SAVE'})
    suggested_directory: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    reuse_existing_folder: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    wizard_step: bpy.props.EnumProperty(
        items=[('TYPE', '1  Asset type', 'Choose the project and asset type'),
               ('LOCATION', '2  Name & location', 'Name the asset and choose its parent folder'),
               ('SETUP', '3  Setup & create', 'Choose the starting scene and review the destination')],
        default='TYPE', options={'SKIP_SAVE'},
    )
    def update_source(self, context):
        self.selected_only = self.source_mode == 'SELECTED'

    source_mode: bpy.props.EnumProperty(
        name='Start with', default='CURRENT', update=update_source,
        items=[('CURRENT', 'Current scene', 'Use the current scene'),
               ('SELECTED', 'Selected objects', 'Copy selected objects into a separate asset scene'),
               ('EMPTY', 'Empty scene', 'Start with an empty asset scene'),
               ('TAG', 'Existing asset tag', 'Import an existing tag into a clean asset scene')],
    )

    def reset_reuse(self, context):
        if getattr(self, 'wizard_initialized', False):
            self.reuse_existing_folder = False

    def update_destination(self, context):
        if not getattr(self, 'wizard_initialized', False):
            return
        self.reuse_existing_folder = False
        project = utils.get_project(self.project, use_external=False)
        if project is not None:
            previous = self.suggested_directory
            if not self.directory or self.directory == previous:
                self.directory = default_asset_directory(self, project)
                self.suggested_directory = self.directory

    def object_type_items(self, context):
        project = utils.get_project(self.project, use_external=False)
        game = project.game if project else 'reach'
        excluded = set()
        if game == 'halo1':
            excluded.add('crate')
        if game in {'halo1', 'halo2'}:
            excluded.update(('device_terminal', 'giant', 'effect_scenery'))
        if game not in {'halo4', 'halo2a'}:
            excluded.add('device_dispenser')
        if game not in _preset_items_cache:
            _preset_items_cache[game] = [
                (name, name.replace('_', ' ').title(), OBJECT_TYPE_DESCRIPTIONS[name], index)
                for index, name in enumerate(MODEL_OUTPUTS) if name not in excluded
            ] + [('custom', 'Custom outputs', OBJECT_TYPE_DESCRIPTIONS['custom'], len(MODEL_OUTPUTS))]
        return _preset_items_cache[game]

    def update_object_type(self, context):
        if self.object_type != 'custom':
            for name in MODEL_OUTPUTS:
                setattr(self, 'output_' + name, name == self.object_type)
        NWO_OT_NewAsset.update_destination(self, context)

    object_type: bpy.props.EnumProperty(name='Object type', items=object_type_items,
                                        update=update_object_type)
    scenario_type: bpy.props.EnumProperty(
        name='Scenario type', items=[('solo', 'Singleplayer', ''),
                                    ('multiplayer', 'Multiplayer', ''),
                                    ('main menu', 'Main Menu', '')])
    scenario_auto_bsp_by_origin: bpy.props.BoolProperty(name='Create BSPs by origin')

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
    
    directory: bpy.props.StringProperty(name='Create in — parent folder', subtype='NONE',
        description="Parent folder beneath the project's data directory; Foundry creates the asset folder",
        update=reset_reuse)

    def update_asset_name(self, context):
        if getattr(self, 'wizard_initialized', False):
            self.reuse_existing_folder = False
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
        update=update_destination,
    )
    
    def update_file_directory(self, context: bpy.types.Context):
        if self.project:
            project = utils.get_project(self.project, use_external=False)
            if project and self.asset_type not in SUPPORTED_ASSETS.get(project.game, {self.asset_type}):
                self.asset_type = 'model'
            if project and getattr(self, 'wizard_initialized', False):
                if self.object_type not in {item[0] for item in NWO_OT_NewAsset.object_type_items(self, context)}:
                    self.object_type = 'scenery'
                self.directory = default_asset_directory(self, project)
                self.suggested_directory = self.directory
                self.reuse_existing_folder = False
                if self.template_project == self.suggested_template_project:
                    self.template_project = self.project
                    self.suggested_template_project = self.project
    
    def project_items(self, context):
        items = []
        for i, p in enumerate(utils.get_prefs().projects):
            items.append((p.project_id, p.name, f'Tags: {p.tags_directory}\nData: {p.data_directory}', utils.project_icon(context, p), i))
            
        _project_items_cache[:] = items
        return _project_items_cache
            
    
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
        default=False,
    )
    
    generate_halo_skeleton: bpy.props.BoolProperty(
        name="Generate Halo Armature",
        description="Builds a new armature ready for Halo. If the output tags include a biped, vehicle, or giant. This armature includes aim deform and control bones"
    )
    
    save_new_blend_file: bpy.props.BoolProperty(
        name="Save Blend file in the asset folder",
        description="Save the Blend under the asset's name. Disable to keep its current location without saving it",
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

    def update_template_project(self, context):
        if self.wizard_initialized:
            self.template_tag = ''

    template_project: bpy.props.EnumProperty(
        name='Source project', items=project_items, update=update_template_project,
        description='Project containing the existing asset tag')
    suggested_template_project: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    template_tag: bpy.props.StringProperty(
        name='Asset tag', description="Tag path relative to the source project's tags folder")

    def template_extensions(self):
        source = utils.get_project(self.template_project, use_external=False)
        if source is None or self.asset_type not in SUPPORTED_ASSETS.get(source.game, set()):
            return ()
        outputs = tuple(name for name in MODEL_OUTPUTS if getattr(self, 'output_' + name))
        return template_tag_extensions(source.game, self.asset_type, self.object_type, outputs)

    def template_path(self):
        source = utils.get_project(self.template_project, use_external=False)
        if source is None:
            raise ValueError('Choose a valid source project for the asset tag.')
        return resolve_template_tag(source.tags_directory, self.template_tag, self.template_extensions())

    def asset_location(self, project, directory=None, filename=None):
        name = self.filename if filename is None else filename
        directory = (self.directory or self.filepath) if directory is None else directory
        root, parent = resolve_parent(project.data_directory, directory)
        candidate = reuse_candidate(parent, name, root) if name else None
        destination = candidate if getattr(self, 'reuse_existing_folder', False) and candidate else parent / name
        destination = destination.resolve()
        if not destination.is_relative_to(root) or destination == root:
            raise ValueError("Choose an asset folder beneath this project's data directory.")
        return name, destination

    def location_feedback(self, project):
        error = name_error(self.filename)
        if error:
            suggestion = name_suggestion(self.filename)
            return error, 'NAME' if suggestion and suggestion != self.filename else '', suggestion
        try:
            root, parent = resolve_parent(project.data_directory, self.directory or self.filepath)
        except (ValueError, OSError) as exc:
            return str(exc), '', ''
        candidate = reuse_candidate(parent, self.filename, root)
        owner = existing_asset(parent, root)
        if owner and owner != candidate:
            return (f'This folder belongs to the existing {owner.name} asset. Create the new asset alongside it.',
                    'SIBLING', str(owner.parent))
        destination = candidate if candidate else parent / self.filename
        if not destination.resolve().is_relative_to(root) or destination.resolve() == root:
            return "Choose an asset folder beneath this project's data directory.", '', ''
        if destination.exists() and not destination.is_dir():
            return folder_conflict(destination), '', ''
        if candidate and candidate != parent / self.filename and not getattr(self, 'reuse_existing_folder', False):
            return (f'Use {candidate.name} as the asset folder, rather than creating another folder inside it.',
                    'REUSE', str(candidate))
        return '', '', ''

    def overwrite_warning(self, project):
        if project is None:
            return ''
        try:
            name, destination = self.asset_location(project)
        except (ValueError, OSError):
            return ''
        if not destination.is_dir() or not folder_conflict(destination, bpy.data.filepath, self.save_new_blend_file):
            return ''
        blend = f' and {name}.blend' if self.save_new_blend_file else ''
        return (f'This folder already contains files. Any matching asset metadata{blend} will be overwritten. '
                'Other files will be kept.')

    def creation_error(self, context, project, validate_template=True):
        if project is None:
            return 'Choose a valid Foundry project.'
        if self.asset_type not in SUPPORTED_ASSETS.get(project.game, set()):
            return 'Choose an asset type supported by this project.'
        error, _, _ = self.location_feedback(project)
        if error:
            return error
        if (getattr(self, 'source_mode', 'CURRENT') == 'SELECTED' or self.selected_only) and not context.selected_objects:
            return 'Select the objects to use, or choose a different starting scene.'
        if self.source_mode == 'TAG' and validate_template:
            try:
                self.template_path()
            except (ValueError, OSError) as exc:
                return str(exc)
        return ''

    def execute(self, context):
        with utils.busy_cursor(context):
            return self.create_asset(context)

    def prepare_source_scene(self, context, asset_name):
        mode = getattr(self, 'source_mode', 'CURRENT')
        if self.selected_only:
            mode = 'SELECTED'
        source = context.scene
        if mode == 'CURRENT':
            return source
        selected = set(context.selected_objects)
        scene = source.copy()
        scene.name = asset_name
        if mode in {'EMPTY', 'TAG'}:
            # The scene's master collection is private, even though its children
            # initially refer to the original collections.
            for child in list(scene.collection.children):
                scene.collection.children.unlink(child)
            for ob in list(scene.collection.objects):
                scene.collection.objects.unlink(ob)
            scene.camera = None
            scene.nwo.animations.clear()
            scene.nwo.main_armature = None
        else:
            from ..scene_conversion import isolate_scope, collect_collections
            _, object_map = isolate_scope(scene)
            keep = {object_map.get(ob, ob) for ob in selected}
            for collection in collect_collections(scene):
                for ob in list(collection.objects):
                    if ob not in keep:
                        collection.objects.unlink(ob)
            if scene.camera not in keep:
                scene.camera = None
        context.window.scene = scene
        return scene

    def create_asset(self, context):
        project = utils.get_project(self.project, use_external=False)
        error = self.creation_error(context, project)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        warning = self.overwrite_warning(project)
        if warning:
            self.report({'WARNING'}, warning)
        asset_name, asset_directory = self.asset_location(project)
        folders = asset_folders(project.game, self.asset_type)
        asset_directory.mkdir(parents=True, exist_ok=True)
        for folder in folders:
            (asset_directory / folder).mkdir(parents=True, exist_ok=True)
        asset_path = asset_directory / asset_name
        sidecar_path_full = asset_path.with_suffix('.sidecar.xml')
        sidecar_path = sidecar_path_full.relative_to(Path(project.data_directory).resolve())
        blender_filepath = asset_path.with_suffix('.blend')

        # Keep-location means no save at all, including no automatic source save.
        if self.save_new_blend_file and bpy.data.filepath and Path(bpy.data.filepath).resolve() != blender_filepath:
            result = bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
            if 'FINISHED' not in result:
                self.report({'ERROR'}, 'Could not save the original Blend file. Asset creation cancelled.')
                return {'CANCELLED'}

        scene = self.prepare_source_scene(context, asset_name)
        scene_nwo = getattr(scene, 'nwo', None) or utils.get_scene_props()
        # Export helpers locate the main scene even when another scene is active.
        for other in getattr(bpy.data, 'scenes', ()):
            other.nwo.is_main_scene = other == scene
        scene.render.fps = 30
        scene.render.image_settings.tiff_codec = 'LZW'
        utils.set_scene_project(scene_nwo, project)
        scene_nwo.sidecar_path = str(sidecar_path)
        scene_nwo.asset_type = self.asset_type
        scene_nwo.is_child_asset = False
        if scene_nwo.scale != self.scale:
            scene_nwo.scale = self.scale
        scene_nwo.forward_direction = self.forward_direction
        for name in MODEL_OUTPUTS:
            enabled = getattr(self, 'output_' + name)
            if name == 'crate' and project.game == 'halo1':
                enabled = False
            if name in {'device_terminal', 'giant', 'effect_scenery'} and project.game in {'halo1', 'halo2'}:
                enabled = False
            if name == 'device_dispenser' and project.game not in {'halo4', 'halo2a'}:
                enabled = False
            setattr(scene_nwo, 'output_' + name, enabled)
        scene_nwo.asset_animation_type = self.animation_type
        scene_nwo.particle_uses_custom_points = self.particle_uses_custom_points
        if self.asset_type == 'scenario':
            scene_nwo.scenario_type = self.scenario_type
            scene_nwo.scenario_auto_bsp_by_origin = self.scenario_auto_bsp_by_origin
        if self.append_special_materials:
            add_special_materials(project.game, self.asset_type)
        if self.append_grid_materials:
            try:
                append_grid_materials()
            except Exception as exc:
                traceback.print_exc()
                self.report({'WARNING'}, f'Could not create Grid Materials; continuing asset creation: {exc}')
        if self.generate_halo_skeleton and self.asset_type == 'model' and self.source_mode != 'TAG':
            add_rig(context, self.output_biped or self.output_vehicle or scene_nwo.output_giant)
        if self.save_new_blend_file:
            result = bpy.ops.wm.save_as_mainfile(filepath=str(blender_filepath), check_existing=True,
                compress=context.preferences.filepaths.use_file_compression)
            if 'FINISHED' not in result:
                self.report({'ERROR'}, 'Could not save the new Blend file. Asset creation cancelled.')
                return {'CANCELLED'}
        sidecar = Sidecar(sidecar_path_full, sidecar_path, asset_path, asset_name,
                          None, scene_nwo, utils.is_corinth(context), context)
        sidecar.build()
        _last_asset_parents[(self.project, self.asset_type, self.object_type,
                            getattr(project, 'default_asset_folder', ''))] = str(
            asset_directory.parent.relative_to(Path(project.data_directory).resolve()))
        suffix = ' Blend file kept in its current location without saving.' if not self.save_new_blend_file else ''
        self.report({'INFO'}, f"Created {self.asset_type.replace('_', ' ').title()} asset '{asset_name}' for {project.name}.{suffix}")
        if self.source_mode == 'TAG':
            from .asset_template import open_template_import
            open_template_import(self, context, scene)
        return {'FINISHED'}

    def invoke(self, context, event):
        scene_nwo = utils.get_scene_props()
        if not self.resume_wizard and not getattr(utils.get_prefs(), 'use_new_asset_editor_wizard', True):
            options = {}
            if self.selected_only:
                options['selected_only'] = True
            result = bpy.ops.nwo.new_asset_legacy('INVOKE_DEFAULT', **options)
            return {'FINISHED'} if result & {'RUNNING_MODAL', 'FINISHED', 'INTERFACE'} else {'CANCELLED'}
        if not self.resume_wizard:
            self.wizard_moved = False
            self.scale = scene_nwo.scale
            self.forward_direction = scene_nwo.forward_direction
            for name in MODEL_OUTPUTS:
                setattr(self, 'output_' + name, getattr(scene_nwo, 'output_' + name))
            if scene_nwo.scene_project:
                project = utils.get_project(use_external=False)
                if project is not None:
                    self.project = project.project_id
            self.asset_type = scene_nwo.asset_type
            self.animation_type = scene_nwo.asset_animation_type
            self.particle_uses_custom_points = scene_nwo.particle_uses_custom_points
            self.scenario_type = scene_nwo.scenario_type
            self.scenario_auto_bsp_by_origin = scene_nwo.scenario_auto_bsp_by_origin
            if not self.properties.is_property_set('source_mode'):
                self.source_mode = 'SELECTED' if self.selected_only else 'CURRENT'
            if not self.properties.is_property_set('template_project'):
                self.template_project = self.project
            project = utils.get_project(self.project, use_external=False)
            if project:
                if self.asset_type not in SUPPORTED_ASSETS.get(project.game, set()):
                    self.asset_type = 'model'
                enabled = [name for name in MODEL_OUTPUTS if getattr(self, 'output_' + name)]
                supported_presets = {item[0] for item in self.object_type_items(context)}
                self.object_type = enabled[0] if len(enabled) == 1 and enabled[0] in supported_presets else 'custom'
                if not self.directory:
                    self.directory = default_asset_directory(self, project)
                if not self.filename and not scene_nwo.sidecar_path and bpy.data.filepath:
                    self.filename = name_suggestion(Path(bpy.data.filepath).stem)
            self.wizard_step = 'TYPE'
        self.wizard_initialized = True
        self.suggested_directory = self.directory
        self.suggested_template_project = self.project if self.template_project == self.project else ''
        if bpy.app.background:
            self.report({'ERROR'}, 'The asset wizard requires a Blender window.')
            return {'CANCELLED'}
        from .asset_wizard_ui import AssetWizard
        self._wizard_ui = AssetWizard(self, context)
        return self._wizard_ui.start(context)

    def modal(self, context, event):
        return self._wizard_ui.modal(context, event)

    def cancel(self, context):
        wizard = getattr(self, '_wizard_ui', None)
        if wizard:
            wizard.close()


class NWO_OT_AssetWizardBrowse(bpy.types.Operator):
    bl_idname = 'nwo.asset_wizard_browse'
    bl_label = 'Choose parent folder'
    bl_options = {'INTERNAL'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    wizard_settings: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        if not self.wizard_settings:
            return {'CANCELLED'}
        settings = json.loads(self.wizard_settings)
        project = utils.get_project(settings['project'], use_external=False)
        if project is None:
            self.report({'ERROR'}, 'The selected project is no longer available.')
            return {'CANCELLED'}
        try:
            _, parent = resolve_parent(project.data_directory, settings['directory'])
            self.directory = str(parent) + os.sep
        except (ValueError, OSError):
            self.directory = project.data_directory + os.sep
        self._return_window = context.window
        self._return_area = context.area
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = json.loads(self.wizard_settings)
        settings['directory'] = self.directory
        settings['reuse_existing_folder'] = False
        _reopen_wizard(settings, self._return_window, self._return_area)
        return {'FINISHED'}

    def cancel(self, context):
        _reopen_wizard(json.loads(self.wizard_settings), self._return_window, self._return_area)
