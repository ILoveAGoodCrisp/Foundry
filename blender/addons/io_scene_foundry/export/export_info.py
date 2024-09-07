
from enum import Enum, auto
from getpass import getuser
import re
from socket import gethostname
from datetime import datetime

pattern = re.compile(r'(?<!^)(?=[A-Z])')

def snake(text: str) -> str:
     return pattern.sub('_', text).lower()

class BungieEnum(Enum):
    @classmethod
    def names(cls):
        text = str(list(map(lambda c: f"_connected_geometry_{snake(cls.__name__)}_{c.name}", cls)))
        return f"#({text.strip('[]')})".encode()
    @classmethod
    def values(cls):
        text = str(list(map(lambda c: c.value, cls)))
        return f"#({text.strip('[]')})".encode()

class ObjectType(BungieEnum):
    none = 0
    frame = 1
    marker = 2
    mesh = 3
    light = 4
    animation_control = 5
    animation_camera = 6
    animation_event = 7
    debug = 8
    pca = 9
    
class MeshType(BungieEnum):
    none = 0
    boundary_surface = 1
    collision = 2
    default = 3
    poop = 4
    poop_collision = 5
    poop_physics = 6
    poop_marker = 7
    poop_rain_blocker = 8
    poop_verticle_rain_shee = 9
    decorator = 10
    object_instance = 11
    physics = 12
    portal = 13
    seam = 14
    planar_fog_volume = 15
    
class MarkerType(BungieEnum): ...

class FaceType(BungieEnum):
    normal = 0
    seam_sealer = 1
    sky = 2
    
class FaceMode(BungieEnum):
    normal = 0
    render_only = 1
    collision_only = 2
    sphere_collision_only = 3
    shadow_only = 4
    lightmap_only = 5
    breakable = 6
    
class FaceSides(BungieEnum):
    one_sided = 0
    one_sided_transparent = 1
    two_sided = 2
    two_sided_transparent = 3
    mirror = 4
    mirror_transparent = 5
    keep = 6
    keep_transparent = 7
    
class FaceDrawDistance(BungieEnum):
    normal = 0
    detail_mid = 1
    detail_close = 2

class LightmapType(BungieEnum):
    per_pixel = 0
    per_vertex = 1
    
class ExportInfo:
    def __init__(self, regions, global_materials):
        self.export_user = getuser()
        self.export_machine = gethostname()
        self.export_toolset = "Foundry"
        time = datetime.today()
        self.export_date = time.strftime("%Y-%m-%d")
        self.export_time = time.strftime("%H:%M:%S")
        
        # self.object_type = ObjectType
        # self.mesh_type = MeshType
        self.face_mode = FaceMode
        self.face_sides = FaceSides
        self.face_draw_distance = FaceDrawDistance
        self.lightmap_type = LightmapType
        
        self.regions = regions
        self.global_material = global_materials
        
    def create_info(self) -> dict:
        info = {}
        for key, value in self.__dict__.items():
            if isinstance(value, str):
                info[f"bungie_{key}"] = value.encode()
            elif isinstance(value, list):
                names_key = f"connected_geometry_{key}_table_enum_names"
                values_key = f"connected_geometry_{key}_table_enum_values"
                info[names_key] = f"#({str(value).strip('[]')})".encode()
                info[values_key] = f"#({str(list(range(len(value)))).strip('[]')})".encode()
            else:
                names_key = f"e_connected_geometry_{snake(key)}_enum_names"
                values_key = f"e_connected_geometry_{snake(key)}_enum_values"
                info[names_key] = value.names()
                info[values_key] = value.values()
                
        return info