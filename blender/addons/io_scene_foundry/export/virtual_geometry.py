'''Classes to store intermediate geometry data to be passed to granny files'''

from collections import defaultdict
import csv
from ctypes import Array, Structure, c_char_p, c_float, c_int, POINTER, c_int16, c_ubyte, c_void_p, cast, create_string_buffer, memmove, pointer, sizeof
import logging
from math import degrees, inf, nextafter
from pathlib import Path
import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
import numpy as np

from ..tools.light_exporter import calc_attenutation

from ..managed_blam.material import MaterialTag

from ..managed_blam.shader import ShaderTag
from ..managed_blam.shader_decal import ShaderDecalTag

from ..granny.formats import GrannyAnimation, GrannyBone, GrannyCurveDataDaKeyframes32f, GrannyDataTypeDefinition, GrannyMaterial, GrannyMaterialMap, GrannyMemberType, GrannyMorphTarget, GrannyTrackGroup, GrannyTransform, GrannyTransformTrack, GrannyTriAnnotationSet, GrannyTriMaterialGroup, GrannyTriTopology, GrannyVectorTrack, GrannyVertexData
from ..granny import Granny

from .export_info import AdditionalCompression, ExportInfo, FaceDrawDistance, FaceMode, FaceSides, FaceType, LightmapType, MeshTessellationDensity, MeshType, ObjectType, PoopCollisionType

from ..props.mesh import NWO_MeshPropertiesGroup

from .. import utils

from ..tools.asset_types import AssetType

from .cinematic import Actor, Frame

from ..constants import IDENTITY_MATRIX, VALID_MESHES, WU_SCALAR
NORMAL_FIX_MATRIX = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
logging.basicConfig(level=logging.DEBUG)


face_prop_defaults = {
    "bungie_face_region": 0,
    "bungie_face_global_material": 0,
    "bungie_face_type": 0,
    "bungie_face_mode": 0,
    "bungie_face_sides": 0,
    "bungie_mesh_poop_collision_type": 0,
    "bungie_mesh_type": 3,
    "bungie_face_draw_distance": 0,
    "bungie_ladder": 0,
    "bungie_slip_surface": 0,
    "bungie_decal_offset": 0,
    "bungie_no_shadow": 0,
    "bungie_invisible_to_pvs": 0,
    "bungie_no_lightmap": 0,
    "bungie_precise_position": 0,
    "bungie_mesh_tessellation_density": 0,
    "bungie_lightmap_ignore_default_resolution_scale": 0,
    "bungie_lightmap_additive_transparency": (0, 0, 0),
    "bungie_lightmap_resolution_scale": 3,
    "bungie_lightmap_type": 0,
    "bungie_lightmap_translucency_tint_color": (0, 0, 0),
    "bungie_lightmap_lighting_from_both_sides": 0,
    "bungie_lightmap_transparency_override": 0,
    "bungie_lightmap_analytical_bounce_modifier": 1.0,
    "bungie_lightmap_general_bounce_modifier": 1.0,
    "bungie_lightmap_chart_group": 0,
    "bungie_lighting_emissive_power": 0.0,
    "bungie_lighting_emissive_color": (0, 0, 0, 0),
    "bungie_lighting_emissive_per_unit": 0,
    "bungie_lighting_emissive_quality": 1.0,
    "bungie_lighting_use_shader_gel": 0,
    "bungie_lighting_bounce_ratio": 1.0,
    "bungie_lighting_attenuation_enabled": 0,
    "bungie_lighting_attenuation_cutoff": 0.0,
    "bungie_lighting_attenuation_falloff": 0.0,
    "bungie_lighting_emissive_focus": 0.0,
}

# TODO
# default invalid shader / default water shader
# Look into lighting_info failing to open

DESIGN_MESH_TYPES = {
    MeshType.planar_fog_volume.value,
    MeshType.boundary_surface.value,
    MeshType.water_physics_volume.value,
    MeshType.poop_rain_blocker.value,
    MeshType.poop_vertical_rain_sheet.value
}

FACE_PROP_TYPES = {
    MeshType.default.value,
    MeshType.poop.value,
    MeshType.collision.value,
    MeshType.poop_collision.value,
    MeshType.object_instance.value,
    MeshType.water_surface.value,
}

COLLISION_FACE_MODES = (
    FaceMode.normal.value,
    FaceMode.collision_only.value,
    FaceMode.sphere_collision_only.value,
    FaceMode.breakable.value,
)

def read_frame_id_list() -> list:
    filepath = Path(utils.addon_root(), "export", "frameidlist.csv")
    frame_ids = []
    with filepath.open(mode="r") as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        frame_ids = [row for row in csv_reader]

    return frame_ids

class VirtualShotAnimation:
    def __init__(self, animation_name, granny_track_group, granny_animation, index: int, is_pca):
        self.name = animation_name
        self.granny_track_group = granny_track_group
        self.granny_event_track_groups = None
        self.granny_animation = granny_animation
        self.is_pca = is_pca
        self.gr2_path = None
        self.shot_index = index
        
class VirtualShotActor:
    def __init__(self, actor: Actor, scene: 'VirtualScene'):
        self.name = actor.name
        self.name_encoded = actor.name.encode()
        self.ob = actor.ob
        self.actor = actor
        self.bones = None
        self.in_scope = scene.cinematic_scope != 'CAMERA' and (not scene.selected_cinematic_objects_only or actor.ob in scene.selected_actors)
        model = scene.models.get(actor.ob)
        if model is not None:
            skeleton = model.skeleton
            if skeleton is not None:
                self.bones = skeleton.animated_bones
                
        self.positions = defaultdict(list)
        self.orientations = defaultdict(list)
        self.scales = defaultdict(list)

class VirtualShot:
    def __init__(self,  frame_start: int, frame_end: int, actors: list[Actor], camera: bpy.types.Object, index, scene: 'VirtualScene', shape_key_objects=[], in_scope=True):
        self.shot_actors = [VirtualShotActor(actor, scene) for actor in actors]
        self.camera = camera
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.frame_count = frame_end - frame_start + 1
        self.frames: list[Frame] = []
        self.index = index
        self.actor_animation = {}
        self.shot_index = index
        self.sounds = []
        self.effects = []
        self.scripts = []
        self.in_scope = in_scope
    
    def perform(self, scene: 'VirtualScene'):
        if scene.cinematic_scope != 'OBJECT' and self.in_scope:
            for frame in range(self.frame_start, self.frame_end + 1):
                scene.context.scene.frame_set(frame)
                # Camera Animation
                self.frames.append(Frame(self.camera, scene.corinth))
                # Bone Animation
                for shot_actor in self.shot_actors:
                    if not shot_actor.in_scope:
                        continue
                    bone_inverse_matrices = {}
                    for bone in shot_actor.bones:
                        if bone.parent:
                            matrix_world = scene.rotation_matrix @ bone.ob.matrix_world @ bone.pbone.matrix
                            bone_inverse_matrices[bone.pbone] = matrix_world.inverted_safe()
                            matrix = bone_inverse_matrices[bone.parent] @ matrix_world
                        else:
                            matrix = scene.rotation_matrix @ bone.ob.matrix_world @ bone.pbone.matrix
                            bone_inverse_matrices[bone.pbone] = matrix.inverted_safe()

                        loc, rot, sca = matrix.decompose()
                        position = (c_float * 3)(loc.x, loc.y, loc.z)
                        orientation = (c_float * 4)(rot.x, rot.y, rot.z, rot.w)
                        scale_shear = (c_float * 9)(sca.x, 0.0, 0.0, 0.0, sca.y, 0.0, 0.0, 0.0, sca.z)
                        shot_actor.positions[bone].extend(position)
                        shot_actor.orientations[bone].extend(orientation)
                        shot_actor.scales[bone].extend(scale_shear)
                
        frame_total = self.frame_count - 1
                
        for shot_actor in self.shot_actors:
            if shot_actor.in_scope:
                tracks = []
                for bone in shot_actor.bones:
                    tracks.append((c_float * (self.frame_count * 3))(*shot_actor.positions[bone]))
                    tracks.append((c_float * (self.frame_count * 4))(*shot_actor.orientations[bone]))
                    tracks.append((c_float * (self.frame_count * 9))(*shot_actor.scales[bone]))
                    
                granny_tracks = []
                for bone_idx, i in enumerate(range(0, len(tracks), 3)):
                    granny_track = GrannyTransformTrack()
                    granny_track.name = shot_actor.bones[bone_idx].pbone.name.encode()
                    
                    builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 3, self.frame_count)
                    scene.granny.push_control_array(builder, tracks[i])
                    position_curve = scene.granny.end_curve(builder)
                    
                    builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 4, self.frame_count)
                    scene.granny.push_control_array(builder, tracks[i + 1])
                    orientation_curve = scene.granny.end_curve(builder)
                    
                    builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 9, self.frame_count)
                    scene.granny.push_control_array(builder, tracks[i + 2])
                    scale_curve = scene.granny.end_curve(builder)
                    
                    granny_track.position_curve = position_curve.contents
                    granny_track.orientation_curve = orientation_curve.contents
                    granny_track.scale_shear_curve = scale_curve.contents

                    del position_curve
                    del orientation_curve
                    del scale_curve

                    granny_tracks.append(granny_track)
                    
                granny_track = GrannyTransformTrack()
                granny_track.name = shot_actor.name_encoded
                arm_tracks = []
                loc, rot, sca = IDENTITY_MATRIX.decompose()
                positions = []
                orientations = []
                scales = []
                for frame in range(self.frame_count):
                    position = (c_float * 3)(0, 0, 0)
                    orientation = (c_float * 4)(0, 0, 0, 1)
                    scale_shear = (c_float * 9)(1, 0.0, 0.0, 0.0, 1, 0.0, 0.0, 0.0, 1)
                    positions.extend(position)
                    orientations.extend(orientation)
                    scales.extend(scale_shear)

                arm_tracks.append((c_float * (self.frame_count * 3))(*positions))
                arm_tracks.append((c_float * (self.frame_count * 4))(*orientations))
                arm_tracks.append((c_float * (self.frame_count * 9))(*scales))

                builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 3, self.frame_count)
                scene.granny.push_control_array(builder, arm_tracks[0])
                position_curve = scene.granny.end_curve(builder)
                
                builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 4, self.frame_count)
                scene.granny.push_control_array(builder, arm_tracks[1])
                orientation_curve = scene.granny.end_curve(builder)
                
                builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 9, self.frame_count)
                scene.granny.push_control_array(builder, arm_tracks[2])
                scale_curve = scene.granny.end_curve(builder)

                granny_track.position_curve = position_curve.contents
                granny_track.orientation_curve = orientation_curve.contents
                granny_track.scale_shear_curve = scale_curve.contents

                granny_tracks.append(granny_track)

                granny_tracks.sort(key=lambda track: track.name)
                granny_transform_tracks = (GrannyTransformTrack * len(granny_tracks))(*granny_tracks)
                    
                granny_track_group = GrannyTrackGroup()
                granny_track_group.name = shot_actor.name_encoded
                granny_track_group.transform_track_count = len(granny_tracks)
                granny_track_group.transform_tracks = granny_transform_tracks
                granny_track_group.flags = 2
                ptr_granny_track_group = pointer(granny_track_group)
                
                granny_animation = GrannyAnimation()
                animation_name = f"{shot_actor.name}_{self.index + 1}"
                granny_animation.name = animation_name.encode()
                granny_animation.duration = scene.time_step * frame_total + 0.00001
                granny_animation.time_step = scene.time_step
                granny_animation.oversampling = 1
                granny_animation.track_group_count = 1
                granny_animation.track_groups = pointer(ptr_granny_track_group)
                animation = VirtualShotAnimation(animation_name, ptr_granny_track_group, pointer(granny_animation), self.index, False)
                self.actor_animation[shot_actor] = animation
            else:
                animation_name = f"{shot_actor.name}_{self.index + 1}"
                animation = VirtualShotAnimation(animation_name, None, None, self.index, False)
                self.actor_animation[shot_actor] = animation
                
vector_event_types = {
    '_connected_geometry_animation_event_type_ik_active',
    '_connected_geometry_animation_event_type_ik_passive',
    '_connected_geometry_animation_event_type_wrinkle_map',
    '_connected_geometry_animation_event_type_object_function'
}

class VectorEvent:
    def __init__(self, name: str, event, effect_name: str):
        self.name = name
        self.event = event
        self.effect_name = effect_name
        self.effect_data: list[float] = []
        
class VectorTrack:
    def __init__(self, granny_vector_track, bone_name: c_char_p):
        self.granny_vector_track = granny_vector_track
        self.bone_name = bone_name
            
class VirtualAnimation:
    def __init__(self, animation, scene: 'VirtualScene', sample: bool, animation_controls=[], shape_key_objects=[], vector_events=[]):
        self.name = animation.name
        self.anim = animation
        if scene.default_animation_compression != "Automatic" and animation.compression == "Default":
            self.compression = scene.default_animation_compression
        else:
            self.compression = animation.compression
            
        self.animation_type = animation.animation_type
        self.movement = animation.animation_movement_data
        self.space = animation.animation_space
        self.overlay = animation.animation_type == 'overlay'
        self.pose_overlay = False # Now calculating this rather than this being user defined
        
        self.morph_target_data = []
        self.is_pca = False
        
        self.frame_count: int = animation.frame_end - animation.frame_start + 1
        self.frame_range: tuple[int, int] = (animation.frame_start, animation.frame_end)
        self.granny_animation = None
        self.granny_track_group = None
        self.granny_event_track_groups = []
        
        self.granny_morph_targets_counts = {}
        self.granny_morph_targets = {}
        
        self.nodes = []
        self.suspension = False
        self.suspension_marker = None
        self.suspension_contact_marker = None
        self.suspension_extension_depth = 0.0
        self.suspension_compression_depth = 0.0
        self.suspension_destroyed_contact_marker = None
        self.suspension_destroyed_extension_depth = 0.0
        self.suspension_destroyed_compression_depth = 0.0
        self.suspension_destroyed_region_name = ""
        
        uses_suspension = not scene.disable_automatic_suspension_computation and utils.tokenise(self.name)[0] == "suspension"
        if uses_suspension:
            if not animation.suspension_marker:
                scene.warnings.append(f"Suspension Point not set for {animation.name}. Cannot automatically calculate suspension extension and compression points")
            if not animation.suspension_contact_marker:
                scene.warnings.append(f"Suspension Contact Point not set for {animation.name}. Cannot automatically calculate suspension extension and compression points")
                
            if animation.suspension_marker is not None and animation.suspension_contact_marker is not None:
                self.suspension = True
                self.suspension_marker = animation.suspension_marker
                self.suspension_contact_marker = animation.suspension_contact_marker
                if animation.suspension_destroyed_region_name.strip():
                    self.suspension_destroyed_region_name = animation.suspension_destroyed_region_name
                    if animation.suspension_destroyed_contact_marker is None:
                        self.suspension_destroyed_contact_marker = animation.suspension_contact_marker
                    else:
                        self.suspension_destroyed_contact_marker = animation.suspension_destroyed_contact_marker

        if sample:
            self.create_track_group(scene.skeleton_model.skeleton.animated_bones + animation_controls, scene, shape_key_objects, vector_events)
            self.to_granny_animation(scene)
            
    def create_vector_track_groups(self, scene: 'VirtualScene', vector_events: list[VectorEvent]):
        # Vector events
        for event in vector_events:
            granny_vector_track = GrannyVectorTrack()
            granny_vector_track.name = event.effect_name.encode()
            granny_vector_track.track_key = 0
            granny_vector_track.dimension = 1
            # builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 1, len(event.effect_data))
            # scene.granny.push_control_array(builder, (c_float * len(event.effect_data))(*event.effect_data))
            # vector_curve = scene.granny.end_curve(builder)
            # granny_vector_track.value_curve = vector_curve.contents
            # del vector_curve
            
            # Creating the curve manually. granny.push_control_array seems to build a vector float array with the first two values corrupted
            curve_data = GrannyCurveDataDaKeyframes32f()
            curve_data.dimension = 1
            curve_data.control_count = len(event.effect_data)
            curve_data.controls = (c_float * len(event.effect_data))(*event.effect_data)
            granny_vector_track.value_curve.curve_data.type = scene.granny.keyframe_type
            granny_vector_track.value_curve.curve_data.object = cast(pointer(curve_data), c_void_p)
            
            granny_track_group = GrannyTrackGroup()
            granny_track_group.name = event.name.encode()
            granny_track_group.vector_track_count = 1
            granny_track_group.vector_tracks = pointer(granny_vector_track)
            granny_track_group.flags = 2
            self.granny_event_track_groups.append(pointer(granny_track_group))
            scene.vector_tracks.append(VectorTrack(granny_vector_track, event.name.encode()))
        
    def create_track_group(self, bones: list['AnimatedBone'], scene: 'VirtualScene', shape_key_objects, vector_events: list[VectorEvent]):
        positions = defaultdict(list)
        orientations = defaultdict(list)
        scales = defaultdict(list)
        tracks = []
        failed_pose_overlay = False
        pose_overlay_frame_data = defaultdict(list)
        # scale_matrix = Matrix.Diagonal(scene.armature_matrix.to_scale()).to_4x4()
        morph_target_datas = defaultdict(list)
        shape_key_data = {}
        for ob in shape_key_objects:
            node = scene.nodes.get(ob)
            if node is not None:
                shape_key_data[ob] = node
                self.nodes.append(node)
                
        if shape_key_data:
            self.is_pca = True
        
        first_frame = True
        suspension_extension_frame = False
        suspension_reference_height = 0.0
        suspension_extension_height = 0.0
        suspension_compression_height = 0.0
        suspension_destroyed_extension_height = 0.0
        suspension_destroyed_compression_height = 0.0
        
        for frame in range(self.frame_range[0], self.frame_range[1] + 1):
            scene.context.scene.frame_set(frame)
            
            # suspension calcs
            if self.suspension:
                if first_frame:
                    scene.atten_scalar
                    suspension_reference_height = self.suspension_marker.matrix_world.translation.z
                    suspension_extension_frame = True
                elif suspension_extension_frame:
                    suspension_extension_height = self.suspension_contact_marker.matrix_world.translation.z
                    if self.suspension_destroyed_region_name:
                        suspension_destroyed_extension_height = self.suspension_destroyed_contact_marker.matrix_world.translation.z
                    suspension_extension_frame = False
                elif frame == self.frame_range[1]:
                    suspension_compression_height = self.suspension_contact_marker.matrix_world.translation.z
                
                    self.suspension_extension_depth = (suspension_reference_height - suspension_extension_height) * scene.unit_factor * WU_SCALAR
                    self.suspension_compression_depth = (suspension_reference_height - suspension_compression_height) * scene.unit_factor * WU_SCALAR
                    
                    if self.suspension_destroyed_region_name:
                        suspension_destroyed_compression_height = self.suspension_destroyed_contact_marker.matrix_world.translation.z
                            
                        self.suspension_destroyed_extension_depth = (suspension_reference_height - suspension_destroyed_extension_height) * scene.unit_factor * WU_SCALAR
                        self.suspension_destroyed_compression_depth = (suspension_reference_height - suspension_destroyed_compression_height) * scene.unit_factor * WU_SCALAR
 
            bone_inverse_matrices = {}
            for bone in bones:
                if bone.is_object:
                    matrix = scene.rotation_matrix @ bone.pbone.matrix_world
                elif bone.parent:
                    matrix_world = scene.rotation_matrix @ bone.ob.matrix_world @ bone.pbone.matrix
                    bone_inverse_matrices[bone.pbone] = matrix_world.inverted_safe()
                    matrix = bone_inverse_matrices[bone.parent] @ matrix_world    
                        
                else:
                    matrix = scene.rotation_matrix @ bone.ob.matrix_world @ bone.pbone.matrix
                    bone_inverse_matrices[bone.pbone] = matrix.inverted_safe()

                loc, rot, sca = matrix.decompose()
                
                if self.overlay and bone.is_aim_bone and not first_frame:
                    pose_overlay_frame_data[bone.name].append(tuple(rot.to_euler('XYZ')))
                
                position = (c_float * 3)(loc.x, loc.y, loc.z)
                orientation = (c_float * 4)(rot.x, rot.y, rot.z, rot.w)
                scale_shear = (c_float * 9)(sca.x, 0.0, 0.0, 0.0, sca.y, 0.0, 0.0, 0.0, sca.z)
                positions[bone].extend(position)
                orientations[bone].extend(orientation)
                scales[bone].extend(scale_shear)
                
            first_frame = False
                
            # TODO Get vector track info for wrinkle_maps, IK events, and object_functions
            for event in vector_events:
                event.effect_data.append(event.event.event_value)
            
            if shape_key_data:
                for ob, node in shape_key_data.items():
                    morph_target_datas[node].append(VirtualMorphTargetData(ob, scene, node))
            
        self.create_vector_track_groups(scene, vector_events)
            
        if self.overlay and pose_overlay_frame_data:
            frame_data = zip(*pose_overlay_frame_data.values())
            data_map = defaultdict(list)
            for idx, data in enumerate(frame_data):
                data_map[data].append(idx)
            
            duplicate_data = {key: indexes for key, indexes in data_map.items() if len(indexes) > 1}
            
            if len(duplicate_data) != len(data_map):
                # This must be a pose overlay if aim bones don't have same rotation on every frame
                # Even if duplicate frame data is found, keep this as pose overlay so the user is also warned of the issue by Tool
                self.pose_overlay = True
                if duplicate_data:
                    scene.warnings.append(f"Pose overlay animation [{self.name}] has duplicate frames and may fail pose computation. Details below:")
                    for rotation, indexes in duplicate_data.items():
                        frames = [self.anim.frame_start + i + 1 for i in indexes]
                        rotation_with_names = {tuple(pose_overlay_frame_data)[idx]: tuple(degrees(r) for r in rot) for (idx, rot) in enumerate(rotation)}
                        scene.warnings.append(f"--- XYZ rotation {rotation_with_names} occurs at frames {frames}")

        for bone in bones:
            tracks.append((c_float * (self.frame_count * 3))(*positions[bone]))
            tracks.append((c_float * (self.frame_count * 4))(*orientations[bone]))
            tracks.append((c_float * (self.frame_count * 9))(*scales[bone]))
            
        granny_tracks = []
        for bone_idx, i in enumerate(range(0, len(tracks), 3)):
            granny_track = GrannyTransformTrack()
            granny_track.name = bones[bone_idx].pbone.name.encode()
            
            builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 3, self.frame_count)
            scene.granny.push_control_array(builder, tracks[i])
            position_curve = scene.granny.end_curve(builder)
            
            builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 4, self.frame_count)
            scene.granny.push_control_array(builder, tracks[i + 1])
            orientation_curve = scene.granny.end_curve(builder)
            
            builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 9, self.frame_count)
            scene.granny.push_control_array(builder, tracks[i + 2])
            scale_curve = scene.granny.end_curve(builder)
            
            granny_track.position_curve = position_curve.contents
            granny_track.orientation_curve = orientation_curve.contents
            granny_track.scale_shear_curve = scale_curve.contents

            del position_curve
            del orientation_curve
            del scale_curve

            granny_tracks.append(granny_track)


        granny_track = GrannyTransformTrack()
        granny_track.name = scene.skeleton_node.name.encode()
        arm_tracks = []
        loc, rot, sca = IDENTITY_MATRIX.decompose()
        positions = []
        orientations = []
        scales = []
        for frame in range(self.frame_count):
            position = (c_float * 3)(0, 0, 0)
            orientation = (c_float * 4)(0, 0, 0, 1)
            scale_shear = (c_float * 9)(1, 0.0, 0.0, 0.0, 1, 0.0, 0.0, 0.0, 1)
            positions.extend(position)
            orientations.extend(orientation)
            scales.extend(scale_shear)

        arm_tracks.append((c_float * (self.frame_count * 3))(*positions))
        arm_tracks.append((c_float * (self.frame_count * 4))(*orientations))
        arm_tracks.append((c_float * (self.frame_count * 9))(*scales))

        builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 3, self.frame_count)
        scene.granny.push_control_array(builder, arm_tracks[0])
        position_curve = scene.granny.end_curve(builder)
        
        builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 4, self.frame_count)
        scene.granny.push_control_array(builder, arm_tracks[1])
        orientation_curve = scene.granny.end_curve(builder)
        
        builder = scene.granny.begin_curve(scene.granny.keyframe_type, 0, 9, self.frame_count)
        scene.granny.push_control_array(builder, arm_tracks[2])
        scale_curve = scene.granny.end_curve(builder)

        granny_track.position_curve = position_curve.contents
        granny_track.orientation_curve = orientation_curve.contents
        granny_track.scale_shear_curve = scale_curve.contents

        # del position_curve
        # del orientation_curve
        # del scale_curve

        granny_tracks.append(granny_track)

        granny_tracks.sort(key=lambda track: track.name)
        granny_transform_tracks = (GrannyTransformTrack * len(granny_tracks))(*granny_tracks)
            
        granny_track_group = GrannyTrackGroup()
        granny_track_group.name = scene.skeleton_node.name.encode()
        granny_track_group.transform_track_count = len(granny_tracks)
        granny_track_group.transform_tracks = granny_transform_tracks
        granny_track_group.flags = 2
        self.granny_track_group = pointer(granny_track_group)
        # self.granny_track_group = scene.granny.end_track_group(group_builder)
        
        for node, data in morph_target_datas.items():
            morphs = [morph.granny_morph_target for morph in data]
            self.granny_morph_targets_counts[node] = len(morphs)
            self.granny_morph_targets[node] = (GrannyMorphTarget * len(morphs))(*morphs)

    def to_granny_animation(self, scene: 'VirtualScene'):
        frame_total = self.frame_count - 1
        granny_animation = GrannyAnimation()
        granny_animation.name = self.name.encode()
        granny_animation.duration = scene.time_step * frame_total + 0.00001
        granny_animation.time_step = scene.time_step
        granny_animation.oversampling = 1
        all_track_groups = [self.granny_track_group] + self.granny_event_track_groups
        granny_animation.track_group_count = len(all_track_groups)
        granny_animation.track_groups = (POINTER(GrannyTrackGroup) * len(all_track_groups))(*all_track_groups)
        
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
        self.scene = scene
        if shader_path is not None:
            if not str(shader_path).strip() or str(shader_path) == '.':
                return self.set_default_shader(scene)
        
            path = Path(shader_path)
            full_path = Path(scene.tags_dir, shader_path)
            if not (full_path.exists() and full_path.is_file()):
                return self.set_default_shader(scene)
        
            self.shader_path = str(path.with_suffix(""))
            
            if scene.corinth:
                self.shader_type = "material"
            else:
                self.shader_type = path.suffix[1:]
                if not self.shader_type.startswith("shader"):
                    self.shader_type = "shader"
            
        
        self.to_granny_data(scene)
        if scene.uses_textures:
            self.make_granny_texture(scene)
        
    def set_default_shader(self, scene: 'VirtualScene'):
        self.shader_path = scene.default_shader_path
        self.shader_type = scene.default_shader_type
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
        bitmap_data = None
        if not full_path.exists():
            return
        if scene.corinth:
            with MaterialTag(path=shader_path) as shader:
                bitmap_data = shader.get_diffuse_bitmap_data_for_granny()
        else:
            match self.shader_type:
                case 'shader':
                    with ShaderTag(path=shader_path) as shader:
                        bitmap_data = shader.get_diffuse_bitmap_data_for_granny()
                case 'shader_decal':
                    with ShaderDecalTag(path=shader_path) as shader:
                        bitmap_data = shader.get_diffuse_bitmap_data_for_granny()
            
        if not bitmap_data:
            return
        
        # Create a granny texture builder instance
        width, height, stride, rgba = bitmap_data
        builder = scene.granny.begin_texture_builder(width, height)
        scene.granny.encode_image(builder, width, height, stride, 1, rgba)
        texture = scene.granny.end_texture(builder)
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

class VirtualMorphTargetData:
    def __init__(self, ob, scene, node: 'VirtualNode'):
        self.ob = ob
        self.positions: np.ndarray = None
        self.normals: np.ndarray = None
        self.vertex_colors: list[np.ndarray] = [] # Up to two sets of vert colors
        self.tension: np.ndarray = None
        self.num_vertices = 0
        self.invalid = False
        self._setup(ob, scene, node)
        self._granny_vertex_data(scene)
        self._write_vertex_position(scene, node)
        self.granny_morph_target = GrannyMorphTarget(None, self.granny_vertex_data, 0)
        
    def _write_vertex_position(self, scene, node):
        self.granny_vertex_data = GrannyVertexData()
        self.granny_vertex_data.vertex_component_names = self.vertex_component_names
        self.granny_vertex_data.vertex_component_name_count = self.vertex_component_name_count
        self.granny_vertex_data.vertex_type = self.vertex_type
        vertex_array = (c_ubyte * self.len_vertex_array)()
        if node.matrix_world == IDENTITY_MATRIX:
            vertex_array = self.vertex_array
        else:
            vertex_array = (c_ubyte * self.len_vertex_array)()
            memmove(vertex_array, self.vertex_array, self.len_vertex_array)
            affine3, linear3x3, inverse_linear3x3 = calc_transforms(node.matrix_world)
            scene.granny.transform_vertices(self.num_vertices,
                                            self.granny_vertex_data.vertex_type,
                                            vertex_array,
                                            affine3,
                                            linear3x3,
                                            inverse_linear3x3,
                                            True,
                                            False,
                                            )
        
        self.granny_vertex_data.vertices = cast(vertex_array, POINTER(c_ubyte))
        self.granny_vertex_data.vertex_count = self.num_vertices
        self.granny_vertex_data = pointer(self.granny_vertex_data)   
    
    def _setup(self, ob: bpy.types.Object, scene: 'VirtualScene' , node: 'VirtualNode'):
        eval_ob = ob.evaluated_get(scene.depsgraph)
        mesh = eval_ob.to_mesh(preserve_all_data_layers=False, depsgraph=scene.depsgraph)
        
        self.name = mesh.name
        if not mesh.polygons:
            scene.warnings.append(f"Mesh data [{self.name}] of object [{ob.name}] has no faces. Skipping writing morph target data")
            self.invalid = True
            return
            
        num_loops = len(mesh.loops)
        num_vertices = len(mesh.vertices)
        
        vertex_positions = np.empty((num_vertices, 3), dtype=np.single)
        loop_vertex_indices = np.empty(num_loops, dtype=np.int32)
        
        mesh.vertices.foreach_get("co", vertex_positions.ravel())
        mesh.loops.foreach_get("vertex_index", loop_vertex_indices)
        
        self.positions = vertex_positions[loop_vertex_indices]
        self.normals = np.empty((num_loops, 3), dtype=np.single)
        mesh.corner_normals.foreach_get("vector", self.normals.ravel())
        
        for idx, layer in enumerate(mesh.color_attributes):
            if len(self.vertex_colors) >= 2:
                break
            
            colors = np.empty((num_vertices, 4) if layer.domain == 'POINT' else (num_loops, 4), dtype=np.single)
            layer.data.foreach_get("color", colors.ravel())
            is_tension = layer.name.lower() == "tension"
            
            #if not is_tension:
            colors = colors[:, :3]
            if layer.domain == 'POINT':
                colors = colors[loop_vertex_indices]

            if is_tension:
                self.tension = colors
                # self.tension = np.concatenate((colors[:, 3:4], colors[:, :3]), axis=1)
            else:
                self.vertex_colors.append(colors)
                
        if self.tension is None:
            self.tension = np.zeros((num_loops, 3), dtype=np.single)
        
        new_indices = node.mesh.new_indices
        
        self.positions = self.positions[new_indices, :]
        
        if self.normals is not None:
            self.normals = self.normals[new_indices, :]

        if self.vertex_colors is not None:
            for idx, vcolor in enumerate(self.vertex_colors):
                self.vertex_colors[idx] = vcolor[new_indices, :]
                
        if self.tension is not None:
            self.tension = self.tension[new_indices, :]
            
        eval_ob.to_mesh_clear()
        
        self.num_vertices = len(self.positions)

    def _granny_vertex_data(self, scene: 'VirtualScene'):
        data = [self.positions]
        types = [GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Position", None, 3)]
        type_names = [b"Position"]
        dtypes = [('Position', np.single, (3,))]
        
        if self.normals is not None:
            data.append(self.normals)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Normal", None, 3))
            type_names.append(b"Normal")
            dtypes.append(('Normal', np.single, (3,)))
            
        for idx, vcolors in enumerate(self.vertex_colors):
            name = f"DiffuseColor{idx}"
            name_encoded = name.encode()
            data.append(vcolors)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, name_encoded, None, 3))
            type_names.append(name_encoded)
            dtypes.append((name, np.single, (3,)))
            
        if self.tension is not None:
            data.append(self.tension)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"DiffuseColor0", None, 3))
            type_names.append(b"tension")
            dtypes.append(("tension", np.single, (3,)))

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
    
    
class VirtualMesh:
    def __init__(self, vertex_weighted: bool, scene: 'VirtualScene', bone_bindings: list[str], ob: bpy.types.Object, render_mesh: bool, proxies: list, props: dict, negative_scaling: bool, bones: list[str], materials: tuple[bpy.types.Material]):
        self.name = ob.data.name
        self.mesh = ob.data
        self.proxies = proxies
        self.positions: np.ndarray = None
        self.normals: np.ndarray = None
        self.bone_weights: np.ndarray = None
        self.bone_indices: np.ndarray = None
        self.texcoords: list[np.ndarray] = [] # Up to 4 uv layers
        self.lighting_texcoords: np.ndarray = None
        self.vertex_colors: list[np.ndarray] = [] # Up to two sets of vert colors
        self.vertex_ids: np.ndarray = None # Corinth only
        self.tension: np.ndarray = None # Corinth only
        self.indices: np.ndarray = None
        self.num_indices = 0
        self.groups: list[VirtualMaterial, int, int] = []
        self.materials = {}
        self.bpy_materials = materials
        self.face_properties: dict = {}
        self.bone_bindings = bone_bindings
        self.vertex_weighted = vertex_weighted
        self.num_vertices = 0
        self.invalid = False
        self.granny_tri_topology = None
        self.siblings = [ob.name]
        self.new_indices = None
        self._setup(ob, scene, render_mesh, props, bones)
            
        if not self.invalid:
            self.to_granny_data(scene)
            if negative_scaling:
                scene.granny.invert_tri_topology_winding(self.granny_tri_topology)
        
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
        data = [self.positions]
        types = [GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Position", None, 3)]
        type_names = [b"Position"]
        dtypes = [('Position', np.single, (3,))]
        
        if self.normals is not None:
            data.append(self.normals)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"Normal", None, 3))
            type_names.append(b"Normal")
            dtypes.append(('Normal', np.single, (3,)))
        
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
            dtypes.append((name, np.single, (3,)))
            
        if self.lighting_texcoords is not None:
            data.append(self.lighting_texcoords)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, b"TextureCoordinateslighting", None, 3))
            type_names.append(b"lighting")
            dtypes.append((f'TextureCoordinateslighting{idx}', np.single, (3,)))
            
        for idx, vcolors in enumerate(self.vertex_colors):
            name = f"colorSet{idx + 1}" if scene.corinth else f"DiffuseColor{idx}"
            data.append(vcolors)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, f"DiffuseColor{idx}".encode(), None, 3))
            type_names.append(name.encode())
            dtypes.append((name, np.single, (3,)))
            
        if self.tension is not None:
            data.append(self.tension)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, f"DiffuseColor{len(self.vertex_colors)}".encode(), None, 3))
            type_names.append(b"tension")
            dtypes.append(("tension", np.single, (3,)))
            
        if self.vertex_ids is not None:
            data.append(self.vertex_ids)
            types.append(GrannyDataTypeDefinition(GrannyMemberType.granny_real32_member.value, f"TextureCoordinates{len(self.texcoords)}".encode(), None, 2))
            type_names.append(b"vertex_id")
            dtypes.append(('vertex_id', np.single, (2,)))

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
        
    def _setup(self, ob: bpy.types.Object, scene: 'VirtualScene', render_mesh: bool, props: dict, bones: list[str]):
        old_shape_key_index = 0
        shape_key_unmutes = []
        mesh_type_value = props.get("bungie_mesh_type")
        has_shape_keys = ob.type == 'MESH' and ob.data.shape_keys
        if has_shape_keys:
            old_shape_key_index = ob.active_shape_key_index
            ob.active_shape_key_index = 0
            for key_block in ob.data.shape_keys.key_blocks[1:]:
                if not key_block.mute:
                    shape_key_unmutes.append(key_block)
                    key_block.mute = True
                
        eval_ob = ob.evaluated_get(scene.depsgraph)
        
        true_mesh = ob.type == 'MESH'
        
        def add_triangle_mod(ob: bpy.types.Object) -> bpy.types.Modifier:
            mods = ob.modifiers
            for m in mods:
                if m.type == 'TRIANGULATE': return
                
            tri_mod = mods.new('Triangulate', 'TRIANGULATE')
            tri_mod.quad_method = scene.quad_method
            tri_mod.ngon_method = scene.ngon_method
            tri_mod.keep_custom_normals = True
        
        if true_mesh:
            add_triangle_mod(eval_ob)

        mesh = eval_ob.to_mesh(preserve_all_data_layers=True, depsgraph=scene.depsgraph)
        self.name = mesh.name
        if not mesh.polygons:
            if true_mesh:
                scene.warnings.append(f"Mesh data [{self.name}] of object [{ob.name}] has no faces. {ob.name} removed from geometry tree")
            self.invalid = True
            return
        
        indices = np.empty(len(mesh.polygons))
        mesh.polygons.foreach_get("loop_total", indices)
        unique_indices = np.unique(indices)
        
        if len(unique_indices) > 1 or unique_indices[0] != 3:
            # Only if we couldn't triangulate the mesh earlier
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces, quad_method=utils.tri_mod_to_bmesh_tri(scene.quad_method), ngon_method=utils.tri_mod_to_bmesh_tri(scene.ngon_method))
            bm.to_mesh(mesh)
            bm.free()
            
        if not mesh.polygons:
            if true_mesh:
                scene.warnings.append(f"Mesh data [{self.name}] of object [{ob.name}] has no faces. {ob.name} removed from geometry tree")
            self.invalid = True
            return
        
        is_object_instance = mesh_type_value == MeshType.object_instance.value
                    
        num_loops = len(mesh.loops)
        num_vertices = len(mesh.vertices)
        num_polygons = len(mesh.polygons)

        num_materials = len(self.bpy_materials)
        special_mats_dict = defaultdict(list)
        prop_mats_dict = defaultdict(list)
        valid_materials_count = 0
        for idx, mat in enumerate(self.bpy_materials):
            if mat is not None:
                if mat.nwo.SpecialMaterial:
                    special_mats_dict[mat].append(idx)
                elif mat.nwo.material_props:
                    prop_mats_dict[mat].append(idx)
                    
                valid_materials_count += 1

        sorted_order = None
        
        vertex_positions = np.empty((num_vertices, 3), dtype=np.single)
        loop_vertex_indices = np.empty(num_loops, dtype=np.int32)
        
        mesh.vertices.foreach_get("co", vertex_positions.ravel())
        mesh.loops.foreach_get("vertex_index", loop_vertex_indices)
        
        self.positions = vertex_positions[loop_vertex_indices]
        
        def remap(i):
            return vgroup_remap.get(i, 0)
        # TODO ensure collision is not skinned
        if self.vertex_weighted:
            # collision = props.get("bungie_mesh_type") == MeshType.collision.value
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

            for idx, vertex in enumerate(mesh.vertices):
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
                    
                    bone_weights[idx] = np.pad((top_weights * 255), (0, 4 - len(top_weights)))
                    bone_indices[idx] = np.pad(top_bone_indices, (0, 4 - len(top_bone_indices)))

                    unique_bone_indices.update(top_bone_indices)
                    
                
            if vgroup_remap:
                self.bone_bindings = [bones[idx] for idx in vgroup_remap.values()]
                max_index = max(vgroup_remap.values()) + 1
                mapping_array = np.full(max_index, -1, dtype=np.int32)
                for new_idx, old_idx in enumerate(vgroup_remap.values()):
                    mapping_array[old_idx] = new_idx

                bone_indices = np.clip(mapping_array[bone_indices], 0, max_index - 1)

                self.bone_weights = bone_weights.astype(np.byte)[loop_vertex_indices]
                self.bone_indices = bone_indices.astype(np.byte)[loop_vertex_indices]
        
        if render_mesh:
            # We only care about writing this data if the in game mesh will have a render definition
            if mesh.has_custom_normals and ob.data.nwo.from_vert_normals: # Use game vert normals
                normals = np.empty((num_loops, 3), dtype=np.single)
                mesh.corner_normals.foreach_get("vector", normals.ravel())
                vertex_normals = np.zeros((num_vertices, 3), dtype=np.single)
                vertex_counts = np.zeros(num_vertices, dtype=np.int32)
                np.add.at(vertex_normals, loop_vertex_indices, normals)
                vertex_counts = np.bincount(loop_vertex_indices)
                valid_mask = vertex_counts > 0
                vertex_normals[valid_mask] /= vertex_counts[valid_mask, None]
                self.normals = vertex_normals[loop_vertex_indices]
            else:
                self.normals = np.empty((num_loops, 3), dtype=np.single)
                mesh.corner_normals.foreach_get("vector", self.normals.ravel())
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
                is_tension = scene.corinth and layer.name.lower() == "tension"
                
                #if not is_tension:
                colors = colors[:, :3]
                if layer.domain == 'POINT':
                    colors = colors[loop_vertex_indices]
    
                if is_tension:
                    self.tension = colors #np.concatenate((colors[:, 3:4], colors[:, :3]), axis=1)
                else:
                    self.vertex_colors.append(colors)
                    
            if scene.corinth and self.tension is None and ob.data.shape_keys:
                self.tension = np.zeros((num_loops, 3), dtype=np.single)

        # Remove duplicate vertex data
        data = [self.positions]
        if self.normals is not None:
            data.append(self.normals)
        if self.texcoords is not None:
            data.extend(self.texcoords)
        if self.lighting_texcoords is not None:
            data.append(self.lighting_texcoords)
        if self.vertex_colors is not None:
            data.extend(self.vertex_colors)
        if self.tension is not None:
            data.append(self.tension)

        loop_data = np.hstack(data)

        _, new_indices, face_indices = np.unique(loop_data, axis=0, return_index=True, return_inverse=True)
        
        if scene.corinth:
            # Extract the start index and number of loops for each face
            loop_starts = np.empty(num_polygons, dtype=np.int32)
            loop_totals = np.empty(num_polygons, dtype=np.int32)

            mesh.polygons.foreach_get("loop_start", loop_starts)
            mesh.polygons.foreach_get("loop_total", loop_totals)

            # Compute the loop index within each face
            loop_in_face_indices = np.arange(num_loops) - np.repeat(loop_starts, loop_totals)

            # Combine face indices and loop indices into a single array
            self.vertex_ids = np.column_stack((face_indices, loop_in_face_indices))
            self.vertex_ids.astype(np.single)
            
        
        # self.indices = np.array(range(num_loops))

        self.indices = face_indices.astype(np.int32)
        new_indices = tuple(new_indices)
        
        self.new_indices = new_indices

        self.positions = self.positions[new_indices, :]
        
        if self.normals is not None:
            self.normals = self.normals[new_indices, :]

        if self.texcoords is not None:
            for idx, texcoord in enumerate(self.texcoords):
                self.texcoords[idx] = texcoord[new_indices, :]

        if self.lighting_texcoords is not None:
            self.lighting_texcoords = self.lighting_texcoords[new_indices, :]

        if self.vertex_colors is not None:
            for idx, vcolor in enumerate(self.vertex_colors):
                self.vertex_colors[idx] = vcolor[new_indices, :]
                
        if self.tension is not None:
            self.tension = self.tension[new_indices, :]

        if self.bone_weights is not None:
            self.bone_weights = self.bone_weights[new_indices, :]
            self.bone_indices = self.bone_indices[new_indices, :]
            
        if self.vertex_ids is not None:
            self.vertex_ids = self.vertex_ids[new_indices, :]
        
        if num_materials > 1 and scene.supports_multiple_materials(ob, props, mesh_type_value):
            material_indices = np.empty(num_polygons, dtype=np.int32)
            mesh.polygons.foreach_get("material_index", material_indices)
            sorted_order = np.argsort(material_indices)
            sorted_polygons = self.indices.reshape((-1, 3))[sorted_order]
            self.indices = sorted_polygons.ravel()
            unique_indices = np.concatenate(([0], np.where(np.diff(material_indices[sorted_order]) != 0)[0] + 1))
            counts = np.diff(np.concatenate((unique_indices, [len(material_indices)])))
            mat_index_counts = list(zip(unique_indices, counts))
            used_materials = [self.bpy_materials[i] for i in np.unique(material_indices) if i < len(self.bpy_materials)]
            unique_materials = list(dict.fromkeys([m for m in used_materials]))
            for idx, mat in enumerate(used_materials):
                virtual_mat = scene._get_material(mat, scene)
                self.materials[virtual_mat] = None
                self.groups.append((virtual_mat, unique_materials.index(mat), mat_index_counts[idx]))
        elif num_materials >= 1:
            virtual_mat = scene._get_material(self.bpy_materials[0], scene)
            self.materials[virtual_mat] = None
            self.groups.append((virtual_mat, 0, (0, num_polygons)))
        else:
            virtual_mat = scene.materials["invalid"]
            self.materials[virtual_mat] = None
            self.groups.append((virtual_mat, 0, (0, num_polygons))) # default material
        
        self.num_indices = len(self.indices)
        self.num_vertices = len(self.positions)
        
        # check if this mesh should be structure
        # if not scene.corinth and props.get("bungie_mesh_type") == MeshType.poop.value and not props.get("bungie_face_mode") in (FaceMode.render_only, FaceMode.lightmap_only, FaceMode.shadow_only):
        #     bm = bmesh.new()
        #     bm.from_mesh(mesh)
        #     vol = bm.calc_volume(signed=True)
        #     bm.free()
        #     if vol < 0:
        #         scene.warnings.append("blah")
        #         props["bungie_mesh_type"] = MeshType.default.value
        
        force_render_only = False
        if not scene.corinth and mesh_type_value == MeshType.poop.value:
            mask = np.asarray(scene.poop_obs[ob.data])
            if mask.all(): # Checks if all instances of a mesh use the poop_render_only flag, in which case it sets render only at face level
                force_render_only = True
        
        if (force_render_only or ob.data.nwo.face_props or (valid_materials_count > 1 and (special_mats_dict or prop_mats_dict))) and mesh_type_value in FACE_PROP_TYPES:
            self.face_properties = gather_face_props(ob.data.nwo, mesh, num_polygons, scene, sorted_order, special_mats_dict, prop_mats_dict, props, force_render_only)
            
            if is_object_instance:
                for prop_name, face_set in self.face_properties.items():
                    new_array = face_set.array.copy()
                    values, counts = np.unique(new_array, return_counts=True)
                    mode = values[counts.argmax()]
                    new_array[...] = mode
                    if not np.array_equal(face_set.array, new_array):
                        scene.warnings.append(f"Object '{ob.name}' has different mesh properties per face, this is not allowed for instanced objects. Forcing {prop_name} to {face_set.array[0]}")
                        face_set.array = new_array
            
        eval_ob.to_mesh_clear()
        
        if has_shape_keys:
            for key_block in shape_key_unmutes:
                key_block.mute = False
            if old_shape_key_index:
                ob.active_shape_key_index = old_shape_key_index
    
class VirtualNode:
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone, props: dict, region: str = None, permutation: str = None, scene: 'VirtualScene' = None, proxies = [], template_node: 'VirtualNode' = None, bones: list[str] = [], parent_matrix: Matrix = IDENTITY_MATRIX, animation_owner=None):
        self.name: str = id.name
        if isinstance(id, bpy.types.Object) and id.nwo.export_name:
            self.name = id.nwo.export_name
        self.ob = id
        self.id = id
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
        self.for_animation = animation_owner is not None
        self._set_group(scene, animation_owner)
        self.parent: VirtualNode = None
        self.bone_bindings: list[str] = []
        self.granny_vertex_data = None
        self.negative_scaling = False
        if not self.invalid and self.tag_type in scene.export_tag_types:
            # Skip writing mesh data for non-selected bsps/permutations
            if scene.limit_bsps and region not in scene.selected_bsps: return
            if scene.limit_permutations and permutation not in scene.selected_permutations: return
            self._setup(id, scene, proxies, template_node, bones, parent_matrix)
        
    def _setup(self, id: bpy.types.Object | bpy.types.PoseBone, scene: 'VirtualScene', proxies: list, template_node: 'VirtualNode', bones: list[str], parent_matrix: Matrix):
        if isinstance(id, bpy.types.Object):
            if template_node is None:
                if id.type == 'ARMATURE' and not id.parent:
                    self.matrix_world = IDENTITY_MATRIX
                    self.matrix_local = IDENTITY_MATRIX
                else:
                    if scene.maintain_marker_axis and self.props.get("bungie_object_type") == ObjectType.marker.value:
                        self.matrix_world = scene.rotation_matrix @ id.matrix_world @ scene.marker_rotation_matrix
                    else:
                        self.matrix_world = scene.rotation_matrix @ id.matrix_world
                        
                    self.matrix_local = parent_matrix @ self.matrix_world
            else:
                self.matrix_world = template_node.matrix_world.copy()
                # self.matrix_local = IDENTITY_MATRIX
                if template_node.negative_scaling:
                    id.nwo.invert_topology = not id.nwo.invert_topology
                
            if id.type in VALID_MESHES:
                default_bone_bindings = [self.name]
                self.negative_scaling = id.matrix_world.is_negative
                if id.nwo.invert_topology:
                    self.negative_scaling = not self.negative_scaling

                materials = tuple(slot.material for slot in id.material_slots)
                
                existing_mesh = scene.meshes.get((id.data, self.negative_scaling, materials))
                existing_linked_mesh = scene.meshes_linked.get(id.data)
                    
                if existing_mesh:
                    self.mesh = existing_mesh
                    self.mesh.siblings.append(self.name)
                else:
                    vertex_weighted = id.vertex_groups and id.parent and id.parent.type == 'ARMATURE' and id.parent_type != "BONE" and has_armature_deform_mod(id)
                    mesh = VirtualMesh(vertex_weighted, scene, default_bone_bindings, id, is_rendered(self.props), proxies if existing_linked_mesh is None else existing_linked_mesh.proxies, self.props, self.negative_scaling, bones, materials)
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
                    scene.granny.transform_vertices(self.mesh.num_vertices,
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
            
    def _set_group(self, scene: 'VirtualScene', animation: str | None):
        if animation is None:
            match scene.asset_type:
                case AssetType.MODEL | AssetType.ANIMATION | AssetType.SKY:
                    mesh_type = self.props.get("bungie_mesh_type")
                    if mesh_type:
                        match mesh_type:
                            case MeshType.default.value | MeshType.object_instance.value:
                                self.tag_type = 'render'
                            case MeshType.collision.value:
                                self.tag_type = 'collision'
                            case MeshType.physics.value:
                                self.tag_type = 'physics'
                        
                        self.group = f'{self.tag_type}_{self.permutation}'
                        
                    else:
                        object_type = self.props.get("bungie_object_type")
                        if object_type is None:
                            self.invalid = True
                            scene.warnings.append(f"Object [{self.name}] has no Halo object type")
                            return
                        
                        match object_type:
                            case ObjectType.marker.value:
                                self.tag_type = 'markers'
                            case ObjectType.frame.value:
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
                        if mesh_type == MeshType.default.value:
                            scene.bsps_with_structure.add(self.region)
                        
                    self.group = f'{self.tag_type}_{self.region}_{self.permutation}'
                    
                case AssetType.PREFAB:
                    self.tag_type = 'structure'
                    self.group = f'{self.tag_type}_{self.permutation}'
                    
                case _:
                    self.tag_type = 'render'
                    self.group = 'default'
        else:
            self.tag_type = 'animation'
            self.group = animation
                
    
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
    
class VirtualBone:
    '''Describes an blender object/bone which is a child'''
    def __init__(self, id: bpy.types.Object | bpy.types.PoseBone, name):
        self.name: str = name
        self.bone = id
        self.parent_index: int = -1
        self.node: VirtualNode = None
        self.matrix_local: Matrix = IDENTITY_MATRIX
        self.matrix_world: Matrix = IDENTITY_MATRIX
        self.props = {}
        self.granny_bone = GrannyBone()
        
    def create_bone_props(self, frame_ids):
        self.props["bungie_frame_ID1"] = int(frame_ids[0])
        self.props["bungie_frame_ID2"] = int(frame_ids[1])
        self.props["bungie_object_animates"] = 1
        self.props["bungie_object_type"] = ObjectType.frame.value
        
    def to_granny_data(self, scene: 'VirtualScene'):
        self.granny_bone.name = self.name.encode()
        self.granny_bone.parent_index = self.parent_index
        self.granny_bone.local_transform = GrannyTransform(7, *granny_transform_parts(self.matrix_local))
        self.granny_bone.inverse_world_4x4 = self._granny_world_transform()
        if self.props:
            scene.granny.create_extended_data(self.props, self.granny_bone)
        
    def _granny_world_transform(self):
        inverse_matrix = self.matrix_world.inverted_safe()
        inverse_transform = (c_float * 4 * 4)((tuple(inverse_matrix.col[0])), (tuple(inverse_matrix.col[1])), (tuple(inverse_matrix.col[2])), (tuple(inverse_matrix.col[3])))
        return inverse_transform
    
class AnimatedBone:
    def __init__(self, ob: bpy.types.Object, pbone, parent_override=None, is_aim_bone=False):
        self.name = pbone.name
        self.ob = ob
        self.parent_matrix_rest_inverted = ob.matrix_world.inverted_safe()
        self.pbone: bpy.types.PoseBone = pbone
        self.parent = None
        self.is_object = False
        self.is_aim_bone = is_aim_bone
        if isinstance(pbone, bpy.types.Object):
            self.is_object = True
        else:
            if parent_override is None:
                self.parent = pbone.parent
            else:
                self.parent = parent_override

class FakeBone:
    def __init__(self, ob: bpy.types.Object, bone: bpy.types.PoseBone, parent: 'FakeBone' = None, special_bone_names=[], parent_ob: bpy.types.Object = None):
        self.name = bone.name
        self.ob = ob
        self.parent = parent
        self.bone = bone
        self.export = ob.data.bones[bone.name].use_deform or self.name in special_bone_names
        if parent_ob is None:
            self.matrix = bone.matrix
        else:
            self.matrix = ob.matrix_world @ bone.matrix
        
def sort_bones_by_hierachy(fake_bones: list[FakeBone]):
    bone_dict = {}
    for fake_bone in fake_bones:
        if fake_bone.parent:
            bone_dict[fake_bone] = bone_dict[fake_bone.parent] + 1
        else:
            bone_dict[fake_bone] = 0
            
    return sorted(fake_bones, key=lambda x: bone_dict[x])
        
class VirtualSkeleton:
    '''Describes a list of bones'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene', node: VirtualNode, is_main_armature = False):
        self.name: str = ob.name
        if ob.nwo.export_name:
            self.name = ob.nwo.export_name
        self.ob = ob
        self.node = node
        self.pbones = {}
        self.animated_bones = []
        own_bone = VirtualBone(ob, self.name)
        own_bone.node = node
        if ob.type == 'ARMATURE':
            scene.armature_matrix = ob.matrix_world.copy()
            own_bone.props = {
                    "bungie_frame_world": 1,
                    "bungie_frame_ID1": 8078,
                    "bungie_frame_ID2": 378163771,
                    "bungie_object_type": ObjectType.frame.value,
                }
        elif own_bone.node and not own_bone.node.mesh:
            own_bone.props = own_bone.node.props
            
        own_bone.matrix_world = own_bone.node.matrix_world
        own_bone.matrix_local = IDENTITY_MATRIX
        
        own_bone.to_granny_data(scene)
        self.bones: list[VirtualBone] = [own_bone]
        self._get_bones(ob, scene, is_main_armature)
        
    def _get_bones(self, ob, scene: 'VirtualScene', is_main_armature: bool):
        if ob.type == 'ARMATURE':
            main_arm = ob
            scene_nwo = scene.context.scene.nwo
            aim_bone_names = {scene_nwo.node_usage_pose_blend_pitch, scene_nwo.node_usage_pose_blend_yaw}
            special_bone_names = {scene_nwo.node_usage_pedestal, scene_nwo.node_usage_pose_blend_pitch, scene_nwo.node_usage_pose_blend_yaw}
            # Get all bones at fake_bones, so we can more easily create a virtual skeleton containing multiple armatures
            support_armature_bone_parent_names = set()
            if is_main_armature:
                export_bones = [b for b in main_arm.data.bones if b.use_deform or b.name in special_bone_names]
                export_bone_names = [b.name for b in export_bones]
                root_bone_names = [b.name for b in export_bones if b.parent is None]
                if root_bone_names:
                    root = root_bone_names[0]
                    for child in scene.support_armatures:
                        if child.parent_type == 'BONE' and child.parent_bone in export_bone_names:
                            support_armature_bone_parent_names.add(child.parent_bone)
                        else:
                            support_armature_bone_parent_names.add(root)

            start_bones_dict = {}
            
            def create_fake_bone(arm, pb, parent_fb=None, parent_arm=None) -> FakeBone:
                if parent_fb is None:
                    parent = pb.parent
                    if parent:
                        parent_fb = start_bones_dict.get(parent)
                fb = FakeBone(arm, pb, parent_fb, special_bone_names, parent_arm)
                start_bones_dict[pb] = fb
                if fb.export and parent_fb is not None and not parent_fb.export: # Ensure parents of deform bones are themselves deform
                    scene.warnings.append(f"Bone {parent_fb.name} is marked non-deform but has deforming children. Including {parent_fb.name} in export")
                    parent_fb.export = True
                    
                return fb
            
            fb_names = []
            fbs = []
            for pbone in main_arm.pose.bones:
                fb = create_fake_bone(main_arm, pbone)
                fb_names.append(fb.name)
                fbs.append(fb)
                if fb.name in support_armature_bone_parent_names:
                    for child in scene.support_armatures:
                        for pbone_s in child.pose.bones:
                            cfb = create_fake_bone(child, pbone_s, fb if pbone_s.parent is None else None, main_arm)
                            fb_names.append(cfb.name)
                            fbs.append(cfb)
                            
            if len(set(fb_names)) != len(fb_names):
                error_str = [f"{fb.ob.name} --> {fb.name}" for fb in fbs]
                raise RuntimeError(f"Duplicate bone names found. Ensure that all exported armatures have unique bone names. Armature Bones list:\n{error_str}\n")
                
            start_bones = list(start_bones_dict.values())
            
            # Sort bones by hierachy i.e. all bones in a certain depth level in the child-parent relationship come before the next depth level
            sorted_bones = sort_bones_by_hierachy(start_bones)
            valid_bones = [fb for fb in sorted_bones if fb.export]
            # More bone collections for later
            list_bones = [fb.name for fb in valid_bones]
            dict_bones = {v: i for i, v in enumerate(list_bones)}
            self.pbones = {fb.name: fb.bone for fb in valid_bones}

            root_bone = None
            root_bone_found = False
            bone_inverse_matrices = {}
            for idx, fb in enumerate(valid_bones):
                b = VirtualBone(fb.bone, fb.name)
                frame_ids_index = None
                if scene.is_cinematic:
                    actor = scene.actors.get(ob)
                    if actor is not None and actor.node_order is not None:
                        frame_ids_index = actor.node_order.get(b.name)
                else:
                    frame_ids_index = scene.template_node_order.get(b.name)
                if frame_ids_index is None:
                    frame_ids_index = idx
                b.create_bone_props(scene.frame_ids[frame_ids_index])
                if fb.parent:
                    # Add one to this since the root is the armature
                    b.parent_index = dict_bones[fb.parent.name] + 1
                    b.matrix_world = scene.rotation_matrix @ fb.matrix
                    bone_inverse_matrices[fb.bone] = b.matrix_world.inverted_safe()
                    b.matrix_local = bone_inverse_matrices[fb.parent.bone] @ b.matrix_world
                else:
                    if root_bone_found:
                        raise RuntimeError(f"Armature {ob.name} has multiple root bones: {[bone.name for bone in valid_bones if not bone.parent]}. Halo requires that models have a single root bone. If one of the root bones is a control bone, ensure the deform checkbox is toggled off")
                    root_bone_found = True
                    root_bone = fb.bone
                    b.parent_index = 0
                    b.matrix_world = scene.rotation_matrix @ fb.matrix
                    b.matrix_local = b.matrix_world
                    bone_inverse_matrices[fb.bone] = b.matrix_world.inverted_safe()
                    scene.root_bone = root_bone
                
                b.to_granny_data(scene)
                self.bones.append(b)
                if is_main_armature or scene.is_cinematic:
                    self.animated_bones.append(AnimatedBone(fb.ob, fb.bone, is_aim_bone=fb.name in aim_bone_names, parent_override=fb.parent.bone if fb.parent else None))
                
            child_index = 0
            for child in scene.get_immediate_children(ob):
                bone_parented = child.parent_type == 'BONE' and child.parent_bone
                parent_matrix = IDENTITY_MATRIX
                parent_index = 0
                if bone_parented:
                    bone_index = dict_bones.get(child.parent_bone)
                    if bone_index is None:
                        scene.warnings.append(f"{child.name} is parented to non-existent or non-deform bone: {child.parent_bone}. Parenting to {list_bones[0]}")
                        bone_index = 0
                    parent_bone = valid_bones[bone_index]
                    parent_index = bone_index + 1
                    parent_matrix = bone_inverse_matrices[parent_bone.bone]

                node = scene.add(child, *scene.object_halo_data[child], bones=list_bones, parent_matrix=parent_matrix)
                if not node: continue
                child_index += 1
                if not node or node.invalid: continue
                if not bone_parented and not (node.mesh and node.mesh.vertex_weighted):
                    parent_index = 1
                    
                b = VirtualBone(child, node.name)
                b.node = node
                if child.type != 'MESH':
                    b.props = b.node.props
                b.matrix_world = node.matrix_world
                b.matrix_local = node.matrix_local
                b.parent_index = parent_index

                b.to_granny_data(scene)
                self.bones.append(b)
                self.find_children(child, scene, child_index)
                    
        else:
            self.find_children(ob, scene)
                    
    def find_children(self, ob: bpy.types.Object, scene: 'VirtualScene', parent_index=0):
        child_index = parent_index
        for child in scene.get_immediate_children(ob):
            parent_node = scene.nodes.get(ob)
            if parent_node is None:
                continue
            node = scene.add(child, *scene.object_halo_data[child], parent_matrix=parent_node.matrix_world.inverted_safe())
            if not node or node.invalid: continue
            child_index += 1
            b = VirtualBone(child, node.name)
            b.parent_index = parent_index
            b.node = node
            if child.type != 'MESH':
                b.props = b.node.props
            b.matrix_world = node.matrix_world
            b.matrix_local = node.matrix_local
            b.to_granny_data(scene)
            self.bones.append(b)
            self.find_children(child, scene, child_index)
            
        if self.node.mesh:
            for proxy in self.node.mesh.proxies:
                node = scene.add(proxy, *scene.object_halo_data[proxy], self.node)
                if not node or node.invalid: continue
                b = VirtualBone(proxy, node.name)
                b.parent_index = parent_index
                b.node = node
                b.matrix_world = b.node.matrix_world
                b.matrix_local = b.node.matrix_local
                b.to_granny_data(scene)
                self.bones.append(b)
                
    def append_animation_control(self, ob: bpy.types.Object, node: VirtualNode, scene: 'VirtualScene', parent_index=1):
        b = VirtualBone(ob, node.name)
        b.parent_index = parent_index
        b.node = node
        b.matrix_world = b.node.matrix_world
        b.matrix_local = b.node.matrix_local
        b.props = node.props
        b.to_granny_data(scene)
        self.bones.append(b)
    
class VirtualModel:
    '''Describes a blender object which has no parent'''
    def __init__(self, ob: bpy.types.Object, scene: 'VirtualScene', props=None, region=None, permutation=None, animation_owner=None):
        self.name: str = ob.name
        if ob.nwo.export_name:
            self.name = ob.nwo.export_name
        self.ob = ob
        self.node = None
        self.skeleton = None
        is_main_armature = False
        if props is None:
            node = scene.add(ob, *scene.object_halo_data[ob])
        else:
            node = scene.add(ob, props, region, permutation, animation_owner=animation_owner)
        if node and not node.invalid:
            self.node = node
            if ob.type == 'ARMATURE' and scene.has_main_skeleton:
                if not scene.skeleton_node or scene.context.scene.nwo.main_armature == ob:
                    scene.skeleton_node = self.node
                    scene.skeleton_model = self
                    scene.skeleton_object = ob
                    is_main_armature = True

            self.skeleton: VirtualSkeleton = VirtualSkeleton(ob, scene, self.node, is_main_armature)
            self.matrix: Matrix = ob.matrix_world.copy()
            
class VirtualScene:
    def __init__(self, asset_type: AssetType, depsgraph: bpy.types.Depsgraph, corinth: bool, tags_dir: Path, granny: Granny, export_settings, time_step: float, animation_compression: str, rotation: float, maintain_marker_axis: bool, granny_textures: bool, project, light_scale: float, unit_factor: float, atten_scalar: int, context: bpy.types.Context):
        self.nodes: dict[VirtualNode] = {}
        self.meshes: dict[VirtualMesh] = {}
        self.meshes_linked: dict[VirtualMesh] = {}
        self.materials: dict[VirtualMaterial] = {}
        self.models: dict[VirtualModel] = {}
        self.root: VirtualNode = None
        self.uses_textures = granny_textures
        self.quad_method = export_settings.triangulate_quad_method
        self.ngon_method = export_settings.triangulate_ngon_method
        self.asset_type = asset_type
        self.depsgraph = depsgraph
        self.tags_dir = tags_dir
        self.granny = granny
        self.regions: dict = {}
        self.regions_set = set()
        self.permutations: list = []
        self.global_materials: dict = {}
        self.global_materials_set = set()
        self.skeleton_node: VirtualNode = None
        self.skeleton_model: VirtualModel = None
        self.skeleton_object: bpy.types.Object
        self.time_step = time_step
        # self.time_step = 1.0010000467300415 / 30
        self.corinth = corinth
        self.export_info: ExportInfo = None
        self.valid_bones = []
        self.frame_ids = read_frame_id_list()
        self.structure = set()
        self.design = set()
        self.bsps_with_structure = set()
        self.warnings = []
        self.animations = []
        self.shots = []
        self.default_animation_compression = animation_compression
        
        self.object_parent_dict: dict[bpy.types.Object: bpy.types.Object] = {}
        self.object_halo_data: dict[bpy.types.Object: tuple[dict, str, str, list]] = {}
        self.mesh_object_map: dict[tuple[bpy.types.Mesh, bool]: list[bpy.types.Object]] = {}
        
        self.material_extended_data_type = self._create_material_extended_data_type()
        self.correction_matrix = IDENTITY_MATRIX
        self.root_bone = None
        self.aim_pitch = None
        self.aim_yaw = None
        self.root_bone_inverse_matrix = IDENTITY_MATRIX
        self.aim_pitch_matrix_inverse = IDENTITY_MATRIX
        self.aim_yaw_matrix_inverse = IDENTITY_MATRIX

        self.rotation_matrix = Matrix.Rotation(rotation, 4, Vector((0, 0, 1)))
        self.marker_rotation_matrix = Matrix.Rotation(-rotation, 4, 'Z')
        self.maintain_marker_axis = maintain_marker_axis
        self.armature_matrix = IDENTITY_MATRIX
        
        self.export_tag_types = set()
        self.support_armatures = []
        
        self.light_scale = light_scale
        self.unit_factor = unit_factor
        self.atten_scalar = atten_scalar
        
        self.selected_bsps = set()
        self.selected_permutations = set()
        self.limit_bsps = False
        self.limit_permutations = False
        
        self.context = context
        self.actors = []
        self.selected_actors = set()
        self.selected_cinematic_objects_only = False
        self.cinematic_scope = 'BOTH'
        
        self.vector_tracks = []
        self.poop_obs = {}
        
        spath = "shaders\invalid"
        stype = "material" if corinth else "shader"
        if project and project.default_material:
            relative_default_shader = utils.relative_path(project.default_material)
            if Path(tags_dir, relative_default_shader).exists():
                spath, _, stype = relative_default_shader.rpartition('.')
        
        self.default_shader_path = spath
        self.default_shader_type = stype
        
        # Create default material
        default_material = VirtualMaterial("invalid", self, f"{self.default_shader_path}.{self.default_shader_type}")
            
        self.materials["invalid"] = default_material

        self.template_node_order = {}
        
        self.has_main_skeleton = asset_type in {AssetType.MODEL, AssetType.SKY, AssetType.ANIMATION}
        self.is_cinematic = asset_type == AssetType.CINEMATIC
        
        self.disable_automatic_suspension_computation = export_settings.disable_automatic_suspension_computation
        
    def _create_material_extended_data_type(self):
        material_extended_data_type = (GrannyDataTypeDefinition * 3)(
            GrannyDataTypeDefinition(member_type=GrannyMemberType.granny_string_member, name=b"bungie_shader_path"),
            GrannyDataTypeDefinition(member_type=GrannyMemberType.granny_string_member, name=b"bungie_shader_type"),
            GrannyDataTypeDefinition(GrannyMemberType.granny_end_member.value)
        )
        
        return material_extended_data_type
    
    def _create_curve_data_type(self):
        pass
        
    def add(self, id: bpy.types.Object, props: dict, region: str = None, permutation: str = None, proxies: list = [], template_node: VirtualNode = None, bones: list[str] = [], parent_matrix: Matrix = IDENTITY_MATRIX, animation_owner=None) -> VirtualNode:
        '''Creates a new node with the given parameters and appends it to the virtual scene'''
        node = VirtualNode(id, props, region, permutation, self, proxies, template_node, bones, parent_matrix, animation_owner)
        if not node.invalid:
            self.nodes[node.ob] = node
            if node.new_mesh:
                # This is a tuple containing whether the object has a negative scale. This because we need to create separate mesh data for negatively scaled objects
                negative_scaling = id.matrix_world.is_negative
                if id.nwo.invert_topology:
                    negative_scaling = not negative_scaling
                self.meshes[(node.mesh.mesh, negative_scaling, node.mesh.bpy_materials)] = node.mesh
                self.meshes_linked[node.mesh.mesh] = node.mesh
            
        return node
            
    def get_immediate_children(self, parent):
        children = [ob for ob, ob_parent in self.object_parent_dict.items() if ob_parent == parent]
        return children
        
    def add_model(self, ob):
        model = VirtualModel(ob, self)
        if model.node:
            self.models[ob] = model
            
    def add_model_for_animation(self, ob, props, animation_owner):
        model = VirtualModel(ob, self, props=props, animation_owner=animation_owner)
        if model.node:
            self.models[ob] = model
            return model.node
            
    def add_animation(self, anim, sample=True, controls=[], shape_key_objects=[], vector_events=[]):
        animation = VirtualAnimation(anim, self, sample, controls, shape_key_objects, vector_events)
        self.animations.append(animation)
        return animation.name
    
    def add_shot(self, frame_start: int, frame_end: int, actors: list[bpy.types.Object], camera: bpy.types.Object, index: int, in_scope: bool):
        shot = VirtualShot(frame_start, frame_end, actors, camera, index, self, in_scope)
        shot.perform(self)
        self.shots.append(shot)
        
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
        
    def add_automatic_structure(self, default_region, default_permutation, scalar):
        def wrap_bounding_box(nodes, padding):
            min_x, min_y, min_z, max_x, max_y, max_z = (i * scalar for i in (-10, -10, 0, 10, 10, 30))
            for node in nodes:
                # inverse the rotation matrix otherwise this will be rotated incorrectly
                if node.id.type == 'MESH':
                    bbox = node.id.bound_box
                    for co in bbox:
                        bounds = self.rotation_matrix.inverted_safe() @ node.matrix_world @ Vector((co[0], co[1], co[2]))
                        min_x = min(min_x, bounds.x - padding)
                        min_y = min(min_y, bounds.y - padding)
                        min_z = min(min_z, bounds.z - padding)
                        max_x = max(max_x, bounds.x + padding)
                        max_y = max(max_y, bounds.y + padding)
                        max_z = max(max_z, bounds.z + padding)
                else:
                    bounds = self.rotation_matrix.inverted_safe() @ node.matrix_world.to_translation()
                    min_x = min(min_x, bounds.x - padding)
                    min_y = min(min_y, bounds.y - padding)
                    min_z = min(min_z, bounds.z - padding)
                    max_x = max(max_x, bounds.x + padding)
                    max_y = max(max_y, bounds.y + padding)
                    max_z = max(max_z, bounds.z + padding)
        
            # Create the box with bmesh
            bm = bmesh.new()
            xyz = bm.verts.new(Vector((min_x, min_y, min_z)))
            xyz = bm.verts.new(Vector((min_x, min_y, min_z)))
            xYz = bm.verts.new(Vector((min_x, max_y, min_z)))
            xYZ = bm.verts.new(Vector((min_x, max_y, max_z)))
            xyZ = bm.verts.new(Vector((min_x, min_y, max_z)))
            
            Xyz = bm.verts.new(Vector((max_x, min_y, min_z)))
            XYz = bm.verts.new(Vector((max_x, max_y, min_z)))
            XYZ = bm.verts.new(Vector((max_x, max_y, max_z)))
            XyZ = bm.verts.new(Vector((max_x, min_y, max_z)))
            
            bm.faces.new([xyz, xYz, xYZ, xyZ]) # Create the minimum x face
            bm.faces.new([Xyz, XYz, XYZ, XyZ]) # Create the maximum x face
            
            bm.faces.new([xyz, Xyz, XyZ, xyZ]) # Create the minimum y face
            bm.faces.new([xYz, xYZ, XYZ, XYz]) # Create the maximum y face
            
            bm.faces.new([xyz, xYz, XYz, Xyz]) # Create the minimum z face
            bm.faces.new([xyZ, xYZ, XYZ, XyZ]) # Create the maximum z face
            
            # Calculate consistent faces
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            # Flip em since bmesh by default calculates outside normals
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='FIXED')
            
            # Create the mesh and object
            structure_mesh = bpy.data.meshes.new('autogenerated_structure')
            bm.to_mesh(structure_mesh)
            structure_ob = bpy.data.objects.new('autogenerated_structure', structure_mesh)
            props = {}
            props["bungie_object_type"] = ObjectType.mesh.value
            props["bungie_mesh_type"] = MeshType.default.value
            props["bungie_face_type"] = FaceType.sky.value
            
            return structure_ob, props
        
        if not self.structure:
            self.structure.add(default_region)

        if self.structure == self.bsps_with_structure:
            return
        no_bsp_structure = self.structure.difference(self.bsps_with_structure)
        print(f"--- Adding Structure Geometry For BSPs: {[bsp for bsp in no_bsp_structure]}")
        for bsp in no_bsp_structure:
            ob, props = wrap_bounding_box([node for node in self.nodes.values() if node.region == bsp], 0 if self.corinth else 1 * scalar)
            self.models[ob] = VirtualModel(ob, self, props, bsp, default_permutation)

    def supports_multiple_materials(self, ob: bpy.types.Object, props: dict, mesh_type: int) -> bool:
        if mesh_type in {
            MeshType.default.value,
            MeshType.poop.value,
            MeshType.poop_collision.value,
            MeshType.poop_physics.value,
            MeshType.water_surface.value,
        }:
            return True
        
        if mesh_type == MeshType.object_instance.value:
            self.warnings.append(f"'{ob.name}' has more than one material. Instanced Objects only support a single material. Ignoring materials after {ob.data.materials[0].name}")

        return False
    
    # def __del__(self):
    #     for animation in self.animations:
    #         del animation

    #     for node in self.nodes.values():
    #         del node

    #     for mesh in self.meshes.values():
    #         del mesh

    #     for material in self.materials.values():
    #         del material

    #     for model in self.models:
    #         del model
                
def has_armature_deform_mod(ob: bpy.types.Object):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE' and mod.object and mod.use_vertex_groups:
            return True
            
    return False

class FaceSet:
    def __init__(self, array: np.ndarray):
        self.array = array
        self.annotation_type = None
        self._set_tri_annotation_type()
        
    def update(self, mesh: bpy.types.Mesh, prop, value: object, additive=False):
        attribute = mesh.attributes.get(prop.attribute_name)
        if attribute is not None:
            values_array = np.zeros(len(mesh.polygons), dtype=np.int8)
            attribute.data.foreach_get("value", values_array)
            mask = values_array.astype(bool)
            if additive:
                self.array[mask] += value
            else:
                self.array[mask] = value
            
    def update_from_material(self, mesh: bpy.types.Mesh, material_indices: set[int], value: object, additive=False):
        values_array = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", values_array)
        mask = np.isin(values_array, material_indices)
        if additive:
            self.array[mask] += value
        else:
            self.array[mask] = value
            
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
            # case np.uint8:
            #     annotation_type.append(GrannyDataTypeDefinition(GrannyMemberType.granny_uint8_member.value, b"Uint8", None, size))
            case _:
                raise(f"Unimplemented numpy data type: {self.array.dtype}")
            
        annotation_type.append(GrannyDataTypeDefinition(0, None, None, 0))
        
        type_info_array = (GrannyDataTypeDefinition * 2)(*annotation_type)
        self.annotation_type = cast(type_info_array, POINTER(GrannyDataTypeDefinition))
            

def gather_face_props(mesh_props: NWO_MeshPropertiesGroup, mesh: bpy.types.Mesh, num_faces: int, scene: VirtualScene, sorted_order, special_mats_dict: dict, prop_mats_dict: dict, props: dict, force_render_only: bool) -> dict:
    is_structure = props.get("bungie_mesh_type") == MeshType.default.value
    face_properties = {}
    deferred_transparencies = []
    deferred_opaques = []
    
    # Do material probs first to ensure they can be overriden by face props
    
    for material, material_indices in prop_mats_dict.items():
        for prop in material.nwo.material_props:
            match prop.type:
                case 'face_mode':
                    if props.get("bungie_face_mode") is None:
                        face_mode = FaceMode[prop.face_mode]
                        
                        if scene.corinth and face_mode == FaceMode.breakable:
                            continue
                        face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_mode"], dtype=np.int32))).update_from_material(mesh, material_indices, face_mode.value)
                case 'collision_type':
                    if props.get("bungie_mesh_poop_collision_type") is None:
                        face_properties.setdefault("bungie_mesh_poop_collision_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_poop_collision_type"], dtype=np.int32))).update_from_material(mesh, material_indices, PoopCollisionType[prop.collision_type].value)
                case 'face_sides':
                    if props.get("bungie_face_sides") is None:
                        side_value = 2 if prop.two_sided else 0
                        if prop.two_sided and scene.corinth and prop.face_sides_type != "two_sided":
                            side_value = 4 if prop.face_sides_type == 'mirror' else 6
                        face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_sides"], dtype=np.int32))).update_from_material(mesh, material_indices, side_value)
                case 'transparent':
                    if props.get("bungie_face_sides") is None and prop.transparent:
                        deferred_transparencies.append(material_indices)
                            
                        # face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_sides"], dtype=np.int32))).update_from_material(mesh, material_indices, 1, additive=True)
                case 'region':
                    if scene.asset_type.supports_regions and props.get("bungie_face_region") is None:
                        rv = scene.regions.get(face_prop_defaults["bungie_face_region"], 0)
                        face_rv = scene.regions.get(prop.region)
                        if face_rv is not None:
                            face_properties.setdefault("bungie_face_region", FaceSet(np.full(num_faces, rv, dtype=np.int32))).update_from_material(mesh, material_indices, face_rv)
                case 'draw_distance':
                    if props.get("bungie_face_draw_distance") is None:
                        face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_draw_distance"], dtype=np.int32))).update_from_material(mesh, material_indices, FaceDrawDistance[prop.draw_distance].value)
                case 'global_material':
                    if props.get("bungie_face_global_material") is None:
                        gmv = scene.global_materials.get(face_prop_defaults["bungie_face_global_material"], 0)
                        face_gmv = scene.global_materials.get(prop.global_material.strip().replace(' ', "_"))
                        if face_gmv is not None:
                            if scene.corinth and props.get("bungie_mesh_type") in {MeshType.poop.value or MeshType.poop_collision.value}:
                                face_properties.setdefault("bungie_mesh_global_material", FaceSet(np.full(num_faces, gmv, dtype=np.int32))).update_from_material(mesh, material_indices, face_gmv)
                                face_properties.setdefault("bungie_mesh_poop_collision_override_global_material", FaceSet(np.full(num_faces, 0, dtype=np.int32))).update_from_material(mesh, material_indices, 1)
                            else:
                                face_properties.setdefault("bungie_face_global_material", FaceSet(np.full(num_faces, gmv, dtype=np.int32))).update_from_material(mesh, material_indices, face_gmv)
                case 'ladder':
                    if props.get("bungie_ladder") is None:
                        face_properties.setdefault("bungie_ladder", FaceSet(np.full(num_faces, face_prop_defaults["bungie_ladder"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.ladder))
                case 'slip_surface':
                    if props.get("bungie_slip_surface") is None:
                        face_properties.setdefault("bungie_slip_surface", FaceSet(np.full(num_faces, face_prop_defaults["bungie_slip_surface"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.slip_surface))
                case 'decal_offset':
                    if props.get("bungie_decal_offset") is None:
                        face_properties.setdefault("bungie_decal_offset", FaceSet(np.full(num_faces, face_prop_defaults["bungie_decal_offset"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.decal_offset))
                case 'no_shadow':
                    if props.get("bungie_no_shadow") is None:
                        face_properties.setdefault("bungie_no_shadow", FaceSet(np.full(num_faces, face_prop_defaults["bungie_no_shadow"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.no_shadow))
                case 'precise_position':
                    if props.get("bungie_precise_position") is None:
                        face_properties.setdefault("bungie_precise_position", FaceSet(np.full(num_faces, face_prop_defaults["bungie_precise_position"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.precise_position))
                case 'uncompressed':
                    if props.get("bungie_mesh_use_uncompressed_verts") is None:
                        face_properties.setdefault("bungie_mesh_use_uncompressed_verts", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_use_uncompressed_verts"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.uncompressed))
                case 'additional_compression':
                    if props.get("bungie_mesh_additional_compression") is None:
                        face_properties.setdefault("bungie_mesh_additional_compression", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_additional_compression"], dtype=np.int32))).update_from_material(mesh, material_indices, AdditionalCompression[prop.additional_compression].value)
                case 'no_lightmap':
                    if props.get("bungie_no_lightmap") is None:
                        face_properties.setdefault("bungie_no_lightmap", FaceSet(np.full(num_faces, face_prop_defaults["bungie_no_lightmap"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.no_lightmap))
                case 'no_pvs':
                    if props.get("bungie_invisible_to_pvs") is None:
                        face_properties.setdefault("bungie_invisible_to_pvs", FaceSet(np.full(num_faces, face_prop_defaults["bungie_invisible_to_pvs"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.no_pvs))
                case 'mesh_tessellation_density':
                    if props.get("bungie_mesh_tessellation_density") is None:
                        face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_tessellation_density"], dtype=np.int32))).update_from_material(mesh, material_indices, MeshTessellationDensity[prop.mesh_tessellation_density].value)
                case 'lightmap_resolution_scale':
                    if props.get("bungie_lightmap_resolution_scale") is None:
                        face_properties.setdefault("bungie_lightmap_resolution_scale", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_resolution_scale"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.lightmap_resolution_scale))
                case 'lightmap_ignore_default_resolution_scale':
                    if props.get("bungie_lightmap_ignore_default_resolution_scale") is None:
                        face_properties.setdefault("bungie_lightmap_ignore_default_resolution_scale", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_ignore_default_resolution_scale"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.lightmap_ignore_default_resolution_scale))
                case 'lightmap_chart_group':
                    if props.get("bungie_lightmap_chart_group") is None:
                        face_properties.setdefault("bungie_lightmap_chart_group", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_chart_group"], dtype=np.int32))).update_from_material(mesh, material_indices, prop.lightmap_chart_group)
                case 'lightmap_type':
                    if props.get("bungie_lightmap_type") is None:
                        face_properties.setdefault("bungie_lightmap_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_type"], dtype=np.int32))).update_from_material(mesh, material_indices, LightmapType[prop.lightmap_type].value)
                case 'lightmap_additive_transparency':
                    if props.get("bungie_lightmap_additive_transparency") is None:
                        face_properties.setdefault("bungie_lightmap_additive_transparency", FaceSet(np.full((num_faces, 3), face_prop_defaults["bungie_lightmap_additive_transparency"], dtype=np.single))).update_from_material(mesh, material_indices, utils.color_3p_int(prop.lightmap_additive_transparency))
                case 'lightmap_transparency_override':
                    if props.get("bungie_lightmap_transparency_override") is None:
                        face_properties.setdefault("bungie_lightmap_transparency_override", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_transparency_override"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.lightmap_transparency_override))
                case 'lightmap_analytical_bounce_modifier':
                    if props.get("bungie_lightmap_analytical_bounce_modifier") is None:
                        face_properties.setdefault("bungie_lightmap_analytical_bounce_modifier", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_analytical_bounce_modifier"], dtype=np.single))).update_from_material(mesh, material_indices, prop.lightmap_analytical_bounce_modifier)
                case 'lightmap_general_bounce_modifier':
                    if props.get("bungie_lightmap_general_bounce_modifier") is None:
                        face_properties.setdefault("bungie_lightmap_general_bounce_modifier", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_general_bounce_modifier"], dtype=np.single))).update_from_material(mesh, material_indices, prop.lightmap_general_bounce_modifier)
                case 'lightmap_translucency_tint_color':
                    if props.get("bungie_lightmap_translucency_tint_color") is None:
                        face_properties.setdefault("bungie_lightmap_translucency_tint_color", FaceSet(np.full((num_faces, 3), face_prop_defaults["bungie_lightmap_translucency_tint_color"], dtype=np.single))).update_from_material(mesh, material_indices, utils.color_3p_int(prop.lightmap_translucency_tint_color))
                case 'lightmap_lighting_from_both_sides':
                    if props.get("bungie_lightmap_lighting_from_both_sides") is None:
                        face_properties.setdefault("bungie_lightmap_lighting_from_both_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_lighting_from_both_sides"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.lightmap_lighting_from_both_sides))
                case 'emissive':
                    if props.get("bungie_lighting_emissive_power") is None and prop.material_lighting_emissive_power > 0:
                        power = max(prop.light_intensity, 0.0001)
                        if prop.material_lighting_attenuation_cutoff > 0:
                            falloff = prop.material_lighting_attenuation_falloff
                            cutoff = prop.material_lighting_attenuation_cutoff
                        else:
                            falloff, cutoff = calc_attenutation(prop.material_lighting_emissive_power * scene.unit_factor ** 2)
                        face_properties.setdefault("bungie_lighting_emissive_power", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_power"], np.single))).update_from_material(mesh, material_indices, power)
                        face_properties.setdefault("bungie_lighting_emissive_color", FaceSet(np.full((num_faces, 4), face_prop_defaults["bungie_lighting_emissive_color"], np.single))).update_from_material(mesh, material_indices, utils.color_4p_int(prop.material_lighting_emissive_color))
                        face_properties.setdefault("bungie_lighting_emissive_per_unit", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_per_unit"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.material_lighting_emissive_per_unit))
                        face_properties.setdefault("bungie_lighting_emissive_quality", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_quality"], np.single))).update_from_material(mesh, material_indices, prop.material_lighting_emissive_quality)
                        face_properties.setdefault("bungie_lighting_use_shader_gel", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_use_shader_gel"], dtype=np.int32))).update_from_material(mesh, material_indices, int(prop.material_lighting_use_shader_gel))
                        face_properties.setdefault("bungie_lighting_bounce_ratio", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_bounce_ratio"], np.single))).update_from_material(mesh, material_indices, prop.material_lighting_bounce_ratio)
                        face_properties.setdefault("bungie_lighting_attenuation_enabled", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_attenuation_enabled"], dtype=np.int32))).update_from_material(mesh, material_indices, 1)
                        face_properties.setdefault("bungie_lighting_attenuation_cutoff", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_attenuation_cutoff"], np.single))).update_from_material(mesh, material_indices, cutoff * scene.atten_scalar * WU_SCALAR)
                        face_properties.setdefault("bungie_lighting_attenuation_falloff", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_attenuation_falloff"], np.single))).update_from_material(mesh, material_indices, falloff * scene.atten_scalar * WU_SCALAR)
                        face_properties.setdefault("bungie_lighting_emissive_focus", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_focus"], np.single))).update_from_material(mesh, material_indices, degrees(prop.material_lighting_emissive_focus) / 180)
        
    
    for prop in mesh_props.face_props:
        match prop.type:
            case 'face_mode':
                if props.get("bungie_face_mode") is None:
                    face_mode = FaceMode[prop.face_mode]
                    
                    if scene.corinth and face_mode == FaceMode.breakable:
                        continue
                    face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_mode"], dtype=np.int32))).update(mesh, prop, face_mode.value)
            case 'collision_type':
                if props.get("bungie_mesh_poop_collision_type") is None:
                    face_properties.setdefault("bungie_mesh_poop_collision_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_poop_collision_type"], dtype=np.int32))).update(mesh, prop, PoopCollisionType[prop.collision_type].value)
            case 'face_sides':
                if props.get("bungie_face_sides") is None:
                    side_value = 2 if prop.two_sided else 0
                    if prop.two_sided and scene.corinth and prop.face_sides_type != "two_sided":
                        side_value = 4 if prop.face_sides_type == 'mirror' else 6
                    face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_sides"], dtype=np.int32))).update(mesh, prop, side_value)
            case 'transparent':
                if props.get("bungie_face_sides") is None:
                    attribute = mesh.attributes.get(prop.attribute_name)
                    if attribute is not None:
                        prop_face_indices = np.zeros(len(mesh.polygons), dtype=np.int8)
                        attribute.data.foreach_get("value", prop_face_indices)
                        if prop.transparent:
                            deferred_transparencies.append(np.nonzero(prop_face_indices)[0])
                        else:
                            deferred_opaques.append(np.nonzero(prop_face_indices)[0])
                    # face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_sides"], dtype=np.int32))).update(mesh, prop, 1, additive=True)
            case 'region':
                if scene.asset_type.supports_regions and props.get("bungie_face_region") is None:
                    rv = scene.regions.get(face_prop_defaults["bungie_face_region"], 0)
                    face_rv = scene.regions.get(prop.region)
                    if face_rv is not None:
                        face_properties.setdefault("bungie_face_region", FaceSet(np.full(num_faces, rv, dtype=np.int32))).update(mesh, prop, face_rv)
            case 'draw_distance':
                if props.get("bungie_face_draw_distance") is None:
                    face_properties.setdefault("bungie_face_draw_distance", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_draw_distance"], dtype=np.int32))).update(mesh, prop, FaceDrawDistance[prop.draw_distance].value)
            case 'global_material':
                if props.get("bungie_face_global_material") is None:
                    gmv = scene.global_materials.get(face_prop_defaults["bungie_face_global_material"], 0)
                    face_gmv = scene.global_materials.get(prop.global_material.strip().replace(' ', "_"))
                    if face_gmv is not None:
                        if scene.corinth and props.get("bungie_mesh_type") in {MeshType.poop.value or MeshType.poop_collision.value}:
                            face_properties.setdefault("bungie_mesh_global_material", FaceSet(np.full(num_faces, gmv, dtype=np.int32))).update(mesh, prop, face_gmv)
                            face_properties.setdefault("bungie_mesh_poop_collision_override_global_material", FaceSet(np.full(num_faces, 0, dtype=np.int32))).update(mesh, prop, 1)
                        else:
                            face_properties.setdefault("bungie_face_global_material", FaceSet(np.full(num_faces, gmv, dtype=np.int32))).update(mesh, prop, face_gmv)
            case 'ladder':
                if props.get("bungie_ladder") is None:
                    face_properties.setdefault("bungie_ladder", FaceSet(np.full(num_faces, face_prop_defaults["bungie_ladder"], dtype=np.int32))).update(mesh, prop, int(prop.ladder))
            case 'slip_surface':
                if props.get("bungie_slip_surface") is None:
                    face_properties.setdefault("bungie_slip_surface", FaceSet(np.full(num_faces, face_prop_defaults["bungie_slip_surface"], dtype=np.int32))).update(mesh, prop, int(prop.slip_surface))
            case 'decal_offset':
                if props.get("bungie_decal_offset") is None:
                    face_properties.setdefault("bungie_decal_offset", FaceSet(np.full(num_faces, face_prop_defaults["bungie_decal_offset"], dtype=np.int32))).update(mesh, prop, int(prop.decal_offset))
            case 'no_shadow':
                if props.get("bungie_no_shadow") is None:
                    face_properties.setdefault("bungie_no_shadow", FaceSet(np.full(num_faces, face_prop_defaults["bungie_no_shadow"], dtype=np.int32))).update(mesh, prop, int(prop.no_shadow))
            case 'precise_position':
                if props.get("bungie_precise_position") is None:
                    face_properties.setdefault("bungie_precise_position", FaceSet(np.full(num_faces, face_prop_defaults["bungie_precise_position"], dtype=np.int32))).update(mesh, prop, int(prop.precise_position))
            case 'uncompressed':
                if props.get("bungie_mesh_use_uncompressed_verts") is None:
                    face_properties.setdefault("bungie_mesh_use_uncompressed_verts", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_use_uncompressed_verts"], dtype=np.int32))).update(mesh, prop, int(prop.uncompressed))
            case 'additional_compression':
                if props.get("bungie_mesh_additional_compression") is None:
                    face_properties.setdefault("bungie_mesh_additional_compression", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_additional_compression"], dtype=np.int32))).update(mesh, prop, AdditionalCompression[prop.additional_compression].value)
            case 'no_lightmap':
                if props.get("bungie_no_lightmap") is None:
                    face_properties.setdefault("bungie_no_lightmap", FaceSet(np.full(num_faces, face_prop_defaults["bungie_no_lightmap"], dtype=np.int32))).update(mesh, prop, int(prop.no_lightmap))
            case 'no_pvs':
                if props.get("bungie_invisible_to_pvs") is None:
                    face_properties.setdefault("bungie_invisible_to_pvs", FaceSet(np.full(num_faces, face_prop_defaults["bungie_invisible_to_pvs"], dtype=np.int32))).update(mesh, prop, int(prop.no_pvs))
            case 'mesh_tessellation_density':
                if props.get("bungie_mesh_tessellation_density") is None:
                    face_properties.setdefault("bungie_mesh_tessellation_density", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_tessellation_density"], dtype=np.int32))).update(mesh, prop, MeshTessellationDensity[prop.mesh_tessellation_density].value)
            case 'lightmap_resolution_scale':
                if props.get("bungie_lightmap_resolution_scale") is None:
                    face_properties.setdefault("bungie_lightmap_resolution_scale", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_resolution_scale"], dtype=np.int32))).update(mesh, prop, int(prop.lightmap_resolution_scale))
            case 'lightmap_ignore_default_resolution_scale':
                if props.get("bungie_lightmap_ignore_default_resolution_scale") is None and prop.lightmap_ignore_default_resolution_scale:
                    face_properties.setdefault("bungie_lightmap_ignore_default_resolution_scale", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_ignore_default_resolution_scale"], dtype=np.int32))).update(mesh, prop, 1)
            case 'lightmap_chart_group':
                if props.get("bungie_lightmap_chart_group") is None:
                    face_properties.setdefault("bungie_lightmap_chart_group", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_chart_group"], dtype=np.int32))).update(mesh, prop, prop.lightmap_chart_group)
            case 'lightmap_type':
                if props.get("bungie_lightmap_type") is None:
                    face_properties.setdefault("bungie_lightmap_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_type"], dtype=np.int32))).update(mesh, prop, LightmapType[prop.lightmap_type].value)
            case 'lightmap_additive_transparency':
                if props.get("bungie_lightmap_additive_transparency") is None:
                    face_properties.setdefault("bungie_lightmap_additive_transparency", FaceSet(np.full((num_faces, 3), face_prop_defaults["bungie_lightmap_additive_transparency"], dtype=np.single))).update(mesh, prop, utils.color_3p_int(prop.lightmap_additive_transparency))
            case 'lightmap_transparency_override':
                if props.get("bungie_lightmap_transparency_override") is None:
                    face_properties.setdefault("bungie_lightmap_transparency_override", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_transparency_override"], dtype=np.int32))).update(mesh, prop, int(prop.lightmap_transparency_override))
            case 'lightmap_analytical_bounce_modifier':
                if props.get("bungie_lightmap_analytical_bounce_modifier") is None:
                    face_properties.setdefault("bungie_lightmap_analytical_bounce_modifier", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_analytical_bounce_modifier"], dtype=np.single))).update(mesh, prop, prop.lightmap_analytical_bounce_modifier)
            case 'lightmap_general_bounce_modifier':
                if props.get("bungie_lightmap_general_bounce_modifier") is None:
                    face_properties.setdefault("bungie_lightmap_general_bounce_modifier", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_general_bounce_modifier"], dtype=np.single))).update(mesh, prop, prop.lightmap_general_bounce_modifier)
            case 'lightmap_translucency_tint_color':
                if props.get("bungie_lightmap_translucency_tint_color") is None:
                    face_properties.setdefault("bungie_lightmap_translucency_tint_color", FaceSet(np.full((num_faces, 3), face_prop_defaults["bungie_lightmap_translucency_tint_color"], dtype=np.single))).update(mesh, prop, utils.color_3p_int(prop.lightmap_translucency_tint_color))
            case 'lightmap_lighting_from_both_sides':
                if props.get("bungie_lightmap_lighting_from_both_sides") is None:
                    face_properties.setdefault("bungie_lightmap_lighting_from_both_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lightmap_lighting_from_both_sides"], dtype=np.int32))).update(mesh, prop, int(prop.lightmap_lighting_from_both_sides))
            case 'emissive':
                if props.get("bungie_lighting_emissive_power") is None and prop.material_lighting_emissive_power > 0:
                    power = max(prop.light_intensity, 0.0001)
                    if prop.material_lighting_attenuation_cutoff > 0:
                        falloff = prop.material_lighting_attenuation_falloff
                        cutoff = prop.material_lighting_attenuation_cutoff
                    else:
                        falloff, cutoff = calc_attenutation(prop.material_lighting_emissive_power * scene.unit_factor ** 2)
                    face_properties.setdefault("bungie_lighting_emissive_power", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_power"], np.single))).update(mesh, prop, power)
                    face_properties.setdefault("bungie_lighting_emissive_color", FaceSet(np.full((num_faces, 4), face_prop_defaults["bungie_lighting_emissive_color"], np.single))).update(mesh, prop, utils.color_4p_int(prop.material_lighting_emissive_color))
                    face_properties.setdefault("bungie_lighting_emissive_per_unit", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_per_unit"], dtype=np.int32))).update(mesh, prop, int(prop.material_lighting_emissive_per_unit))
                    face_properties.setdefault("bungie_lighting_emissive_quality", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_quality"], np.single))).update(mesh, prop, prop.material_lighting_emissive_quality)
                    face_properties.setdefault("bungie_lighting_use_shader_gel", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_use_shader_gel"], dtype=np.int32))).update(mesh, prop, int(prop.material_lighting_use_shader_gel))
                    face_properties.setdefault("bungie_lighting_bounce_ratio", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_bounce_ratio"], np.single))).update(mesh, prop, prop.material_lighting_bounce_ratio)
                    face_properties.setdefault("bungie_lighting_attenuation_enabled", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_attenuation_enabled"], dtype=np.int32))).update(mesh, prop, 1)
                    face_properties.setdefault("bungie_lighting_attenuation_cutoff", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_attenuation_cutoff"], np.single))).update(mesh, prop, cutoff * scene.atten_scalar * WU_SCALAR)
                    face_properties.setdefault("bungie_lighting_attenuation_falloff", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_attenuation_falloff"], np.single))).update(mesh, prop, falloff * scene.atten_scalar * WU_SCALAR)
                    face_properties.setdefault("bungie_lighting_emissive_focus", FaceSet(np.full(num_faces, face_prop_defaults["bungie_lighting_emissive_focus"], np.single))).update(mesh, prop, degrees(prop.material_lighting_emissive_focus) / 180)
                    
    if deferred_transparencies:
        transparent_indices = np.unique(np.concatenate([a for a in deferred_transparencies]))
        if deferred_opaques:
            opaque_indices = np.unique(np.concatenate([a for a in deferred_opaques]))
            mask = ~np.isin(transparent_indices, opaque_indices)
            transparent_indices = transparent_indices[mask]
            
        face_properties.setdefault("bungie_face_sides", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_sides"], dtype=np.int32))).update_from_material(mesh, transparent_indices, 1, additive=True)
                    
    for material, material_indices in special_mats_dict.items():
        if material.name.lower().startswith('+seamsealer') and props.get("bungie_face_type") is None:
            if scene.corinth:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_mode"], dtype=np.int32))).update_from_material(mesh, material_indices, FaceMode.collision_only.value)
                face_properties.setdefault("bungie_mesh_poop_collision_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_poop_collision_type"], dtype=np.int32))).update_from_material(mesh, material_indices, PoopCollisionType.invisible_wall.value)
            else:
                face_properties.setdefault("bungie_face_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_type"], dtype=np.int32))).update_from_material(mesh, material_indices, FaceType.seam_sealer.value)
        elif is_structure and material.name.lower().startswith('+seam') and props.get("bungie_mesh_type") != MeshType.seam.value:
            props.pop("bungie_mesh_type")
            face_properties.setdefault("bungie_mesh_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_type"], dtype=np.int32))).update_from_material(mesh, material_indices, MeshType.seam.value)
        elif material.name.lower().startswith('+'):
            if not is_structure and scene.corinth:
                face_properties.setdefault("bungie_face_mode", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_mode"], dtype=np.int32))).update_from_material(mesh, material_indices, FaceMode.collision_only.value)
                face_properties.setdefault("bungie_mesh_poop_collision_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_mesh_poop_collision_type"], dtype=np.int32))).update_from_material(mesh, material_indices, PoopCollisionType.invisible_wall.value)
            else:
                enum_val = FaceType.sky.value if (is_structure and scene.asset_type == AssetType.SCENARIO) else FaceType.seam_sealer.value
                if props.get("bungie_face_type") is None:
                    face_properties.setdefault("bungie_face_type", FaceSet(np.full(num_faces, face_prop_defaults["bungie_face_type"], dtype=np.int32))).update_from_material(mesh, material_indices, enum_val)
                
                if not scene.corinth and enum_val == FaceType.sky.value:
                    if len(material.name) > 4 and material.name[4].isdigit():
                        if len(material.name) > 5 and material.name[5].isdigit():
                            sky_index = int("".join(material.name[4:5]))
                        else:
                            sky_index = int(material.name[4])
                        if sky_index > 0 and props.get("bungie_sky_permutation_index") is None:
                            face_properties.setdefault("bungie_sky_permutation_index", FaceSet(np.zeros(num_faces, dtype=np.int32))).update_from_material(mesh, material_indices, sky_index)
                        
                        
    if force_render_only:
        existing_face_face_mode = face_properties.get("bungie_face_mode")
        if existing_face_face_mode is None:
            existing_mesh_face_mode = props.get("bungie_face_mode")
            if existing_mesh_face_mode is None or existing_mesh_face_mode in COLLISION_FACE_MODES:
                face_properties["bungie_face_mode"] = FaceSet(np.full(num_faces, FaceMode.render_only.value, np.int32))
        else:
            existing_face_face_mode.array = np.where(np.isin(existing_face_face_mode.array, COLLISION_FACE_MODES), FaceMode.render_only.value, existing_face_face_mode.array)

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
    
    return mesh_type in {MeshType.default.value, MeshType.poop.value, MeshType.object_instance.value, MeshType.water_surface.value, MeshType.decorator.value}

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