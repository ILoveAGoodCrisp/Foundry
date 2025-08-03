import os
from pathlib import Path

from ..tools.asset_types import AssetType
from .. import utils
from ..props.scene import NWO_ScenePropertiesGroup
from ..ui.bar import NWO_HaloExportPropertiesGroup

default_templates = [
    'model',
    'render_model',
    'collision_model',
    'physics_model',
    'model_animation_graph',
    'biped',
    'crate',
    'creature',
    'device_control',
    'device_machine',
    'device_terminal',
    'effect_scenery',
    'equipment',
    'giant',
    'scenery',
    'vehicle',
    'weapon'
]

class SidecarImport:
    def __init__(self, asset_path: str, asset_name: str, asset_type: AssetType, sidecar_path: Path, scene_settings: NWO_ScenePropertiesGroup, export_settings: NWO_HaloExportPropertiesGroup, selected_bsps: list[str], corinth: bool, bsps: set, tags_dir, selected_actors: set, cinematic_scene, active_animation: str, structures: list[str], designs: list[str], no_virtual_scene: bool):
        self.asset_path = asset_path
        self.relative_asset_path = utils.relative_path(asset_path)
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.sidecar_path = sidecar_path
        self.scene_settings = scene_settings
        self.export_settings = export_settings
        self.selected_bsps = selected_bsps
        self.selected_actors = selected_actors
        self.bsps = bsps
        self.corinth = corinth
        self.lighting_infos = {}
        self.import_failed = False
        self.error = ""
        self.tags_dir = tags_dir
        self.cinematic_scene = cinematic_scene
        self.active_animation = active_animation
        self.structures = structures
        self.designs = designs
        self.no_virtual_scene = no_virtual_scene
    
    def setup_templates(self):
        templates = default_templates.copy()
        if self.corinth:
            templates.append('device_dispenser')
        for template in templates:
            self._set_template(template)
        
    def _set_template(self, tag_type: str, frame_event_tag=False):
        animation = tag_type == 'model_animation_graph'
        if frame_event_tag or animation or tag_type.endswith('model') or getattr(self.scene_settings, 'output_' + tag_type):
            if animation:
                self._set_template("frame_event_list", frame_event_tag=True)
                
            if frame_event_tag:
                template_path = utils.dot_partition(self.scene_settings.template_model_animation_graph) + ".frame_event_list"
            else:
                template_path = getattr(self.scene_settings, 'template_' + tag_type)
                
            if not template_path:
                return
            
            relative_template_path = utils.relative_path(template_path)
            expected_asset_path = Path(self.tags_dir, self.relative_asset_path, f'{self.asset_name}.{tag_type}')
            if expected_asset_path.exists():
                return
            
            asset_folder = expected_asset_path.parent
            if not asset_folder.exists():
                asset_folder.mkdir(parents=True, exist_ok=True)
            full_path = Path(self.tags_dir, relative_template_path)
            if full_path.exists():
                utils.copy_file(full_path, expected_asset_path)
                print(f'- Loaded {tag_type} tag template')
            elif not frame_event_tag: # Don't warn about the frame event list since the user doesn't explictly specify this
                utils.print_warning(f'Tried to set up template for {tag_type} tag but given template tag [{full_path}] does not exist')
    
    def save_lighting_infos(self):
        lighting_info_paths = [str(Path(self.tags_dir, self.relative_asset_path, f'{b}.scenario_structure_lighting_info')) for b in self.bsps]
        for file in lighting_info_paths:
            if Path(file).exists():
                with open(file, 'r+b') as f:
                    self.lighting_infos[file] = f.read()
    
    def restore_lighting_infos(self):
        for file, data in self.lighting_infos.items():
            with open(file, 'w+b') as f:
                f.write(data)
                
    def run(self):
        self.import_failed, self.error = utils.run_tool_sidecar(
            [
                "import",
                self.sidecar_path,
                *self._get_import_flags()
            ],
            self.asset_path,
            self.export_settings.event_level
        )
        
    def _get_import_flags(self):
        flags = []
        if self.export_settings.import_force:
            flags.append("force")
        if self.export_settings.import_skip_instances:
            flags.append("skip_instances")
        if self.corinth:
            # flags.append("preserve_namespaces")
            if self.export_settings.import_lighting:
                flags.append("lighting")
            if self.export_settings.import_meta_only:
                flags.append("meta_only")
            if self.export_settings.import_disable_hulls:
                flags.append("disable_hulls")
            if self.export_settings.import_disable_collision:
                flags.append("no_collision")
            if self.export_settings.import_no_pca:
                flags.append("no_pca")
            if self.export_settings.import_force_animations:
                flags.append("force_errors")
        else:
            if self.asset_type in {AssetType.MODEL, AssetType.SKY}:
                if not self.export_settings.lightmap_structure:
                    flags.append("draft")
                elif not self.export_settings.import_force:
                    flags.append("force")
            elif self.asset_type == AssetType.ANIMATION:
                flags.append("draft")
            if self.export_settings.import_seam_debug:
                flags.append("seam_debug")
            # if self.export_settings.import_decompose_instances:
            #     flags.append("decompose_instances")
            if self.export_settings.import_suppress_errors:
                flags.append("suppress_errors_to_vrml")

        if self.asset_type == AssetType.SCENARIO:
            if self.selected_bsps:
                for bsp in self.selected_bsps:
                    flags.append(bsp)
            elif not self.no_virtual_scene and (not self.export_settings.export_design or not self.export_settings.export_structure):
                if self.export_settings.export_design:
                    for design in self.designs:
                        flags.append(design)
                elif self.export_settings.export_structure:
                    for bsp in self.structures:
                        flags.append(bsp)
                
        if self.cinematic_scene is not None:
            flags.append(self.cinematic_scene.name)
            
        if self.asset_type == AssetType.ANIMATION:
            if self.corinth and self.export_settings.export_animations == 'ACTIVE':
                flags.append("animation")
                flags.append(self.active_animation)
            else:
                flags.append("animations")
        elif self.asset_type == AssetType.MODEL:
            if self.export_settings.export_render or self.export_settings.export_markers or self.export_settings.export_skeleton:
                flags.append("render")
            if self.export_settings.export_collision:
                flags.append("collision")
            if self.export_settings.export_physics:
                flags.append("physics")
            if self.corinth and self.export_settings.export_animations == 'ACTIVE':
                flags.append("animation")
                flags.append(self.active_animation)
            elif self.export_settings.export_animations == 'ALL':
                flags.append("animations")

        return flags
    
    def cull_unused_tags(self):
        try:
            tag_path = Path(self.tags_dir, self.relative_asset_path, self.asset_name)
            scenery = tag_path.with_suffix(".scenery")
            model = tag_path.with_suffix(".model")
            render_model = tag_path.with_suffix(".render_model")
            # remove the unused tags
            if scenery.exists():
                scenery.unlink()
            if model.exists():
                model.unlink()
            if render_model.exists():
                render_model.unlink()
        except:
            print("Failed to remove unused tags")
            
    def cull_imposter_defs(self):
        try:
            for bsp in self.structures:
                path = Path(self.tags_dir, self.relative_asset_path, bsp).with_suffix(".instance_imposter_definition")
                if path.exists():
                    path.unlink()
        except:
            print("Failed to remove instance_imposter_definition tags")
