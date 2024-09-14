'''Classes to store intermediate geometry data to be passed to granny files'''

from collections import defaultdict
import csv
from ctypes import Array, Structure, c_char_p, c_float, c_int, POINTER, c_ubyte, c_void_p, cast, memmove, pointer
from enum import Enum
import logging
from math import degrees
from pathlib import Path
import time
import bmesh
import bpy
from mathutils import Matrix
import numpy as np

from ..granny.formats import GrannyDataTypeDefinition, GrannyMaterial, GrannyMemberType, GrannyTriAnnotationSet, GrannyTriMaterialGroup, GrannyTriTopology, GrannyVertexData
from ..granny import Granny

from .export_info import ExportInfo, FaceDrawDistance, FaceMode, FaceSides, FaceType, LightmapType

from ..props.mesh import NWO_FaceProperties_ListItems, NWO_MeshPropertiesGroup

from .. import utils

from ..tools.asset_types import AssetType

from ..constants import IDENTITY_MATRIX, RENDER_MESH_TYPES, VALID_MESHES

logging.basicConfig(level=logging.ERROR)

DESIGN_MESH_TYPES = {
    "_connected_geometry_mesh_type_planar_fog_volume",
    "_connected_geometry_mesh_type_boundary_surface",
    "_connected_geometry_mesh_type_water_physics_volume",
    "_connected_geometry_mesh_type_poop_rain_blocker",
    "_connected_geometry_mesh_type_poop_vertical_rain_sheet",
}

def read_frame_id_list() -> list:
    filepath = Path(utils.addon_root(), "export", "frameidlist.csv")
    frame_ids = []
    with filepath.open(mode="r") as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        frame_ids = [row for row in csv_reader]

    return frame_ids

class MaterialExtendedData(Structure):
    _pack_ = 1
    _fields_ = [('shader_path', c_char_p), ('shader_type', c_char_p)]

class VirtualMaterial:  
    def __init__(self, name, scene: 'VirtualScene', shader_path: str | Path | None = None):
        self.name: str = name
        self.granny_material = None
        self.shader_path = "override"
        self.shader_type = "override"
        if shader_path is not None:
            if not str(shader_path).strip() or str(shader_path) == '.':
                return self.set_invalid(scene)
        
            path = Path(shader_path)
            full_path = Path(scene.tags_dir, shader_path)
            if not (full_path.exists() and full_path.is_file()):
                return self.set_invalid(scene)
        
        self.shader_path = str(path.with_suffix(""))
        self.shader_type = path.suffix[1:]
        
        self.to_granny_data(scene)
        
    def set_invalid(self, scene: 'VirtualScene'):
        self.shader_path = r"shaders\invalid"
        self.shader_type = "material" if scene.corinth else "shader"
    
    def to_granny_data(self, scene):
        self.granny_material = GrannyMaterial()
        self.granny_material.name = self.name.encode()
        data = MaterialExtendedData(shader_path=self.shader_path.encode(), shader_type=self.shader_type.encode())
        self.granny_material.extended_data.object = cast(pointer(data), c_void_p)
        self.granny_material.extended_data.type = scene.material_extended_data_type
        self.granny_material = pointer(self.granny_material)
    
class VirtualMesh:
    def __init__(self, vertex_weighted: bool, scene: 'VirtualScene', bone_bindings: list[str], ob: bpy.types.Object, fp_defaults: dict, render_mesh: bool):
        self.name = "default"
        self.positions: np.ndarray = None
        self.normals: np.ndarray = None
        self.bone_weights: np.ndarray = None
        self.bone_indices: np.ndarray = None
        self.texcoords: list[np.ndarray] = [] # Up to 4 uv layers
        self.lighting_texcoords: np.ndarray = None
        self.vertex_colors: list[np.ndarray] = [] # Up to two sets of vert colors
        self.indices: np.ndarray = None
        self.num_indices = 0
        self.groups: list[VirtualMaterial, int, int] = []
        self.materials = set()
        self.face_properties: dict = {}
        self.bone_bindings = bone_bindings
        self.vertex_weighted = vertex_weighted
        self.num_loops = 0
        self.invalid = False
        self._setup(ob, scene, fp_defaults, render_mesh)
        if not self.invalid:
            self.to_granny_data(scene)
            
        del self.positions
        del self.normals
        del self.bone_weights
        del self.bone_indices
        del self.texcoords
        del self.lighting_texcoords
        del self.vertex_colors
        del self.indices
        
    def to_granny_data(self, scene):
        self._granny_tri_topology()
        self._granny_vertex_data(scene)
        
    def _granny_tri_topology(self):
        indices = (c_int * self.num_indices).from_buffer_copy(self.indices.tobytes())

        granny_tri_topology = GrannyTriTopology()

        num_groups = len(self.groups)
        groups = (GrannyTriMaterialGroup * num_groups)()

        material_data = [(material[1], material[2][0], material[2][1]) for material in self.groups]
        for i, (material_index, tri_first, tri_count) in enumerate(material_data):
            groups[i].material_index = material_index
            groups[i].tri_first = tri_first
            groups[i].tri_count = tri_count

        granny_tri_topology.group_count = num_groups
        granny_tri_topology.groups = cast(groups, POINTER(GrannyTriMaterialGroup))
        granny_tri_topology.index_count = self.num_indices
        granny_tri_topology.indices = cast(indices, POINTER(c_int))

        # Handle Tri Annotation Sets
        if self.face_properties:
            num_tri_annotation_sets = len(self.face_properties)
            tri_annotation_sets = (GrannyTriAnnotationSet * num_tri_annotation_sets)()

            for i, (name, face_set) in enumerate(self.face_properties.items()):
                granny_tri_annotation_set = tri_annotation_sets[i]
                granny_tri_annotation_set.name = name.encode()
                granny_tri_annotation_set.indices_map_from_tri_to_annotation = 1
                        
                granny_tri_annotation_set.tri_annotation_type = face_set.annotation_type
                
                num_tri_annotations = len(face_set.array)
                annotation_byte_array = face_set.array.tobytes()
                annotation_array = (c_ubyte * len(annotation_byte_array)).from_buffer_copy(annotation_byte_array)
                
                granny_tri_annotation_set.tri_annotation_count = num_tri_annotations
                granny_tri_annotation_set.tri_annotations = cast(annotation_array, POINTER(c_ubyte))

            granny_tri_topology.tri_annotation_set_count = num_tri_annotation_sets
            granny_tri_topology.tri_annotation_sets = cast(tri_annotation_sets, POINTER(GrannyTriAnnotationSet))

        self.granny_tri_topology = pointer(granny_tri_topology)
        
    def _granny_vertex_data(self, scene: 'VirtualScene'):
        data = [self.positions, self.normals]
        types = [
            GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Position", None, 3),
            GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Normal", None, 3)
        ]
        type_names = [b"Position", b"Normal"]
        
        if self.bone_weights is not None:
            data.extend([self.bone_weights, self.bone_indices])
            types.extend([
                GrannyDataTypeDefinition(GrannyMemberType.granny_uint8_member.value, b"BoneWeights", None, 4),
                GrannyDataTypeDefinition(GrannyMemberType.granny_uint8_member.value, b"BoneIndices", None, 4)
            ])
            type_names.extend([b"BoneWeights", b"BoneIndices"])
        
        for idx, uvs in enumerate(self.texcoords):
            name = f"TextureCoordinates{idx}".encode()
            data.append(uvs)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, name, None, 3))
            type_names.append(name)
            
        if self.lighting_texcoords is not None:
            data.append(self.lighting_texcoords)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"TextureCoordinateslighting", None, 3))
            type_names.append(b"lighting")
            
        for idx, vcolors in enumerate(self.vertex_colors):
            name = f"colorSet{idx + 1}".encode() if scene.corinth else f"DiffuseColor{idx}".encode()
            data.append(vcolors)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, name, None, 3))
            type_names.append(name)

        types.append((GrannyMemberType.granny_end_member.value, None, None, 0))
        
        num_types = len(type_names)
        names_array = (c_char_p * num_types)(*type_names)
        self.vertex_component_names = cast(names_array, POINTER(c_char_p))
        self.vertex_component_name_count = num_types
        
        type_info_array = (GrannyDataTypeDefinition * (num_types + 1))(*types)
        self.vertex_type = cast(type_info_array, POINTER(GrannyDataTypeDefinition))
        
        contiguous_data = [np.ascontiguousarray(arr) for arr in data]
        vertex_byte_array = np.hstack(contiguous_data).tobytes()

        self.len_vertex_array = len(vertex_byte_array)
        self.vertex_array = (c_ubyte * self.len_vertex_array).from_buffer_copy(vertex_byte_array)
        
    def _setup(self, ob: bpy.types.Object, scene: 'VirtualScene', fp_defaults: dict, render_mesh: bool):
        def add_triangle_mod(ob: bpy.types.Object):
            mods = ob.modifiers
            for m in mods:
                if m.type == 'TRIANGULATE': return
                
            tri_mod = mods.new('Triangulate', 'TRIANGULATE')
            tri_mod.quad_method = 'FIXED'
            
        add_triangle_mod(ob)
        mesh = ob.to_mesh(preserve_all_data_layers=True, depsgraph=scene.depsgraph)
        self.name = mesh.name
        if not mesh.polygons:
            scene.warnings.append(f"Mesh data [{self.name}] of object [{ob.name}] has no faces. {ob.name} removed from geometry tree")
            self.invalid = True
            return
        
        unique_materials = list(dict.fromkeys([m for m in mesh.materials]))
        num_materials = len(mesh.materials)
        special_mats_dict = defaultdict(list)
        for idx, mat in enumerate([m for m in mesh.materials if m.nwo.has_material_properties or m.name[0] == "+"]):
            special_mats_dict[mat].append(idx)
                
        sorted_order = None
        
        num_loops = len(mesh.loops)
        num_vertices = len(mesh.vertices)
        num_polygons = len(mesh.polygons)
        
        vertex_positions = np.empty((num_vertices, 3), dtype=np.single)
        loop_vertex_indices = np.empty(num_loops, dtype=np.int32)
        
        mesh.vertices.foreach_get("co", vertex_positions.ravel())
        mesh.loops.foreach_get("vertex_index", loop_vertex_indices)
        
        self.positions = vertex_positions[loop_vertex_indices]
        self.normals = np.empty((num_loops, 3), dtype=np.single)
        mesh.corner_normals.foreach_get("vector", self.normals.ravel())
        
        loop_starts = np.empty(num_polygons, dtype=np.int32)
        loop_totals = np.empty(num_polygons, dtype=np.int32)
        
        mesh.polygons.foreach_get("loop_start", loop_starts)
        mesh.polygons.foreach_get("loop_total", loop_totals)
        self.indices = np.add.outer(loop_starts, np.arange(loop_totals.max())).flatten()[:loop_totals.sum()]

        if num_materials > 1:
            material_indices = np.empty(num_polygons, dtype=np.int32)
            mesh.polygons.foreach_get("material_index", material_indices)
            sorted_order = np.argsort(material_indices)
            sorted_polygons = self.indices.reshape((-1, 3))[sorted_order]
            self.indices = sorted_polygons.ravel()
            unique_indices = np.concatenate(([0], np.where(np.diff(material_indices[sorted_order]) != 0)[0] + 1))
            counts = np.diff(np.concatenate((unique_indices, [len(material_indices)])))
            mat_index_counts = list(zip(unique_indices, counts))
            used_materials = [mesh.materials[i] for i in np.unique(material_indices)]
            for idx, mat in enumerate(used_materials):
                virtual_mat = scene._get_material(mat, scene)
                self.materials.add(virtual_mat)
                self.groups.append((scene._get_material(mat, scene), unique_materials.index(mat), mat_index_counts[idx]))
        else:
            if num_materials == 1:
                virtual_mat = scene._get_material(mesh.materials[0], scene)
                self.materials.add(virtual_mat)
                self.groups.append((virtual_mat, 0, (0, num_polygons)))
            else:
                virtual_mat = scene.materials["invalid"]
                self.materials.add(virtual_mat)
                self.groups.append((virtual_mat, 0, (0, num_polygons))) # default material
        
        self.num_indices = len(self.indices)
        
        if self.vertex_weighted:
            unique_bone_indices = set()
            bone_weights = np.zeros((num_loops, 4), dtype=np.int32)
            bone_indices = np.zeros((num_loops, 4), dtype=np.int32)

            for loop_index, loop in enumerate(mesh.loops):
                vertex_index = loop.vertex_index
                vertex = mesh.vertices[vertex_index]
                groups = vertex.groups

                if groups:
                    weights = np.empty(len(groups), dtype=np.single)
                    indices = np.empty(len(groups), dtype=np.int32)
                    groups.foreach_get("weight", weights)
                    groups.foreach_get("group", indices)

                    top_indices = np.argsort(-weights)[:4]
                    top_weights = weights[top_indices]
                    top_bone_indices = indices[top_indices]

                    top_weights /= top_weights.sum()
                    bone_weights[loop_index] = np.pad((top_weights * 255).astype(np.int32), (0, 4 - len(top_weights)))
                    bone_indices[loop_index] = np.pad(top_bone_indices, (0, 4 - len(top_bone_indices)))

                    unique_bone_indices.update(top_bone_indices)

            self.bone_weights = bone_weights
            self.bone_indices = bone_indices
            self.bone_bindings = [scene.valid_bones[idx] for idx in unique_bone_indices]
        
        if render_mesh:
            # We only care about writing this data if the in game mesh will have a render definition
            for idx, layer in enumerate(mesh.uv_layers):
                if len(self.texcoords) >= 4:
                    break
                
                loop_uvs = np.empty((num_loops, 2), dtype=np.single)
                layer.uv.foreach_get("vector", loop_uvs.ravel())
                zeros_column = np.zeros((num_loops, 1), dtype=np.single)
                combined_uvs = np.hstack((loop_uvs, zeros_column))
                if layer.name.lower() == "lighting":
                    self.lighting_texcoords = combined_uvs
                else:
                    self.texcoords.append(combined_uvs)
                    
            for idx, layer in enumerate(mesh.color_attributes):
                if len(self.vertex_colors) >= 2:
                    break
                
                colors = np.empty((num_vertices, 4) if layer.domain == 'POINT' else (num_loops, 4), dtype=np.single)
                layer.data.foreach_get("color", colors.ravel())
                colors = colors[:, :3]
                if layer.domain == 'POINT':
                    colors = colors[loop_vertex_indices]
    
                self.vertex_colors.append(colors)
                
        self.num_loops = num_loops
        if ob.original.data.nwo.face_props or special_mats_dict:
            self.face_properties = gather_face_props(ob.original.data.nwo, mesh, num_polygons, scene, sorted_order, special_mats_dict, fp_defaults)
        
        
    # def _setup(self, mesh: bpy.types.Mesh, scene: 'VirtualScene', ob: bpy.types.Object):
        
    #     unique_materials = list(dict.fromkeys([m for m in mesh.materials]))
        
    #     bm = bmesh.new()
    #     bm.from_mesh(mesh)
    #     # bmesh stuff goes here
        
    #     if mesh.has_custom_normals:
    #         print("has custom normals??")
    #         pass # Code for splitting mesh goes here
    #     else:
    #         # print(mesh.normals_domain)
    #         match mesh.normals_domain:
    #             case 'FACE': # Using polygon normals, split all the edges
    #                 bmesh.ops.split_edges(bm, edges=bm.edges)
    #             case 'CORNER': # Split edges only if they are sharp
    #                 bmesh.ops.split_edges(bm, edges=[edge for edge in bm.edges if not edge.smooth])
    #             # Last option is vertex normals (smooth shading), don't need to edge split
        
    #     bmesh.ops.triangulate(bm, faces=bm.faces) # granny only supports tris for faces
    #     bm.faces.sort(key=lambda face: face.material_index) # faces set sorted by material index, important for granny
        
    #     bm.to_mesh(mesh)
            
    #     self.num_vertices = len(mesh.vertices)
    #     num_polygons = len(mesh.polygons)
        
    #     if mesh.nwo.face_props:
    #         self.face_properties = gather_face_props(mesh.nwo, bm, num_polygons, scene)
            
    #     bm.free()
        
    #     num_materials = len(mesh.materials)
    #     num_loops = len(mesh.loops)
    #     positions = np.empty(self.num_vertices * 3, dtype=np.float32)
    #     normals = positions.copy()
    #     mesh.vertices.foreach_get("co", positions)
    #     self.positions = positions.reshape(-1, 3)
        
    #     # Get normals - for granny these are always vertex normals
    #     mesh.vertices.foreach_get("normal", normals)
    #     self.normals = normals.reshape(-1, 3)
    #     # match mesh.normals_domain:
    #     #     case 'FACE':
    #     #         normals = mesh.polygon_normals
    #     #     case 'POINT':
    #     #         mesh.vertex_normals.foreach_get("vector", normals)
    #     #     case _:
    #     #         normals = mesh.corner_normals
        
    #     self.indices = np.empty(num_polygons * 3, dtype=np.int32)
    #     mesh.polygons.foreach_get("vertices", self.indices)
    #     if num_materials > 1:
    #         material_indices = np.empty(num_polygons, dtype=np.int32)
    #         mesh.polygons.foreach_get("material_index", material_indices)
    #         unique_indices = np.concatenate(([0], np.where(np.diff(material_indices) != 0)[0] + 1))
    #         counts = np.diff(np.concatenate((unique_indices, [len(material_indices)])))
    #         mat_index_counts = list(zip(unique_indices, counts))
    #         for idx, mat in enumerate(mesh.materials):
    #             self.materials.append((scene._get_material(mat, scene), unique_materials.index(mat), mat_index_counts[idx]))
    #     elif num_materials == 1:
    #         self.materials.append((scene._get_material(mesh.materials[0], scene), 0, (0, num_polygons)))
    #     else:
    #         self.materials.append((scene.materials["invalid"], 0, (0, num_polygons))) # default material
        
    #     # Bone Weights & Indices
    #     self.bone_weights = np.zeros((self.num_vertices * 4, 4), dtype=np.byte)
    #     self.bone_indices = np.zeros((self.num_vertices * 4, 4), dtype=np.byte)
        
    #     if self.vertex_weighted:
    #         unique_bone_indices = set()
    #         invalid_indices = set()
    #         vertex_group_names = []
    #         for idx, vgroup in enumerate(ob.vertex_groups):
    #             name = vgroup.name
    #             if name in scene.valid_bones:
    #                 vertex_group_names.append(name)
    #             else:
    #                 invalid_indices.add(idx)
                    
    #         for i in range(self.num_vertices):
    #             groups = mesh.vertices[i].groups
    #             num_groups = len(groups)
    #             weights = np.empty(num_groups, dtype=np.single)
    #             indices = np.empty(num_groups, dtype=np.int32)
    #             groups.foreach_get("weight", weights)
    #             groups.foreach_get("group", indices)
                
    #             if len(weights) > 0:
    #                 sorted_indices = np.argsort(-weights)
    #                 top_weights = weights[sorted_indices[:4]]
    #                 top_indices = indices[sorted_indices[:4]]
    #                 unique_bone_indices.update(top_indices)
                    
    #                 top_weights /= top_weights.sum()
                    
    #                 if len(top_weights) < 4:
    #                     top_weights = np.pad(top_weights, (0, 4 - len(top_weights)), 'constant', constant_values=0)
    #                     top_indices = np.pad(top_indices, (0, 4 - len(top_indices)), 'constant', constant_values=0)

    #                 self.bone_weights[i] = [int(w * 255.0) for w in top_weights]
    #                 self.bone_indices[i] = top_indices
            
    #         self.bone_bindings.clear()
    #         for index in unique_bone_indices:
    #             self.bone_bindings.append(vertex_group_names[index])
        
    #     loop_vertices = np.empty(num_loops, dtype=np.int32)
    #     mesh.loops.foreach_get("vertex_index", loop_vertices)
        
    #     # Texcoords
    #     for layer in mesh.uv_layers:
    #         if len(self.texcoords) >= 4:
    #             break
            
    #         loop_uvs = np.empty(num_loops * 2, dtype=np.float32)
    #         layer.uv.foreach_get("vector", loop_uvs)
    #         loop_uvs = loop_uvs.reshape(-1, 2)

    #         vertex_uvs = [[] for _ in range(self.num_vertices)]

    #         for loop_idx, vert_idx in enumerate(loop_vertices):
    #             vertex_uvs[vert_idx].append(loop_uvs[loop_idx])

    #         averaged_vertex_uvs = np.zeros((self.num_vertices, 2), dtype=np.float32)

    #         for vert_idx, uvs in enumerate(vertex_uvs):
    #             if uvs:
    #                 averaged_vertex_uvs[vert_idx] = np.mean(uvs, axis=0)
    #             else:
    #                 averaged_vertex_uvs[vert_idx] = [0, 0]

            
    #         if layer.name.lower() == "lighting":
    #             self.lighting_texcoords = averaged_vertex_uvs
    #         else:
    #             self.texcoords.append(averaged_vertex_uvs)
                
    #     # Vertex Colors
    #     for layer in mesh.color_attributes:
    #         if len(self.vertex_colors) >= 2:
    #             break
    #         point_colors =  layer.domain == 'POINT'
    #         num_colors = self.num_vertices if point_colors else num_loops
    #         colors = np.empty(num_colors * 4, dtype=np.float32)
    #         layer.data.foreach_get("color", colors)
    #         colors = colors.reshape(-1, 4)
            
    #         if point_colors:
    #             self.vertex_colors.append(colors)
    #             continue
            
    #         vertex_colors = [[] for _ in range(self.num_vertices)]

    #         for loop_idx, vert_idx in enumerate(loop_vertices):
    #             vertex_colors[vert_idx].append(colors[loop_idx])

    #         averaged_vertex_colors = np.zeros((self.num_vertices, 4), dtype=np.float32)

    #         for vert_idx, cols in enumerate(vertex_colors):
    #             if cols:
    #                 averaged_vertex_colors[vert_idx] = np.mean(cols, axis=0)
    #             else:
    #                 averaged_vertex_colors[vert_idx] = [0, 0, 0, 0]
            
    #         self.vertex_colors.append(averaged_vertex_colors)
            
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
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone, props: dict, region: str = None, permutation: str = None, fp_defaults: dict = None, scene: 'VirtualScene' = None):
        self.name: str = "object"
        self.matrix_world: Matrix = IDENTITY_MATRIX
        self.matrix_local: Matrix = IDENTITY_MATRIX
        self.mesh: VirtualMesh | None = None
        self.new_mesh = False
        self.skeleton: VirtualSkeleton = None
        self.region = region
        self.permutation = permutation
        self.props = props
        self.group: str = "default"
        self.tag_type: str = "render"
        self.invalid = False
        self._set_group(scene)
        self.parent: VirtualNode = None
        self.selected = False
        self.bone_bindings: list[str] = []
        self.granny_vertex_data = None
        if not self.invalid:
            self._setup(id, scene, fp_defaults)
        
    def _setup(self, id: bpy.types.Object | bpy.types.PoseBone, scene: 'VirtualScene', fp_defaults: dict):
        self.name = id.name
        if isinstance(id, bpy.types.Object):
            self.selected = id.original.select_get()
            self.matrix_world = id.original.matrix_world.copy()
            self.matrix_local = id.original.matrix_local.copy()
            if id.type in VALID_MESHES:
                default_bone_bindings = [self.name]
                existing_mesh = scene.meshes.get(id.data.name)
                if existing_mesh:
                    self.mesh = existing_mesh
                    self.bone_bindings = existing_mesh.bone_bindings
                else:
                    vertex_weighted = id.vertex_groups and id.parent and id.parent.type == 'ARMATURE' and id.parent_type != "BONE" and has_armature_deform_mod(id)
                    mesh = VirtualMesh(vertex_weighted, scene, default_bone_bindings, id, fp_defaults, is_rendered(self.props))
                    id.to_mesh_clear()
                    self.mesh = mesh
                    self.new_mesh = True
                    self.bone_bindings = mesh.bone_bindings
                    
                if self.mesh.invalid:
                    self.invalid = True
                    return
                    
                self.granny_vertex_data = GrannyVertexData()
                self.granny_vertex_data.vertex_component_names = self.mesh.vertex_component_names
                self.granny_vertex_data.vertex_component_name_count = self.mesh.vertex_component_name_count
                self.granny_vertex_data.vertex_type = self.mesh.vertex_type
                vertex_array = (c_ubyte * self.mesh.len_vertex_array)()
                if self.matrix_world == IDENTITY_MATRIX:
                    vertex_array = self.mesh.vertex_array
                else:
                    vertex_array = (c_ubyte * self.mesh.len_vertex_array)()
                    memmove(vertex_array, self.mesh.vertex_array, self.mesh.len_vertex_array)
                    affine3, linear3x3, inverse_linear3x3 = calc_transforms(self.matrix_world)
                    scene.granny._transform_vertices(self.mesh.num_loops,
                                                    self.granny_vertex_data.vertex_type,
                                                    vertex_array,
                                                    affine3,
                                                    linear3x3,
                                                    inverse_linear3x3,
                                                    True,
                                                    False,
                                                    )
                
                self.granny_vertex_data.vertices = cast(vertex_array, POINTER(c_ubyte))
                self.granny_vertex_data.vertex_count = self.mesh.num_loops
                self.granny_vertex_data = pointer(self.granny_vertex_data)
                    
            
    def _set_group(self, scene: 'VirtualScene'):
        match scene.asset_type:
            case AssetType.MODEL:
                mesh_type = self.props.get("bungie_mesh_type")
                if mesh_type:
                    match mesh_type:
                        case '_connected_geometry_mesh_type_default' | '_connected_geometry_mesh_type_object_instance':
                            self.tag_type = 'render'
                        case '_connected_geometry_mesh_type_collision':
                            self.tag_type = 'collision'
                        case '_connected_geometry_mesh_type_physics':
                            self.tag_type = 'physics'
                    
                    self.group = f'{self.tag_type}_{self.permutation}'
                    
                else:
                    object_type = self.props.get("bungie_object_type")
                    if not object_type:
                        self.invalid = True
                        scene.warnings.append(f"Object [{self.name}] has no Halo object type")
                        return
                    
                    match object_type:
                        case '_connected_geometry_object_type_marker':
                            self.tag_type = 'markers'
                        case '_connected_geometry_object_type_frame':
                            self.tag_type = 'skeleton'
                            
                    self.group = self.tag_type
            
            case AssetType.SCENARIO:
                mesh_type = self.props.get("bungie_mesh_type")
                if mesh_type in DESIGN_MESH_TYPES:
                    self.tag_type = 'design'
                    scene.design.add(self.region)
                elif self.region == 'shared':
                    self.tag_type = 'shared'
                else:
                    self.tag_type = 'structure'
                    scene.structure.add(self.region)
                    if mesh_type == '_connected_geometry_mesh_type_default':
                        scene.bsps_with_structure.add(self.region)
                    
                self.group = f'{self.tag_type}_{self.region}_{self.permutation}'
                
            case AssetType.PREFAB:
                self.tag_type = 'structure'
                self.group = f'{self.tag_type}_{self.permutation}'
                
            case _:
                self.tag_type = 'render'
                self.group = 'default'
                
    
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
        self.matrix_local: Matrix = IDENTITY_MATRIX
        self.matrix_world: Matrix = IDENTITY_MATRIX
        self.props = {}
        
    def create_bone_props(self, bone, frame_ids):
        self.props["bungie_frame_ID1"] = frame_ids[0]
        self.props["bungie_frame_ID2"] = frame_ids[1]
        self.props["bungie_object_animates"] = "1"
        self.props["bungie_object_type"] = "_connected_geometry_object_type_frame"
        
class VirtualSkeleton:
    '''Describes a list of bones'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene', node: VirtualNode):
        self.name: str = ob.name
        own_bone = VirtualBone(ob)
        own_bone.node = node
        own_bone.matrix_world = own_bone.node.matrix_world
        own_bone.matrix_local = IDENTITY_MATRIX
        if ob.type == 'ARMATURE':
            own_bone.props = {
                    "bungie_frame_world": "1",
                    "bungie_frame_ID1": "8078",
                    "bungie_frame_ID2": "378163771",
                    "bungie_object_type": "_connected_geometry_object_type_frame",
                }
        elif own_bone.node:
            own_bone.props = own_bone.node.props
        self.bones: list[VirtualBone] = [own_bone]
        self._get_bones(ob, scene)
        
    def _get_bones(self, ob, scene: 'VirtualScene'):
        if ob.type == 'ARMATURE':
            valid_bones = [pbone for pbone in ob.pose.bones if ob.data.bones[pbone.name].use_deform]
            list_bones = [pbone.name for pbone in valid_bones]
            for idx, bone in enumerate(valid_bones):
                bone: bpy.types.PoseBone
                b = VirtualBone(bone)
                b.create_bone_props(bone, scene.frame_ids[idx])
                b.matrix_world = bone.matrix.copy()
                # b.properties = utils.get_halo_props_for_granny(ob.data.bones[idx])
                if bone.parent:
                    # Add one to this since the root is the armature
                    b.parent_index = list_bones.index(bone.parent.name) + 1
                    b.matrix_local = utils.get_bone_matrix_local(ob, bone)
                else:
                    b.parent_index = 0
                    b.matrix_local = bone.matrix.copy()
                self.bones.append(b)
                
            child_index = 0
            for child in scene.get_immediate_children(ob):
                node = scene.add(child, *scene.object_halo_data[child])
                if not node: continue
                child_index += 1
                if not node or node.invalid: continue
                b = VirtualBone(child)
                b.node = node
                if child.type != 'MESH':
                    b.props = b.node.props
                b.matrix_world = child.matrix_world.copy()
                b.matrix_local = child.matrix_local.copy()
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
        for child in scene.get_immediate_children(ob):
            node = scene.add(child, *scene.object_halo_data[child])
            if not node or node.invalid: continue
            child_index += 1
            b = VirtualBone(child)
            b.parent_index = parent_index
            b.node = node
            if child.type != 'MESH':
                b.props = b.node.props
            b.matrix_world = b.node.matrix_world
            b.matrix_local = b.node.matrix_local
            self.bones.append(b)
            self.find_children(child, scene, child_index)
    
class VirtualModel:
    '''Describes a blender object which has no parent'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene'):
        self.name: str = ob.name
        self.node = None
        node = scene.add(ob, *scene.object_halo_data[ob])
        if node and not node.invalid:
            self.node = node
            self.skeleton: VirtualSkeleton = VirtualSkeleton(ob, scene, self.node)
            self.matrix: Matrix = ob.matrix_world.copy()
            if ob.type == 'ARMATURE':
                if not scene.skeleton_node:
                    scene.skeleton_node = self.node
            
class VirtualScene:
    def __init__(self, asset_type: AssetType, depsgraph: bpy.types.Depsgraph, corinth: bool, tags_dir: Path, granny: Granny):
        self.nodes: dict[VirtualNode] = {}
        self.meshes: dict[VirtualMesh] = {}
        self.materials: dict[VirtualMaterial] = {}
        self.models: dict[VirtualModel] = {}
        self.root: VirtualNode = None
        self.asset_type = asset_type
        self.depsgraph = depsgraph
        self.tags_dir = tags_dir
        self.granny = granny
        self.regions: list = []
        self.regions_set: set()
        self.permutations: list = []
        self.global_materials: list = []
        self.global_materials_set: set()
        self.skeleton_node: VirtualNode = None
        self.corinth = corinth
        self.export_info: ExportInfo = None
        self.valid_bones = []
        self.frame_ids = read_frame_id_list()
        self.structure = set()
        self.design = set()
        self.bsps_with_structure = set()
        self.warnings = []
        
        self.object_parent_dict: dict[bpy.types.Object: bpy.types.Object] = {}
        self.object_halo_data: dict[bpy.types.Object: tuple[dict, str, str]] = {}
        
        self.material_extended_data_type = self._create_material_extended_data_type()
        
        # Create default material
        if corinth:
            default_material = VirtualMaterial("invalid", self, r"shaders\invalid.material")
        else:
            default_material = VirtualMaterial("invalid", self, r"shaders\invalid.shader")
            
        self.materials["invalid"] = default_material
        
    def _create_material_extended_data_type(self):
        material_extended_data_type = (GrannyDataTypeDefinition * 3)()
        material_extended_data_type[0] = GrannyDataTypeDefinition(member_type=GrannyMemberType.granny_string_member, name=b"bungie_shader_path")
        material_extended_data_type[1] = GrannyDataTypeDefinition(member_type=GrannyMemberType.granny_string_member, name=b"bungie_shader_type")
        material_extended_data_type[2] = GrannyDataTypeDefinition(GrannyMemberType.granny_end_member.value)
        
        return material_extended_data_type
        
        
    def add(self, id: bpy.types.Object, props: dict, region: str = None, permutation: str = None, fp_defaults: dict = None):
        '''Creates a new node with the given parameters and appends it to the virtual scene'''
        node = VirtualNode(id, props, region, permutation, fp_defaults, self)
        if not node.invalid:
            self.nodes[node.name] = node
            if node.new_mesh:
                self.meshes[node.mesh.name] = node.mesh
            
        return node
            
    def get_immediate_children(self, parent):
        children = [ob for ob, ob_parent in self.object_parent_dict.items() if ob_parent == parent]
        return children
        
    def add_model(self, ob):
        model = VirtualModel(ob, self)
        if model.node:
            self.models[ob.name] = model
        else:
            del model
        
    def _get_material(self, material: bpy.types.Material, scene):
        virtual_mat = self.materials.get(material.name)
        if virtual_mat: return virtual_mat
        mat_name = material.name
        if mat_name[0] == "+":
            virtual_mat = VirtualMaterial(material.name, scene)
        else:
            shader_path = material.nwo.shader_path
            if not shader_path.strip():
                virtual_mat = VirtualMaterial(material.name, scene, "")
            else:
                relative = utils.relative_path(shader_path)
                virtual_mat = VirtualMaterial(material.name, scene, relative)
                
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
        self.annotation_type = None
        self._set_tri_annotation_type()
        
    def update(self, bm: bmesh.types.BMesh, layer_name: str, value: object):
        layer = bm.faces.layers.int.get(layer_name)
        if layer:
            self.face_props[layer] = value
            
    def update_from_material(self, bm: bmesh.types.BMesh, material_indexes: list[int], value: object):
        for idx in material_indexes:
            self.face_props[idx] = value
            
    def _set_tri_annotation_type(self):
        annotation_type = []
        if len(self.array.shape) == 1:
            size = 1
        else:
            size = self.array.shape[1]
        match self.array.dtype:
            case np.single:
                annotation_type.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Real32", None, size))
            case np.int32:
                annotation_type.append(GrannyDataTypeDefinition(GrannyMemberType.granny_int32_member.value, b"Int32", None, size))
            case np.uint8:
                annotation_type.append(GrannyDataTypeDefinition(GrannyMemberType.granny_uint8_member.value, b"Uint8", None, size))
            case _:
                raise(f"Unimplemented numpy data type: {self.array.dtype}")
            
        annotation_type.append(GrannyDataTypeDefinition(0, None, None, 0))
        
        type_info_array = (GrannyDataTypeDefinition * 2)(*annotation_type)
        self.annotation_type = cast(type_info_array, POINTER(GrannyDataTypeDefinition))
            

def gather_face_props(mesh_props: NWO_MeshPropertiesGroup, mesh: bpy.types.Mesh, num_faces: int, scene: VirtualScene, sorted_order, special_mats_dict: dict, fp_defaults: dict) -> dict:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    
    face_properties = {}
    
    side_layers = {}
    
    for face_prop in mesh_props.face_props:
        if face_prop.render_only_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.render_only.value)
        elif face_prop.collision_only_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.collision_only.value)
        elif face_prop.sphere_collision_only_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.sphere_collision_only.value)
        elif face_prop.breakable_override:
            face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.breakable.value)
            
        if face_prop.face_two_sided_override:
            two_sided_layer = bm.faces.layers.int.get(face_prop.layer_name)
            if two_sided_layer:
                sides_value = FaceSides.two_sided.value
                if scene.corinth:
                    match face_prop.face_two_sided_type:
                        case "mirror":
                            sides_value = FaceSides.mirror.value
                        case "keep":
                            sides_value = FaceSides.keep.value
                            
                side_layers[two_sided_layer] = sides_value
                    
                face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, fp_defaults["bungie_face_sides"], np.uint8))).update(bm, face_prop.layer_name, -sides_value)
            
        if face_prop.face_transparent_override:
            transparent_layer = bm.faces.layers.int.get(face_prop.layer_name)
            if transparent_layer:
                side_layers[transparent_layer] = 1
                face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, fp_defaults["bungie_face_sides"], np.uint8))).update(bm, face_prop.layer_name, -FaceSides.one_sided_transparent.value)
            
        if face_prop.face_draw_distance_override:
            match face_prop.face_draw_distance:
                case '_connected_geometry_face_draw_distance_detail_mid':
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.full(num_faces, fp_defaults["bungie_face_draw_distance"], np.uint8))).update(bm, face_prop.layer_name, FaceDrawDistance.detail_mid.value)
                case '_connected_geometry_face_draw_distance_detail_close':
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.full(num_faces, fp_defaults["bungie_face_draw_distance"], np.uint8))).update(bm, face_prop.layer_name, FaceDrawDistance.detail_close.value)
                    
        if face_prop.face_global_material_override:
            gmv = 0
            default_global_material = fp_defaults["bungie_face_global_material"]
            if default_global_material in scene.global_materials_set:
                gmv = scene.global_materials.index(fp_defaults["bungie_face_global_material"])
            face_properties.setdefault("bungie_face_global_material", FaceSet(np.full(num_faces, gmv, np.int32))).update(bm, face_prop.layer_name, scene.global_materials.index(face_prop.face_global_material.strip().replace(' ', "_")))
        if scene.asset_type.supports_regions and face_prop.region_name_override:
            rv = 0
            default_region = fp_defaults["bungie_face_region"]
            if default_region in scene.regions_set:
                rv = scene.regions.index(fp_defaults["bungie_face_region"])
            face_properties.setdefault("bungie_face_region", FaceSet(np.full(num_faces, rv, np.int32))).update(bm, face_prop.layer_name, scene.regions.index(face_prop.region_name))
            
        if face_prop.ladder_override:
            face_properties.setdefault("bungie_ladder", FaceSet(np.full(num_faces, fp_defaults["bungie_ladder"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.slip_surface_override:
            face_properties.setdefault("bungie_slip_surface", FaceSet(np.full(num_faces, fp_defaults["bungie_slip_surface"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.decal_offset_override:
            face_properties.setdefault("bungie_decal_offset", FaceSet(np.full(num_faces, fp_defaults["bungie_decal_offset"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_shadow_override:
            face_properties.setdefault("bungie_no_shadow", FaceSet(np.full(num_faces, fp_defaults["bungie_no_shadow"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_pvs_override:
            face_properties.setdefault("bungie_invisible_to_pvs", FaceSet(np.full(num_faces, fp_defaults["bungie_invisible_to_pvs"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_lightmap_override:
            face_properties.setdefault("bungie_no_lightmap", FaceSet(np.full(num_faces, fp_defaults["bungie_no_lightmap"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.precise_position_override:
            face_properties.setdefault("bungie_precise_position", FaceSet(np.full(num_faces, fp_defaults["bungie_precise_position"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.mesh_tessellation_density_override:
            match face_prop.mesh_tessellation_density:
                case '_connected_geometry_mesh_tessellation_density_4x':
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, fp_defaults["bungie_mesh_tessellation_density"], np.uint8))).update(bm, face_prop.layer_name, 1)
                case '_connected_geometry_mesh_tessellation_density_9x':
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, fp_defaults["bungie_mesh_tessellation_density"], np.uint8))).update(bm, face_prop.layer_name, 2)
                case '_connected_geometry_mesh_tessellation_density_36x':
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, fp_defaults["bungie_mesh_tessellation_density"], np.uint8))).update(bm, face_prop.layer_name, 3)
            
        # Lightmap Props
        if face_prop.lightmap_additive_transparency_override:
            face_properties.setdefault("bungie_lightmap_additive_transparency", FaceSet(np.full((num_faces, 4), fp_defaults["bungie_lightmap_additive_transparency"], np.single))).update(bm, face_prop.layer_name, utils.color_4p(face_prop.lightmap_additive_transparency))
        if face_prop.lightmap_resolution_scale_override:
            # face_properties.setdefault("bungie_lightmap_ignore_default_resolution_scale", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1) # TODO needs to be own settable prop
            face_properties.setdefault("bungie_lightmap_resolution_scale", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_resolution_scale"], np.uint8))).update(bm, face_prop.layer_name, face_prop.lightmap_resolution_scale)
        if face_prop.lightmap_type_override:
            if face_prop.lightmap_type == '_connected_geometry_lightmap_type_per_vertex':
                face_properties.setdefault("bungie_lightmap_type", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_type"], np.uint8))).update(bm, face_prop.layer_name, LightmapType.per_vertex.value)
            else:
                face_properties.setdefault("bungie_lightmap_type", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_type"], np.uint8))).update(bm, face_prop.layer_name, LightmapType.per_pixel.value)
        if face_prop.lightmap_translucency_tint_color_override:
            face_properties.setdefault("bungie_lightmap_translucency_tint_color", FaceSet(np.full((num_faces, 4), fp_defaults["bungie_lightmap_translucency_tint_color"], np.single))).update(bm, face_prop.layer_name, utils.color_4p(face_prop.lightmap_translucency_tint_color))
        if face_prop.lightmap_lighting_from_both_sides_override:
            face_properties.setdefault("bungie_lightmap_lighting_from_both_sides", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_lighting_from_both_sides"], np.uint8))).update(bm, face_prop.layer_name, 1)
        
        # TODO fp_defaults for emissives here + in process.py
        
        # Emissives
        if face_prop.emissive_override:
            face_properties.setdefault("bungie_lighting_emissive_power", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_emissive_power"], np.single))).update(bm, face_prop.layer_name, face_prop.material_lighting_emissive_power)
            face_properties.setdefault("bungie_lighting_emissive_color", FaceSet(np.full((num_faces, 4), fp_defaults["bungie_lighting_emissive_color"], np.single))).update(bm, face_prop.layer_name, utils.color_4p(face_prop.material_lighting_emissive_color))
            face_properties.setdefault("bungie_lighting_emissive_per_unit", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_emissive_per_unit"], np.uint8))).update(bm, face_prop.layer_name, 1)
            face_properties.setdefault("bungie_lighting_emissive_quality", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_emissive_quality"], np.single))).update(bm, face_prop.layer_name, face_prop.material_lighting_emissive_quality)
            face_properties.setdefault("bungie_lighting_use_shader_gel", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_use_shader_gel"], np.uint8))).update(bm, face_prop.layer_name, 1)
            face_properties.setdefault("bungie_lighting_bounce_ratio", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_bounce_ratio"], np.single))).update(bm, face_prop.layer_name, face_prop.material_lighting_bounce_ratio)
            face_properties.setdefault("bungie_lighting_attenuation_enabled", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_attenuation_enabled"], np.uint8))).update(bm, face_prop.layer_name, 1)
            face_properties.setdefault("bungie_lighting_attenuation_cutoff", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_attenuation_cutoff"], np.single))).update(bm, face_prop.layer_name, face_prop.material_lighting_attenuation_cutoff)
            face_properties.setdefault("bungie_lighting_attenuation_falloff", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_attenuation_falloff"], np.single))).update(bm, face_prop.layer_name, face_prop.material_lighting_attenuation_falloff)
            face_properties.setdefault("bungie_lighting_emissive_focus", FaceSet(np.full(num_faces, fp_defaults["bungie_lighting_emissive_focus"], np.single))).update(bm, face_prop.layer_name, degrees(face_prop.material_lighting_emissive_focus) / 180)
            
    for material, material_indexes in special_mats_dict.items():
        if material.name.lower().startswith('+seamsealer'):
            face_properties.setdefault("bungie_face_type", FaceSet(np.zeros(num_faces, np.uint8))).update_from_material(bm, material_indexes, FaceType.seam_sealer.value)
        elif material.name.lower().startswith('+sky'):
            face_properties.setdefault("bungie_face_type", FaceSet(np.zeros(num_faces, np.uint8))).update_from_material(bm, material_indexes, FaceType.sky.value)
            if len(material.name) > 4 and material.name[4].isdigit():
                sky_index = int(material.name[4])
                if sky_index > 0:
                    face_properties.setdefault("bungie_sky_permutation_index", FaceSet(np.zeros(num_faces, np.uint8))).update_from_material(bm, material_indexes, sky_index)
        else:
            # Must be a material with material properties
            pass
        
    for idx, face in enumerate(bm.faces):
        for v in face_properties.values():
            for key, value in v.face_props.items():
                if isinstance(key, int):
                    if face.material_index == key:
                        v.array[idx] = value
                else:
                    if face[key]:
                        if isinstance(value, int) and value < 0: # for handling face_sides
                            value = abs(value)
                            for l, va in side_layers.items():
                                if l != key and abs(va) != value and face[l]:
                                    value += abs(va)
                                    break
                                    
                        v.array[idx] = value
                    
    bm.free()
    if sorted_order is not None:
        for v in face_properties.values():
            v.array = v.array[sorted_order]
    
    return face_properties
    
def calc_transforms(matrix: Matrix) -> tuple[Array, Array, Array]:
    '''Gets the affine3, linear3x3, and inverse_linear3x3 from a matrix'''
    matrix3x3 = matrix.to_3x3()
    affine3 = (c_float * 3)(*matrix.translation.to_tuple())
    linear3x3 = (c_float * 9)(*[f for row in matrix3x3 for f in row])
    
    determinant3x3 = matrix3x3.determinant()
    if determinant3x3 != 0.0:
        adjugate3x3 = matrix3x3.adjugated()
        inverse = [[adjugate3x3[row][col] / determinant3x3 for col in range(3)] for row in range(3)]
    else:
        inverse = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        
    inverse_linear3x3 = (c_float * 9)(
        inverse[0][0], inverse[0][1], inverse[0][2],
        inverse[1][0], inverse[1][1], inverse[1][2],
        inverse[2][0], inverse[2][1], inverse[2][2]
    )
    
    return affine3, linear3x3, inverse_linear3x3

def is_rendered(props: dict) -> bool:
    mesh_type = props.get("bungie_mesh_type", None)
    if mesh_type is None:
        # returning true since the absence of a mesh type means the game will use the default mesh type - _connected_geometry_mesh_type_default
        return True 
    
    return mesh_type in RENDER_MESH_TYPES