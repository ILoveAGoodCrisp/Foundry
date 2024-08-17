from enum import Enum
import os
from pathlib import Path
import tempfile
import bpy
from mathutils import Matrix

from ..granny import Granny
from .. import utils
from ..ui.bar import NWO_HaloExportPropertiesGroup
from ..props.scene import NWO_ScenePropertiesGroup
from ..constants import GameVersion, VALID_MESHES, VALID_OBJECTS
from ..tools.asset_types import AssetType

class ExportTagType(Enum):
    RENDER = 0
    COLLISION = 1
    PHYSICS = 2
    MARKERS = 3
    SKELETON = 4
    ANIMATION = 5
    SKY = 6
    DECORATOR = 7
    STRUCTURE = 8
    STRUCTURE_DESIGN = 9
    
class SidecarData:
    gr2_path: Path
    blend_path: Path
    permutation: str
    
    def __init__(self, gr2_path: Path, data_dir: Path, permutation: 'Permutation'):
        self.gr2_path = gr2_path.relative_to(data_dir)
        self.blend_path = Path(bpy.data.filepath).relative_to(data_dir)
        self.permutation = permutation.name

class Permutation:
    name: str
    valid: bool
    
    def __init__(self, name: str):
        self.name = name.lower()
        self.valid = True
        
    @property
    def is_default(self) -> bool:
        return self.name == "default"
    
class Region:
    name: str
    valid: bool
    
    def __init__(self, name: str):
        self.name = name.lower()
        self.valid = True
        
    @property
    def is_default(self) -> bool:
        return self.name == "default"
    
class ExportFaceProp:
    '''Holds face layer data'''
    
class ExportMesh:
    '''Holds export mesh data'''
    mesh: bpy.types.Mesh
    props: dict
    face_props: list[ExportFaceProp]
    
    def __init__(self, blob: bpy.types.Object):
        self.mesh = blob.to_mesh()
    
class ExportMaterial:
    '''Holds the material data we need for granny'''
    
class ExportObject:
    '''Holds export object data'''
    blob: bpy.types.Object
    name: str
    matrix: Matrix
    region: str
    permutation: str
    props: dict
    mesh: ExportMesh | None
    
    def __init__(self, blob: bpy.types.Object):
        self.blob = blob
        self.name = blob.name
        self.matrix = blob.matrix_world.copy()
        self.mesh = None
        if blob.type == 'MESH':
            self.mesh = ExportMesh(blob)
            
class ExportScene:
    '''Scene to hold all the export objects'''
    context: bpy.types.Context
    asset_type: AssetType
    asset_name: str
    asset_path: Path
    corinth: bool
    game_version: GameVersion
    scene_settings: NWO_ScenePropertiesGroup
    export_settings: NWO_HaloExportPropertiesGroup
    tags_dir: Path
    data_dir: Path
    root_dir: Path
    warning_hit: bool
    bsps_with_structure: set
    disabled_collections: set[bpy.types.Collection]
    export_objects: list[ExportObject]
    permutations: list[str]
    regions: list[str]
    global_materials: list[str]
    
    def __init__(self, context, asset_type, asset_name, corinth):
        self.context = context
        self.asset_type = AssetType(asset_type.upper())
        self.asset_name = asset_name
        self.corinth = corinth
        self.tags_dir = Path(utils.get_tags_path())
        self.data_dir = Path(utils.get_data_path())
        self.root_dir = self.data_dir.parent
        
    def ready_scene(self):
        utils.exit_local_view(self.context)
        self.context.view_layer.update()
        utils.set_object_mode(self.context)
        self.disabled_collections = utils.disable_excluded_collections(self.context)
        
    def get_initial_export_objects(self):
        if self.AssetType == AssetType.ANIMATION:
            self.export_objects = {ExportObject(ob) for ob in self.context.view_layer.objects if ob.type == "ARMATURE"}
        else:
            self.export_objects = {ExportObject(ob) for ob in self.context.view_layer.objects if ob.nwo.export_this or ob.type in VALID_OBJECTS}
            
    def setup_skeleton(self):
        self.armature = utils.get_rig(self.context, scope=self.export_objects)
    
    
            
            
    def process(self):
        # make necessary directories
        self.models_dir = Path(self.asset_path, "models")
        self.models_export_dir = Path(self.asset_path, "export", "models")
        if not self.models_dir.exists():
            self.models_dir.mkdir(parents=True, exist_ok=True)
        if not self.models_export_dir.exists():
            self.models_export_dir.mkdir(parents=True, exist_ok=True)
            
        if self.asset_type == AssetType.MODEL or self.asset_type == AssetType.ANIMATION:
            self.animations_dir = Path(self.asset_path, "animations")
            self.animations_export_dir = Path(self.asset_path, "export", "animations")
            if not self.animations_dir.exists():
                self.animations_dir.mkdir(parents=True, exist_ok=True)
            if not self.animations_export_dir.exists():
                self.animations_export_dir.mkdir(parents=True, exist_ok=True)
                
    def _process_models(self):
        pass
    
    def _export_model(self, tag_type: ExportTagType):
        for permutation in self.permutations:
            granny_path = self._get_export_path(tag_type, permutation=permutation)
            self.sidecar_info.append(SidecarData(granny_path, self.data_dir, permutation))
            
            
    def _export_granny(self, filepath: Path, objects: list[ExportObject] = None, animations: list = None):
        os.chdir(tempfile.gettempdir())
        granny = Granny(Path(self.root_dir, "granny2_x64.dll"), filepath)
        granny.create_materials(self.export_materials)
        granny.create_skeletons(self.export_skeletons)
        granny.save()
        
            
    def _get_export_path(self, tag_type: ExportTagType, region: Region = None, permutation: Permutation = None, animation: str = None):
        """Gets the path to save a particular file to"""
        if self.asset_type == AssetType.SCENARIO:
            if tag_type == ExportTagType.STRUCTURE_DESIGN:
                if permutation.is_default:
                    return Path(self.models_export_dir, f"{self.asset_name}_{region.name}_design.gr2")
                else:
                    return Path(self.models_export_dir, f"{self.asset_name}_{region}_{permutation.name}_design.gr2")
            else:
                if permutation.is_default:
                    return Path(self.models_export_dir, f"{self.asset_name}_{region.name}.gr2")
                else:
                    return Path(self.models_export_dir, f"{self.asset_name}_{region.name}_{permutation.name}.gr2")
        else:
            if tag_type == ExportTagType.ANIMATION:
                return Path(self.animations_export_dir, f"{animation}.gr2")
            else:
                if permutation.is_default or tag_type in {ExportTagType.MARKERS, ExportTagType.SKELETON}:
                    return Path(self.models_export_dir, f"{self.asset_name}_{tag_type.name.lower()}.gr2")
                else:
                    return Path(self.models_export_dir, f"{self.asset_name}_{permutation.name}_{tag_type.name.lower()}.gr2")