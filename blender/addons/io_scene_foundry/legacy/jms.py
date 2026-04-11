from pathlib import Path

from mathutils import Quaternion, Vector
import bpy
from . import gen_lines, sint, to_quaternion, to_vector
from .. import utils


class Node:
    def __init__(self, name: str, parent_node_index: int, default_rotation: Quaternion, default_translation: Vector):
        self.name = name
        self.parent_node_index = parent_node_index
        self.default_rotation = default_rotation
        self.default_translation = default_translation
        
class Material:
    def __init__(self, name: str, material_name: str):
        self.name = name
        self.material_name = material_name
        parts = self.material_name.split()
        self.value = parts[0].strip("()")
        self.permutation = parts[1]
        self.region = parts[2]
        
        self.clean_name = utils.get_valid_shader_name(name)
        
        self.blender_material = bpy.data.materials.get(self.clean_name)
        
        if self.blender_material is None:
            self.blender_material = bpy.data.materials.new(self.clean_name)
        
class Marker:
    def __init__(self):
        self.name = "default"
        self.node_index = 0
        self.rotation: Quaternion = None
        self.translation: Vector = None
        self.radius = 1
        
class Xref:
    def __init__(self):
        self.path = "default"
        self.name = "default"

class InstanceMarker:
    def __init__(self):
        self.name = "default"
        self.unique_identifier = 0
        self.path_index = -1
        self.rotation: Quaternion = None
        self.translation: Vector = None
        
class NodeInfluence:
    def __init__(self):
        self.index = -1
        self.weight = 0
        
class TextureCoordinate:
    def __init__(self):
        self.u = 0.0
        self.v = 0.0

class VertexColor:
    def __init__(self):
        self.r = 0
        self.g = 0
        self.b = 0
        
class VertexIndices:
    def __init__(self):
        self.v1 = 0
        self.v2 = 1
        self.v3 = 2

class Triangle:
    def __init__(self):
        self.material_index = 0
        self.vertex_indices: VertexIndices = None
        
class Vertex:
    def __init__(self):
        self.positon: Vector = None
        self.normal: Vector = None
        self.node_influences_count = 0
        self.node_influences: list[NodeInfluence]  = []
        self.texture_coordinate_count: list[NodeInfluence]  = []
        
class Sphere:
    def __init__(self):
        self.name = "default"
        self.parent = None
        self.material = 0
        
class JMS:
    def __init__(self):
        self.name = ""
        self.version = 8213
        
        self.node_count = 0
        self.nodes: list[Node] = []
        
        self.material_count = 0
        self.materials: list[Material] = []
        
        self.marker_count = 0
        self.markers: list[Marker] = []
        
    def from_file(self, filepath):
        self.name = Path(filepath).with_suffix("").name
        lines = gen_lines(filepath)
        get = lambda: next(lines)
        geti = lambda: sint(next(lines))
        getf = lambda: float(next(lines))
        getv = lambda: to_vector(next(lines))
        getq = lambda: to_quaternion(next(lines))
        self.version = sint(get())
        
        # NODES
        self.node_count = geti()
        for _ in range(self.node_count):
            self.nodes.append(Node(get(), geti(), getq(), getv()))
            
        # MATERIALS
        self.material_count = geti()
        for _ in range(self.material_count):
            self.materials.append(Material(get(), get()))
            
        # MARKERS
        self.marker_count = geti()
        for _ in range(self.marker_count):
            self.markers.append(Marker(get(), geti(), getq(), getv(), getf()))
            
        # XREF Paths
        
        # INSTANCE MARKERS
        
        # VERTICES
        self.vertex_count = geti()
        for _ in range(self.vertex_count):
            self.vertices.append(Vertex(getv(), getv(), [NodeInfluence(geti(), getf()) for _ in range(geti())], [TextureCoordinate(getv(), getv()) for _ in range(geti())], VertexColor(getv())))
    
    def to_mesh(self):
        pass