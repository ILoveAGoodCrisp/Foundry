'''Classes to store intermediate geometry data to be passed to granny files'''

from collections import defaultdict
import csv
from ctypes import Array, Structure, c_char_p, c_float, c_int, c_uint, POINTER, c_ubyte, c_void_p, cast, create_string_buffer, memmove, pointer, sizeof
import logging
from math import degrees
from pathlib import Path
import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np
import clr

from ..managed_blam.material import MaterialTag

from ..managed_blam.shader import ShaderTag

from ..granny.formats import GrannyAnimation, GrannyBone, GrannyCompressCurveParameters, GrannyCurve2, GrannyCurveDataDaKeyframes32f, GrannyDataTypeDefinition, GrannyMaterial, GrannyMaterialMap, GrannyMemberType, GrannyTrackGroup, GrannyTransform, GrannyTransformTrack, GrannyTriAnnotationSet, GrannyTriMaterialGroup, GrannyTriTopology, GrannyVertexData
from ..granny import Granny

from .export_info import ExportInfo, FaceDrawDistance, FaceMode, FaceSides, FaceType, LightmapType

from ..props.mesh import NWO_FaceProperties_ListItems, NWO_MeshPropertiesGroup

from .. import utils

from ..tools.asset_types import AssetType

from ..constants import IDENTITY_MATRIX, RENDER_MESH_TYPES, VALID_MESHES
NORMAL_FIX_MATRIX = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
logging.basicConfig(level=logging.DEBUG)

# PEDESTAL_MATRIX_X_POSITIVE = Matrix(((1.0, 0.0, 0.0, 0.0),
#                                 (0.0, 1.0, 0.0, 0.0),
#                                 (0.0, 0.0, 1.0, 0.0),
#                                 (0.0, 0.0, 0.0, 1.0)))

# PEDESTAL_MATRIX_Y_NEGATIVE = Matrix(((0.0, 1.0, 0.0, 0.0),
#                                     (-1.0, 0.0, 0.0, 0.0),
#                                     (0.0, 0.0, 1.0, 0.0),
#                                     (0.0, 0.0, 0.0, 1.0)))

# PEDESTAL_MATRIX_Y_POSITIVE = Matrix(((0.0, -1.0, 0.0, 0.0),
#                                     (1.0, 0.0, 0.0, 0.0),
#                                     (0.0, 0.0, 1.0, 0.0),
#                                     (0.0, 0.0, 0.0, 1.0)))

# PEDESTAL_MATRIX_X_NEGATIVE = Matrix(((-1.0, 0.0, 0.0, 0.0),
#                                     (0.0, -1.0, 0.0, 0.0),
#                                     (0.0, 0.0, 1.0, 0.0),
#                                     (0.0, 0.0, 0.0, 1.0)))

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
            
class TransformTrack:
    def __init__(self, name: str):
        self.name = name
        self.position_data: GrannyCurveDataDaKeyframes32f = GrannyCurveDataDaKeyframes32f()
        self.orientation_data: GrannyCurveDataDaKeyframes32f = GrannyCurveDataDaKeyframes32f()
        self.scale_data: GrannyCurveDataDaKeyframes32f = GrannyCurveDataDaKeyframes32f()
    
class TrackGroup:
    def __init__(self, name: str):
        self.name = name
        self.transform_tracks: list[TransformTrack] = []
        self.granny = None

class VirtualAnimation:
    def __init__(self, action: bpy.types.Action, scene: 'VirtualScene'):
        nwo = action.nwo
        self.name = nwo.name_override.strip() if nwo.name_override.strip() else action.name
        
        if scene.default_animation_compression != "Automatic" and nwo.compression == "Default":
            self.compression = scene.default_animation_compression
        else:
            self.compression = nwo.compression
            
        self.animation_type = nwo.animation_type
        self.movement = nwo.animation_movement_data
        self.space = nwo.animation_space
        self.pose_overlay = nwo.animation_is_pose
        
        self.frame_count: int = int(action.frame_end) - int(action.frame_start) + 1
        self.frame_range: tuple[int, int] = (int(action.frame_start), int(action.frame_end))
        self.granny_animation = None
        self.granny_track_group = None
        
        self.track_group = self.create_track_group(sorted(scene.animated_bones, key=lambda bone: bone.name), scene)
        # self.to_granny_track_group(scene)
        self.to_granny_animation(scene)
        return
        bones = scene.animated_bones
        num_transform_tracks = len(bones)
        sampler = scene.granny._begin_sampled_animation(num_transform_tracks, self.frame_count)
        
        for frame_idx, frame in enumerate(range(*self.frame_range)):
            bpy.context.scene.frame_set(frame)
            for idx, bone in enumerate(bones):
                bone: bpy.types.PoseBone
                loc, rot, sca = bone.matrix.decompose()
                position = (c_float * 3)(loc.x, loc.y, loc.z)
                orientation = (c_float * 4)(rot.x, rot.y, rot.z, rot.w)
                scale_shear = (c_float * 9)(sca.x, 0.0, 0.0, 0.0, sca.y, 0.0, 0.0, 0.0, sca.z)
                scene.granny._set_transform_sample(sampler, idx, frame_idx, position, orientation, scale_shear)
                
        max_degree = 0
        max_dimension = 9
        max_sample_count = self.frame_count
        
        solver = scene.granny._allocate_bspline_solver(max_degree, max_sample_count, max_dimension)
        # builder = scene.granny._begin_track_group(create_string_buffer(scene.skeleton_node.name.encode()), 0, num_transform_tracks, 0, False)
        tracks = []
        curves = []
        for idx, bone in enumerate(bones):
            position_samples = scene.granny._get_position_samples(sampler, idx)
            orientation_samples = scene.granny._get_orientation_samples(sampler, idx)
            scale_shear_samples = scene.granny._get_scale_shear_samples(sampler, idx)
            
            curve_format = pointer(scene.granny.curve_type)
            
            # 0x30
            curve_parameters = GrannyCompressCurveParameters()
            curve_parameters.desired_degree = 0
            curve_parameters.allow_degree_reduction = False
            curve_parameters.error_tolerance = 0.0
            curve_parameters.c0_threshold = 0.0
            curve_parameters.c1_threshold = 0.0
            curve_parameters.possible_compression_types = curve_format
            curve_parameters.possible_compression_types_count = 1
            curve_parameters.constant_compression_type = None
            curve_parameters.identity_compression_type = None
            curve_parameters.identity_vector = None
            
            position_curve = scene.granny._compress_curve(solver, 0x30, curve_parameters, position_samples, 3, self.frame_count, scene.time_step, False)
            orientation_curve = scene.granny._compress_curve(solver, 0x30, curve_parameters, orientation_samples, 4, self.frame_count, scene.time_step, False)
            scale_shear_curve = scene.granny._compress_curve(solver, 0x30, curve_parameters, scale_shear_samples, 9, self.frame_count, scene.time_step, False)
            
            track = GrannyTransformTrack()
            
            track.name = bone.name.encode()
            track.position_curve = position_curve.contents
            track.orientation_curve = orientation_curve.contents
            track.scale_shear_curve = scale_shear_curve.contents
            tracks.append(track)
            # track.initial_placement = GrannyTransform(flags=7, position=(c_float * 3)(0, 0, 0), orientation=(c_float * 4)(0, 0, 0, 1), scale_shear=(c_float * 3 * 3)((1, 0, 0), (0.0, 1, 0), (0.0, 0.0, 1)))
            # curves.append((position_curve, orientation_curve, scale_shear_curve))

        # for idx, (p, o, s) in enumerate(curves):
        #     # scene.granny._begin_transform_track(builder, create_string_buffer(b""), 0)
        #     # scene.granny._set_transform_track_position(builder, p)
        #     # scene.granny._set_transform_track_orientation(builder, o)
        #     # scene.granny._set_transform_track_scale(builder, s)
        #     # scene.granny._end_transform_track(builder)

        #     track = GrannyTransformTrack()
        #     track.name = bone.name.encode()
        #     track.position_curve = p.contents
        #     track.orientation_curve = o.contents
        #     track.scale_shear_curve = s.contents
        #     tracks.append(track)
        
        # self.granny_track_group = scene.granny._end_track_group(builder)
        # self.granny_track_group.contents.name = scene.skeleton_node.name.encode()
        granny_track_group = GrannyTrackGroup()
        granny_track_group.name = scene.skeleton_node.name.encode()
        granny_track_group.transform_track_count = len(tracks)
        granny_track_group.transform_tracks = (GrannyTransformTrack * len(tracks))(*tracks)
        granny_track_group.flags = 2
        granny_track_group.initial_placement = GrannyTransform(flags=7, position=(c_float * 3)(0, 0, 0), orientation=(c_float * 4)(0, 0, 0, 1), scale_shear=(c_float * 3 * 3)((1, 0, 0), (0.0, 1, 0), (0.0, 0.0, 1)))
        self.granny_track_group = pointer(granny_track_group)
        self.to_granny_animation(scene)
            
        
    def create_track_group(self, bones: list[bpy.types.PoseBone], scene: 'VirtualScene') -> TrackGroup:
        positions = defaultdict(list)
        orientations = defaultdict(list)
        scales = defaultdict(list)
        tracks = []
        yaw_index = 0
        for frame_idx, frame in enumerate(range(self.frame_range[0], self.frame_range[1] + 1)):
            bpy.context.scene.frame_set(frame)
            for idx, bone in enumerate(bones):
                bone: bpy.types.PoseBone
                if bone.parent:
                    loc, rot, sca = utils.get_bone_matrix_local(bone).decompose()
                else:
                    loc, rot, sca = (IDENTITY_MATRIX).decompose()
                
                i = round(rot[1], 7)
                j = round(rot[2], 7)
                k = round(rot[3], 7)
                w = round(rot[0], 7)
                position = (c_float * 3)(loc.x, loc.y, loc.z)
                orientation = (c_float * 4)(i, j, k, w)
                scale_shear = (c_float * 9)(sca.x, 0.0, 0.0, 0.0, sca.y, 0.0, 0.0, 0.0, sca.z)
                positions[bone].extend(position)
                orientations[bone].extend(orientation)
                scales[bone].extend(scale_shear)
        
        for bone in bones:
            track = (c_float * (self.frame_count * 3))(*positions[bone])
            tracks.append(track)
            
            track = (c_float * (self.frame_count * 4))(*orientations[bone])
            tracks.append(track)
            
            track = (c_float * (self.frame_count * 9))(*scales[bone])
            tracks.append(track)
            
        num_transform_tracks = len(bones)
        granny_transform_tracks = (GrannyTransformTrack * num_transform_tracks)()
        
        # group_builder = scene.granny._begin_track_group(self.name.encode(), 0, num_transform_tracks, 0)
        
        for bone_idx, i in enumerate(range(0, len(tracks), 3)):
            granny_transform_tracks[bone_idx].name = bones[bone_idx].name.encode()
            
            builder = scene.granny._begin_curve(scene.granny.keyframe_type, 0, 3, self.frame_count)
            scene.granny._push_control_array(builder, tracks[i])
            position_curve = scene.granny._end_curve(builder)
            
            builder = scene.granny._begin_curve(scene.granny.keyframe_type, 0, 4, self.frame_count)
            scene.granny._push_control_array(builder, tracks[i + 1])
            orientation_curve = scene.granny._end_curve(builder)
            
            builder = scene.granny._begin_curve(scene.granny.keyframe_type, 0, 9, self.frame_count)
            scene.granny._push_control_array(builder, tracks[i + 2])
            scale_curve = scene.granny._end_curve(builder)
            
            granny_transform_tracks[bone_idx].position_curve = position_curve.contents
            granny_transform_tracks[bone_idx].orientation_curve = orientation_curve.contents
            granny_transform_tracks[bone_idx].scale_shear_curve = scale_curve.contents
            
        granny_track_group = GrannyTrackGroup()
        granny_track_group.name = scene.skeleton_node.name.encode()
        granny_track_group.transform_track_count = num_transform_tracks
        granny_track_group.transform_tracks = granny_transform_tracks
        granny_track_group.flags = 2
        self.granny_track_group = pointer(granny_track_group)
        # self.granny_track_group = scene.granny._end_track_group(group_builder)
        


    def to_granny_track_group(self, scene: 'VirtualScene'):
        num_transform_tracks = len(self.track_group.transform_tracks)
        granny_transform_tracks = (GrannyTransformTrack * num_transform_tracks)()
        for i in range(num_transform_tracks):
            transform_track = GrannyTransformTrack()
            granny_transform_tracks[i].name = self.track_group.transform_tracks[i].name.encode()
            transform_track.name = self.track_group.transform_tracks[i].name.encode()
            
            position_curve = GrannyCurve2()
            position_curve.curve_data.type = scene.granny.keyframe_type
            position_curve.curve_data.object = cast(pointer(self.track_group.transform_tracks[i].position_data), c_void_p)
            
            orientation_curve = GrannyCurve2()
            orientation_curve.curve_data.type = scene.granny.keyframe_type
            orientation_curve.curve_data.object = cast(pointer(self.track_group.transform_tracks[i].orientation_data), c_void_p)
            
            
            scale_curve = GrannyCurve2()
            scale_curve.curve_data.type = scene.granny.keyframe_type
            scale_curve.curve_data.object = cast(pointer(self.track_group.transform_tracks[i].scale_data), c_void_p)
            
            scene.granny._initialise_curve_format(position_curve)
            scene.granny._initialise_curve_format(orientation_curve)
            scene.granny._initialise_curve_format(scale_curve)
            
            transform_track.position_curve = position_curve
            transform_track.orientation_curve = orientation_curve
            transform_track.scale_shear_curve = scale_curve
            
            
            granny_transform_tracks[i].position_curve = position_curve
            granny_transform_tracks[i].orientation_curve = orientation_curve
            granny_transform_tracks[i].scale_shear_curve = scale_curve
            
        granny_track_group = GrannyTrackGroup()
        granny_track_group.name = scene.skeleton_node.name.encode()
        granny_track_group.transform_track_count = num_transform_tracks
        granny_track_group.transform_tracks = granny_transform_tracks
        self.granny_track_group = pointer(granny_track_group)
        
        
        # builder = scene.granny._begin_track_group(self.name.encode(), 0, len(self.track_group.transform_tracks), 0, False)
        # for track in self.track_group.transform_tracks:
        #     scene.granny._begin_transform_track(builder, track.name.encode(), 0)

        #     position_curve = GrannyCurve2()
        #     position_curve.curve_data.type = scene.granny.keyframe_type
        #     position_curve.curve_data.object = cast(pointer(track.position_data), c_void_p)
            
        #     orientation_curve = GrannyCurve2()
        #     orientation_curve.curve_data.type = scene.granny.keyframe_type
        #     orientation_curve.curve_data.object = cast(pointer(track.orientation_data), c_void_p)
            
        #     scale_curve = GrannyCurve2()
        #     scale_curve.curve_data.type = scene.granny.keyframe_type
        #     scale_curve.curve_data.object = cast(pointer(track.scale_data), c_void_p)
            
        #     scene.granny._initialise_curve_format(position_curve)
        #     scene.granny._initialise_curve_format(orientation_curve)
        #     scene.granny._initialise_curve_format(scale_curve)
            
        #     scene.granny._set_transform_track_position(builder, position_curve)
        #     scene.granny._set_transform_track_orientation(builder, orientation_curve)
        #     scene.granny._set_transform_track_scale(builder, scale_curve)
            
        #     scene.granny._end_transform_track(builder)
            
        # self.granny_track_group = scene.granny._end_track_group(builder)
        
    def to_granny_animation(self, scene: 'VirtualScene'):
        granny_animation = GrannyAnimation()
        granny_animation.name = self.name.encode()
        granny_animation.duration = scene.time_step * (self.frame_count - 1)
        granny_animation.time_step = scene.time_step
        granny_animation.oversampling = 1
        granny_animation.track_group_count = 1
        granny_animation.track_groups = pointer(self.granny_track_group)
        
        self.granny_animation = pointer(granny_animation)

class MaterialExtendedData(Structure):
    _pack_ = 1
    _fields_ = [('shader_path', c_char_p), ('shader_type', c_char_p)]

class VirtualMaterial:  
    def __init__(self, name, scene: 'VirtualScene', shader_path: str | Path | None = None):
        self.name: str = name
        self.granny_material = None
        self.shader_path = "override"
        self.shader_type = "override"
        self.granny_texture = None
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
        if scene.uses_textures:
            self.make_granny_texture(scene)
        
    def set_invalid(self, scene: 'VirtualScene'):
        self.shader_path = r"shaders\invalid"
        self.shader_type = "material" if scene.corinth else "shader"
        self.to_granny_data(scene)
    
    def to_granny_data(self, scene):
        self.granny_material = GrannyMaterial()
        self.granny_material.name = self.name.encode()
        data = MaterialExtendedData(shader_path=self.shader_path.encode(), shader_type=self.shader_type.encode())
        self.granny_material.extended_data.object = cast(pointer(data), c_void_p)
        self.granny_material.extended_data.type = scene.material_extended_data_type
        self.granny_material = pointer(self.granny_material)
        
    def make_granny_texture(self, scene: 'VirtualScene'):
        if self.shader_type == "override" or not self.shader_path:
            return

        shader_path = Path(self.shader_path).with_suffix("." + self.shader_type)
        full_path = Path(scene.tags_dir, shader_path)
        if not full_path.exists():
            return
        if scene.corinth:
            with MaterialTag(path=shader_path) as shader:
                bitmap_data = shader.get_diffuse_bitmap_data_for_granny()
        else:
            with ShaderTag(path=shader_path) as shader:
                bitmap_data = shader.get_diffuse_bitmap_data_for_granny()
            
        if not bitmap_data:
            return
        
        # Create a granny texture builder instance
        width, height, stride, rgba = bitmap_data
        builder = scene.granny._begin_texture_builder(width, height)
        scene.granny._encode_image(builder, width, height, stride, 1, rgba)
        texture = scene.granny._end_texture(builder)
        texture.contents.file_name = str(full_path).encode()
        texture.contents.texture_type = 2
        self.granny_texture = texture
        self.granny_material.contents.texture = texture
        # Set up texture map
        map = GrannyMaterialMap()
        map.usage = b"diffuse"
        map.material = self.granny_material
        self.granny_material.contents.maps = pointer(map)
        self.granny_material.contents.map_count = 1

    
class VirtualMesh:
    def __init__(self, vertex_weighted: bool, scene: 'VirtualScene', bone_bindings: list[str], ob: bpy.types.Object, fp_defaults: dict, render_mesh: bool, proxies: list, props: dict, negative_scaling: bool, bones: list[str]):
        self.name = ob.data.name
        self.proxies = proxies
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
        self.materials = {}
        self.face_properties: dict = {}
        self.bone_bindings = bone_bindings
        self.vertex_weighted = vertex_weighted
        self.num_vertices = 0
        self.invalid = False
        self.granny_tri_topology = None
        # Check if a mesh already exists so we can copy its data (this will be the case in instances of shared mesh data but negative scale)
        # Transforms to account for negative scaling are done at granny level so the blender data can stay the same
        existing_mesh = scene.meshes.get((self.name, not negative_scaling))
        if existing_mesh and not existing_mesh.invalid:
            self.num_vertices = existing_mesh.num_vertices
            self.vertex_component_names = existing_mesh.vertex_component_names
            self.vertex_component_name_count = existing_mesh.vertex_component_name_count
            self.vertex_type = existing_mesh.vertex_type
            self.vertex_array = existing_mesh.vertex_array
            self.len_vertex_array = existing_mesh.len_vertex_array
            self.granny_tri_topology = deep_copy_granny_tri_topology(existing_mesh.granny_tri_topology)
            scene.granny.invert_tri_topology_winding(self.granny_tri_topology)
        else:
            self._setup(ob, scene, fp_defaults, render_mesh, props, bones)
            
            if not self.invalid:
                self.to_granny_data(scene)
                if negative_scaling:
                    scene.granny.invert_tri_topology_winding(self.granny_tri_topology)
            
        del self.positions
        del self.normals
        del self.bone_weights
        del self.bone_indices
        del self.texcoords
        del self.lighting_texcoords
        del self.vertex_colors
        del self.indices
        
    def to_granny_data(self, scene: 'VirtualScene'):
        self._granny_tri_topology(scene)
        self._granny_vertex_data(scene)
        
    def _granny_tri_topology(self, scene: 'VirtualScene'):
        indices = (c_int * len(self.indices)).from_buffer_copy(self.indices.tobytes())

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
        granny_tri_topology.index_count = len(self.indices)
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
        dtypes = [('Position', np.single, (3,)), ('Normal', np.single, (3,))]
        
        if self.bone_weights is not None:
            data.extend([self.bone_weights, self.bone_indices])
            types.extend([
                GrannyDataTypeDefinition(GrannyMemberType.granny_normal_u_int8_member.value, b"BoneWeights", None, 4),
                GrannyDataTypeDefinition(GrannyMemberType.granny_uint8_member.value, b"BoneIndices", None, 4)
            ])
            type_names.extend([b"BoneWeights", b"BoneIndices"])
            dtypes.append(('BoneWeights', np.byte, (4,)))
            dtypes.append(('BoneIndices', np.byte, (4,)))
        
        for idx, uvs in enumerate(self.texcoords):
            name = f"TextureCoordinates{idx}"
            name_encoded = name.encode()
            data.append(uvs)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, name_encoded, None, 3))
            type_names.append(name_encoded)
            dtypes.append((name, np.float32, (3,)))
            
        if self.lighting_texcoords is not None:
            data.append(self.lighting_texcoords)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"TextureCoordinateslighting", None, 3))
            type_names.append(b"lighting")
            dtypes.append((f'TextureCoordinateslighting{idx}', np.float32, (3,)))
            
        for idx, vcolors in enumerate(self.vertex_colors):
            name = f"colorSet{idx + 1}" if scene.corinth else f"DiffuseColor{idx}"
            name_encoded = name.encode()
            data.append(vcolors)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, name_encoded, None, 3))
            type_names.append(name_encoded)
            dtypes.append((name, np.float32, (3,)))

        types.append((GrannyMemberType.granny_end_member.value, None, None, 0))
        
        num_types = len(type_names)
        names_array = (c_char_p * num_types)(*type_names)
        self.vertex_component_names = cast(names_array, POINTER(c_char_p))
        self.vertex_component_name_count = num_types
        
        type_info_array = (GrannyDataTypeDefinition * (num_types + 1))(*types)
        self.vertex_type = cast(type_info_array, POINTER(GrannyDataTypeDefinition))
        
        vertex_array = np.zeros(len(self.positions), dtype=dtypes)
        for array, data_type in zip(data, dtypes):
            vertex_array[data_type[0]] = array

        vertex_byte_array = vertex_array.tobytes()

        self.len_vertex_array = len(vertex_byte_array)
        self.vertex_array = (c_ubyte * self.len_vertex_array).from_buffer_copy(vertex_byte_array)
        
    def _setup(self, ob: bpy.types.Object, scene: 'VirtualScene', fp_defaults: dict, render_mesh: bool, props: dict, bones: list[str]):
        def add_triangle_mod(ob: bpy.types.Object):
            mods = ob.modifiers
            for m in mods:
                if m.type == 'TRIANGULATE': return
                
            tri_mod = mods.new('Triangulate', 'TRIANGULATE')
            tri_mod.quad_method = scene.quad_method
            tri_mod.ngon_method = scene.ngon_method
            
        add_triangle_mod(ob)
        mesh = ob.to_mesh(preserve_all_data_layers=True, depsgraph=scene.depsgraph)
        self.name = mesh.name
        if not mesh.polygons:
            scene.warnings.append(f"Mesh data [{self.name}] of object [{ob.name}] has no faces. {ob.name} removed from geometry tree")
            self.invalid = True
            return
        
        num_materials = len(mesh.materials)
        special_mats_dict = defaultdict(list)
        for idx, mat in enumerate(mesh.materials):
            if mat is not None and (mat.nwo.has_material_properties or mat.name[0] == "+"):
                special_mats_dict[mat].append(idx)

        num_loops = len(mesh.loops)
        num_vertices = len(mesh.vertices)
        num_polygons = len(mesh.polygons)
        
        self.normals = np.empty((num_loops, 3), dtype=np.single)
        mesh.corner_normals.foreach_get("vector", self.normals.ravel())
        
        sorted_order = None
        
        vertex_positions = np.empty((num_vertices, 3), dtype=np.single)
        loop_vertex_indices = np.empty(num_loops, dtype=np.int32)
        
        mesh.vertices.foreach_get("co", vertex_positions.ravel())
        mesh.loops.foreach_get("vertex_index", loop_vertex_indices)
        
        self.positions = vertex_positions[loop_vertex_indices]
        
        def remap(i):
            return vgroup_remap.get(i, 0)
        
        if self.vertex_weighted:
            unique_bone_indices = set()
            vgroup_bone_names = {}
            for idx, vg in enumerate(ob.vertex_groups):
                vgroup_bone_names[vg.name] = idx
            bone_weights = np.zeros((num_loops, 4), dtype=np.single)
            bone_indices = np.zeros((num_loops, 4), dtype=np.int32)
            vgroup_remap = {}
            for idx, bone in enumerate(bones):
                vg_bone_index = vgroup_bone_names.get(bone)
                if vg_bone_index is not None:
                    vgroup_remap[vg_bone_index] = idx

            for loop_index, loop in enumerate(mesh.loops):
                vertex_index = loop.vertex_index
                vertex = mesh.vertices[vertex_index]
                groups = vertex.groups

                if groups:
                    weights = np.empty(len(groups), dtype=np.single)
                    indices = np.empty(len(groups), dtype=np.int32)
                    groups.foreach_get("weight", weights)
                    groups.foreach_get("group", indices)
                        
                    indices = np.vectorize(remap)(indices)

                    top_indices = np.argsort(-weights)[:4]
                    top_weights = weights[top_indices]
                    top_bone_indices = indices[top_indices]

                    if top_weights.sum() > 0:
                        top_weights /= top_weights.sum()

                    top_bone_indices[top_weights == 0] = 0
                    
                    bone_weights[loop_index] = np.pad((top_weights * 255), (0, 4 - len(top_weights)))
                    bone_indices[loop_index] = np.pad(top_bone_indices, (0, 4 - len(top_bone_indices)))

                    unique_bone_indices.update(top_bone_indices)
                    
                
            self.bone_bindings = [bones[idx] for idx in vgroup_remap.values()]
            
            max_index = max(vgroup_remap.values()) + 1
            mapping_array = np.full(max_index, -1, dtype=np.int32)
            for new_idx, old_idx in enumerate(vgroup_remap.values()):
                mapping_array[old_idx] = new_idx

            bone_indices = np.clip(mapping_array[bone_indices], 0, max_index - 1)

            self.bone_weights = bone_weights.astype(np.byte)
            self.bone_indices = bone_indices.astype(np.byte)
        
        if render_mesh:
            # We only care about writing this data if the in game mesh will have a render definition
            for idx, layer in enumerate(mesh.uv_layers):
                if len(self.texcoords) >= 4:
                    break
                
                loop_uvs = np.zeros((num_loops, 2), dtype=np.single)
                layer.uv.foreach_get("vector", loop_uvs.ravel())
                loop_uvs[:, 1] = 1-loop_uvs[:, 1]
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

        # Remove duplicate vertex data
        data = [self.positions, self.normals]
        # if self.texcoords is not None:
        #     data.extend(self.texcoords)
        # if self.vertex_colors is not None:
        #     data.extend(self.vertex_colors)

        loop_data = np.hstack(data)

        _, new_indices, face_indices = np.unique(loop_data, axis=0, return_index=True, return_inverse=True)

        self.indices = face_indices.astype(np.int32)
        new_indices = tuple(new_indices)

        self.positions = self.positions[new_indices, :]
        self.normals = self.normals[new_indices, :]

        if self.texcoords is not None:
            for idx, texcoord in enumerate(self.texcoords):
                self.texcoords[idx] = texcoord[new_indices, :]

        if self.lighting_texcoords is not None:
            self.lighting_texcoords = self.lighting_texcoords[new_indices, :]

        if self.vertex_colors is not None:
            for idx, vcolor in enumerate(self.vertex_colors):
                self.vertex_colors[idx] = vcolor[new_indices, :]

        if self.bone_weights is not None:
            self.bone_weights = self.bone_weights[new_indices, :]
            self.bone_indices = self.bone_weights[new_indices, :]

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
            unique_materials = list(dict.fromkeys([m for m in used_materials]))
            for idx, mat in enumerate(used_materials):
                virtual_mat = scene._get_material(mat, scene)
                self.materials[virtual_mat] = None
                self.groups.append((virtual_mat, unique_materials.index(mat), mat_index_counts[idx]))
        elif num_materials == 1:
            virtual_mat = scene._get_material(mesh.materials[0], scene)
            self.materials[virtual_mat] = None
            self.groups.append((virtual_mat, 0, (0, num_polygons)))
        else:
            virtual_mat = scene.materials["invalid"]
            self.materials[virtual_mat] = None
            self.groups.append((virtual_mat, 0, (0, num_polygons))) # default material
        
        self.num_indices = len(self.indices)
        self.num_vertices = len(self.positions)
        if ob.original.data.nwo.face_props or special_mats_dict:
            self.face_properties = gather_face_props(ob.original.data.nwo, mesh, num_polygons, scene, sorted_order, special_mats_dict, fp_defaults, props)
    
class VirtualNode:
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone, props: dict, region: str = None, permutation: str = None, fp_defaults: dict = None, scene: 'VirtualScene' = None, proxies = [], template_node: 'VirtualNode' = None, bones: list[str] = []):
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
            self._setup(id, scene, fp_defaults, proxies, template_node, bones)
        
    def _setup(self, id: bpy.types.Object | bpy.types.PoseBone, scene: 'VirtualScene', fp_defaults: dict, proxies: list, template_node: 'VirtualNode', bones: list[str]):
        self.name = id.name
        if isinstance(id, bpy.types.Object):
            self.selected = id.original.select_get()
            if template_node is None:
                self.matrix_world = id.original.matrix_world.copy()
                self.matrix_local = id.original.matrix_local.copy()
            else:
                self.matrix_world = template_node.matrix_world.copy()
                # self.matrix_local = IDENTITY_MATRIX
            if id.type in VALID_MESHES:
                default_bone_bindings = [self.name]
                negative_scaling = id.matrix_world.is_negative
                existing_mesh = scene.meshes.get((id.data.name, negative_scaling))
                    
                if existing_mesh:
                    self.mesh = existing_mesh
                    
                else:
                    vertex_weighted = id.vertex_groups and id.parent and id.parent.type == 'ARMATURE' and id.parent_type != "BONE" and has_armature_deform_mod(id)
                    mesh = VirtualMesh(vertex_weighted, scene, default_bone_bindings, id, fp_defaults, is_rendered(self.props), proxies, self.props, negative_scaling, bones)
                    id.to_mesh_clear()
                    self.mesh = mesh
                    self.new_mesh = True
                    
                self.bone_bindings = self.mesh.bone_bindings
                if self.mesh.vertex_weighted:
                    self.matrix_local = IDENTITY_MATRIX
                    
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
                    scene.granny._transform_vertices(self.mesh.num_vertices,
                                                    self.granny_vertex_data.vertex_type,
                                                    vertex_array,
                                                    affine3,
                                                    linear3x3,
                                                    inverse_linear3x3,
                                                    True,
                                                    False,
                                                    )
                
                self.granny_vertex_data.vertices = cast(vertex_array, POINTER(c_ubyte))
                self.granny_vertex_data.vertex_count = self.mesh.num_vertices
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
    
def granny_transform_parts(matrix_local: Matrix):
    loc = matrix_local.to_translation()
    position = (c_float * 3)(loc[0], loc[1], loc[2])
    quaternion = matrix_local.to_quaternion()
    orientation = (c_float * 4)(quaternion[1], quaternion[2], quaternion[3], quaternion[0])
    scale = matrix_local.to_scale()

    scale_shear = (c_float * 3 * 3)((scale[0], 0.0, 0.0), (0.0, scale[1], 0.0), (0.0, 0.0, scale[2]))
    
    return position, orientation, scale_shear

        
def create_extended_data(props, granny):
    granny_props = utils.get_halo_props_for_granny(props)
    if not granny_props: return
    
    ExtendedDataType = (GrannyDataTypeDefinition * (len(granny_props) + 1))()
    
    for i, key in enumerate(granny_props):
        ExtendedDataType[i] = GrannyDataTypeDefinition(
            member_type=8,
            name=key.encode()
        )
    
    ExtendedDataType[-1] = GrannyDataTypeDefinition(member_type=0)
    data = extended_data_create(granny_props)

    granny.extended_data.object = cast(pointer(data), c_void_p)
    granny.extended_data.type = ExtendedDataType
    
def extended_data_create(properties):
    fields = [(key, c_char_p) for key in properties.keys()]

    class ExtendedData(Structure):
        _pack_ = 1
        _fields_ = fields
    
    return ExtendedData(**properties)
    
class VirtualBone:
    '''Describes an blender object/bone which is a child'''
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone):
        self.name: str = id.name
        self.parent_index: int = -1
        self.node: VirtualNode = None
        self.matrix_local: Matrix = IDENTITY_MATRIX
        self.matrix_world: Matrix = IDENTITY_MATRIX
        self.props = {}
        self.granny_bone = GrannyBone()
        
    def create_bone_props(self, bone, frame_ids):
        self.props["bungie_frame_ID1"] = frame_ids[0]
        self.props["bungie_frame_ID2"] = frame_ids[1]
        self.props["bungie_object_animates"] = "1"
        self.props["bungie_object_type"] = "_connected_geometry_object_type_frame"
        
    def to_granny_data(self):
        self.granny_bone.name = self.name.encode()
        self.granny_bone.parent_index = self.parent_index
        self.granny_bone.local_transform = GrannyTransform(7, *granny_transform_parts(self.matrix_local))
        self.granny_bone.inverse_world_4x4 = self._granny_world_transform()
        if self.props:
            create_extended_data(self.props, self.granny_bone)
        
    def _granny_world_transform(self):
        inverse_matrix = self.matrix_world.inverted()
        inverse_transform = (c_float * 4 * 4)((tuple(inverse_matrix.col[0])), (tuple(inverse_matrix.col[1])), (tuple(inverse_matrix.col[2])), (tuple(inverse_matrix.col[3])))
        return inverse_transform
        
class VirtualSkeleton:
    '''Describes a list of bones'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene', node: VirtualNode):
        self.name: str = ob.name
        self.node = node
        own_bone = VirtualBone(ob)
        own_bone.node = node
        if ob.type == 'ARMATURE':
            own_bone.props = {
                    "bungie_frame_world": "1",
                    "bungie_frame_ID1": "8078",
                    "bungie_frame_ID2": "378163771",
                    "bungie_object_type": "_connected_geometry_object_type_frame",
                }
        elif own_bone.node and not own_bone.node.mesh:
            own_bone.props = own_bone.node.props
            
        own_bone.matrix_world = own_bone.node.matrix_world
        own_bone.matrix_local = IDENTITY_MATRIX
        self.skeleton_matrix_world = own_bone.matrix_world.copy()
        own_bone.to_granny_data()
        self.bones: list[VirtualBone] = [own_bone]
        self._get_bones(ob, scene)
        
    def _get_bones(self, ob, scene: 'VirtualScene'):
        if ob.type == 'ARMATURE':
            valid_bones = [pbone for pbone in ob.original.pose.bones if ob.original.data.bones[pbone.name].use_deform]
            list_bones = [pbone.name for pbone in valid_bones]
            dict_bones = {v: i for i, v in enumerate(list_bones)}
            for idx, bone in enumerate(valid_bones):
                bone: bpy.types.PoseBone
                b = VirtualBone(bone)
                frame_ids_index = scene.template_node_order.get(b.name)
                if frame_ids_index is None:
                    frame_ids_index = idx
                b.create_bone_props(bone, scene.frame_ids[frame_ids_index])
                # b.properties = utils.get_halo_props_for_granny(ob.data.bones[idx])
                b.matrix_world = self.skeleton_matrix_world @ bone.matrix
                if bone.parent:
                    # Add one to this since the root is the armature
                    b.parent_index = list_bones.index(bone.parent.name) + 1
                    b.matrix_local = utils.get_bone_matrix_local(bone)
                else:
                    b.parent_index = 0
                    b.matrix_local = IDENTITY_MATRIX
                    b.matrix_world = IDENTITY_MATRIX
                    
                b.to_granny_data()
                self.bones.append(b)
                scene.animated_bones.append(bone)
                
            child_index = 0
            for child in scene.get_immediate_children(ob):
                node = scene.add(child, *scene.object_halo_data[child], bones=list_bones)
                if not node: continue
                child_index += 1
                if not node or node.invalid: continue
                b = VirtualBone(child)
                b.node = node
                if child.type != 'MESH':
                    b.props = b.node.props
                b.matrix_world = node.matrix_world.copy()
                if child.parent_type == 'BONE':
                    # Can't just use an objects matrix_local here as this gets a matrix relative to a bone's tail
                    # the below gets the matrix relative to bone head
                    bone_index = dict_bones.get(child.parent_bone)
                    if bone_index is None:
                        scene.warnings.append(f"{child.name} is parented to non-existant bone: {child.parent_bone}. Parenting to {list_bones[0]}")
                        bone_index = 0
                    bone = valid_bones[bone_index]
                    b.matrix_local = (self.skeleton_matrix_world @ bone.matrix).inverted() @ b.matrix_world
                    b.parent_index = bone_index + 1
                else:
                    b.matrix_local = node.matrix_local.copy()
                    b.parent_index = 0
                b.to_granny_data()
                self.bones.append(b)
                self.find_children(child, scene, child_index)
                    
        else:
            self.find_children(ob, scene)
                    
    def find_children(self, ob: bpy.types.Object, scene: 'VirtualScene', parent_index=0):
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
            b.matrix_world = node.matrix_world
            b.matrix_local = node.matrix_local
            b.to_granny_data()
            self.bones.append(b)
            self.find_children(child, scene, child_index)
            
        if self.node.mesh:
            for proxy in self.node.mesh.proxies:
                node = scene.add(proxy, *scene.object_halo_data[proxy], self.node)
                if not node or node.invalid: continue
                b = VirtualBone(proxy)
                b.parent_index = parent_index
                b.node = node
                b.matrix_world = b.node.matrix_world
                b.matrix_local = b.node.matrix_local
                b.to_granny_data()
                self.bones.append(b)
    
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
    def __init__(self, asset_type: AssetType, depsgraph: bpy.types.Depsgraph, corinth: bool, tags_dir: Path, granny: Granny, export_settings, fps: int, animation_compression: str):
        self.nodes: dict[VirtualNode] = {}
        self.meshes: dict[VirtualMesh] = {}
        self.materials: dict[VirtualMaterial] = {}
        self.models: dict[VirtualModel] = {}
        self.root: VirtualNode = None
        self.uses_textures = export_settings.granny_textures
        self.quad_method = export_settings.triangulate_quad_method
        self.ngon_method = export_settings.triangulate_ngon_method
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
        self.time_step = 1.0 / fps
        self.corinth = corinth
        self.export_info: ExportInfo = None
        self.valid_bones = []
        self.frame_ids = read_frame_id_list()
        self.structure = set()
        self.design = set()
        self.bsps_with_structure = set()
        self.warnings = []
        self.animated_bones = []
        self.animations = []
        self.default_animation_compression = animation_compression
        
        self.object_parent_dict: dict[bpy.types.Object: bpy.types.Object] = {}
        self.object_halo_data: dict[bpy.types.Object: tuple[dict, str, str, list]] = {}
        self.mesh_object_map: dict[tuple[bpy.types.Mesh, bool]: list[bpy.types.Object]] = {}
        
        self.material_extended_data_type = self._create_material_extended_data_type()
        
        # Create default material
        if corinth:
            default_material = VirtualMaterial("invalid", self, r"shaders\invalid.material")
        else:
            default_material = VirtualMaterial("invalid", self, r"shaders\invalid.shader")
            
        self.materials["invalid"] = default_material

        self.template_node_order = {}
        
    def _create_material_extended_data_type(self):
        material_extended_data_type = (GrannyDataTypeDefinition * 3)(
            GrannyDataTypeDefinition(member_type=GrannyMemberType.granny_string_member, name=b"bungie_shader_path"),
            GrannyDataTypeDefinition(member_type=GrannyMemberType.granny_string_member, name=b"bungie_shader_type"),
            GrannyDataTypeDefinition(GrannyMemberType.granny_end_member.value)
        )
        
        return material_extended_data_type
    
    def _create_curve_data_type(self):
        pass
        
        
    def add(self, id: bpy.types.Object, props: dict, region: str = None, permutation: str = None, fp_defaults: dict = None, proxies: list = None, template_node: VirtualNode = None, bones: list[str] = []) -> VirtualNode:
        '''Creates a new node with the given parameters and appends it to the virtual scene'''
        node = VirtualNode(id, props, region, permutation, fp_defaults, self, proxies, template_node, bones)
        if not node.invalid:
            self.nodes[node.name] = node
            if node.new_mesh:
                # This is a tuple containing whether the object has a negative scale. This because we need to create seperate mesh data for negatively scaled objects
                self.meshes[(node.mesh.name, id.matrix_world.is_negative)] = node.mesh
            
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
            
    def add_animation(self, action: bpy.types.Action):
        animation = VirtualAnimation(action, self)
        if animation.granny_animation:
            self.animations.append(animation)
        else:
            del animation
        
    def _get_material(self, material: bpy.types.Material, scene: 'VirtualScene'):
        if material is None:
            return scene.materials['invalid']
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
    
    def has_instance_proxy(self, node: VirtualNode):
        return (self.asset_type.supports_bsp and 
                node and 
                node.mesh and 
                node.props.get("bungie_mesh_type") == "_connected_geometry_mesh_type_poop")
        
    def add_automatic_structure(self):
        if self.structure == self.bsps_with_structure:
            return
        no_bsp_structure = self.structure.difference(self.bsps_with_structure)
                
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
            

def gather_face_props(mesh_props: NWO_MeshPropertiesGroup, mesh: bpy.types.Mesh, num_faces: int, scene: VirtualScene, sorted_order, special_mats_dict: dict, fp_defaults: dict, props: dict) -> dict:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    
    face_properties = {}
    side_layers = {}
    
    for face_prop in mesh_props.face_props:
        if props.get("bungie_face_mode") is None:
            if face_prop.render_only_override:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.render_only.value)
            elif face_prop.collision_only_override:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.collision_only.value)
            elif face_prop.sphere_collision_only_override:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.sphere_collision_only.value)
            elif face_prop.lightmap_only_override:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.lightmap_only.value)
            elif face_prop.breakable_override:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, fp_defaults["bungie_face_mode"], np.uint8))).update(bm, face_prop.layer_name, FaceMode.breakable.value)
        
        if props.get("bungie_face_sides") is None:
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
            
        if face_prop.face_draw_distance_override and props.get("bungie_face_draw_distance") is None:
            match face_prop.face_draw_distance:
                case '_connected_geometry_face_draw_distance_detail_mid':
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.full(num_faces, fp_defaults["bungie_face_draw_distance"], np.uint8))).update(bm, face_prop.layer_name, FaceDrawDistance.detail_mid.value)
                case '_connected_geometry_face_draw_distance_detail_close':
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.full(num_faces, fp_defaults["bungie_face_draw_distance"], np.uint8))).update(bm, face_prop.layer_name, FaceDrawDistance.detail_close.value)

        if face_prop.face_global_material_override and props.get("bungie_face_global_material") is None:
            gmv = 0
            default_global_material = fp_defaults["bungie_face_global_material"]
            if default_global_material in scene.global_materials_set:
                gmv = scene.global_materials.index(fp_defaults["bungie_face_global_material"])
            face_properties.setdefault("bungie_face_global_material", FaceSet(np.full(num_faces, gmv, np.int32))).update(bm, face_prop.layer_name, scene.global_materials.index(face_prop.face_global_material.strip().replace(' ', "_")))
        if scene.asset_type.supports_regions and face_prop.region_name_override and props.get("bungie_face_region") is None:
            rv = 0
            default_region = fp_defaults["bungie_face_region"]
            if default_region in scene.regions_set:
                rv = scene.regions.index(fp_defaults["bungie_face_region"])
            face_properties.setdefault("bungie_face_region", FaceSet(np.full(num_faces, rv, np.int32))).update(bm, face_prop.layer_name, scene.regions.index(face_prop.region_name))
            
        if face_prop.ladder_override and props.get("bungie_ladder") is None:
            face_properties.setdefault("bungie_ladder", FaceSet(np.full(num_faces, fp_defaults["bungie_ladder"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.slip_surface_override and props.get("bungie_slip_surface") is None:
            face_properties.setdefault("bungie_slip_surface", FaceSet(np.full(num_faces, fp_defaults["bungie_slip_surface"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.decal_offset_override and props.get("bungie_decal_offset") is None:
            face_properties.setdefault("bungie_decal_offset", FaceSet(np.full(num_faces, fp_defaults["bungie_decal_offset"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_shadow_override and props.get("bungie_no_shadow") is None:
            face_properties.setdefault("bungie_no_shadow", FaceSet(np.full(num_faces, fp_defaults["bungie_no_shadow"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_pvs_override and props.get("bungie_invisible_to_pvs") is None:
            face_properties.setdefault("bungie_invisible_to_pvs", FaceSet(np.full(num_faces, fp_defaults["bungie_invisible_to_pvs"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.no_lightmap_override and props.get("bungie_no_lightmap") is None:
            face_properties.setdefault("bungie_no_lightmap", FaceSet(np.full(num_faces, fp_defaults["bungie_no_lightmap"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.precise_position_override and props.get("bungie_precise_position") is None:
            face_properties.setdefault("bungie_precise_position", FaceSet(np.full(num_faces, fp_defaults["bungie_precise_position"], np.uint8))).update(bm, face_prop.layer_name, 1)
        if face_prop.mesh_tessellation_density_override and props.get("_connected_geometry_mesh_tessellation_density_4x") is None:
            match face_prop.mesh_tessellation_density:
                case '_connected_geometry_mesh_tessellation_density_4x':
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, fp_defaults["bungie_mesh_tessellation_density"], np.uint8))).update(bm, face_prop.layer_name, 1)
                case '_connected_geometry_mesh_tessellation_density_9x':
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, fp_defaults["bungie_mesh_tessellation_density"], np.uint8))).update(bm, face_prop.layer_name, 2)
                case '_connected_geometry_mesh_tessellation_density_36x':
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, fp_defaults["bungie_mesh_tessellation_density"], np.uint8))).update(bm, face_prop.layer_name, 3)
            
        # Lightmap Props
        if face_prop.lightmap_additive_transparency_override and props.get("bungie_lightmap_additive_transparency") is None:
            face_properties.setdefault("bungie_lightmap_additive_transparency", FaceSet(np.full((num_faces, 4), fp_defaults["bungie_lightmap_additive_transparency"], np.single))).update(bm, face_prop.layer_name, utils.color_4p(face_prop.lightmap_additive_transparency))
        if face_prop.lightmap_resolution_scale_override and props.get("bungie_lightmap_additive_transparency") is None:
            # face_properties.setdefault("bungie_lightmap_ignore_default_resolution_scale", FaceSet(np.zeros(num_faces, np.int32))).update(bm, face_prop.layer_name, 1) # TODO needs to be own settable prop
            face_properties.setdefault("bungie_lightmap_resolution_scale", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_resolution_scale"], np.uint8))).update(bm, face_prop.layer_name, face_prop.lightmap_resolution_scale)
        if face_prop.lightmap_type_override and props.get("bungie_lightmap_type") is None:
            if face_prop.lightmap_type == '_connected_geometry_lightmap_type_per_vertex':
                face_properties.setdefault("bungie_lightmap_type", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_type"], np.uint8))).update(bm, face_prop.layer_name, LightmapType.per_vertex.value)
            else:
                face_properties.setdefault("bungie_lightmap_type", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_type"], np.uint8))).update(bm, face_prop.layer_name, LightmapType.per_pixel.value)
        if face_prop.lightmap_translucency_tint_color_override and props.get("bungie_lightmap_translucency_tint_color") is None:
            face_properties.setdefault("bungie_lightmap_translucency_tint_color", FaceSet(np.full((num_faces, 4), fp_defaults["bungie_lightmap_translucency_tint_color"], np.single))).update(bm, face_prop.layer_name, utils.color_4p(face_prop.lightmap_translucency_tint_color))
        if face_prop.lightmap_lighting_from_both_sides_override and props.get("bungie_lightmap_lighting_from_both_sides") is None:
            face_properties.setdefault("bungie_lightmap_lighting_from_both_sides", FaceSet(np.full(num_faces, fp_defaults["bungie_lightmap_lighting_from_both_sides"], np.uint8))).update(bm, face_prop.layer_name, 1)
        
        # Emissives
        if face_prop.emissive_override and props.get("bungie_lighting_emissive_power") is None:
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
        if material.name.lower().startswith('+seamsealer') and props.get("bungie_face_type") is None:
            face_properties.setdefault("bungie_face_type", FaceSet(np.zeros(num_faces, np.uint8))).update_from_material(bm, material_indexes, FaceType.seam_sealer.value)
        elif material.name.lower().startswith('+sky'):
            if props.get("bungie_face_type") is None:
                face_properties.setdefault("bungie_face_type", FaceSet(np.zeros(num_faces, np.uint8))).update_from_material(bm, material_indexes, FaceType.sky.value)
            if len(material.name) > 4 and material.name[4].isdigit():
                sky_index = int(material.name[4])
                if sky_index > 0 and props.get("bungie_sky_permutation_index") is None:
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
    inverse_linear3x3 = (c_float * 9)(*[f for row in matrix3x3.inverted(Matrix.Identity(4).to_3x3()) for f in row])
    
    return affine3, linear3x3, inverse_linear3x3

def is_rendered(props: dict) -> bool:
    mesh_type = props.get("bungie_mesh_type", None)
    if mesh_type is None:
        # returning true since the absence of a mesh type means the game will use the default mesh type - _connected_geometry_mesh_type_default
        return True 
    
    return mesh_type in RENDER_MESH_TYPES

def deep_copy_granny_tri_topology(original):
    copy = GrannyTriTopology()
    copy.group_count = original.contents.group_count
    copy.index_count = original.contents.index_count
    copy.tri_annotation_set_count = original.contents.tri_annotation_set_count

    if original.contents.groups:
        num_groups = original.contents.group_count
        groups = (GrannyTriMaterialGroup * num_groups)()
        memmove(groups, original.contents.groups, sizeof(GrannyTriMaterialGroup) * num_groups)
        copy.groups = cast(groups, POINTER(GrannyTriMaterialGroup))

    if original.contents.indices:
        indices = (c_int * original.contents.index_count)()
        memmove(indices, original.contents.indices, sizeof(c_int) * original.contents.index_count)
        copy.indices = cast(indices, POINTER(c_int))

    if original.contents.tri_annotation_sets:
        num_sets = original.contents.tri_annotation_set_count
        tri_annotation_sets = (GrannyTriAnnotationSet * num_sets)()
        
        for i in range(num_sets):
            tri_annotation_sets[i].name = create_string_buffer(original.contents.tri_annotation_sets[i].name).raw
            tri_annotation_sets[i].indices_map_from_tri_to_annotation = original.contents.tri_annotation_sets[i].indices_map_from_tri_to_annotation
            tri_annotation_sets[i].tri_annotation_type = original.contents.tri_annotation_sets[i].tri_annotation_type
            tri_annotation_sets[i].tri_annotation_count = original.contents.tri_annotation_sets[i].tri_annotation_count

            annotation_size = original.contents.tri_annotation_sets[i].tri_annotation_count
            annotations = (c_ubyte * annotation_size)()
            memmove(annotations, original.contents.tri_annotation_sets[i].tri_annotations, sizeof(c_ubyte) * annotation_size)
            tri_annotation_sets[i].tri_annotations = cast(annotations, POINTER(c_ubyte))
        
        copy.tri_annotation_sets = cast(tri_annotation_sets, POINTER(GrannyTriAnnotationSet))

    return pointer(copy)
