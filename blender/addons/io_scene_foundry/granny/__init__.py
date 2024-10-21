from collections import defaultdict
from ctypes import CDLL, Array, byref, c_uint32, cast, cdll, create_string_buffer, pointer, sizeof, string_at, windll
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
    def __init__(self, granny_dll_path: str | Path, corinth: bool):
        self.dll = cdll.LoadLibrary(str(granny_dll_path))
        self.file_info = None
        self.corinth = corinth
        self._define_granny_functions()
        self.file_info_type = POINTER(GrannyDataTypeDefinition).in_dll(self.dll, "GrannyFileInfoType")
        self.magic_value = POINTER(GrannyFileMagic).in_dll(self.dll, "GrannyGRNFileMV_ThisPlatform")
        self.keyframe_type = POINTER(GrannyDataTypeDefinition).in_dll(self.dll, "GrannyCurveDataDaKeyframes32fType")
        self.curve_type = POINTER(GrannyDataTypeDefinition).in_dll(self.dll, "GrannyCurveDataDaK32fC32fType")
        self.string_table = self.new_string_table()
        self._create_callback()
        self.filename = ""
    
        
    def new(self, filepath: Path, forward: str, scale: float, mirror: bool):
        self.filename = str(filepath)
        parent_dir = filepath.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
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
            
        self.back_vector = (c_float * 3)(-1, 0, 0)
        self.right_vector = (c_float * 3)(0, 1 if mirror else -1, 0)
        
        # File Info
        self.granny_export_info = None
        self._create_file_info()
        
    def create_extended_data(self, props: dict, entity, sibling_instances=[], name=None):
        granny_props = utils.get_halo_props_for_granny(props)
        if not granny_props: return
        
        builder = self.begin_variant(self.string_table)
        
        for key, value in granny_props.items():
            if isinstance(value, c_int):
                self.add_integer_member(builder, key, value)
            elif isinstance(value, c_float):
                self.add_scalar_member(builder, key, value)
            elif isinstance(value, bytes):
                self.add_string_member(builder, key, value)
            elif isinstance(value, Array):
                first = value[0]
                if isinstance(first, int):
                    self.add_integer_array_member(builder, key, int(sizeof(value) / 4), value)
                elif isinstance(first, float):
                    self.add_scalar_array_member(builder, key, int(sizeof(value) / 4), value)
            else:
                print(value, type(value))
                
        if sibling_instances:
            if self.corinth:
                # Corinth
                info_builder = self.begin_variant(self.string_table)
                self.add_integer_member(info_builder, b"IsInstanced", c_int(1))
                self.add_integer_member(info_builder, b"IndirectlyInstanced", c_int(1))
                
                paths_builder = self.begin_variant(self.string_table)
                for sibling in sibling_instances:
                    self.add_string_member(paths_builder, b"String", sibling)
                    
                paths_type = pointer(GrannyDataTypeDefinition())
                paths_object = c_void_p()
                    
                self.end_variant(paths_builder, byref(paths_type), byref(paths_object))
                
                self.add_dynamic_array_member(info_builder, b"AllPaths", 1, paths_type, paths_object)
                
                info_type = pointer(GrannyDataTypeDefinition())
                info_object = c_void_p()
                self.end_variant(info_builder, byref(info_type), byref(info_object))
                self.add_reference_member(builder, b"InstancingInfo", info_type, info_object)
            else:
                sibling_builder = self.begin_variant(self.string_table)
                # reference_builder = self.begin_variant(self.string_table)
                for sibling in sibling_instances:
                    self.add_string_member(sibling_builder, b"String", sibling)
                    # self.add_integer_member(reference_builder, b"Int32", c_int(0))
                    
                sibling_type = pointer(GrannyDataTypeDefinition())
                sibling_object = c_void_p()
                # reference_type = pointer(GrannyDataTypeDefinition())
                # reference_object = c_void_p()
                    
                self.end_variant(sibling_builder, byref(sibling_type), byref(sibling_object))
                # self.end_variant(reference_builder, byref(reference_type), byref(reference_object))
                # self.add_reference_member(builder, b"SiblingInstances", sibling_type, sibling_object)
                # self.add_reference_member(builder, b"SiblingIsReference", reference_type, reference_object)
                self.add_dynamic_array_member(builder, b"SiblingInstances", 1, sibling_type, sibling_object)
                # self.add_dynamic_array_member(builder, b"SiblingIsReference", 1, reference_type, reference_object)
                
                if name is not None:
                    self.add_string_member(builder, b"FullPath", name)
                # self.add_string_member(builder, b"typeName", b"Node")
        
        data = c_void_p()
        
        self.end_variant(builder, entity.extended_data.type, byref(data))
        
        entity.extended_data.object = data
        
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
        for model in scene.models.values():
            node = nodes.get(model.name)
            if not node: continue
            self.export_skeletons.append(Skeleton(model.skeleton, node, nodes))
            mesh_binding_indices = []
            for bone in model.skeleton.bones:
                if bone.node and nodes.get(bone.name) and bone.node.mesh:
                    self.export_vertex_datas.append(bone.node.granny_vertex_data)
                    # self.export_tri_topologies.append(bone.node.granny_tri_topology)
                    self.export_meshes.append(Mesh(bone.node))
                    materials.update(bone.node.mesh.materials)
                    meshes.add(bone.node.mesh)
                    mesh_binding_indices.append(len(self.export_meshes) - 1)
                    
            self.export_models.append(Model(model, len(self.export_skeletons) - 1, mesh_binding_indices))
            
        if meshes:
            self.export_tri_topologies = [mesh.granny_tri_topology for mesh in meshes]
            self.export_materials = [mat.granny_material for mat in materials]
            if scene.uses_textures:
                self.export_textures = [mat.granny_texture for mat in materials if mat.granny_texture is not None]
        
    def save(self):
        data_tree_writer = self.begin_file_data_tree_writing()
        if data_tree_writer:
            if self.write_data_tree_to_file(data_tree_writer):
                self.end_file_data_tree_writing(data_tree_writer)
                
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
        
        self.compute_basis_conversion(self.file_info, 
                                      halo_units_per_meter,
                                      halo_origin,
                                      halo_right_vector,
                                      halo_up_vector,
                                      halo_back_vector,
                                      affine3,
                                      linear3x3,
                                      inverse_linear3x3,
                                      )
        
        self.transform_file(
            self.file_info,
            affine3,
            linear3x3,
            inverse_linear3x3,
            1e-5,
            1e-5,
            3, # 3 represents the flags GrannyRenormalizeNormals & GrannyReorderTriangleIndices
        )
        
    def write_track_groups(self, export_track_group):
        self.file_info.track_group_count = 1
        self.file_info.track_groups = pointer(export_track_group)
        
    def write_animations(self, export_animation):
        self.file_info.animation_count = 1
        self.file_info.animations = pointer(export_animation)
                
    def write_materials(self):
        num_materials = len(self.export_materials)
        materials = (POINTER(GrannyMaterial) * num_materials)(*self.export_materials)
        self.file_info.material_count = num_materials
        self.file_info.materials = materials
        
    def write_textures(self):
        num_textures = len(self.export_textures)
        textures = (POINTER(GrannyTexture) * num_textures)(*self.export_textures)
        self.file_info.texture_count = num_textures
        self.file_info.textures = textures

    def write_skeletons(self, export_info=None):
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

        self.create_extended_data(export_info, granny_bone)
        
        granny_skeleton.bone_count = 1
        granny_skeleton.bones = cast(bones, POINTER(GrannyBone))
        
    def write_vertex_data(self):
        num_vertex_datas = len(self.export_vertex_datas)
        vertex_datas = (POINTER(GrannyVertexData) * num_vertex_datas)(*self.export_vertex_datas)
        self.file_info.vertex_data_count = num_vertex_datas
        self.file_info.vertex_datas = vertex_datas
    
    def write_tri_topologies(self):
        num_tri_topologies = len(self.export_tri_topologies)
        tri_topologies = (POINTER(GrannyTriTopology) * num_tri_topologies)(*self.export_tri_topologies)
        self.file_info.tri_topology_count = num_tri_topologies
        self.file_info.tri_topologies = tri_topologies
        
    def write_meshes(self):
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
        self.create_extended_data(export_mesh.props, granny_mesh, export_mesh.siblings, export_mesh.name)
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
        
    def write_models(self):
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
        self.set_log_callback(callback)
        
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
        major, minor, build = utils.get_version()
        exporter_info.exporter_name = b'Foundry'
        exporter_info.exporter_major_revision = major
        exporter_info.exporter_minor_revision = minor
        exporter_info.exporter_build_number = build
        exporter_info.extended_data.type = None
        exporter_info.extended_data.object = None
        return exporter_info
    
    def _new_callback_function(self, callback_type, callback_origin, source_file, source_line, message, user_data):
        utils.print_warning(
            f"Granny Traceback\n" 
            f"Type: {self._grannyget_log_message_type_string(callback_type)}\n"
            f"Origin: {self._grannyget_log_message_origin_string(callback_origin)}\n"
            f"File: {source_file}\n"
            f"Line: {source_line}\n"
            f"Message: {message}\n"
            f"User Data: {user_data}"
        )
    
    ### DLL FUNCTIONS
    
    def get_version_string(self) -> str:
        """Returns the granny dll version as a string"""
        return self.dll.GrannyGetVersionString().decode()
    
    def begin_file_data_tree_writing(self):
        "Starts writing the gr2 data"
        return self.dll.GrannyBeginFileDataTreeWriting(self.file_info_type, pointer(self.file_info), 0, 0)
    
    def write_data_tree_to_file(self, writer):
        "Write the gr2 to a system file"
        return self.dll.GrannyWriteDataTreeToFile(writer, 0x80000037, self.magic_value, self.filename.encode(), 1)
    
    def end_file_data_tree_writing(self, writer):
        "Ends gr2 data writing"
        self.dll.GrannyEndFileDataTreeWriting(writer)
    
    def set_log_file_name(self, file_name: str, clear: c_bool) -> c_bool:
        return self.dll.GrannySetLogFileName(file_name.encode(), clear)
    
    def get_log_callback(self, callback: GrannyLogCallback):
        self.dll.GrannyGetLogCallback(callback)
        
    def set_log_callback(self, callback: GrannyLogCallback):
        self.dll.GrannySetLogCallback(callback)
        
    def get_log_message_type_string(self, message_type: c_int) -> c_char_p:
        return self.dll.GrannyGetLogMessageTypeString(message_type)

    def get_log_message_origin_string(self, origin: c_int) -> c_char_p:
        return self.dll.GrannyGetLogMessageOriginString(origin)
    
    def set_transform_with_identity_check(self, result: GrannyTransform, position_3: c_float, orientation4: c_float, scale_shear_3x3: c_float):
        "Sets the value of the given granny_transform and updates its identity flags"
        self.dll.GrannySetTransformWithIdentityCheck(result,position_3,orientation4,scale_shear_3x3)
        
    def transform_file(self, file_info : GrannyFileInfo, affine_3 : c_float, linear_3x3 : c_float, inverse_linear_3x3 : c_float, affine_tolerance : c_float, linear_tolerance : c_float, flags : c_uint):
        "Transforms the entire file. Flags: 1 = renormalise normals, 2 = reorder triangle indices"
        self.dll.GrannyTransformFile(file_info, affine_3, linear_3x3, inverse_linear_3x3, affine_tolerance, linear_tolerance, flags)
        
    def compute_basis_conversion(self, file_info : GrannyFileInfo, desired_units_per_meter : c_float, desired_origin_3 : c_float, desired_right_3 : c_float, desired_up_3 : c_float, desired_back_3 : c_float, result_affine_3 : c_float, result_linear_3x3 : c_float, result_inverse_linear_3x3 : c_float) -> c_bool:
        "Computes the given affine, linear and inverse linear values to those required to transform the file from the current coordinates to the given coordinates. The results are written directly to the given affine, linear and inverse linear values"
        return self.dll.GrannyComputeBasisConversion(file_info,desired_units_per_meter,desired_origin_3,desired_right_3,desired_up_3,desired_back_3,result_affine_3,result_linear_3x3,result_inverse_linear_3x3)
    
    def transform_mesh(self, mesh: GrannyMesh, affine_3 : c_float, linear_3x3 : c_float, inverse_linear_3x3 : c_float, affine_tolerance : c_float, linear_tolerance : c_float, flags : c_uint):
        "Transforms a mesh"
        self.dll.GrannyTransformFile(mesh, affine_3, linear_3x3, inverse_linear_3x3, affine_tolerance, linear_tolerance, flags)
        
    def transform_vertices(self, vertex_count: c_int, layout: GrannyDataTypeDefinition, vertices, affine_3 : c_float, linear_3x3 : c_float, inverse_linear_3x3 : c_float, renormalise: bool, treat_as_deltas: bool):
        "Transforms vertices. Flags: 1 = renormalise normals, 2 = treat as deltas"
        self.dll.GrannyTransformVertices(vertex_count, layout, vertices, affine_3, linear_3x3, inverse_linear_3x3, renormalise, treat_as_deltas)
        
    def invert_tri_topology_winding(self, tri_topology: GrannyTriTopology):
        "Inverts face winding of the given tri_topology"
        self.dll.GrannyInvertTriTopologyWinding(tri_topology)
        
    def normalise_vertices(self, vertex_count: c_int, layout: GrannyDataTypeDefinition, vertices):
        self.dll.GrannyNormalizeVertices(vertex_count, layout, vertices)
        
    def begin_texture_builder(self, width: c_int, height: c_int):
        "Returns a granny texture builder instance"
        return self.dll.GrannyBeginBestMatchS3TCTexture(width, height)
    
    def encode_image(self, builder: POINTER(GrannyTextureBuilder), width: c_int, height: c_int, stride: c_int, mip_count: c_int, rgba_data: c_void_p):
        "Encodes an image i.e makes it"
        self.dll.GrannyEncodeImage(builder, width, height, stride, mip_count, rgba_data)
    
    def end_texture(self, builder: POINTER(GrannyTextureBuilder)):
        "returns a granny texture from a builder instance"
        return self.dll.GrannyEndTexture(builder)
    
    def free_texture(self, texture: c_void_p):
        "Frees the texture from memory"
        self.dll.GrannyFreeBuilderResult(texture)
        
    def begin_track_group(self, name: c_char_p, vector_track_count: c_int, transform_track_count: c_int, text_track_count: c_int, include_lod_error_space: c_bool) -> POINTER(GrannyTrackGroupBuilder):
        return self.dll.GrannyBeginTrackGroup(name, vector_track_count, transform_track_count, text_track_count, include_lod_error_space)
    
    def begin_transform_track(self, builder: POINTER(GrannyTrackGroupBuilder), name: c_char_p, flags: c_int):
        self.dll.GrannyBeginTransformTrack(builder, name, flags)
        
    def initialise_curve_format(self, curve: POINTER(GrannyCurve2)):
        self.dll.GrannyCurveInitializeFormat(curve)
        
    def set_transform_track_position(self, builder: POINTER(GrannyTrackGroupBuilder), source_curve: POINTER(GrannyCurve2)):
        self.dll.GrannySetTransformTrackPositionCurve(builder, source_curve)
        
    def set_transform_track_orientation(self, builder: POINTER(GrannyTrackGroupBuilder), source_curve: POINTER(GrannyCurve2)):
        self.dll.GrannySetTransformTrackOrientationCurve(builder, source_curve)
        
    def set_transform_track_scale(self, builder: POINTER(GrannyTrackGroupBuilder), source_curve: POINTER(GrannyCurve2)):
        self.dll.GrannySetTransformTrackScaleShearCurve(builder, source_curve)
        
    def end_transform_track(self, builder: POINTER(GrannyTrackGroupBuilder)):
        self.dll.GrannyEndTransformTrack(builder)
        
    def end_track_group(self, builder: POINTER(GrannyTrackGroupBuilder)) -> POINTER(GrannyTrackGroup):
        return self.dll.GrannyEndTrackGroup(builder)
    
    def curve_format_is_initialized_correctly(self, curve: POINTER(GrannyCurve2), check_types: c_bool) -> c_bool:
        return self.dll.GrannyCurveFormatIsInitializedCorrectly(curve, check_types)
    
    def begin_sampled_animation(self, transform_curve_count: c_int, sample_count: c_int) -> POINTER(GrannyTrackGroupSampler):
        return self.dll.GrannyBeginSampledAnimation(transform_curve_count, sample_count)
    
    def set_transform_sample(self, sampler: POINTER(GrannyTrackGroupSampler), track_index: c_int, sample_index: c_int, position3: POINTER(c_float), orientation4: POINTER(c_float), scale_shear3x3: POINTER(c_float)):
        self.dll.GrannySetTransformSample(sampler, track_index, sample_index, position3, orientation4, scale_shear3x3)
        
    def fit_bspline_to_samples(self, solver: POINTER(GrannyBSplineSolver), solver_flags: c_uint32, degree: c_int, error_threshold: c_float, c0_threshold: c_float, c1_threshold: c_float, samples: POINTER(c_float), dimension: c_int, sample_count: c_int, dt: c_float, curve_data_type: POINTER(GrannyDataTypeDefinition), maximum_curve_size_in_bytes: c_int, achieved_tolerance: c_bool, curve_size_in_bytes: c_int) -> POINTER(GrannyCurve2):
        return self.dll.GrannyFitBSplineToSamples(solver, solver_flags, degree, error_threshold, c0_threshold, c1_threshold, samples, dimension, sample_count, dt, curve_data_type, maximum_curve_size_in_bytes, achieved_tolerance, curve_size_in_bytes)

    def allocate_bspline_solver(self, max_degree: c_int, max_sample_count: c_int, max_dimension: c_int) -> POINTER(GrannyBSplineSolver):
        return self.dll.GrannyAllocateBSplineSolver(max_degree, max_sample_count, max_dimension)
    
    def get_position_samples(self, sampler: POINTER(GrannyTrackGroupSampler), track_index: c_int) -> POINTER(c_float):
        return self.dll.GrannyGetPositionSamples(sampler, track_index)
    
    def get_orientation_samples(self, sampler: POINTER(GrannyTrackGroupSampler), track_index: c_int) -> POINTER(c_float):
        return self.dll.GrannyGetOrientationSamples(sampler, track_index)
    
    def get_scale_shear_samples(self, sampler: POINTER(GrannyTrackGroupSampler), track_index: c_int) -> POINTER(c_float):
        return self.dll.GrannyGetScaleShearSamples(sampler, track_index)
    
    def compress_curve(self, solver: POINTER(GrannyBSplineSolver), solver_flags: c_uint32, params: POINTER(GrannyCompressCurveParameters), samples: POINTER(c_float), dimension: c_int, frame_count: c_int, dt: c_float, curve_achieved_tolerance: c_bool) -> POINTER(GrannyCurve2):
        return self.dll.GrannyCompressCurve(solver, solver_flags, params, samples, dimension, frame_count, dt, curve_achieved_tolerance)
    
    def begin_curve(self, type_definition: POINTER(GrannyDataTypeDefinition), degree: c_int, dimension: c_int, knot_count: c_int) -> POINTER(GrannyCurveBuilder):
        return self.dll.GrannyBeginCurve(type_definition, degree, dimension, knot_count)
    
    def push_control_array(self, builder: POINTER(GrannyCurveBuilder), control_array: POINTER(c_float)):
        self.dll.GrannyPushCurveControlArray(builder, control_array)
        
    def end_curve(self, builder: POINTER(GrannyCurveBuilder)) -> POINTER(GrannyCurve2):
        return self.dll.GrannyEndCurve(builder)
    
    def begin_variant(self, string_table_builder: POINTER(GrannyStringTable)) -> POINTER(GrannyVariantBuilder):
        return self.dll.GrannyBeginVariant(string_table_builder)
    
    def end_variant(self, builder: POINTER(GrannyVariantBuilder), dtype: POINTER(POINTER(GrannyDataTypeDefinition)), dobject: POINTER(c_void_p)) -> c_void_p:
        return self.dll.GrannyEndVariant(builder, dtype, dobject)
    
    def add_integer_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, value: c_int32):
        self.dll.GrannyAddIntegerMember(builder, name, value)
        
    def add_integer_array_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, width: c_int32, value: POINTER(c_int32)):
        self.dll.GrannyAddIntegerArrayMember(builder, name, width, value)
        
    def add_unsigned_integer_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, value: c_uint32):
        self.dll.GrannyAddUnsignedIntegerMember(builder, name, value)
        
    def add_scalar_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, value: c_float):
        self.dll.GrannyAddScalarMember(builder, name, value)
        
    def add_scalar_array_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, width: c_int32, value: POINTER(c_float)):
        self.dll.GrannyAddScalarArrayMember(builder, name, width, value)
        
    def add_string_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, value: c_char_p):
        self.dll.GrannyAddStringMember(builder, name, value)
        
    def add_reference_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, dtype: POINTER(GrannyDataTypeDefinition), value: c_char_p):
        self.dll.GrannyAddReferenceMember(builder, name, dtype, value)
        
    def add_dynamic_array_member(self, builder: POINTER(GrannyVariantBuilder), name: c_char_p, count: c_int32, entry_type: POINTER(GrannyDataTypeDefinition), array_entries: c_void_p):
        self.dll.GrannyAddDynamicArrayMember(builder, name, count, entry_type, array_entries)
        
    def new_string_table(self) -> POINTER(GrannyStringTable):
        return self.dll.GrannyNewStringTable()

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
        # Begin track group
        self.dll.GrannyBeginTrackGroup.argtypes=[c_char_p, c_int, c_int, c_int, c_bool]
        self.dll.GrannyBeginTrackGroup.restype=POINTER(GrannyTrackGroupBuilder)
        # Begin transform track
        self.dll.GrannyBeginTransformTrack.argtypes=[POINTER(GrannyTrackGroupBuilder), c_char_p, c_int]
        # Initialse curve format
        self.dll.GrannyCurveInitializeFormat.argtypes=[POINTER(GrannyCurve2)]
        # Set position curve
        self.dll.GrannySetTransformTrackPositionCurve.argtypes=[POINTER(GrannyTrackGroupBuilder), POINTER(GrannyCurve2)]
        # Set orientation curve
        self.dll.GrannySetTransformTrackOrientationCurve.argtypes=[POINTER(GrannyTrackGroupBuilder), POINTER(GrannyCurve2)]
        # Set scale shear curve
        self.dll.GrannySetTransformTrackScaleShearCurve.argtypes=[POINTER(GrannyTrackGroupBuilder), POINTER(GrannyCurve2)]
        # End transform track
        self.dll.GrannyEndTransformTrack.argtypes=[POINTER(GrannyTrackGroupBuilder)]
        # End track group
        self.dll.GrannyEndTrackGroup.argtypes=[POINTER(GrannyTrackGroupBuilder)]
        self.dll.GrannyEndTrackGroup.restype=POINTER(GrannyTrackGroup)
        # Get animation sampler
        self.dll.GrannyBeginSampledAnimation.argtypes=[c_int, c_int]
        self.dll.GrannyBeginSampledAnimation.restype=POINTER(GrannyTrackGroupSampler)
        # Set transform sample
        self.dll.GrannySetTransformSample.argtypes=[POINTER(GrannyTrackGroupSampler), c_int, c_int, POINTER(c_float), POINTER(c_float), POINTER(c_float)]
        # Fit b spline to samples
        self.dll.GrannyFitBSplineToSamples.argtypes=[POINTER(GrannyBSplineSolver), c_uint32, c_int, c_float, c_float, c_float, POINTER(c_float), c_int, c_int, c_float, POINTER(GrannyDataTypeDefinition), c_int, c_bool, c_int]
        self.dll.GrannyFitBSplineToSamples.restype=POINTER(GrannyCurve2)
        # Allocate bspline solver
        self.dll.GrannyAllocateBSplineSolver.argtypes=[c_int, c_int, c_int]
        self.dll.GrannyAllocateBSplineSolver.restype=POINTER(GrannyBSplineSolver)
        # Get position samples
        self.dll.GrannyGetPositionSamples.argtypes=[POINTER(GrannyTrackGroupSampler), c_int]
        self.dll.GrannyGetPositionSamples.restype=POINTER(c_float)
        # Get orientation samples
        self.dll.GrannyGetOrientationSamples.argtypes=[POINTER(GrannyTrackGroupSampler), c_int]
        self.dll.GrannyGetOrientationSamples.restype=POINTER(c_float)
        # Get scale_shear samples
        self.dll.GrannyGetScaleShearSamples.argtypes=[POINTER(GrannyTrackGroupSampler), c_int]
        self.dll.GrannyGetScaleShearSamples.restype=POINTER(c_float)
        # Compress Curve
        self.dll.GrannyCompressCurve.argtypes=[POINTER(GrannyBSplineSolver), c_uint32, POINTER(GrannyCompressCurveParameters), POINTER(c_float), c_int, c_int, c_float, c_bool]
        self.dll.GrannyCompressCurve.restype=POINTER(GrannyCurve2)
        # Begin Curve
        self.dll.GrannyBeginCurve.argtypes=[POINTER(GrannyDataTypeDefinition), c_int, c_int, c_int]
        self.dll.GrannyBeginCurve.restype=POINTER(GrannyCurveBuilder)
        # Push control array
        self.dll.GrannyPushCurveControlArray.argtypes=[POINTER(GrannyCurveBuilder), POINTER(c_float)]
        # End Curve
        self.dll.GrannyEndCurve.argtypes=[POINTER(GrannyCurveBuilder)]
        self.dll.GrannyEndCurve.restype=POINTER(GrannyCurve2)
        # Begin Variant
        self.dll.GrannyBeginVariant.argtypes=[POINTER(GrannyStringTable)]
        self.dll.GrannyBeginVariant.restype=POINTER(GrannyVariantBuilder)
        # End Variant
        self.dll.GrannyEndVariant.argtypes=[POINTER(GrannyVariantBuilder), POINTER(POINTER(GrannyDataTypeDefinition)), POINTER(c_void_p)]
        self.dll.GrannyEndVariant.restype=c_void_p
        # Add integer member
        self.dll.GrannyAddIntegerMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_int32]
        # Add integer array member
        self.dll.GrannyAddIntegerArrayMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_int32, POINTER(c_int32)]
        # Add uint member
        self.dll.GrannyAddUnsignedIntegerMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_uint32]
        # Add float member
        self.dll.GrannyAddScalarMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_float]
        # Add float array member
        self.dll.GrannyAddScalarArrayMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_int32, POINTER(c_float)]
        # Add string member
        self.dll.GrannyAddStringMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_char_p]
        # Add reference member
        self.dll.GrannyAddReferenceMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, POINTER(GrannyDataTypeDefinition), c_void_p]
        # Add dynamic array member
        self.dll.GrannyAddDynamicArrayMember.argtypes=[POINTER(GrannyVariantBuilder), c_char_p, c_int32, POINTER(GrannyDataTypeDefinition), c_void_p]
        # Create string table
        self.dll.GrannyNewStringTable.restype=POINTER(GrannyStringTable)
        