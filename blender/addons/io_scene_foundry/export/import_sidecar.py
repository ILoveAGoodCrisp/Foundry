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
    def __init__(self, asset_path: str, asset_name: str, asset_type: AssetType, sidecar_path: Path, scene_settings: NWO_ScenePropertiesGroup, export_settings: NWO_HaloExportPropertiesGroup, selected_bsps: list[str], corinth: bool, bsps: set):
        self.asset_path = asset_path
        self.relative_asset_path = utils.relative_path(asset_path)
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.sidecar_path = sidecar_path
        self.scene_settings = scene_settings
        self.export_settings = export_settings
        self.selected_bsps = selected_bsps
        self.bsps = bsps
        self.corinth = corinth
        self.lighting_infos = {}
        self.import_failed = False
        self.error = ""
    
    def _setup_templates(self):
        templates = default_templates.copy()
        if self.corinth:
            templates.append('device_dispenser')
        for template in templates:
            self._set_template(template)
        
    def _set_template(self, tag_type: str):
        if tag_type.endswith('model') or tag_type == 'model_animation_graph' or getattr(self.scene_settings, 'output_' + tag_type):
            relative_path = getattr(self.scene_settings, 'template_' + tag_type)
            expected_asset_path = Path(self.asset_path, f'{self.asset_name}.{tag_type}')
            if relative_path and expected_asset_path.exists():
                asset_folder = expected_asset_path.parent
                if not asset_folder.exists():
                    asset_folder.mkdir(parents=True, exist_ok=True)
                full_path = Path(self.tags_dir, relative_path)
                if full_path.exists():
                    utils.copy_file(full_path, expected_asset_path)
                    print(f'- Loaded {tag_type} tag template')
                else:
                    utils.print_warning(f'Tried to set up template for {tag_type} tag but given template tag [{full_path}] does not exist')
    
    def save_lighting_infos(self):
        lighting_info_paths = [str(Path(self.self.tags_dir, self.relative_asset_path, f'{self.asset_name}_{b}.scenario_structure_lighting_info')) for b in self.bsps]
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
            self.asset_path
        )
        
    def _get_import_flags(self):
        flags = []
        if self.export_settings.import_force:
            flags.append("force")
        if self.export_settings.import_skip_instances:
            flags.append("skip_instances")
        if self.corinth:
            flags.append("preserve_namespaces")
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
            if self.export_settings.import_draft:
                flags.append("draft")
            if self.export_settings.import_seam_debug:
                flags.append("seam_debug")
            if self.export_settings.import_decompose_instances:
                flags.append("decompose_instances")
            if self.export_settings.import_suppress_errors:
                flags.append("suppress_errors_to_vrml")

        if self.selected_bsps:
            for bsp in self.selected_bsps:
                flags.append(f"{self.asset_name}_{bsp}")

        return flags
    
    def cull_unused_tags(self):
        try:
            tag_path = Path(self.tags_dir, self.asset_path, self.asset_name)
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
