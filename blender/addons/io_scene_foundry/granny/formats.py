"""Contains Granny struct and data information."""
from ctypes import CFUNCTYPE, c_byte, c_int, c_int32, c_longlong, c_ushort, c_void_p, c_bool, c_uint, c_char_p, c_float, c_ubyte, c_ulonglong, Structure, POINTER
from enum import IntEnum

# Define the types we need.
class CtypesEnum(IntEnum):
    """A ctypes-compatible IntEnum superclass."""
    @classmethod
    def from_param(cls, obj : int):
        return int(obj)

class GrannyRef(Structure):
    _pack_ = 1
    _fields_ = [('section_index', c_uint),
                ('offset',c_uint)]

class GrannyFileHeader(Structure):
    _pack_ = 1
    _fields_ = [('version', c_uint),
                ('total_size',c_uint),
                ('crc',c_uint),
                ('section_array_offset',c_uint),
                ('section_array_count',c_uint),
                ('root_object_type_definition',POINTER(GrannyRef)),
                ('root_object',POINTER(GrannyRef)),
                ('type_tag', c_uint),
                ('extra_tags', c_uint * 4),
                ('string_database_crc', c_uint),
                ('reserved_unused', c_uint * 3),]

class GrannyFileMagic(Structure):
    _pack_ = 1
    _fields_ = [('magic_value', c_uint * 4),
                ('header_size',c_uint),
                ('header_format',c_uint),
                ('reserved', c_uint * 2)]

class GrannyFile(Structure):
    _pack_ = 1
    _fields_ = [('is_byte_reversed', c_int),
                ('header',POINTER(GrannyFileHeader)),
                ('source_magic_value',POINTER(GrannyFileMagic)),
                ('section_count',c_int),
                ('sections',POINTER(c_void_p)),
                ('marshalled',POINTER(c_bool)),
                ('is_user_memory',POINTER(c_bool)),
                ('conversion_buffer',POINTER(c_bool)),]

class GrannyMemberType(CtypesEnum):
    granny_end_member = 0
    granny_inline_member = 1
    granny_reference_member = 2
    granny_reference_to_array_member = 3
    granny_array_of_reference_member = 4
    granny_variant_reference_member = 5
    granny_unsupported_member_type = 6
    granny_reference_to_variant_array_member = 7
    granny_string_member = 8
    granny_transform_member = 9
    granny_real32_member = 10
    granny_int8_member = 11
    granny_uint8_member = 12
    granny_binormal_int8_member = 13
    granny_normal_u_int8_member = 14
    granny_int16_member = 15
    granny_uint16_member = 16
    granny_binormal_int16_member = 17
    granny_normal_u_int16_member = 18
    granny_int32_member = 19
    granny_uint32_member = 20
    granny_real16_member = 21
    granny_empty_reference_member = 22
    granny_one_past_last_member_type = 23
    granny_bool32_member = granny_int32_member
    granny_member_type_force_int = int(0x7fffffff)

class GrannyDataTypeDefinition(Structure):
    """ granny data type info """
    pass

GrannyDataTypeDefinition._pack_ = 1
GrannyDataTypeDefinition._fields_ = [
                ('member_type',c_int), # GrannyMemberType
                ('name',c_char_p),
                ('reference_type',POINTER(GrannyDataTypeDefinition)),
                ('array_width',c_int32),
                ('extra',c_uint * 3),
                ('unused_or_ignored',c_ulonglong)]

class GrannyVariant(Structure):
    _pack_ = 1
    _fields_ = [
                ('type',POINTER(GrannyDataTypeDefinition)),
                ('object',c_void_p)]

class GrannyFileArtToolInfo(Structure):
    _pack_ = 1
    _fields_ = [
                ('art_tool_name',c_char_p),
                ('art_tool_major_revision',c_int),
                ('art_tool_minor_revision',c_int),
                ('art_tool_pointer_size',c_int),
                ('units_per_meter',c_float),
                ('origin',c_float * 3),
                ('right_vector',c_float * 3),
                ('up_vector',c_float * 3),
                ('back_vector',c_float * 3),
                ('extended_data',GrannyVariant)]

class GrannyFileExporterInfo(Structure):
    _pack_ = 1
    _fields_ = [
                ('exporter_name',c_char_p),
                ('exporter_major_revision',c_int),
                ('exporter_minor_revision',c_int),
                ('exporter_customization',c_int),
                ('exporter_build_number',c_int),
                ('extended_data',GrannyVariant)]

class GrannyTextureMipLevel(Structure):
    _pack_ = 1
    _fields_ = [
                ('stride',c_int),
                ('pixel_byte_count',c_int),
                ('pixel_bytes',c_void_p)]     

class GrannyTextureImage(Structure):
    _pack_ = 1
    _fields_ = [
                ('mip_level_count',c_int),
                ('mip_levels',POINTER(GrannyTextureMipLevel))]     

class GrannyPixelLayout(Structure):
    _pack_ = 1
    _fields_ = [
                ('bytes_per_pixel',c_int),
                ('shift_for_component',c_int * 4),
                ('bits_for_component',c_int * 4)]     

class GrannyTexture(Structure):
    _pack_ = 1
    _fields_ = [
                ('file_name',c_char_p),
                ('texture_type',c_int),
                ('width',c_int),
                ('height',c_int),
                ('encoding',c_int),
                ('sub_format',c_int),
                ('pixel_layout',GrannyPixelLayout),
                ('image_count',c_int),
                ('images',POINTER(GrannyTextureImage)),
                ('extended_data',GrannyVariant)]

class GrannyMaterialMap(Structure):
    pass
GrannyMaterialMap._pack_ = 1


class GrannyMaterial(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('map_count',c_int),
                ('maps', POINTER(GrannyMaterialMap)),
                ('texture', POINTER(GrannyTextureImage)),
                ('extended_data', GrannyVariant)]     

GrannyMaterialMap._fields_ = [
                ('usage', c_char_p),
                ('maps', POINTER(GrannyMaterial))]     

class GrannyTransform(Structure):
    _pack_ = 1
    _fields_ = [
                ('flags',c_uint),
                ('position',c_float * 3),
                ('orientation',c_float * 4),
                ('scale_shear',c_float * 3 * 3)]     

class GrannyBone(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('parent_index',c_int),
                ('local_transform',GrannyTransform),
                ('inverse_world_4x4',c_float * 4 * 4),
                ('lod_error',c_float),
                ('extended_data',GrannyVariant)]     

class GrannySkeleton(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('bone_count',c_int),
                ('bones',POINTER(GrannyBone)),
                ('lod_type',c_int),
                ('extended_data',GrannyVariant)]     

class GrannyVertexAnnotationSet(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('vertex_annotation_type',POINTER(GrannyDataTypeDefinition)),
                ('vertex_annotation_count',c_int),
                ('vertex_annotations',POINTER(c_ubyte)),
                ('indices_map_from_vertex_to_annotation',c_int),
                ('vertex_annotation_index_count',c_int),
                ('vertex_annotation_indices',POINTER(c_int))]    

class GrannyVertexData(Structure):
    _pack_ = 1
    _fields_ = [
                ('vertex_type',POINTER(GrannyDataTypeDefinition)),
                ('vertex_count',c_int),
                ('vertices',POINTER(c_ubyte)),
                ('vertex_component_name_count',c_int),
                ('vertex_component_names',POINTER(c_char_p)),
                ('vertex_annotation_set_count',c_int),
                ('vertex_annotation_sets',POINTER(GrannyVertexAnnotationSet))]     

class GrannyTriAnnotationSet(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('tri_annotation_type',POINTER(GrannyDataTypeDefinition)),
                ('tri_annotation_count',c_int),
                ('tri_annotations',POINTER(c_ubyte)),
                ('indices_map_from_tri_to_annotation',c_int),
                ('tri_annotation_index_count',c_int),
                ('tri_annotation_indices',POINTER(c_int))]     

class GrannyTriMaterialGroup(Structure):
    _pack_ = 1
    _fields_ = [
                ('material_index',c_int),
                ('tri_first',c_int),
                ('tri_count',c_int)]    

class GrannyTriTopology(Structure):
    _pack_ = 1
    _fields_ = [
                ('group_count',c_int),
                ('groups',POINTER(GrannyTriMaterialGroup)),
                ('index_count',c_int),
                ('indices',POINTER(c_int)),
                ('index16_count',c_int),
                ('indices16',POINTER(c_ushort)),
                ('vertex_to_vertex_count',c_int),
                ('vertex_to_vertex_map',POINTER(c_int)),
                ('vertex_to_triangle_count',c_int),
                ('vertex_to_triangle_map',POINTER(c_int)),
                ('side_to_neighbor_count',c_int),
                ('side_to_neighbor_map',POINTER(c_uint)),
                ('bones_for_triangle_count',c_int),
                ('bones_for_triangle',POINTER(c_int)),
                ('triangle_to_bone_count',c_int),
                ('triangle_to_bone_indices',POINTER(c_int)),
                ('tri_annotation_set_count',c_int),
                ('tri_annotation_sets',POINTER(GrannyTriAnnotationSet))]    

class GrannyMorphTarget(Structure):
    _pack_ = 1
    _fields_ = [
                ('scalar_name',c_char_p),
                ('vertex_data',POINTER(GrannyVertexData)),
                ('data_is_deltas',c_int)]  

class GrannyMaterialBinding(Structure):
    _pack_ = 1
    _fields_ = [
                ('material',POINTER(GrannyMaterial))]  

class GrannyBoneBinding(Structure):
    _pack_ = 1
    _fields_ = [
                ('bone_name',c_char_p),
                ('obb_min',c_float * 3),
                ('obb_max',c_float * 3),
                ('triangle_count',c_int),
                ('triangle_indices',POINTER(c_int))]  

class GrannyMesh(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('primary_vertex_data',POINTER(GrannyVertexData)),
                ('morph_target_count',c_int),
                ('morph_targets',POINTER(GrannyMorphTarget)),
                ('primary_topology',POINTER(GrannyTriTopology)),
                ('material_binding_count',c_int),
                ('material_bindings',POINTER(GrannyMaterialBinding)),
                ('bone_bindings_count',c_int),
                ('bone_bindings',POINTER(GrannyBoneBinding)),
                ('extended_data',GrannyVariant)]  

class GrannyModelMeshBinding(Structure):
    _pack_ = 1
    _fields_ = [
                ('mesh',POINTER(GrannyMesh))]  

class GrannyModel(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('skeleton',POINTER(GrannySkeleton)),
                ('initial_placement',GrannyTransform),
                ('mesh_binding_count',c_int),
                ('mesh_bindings',POINTER(GrannyModelMeshBinding)),
                ('extended_data',GrannyVariant)]  


class GrannyModelInstance(Structure):
    _pack_ = 1
    pass

GrannyModelInstance._fields_ = [
    ('model',POINTER(GrannyModel)),
    ('cached_skeleton',POINTER(GrannySkeleton)),
    ('cached_bones',POINTER(GrannyBone)),
    ('cached_bone_count',c_longlong),
    ('binding_sentinel',c_byte * 128), # GrannyModelControlBinding
    ('mirror_transform_cache',POINTER(GrannyTransform)),
    ('next',POINTER(GrannyModelInstance)),
    ('prev',POINTER(GrannyModelInstance)),
    ('user_data',c_void_p * 4),
    ('reserved0',c_void_p)]  


# GrannyModelControlBinding._fields_ = [
#     ('control',POINTER(c_void_p)), #GrannyControl (Cant be bothered doing that struct right now.)
#     ('control_prev',POINTER(GrannyModelControlBinding)),
#     ('control_next',POINTER(GrannyModelControlBinding)),
#     ('model_instance',POINTER(GrannyModelInstance)),
#     ('model_prev',POINTER(GrannyModelControlBinding)),
#     ('model_next',POINTER(GrannyModelControlBinding)),
#     ('callbacks',c_void_p), #GrannyModelControlCallbacks (Cant be bothered doing that struct right now.)
#     ('derived',c_uint * 16),
#     ('binding_type',c_longlong)]  #GrannyModelControlBindingType
    
class GrannyCurve2(Structure):
    _pack_ = 1
    _fields_ = [
                ('curve_data',GrannyVariant)]  

class GrannyVectorTrack(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('track_key',c_int),
                ('dimension',c_int),
                ('value_curve',GrannyCurve2)]  

class GrannyTransformTrack(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('flags',c_int),
                ('orientation_curve',GrannyCurve2),
                ('position_curve',GrannyCurve2),
                ('scale_shear_curve',GrannyCurve2)]  

class GrannyTextTrackEntry(Structure):
    _pack_ = 1
    _fields_ = [
                ('timestamp',c_float),
                ('timestamp',c_char_p)]  

class GrannyTextTrack(Structure):
    """ text animation data used for engine stuff """
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),  
                ('entry_count',c_int),
                ('entries',POINTER(GrannyTextTrackEntry)),]  

class GrannyPeriodicLoop(Structure):
    _pack_ = 1
    _fields_ = [
                ('radius',c_float),
                ('d_angle',c_float),
                ('d_z',c_float),
                ('basis_x',c_float * 3),
                ('basis_y',c_float * 3),
                ('axis',c_float * 3),]  

class GrannyTrackGroup(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('vector_track_count',c_int),
                ('vector_tracks',POINTER(GrannyVectorTrack)),
                ('transform_track_count',c_int),
                ('morph_targets',POINTER(GrannyTransformTrack)),
                ('transform_lod_error_count',c_int),
                ('tranform_lod_errors',POINTER(c_float)),
                ('text_track_count',c_int),
                ('text_tracks',POINTER(GrannyTextTrack)),
                ('initial_placement',GrannyTransform),
                ('flags',c_int),
                ('loop_translation',c_float * 3),
                ('periodic_loop',POINTER(GrannyPeriodicLoop)),
                ('extended_data',GrannyVariant)]  

class GrannyAnimation(Structure):
    _pack_ = 1
    _fields_ = [
                ('name',c_char_p),
                ('duration',c_float),
                ('time_step',c_float),
                ('oversampling',c_float),
                ('track_group_count',c_int),
                ('track_groups',POINTER(GrannyTrackGroup)),
                ('default_loop_count',c_int),
                ('flags',c_int),
                ('extended_data',GrannyVariant)]  


class GrannyFileInfo(Structure):
    _pack_ = 1
    _fields_ = [
                ('art_tool_info',POINTER(GrannyFileArtToolInfo)),
                ('exporter_info',POINTER(GrannyFileExporterInfo)),
                ('file_name',c_char_p),
                ('texture_count',c_int),
                ('textures',POINTER(POINTER(GrannyTexture))),
                ('material_count',c_int),
                ('materials',POINTER(POINTER(GrannyMaterial))),
                ('skeleton_count',c_int),
                ('skeletons',POINTER(POINTER(GrannySkeleton))),
                ('vertex_data_count',c_int),
                ('vertex_datas',POINTER(POINTER(GrannyVertexData))),
                ('tri_topology_count',c_int),
                ('tri_topologies',POINTER(POINTER(GrannyTriTopology))),
                ('mesh_count',c_int),
                ('meshes',POINTER(POINTER(GrannyMesh))),
                ('model_count',c_int),
                ('models',POINTER(POINTER(GrannyModel))),
                ('track_group_count',c_int),
                ('track_groups',POINTER(POINTER(GrannyTrackGroup))),
                ('animation_count',c_int),
                ('animations',POINTER(POINTER(GrannyAnimation))),
                ('extended_data',GrannyVariant)]


class GrannyGRNSection(Structure):
    _pack_ = 1
    _fields_ = [
                ('format',c_uint),
                ('data_offset',c_uint),
                ('data_size',c_uint),
                ('expanded_data_size',c_uint),
                ('internal_alignment',c_uint),
                ('first_16bit',c_uint),
                ('first_8bit',c_uint),
                ('pointer_fixup_array_offset',c_uint),
                ('pointer_fixup_array_count',c_uint),
                ('mixed_marshalling_fixup_array_offset',c_uint),
                ('mixed_marshalling_fixup_array_count',c_uint)]

class GrannyLogCallback(Structure):
    _pack_ = 1
    _fields_ = [
                ('function',CFUNCTYPE(None, c_int,c_int,c_char_p,c_int,c_char_p,c_void_p)),
                ('user_data',c_void_p)]

class GrannyStringTreeEntry(Structure):
    _pack_ = 1
    pass

GrannyStringTreeEntry._fields_ = [
                ('string',c_char_p),
                ('left',POINTER(GrannyStringTreeEntry)),
                ('right',POINTER(GrannyStringTreeEntry))]

class GrannyStringTree(Structure):
    _pack_ = 1
    _fields_ = [
                ('unused',POINTER(GrannyStringTreeEntry)),
                ('first',POINTER(GrannyStringTreeEntry)),
                ('last',POINTER(GrannyStringTreeEntry)),
                ('root',POINTER(GrannyStringTreeEntry)),
                ('container_buffers_member',c_void_p)]

class GrannyMemoryArena(Structure):
    _pack_ = 1
    pass

GrannyMemoryArena._fields_ = [
                ('data_start',c_ulonglong),
                ('next',POINTER(GrannyMemoryArena))]

class GrannyStringTableBlock(Structure):
    """ granny string stuff """
    _pack_ = 1
    pass

GrannyStringTableBlock._fields_ = [
                ('data_start',c_char_p),
                ('one_past_last_data',c_char_p),
                ('last',POINTER(GrannyStringTableBlock))]

class GrannyStringTable(Structure):
    _pack_ = 1
    _fields_ = [
                ('tree',GrannyStringTree),
                ('block_size',c_int),
                ('last_block',POINTER(GrannyStringTableBlock)),
                ('arena',POINTER(GrannyMemoryArena))]

class GrannyVariantMemberBuilder(Structure):
    _pack_ = 1
    pass

GrannyVariantMemberBuilder._fields_ = [
                ('type',GrannyDataTypeDefinition),
                ('data',c_void_p),
                ('next',POINTER(GrannyVariantMemberBuilder))]

class GrannyVariantBuilder(Structure):
    _pack_ = 1
    _fields_ = [
                ('strings',POINTER(GrannyStringTable)),
                ('member_count',c_int),
                ('total_object_size',c_int),
                ('first_member',POINTER(GrannyVariantMemberBuilder)),
                ('last_member',POINTER(GrannyVariantMemberBuilder))]

class GrannyWrittenType(Structure):
    _pack_ = 1
    pass

GrannyWrittenType._fields_ = [
        ('signature',c_uint),
        ('type',POINTER(GrannyDataTypeDefinition)),
        ('left',POINTER(GrannyWrittenType)),
        ('right',POINTER(GrannyWrittenType)),
        ('next',POINTER(GrannyWrittenType)),
        ('previous',POINTER(GrannyWrittenType))]

class GrannyWrittenTypeRegistry(Structure):
    _pack_ = 1
    _fields_ = [
        ('unused',POINTER(GrannyWrittenType)),
        ('first',POINTER(GrannyWrittenType)),
        ('last',POINTER(GrannyWrittenType)),
        ('root',POINTER(GrannyWrittenType)),
        ('container_buffers_member',c_void_p),]

class GrannyHashEntry(Structure):
    _pack_ = 1
    pass

GrannyHashEntry._fields_ = [
        ('key',c_void_p),
        ('data',c_void_p),
        ('left',POINTER(GrannyHashEntry)),
        ('right',POINTER(GrannyHashEntry))]

class GrannyPointerHash(Structure):
    _pack_ = 1
    _fields_ = [
        ('unused',POINTER(GrannyHashEntry)),
        ('first',POINTER(GrannyHashEntry)),
        ('last',POINTER(GrannyHashEntry)),
        ('root',POINTER(GrannyHashEntry)),
        ('container_buffers_member',c_void_p),]

class GrannyAllocatedBlock(Structure):
    _pack_ = 1
    pass

GrannyAllocatedBlock._fields_ = [
        ('used_unit_count',c_int),
        ('base',POINTER(c_ubyte)),
        ('first_index',c_int),
        ('previous',POINTER(GrannyAllocatedBlock))]

class GrannyStackAllocator(Structure):
    _pack_ = 1
    _fields_ = [
        ('unit_size',c_int),
        ('units_per_block',c_int),
        ('total_used_unit_count',c_int),
        ('last_block',POINTER(GrannyAllocatedBlock)),
        ('max_units',c_int),
        ('active_blocks',c_int),
        ('max_active_blocks',c_int),
        ('block_directory',POINTER(POINTER(GrannyAllocatedBlock)))]

class GrannyFileDataTreeWriter(Structure):
    _pack_ = 1
    _fields_ = [
        ('root_object_type_definition',POINTER(GrannyDataTypeDefinition)),
        ('root_object',c_void_p),
        ('traversal_number',c_int),
        ('flags',c_uint),
        ('default_type_section_index',c_int),
        ('default_object_section_index',c_int),
        ('object_blocks',GrannyStackAllocator),
        ('block_hash',POINTER(GrannyPointerHash)),
        ('string_callback',CFUNCTYPE(c_uint,c_void_p,c_char_p)),
        ('string_callback_data',c_void_p),
        ('written_type_registry',GrannyWrittenTypeRegistry),
        ('source_file_for_sectioning',POINTER(GrannyFile)),
        ('source_file_for_formats',POINTER(GrannyFile))]