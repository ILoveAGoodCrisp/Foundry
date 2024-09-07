'''Classes to store intermediate geometry data to be passed to granny files'''

from collections import defaultdict
from enum import Enum
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix
import numpy as np

from .export_info import ExportInfo, FaceDrawDistance, FaceMode, FaceSides, FaceType

from ..props.mesh import NWO_FaceProperties_ListItems, NWO_MeshPropertiesGroup

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
        self.face_properties: dict[str: np.ndarray] = {}
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
            # print(mesh.normals_domain)
            match mesh.normals_domain:
                case 'FACE': # Using polygon normals, split all the edges
                    bmesh.ops.split_edges(bm, edges=bm.edges)
                case 'CORNER': # Split edges only if they are sharp
                    bmesh.ops.split_edges(bm, edges=[edge for edge in bm.edges if not edge.smooth])
                # Last option is vertex normals (smooth shading), don't need to edge split
        
        bmesh.ops.triangulate(bm, faces=bm.faces) # granny only supports tris for faces
        bm.faces.sort(key=lambda face: face.material_index) # faces set sorted by material index, important for granny
        
        
        bm.to_mesh(mesh)
            
        self.num_vertices = len(mesh.vertices)
        num_polygons = len(mesh.polygons)
        
        if mesh.nwo.face_props:
            self.face_properties = gather_face_props(mesh.nwo, bm, num_polygons, scene)
            
        bm.free()
        
        num_materials = len(mesh.materials)
        num_loops = len(mesh.loops)
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
        
        loop_vertices = np.empty(num_loops, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vertices)
        
        # Texcoords
        for layer in mesh.uv_layers:
            if len(self.texcoords) >= 4:
                break
            
            loop_uvs = np.empty(num_loops * 2, dtype=np.float32)
            layer.uv.foreach_get("vector", loop_uvs)
            loop_uvs = loop_uvs.reshape(-1, 2)

            vertex_uvs = [[] for _ in range(self.num_vertices)]

            for loop_idx, vert_idx in enumerate(loop_vertices):
                vertex_uvs[vert_idx].append(loop_uvs[loop_idx])

            averaged_vertex_uvs = np.zeros((self.num_vertices, 2), dtype=np.float32)

            for vert_idx, uvs in enumerate(vertex_uvs):
                if uvs:
                    averaged_vertex_uvs[vert_idx] = np.mean(uvs, axis=0)
                else:
                    averaged_vertex_uvs[vert_idx] = [0, 0]

            
            if layer.name.lower() == "lighting":
                self.lighting_texcoords = averaged_vertex_uvs
            else:
                self.texcoords.append(averaged_vertex_uvs)
                
        # Vertex Colors
        for layer in mesh.color_attributes:
            if len(self.vertex_colors) >= 2:
                break
            point_colors =  layer.domain == 'POINT'
            num_colors = self.num_vertices if point_colors else num_loops
            colors = np.empty(num_colors * 4, dtype=np.float32)
            layer.data.foreach_get("color", colors)
            colors = colors.reshape(-1, 4)
            
            if point_colors:
                self.vertex_colors.append(colors)
                continue
            
            vertex_colors = [[] for _ in range(self.num_vertices)]

            for loop_idx, vert_idx in enumerate(loop_vertices):
                vertex_colors[vert_idx].append(colors[loop_idx])

            averaged_vertex_colors = np.zeros((self.num_vertices, 4), dtype=np.float32)

            for vert_idx, cols in enumerate(vertex_colors):
                if cols:
                    averaged_vertex_colors[vert_idx] = np.mean(cols, axis=0)
                else:
                    averaged_vertex_colors[vert_idx] = [0, 0, 0, 0]
            
            self.vertex_colors.append(averaged_vertex_colors)
            
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
    def __init__(self, asset_type: AssetType, depsgraph: bpy.types.Depsgraph, corinth: bool):
        self.nodes: dict[VirtualNode] = {}
        self.meshes: dict[VirtualMesh] = {}
        self.materials: dict[VirtualMaterial] = {}
        self.models: dict[VirtualModel] = {}
        self.root: VirtualNode = None
        self.asset_type = asset_type
        self.depsgraph = depsgraph
        self.regions: list = []
        self.permutations: list = []
        self.global_materials: list = []
        self.skeleton_node: VirtualNode = None
        self.corinth = corinth
        self.export_info: ExportInfo = None
        
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

class FaceSet:
    def __init__(self, array: np.ndarray):
        self.face_props: dict[NWO_FaceProperties_ListItems: bmesh.types.BMLayerItem] = {}
        self.array = array
        
    def update(self, bm: bmesh.types.BMesh, layer_name: str, value: object):
        layer = bm.faces.layers.int.get(layer_name)
        if layer:
            self.face_props[layer] = value

def gather_face_props(mesh_props: NWO_MeshPropertiesGroup, bm: bmesh.types.BMesh, num_faces: int, scene: VirtualScene) -> dict:
    face_properties = {}
    for face_prop in mesh_props.face_props:
        # Main face props
        if not scene.corinth:
            if face_prop.seam_sealer_override:
                face_properties.setdefault("bungie_face_type", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceType.seam_sealer.value)
            elif face_prop.sky_override:
                face_properties.setdefault("bungie_face_type", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceType.sky.value)
                face_properties.setdefault("bungie_sky_permutation_index", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, face_prop.sky_permutation_index)
            
        if face_prop.render_only_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceMode.render_only.value)
        elif face_prop.collision_only_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceMode.collision_only.value)
        elif face_prop.sphere_collision_only_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceMode.sphere_collision_only.value)
        elif face_prop.breakable_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceMode.breakable.value)
            
        if face_prop.face_two_sided_override:
            sides_value = FaceSides.two_sided.value
            if scene.corinth:
                match face_prop.face_two_sided_type:
                    case "mirror":
                        sides_value = FaceSides.mirror.value
                    case "keep":
                        sides_value = FaceSides.keep.value
                
            face_properties.setdefault("bungie_face_sides", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, sides_value)
            
        if face_prop.face_transparent_override:
            face_properties.setdefault("bungie_face_sides", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceSides.one_sided_transparent.value)
            
        if face_prop.face_draw_distance_override:
            match face_prop.face_draw_distance:
                case '_connected_geometry_face_draw_distance_detail_mid':
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceDrawDistance.detail_mid.value)
                case '_connected_geometry_face_draw_distance_detail_close':
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, FaceDrawDistance.detail_close.value)
                    
        if face_prop.face_global_material_override:
            face_properties.setdefault("bungie_face_global_material", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, scene.global_materials.index(face_prop.face_global_material.strip().replace(' ', "_")))
        if face_prop.region_name_override:
            face_properties.setdefault("bungie_face_region", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, scene.regions.index(face_prop.region_name))
            
        if face_prop.ladder_override:
            face_properties.setdefault("bungie_ladder", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
        if face_prop.slip_surface_override:
            face_properties.setdefault("bungie_slip_surface", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
        if face_prop.decal_offset_override:
            face_properties.setdefault("bungie_decal_offset", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_shadow_override:
            face_properties.setdefault("bungie_no_shadow", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_pvs_override:
            face_properties.setdefault("bungie_invisible_to_pvs", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_lightmap_override:
            face_properties.setdefault("bungie_no_lightmap", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
        if face_prop.precise_position_override:
            face_properties.setdefault("bungie_precise_position", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1)
            
        # Lightmap Props
        # if face_prop.lightmap_additive_transparency_override:
        #     face_properties["bungie_lightmap_additive_transparency"].append(face_prop)
        # if face_prop.lightmap_resolution_scale_override:
        #     face_properties["bungie_lightmap_ignore_default_resolution_scale"].append(face_prop)
        #     face_properties["bungie_lightmap_resolution_scale"].append(face_prop)
        # if face_prop.lightmap_type_override:
        #     face_properties["bungie_lightmap_type"].append(face_prop)
        # if face_prop.lightmap_translucency_tint_color_override:
        #     face_properties["bungie_lightmap_translucency_tint_color"].append(face_prop)
        # if face_prop.lightmap_lighting_from_both_sides_override:
        #     face_properties["bungie_lightmap_lighting_from_both_sides"].append(face_prop)
            
        # Emissives
        # if face_prop.emissive_override:
        #     face_properties["bungie_lighting_attenuation_enabled"].append(face_prop)
        #     face_properties["bungie_lighting_attenuation_cutoff"].append(face_prop)
        #     face_properties["bungie_lighting_attenuation_falloff"].append(face_prop)
        #     face_properties["bungie_lighting_emissive_focus"].append(face_prop)
        #     face_properties["bungie_lighting_emissive_color"].append(face_prop)
        #     face_properties["bungie_lighting_emissive_per_unit"].append(face_prop)
        #     face_properties["bungie_lighting_emissive_power"].append(face_prop)
        #     face_properties["bungie_lighting_emissive_quality"].append(face_prop)
        #     face_properties["bungie_lighting_frustum_blend"].append(face_prop)
        #     face_properties["bungie_lighting_frustum_cutoff"].append(face_prop)
        #     face_properties["bungie_lighting_frustum_falloff"].append(face_prop)
        #     face_properties["bungie_lighting_use_shader_gel"].append(face_prop)
        #     face_properties["bungie_lighting_bounce_ratio"].append(face_prop)
        #     face_properties["bungie_light_is_uber_light"].append(face_prop)
        
    for idx, face in enumerate(bm.faces):
        for v in face_properties.values():
            for layer, value in v.face_props.items():
                if face[layer]:          
                    v.array[idx] = value
                
        
    return {k: v.array for k, v in face_properties.items()}