from ctypes import CDLL, c_uint32, cast, cdll, create_string_buffer, pointer
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix

from .export_classes import *
from .formats import *

dll = None
    
vertex_names = (
    b"Position",
    b"BoneWeights",
    b"BoneIndices",
    b"Normal",
    b"TextureCoordinates0",
    b"TextureCoordinates1",
    b"TextureCoordinates2",
    b"TextureCoordinates3",
    b"lighting",
    b"colorSet1",
    b"colorSet2",
    b"blend_shape",
    b"vertex_id"
)

vertex_type_info = [
    GrannyDataTypeDefinition(10, b"Position", None, 3),
    GrannyDataTypeDefinition(14, b"BoneWeights", None, 4),
    GrannyDataTypeDefinition(12, b"BoneIndices", None, 4),
    GrannyDataTypeDefinition(10, b"Normal", None, 3),
    GrannyDataTypeDefinition(10, b"TextureCoordinates0", None, 3),
    GrannyDataTypeDefinition(10, b"TextureCoordinates1", None, 3),
    GrannyDataTypeDefinition(10, b"TextureCoordinates2", None, 3),
    GrannyDataTypeDefinition(10, b"TextureCoordinates3", None, 3),
    GrannyDataTypeDefinition(10, b"lighting", None, 3),
    GrannyDataTypeDefinition(10, b"colorSet1", None, 3),
    GrannyDataTypeDefinition(10, b"colorSet2", None, 3),
    GrannyDataTypeDefinition(10, b"blend_shape", None, 3),
    GrannyDataTypeDefinition(10, b"vertex_id", None, 2),
    GrannyDataTypeDefinition(0, None, None, 0)  # End marker
]

def granny_get_log_message_type_string(message_type: c_int) -> c_char_p:
    """Granny logging function"""
    dll.GrannyGetLogMessageTypeString.argtypes=[c_int]
    dll.GrannyGetLogMessageTypeString.restype=c_char_p
    result = dll.GrannyGetLogMessageTypeString(message_type)
    return result

def granny_get_log_message_origin_string(origin: c_int) -> c_char_p:
    """Granny logging function"""
    dll.GrannyGetLogMessageOriginString.argtypes=[c_int]
    dll.GrannyGetLogMessageOriginString.restype=c_char_p
    result = dll.GrannyGetLogMessageOriginString(origin)
    return result
    
def output_error(format_string, *args):
    print(format_string % args)
    
def new_callback_function(Type, Origin, SourceFile, SourceLine, Message, UserData):
    output_error(
        "Error(Granny): type %s from subsystem %s: %s" %
        (granny_get_log_message_type_string(Type),
        granny_get_log_message_origin_string(Origin),
        Message)
    )
    
class MaterialExtendedData(Structure):
    """ Halo material type, ditto """
    _pack_ = 1
    _fields_ = [('bungie_shader_path', c_char_p),
                ('bungie_shader_type',c_char_p),]
    
GrannyCallbackType = CFUNCTYPE(
    None,
    c_int,
    c_int,
    c_char_p,
    c_int,
    c_char_p,
    c_void_p
)

class Granny:
    dll: CDLL
    export_materials: list[Material]
    export_skeletons: list[Skeleton]
    export_vertex_datas: list[VertexData]
    export_tri_topologies: list[TriTopology]
    export_meshes: list[Mesh]
    export_models: list[Model]
    export_track_groups: list[TrackGroup]
    export_animations: list[Animation]
    
    def __init__(self, granny_dll_path: str | Path, filepath: Path):
        self.dll = cdll.LoadLibrary(str(granny_dll_path))
        global dll
        dll = self.dll
        self.file_info_type = POINTER(GrannyDataTypeDefinition).in_dll(self.dll, "GrannyFileInfoType")
        self.magic_value = POINTER(GrannyFileMagic).in_dll(self.dll, "GrannyGRNFileMV_ThisPlatform")
        self.old_callback = GrannyLogCallback()
        self.filename = str(filepath)
        self.granny_export_info = None
        self._create_callback()
        self._create_file_info()
        
    def from_objects(self, objects: list[bpy.types.Object]):
        """Creates granny representations of blender objects"""
        materials = set()
        skeletons = set()
        mesh_data = set()
        meshes = set()
        mesh_objects_set = set()
        for ob in objects:
            if not ob.parent:
                skeletons.add(ob)
            if ob.type != 'MESH': continue
            mesh_data.add(ob.data)
            mesh_objects_set.add(ob)
            for mat in ob.data.materials:
                materials.add(mat)
                
        for data in mesh_data:
            meshes.add(data)
            
        meshes = list(meshes)
        mesh_enum = Enum("mesh_enum", [m.name for m in meshes], start=0)
        mesh_objects = list(mesh_objects_set)
        ob_enum = Enum("ob_enum", [m.name for m in mesh_objects], start=0)
        
        self.export_materials = [Material(i) for i in materials]
        material_enum = Enum("material_enum", [m.name_str for m in self.export_materials], start=0)
        
        mesh_dict = {} # Meshes are keys, bmeshes are values
        
        for mesh in meshes:
            do_split = False
            split_by_edge = False
            match mesh.normals_domain:
                case 'POINT':
                    normal_source = mesh.vertex_normals
                case 'FACE':
                    normal_source = mesh.corner_normals
                    do_split = True
                case 'CORNER':
                    normal_source = mesh.corner_normals
                    do_split = True
                    split_by_edge = True
            

            # Split up meshes for their normals
            bm = bmesh.new()
            bm.from_mesh(mesh)
            utils.save_loop_normals(bm, mesh)
            if do_split:
                if split_by_edge:
                    # edges_to_split = set()
                    # for face in bm.faces:
                    #     if not face.smooth:
                    #         edges_to_split.update(face.edges)
                            
                    # for edge in bm.edges:
                    #     if edge.smooth == False:
                    #         edges_to_split.add(edge)
                    
                    # bmesh.ops.split_edges(bm, edges=list(edges_to_split))
                    bmesh.ops.split_edges(bm, edges=[edge for edge in bm.edges if not edge.smooth])
                else:
                    bmesh.ops.split_edges(bm, edges=bm.edges)
            
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            utils.apply_loop_normals(mesh)
            mesh_dict[mesh] = bm
        
        self.export_skeletons = [Skeleton(i) for i in skeletons]
        self.export_vertex_datas = [VertexData(i) for i, j in mesh_dict.items()]
        self.export_tri_topologies = [TriTopology(i) for i, j in mesh_dict.items()]
        self.export_meshes = [Mesh(i, mesh_enum[i.data.name].value, material_enum) for i in mesh_objects]
        self.export_models = [Model(i, idx, ob_enum, mesh_objects_set) for idx, i in enumerate(skeletons)]
        
    def save(self):
        data_tree_writer = self._begin_file_data_tree_writing()
        if data_tree_writer:
            if self._write_data_tree_to_file(data_tree_writer):
                self._end_file_data_tree_writing(data_tree_writer)
                
    def create_materials(self):
        num_materials = len(self.export_materials)
        granny_materials = (POINTER(GrannyMaterial) * num_materials)()

        for i, export_material in enumerate(self.export_materials):
            granny_material = GrannyMaterial()
            granny_materials[i] = pointer(granny_material)
            export_material.granny = granny_materials[i]
            self._populate_material(granny_material, export_material)

        self.file_info.material_count = num_materials
        self.file_info.materials = granny_materials

    def _populate_material(self, granny_material, export_material):
        granny_material.name = export_material.name
        export_material.create_properties(granny_material)

        
    def create_skeletons(self, export_info):
        num_skeletons = len(self.export_skeletons) + int(bool(export_info))
        skeletons = (POINTER(GrannySkeleton) * num_skeletons)()

        for i, export_skeleton in enumerate(self.export_skeletons):
            granny_skeleton = GrannySkeleton()
            skeletons[i] = pointer(granny_skeleton)
            export_skeleton.granny = skeletons[i]
            self._populate_skeleton(granny_skeleton, export_skeleton)

        if export_info:
            granny_skeleton = GrannySkeleton()
            skeletons[-1] = pointer(granny_skeleton)
            self.granny_export_info = skeletons[-1]
            self._populate_export_info_skeleton(granny_skeleton, export_info)

        self.file_info.skeleton_count = num_skeletons
        self.file_info.skeletons = skeletons

    def _populate_skeleton(self, granny_skeleton, export_skeleton):
        granny_skeleton.name = export_skeleton.name
        granny_skeleton.lod_type = export_skeleton.lod

        num_bones = len(export_skeleton.bones)
        bones = (GrannyBone * num_bones)()

        for j, export_bone in enumerate(export_skeleton.bones):
            granny_bone = bones[j]
            granny_bone.name = export_bone.name
            granny_bone.parent_index = export_bone.parent_index
            if export_bone.local_transform:
                granny_bone.local_transform = export_bone.local_transform
                granny_bone.inverse_world_4x4 = export_bone.inverse_transform

            export_bone.create_properties(granny_bone)

        granny_skeleton.bone_count = num_bones
        granny_skeleton.bones = cast(bones, POINTER(GrannyBone))

    def _populate_export_info_skeleton(self, granny_skeleton, export_info):
        granny_skeleton.name = b"BungieExportInfo"
        
        bones = (GrannyBone * 1)()
        granny_bone = bones[0]
        granny_bone.name = b"BungieExportInfo"
        granny_bone.parent_index = -1
        
        props = Properties()
        props.properties = export_info
        props.create_properties(granny_bone)
        
        granny_skeleton.bone_count = 1
        granny_skeleton.bones = cast(bones, POINTER(GrannyBone))
        
    def create_vertex_data(self):
        num_vertex_datas = len(self.export_vertex_datas)
        vertex_datas = (POINTER(GrannyVertexData) * num_vertex_datas)()

        for i, export_vertex_data in enumerate(self.export_vertex_datas):
            granny_vertex_data = GrannyVertexData()
            self._populate_vertex_data(granny_vertex_data, export_vertex_data)
            vertex_datas[i] = pointer(granny_vertex_data)
            export_vertex_data.granny = vertex_datas[i]

        self.file_info.vertex_data_count = num_vertex_datas
        self.file_info.vertex_datas = vertex_datas

    def _populate_vertex_data(self, granny_vertex_data, export_vertex_data):
        names_array = (c_char_p * len(vertex_names))(*vertex_names)
        granny_vertex_data.vertex_component_names = cast(names_array, POINTER(c_char_p))
        granny_vertex_data.vertex_component_name_count = len(vertex_names)

        vertex_type_info_array = (GrannyDataTypeDefinition * len(vertex_type_info))(*vertex_type_info)
        granny_vertex_data.vertex_type = cast(vertex_type_info_array, POINTER(GrannyDataTypeDefinition))

        vertex_byte_array = self._convert_vertices_to_bytearray(export_vertex_data.vertices)

        vertex_array = (c_ubyte * len(vertex_byte_array))(*vertex_byte_array)
        granny_vertex_data.vertices = cast(vertex_array, POINTER(c_ubyte))
        granny_vertex_data.vertex_count = len(export_vertex_data.vertices)

    def _convert_vertices_to_bytearray(self, vertices):
        vertex_byte_array = bytearray()

        for export_vertex in vertices:
            vertex_byte_array.extend(export_vertex.position)
            vertex_byte_array.extend(export_vertex.bone_weights)
            vertex_byte_array.extend(export_vertex.bone_indices)
            vertex_byte_array.extend(export_vertex.normal)
            vertex_byte_array.extend(export_vertex.uvs0)
            vertex_byte_array.extend(export_vertex.uvs1)
            vertex_byte_array.extend(export_vertex.uvs2)
            vertex_byte_array.extend(export_vertex.uvs3)
            vertex_byte_array.extend(export_vertex.lighting_uv)
            vertex_byte_array.extend(export_vertex.vertex_color0)
            vertex_byte_array.extend(export_vertex.vertex_color1)
            vertex_byte_array.extend(export_vertex.blend_shape)
            vertex_byte_array.extend(export_vertex.vertex_id)

        return vertex_byte_array
    
    def create_tri_topologies(self):
        num_tri_topologies = len(self.export_tri_topologies)
        tri_topologies = (POINTER(GrannyTriTopology) * num_tri_topologies)()

        for i, export_tri_topology in enumerate(self.export_tri_topologies):
            granny_tri_topology = GrannyTriTopology()
            self._populate_tri_topology(granny_tri_topology, export_tri_topology)
            tri_topologies[i] = pointer(granny_tri_topology)
            export_tri_topology.granny = tri_topologies[i]

        self.file_info.tri_topology_count = num_tri_topologies
        self.file_info.tri_topologies = tri_topologies

    def _populate_tri_topology(self, granny_tri_topology, export_tri_topology):
        # Populate Groups
        num_groups = len(export_tri_topology.groups)
        groups = (GrannyTriMaterialGroup * num_groups)()

        for j, export_group in enumerate(export_tri_topology.groups):
            granny_group = groups[j]
            granny_group.material_index = export_group.material_index
            granny_group.tri_first = export_group.tri_start
            granny_group.tri_count = export_group.tri_count

        granny_tri_topology.group_count = num_groups
        granny_tri_topology.groups = cast(groups, POINTER(GrannyTriMaterialGroup))
        
        # Populate Indices
        indices = []
        for tri in export_tri_topology.triangles:
            for i in tri.indices:
                indices.append(i)
                
        indices_array = (c_int * len(indices))(*indices)
        
        granny_tri_topology.index_count = len(indices)
        granny_tri_topology.indices = cast(indices_array, POINTER(c_int))
        
    def create_meshes(self):
        num_meshes = len(self.export_meshes)
        meshes = (POINTER(GrannyMesh) * num_meshes)()

        for i, export_mesh in enumerate(self.export_meshes):
            granny_mesh = GrannyMesh()
            meshes[i] = pointer(granny_mesh)
            export_mesh.granny = meshes[i]
            self._populate_mesh(granny_mesh, export_mesh)

        self.file_info.mesh_count = num_meshes
        self.file_info.meshes = meshes

    def _populate_mesh(self, granny_mesh, export_mesh: Mesh):
        granny_mesh.name = export_mesh.name
        export_mesh.create_properties(granny_mesh)
        granny_mesh.primary_vertex_data = self.export_vertex_datas[export_mesh.primary_vertex_data_index].granny
        granny_mesh.primary_topology = self.export_tri_topologies[export_mesh.primary_topology_index].granny
        
        num_material_bindings = len(export_mesh.material_bindings)
        material_bindings = (GrannyMaterialBinding * num_material_bindings)()

        for j, export_material_binding in enumerate(export_mesh.material_bindings):
            granny_material_binding = material_bindings[j]
            granny_material_binding.material = self.export_materials[export_material_binding].granny

        granny_mesh.material_binding_count = num_material_bindings
        granny_mesh.material_bindings = cast(material_bindings, POINTER(GrannyMaterialBinding))
        
        num_bone_bindings = len(export_mesh.bone_bindings)
        bone_bindings = (GrannyBoneBinding * num_bone_bindings)()

        for k, export_bone_binding in enumerate(export_mesh.bone_bindings):
            granny_bone_binding = bone_bindings[k]
            granny_bone_binding.bone_name = export_bone_binding.name
            granny_bone_binding.obb_min = (c_float * 3)(-2, -2, -2)
            granny_bone_binding.obb_max = (c_float * 3)(2, 2, 2)

        granny_mesh.bone_bindings_count = num_bone_bindings
        granny_mesh.bone_bindings = cast(bone_bindings, POINTER(GrannyBoneBinding))
        
    def create_models(self):
        num_models = len(self.export_models) + int(bool(self.granny_export_info))
        models = (POINTER(GrannyModel) * num_models)()

        for i, export_model in enumerate(self.export_models):
            granny_model = GrannyModel()
            models[i] = pointer(granny_model)
            self._populate_model(granny_model, export_model)
            
        if self.granny_export_info:
            granny_model = GrannyModel()
            models[-1] = pointer(granny_model)
            granny_model.name = b"BungieExportInfo"
            granny_model.skeleton = self.granny_export_info

        self.file_info.model_count = num_models
        self.file_info.models = models

    def _populate_model(self, granny_model, export_model: Model):
        granny_model.name = export_model.name
        granny_model.skeleton = self.export_skeletons[export_model.skeleton_index].granny
        granny_model.initial_placement = export_model.initial_placement
        
        num_mesh_bindings = len(export_model.mesh_bindings)
        mesh_bindings = (GrannyModelMeshBinding * num_mesh_bindings)()

        for j, export_mesh_binding in enumerate(export_model.mesh_bindings):
            granny_mesh_binding = mesh_bindings[j]
            granny_mesh_binding.mesh = self.export_meshes[export_mesh_binding].granny

        granny_model.mesh_binding_count = num_mesh_bindings
        granny_model.mesh_bindings = cast(mesh_bindings, POINTER(GrannyModelMeshBinding))

    def get_version_string(self) -> str:
        """Returns the granny dll version as a string"""
        self.dll.GrannyGetVersionString.restype=c_char_p
        return self.dll.GrannyGetVersionString().decode('UTF-8')
    
    def get_version(self, major_version: c_int32, minor_version: c_int32, build_number: c_int32, customization: c_int32):
        """Returns the granny dll version as pointers"""
        self.dll.GrannyGetVersion.argtypes=[POINTER(c_int32),POINTER(c_int32),POINTER(c_int32),POINTER(c_int32)]
        return self.dll.GrannyGetVersion()
    
    def _begin_file_data_tree_writing(self):
        self.dll.GrannyBeginFileDataTreeWriting.argtypes=[POINTER(GrannyDataTypeDefinition), c_void_p, c_int32, c_int32]
        self.dll.GrannyBeginFileDataTreeWriting.restype=c_void_p
        result = self.dll.GrannyBeginFileDataTreeWriting(self.file_info_type, pointer(self.file_info), 0, 0)
        return result
    
    def _write_data_tree_to_file(self, writer):
        file_name_bytes = self.filename.encode()
        self.dll.GrannyWriteDataTreeToFile.argtypes=[c_void_p, c_uint32, POINTER(GrannyFileMagic), c_char_p, c_int32]
        self.dll.GrannyWriteDataTreeToFile.restype=c_bool
        result = self.dll.GrannyWriteDataTreeToFile(writer, 0x80000037, self.magic_value, file_name_bytes, 1)
        return result
    
    def _end_file_data_tree_writing(self, writer):
        self.dll.GrannyEndFileDataTreeWriting.argtypes=[c_void_p]
        self.dll.GrannyEndFileDataTreeWriting(writer)
        
    def _create_callback(self):
        new_callback = self.old_callback
        new_callback.function = GrannyCallbackType(new_callback_function)
        new_callback.user_data = None
        self._set_log_callback(new_callback)
        
    def _create_file_info(self):
        self.file_info = GrannyFileInfo()
        self.file_info.art_tool_info = pointer(self._create_art_tool_info())
        self.file_info.exporter_info = pointer(self._create_basic_exporter_tool_info())
        self.file_info.file_name = bpy.data.filepath.encode() if bpy.data.filepath else self.filename.encode()
        self.file_info.texture_count = 0
        self.file_info.textures = None
        self.file_info.material_count = 0
        self.file_info.materials = None
        self.file_info.skeleton_count = 0
        self.file_info.skeletons = None
        self.file_info.vertex_data_count = 0
        self.file_info.vertex_datas = None
        self.file_info.tri_topology_count = 0
        self.file_info.tri_topologies = None
        self.file_info.mesh_count = 0
        self.file_info.meshes = None
        self.file_info.model_count = 0
        self.file_info.models = None
        self.file_info.track_group_count = 0
        self.file_info.track_groups = None
        self.file_info.animation_count = 0
        self.file_info.animations = None
        self.file_info.extended_data.type = None
        self.file_info.extended_data.object = None
        
    def _create_art_tool_info(self) -> GrannyFileArtToolInfo:
        tool_info = GrannyFileArtToolInfo()
        tool_info.art_tool_name = b'Blender'
        tool_info.art_tool_major_revision = 1
        tool_info.art_tool_minor_revision = 0
        tool_info.art_tool_pointer_size = 64
        tool_info.units_per_meter = 39.370079
        tool_info.origin[:] = [0, 0, 0]
        tool_info.right_vector[:] = [0, -1, 0]
        tool_info.up_vector[:] = [0, 0, 1]
        tool_info.back_vector[:] = [-1, 0, 0]
        tool_info.extended_data.type = None
        tool_info.extended_data.object = None
        return tool_info
    
    def _create_basic_exporter_tool_info(self) -> GrannyFileExporterInfo:
        exporter_info = GrannyFileExporterInfo()
        exporter_info.exporter_name = b'Foundry'
        exporter_info.exporter_major_revision = 2
        exporter_info.exporter_minor_revision = 8
        exporter_info.exporter_build_number = 36
        exporter_info.extended_data.type = None
        exporter_info.extended_data.object = None
        return exporter_info
    
    def _set_log_file_name(self, file_name : str, clear : c_bool) -> c_bool:
        """Sets a file for the granny dll to log to.
        granny_set_log_file_name("c:/blargh.txt", true);
        to turn off: granny_set_log_file_name(0, false);
        """
        file_name_bytes = file_name.encode()
        self.dll.GrannySetLogFileName.argtypes=[c_char_p, c_bool]
        self.dll.GrannySetLogFileName.restype=c_bool
        result = self.dll.GrannySetLogFileName(file_name_bytes, clear)
        return result
    
    def _get_log_callback(self, result : GrannyLogCallback):
        """Granny logging function"""
        self.dll.GrannyGetLogCallback.argtypes=[POINTER(GrannyLogCallback)]
        self.dll.GrannyGetLogCallback(result)
        
    def _set_log_callback(self, result : GrannyLogCallback):
        """Granny logging function"""
        self.dll.GrannySetLogCallback.argtypes=[POINTER(GrannyLogCallback)]
        self.dll.GrannySetLogCallback(result)
        
    def _get_log_message_type_string(self, message_type: c_int) -> c_char_p:
        """Granny logging function"""
        self.dll.GrannyGetLogMessageTypeString.argtypes=[c_int]
        self.dll.GrannyGetLogMessageTypeString.restype=c_char_p
        result = self.dll.GrannyGetLogMessageTypeString(message_type)
        return result

    def _get_log_message_origin_string(self, origin: c_int) -> c_char_p:
        """Granny logging function"""
        self.dll.GrannyGetLogMessageOriginString.argtypes=[c_int]
        self.dll.GrannyGetLogMessageOriginString.restype=c_char_p
        result = self.dll.GrannyGetLogMessageOriginString(origin)
        return result
    
    def _get_log_message_type_string(self, message_type: c_int) -> c_char_p:
        """Granny logging function"""
        self.dll.GrannyGetLogMessageTypeString.argtypes=[c_int]
        self.dll.GrannyGetLogMessageTypeString.restype=c_char_p
        result = self.dll.GrannyGetLogMessageTypeString(message_type)
        return result

    def _get_log_message_origin_string(self, origin: c_int) -> c_char_p:
        """Granny logging function"""
        self.dll.GrannyGetLogMessageOriginString.argtypes=[c_int]
        self.dll.GrannyGetLogMessageOriginString.restype=c_char_p
        result = self.dll.GrannyGetLogMessageOriginString(origin)
        return result