'''Classes to store intermediate geometry data to be passed to granny files'''

from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix
import numpy as np

from ..props.mesh import NWO_MeshPropertiesGroup

from .. import utils

from ..tools.asset_types import AssetType

from ..constants import VALID_MESHES

class VirtualMaterial:  
    def __init__(self, shader_path: str | Path):
        path = Path(shader_path)
        self.name: str = path.with_suffix("").name
        self.index = 0
        self.props = {
          "bungie_shader_type": path.suffix[1:],
          "bungie_shader_path": str(path.with_suffix(""))
        }
        
    def props_encoded(self):
        '''Returns a dict of encoded properties'''
        encoded_props = {key: value.encode() for key, value in self.props.items()}
        return encoded_props
    
class VirtualMesh:
    def __init__(self, mesh: bpy.types.Mesh, vertex_weighted: bool, scene: 'VirtualScene'):
        self.name = mesh.name
        self.positions: np.ndarray = None
        self.normals: np.ndarray = None
        self.bone_weights: np.ndarray = None
        self.bone_indices: np.ndarray = None
        self.texcoords: list[np.ndarray] = [] # Up to 4 uv layers
        self.lighting_texcoords: np.ndarray = None
        self.vertex_colors: list[np.ndarray] = [] # Up to two sets of vert colors
        self.indices: np.ndarray = None
        self.materials: dict[VirtualMaterial: int] = {} # dict of materials and the face index they start at
        self.face_properties: dict[str: list] = {}
        self._setup(mesh, vertex_weighted, scene)
        
        # print("Positions", self.positions)
        
    def _setup(self, mesh: bpy.types.Mesh, vertex_weighted: bool, scene: 'VirtualScene'):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        # bmesh stuff goes here
        
        if mesh.has_custom_normals:
            print("has custom normals??")
            pass # Code for splitting mesh goes here
        else:
            print(mesh.normals_domain)
            match mesh.normals_domain:
                case 'FACE': # Using polygon normals, split all the edges
                    bmesh.ops.split_edges(bm, edges=bm.edges)
                case 'CORNER': # Split edges only if they are sharp
                    bmesh.ops.split_edges(bm, edges=[edge for edge in bm.edges if not edge.smooth])
                # Last option is vertex normals (smooth shading), don't need to edge split
        
        bmesh.ops.triangulate(bm, faces=bm.faces) # granny only supports tris for faces
        bm.faces.sort(key=lambda face: face.material_index) # faces set sorted by material index, important for granny
        
        # Gather face properties
        if mesh.nwo.face_props:
            gather_face_props(mesh.nwo, bm)
        
        bm.to_mesh(mesh)
        bm.free()
        
        self.num_vertices = len(mesh.vertices)
        num_polygons = len(mesh.polygons)
        num_materials = len(mesh.materials)
        positions = np.empty(self.num_vertices * 3, dtype=np.float32)
        normals = positions.copy()
        mesh.vertices.foreach_get("co", positions)
        self.positions = positions.reshape(-1, 3)
        
        # Get normals - for granny these are always vertex normals
        mesh.vertices.foreach_get("normal", normals)
        self.normals = normals.reshape(-1, 3)
        # match mesh.normals_domain:
        #     case 'FACE':
        #         normals = mesh.polygon_normals
        #     case 'POINT':
        #         mesh.vertex_normals.foreach_get("vector", normals)
        #     case _:
        #         normals = mesh.corner_normals
        
        self.indices = np.empty(num_polygons * 3, dtype=np.int32)
        mesh.polygons.foreach_get("vertices", self.indices)
        if num_materials > 1:
            material_indices = np.empty(num_polygons, dtype=np.int32)
            mesh.polygons.foreach_get("material_index", material_indices)
            changes = np.where(np.diff(material_indices, prepend=material_indices[0]))[0]
            lengths = np.diff(np.append(changes, len(material_indices)))
            for idx, mat in enumerate(mesh.materials):
                self.materials[scene._get_material(mat)] = (changes[idx], lengths[idx])
        elif num_materials == 1:
            self.materials[scene._get_material(mesh.materials[0])] = (0, num_polygons)
        else:
            self.materials[scene.materials["invalid"]] = (0, num_polygons) # default material
        
        # Bone Weights & Indices
        self.bone_weights = np.zeros((self.num_vertices * 4), dtype=np.float32)
        self.bone_indices = np.zeros((self.num_vertices * 4), dtype=np.byte)
        
        if vertex_weighted:
            for i in range(self.num_vertices):
                groups = mesh.vertices[i].groups
                weights = np.array([g.weight for g in groups])
                indices = np.array([g.group for g in groups])
                
                if len(weights) > 0:
                    sorted_indices = np.argsort(-weights)
                    top_weights = weights[sorted_indices[:4]]
                    top_indices = indices[sorted_indices[:4]]
                    
                    top_weights /= top_weights.sum()

                    self.bone_weights[i, :len(top_weights)] = top_weights
                    self.bone_indices[i, :len(top_indices)] = top_indices 
        
        loop_vertices = np.empty(len(mesh.loops) * 1, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", self.indices)
        
        # Texcoords
        # for layer in mesh.uv_layers:
        #     if len(self.texcoords) >= 4:
        #         break
        #     vertex_uvs = np.empty(num_vertices * 2, dtype=np.float32)
        #     layer.uv.foreach_get("uv", vertex_uvs)
        #     # for i in range((len(mesh.loops))):
        #     #     uv_coords = layer.data[i].uv.to_tuple()
        #     #     vertex_uvs[loop_vertices[i]].append(uv_coords)
            
        #     if layer.name.lower() == "lighting":
        #         self.lighting_texcoords = vertex_uvs
        #     else:
        #         self.texcoords.append(vertex_uvs)
                
        # Vertex Colors
        for layer in mesh.color_attributes:
            if len(self.vertex_colors) >= 2:
                break
            vertex_colors = np.empty(self.num_vertices * 3, dtype=np.float32)
            layer.data.foreach_get("color", vertex_colors)
            self.vertex_colors.append(vertex_colors)
            
# class VirtualSkeleton:
#     def __init__(self, ob: bpy.types.Object, node: 'VirtualNode', scene: 'VirtualScene'):
#         self.name: str = ob.name
#         self.nodes: list[VirtualNode] = [node]
#         self._setup(ob, node)
        
#     def _setup(self, ob: bpy.types.Object, node: 'VirtualNode', scene: 'VirtualScene'):
#         if ob.type == 'ARMATURE':
#             for bone in ob.pose.bones:
#                 if not ob.data.bones[bone.name].deform: continue # Ignore non-deform bones
#                 node = VirtualNode(bone, self._get_bone_props(bone))
#                 self.nodes.append(node)
#                 scene.nodes[node.name] = node
                
#     def _get_bone_props(self, bone: bpy.types.PoseBone) -> dict:
#         props = {
#             "bungie_object_type": "_connected_geometry_object_type_frame",
#             "bungie_object_animates": "1",
#         }
        
#         props["bungie_frame_ID1"] = "0"
#         props["bungie_frame_ID2"] = "0"
        
#         return props
    
class VirtualNode:
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone, props: dict, region: str = None, permutation: str = None, scene: 'VirtualScene' = None):
        self.name: str
        self.matrix_world: Matrix
        self.matrix_local: Matrix
        self.mesh: VirtualMesh | None
        self.new_mesh = False
        self.skeleton = VirtualSkeleton
        self.region = region
        self.permutation = permutation
        self.props = props
        self.group = self._get_group()
        self.parent: VirtualNode = None
        
        self._setup(id, scene)
        
    def _setup(self, id: bpy.types.Object | bpy.types.PoseBone, scene: 'VirtualScene'):
        self.name = id.name
        if isinstance(id, bpy.types.Object):
            self.matrix_world = id.matrix_world.copy()
            self.matrix_local = id.matrix_local.copy()
            if id.type in VALID_MESHES:
                existing_mesh = scene.meshes.get(id.data.name)
                if existing_mesh:
                    self.mesh = existing_mesh
                else:
                    vertex_weighted = id.vertex_groups and id.parent and id.parent.type == 'ARMATURE' and id.parent_type != "BONE" and has_armature_deform_mod(id)
                    mesh = VirtualMesh(id.to_mesh(preserve_all_data_layers=True, depsgraph=scene.depsgraph), vertex_weighted, scene)
                    self.mesh = mesh
                    id.to_mesh_clear()
                    self.new_mesh = True
                    
            #     if not scene.skeleton_node and not id.parent:
            #         self.skeleton = VirtualSkeleton(id, self)
                    
            # elif id.type == 'ARMATURE':
            #     self.skeleton = VirtualSkeleton(id, self)
            # elif id.type == 'EMPTY' and not scene.skeleton_node and not id.parent:
            #     self.skeleton = VirtualSkeleton(id, self)
            
    def _get_group(self):
        return "default"
    
    def props_encoded(self):
        '''Returns a dict of encoded properties'''
        encoded_props = {key: value.encode() for key, value in self.props.items()}
        return encoded_props
    
class VirtualBone:
    '''Describes an blender object/bone which is a child'''
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone):
        self.name: str = id.name
        self.parent_index: int = -1
        self.node: VirtualNode = None
        self.matrix_local: Matrix = None
        self.matrix_world: Matrix = None
        
class VirtualSkeleton:
    '''Describes a list of bones'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene'):
        self.name: str = ob.name
        own_bone = VirtualBone(ob)
        own_bone.node = scene.nodes.get(ob.name)
        own_bone.matrix_world = own_bone.node.matrix_world
        own_bone.matrix_local = own_bone.node.matrix_local
        self.bones: list[VirtualBone] = [own_bone]
        self._get_bones(ob.original, scene)
        
    def _get_bones(self, ob, scene):
        if ob.type == 'ARMATURE':
            valid_bones = [pbone for pbone in ob.pose.bones if ob.data.bones[pbone.name].deform]
            list_bones = [pbone.name for pbone in valid_bones]
            for bone in valid_bones:
                b = VirtualBone(bone)
                # b.set_transform(bone, ob)
                # b.properties = utils.get_halo_props_for_granny(ob.data.bones[idx])
                if bone.parent:
                    # Add one to this since the root is the armature
                    b.parent_index = list_bones.index(bone.parent.name) + 1
                else:
                    b.parent_index = 0
                self.bones.append(b)
                
            child_index = 0
            for child in ob.children:
                child_index += 1
                b = VirtualBone(child)
                # b.set_transform(child, ob)
                if child.parent_type == 'BONE':
                    b.parent_index = list_bones.index(child.parent_bone) + 1
                else:
                    b.parent_index = 0
                    
                self.bones.append(b)
                self.find_children(child, scene, child_index)
                    
        else:
            self.find_children(ob, scene)
                    
    def find_children(self, ob: bpy.types.Object, scene, parent_index=0):
        child_index = parent_index
        for child in ob.children:
            child_index += 1
            b = VirtualBone(child)
            # b.set_transform(child, ob)
            b.parent_index = parent_index
            b.node = scene.nodes.get(child.name)
            b.matrix_world = b.node.matrix_world
            b.matrix_local = b.node.matrix_local
            self.bones.append(b)
            self.find_children(child, scene, child_index)
    
class VirtualModel:
    '''Describes a blender object which has no parent'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene'):
        self.name: str = ob.name
        self.skeleton: VirtualSkeleton = VirtualSkeleton(ob, scene)
        self.matrix: Matrix = ob.matrix_world.copy()
        self.node = scene.nodes.get(self.name)
            
class VirtualScene:
    def __init__(self, asset_type: AssetType, depsgraph: bpy.types.Depsgraph):
        self.nodes: dict[VirtualNode] = {}
        self.meshes: dict[VirtualMesh] = {}
        self.materials: dict[VirtualMaterial] = {}
        self.models: dict[VirtualModel] = {}
        self.root: VirtualNode = None
        self.asset_type = asset_type
        self.depsgraph = depsgraph
        self.regions: set = set()
        self.permutations: set = set()
        self.global_materials: set = set()
        self.skeleton_node: VirtualNode = None
        
    def add(self, id: bpy.types.Object | bpy.types.PoseBone, props: dict, region: str = None, permutation: str = None):
        '''Creates a new node with the given parameters and appends it to the virtual scene'''
        node = VirtualNode(id, props, region, permutation, self)
        self.nodes[node.name] = node
        if node.new_mesh:
            self.meshes[node.mesh.name] = node.mesh
            
    def set_skeleton(self, ob):
        '''Creates a new skeleton node from this object and sets this as the skeleton node for the scene'''
        props = {
            "bungie_frame_world": "1",
            "bungie_frame_ID1": "8078",
            "bungie_frame_ID2": "378163771",
            "bungie_object_type": "_connected_geometry_object_type_frame",
        }
        self.skeleton_node = VirtualNode(ob, props)
        
    def add_model(self, ob):
        self.models[ob.name] = VirtualModel(ob, self)
        
    def _get_material(self, material: bpy.types.Material):
        virtual_mat = self.materials.get(material.name)
        if virtual_mat: return virtual_mat
        
        shader_path = material.nwo.shader_path
        relative = utils.relative_path(shader_path)
        virtual_mat = VirtualMaterial(relative)
        virtual_mat.index = len(self.materials)
        self.materials[virtual_mat.name] = virtual_mat
        return virtual_mat
                
def has_armature_deform_mod(ob: bpy.types.Object):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE' and mod.object and mod.use_vertex_groups:
            return True
            
    return False

def gather_face_props(mesh_props: NWO_MeshPropertiesGroup, bm: bmesh.types.BMesh):
    face_properties = {}
    for face_prop in mesh_props.face_props:
        pass
        # if face_two_sided_override:
        #     face_properties["bungie_face_sides"] = 
        
    return face_properties