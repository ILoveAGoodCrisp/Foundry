
from enum import Enum, auto
from getpass import getuser
import re
from socket import gethostname
from datetime import today

import bpy

pattern = re.compile(r'(?<!^)(?=[A-Z])')

def snake(text: str) -> str:
     return pattern.sub('_', text).lower()

class BungieEnum(Enum):
    @classmethod
    def names(cls):
        text = str(list(map(lambda c: f'"_connected_geometry_{snake(cls.__name__)}_{c.name}"', cls)))
        return f'#({text})'
    @classmethod
    def values(cls):
        text = str(list(map(lambda c: c.value, cls)))
        return f'#({text})'

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
    
class ExportInfo:
    def __init__(self):
        self.export_user = getuser()
        self.export_machine = gethostname()
        self.export_toolset = "Foundry"
        self.export_date = today().strftime("%Y-%m-%d")
        self.export_time = today().strftime("%H:%M:%S")
        self.object_type = ObjectType
        self.mesh_type = MeshType
        
    def create_node(self) -> bpy.types.Object:
        node = bpy.data.objects.new("BungieExportInfo", None)
        for key, value in self.__dict__.items():
            if type(value) == str:
                node[f"bungie_{key}"] = value
            else:
                names_key = f"e_connected_geometry_{snake(key.__name__)}_enum_names"
                values_key = f"e_connected_geometry_{snake(key.__name__)}_enum_values"
                node[names_key] = value.names()
                node[values_key] = value.values()
                
        return node