from ..exceptions import ExportCancelled
from collections import defaultdict
from enum import Enum
from math import degrees, isfinite
from pathlib import Path
import bpy
from mathutils import Euler

from ..tags.cinematic_lighting import CinematicLightingTag
from ..tags.cinematic_script import script_from_text

from ..tags.object_blender import ObjectTag
from ..tags.model_blender import ModelTag
from ..tags.animation_graph import AnimationGraphTag
from ..tags.cinematic_scene import CinematicCustomScript, CinematicDialogue, CinematicEffect, CinematicMusic, CinematicObjectFunctionKeyframe, NativeCinematicSceneTag
from ..tags.cinematic import CinematicSceneDataTag

from .. import utils
from ..tags.camera_track import camera_correction_matrix

# Blender DOF is lens based, while cinematic tags store linear blur ramps.
# These CoC thresholds give the ramp a photographic sharp point and a sane
# in-game blur cap without baking render-resolution-specific pixel sizes.
CINEMATIC_SHARP_COC_MM = 0.03
CINEMATIC_BLUR_CAP_COC_MM = 0.6
CINEMATIC_FAR_BLUR_TARGET_FRACTION = 0.95
MIN_CINEMATIC_FOCAL_DEPTH = 0.01

BANNED_FUNCTIONS = {
    'heat'
}

AMMO_FUNCTIONS = "primary_ammunition_ones", "primary_ammunition_tens"

class CinematicScene:
    def __init__(self, asset_path, scene_name, scene, scene_settings=None, asset_settings=None):
        nwo = scene.nwo if scene is not None else utils.get_scene_props() # scene specific
        transform_nwo = asset_settings or nwo
        self.name = scene_name
        self.scene = scene
        self.scene_settings = scene_settings
        self.path_no_ext = Path(asset_path, self.name)
        self.path = self.path_no_ext.with_suffix(".cinematic_scene")
        self.path_qua = Path(self.path_no_ext).with_suffix(".qua")
        self.anchor = nwo.cinematic_anchor # scene specific
        self.anchor_name = f"{self.name}_anchor"
        self.anchor_location = 0.0, 0.0, 0.0
        self.anchor_ypr = 0.0, 0.0, 0.0
        self.shots = []
        self.actor_animations = defaultdict(list)
        self.actors = []
        if self.anchor is not None:
            transform_scale = 0.03048 * utils.WU_SCALAR if transform_nwo.scale == 'max' else utils.WU_SCALAR
            rotation_offset = utils.blender_halo_rotation_diff(transform_nwo.forward_direction)
            anchor_matrix = utils.halo_transforms_matrix(self.anchor.matrix_world.inverted_safe(), transform_scale, rotation_offset)
            self.anchor_location = anchor_matrix.translation.to_tuple()
            rot = anchor_matrix.to_euler()
            rotation = Euler((rot.z, -rot.y, rot.x), 'ZYX')
            self.anchor_ypr = degrees(rotation.x - rotation_offset), degrees(rotation.y), degrees(rotation.z)
        
class CinematicDof:
    def __init__(self):
        self.enabled = False
        self.near_focal_plane_distance = 0
        self.far_focal_plane_distance = 0
        self.near_focal_depth = 0
        self.far_focal_depth = 0
        self.near_blur_amount = 0
        self.far_blur_amount = 0
        self.focal_depth = 0
        self.blur_amount = 0


def _cinematic_distance(distance: float, transform_scale: float = None) -> float:
    if not isfinite(distance):
        return 0
    distance = max(distance, 0)
    if transform_scale is None:
        return max(utils.halo_scale(distance) * 100, 0)
    return max(distance * transform_scale * 100, 0)

def _mm_to_scene_units(value: float) -> float:
    return value / 1000

def _focus_distance(camera: bpy.types.Object, data: bpy.types.Camera) -> float:
    if data.dof.focus_object:
        focus_object = data.dof.focus_object
        return (camera.matrix_world.translation - focus_object.matrix_world.translation).length
    return data.dof.focus_distance


def _circle_of_confusion(focal_length: float, focus_distance: float, aperture: float, object_distance: float) -> float:
    if focal_length <= 0 or aperture <= 0 or focus_distance <= focal_length or object_distance <= 0:
        return 0
    return abs(
        (focal_length * focal_length * (object_distance - focus_distance)) /
        (aperture * object_distance * (focus_distance - focal_length))
    )


def _infinity_circle_of_confusion(focal_length: float, focus_distance: float, aperture: float) -> float:
    if focal_length <= 0 or aperture <= 0 or focus_distance <= focal_length:
        return 0
    return (focal_length * focal_length) / (aperture * (focus_distance - focal_length))


def _distance_at_coc(focal_length: float, focus_distance: float, aperture: float, coc: float, near: bool) -> float:
    if focal_length <= 0 or aperture <= 0 or focus_distance <= focal_length or coc <= 0:
        return focus_distance

    ratio = (coc * aperture * (focus_distance - focal_length)) / (focal_length * focal_length)
    if near:
        return focus_distance / (1 + ratio)
    if ratio >= 1:
        return float("inf")
    return focus_distance / (1 - ratio)


def _game_blur_amount(coc: float) -> float:
    cap = _mm_to_scene_units(CINEMATIC_BLUR_CAP_COC_MM)
    if cap <= 0:
        return 0
    return max(min(coc / cap, 1), 0)


def calculate_focal_depths(focus_distance, aperture, coc=0.03, focal_length=50):
    focal_length = _mm_to_scene_units(focal_length)
    coc = _mm_to_scene_units(coc)
    focus_distance = max(focus_distance, focal_length * 1.001)
    near_depth = _distance_at_coc(focal_length, focus_distance, aperture, coc, True)
    far_depth = _distance_at_coc(focal_length, focus_distance, aperture, coc, False)
    return _cinematic_distance(near_depth), _cinematic_distance(far_depth)


def calculate_blur_amount(focal_length, focus_distance, aperture, object_distance, sensor_width):
    focal_length = _mm_to_scene_units(focal_length)
    return _game_blur_amount(_circle_of_confusion(focal_length, focus_distance, aperture, object_distance))


def calculate_focal_distances(camera):
    if not isinstance(camera.data, bpy.types.Camera):
        return None

    cam_data = camera.data
    if not cam_data.dof.use_dof:
        return 0, 0, 0

    lens = _mm_to_scene_units(cam_data.lens)
    aperture = cam_data.dof.aperture_fstop
    focus_distance = max(_focus_distance(camera, cam_data), lens * 1.001)
    coc = _mm_to_scene_units(CINEMATIC_SHARP_COC_MM)
    near_focus = _distance_at_coc(lens, focus_distance, aperture, coc, True)
    far_focus = _distance_at_coc(lens, focus_distance, aperture, coc, False)

    return near_focus, far_focus, focus_distance


def calculate_cinematic_dof(camera: bpy.types.Object, transform_scale: float = None) -> CinematicDof:
    dof = CinematicDof()
    data = camera.data
    data: bpy.types.Camera
    if not data.dof.use_dof:
        return dof

    aperture = data.dof.aperture_fstop
    lens = _mm_to_scene_units(data.lens)
    focus_distance = _focus_distance(camera, data)
    if aperture <= 0 or lens <= 0 or focus_distance <= 0:
        return dof

    focus_distance = max(focus_distance, lens * 1.001)
    clip_start = max(data.clip_start, 0.000001)
    clip_end = max(data.clip_end, focus_distance + 0.000001)
    sharp_coc = _mm_to_scene_units(CINEMATIC_SHARP_COC_MM)
    blur_cap_coc = _mm_to_scene_units(CINEMATIC_BLUR_CAP_COC_MM)

    near_focus = _distance_at_coc(lens, focus_distance, aperture, sharp_coc, True)
    far_focus = _distance_at_coc(lens, focus_distance, aperture, sharp_coc, False)
    far_blur_available = isfinite(far_focus)

    near_focus = min(max(near_focus, clip_start), clip_end)
    if not far_blur_available:
        far_focus = clip_end
    far_focus = min(max(far_focus, near_focus), clip_end)

    dof.enabled = True
    dof.near_focal_plane_distance = _cinematic_distance(near_focus, transform_scale)
    dof.far_focal_plane_distance = _cinematic_distance(far_focus, transform_scale)

    near_max_coc = _circle_of_confusion(lens, focus_distance, aperture, clip_start)
    if near_focus > clip_start and near_max_coc > sharp_coc:
        near_target_coc = min(near_max_coc, blur_cap_coc)
        near_full_blur = _distance_at_coc(lens, focus_distance, aperture, near_target_coc, True)
        near_full_blur = min(max(near_full_blur, clip_start), near_focus)
        dof.near_focal_depth = max(_cinematic_distance(near_focus - near_full_blur, transform_scale), MIN_CINEMATIC_FOCAL_DEPTH)
        dof.near_blur_amount = _game_blur_amount(near_target_coc)
    else:
        dof.near_focal_depth = MIN_CINEMATIC_FOCAL_DEPTH

    far_max_coc = _infinity_circle_of_confusion(lens, focus_distance, aperture)
    if far_focus < clip_end and far_max_coc > sharp_coc:
        if far_max_coc > blur_cap_coc:
            far_target_coc = blur_cap_coc
        else:
            far_target_coc = max(far_max_coc * CINEMATIC_FAR_BLUR_TARGET_FRACTION, sharp_coc)
        far_full_blur = _distance_at_coc(lens, focus_distance, aperture, far_target_coc, False)
        if not isfinite(far_full_blur):
            far_full_blur = clip_end
        far_full_blur = min(max(far_full_blur, far_focus), clip_end)
        dof.far_focal_depth = max(_cinematic_distance(far_full_blur - far_focus, transform_scale), MIN_CINEMATIC_FOCAL_DEPTH)
        dof.far_blur_amount = _game_blur_amount(far_target_coc)
    else:
        dof.far_focal_depth = MIN_CINEMATIC_FOCAL_DEPTH

    near_slope = dof.near_blur_amount / dof.near_focal_depth if dof.near_focal_depth else 0
    far_slope = dof.far_blur_amount / dof.far_focal_depth if dof.far_focal_depth else 0
    if near_slope > far_slope:
        dof.focal_depth = dof.near_focal_depth
        dof.blur_amount = dof.near_blur_amount
    else:
        dof.focal_depth = dof.far_focal_depth
        dof.blur_amount = dof.far_blur_amount

    return dof

class ActorLighting(Enum):
    NONE = 0
    PERSIST = 1
    PER_SHOT = 2

class Actor:
    def __init__(self, ob: bpy.types.Object, scene_name: str, asset_path: str, child_asset_name="", export_name=""):
        self.ob = ob
        self.name = utils.clean_text(export_name or ob.name, replace_spaces=True)
        self.original_tag = utils.relative_path(ob.nwo.cinematic_object)
        self.weapon_tag = None
        path_tag = Path(self.original_tag)
        
        tag_type = path_tag.suffix.lower()
        if tag_type in {'.scenery', '.biped'}:
            self.tag = self.original_tag
        else:
            self.tag = str(path_tag.with_suffix(".scenery"))
            if tag_type == ".weapon":
                self.weapon_tag = self.original_tag
        
        self.graph = str(Path(asset_path, "objects", scene_name, f"{self.name}.model_animation_graph"))
        if child_asset_name:
            self.sidecar = str(Path(asset_path, child_asset_name, "export", "models", self.name))
        else:
            self.sidecar = str(Path(asset_path, "export", "models", self.name))
        self.render_model = None
        self.bones: list = []
        self.shots_active = []
        self.shots_lightmap = []
        self.shots_high_res = []
        self.node_order = None
        self.variant = ob.nwo.cinematic_variant
        self.validation_complete = False
        self.lighting = ActorLighting[ob.nwo.cinematic_lighting]
        self.lighting_marker = utils.clean_text(ob.nwo.cinematic_lighting_marker)
        
    def validate(self) -> str | None:
        """Ensures that the tag will function for the cinematic. Returns a string with the reason for validation for failure, else None"""
        self.validation_complete = True
        tags_dir = utils.get_tags_path()
        object_path = Path(tags_dir, self.original_tag)
        # Check that there is an animation graph
        with ObjectTag(path=object_path) as obj:
            model_path = obj.get_model_tag_path_full()
            if model_path is None or not Path(model_path).exists():
                return f"Actor {self.name} has no valid model"
            with ModelTag(path=model_path) as model:
                if model.reference_render_model.Path is None or not Path(model.reference_render_model.Path.Filename).exists():
                    return f"Actor {self.name} has no valid render_model"
                if model.reference_animation.Path is None or not Path(model.reference_animation.Path.Filename).exists():
                    # No animation, so create on and add skeleton nodes so it is valid
                    graph_path = object_path.with_suffix(".model_animation_graph")
                    with AnimationGraphTag(path=graph_path, tag_must_exist=False) as graph:
                        cinematic_graph = Path(tags_dir, self.graph)
                        if not cinematic_graph.exists():
                            return f"Actor {self.name} has no cinematic animation graph"
                        with AnimationGraphTag(path=cinematic_graph) as cin_graph:
                            graph.copy_skeleton_from(cin_graph)
                        
                        model.reference_animation.Path = graph.tag_path
                        model.tag_has_changes = True
                            
            tag_type = object_path.suffix.lower()
            if tag_type in {'.scenery', '.biped'}:
                return # tag type is already okay for cinematics
            
            # Check if there is a scenery version of the actor tag
            scenery_path = object_path.with_suffix(".scenery")
            if not scenery_path.exists():
                # No scenery? lets create it
                with ObjectTag(path=scenery_path) as scenery:
                    scenery.copy_cinematic_object(obj, AMMO_FUNCTIONS)
                            
class ShotActor:
    def __init__(self, ob: bpy.types.Object, shot_index: int):
        self.ob = ob
        self.name = ob.name
        self.animation_name = f"{self.name}_{shot_index}"
    
class Frame:
    def __init__(self, ob: bpy.types.Object, corinth: bool, film_aperture: float, transform_scale: float = None, rotation: float = None):
        assert(ob.type == 'CAMERA')
        data = ob.data
        data: bpy.types.Camera
        blender_matrix = ob.matrix_world
        matrix = utils.halo_transforms_matrix(blender_matrix, transform_scale, rotation)
        dof = calculate_cinematic_dof(ob, transform_scale)
            
        self.position = matrix.translation.to_tuple()
        matrix_3x3 = matrix.to_3x3() @ camera_correction_matrix.inverted_safe()
        up = matrix_3x3.col[2]
        forward = matrix_3x3.col[0]
        self.up = up.normalized().to_tuple()
        self.forward = forward.normalized().to_tuple()
        # (game aperture from globals * blender focal length) / blender sensor width
        self.focal_length = (film_aperture * data.lens) / max(data.sensor_width, 0.000001)
        self.depth_of_field = int(dof.enabled)

        self.near_focal_plane_distance = dof.near_focal_plane_distance
        self.far_focal_plane_distance = dof.far_focal_plane_distance
        self.focal_depth = dof.focal_depth
        self.blur_amount = dof.blur_amount
        self.near_focal_depth = dof.near_focal_depth
        self.far_focal_depth = dof.far_focal_depth
        self.near_blur_amount = dof.near_blur_amount
        self.far_blur_amount = dof.far_blur_amount

    
class Effect:
    def __init__(self):
        pass

class Script: ...
    
class QUA:
    main_scene_version = 4
    audio_data_version = 3
    custom_script_version = 1
    effect_data_version = 4
    def __init__(self, asset_path, scene_name: str, shots: list, actors: list[Actor], corinth: bool, blender_scene: bpy.types.Scene, is_segment = False, preserve_unexported_shots=False):
        self.has_camera_data = not is_segment
        self.version = 4 if corinth else 2
        self.scene_type = "segment" if is_segment else "main"
        self.scene_name = scene_name
        self.objects = actors
        self.shots = shots
        self.extra_cameras = []
        self.corinth = corinth
        self.tag_path = Path(asset_path, scene_name)
        self.shot_counts = [shot.frame_count for shot in shots]
        self.blender_scene = blender_scene
        self.preserve_unexported_shots = preserve_unexported_shots

    def get_shot_index_and_frame(self, frame_index: int) -> tuple[int | None, int]:
        frame_base = int(self.corinth)
        shot_start = frame_base
        for idx, count in enumerate(self.shot_counts):
            shot_end = shot_start + count
            if shot_start <= frame_index < shot_end:
                return idx, frame_index - shot_start + frame_base
            
            shot_start = shot_end
        
        return None, 0
            
        
    # def write_to_file(self, path: Path):
    #     if not path.parent.exists():
    #         path.mkdir(parents=True, exist_ok=True)
    #     with open(path, "w") as file:
    #         self._write_version(file)
    #         if self.corinth:
    #             self._write_scene_type(file)
    #             self._write_main_scene_version(file)
    #         self._write_scene(file)
    #         self._write_shots_header(file)
    #         self._write_objects(file)
    #         self._write_shots(file)
    #         self._write_extra_cameras(file)   
        
    # def _write_version(self, file: TextIOWrapper):
    #     file.write(
    #         ";### VERSION ###\n"
    #         f"{self.version}\n\n"
    #     )
        
    # def _write_scene_type(self, file: TextIOWrapper):
    #     file.write(
    #         ";### SCENE TYPE ###\n"
    #         f"{self.scene_type}\n\n"
    #     )
        
    # def _write_main_scene_version(self, file: TextIOWrapper):
    #     file.write(
    #         ";### MAIN SCENE VERSION ###\n"
    #         f"{self.main_scene_version}\n\n"
    #     )
        
    # def _write_scene(self, file: TextIOWrapper):
    #     file.write(
    #         ";### SCENE ###\n"
    #         ";      <scene name (string)>\n"
    #         f"{self.scene_name}\n\n"
    #     )
        
    # def _write_shots_header(self, file: TextIOWrapper):
    #     file.write(
    #         ";### SHOTS ###\n"
    #         f"{len(self.shots)}\n\n"
    #     )
        
    # def _write_objects(self, file: TextIOWrapper):
    #     file.write(
    #         ";### OBJECTS ###\n"
    #         f"{len(self.objects)}\n"
    #         ";      <export name (string)>\n"
    #         ";      <animation id (string)>\n"
    #         ";      <animation graph tag path>\n"
    #         ";      <object type tag path>\n"
    #         ";      <shots visible (bit mask - sorta)>\n\n"
    #     )
    #     for actor in self.objects:
    #         file.write(
    #             f"; OBJECT {actor.name}\n"
    #             f"{actor.name}\n"
    #             f"{actor.name}\n"
    #             f"tags\{actor.graph}\n"
    #             f"tags\{actor.tag}\n"
    #             f"{actor.shot_bit_mask}\n\n"
    #         )
            
    # def _write_shots(self, file: TextIOWrapper):
    #     for idx, shot in enumerate(self.shots):
    #         shot_num = idx + 1
    #         if self.has_camera_data:
    #             self._write_shot_camera(file, shot, shot_num)
    #         self._write_shot_data(file, shot, shot_num)
                
    # def _write_shot_camera(self, file: TextIOWrapper, shot: Shot, shot_num: int):
    #     if self.corinth:
    #         file.write(
    #             f"; ### SHOT {shot_num} ###\n"
    #             ";          <Ubercam position (vector)>\n"
    #             ";          <Ubercam up (vector)>\n"
    #             ";          <Ubercam forward (vector)>\n"
    #             ";          <Focal Length (float)>\n"
    #             ";          <Depth of Field (bool)>\n"
    #             ";          <Near Focal Plane Distance (float)>\n"
    #             ";          <Far Focal Plane Distance (float)>\n"
    #             ";          <Near Focal Depth (float)>\n"
    #             ";          <Far Focal Depth (float)>\n"
    #             ";          <Near Blur Amount (float)>\n"
    #             ";          <Far Blur Amount (float)>\n"
    #             f"{len(shot.frames)}\n\n"
    #         )
    #         for idx, frame in enumerate(shot.frames):
    #             file.write(
    #                 f"; FRAME {idx + 1}\n"
    #                 f"{frame.position}\n"
    #                 f"{frame.up}\n"
    #                 f"{frame.forward}\n"
    #                 f"{frame.focal_length}\n"
    #                 f"{frame.depth_of_field}\n"
    #                 f"{frame.near_focal_plane_distance}\n"
    #                 f"{frame.far_focal_plane_distance}\n"
    #                 f"{frame.near_focal_depth}\n"
    #                 f"{frame.far_focal_depth}\n"
    #                 f"{frame.near_blur_amount}\n"
    #                 f"{frame.far_blur_amount}\n\n"
    #             )
    #     else:
    #         file.write(
    #             f"; ### SHOT {shot_num} ###\n"
    #             ";          <Ubercam position (vector)>\n"
    #             ";          <Ubercam up (vector)>\n"
    #             ";          <Ubercam forward (vector)>\n"
    #             ";          <Horizontal field of view (float)>\n"
    #             ";          <Horizontal film aperture (float, millimeters)>\n"
    #             ";          <Focal Length (float)>\n"
    #             ";          <Depth of Field (bool)>\n"
    #             ";          <Near Focal Plane Distance (float)>\n"
    #             ";          <Far Focal Plane Distance (float)>\n"
    #             ";          <Focal Depth (float)>\n"
    #             ";          <Blur Amount (float)>\n"
    #             f"{len(shot.frames)}\n\n"
    #         )
    #         for idx, frame in enumerate(shot.frames):
    #             file.write(
    #                 f"; FRAME {idx + 1}\n"
    #                 f"{frame.position}\n"
    #                 f"{frame.up}\n"
    #                 f"{frame.forward}\n"
    #                 f"{frame.horizontal_fov}\n"
    #                 f"{frame.horizontal_aperture}\n"
    #                 f"{frame.focal_length}\n"
    #                 f"{frame.depth_of_field}\n"
    #                 f"{frame.near_focal_plane_distance}\n"
    #                 f"{frame.far_focal_plane_distance}\n"
    #                 f"{frame.focal_depth}\n"
    #                 f"{frame.blur_amount}\n\n"
    #             )
    
    # def _write_shot_data(self, file: TextIOWrapper, shot: Shot, shot_num: int):
    #     if self.corinth:
    #         file.write(
    #             ";*** AUDIO DATA VERSION ***\n"
    #             f"{self.audio_data_version}\n\n"
    #         )
    #     file.write(
    #         f";*** SHOT {shot_num} AUDIO DATA ***\n"
    #         f"{len(shot.sounds)}\n"
    #         ";          <Sound tag (string)>\n"
    #         ";          <Female sound tag (string)>\n"
    #         ";          <Audio filename (string)>\n"
    #         ";          <Female audio filename (string)>\n"
    #         ";          <Frame number (int)>\n"
    #         ";          <Character (string)>\n"
    #         ";          <Dialog Color (string)>\n\n"
    #     )
    #     for sound in shot.sounds:
    #         file.write(
    #             f"{sound.sound_tag}\n"
    #             f"{sound.female_sound_tag}\n"
    #             f"{sound.audio_filename}\n"
    #             f"{sound.female_audio_filename}\n"
    #             f"{sound.frame_number}\n"
    #             f"{sound.character}\n"
    #             f"{sound.dialog_color}\n\n"
    #         )
        
    #     if self.corinth:
    #         file.write(
    #             ";*** CUSTOM SCRIPT DATA VERSION ***\n"
    #             f"{self.custom_script_version}\n\n"
    #         )
    #     file.write(
    #         f";*** SHOT {shot_num} CUSTOM SCRIPT DATA ***\n"
    #         f"{len(shot.scripts)}\n"
    #         f";          <Node ID (long)>\n"
    #         f";          <Sequence ID (long)>\n"
    #         f";          <Script (string)>\n"
    #         f";          <Frame number (int)>\n\n"
    #     )
    #     for script in shot.scripts:
    #         f"{script.node_id}\n"
    #         f"{script.sequence_id}\n"
    #         f"{script.string}\n"
    #         f"{script.frame_number}\n\n"
            
    #     if self.corinth:
    #         file.write(
    #             ";*** EFFECT DATA VERSION ***\n"
    #             f"{self.effect_data_version}\n\n"
    #         )
    #     file.write(
    #         f";*** SHOT {shot_num} EFFECT DATA ***\n"
    #         f"{len(shot.effects)}\n"
    #         f";          <Node ID (long)>\n"
    #         f";          <Sequence ID (long)>\n"
    #         f";          <Effect (string)>\n"
    #         f";          <Marker Name (string)>\n"
    #         f";          <Marker Parent (string)>\n"
    #         f";          <Frame number (int)>\n"
    #         f";          <Effect State (int)>\n"
    #         f";          <Size Scale (float)>\n"
    #         f";          <Function A (string)>\n"
    #         f";          <Function B (string)>\n"
    #         f";          <Looping (long)>\n\n"
    #     )
    #     for effect in shot.effects:
    #         f"{effect.node_id}\n"
    #         f"{effect.sequence_id}\n"
    #         f"{effect.effect}\n"
    #         f"{effect.marker_name}\n\n"
    #         f"{effect.marker_parent}\n\n"
            
    # def _write_extra_cameras(self, file: TextIOWrapper):
    #     file.write(
    #         ";### EXTRA CAMERAS ###\n"
    #         f"{len(self.extra_cameras)}\n"
    #         f";          <Camera name (string)>\n"
    #         f";          <Camera type (string)>\n\n"
    #     )
    #     for camera in self.extra_cameras:
    #         file.write(
    #             f"{camera.name}\n"
    #             f"{camera.type}\n\n"
    #         )
            
    def write_to_tag(self, cin_scene_settings, blender_scene: bpy.types.Scene = None):
        # scene specific

        scene_path = self.tag_path.with_suffix(".cinematic_scene")
        if self.preserve_unexported_shots and not Path(utils.get_tags_path(), scene_path).is_file():
            raise ExportCancelled('Export all shots before exporting only the current shot')
        data_path = self.tag_path.with_suffix(".cinematic_scene_data") if self.corinth else None
        header = script_from_text(self.corinth, cin_scene_settings.header,
                                  cin_scene_settings.header_text,
                                  cin_scene_settings.header_use_text)
        footer = script_from_text(self.corinth, cin_scene_settings.footer,
                                  cin_scene_settings.footer_text,
                                  cin_scene_settings.footer_use_text)
        music, function_keyframes, scripts, dialogue, effects, lighting = \
            self._collect_scene_events(blender_scene)
        if self.corinth:
            with NativeCinematicSceneTag(path=scene_path, tag_must_exist=False) as native_scene, \
                 CinematicSceneDataTag(path=data_path, tag_must_exist=False) as native_data:
                native_scene.write_export_header(
                    self.scene_name, cin_scene_settings.reset_object_lighting,
                    header, footer, data_path)
                native_scene.write_shot_settings(
                    self.shots, True, script_from_text, rebuild=not self.preserve_unexported_shots)
                native_scene.write_export_objects(
                    self.objects, script_from_text, native_data)
                native_scene.write_camera_events(self.shots, True, utils.game_frame)
                native_scene.write_timeline_events(
                    music, function_keyframes, self.get_shot_index_and_frame)
                native_scene.write_lighting_events(lighting)
                native_data.write_camera_frames(self.shots, True, rebuild=not self.preserve_unexported_shots)
                native_data.write_script_events(
                    scripts, self.get_shot_index_and_frame, True, script_from_text)
                native_data.write_content_events(
                    dialogue, effects, self.get_shot_index_and_frame)
        else:
            with NativeCinematicSceneTag(path=scene_path, tag_must_exist=False) as native_scene:
                native_scene.write_export_header(
                    self.scene_name, cin_scene_settings.reset_object_lighting,
                    header, footer)
                native_scene.write_export_objects(self.objects, script_from_text)
                native_scene.write_camera_shots(
                    self.shots, False, script_from_text, rebuild=not self.preserve_unexported_shots)
                native_scene.write_camera_events(self.shots, False, utils.game_frame)
                native_scene.write_timeline_events(
                    music, function_keyframes, self.get_shot_index_and_frame)
                native_scene.write_lighting_events(lighting)
                native_scene.write_script_events(
                    scripts, self.get_shot_index_and_frame, False, script_from_text)
                native_scene.write_content_events(
                    dialogue, effects, self.get_shot_index_and_frame)

    def _collect_scene_events(self, blender_scene):
        music = {}
        object_function_keyframes = {}
        dialogue = {}
        effects = {}
        custom_scripts = {}
        lighting_assignments = []

        object_tag_weapon_names = {}
        actor_attachment_names = {}
        actor_attachment_weapon_names = {}
        actor_objects = {actor.ob: actor.name for actor in self.objects}
        for actor_index, actor in enumerate(self.objects):
            actor_nwo = actor.ob.nwo
            if actor.weapon_tag is not None:
                object_tag_weapon_names[actor.ob] = f"{actor.name}_weapon"

            for index, attachment in enumerate(actor_nwo.attachments):
                attachment_type = attachment.attachment_type.strip()
                if not attachment_type:
                    continue
                attachment_type = utils.relative_path(attachment_type)
                attachment_base_name = Path(attachment_type).with_suffix("").name or "attachment"
                attachment_object_name = utils.clean_text(
                    f"{actor.name}_{attachment_base_name}_{index + 1}", replace_spaces=True)
                actor_attachments = actor_attachment_names.setdefault(actor.ob, {})
                actor_attachments[attachment.name or str(index + 1)] = attachment_object_name
                actor_attachments[f"ATTACHMENT_{index}"] = attachment_object_name
                actor_attachments[str(index + 1)] = attachment_object_name
                if index == 0:
                    actor_attachments["0"] = attachment_object_name
                if Path(attachment_type).suffix.lower() == ".weapon":
                    weapon_attachments = actor_attachment_weapon_names.setdefault(actor.ob, {})
                    weapon_attachments[attachment.name or str(index + 1)] = attachment_object_name
                    weapon_attachments[f"ATTACHMENT_{index}"] = attachment_object_name
                    weapon_attachments[str(index + 1)] = attachment_object_name
                    if index == 0:
                        weapon_attachments["0"] = attachment_object_name

            def add_lighting(shot_index, persist=False):
                lighting_name = f"{self.scene_name}_sh{shot_index + 1}_{actor.name}"
                lighting_path = Path(self.tag_path.parent, "lights", lighting_name)
                with CinematicLightingTag(path=lighting_path) as cinematic_lighting:
                    lighting_reference = cinematic_lighting.tag_path
                lighting_assignments.append((shot_index, actor_index,
                                             lighting_reference,
                                             actor.lighting_marker, persist))

            match actor.lighting:
                case ActorLighting.PERSIST:
                    if not self.shots:
                        raise ExportCancelled(f"{actor.name}: persistent lighting requires a shot")
                    add_lighting(0, True)
                case ActorLighting.PER_SHOT:
                    for shot_index in actor.shots_active:
                        add_lighting(shot_index)

        fps = blender_scene.render.fps / blender_scene.render.fps_base

        def game_frame(frame):
            return utils.round_int(frame * (30 / fps))

        frame_start = game_frame(int(blender_scene.frame_start))
        sound_sequences = {}
        if blender_scene.sequence_editor:
            sound_sequences = blender_scene.sequence_editor.strips_all
        for event in blender_scene.nwo.cinematic_events:
            frame = game_frame(event.frame)
            match event.type:
                case 'DIALOGUE':
                    item = CinematicDialogue()
                    item.from_event(event, actor_objects)
                    if item.dialogue is not None:
                        if event.sound_strip:
                            strip = sound_sequences.get(event.sound_strip)
                            if strip is not None:
                                frame = game_frame(int(strip.frame_start))
                        dialogue[item] = frame - frame_start + int(self.corinth)
                case 'EFFECT':
                    item = CinematicEffect()
                    item.from_event(event, actor_objects)
                    if item.effect is not None:
                        effects[item] = frame - frame_start + int(self.corinth)
                case 'SCRIPT':
                    item = CinematicCustomScript()
                    item.from_event(event, object_tag_weapon_names, actor_objects,
                                    self.corinth, actor_attachment_names,
                                    actor_attachment_weapon_names)
                    if item.script.strip():
                        frame_index = frame - frame_start + int(self.corinth)
                        custom_scripts[item] = frame_index
                        if (event.script_type == 'WEAPON_TRIGGER_START'
                                and not event.script_bool and item.weapon_name):
                            release = CinematicCustomScript()
                            release.set_weapon_trigger_script(item.weapon_name, False)
                            custom_scripts[release] = frame_index + 1
                case 'MUSIC':
                    item = CinematicMusic()
                    item.from_event(event)
                    if item.music is not None:
                        music[item] = frame - frame_start + int(self.corinth)
                case 'FUNCTION':
                    item = CinematicObjectFunctionKeyframe()
                    item.from_event(event, actor_objects)
                    if item.function_name:
                        object_function_keyframes[item] = (
                            frame - frame_start + int(self.corinth))

        return (music, object_function_keyframes, custom_scripts, dialogue,
                effects, lighting_assignments)
