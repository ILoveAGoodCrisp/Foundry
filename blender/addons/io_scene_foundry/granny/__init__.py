from collections import defaultdict
from ctypes import CDLL, byref, c_uint32, cast, cdll, create_string_buffer, pointer, sizeof, string_at
from pathlib import Path
import struct
import time

import bpy

from .export_classes import *
from .formats import *
    
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
    def __init__(self, granny_dll_path: str | Path):
        self.dll = cdll.LoadLibrary(str(granny_dll_path))
        self._define_granny_functions()
        self.file_info_type = POINTER(GrannyDataTypeDefinition).in_dll(self.dll, "GrannyFileInfoType")
        self.magic_value = POINTER(GrannyFileMagic).in_dll(self.dll, "GrannyGRNFileMV_ThisPlatform")
        self._create_callback()
        self.filename = ""
        
    def new(self, filepath: Path, forward: str, scale: float, mirror: bool):
        self.filename = str(filepath)
        # File Transforms
        self.units_per_meter = (1  / 0.03048) * scale
        self.origin = (c_float * 3)(0, 0, 0)
        self.up_vector = (c_float * 3)(0, 0, 1)
        match forward:
            case 'y-':
                self.back_vector = (c_float * 3)(0, 1, 0)
                self.right_vector = (c_float * 3)(1 if mirror else -1, 0, 0)
            case 'y':
                self.back_vector = (c_float * 3)(0, -1, 0)
                self.right_vector = (c_float * 3)(-1 if mirror else 1, 0, 0)
            case 'x-':
                self.back_vector = (c_float * 3)(1, 0, 0)
                self.right_vector = (c_float * 3)(0, -1 if mirror else 1, 0)
            case 'x':
                self.back_vector = (c_float * 3)(-1, 0, 0)
                self.right_vector = (c_float * 3)(0, 1 if mirror else -1, 0)
            case _:
                raise(f"Invalid forward provided: {forward}")
        
        # File Info
        self.granny_export_info = None
        self._create_file_info()
        
        
    def from_tree(self, scene, nodes):
        self.export_materials = []
        self.export_textures = []
        self.export_meshes = []
        self.export_models = []
        self.export_skeletons = []
        self.export_tri_topologies = []
        self.export_vertex_datas = []
        meshes = set()
        materials = set()
        for model in sorted(scene.models.values(), key=lambda model: model.name):
            node = nodes.get(model.name)
            if not node: continue
            self.export_skeletons.append(Skeleton(model.skeleton, node, nodes))
            mesh_binding_indexes = []
            for bone in sorted(model.skeleton.bones, key=lambda bone: bone.name):
                if bone.node and nodes.get(bone.name) and bone.node.mesh:
                    self.export_vertex_datas.append(bone.node.granny_vertex_data)
                    # self.export_tri_topologies.append(bone.node.granny_tri_topology)
                    self.export_meshes.append(Mesh(bone.node))
                    materials.update(bone.node.mesh.materials)
                    meshes.add(bone.node.mesh)
                    mesh_binding_indexes.append(len(self.export_meshes) - 1)
                    
            self.export_models.append(Model(model, len(self.export_skeletons) - 1, mesh_binding_indexes))
            
        if meshes:
            self.export_tri_topologies = [mesh.granny_tri_topology for mesh in meshes]
            self.export_materials = [mat.granny_material for mat in sorted(materials, key=lambda mat: mat.name)]
            if scene.uses_textures:
                self.export_textures = [mat.granny_texture for mat in sorted(materials, key=lambda mat: mat.name) if mat.granny_texture is not None]
        
    def save(self):
        data_tree_writer = self._begin_file_data_tree_writing()
        if data_tree_writer:
            if self._write_data_tree_to_file(data_tree_writer):
                self._end_file_data_tree_writing(data_tree_writer)
                
    def transform(self):
        '''Transforms the granny file to Halo (Big scale + X forward)'''
        halo_units_per_meter = 1 / 0.03048
        halo_origin = (c_float * 3)(0, 0, 0)
        halo_right_vector = (c_float * 3)(0, -1, 0)
        halo_up_vector = (c_float * 3)(0, 0, 1)
        halo_back_vector = (c_float * 3)(-1, 0, 0)
        affine3 = (c_float * 3)(0, 0, 0)
        linear3x3 = (c_float * 9)(0, 0, 0, 0, 0, 0, 0, 0, 0)
        inverse_linear3x3 = (c_float * 9)(0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        self._compute_basis_conversion(self.file_info, 
                                      halo_units_per_meter,
                                      halo_origin,
                                      halo_right_vector,
                                      halo_up_vector,
                                      halo_back_vector,
                                      affine3,
                                      linear3x3,
                                      inverse_linear3x3,
                                      )
        
        self._transform_file(
            self.file_info,
            affine3,
            linear3x3,
            inverse_linear3x3,
            1e-5,
            1e-5,
            3, # 3 represents the flags GrannyRenormalizeNormals & GrannyReorderTriangleIndices
        )
                
    def create_materials(self):
        num_materials = len(self.export_materials)
        materials = (POINTER(GrannyMaterial) * num_materials)(*self.export_materials)
        self.file_info.material_count = num_materials
        self.file_info.materials = materials
        
    def create_textures(self):
        num_textures = len(self.export_textures)
        textures = (POINTER(GrannyTexture) * num_textures)(*self.export_textures)
        self.file_info.texture_count = num_textures
        self.file_info.textures = textures

    def create_skeletons(self, export_info=None):
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
        bones = (GrannyBone * num_bones)(*export_skeleton.bones)
        granny_skeleton.bone_count = num_bones
        granny_skeleton.bones = cast(bones, POINTER(GrannyBone))

    def _populate_export_info_skeleton(self, granny_skeleton, export_info):
        granny_skeleton.name = b"BungieExportInfo"
        
        bones = (GrannyBone * 1)()
        granny_bone = bones[0]
        granny_bone.name = b"BungieExportInfo"
        granny_bone.parent_index = -1
        granny_bone.local_transform = granny_transform_default
        granny_bone.inverse_world_4x4 = granny_inverse_transform_default
        
        props = Properties()
        props.properties = export_info
        props.create_properties(granny_bone)
        
        granny_skeleton.bone_count = 1
        granny_skeleton.bones = cast(bones, POINTER(GrannyBone))
        
    def create_vertex_data(self):
        num_vertex_datas = len(self.export_vertex_datas)
        vertex_datas = (POINTER(GrannyVertexData) * num_vertex_datas)(*self.export_vertex_datas)
        self.file_info.vertex_data_count = num_vertex_datas
        self.file_info.vertex_datas = vertex_datas
    
    def create_tri_topologies(self):
        num_tri_topologies = len(self.export_tri_topologies)
        tri_topologies = (POINTER(GrannyTriTopology) * num_tri_topologies)(*self.export_tri_topologies)
        self.file_info.tri_topology_count = num_tri_topologies
        self.file_info.tri_topologies = tri_topologies
        
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
        granny_mesh.primary_vertex_data = export_mesh.primary_vertex_data
        granny_mesh.primary_topology = export_mesh.primary_topology
        
        num_material_bindings = len(export_mesh.materials)
        material_bindings = (GrannyMaterialBinding * num_material_bindings)()

        for j, export_material in enumerate(export_mesh.materials):
            granny_material_binding = material_bindings[j]
            granny_material_binding.material = export_material
            
        granny_mesh.material_binding_count = num_material_bindings
        granny_mesh.material_bindings = cast(material_bindings, POINTER(GrannyMaterialBinding))
        
        if export_mesh.bone_bindings:
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
            granny_model.initial_placement = granny_transform_default

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
        
    def _create_callback(self):
        callback = GrannyLogCallback()
        callback.function = GrannyCallbackType(self._new_callback_function)
        self._set_log_callback(callback)
        
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
        blender_version = bpy.app.version
        tool_info = GrannyFileArtToolInfo()
        tool_info.art_tool_name = b'Blender'
        tool_info.art_tool_major_revision = blender_version[0]
        tool_info.art_tool_minor_revision = blender_version[1]
        tool_info.art_tool_pointer_size = 64
        tool_info.units_per_meter = self.units_per_meter
        tool_info.origin[:] = self.origin
        # tool_info.right_vector[:] = [1, 0, 0]
        # tool_info.up_vector[:] = [0, 0, 1]
        # tool_info.back_vector[:] = [0, -1, 0]
        tool_info.right_vector[:] = self.right_vector
        tool_info.up_vector[:] = self.up_vector
        tool_info.back_vector[:] = self.back_vector
        tool_info.extended_data.type = None
        tool_info.extended_data.object = None
        return tool_info
    
    def _create_basic_exporter_tool_info(self) -> GrannyFileExporterInfo:
        exporter_info = GrannyFileExporterInfo()
        exporter_info.exporter_name = b'Foundry'
        exporter_info.exporter_major_revision = 1
        exporter_info.exporter_minor_revision = 0
        exporter_info.exporter_build_number = 0
        exporter_info.extended_data.type = None
        exporter_info.extended_data.object = None
        return exporter_info
    
    def _new_callback_function(self, callback_type, callback_origin, source_file, source_line, message, user_data):
        utils.print_warning(
            f"Granny Traceback\n" 
            f"Type: {self._granny_get_log_message_type_string(callback_type)}\n"
            f"Origin: {self._granny_get_log_message_origin_string(callback_origin)}\n"
            f"File: {source_file}\n"
            f"Line: {source_line}\n"
            f"Message: {message}\n"
            f"User Data: {user_data}"
        )
    
    ### DLL FUNCTIONS
    
    def get_version_string(self) -> str:
        """Returns the granny dll version as a string"""
        return self.dll.GrannyGetVersionString().decode()
    
    def _begin_file_data_tree_writing(self):
        "Starts writing the gr2 data"
        return self.dll.GrannyBeginFileDataTreeWriting(self.file_info_type, pointer(self.file_info), 0, 0)
    
    def _write_data_tree_to_file(self, writer):
        "Write the gr2 to a system file"
        return self.dll.GrannyWriteDataTreeToFile(writer, 0x80000037, self.magic_value, self.filename.encode(), 1)
    
    def _end_file_data_tree_writing(self, writer):
        "Ends gr2 data writing"
        self.dll.GrannyEndFileDataTreeWriting(writer)
    
    def _set_log_file_name(self, file_name: str, clear: c_bool) -> c_bool:
        return self.dll.GrannySetLogFileName(file_name.encode(), clear)
    
    def _get_log_callback(self, callback: GrannyLogCallback):
        self.dll.GrannyGetLogCallback(callback)
        
    def _set_log_callback(self, callback: GrannyLogCallback):
        self.dll.GrannySetLogCallback(callback)
        
    def _get_log_message_type_string(self, message_type: c_int) -> c_char_p:
        return self.dll.GrannyGetLogMessageTypeString(message_type)

    def _get_log_message_origin_string(self, origin: c_int) -> c_char_p:
        return self.dll.GrannyGetLogMessageOriginString(origin)
    
    def _get_log_message_type_string(self, message_type: c_int) -> c_char_p:
        return self.dll.GrannyGetLogMessageTypeString(message_type)

    def _get_log_message_origin_string(self, origin: c_int) -> c_char_p:
        result = self.dll.GrannyGetLogMessageOriginString(origin)
        return result
    
    def _set_transform_with_identity_check(self, result: GrannyTransform, position_3: c_float, orientation4: c_float, scale_shear_3x3: c_float):
        "Sets the value of the given granny_transform and updates its identity flags"
        self.dll.GrannySetTransformWithIdentityCheck(result,position_3,orientation4,scale_shear_3x3)
        
    def _transform_file(self, file_info : GrannyFileInfo, affine_3 : c_float, linear_3x3 : c_float, inverse_linear_3x3 : c_float, affine_tolerance : c_float, linear_tolerance : c_float, flags : c_uint):
        "Transforms the entire file. Flags: 1 = renormalise normals, 2 = reorder triangle indices"
        self.dll.GrannyTransformFile(file_info, affine_3, linear_3x3, inverse_linear_3x3, affine_tolerance, linear_tolerance, flags)
        
    def _compute_basis_conversion(self, file_info : GrannyFileInfo, desired_units_per_meter : c_float, desired_origin_3 : c_float, desired_right_3 : c_float, desired_up_3 : c_float, desired_back_3 : c_float, result_affine_3 : c_float, result_linear_3x3 : c_float, result_inverse_linear_3x3 : c_float) -> c_bool:
        "Computes the given affine, linear and inverse linear values to those required to transform the file from the current coordinates to the given coordinates. The results are written directly to the given affine, linear and inverse linear values"
        return self.dll.GrannyComputeBasisConversion(file_info,desired_units_per_meter,desired_origin_3,desired_right_3,desired_up_3,desired_back_3,result_affine_3,result_linear_3x3,result_inverse_linear_3x3)
    
    def _transform_mesh(self, mesh: GrannyMesh, affine_3 : c_float, linear_3x3 : c_float, inverse_linear_3x3 : c_float, affine_tolerance : c_float, linear_tolerance : c_float, flags : c_uint):
        "Transforms a mesh"
        self.dll.GrannyTransformFile(mesh, affine_3, linear_3x3, inverse_linear_3x3, affine_tolerance, linear_tolerance, flags)
        
    def _transform_vertices(self, vertex_count: c_int, layout: GrannyDataTypeDefinition, vertices, affine_3 : c_float, linear_3x3 : c_float, inverse_linear_3x3 : c_float, renormalise: bool, treat_as_deltas: bool):
        "Transforms vertices. Flags: 1 = renormalise normals, 2 = treat as deltas"
        self.dll.GrannyTransformVertices(vertex_count, layout, vertices, affine_3, linear_3x3, inverse_linear_3x3, renormalise, treat_as_deltas)
        
    def invert_tri_topology_winding(self, tri_topology: GrannyTriTopology):
        "Inverts face winding of the given tri_topology"
        self.dll.GrannyInvertTriTopologyWinding(tri_topology)
        
    def _normalise_vertices(self, vertex_count: c_int, layout: GrannyDataTypeDefinition, vertices):
        self.dll.GrannyNormalizeVertices(vertex_count, layout, vertices)
        
    def _begin_texture_builder(self, width: c_int, height: c_int):
        "Returns a granny texture builder instance"
        return self.dll.GrannyBeginBestMatchS3TCTexture(width, height)
    
    def _encode_image(self, builder: POINTER(GrannyTextureBuilder), width: c_int, height: c_int, stride: c_int, mip_count: c_int, rgba_data: c_void_p):
        "Encodes an image i.e makes it"
        self.dll.GrannyEncodeImage(builder, width, height, stride, mip_count, rgba_data)
    
    def _end_texture(self, builder: POINTER(GrannyTextureBuilder)):
        "returns a granny texture from a builder instance"
        return self.dll.GrannyEndTexture(builder)
    
    def _free_texture(self, texture: c_void_p):
        "Frees the texture from memory"
        self.dll.GrannyFreeBuilderResult(texture)

    def _define_granny_functions(self):
        # Get version
        self.dll.GrannyGetVersionString.restype=c_char_p
        # Begin writing Data Tree
        self.dll.GrannyBeginFileDataTreeWriting.argtypes=[POINTER(GrannyDataTypeDefinition), c_void_p, c_int32, c_int32]
        self.dll.GrannyBeginFileDataTreeWriting.restype=c_void_p
        # Write data tree to file
        self.dll.GrannyWriteDataTreeToFile.argtypes=[c_void_p, c_uint32, POINTER(GrannyFileMagic), c_char_p, c_int32]
        self.dll.GrannyWriteDataTreeToFile.restype=c_bool
        # End data writing
        self.dll.GrannyEndFileDataTreeWriting.argtypes=[c_void_p]
        # Set log filename
        self.dll.GrannySetLogFileName.argtypes=[c_char_p, c_bool]
        self.dll.GrannySetLogFileName.restype=c_bool
        # Get log callback
        self.dll.GrannyGetLogCallback.argtypes=[POINTER(GrannyLogCallback)]
        # Set log callback
        self.dll.GrannySetLogCallback.argtypes=[POINTER(GrannyLogCallback)]
        # Get log message as string
        self.dll.GrannyGetLogMessageTypeString.argtypes=[c_int]
        self.dll.GrannyGetLogMessageTypeString.restype=c_char_p
        # Get log message origin as string
        self.dll.GrannyGetLogMessageOriginString.argtypes=[c_int]
        self.dll.GrannyGetLogMessageOriginString.restype=c_char_p
        # Set transform with identity check
        self.dll.GrannySetTransformWithIdentityCheck.argtypes=[POINTER(GrannyTransform),POINTER(c_float),POINTER(c_float),POINTER(c_float)]
        # Transform file
        self.dll.GrannyTransformFile.argtypes=[POINTER(GrannyFileInfo),POINTER(c_float),POINTER(c_float),POINTER(c_float),c_float,c_float,c_uint]
        # Compute basis conversion
        self.dll.GrannyComputeBasisConversion.argtypes=[POINTER(GrannyFileInfo),c_float,POINTER(c_float),POINTER(c_float),POINTER(c_float),POINTER(c_float),POINTER(c_float),POINTER(c_float),POINTER(c_float)]
        self.dll.GrannyComputeBasisConversion.restype=c_bool
        # Transform mesh
        self.dll.GrannyTransformMesh.argtypes=[POINTER(GrannyMesh), POINTER(c_float), POINTER(c_float), POINTER(c_float), c_float, c_float, c_uint]
        # Transform vertices
        self.dll.GrannyTransformVertices.argtypes=[c_int, POINTER(GrannyDataTypeDefinition), c_void_p, POINTER(c_float), POINTER(c_float), POINTER(c_float), c_bool, c_bool]
        # Invert tri topology winding
        self.dll.GrannyInvertTriTopologyWinding.argtypes=[POINTER(GrannyTriTopology)]
        # Normalise vertices
        self.dll.GrannyNormalizeVertices.argtypes=[c_int, POINTER(GrannyDataTypeDefinition), c_void_p]
        # Begin gexture builder, best matching s3tc texture
        self.dll.GrannyBeginBestMatchS3TCTexture.argtypes=[c_int, c_int]
        self.dll.GrannyBeginBestMatchS3TCTexture.restype=POINTER(GrannyTextureBuilder)
        # Encode an image
        self.dll.GrannyEncodeImage.argtypes=[POINTER(GrannyTextureBuilder), c_int, c_int, c_int, c_int, c_void_p]
        # Get a texture from its builder
        self.dll.GrannyEndTexture.argtypes=[POINTER(GrannyTextureBuilder)]
        self.dll.GrannyEndTexture.restype=POINTER(GrannyTexture)
        # Free texture builder
        self.dll.GrannyFreeBuilderResult.argtypes=[c_void_p]