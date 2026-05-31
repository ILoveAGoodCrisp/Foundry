from collections import defaultdict
from enum import Enum
from math import degrees, isfinite
from pathlib import Path
import bpy
from mathutils import Euler

from ..managed_blam.cinematic_lighting import CinematicLightingTag
from ..managed_blam.lisp_to_corinth import script_from_text

from ..managed_blam.object import ObjectTag
from ..managed_blam.model import ModelTag
from ..managed_blam.animation import AnimationTag
from ..managed_blam.cinematic_scene import CinematicClip, CinematicCustomScript, CinematicDialogue, CinematicEffect, CinematicLighting, CinematicMusic, CinematicObjectFunction, CinematicObjectFunctionKeyframe, CinematicScreenEffect, CinematicTextureMovie, CinematicUserInputConstraints

from ..managed_blam.Tags import TagFieldBlock

from ..managed_blam import Tag

from .. import utils
from ..managed_blam.camera_track import camera_correction_matrix

# Blender DOF is lens based, while cinematic tags store linear blur ramps.
# These CoC thresholds give the ramp a photographic sharp point and a sane
# in-game blur cap without baking render-resolution-specific pixel sizes.
CINEMATIC_SHARP_COC_MM = 0.03
CINEMATIC_BLUR_CAP_COC_MM = 0.6
CINEMATIC_FAR_BLUR_TARGET_FRACTION = 0.95
MIN_CINEMATIC_FOCAL_DEPTH = 0.01

SPECIAL_CASE_NAMES = "player0", "player1", "player2", "player3"

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
            model_tag_path = obj.reference_model.Path
            model_path = obj.get_model_tag_path_full()
            if model_path is None or not Path(model_path).exists():
                return f"Actor {self.name} has no valid model"
            with ModelTag(path=model_path) as model:
                if model.reference_render_model.Path is None or not Path(model.reference_render_model.Path.Filename).exists():
                    return f"Actor {self.name} has no valid render_model"
                if model.reference_animation.Path is None or not Path(model.reference_animation.Path.Filename).exists():
                    # No animation, so create on and add skeleton nodes so it is valid
                    graph_path = object_path.with_suffix(".model_animation_graph")
                    with AnimationTag(path=graph_path) as graph:
                        cinematic_graph = Path(tags_dir, self.graph)
                        if not cinematic_graph.exists():
                            return f"Actor {self.name} has no cinematic animation graph"
                        with AnimationTag(path=cinematic_graph) as cin_graph:
                            cin_graph.block_skeleton_nodes.CopyEntireTagBlock()
                            graph.block_skeleton_nodes.PasteReplaceEntireBlock()
                            graph.tag_has_changes = True
                        
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
                    scenery.reference_model.Path = model_tag_path
                    # Copy across important values
                    scenery_object = scenery.object_struct.Elements[0]
                    obj_object = obj.object_struct.Elements[0]
                    scenery_flags = scenery_object.SelectField("Flags:flags")
                    obj_flags = obj_object.SelectField("Flags:flags")
                    # set some flags which might affect render
                    scenery_flags.SetBit("does not cast shadow", obj_flags.TestBit("does not cast shadow"))
                    scenery_flags.SetBit("search cardinal direction lightmaps on failure", obj_flags.TestBit("search cardinal direction lightmaps on failure"))
                    scenery_flags.SetBit("object scales attachments", obj_flags.TestBit("object scales attachments"))
                    scenery_flags.SetBit("sample enviroment lighting only ignore object lighting", obj_flags.TestBit("sample enviroment lighting only ignore object lighting"))
                    # More stuff
                    scenery_object.SelectField("bounding radius").Data = obj_object.SelectField("bounding radius").Data
                    scenery_object.SelectField("bounding offset").Data = obj_object.SelectField("bounding offset").Data
                    scenery_object.SelectField("lightmap shadow mode").Value = obj_object.SelectField("lightmap shadow mode").Value
                    scenery_object.SelectField("sweetener size").Value = obj_object.SelectField("sweetener size").Value
                    scenery_object.SelectField("dynamic light sphere radius").Data = obj_object.SelectField("dynamic light sphere radius").Data
                    scenery_object.SelectField("dynamic light sphere offset").Data = obj_object.SelectField("dynamic light sphere offset").Data
                    scenery_object.SelectField("default model variant").Data = obj_object.SelectField("default model variant").Data
                    scenery_object.SelectField("crate object").Path = obj_object.SelectField("crate object").Path
                    scenery_object.SelectField("creation effect").Path = obj_object.SelectField("creation effect").Path
                    scenery_object.SelectField("material effects").Path = obj_object.SelectField("material effects").Path
                    scenery_object.SelectField("simulation_interpolation").Path = obj_object.SelectField("material effects").Path
                    # Copy tag blocks
                    obj_object.SelectField("functions").CopyEntireTagBlock()
                    funcs = scenery_object.SelectField("functions")
                    funcs.PasteReplaceEntireBlock()
                    # set all import names to zero so functions are script controlled
                    found_ones = False
                    found_tens = False
                    is_weapon = tag_type == '.weapon'
                    for e in funcs.Elements:
                        e.SelectField("import name").SetStringData("zero")
                        if is_weapon:
                            if e.SelectField("export name").GetStringData() == AMMO_FUNCTIONS[0]:
                                found_ones = True
                            elif e.SelectField("export name").GetStringData() == AMMO_FUNCTIONS[1]:
                                found_tens = True
                                
                    if is_weapon:
                        if not found_ones:
                            e = funcs.AddElement()
                            e.SelectField("import name").SetStringData("zero")
                            e.SelectField("export name").SetStringData(AMMO_FUNCTIONS[0])
                        if not found_tens:
                            e = funcs.AddElement()
                            e.SelectField("import name").SetStringData("zero")
                            e.SelectField("export name").SetStringData(AMMO_FUNCTIONS[1])
                
                    obj_object.SelectField("attachments").CopyEntireTagBlock()
                    scenery_object.SelectField("attachments").PasteReplaceEntireBlock()
                    obj_object.SelectField("hull surfaces").CopyEntireTagBlock()
                    scenery_object.SelectField("hull surfaces").PasteReplaceEntireBlock()
                    obj_object.SelectField("jetwash").CopyEntireTagBlock()
                    scenery_object.SelectField("jetwash").PasteReplaceEntireBlock()
                    obj_object.SelectField("widgets").CopyEntireTagBlock()
                    scenery_object.SelectField("widgets").PasteReplaceEntireBlock()
                    obj_object.SelectField("change colors").CopyEntireTagBlock()
                    scenery_object.SelectField("change colors").PasteReplaceEntireBlock()
                    obj_object.SelectField("spawn effects").CopyEntireTagBlock()
                    scenery_object.SelectField("spawn effects").PasteReplaceEntireBlock()
                    
                    scenery.tag_has_changes = True
                            
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
    def __init__(self, asset_path, scene_name: str, shots: list, actors: list[Actor], corinth: bool, blender_scene: bpy.types.Scene, is_segment = False):
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

    def get_shot_index_and_frame(self, frame_index: int) -> tuple[int | None, int]:
        current_frame_index = 0
        previous_frame_index = 0
        for idx, count in enumerate(self.shot_counts):
            current_frame_index += (count - 1)
            if frame_index <= current_frame_index and frame_index >= previous_frame_index:
                return idx, frame_index - previous_frame_index
            
            previous_frame_index = current_frame_index
        
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

        with Tag(path=self.tag_path.with_suffix(".cinematic_scene")) as scene:
            scene.tag.SelectField("StringId:name").SetStringData(self.scene_name)
            scene.tag.SelectField("StringId:anchor").SetStringData(f"{self.scene_name}_anchor")
            
            # other props
            scene.tag.SelectField("reset object lighting").Value = int(cin_scene_settings.reset_object_lighting)
            scene.tag.SelectField("struct:header").Elements[0].Fields[0].DataAsText = script_from_text(self.corinth, cin_scene_settings.header, cin_scene_settings.header_text, cin_scene_settings.header_use_text)
            scene.tag.SelectField("struct:footer").Elements[0].Fields[0].DataAsText = script_from_text(self.corinth, cin_scene_settings.footer, cin_scene_settings.footer_text, cin_scene_settings.footer_use_text)
            
            scene.tag_has_changes = True
            if self.corinth:
                with Tag(path=self.tag_path.with_suffix(".cinematic_scene_data")) as data:
                    scene.tag.SelectField("Reference:data").Path = data.tag_path
                    data.tag_has_changes = True
                    self._write_scene_data(blender_scene, data, scene.tag.SelectField("Block:objects"), scene.tag.SelectField("Block:shots"), data.tag.SelectField("Block:extra camera frame data"), data.tag.SelectField("Block:objects"), data.tag.SelectField("Block:shots"))
            else:
                self._write_scene_data(blender_scene, scene, scene.tag.SelectField("Block:objects"), scene.tag.SelectField("Block:shots"), scene.tag.SelectField("Block:extra camera frame data"))
            
    def _write_scene_data(self, blender_scene, tag, block_objects: TagFieldBlock, block_shots: TagFieldBlock, block_extra_camera: TagFieldBlock, block_data_objects: TagFieldBlock = None, block_data_shots: TagFieldBlock = None):
        # EXTRA CAMERAS TODO or perhaps never do? They may not work
        # Read existing data
        lighting = {}
        clips = {}
        music = {}
        object_function_keyframes = {}
        screen_effects = {}
        user_input_constraints = {}
        texture_movies = {}
        dialogue = {}
        effects: dict[CinematicEffect: int] = {}
        custom_scripts = {}
        current_frame_index = 0

        if self.corinth:
            elements_zip = zip(block_shots.Elements, block_data_shots.Elements)
            block_shots.RemoveAllElements()
            block_data_shots.RemoveAllElements()
        else:
            elements_zip = zip(block_shots.Elements, block_shots.Elements)
            block_shots.RemoveAllElements()
            
        
        # for element, data_element in elements_zip:
        #     block_dialogue = data_element.SelectField("dialogue")
        #     block_dialogue.RemoveAllElements()
            
        #     block_effects = data_element.SelectField("effects")
        #     for sub_element in block_effects.Elements:
        #         c = CinematicEffect()
        #         c.from_element(sub_element, block_objects, self.corinth)
        #         if not c.use_maya_value:
        #             effects[c] = current_frame_index + c.frame + int(self.corinth)
        #     block_effects.RemoveAllElements()
            
        #     block_custom_script = data_element.SelectField("custom script")
        #     for sub_element in block_custom_script.Elements:
        #         c = CinematicCustomScript()
        #         c.from_element(sub_element)
        #         if not c.use_maya_value:
        #             custom_scripts[c] = current_frame_index + c.frame + int(self.corinth)
        #     block_custom_script.RemoveAllElements()
        
        #     # dicts of element blocks and their overall scene frame
        #     block_lighting = element.SelectField("lighting")
        #     for sub_element in block_lighting.Elements:
        #         c = CinematicLighting()
        #         c.from_element(sub_element, block_objects)
        #         lighting[c] = element.ElementIndex # lighting only stores its shot index as it isn't bound to a frame
        #     block_lighting.RemoveAllElements()
            
        #     block_clip = element.SelectField("clip")
        #     for sub_element in block_clip.Elements:
        #         c = CinematicClip()
        #         c.from_element(sub_element, block_objects)
        #         clips[c] = current_frame_index + c.frame_start + int(self.corinth) # corinth uses index 1 for frames
        #     block_clip.RemoveAllElements()
            
        #     block_music = element.SelectField("music")
        #     for sub_element in block_music.Elements:
        #         c = CinematicMusic()
        #         c.from_element(sub_element)
        #         music[c] = current_frame_index + c.frame + int(self.corinth)
        #     block_music.RemoveAllElements()

        #     block_object_functions = element.SelectField("object functions")
        #     for sub_element in block_object_functions.Elements:
        #         c = CinematicObjectFunction()
        #         c.from_element(sub_element, block_objects)
        #         for keyframe in c.keyframes:
        #             object_function_keyframes[keyframe] = current_frame_index + keyframe.frame + int(self.corinth)
        #     block_object_functions.RemoveAllElements()

        #     block_screen_effects = element.SelectField("screen effects")
        #     for sub_element in block_screen_effects.Elements:
        #         c = CinematicScreenEffect()
        #         c.from_element(sub_element, self.corinth)
        #         screen_effects[c] = current_frame_index + c.frame + int(self.corinth)
        #     block_screen_effects.RemoveAllElements()

        #     block_user_input_constraints = element.SelectField("user input constraints")
        #     for sub_element in block_user_input_constraints.Elements:
        #         c = CinematicUserInputConstraints()
        #         c.from_element(sub_element)
        #         user_input_constraints[c] = current_frame_index + c.frame + int(self.corinth)
        #     block_user_input_constraints.RemoveAllElements()
            
        #     if self.corinth:
        #         block_texture_movies = element.SelectField("texture movies")
        #         for sub_element in block_texture_movies.Elements:
        #             c = CinematicTextureMovie()
        #             c.from_element(sub_element)
        #             texture_movies[c] = current_frame_index + c.frame + int(self.corinth)
        #         block_texture_movies.RemoveAllElements()
  
        #     current_frame_index += (data_element.SelectField("frame count").Data - 1)
            
        # SHOTS
        # make sure shots block is same size as shots count
        # while block_shots.Elements.Count > len(self.shots):
        #     block_shots.RemoveElement(block_shots.Elements.Count - 1)
        # while block_shots.Elements.Count < len(self.shots):
        #     block_shots.AddElement()
            
        # if self.corinth:
        #     while block_data_shots.Elements.Count > len(self.shots):
        #         block_data_shots.RemoveElement(block_data_shots.Elements.Count - 1)
        #     while block_data_shots.Elements.Count < len(self.shots):
        #         block_data_shots.AddElement()
                
        for idx, shot in enumerate(self.shots):
            if self.corinth:
                element = block_data_shots.AddElement()
                # element = block_data_shots.Elements[idx]
            else:
                element = block_shots.AddElement()
                # element = block_shots.Elements[idx]
                
            element.SelectField("frame count").Data = shot.frame_count
            frame_data = element.SelectField("frame data")
            # frame_data.RemoveAllElements()
            if not shot.frames:
                continue
            
            # SHOT SETTINGS
            camera_nwo = shot.camera.nwo
            element.SelectField("Struct:header").Elements[0].Fields[0].DataAsText = script_from_text(self.corinth, camera_nwo.header, camera_nwo.header_text, camera_nwo.header_use_text)
            element.SelectField("Struct:footer").Elements[0].Fields[0].DataAsText = script_from_text(self.corinth, camera_nwo.footer, camera_nwo.footer_text, camera_nwo.footer_use_text)
            element.SelectField("Real:environment darken").Data = camera_nwo.environment_darken
            element.SelectField("Real:forced exposure").Data = camera_nwo.forced_exposure
            shot_flags = element.SelectField("flags")
            shot_flags.SetBit("Instant Auto-Exposure", camera_nwo.instant_auto_exposure)
            shot_flags.SetBit("Force Exposure", camera_nwo.force_exposure)
            shot_flags.SetBit("Generate Looping Script", camera_nwo.generate_looping_script)
            if self.corinth:
                settings_flags = element.SelectField("settings flags")
                
                def flag_set(name, option):
                    match option:
                        case 'CLEAR':
                            settings_flags.SetBit(f"{name} - clear", True)
                        case 'PERSIST':
                            settings_flags.SetBit(f"{name} - persist across shots", True)
                
                if camera_nwo.lightmap_direct_scalar != 1.0:
                    settings_flags.SetBit("Lightmap Scalars - set", True)
                    element.SelectField("Lightmap Direct Scalar").Data = camera_nwo.lightmap_direct_scalar
                    
                if camera_nwo.lightmap_indirect_scalar != 1.0:
                    settings_flags.SetBit("Lightmap Scalars - set", True)
                    element.SelectField("Lightmap Indirect Scalar").Data = camera_nwo.lightmap_indirect_scalar
                    
                flag_set("Lightmap Scalars", camera_nwo.lightmap_scalar_option)
                
                if camera_nwo.sun_scalar != 1.0:
                    settings_flags.SetBit("Sun Scalar - set", True)
                    element.SelectField("Sun Scalar").Data = camera_nwo.sun_scalar

                flag_set("Sun Scalar", camera_nwo.sun_scalar_option)
                
                if camera_nwo.atmosphere_fog.strip():
                    element.SelectField("Atmosphere Fog").Path = tag._TagPath_from_string(camera_nwo.atmosphere_fog)
                if camera_nwo.camera_effects.strip():
                    element.SelectField("Camera Effects").Path = tag._TagPath_from_string(camera_nwo.camera_effects)
                if camera_nwo.cubemap.strip():
                    element.SelectField("Cubemap").Path = tag._TagPath_from_string(camera_nwo.cubemap)
                    
                flag_set("Atmosphere Fog", camera_nwo.atmosphere_fog_option)
                flag_set("Camera Effects", camera_nwo.camera_effects_option)
                flag_set("Cubemap", camera_nwo.cubemap_option)
                
                settings_flags.SetBit("Disable All Lightmap Shadows", camera_nwo.disable_all_lightmap_shadows)
                
            # CAMERA EVENTS
            if camera_nwo.screen_effect.strip():
                c = CinematicScreenEffect()
                c.from_camera(camera_nwo, shot.frame_count - 1, self.corinth)
                screen_effects[c] = shot.frame_start + int(self.corinth)
                
            if camera_nwo.user_input_bounds_t != 0.0 or camera_nwo.user_input_bounds_l != 0.0 or camera_nwo.user_input_bounds_b != 0.0 or camera_nwo.user_input_bounds_r != 0.0:
                c = CinematicUserInputConstraints()
                c.from_camera(camera_nwo, self.corinth)
                user_input_constraints[c] = shot.frame_start + int(self.corinth)

            # FRAME DATA
            if self.corinth:
                for frame in shot.frames:
                    felement = frame_data.AddElement()
                    felement.SelectField("Struct:camera frame[0]/Struct:dynamic data[0]/RealPoint3d:camera position").Data = frame.position
                    felement.SelectField("Struct:camera frame[0]/Struct:dynamic data[0]/RealVector3d:camera forward").Data = frame.forward
                    felement.SelectField("Struct:camera frame[0]/Struct:dynamic data[0]/RealVector3d:camera up").Data = frame.up
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:focal length").Data = frame.focal_length
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/LongInteger:depth of field").Data = frame.depth_of_field
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:near focal plane distance").Data = frame.near_focal_plane_distance
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:far focal plane distance").Data = frame.far_focal_plane_distance
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:near focal depth").Data = frame.near_focal_depth
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:far focal depth").Data = frame.far_focal_depth
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:near blur amount").Data = frame.near_blur_amount
                    felement.SelectField("Struct:camera frame[0]/Struct:constant data[0]/Real:far blur amount").Data = frame.far_blur_amount
            else:
                for frame in shot.frames:
                    felement = frame_data.AddElement()
                    felement.SelectField("Struct:camera frame[0]/RealPoint3d:camera position").Data = frame.position
                    felement.SelectField("Struct:camera frame[0]/RealVector3d:camera forward").Data = frame.forward
                    felement.SelectField("Struct:camera frame[0]/RealVector3d:camera up").Data = frame.up
                    felement.SelectField("Struct:camera frame[0]/Real:focal length").Data = frame.focal_length
                    felement.SelectField("Struct:camera frame[0]/LongInteger:depth of field").Data = frame.depth_of_field
                    felement.SelectField("Struct:camera frame[0]/Real:near focal plane distance").Data = frame.near_focal_plane_distance
                    felement.SelectField("Struct:camera frame[0]/Real:far focal plane distance").Data = frame.far_focal_plane_distance
                    felement.SelectField("Struct:camera frame[0]/Real:focal depth").Data = frame.focal_depth
                    felement.SelectField("Struct:camera frame[0]/Real:blur amount").Data = frame.blur_amount
        
        # OBJECTS
        # to_remove_object_element_indexes = []
        # Loop through elements and assign actors where they already exist, else mark them for deletion
        # for element in block_objects.Elements:
        #     for actor in self.objects:
        #         if actor.name == element.SelectField("name").GetStringData():
        #             actor_elements[actor] = element
        #             break
        #     else:
        #         to_remove_object_element_indexes.append(element.ElementIndex)
        
        # Remove any elements that don't have a valid actor
        # for idx in reversed(to_remove_object_element_indexes):
        #     block_objects.RemoveElement(idx)
        
        def add_actor_attachment(block_attachments, invisible: bool, marker_name: str, object_name: str, attachment_marker_name: str, attachment_type: str):
            attachment_element = block_attachments.AddElement()
            attachment_element.SelectField("flags").SetBit("invisible", invisible)
            attachment_element.SelectField("object marker name").SetStringData(marker_name)
            attachment_element.SelectField("attachment object name").SetStringData(object_name)
            attachment_element.SelectField("attachment marker name").SetStringData(attachment_marker_name)
            attachment_element.SelectField("attachment type").Path = tag._TagPath_from_string(attachment_type)

        def attachment_can_fire_weapon(attachment_type: str) -> bool:
            if Path(attachment_type).suffix.lower() == ".weapon":
                return True

            weapon_path = Path(utils.get_tags_path(), attachment_type).with_suffix(".weapon")
            return weapon_path.exists() and weapon_path.is_file()

        object_tag_weapon_names = {} # used for custom scripts
        actor_attachment_names = {} # used for custom scripts
        actor_attachment_weapon_names = {} # used for weapon trigger scripts
        actor_objects = {a.ob: a.name for a in self.objects} # for checking an event is valid
        block_objects.RemoveAllElements()
        # Add elements for actors without them
        for actor in self.objects:
            element = block_objects.AddElement()
            element.SelectField("name").SetStringData(actor.name)
            element.SelectField("variant name").SetStringData(actor.variant)
            actor_nwo = actor.ob.nwo
            block_attachments = element.SelectField("Block:attachments")
            if actor.weapon_tag is not None:
                wep_name = f"{actor.name}_weapon"
                add_actor_attachment(block_attachments, True, "primary_trigger", wep_name, "primary_trigger", actor.weapon_tag)
                object_tag_weapon_names[actor.ob] = wep_name

            for index, attachment in enumerate(actor_nwo.attachments):
                attachment_type = attachment.attachment_type.strip()
                if not attachment_type:
                    continue

                attachment_type = utils.relative_path(attachment_type)
                marker_name = utils.clean_text(attachment.marker_name, empty_string_allowed=True)
                attachment_marker_name = utils.clean_text(attachment.attachment_marker_name or attachment.marker_name, empty_string_allowed=True)
                attachment_base_name = Path(attachment_type).with_suffix("").name or "attachment"
                attachment_object_name = utils.clean_text(f"{actor.name}_{attachment_base_name}_{index + 1}", replace_spaces=True)
                add_actor_attachment(block_attachments, attachment.invisible, marker_name, attachment_object_name, attachment_marker_name, attachment_type)
                actor_attachments = actor_attachment_names.setdefault(actor.ob, {})
                actor_attachments[attachment.name or str(index + 1)] = attachment_object_name
                actor_attachments[f"ATTACHMENT_{index}"] = attachment_object_name
                actor_attachments[str(index + 1)] = attachment_object_name
                if index == 0:
                    actor_attachments["0"] = attachment_object_name
                if attachment_can_fire_weapon(attachment_type):
                    actor_weapon_attachments = actor_attachment_weapon_names.setdefault(actor.ob, {})
                    actor_weapon_attachments[attachment.name or str(index + 1)] = attachment_object_name
                    actor_weapon_attachments[f"ATTACHMENT_{index}"] = attachment_object_name
                    actor_weapon_attachments[str(index + 1)] = attachment_object_name
                    if index == 0:
                        actor_weapon_attachments["0"] = attachment_object_name

            # Set flags
            actor_flags = element.SelectField("flags")
            
            if actor.name in SPECIAL_CASE_NAMES:
                actor_flags.SetBit("Special Case (like player0)", True)
            else:
                match actor_nwo.object_source:
                    case 'CREATE_ANEW':
                        actor_flags.SetBit("Placed Manually in Sapien", True)
                    case 'USE':
                        actor_flags.SetBit("Object Comes From Game", True)
                        
            actor_flags.SetBit("Effect Object", actor_nwo.effect_object)
            actor_flags.SetBit("No Lightmap Shadow", actor_nwo.no_lightmap_shadow)
            actor_flags.SetBit("Apply Player Customization", actor_nwo.apply_player_customization)
            actor_flags.SetBit("Apply First Person Player Customization", actor_nwo.apply_first_person_player_customization)
            actor_flags.SetBit("I will animate the English lipsync manually", actor_nwo.english_lipsync_manual)
            
            override_flags = element.SelectField("override creation flags")
            override_flags.SetBit("single player", (not actor_nwo.override_1_player))
            override_flags.SetBit("2 player co-op", (not actor_nwo.override_2_player))
            override_flags.SetBit("3 player co-op", (not actor_nwo.override_3_player))
            override_flags.SetBit("4 player co-op", (not actor_nwo.override_4_player))
            
            element.SelectField("custom don't create condition").Elements[0].Fields[0].DataAsText = script_from_text(self.corinth, actor_nwo.override_script, actor_nwo.override_script_text, actor_nwo.override_script_use_text)
            
            if self.corinth:
                actor_flags.SetBit("Primary Cortana", actor_nwo.primary_cortana)
                actor_flags.SetBit("Preload Textures", actor_nwo.preload_textures)
                
                lightmap_flags = element.SelectField("lightmap shadow flags")
                lightmap_flags.RefreshShots()
                lightmap_flags.ClearShots()
                for idx in actor.shots_lightmap:
                    lightmap_flags.SetShotChecked(idx, True)
        
                high_res_flags = element.SelectField("high res flags")
                high_res_flags.RefreshShots()
                high_res_flags.ClearShots()
                for idx in actor.shots_high_res:
                    high_res_flags.SetShotChecked(idx, True)
                
                block_data_objects.RemoveAllElements()
                for actor in self.objects:
                    data_element = block_data_objects.AddElement()
                    data_element.SelectField("name").SetStringData(actor.name)
                    data_element.SelectField("identifier").SetStringData(actor.name)
                    data_element.SelectField("model animation graph").Path = tag._TagPath_from_string(actor.graph)
                    data_element.SelectField("object type").Path = tag._TagPath_from_string(actor.tag)
                    shot_flags = data_element.SelectField("shots active flags")
                    shot_flags.RefreshShots() # shots won't register unless we call this
                    shot_flags.ClearShots()
                    for idx in actor.shots_active:
                        shot_flags.SetShotChecked(idx, True) # SetShotChecked is part of TagFieldCustomCinematicShotFlags, which is not used by Reach
            
            else:
                # Reach writes this data to the cinematic_scene tag so lets do it now
                element.SelectField("identifier").SetStringData(actor.name)
                element.SelectField("model animation graph").Path = tag._TagPath_from_string(actor.graph)
                element.SelectField("object type").Path = tag._TagPath_from_string(actor.tag)
                flag_items = element.SelectField("shots active flags").Items
                for item in flag_items:
                    item.IsSet = False
                for idx in actor.shots_active:
                    flag_items[idx].IsSet = True
                    
                lightmap_flag_items = element.SelectField("lightmap shadow flags").Items
                for item in lightmap_flag_items:
                    item.IsSet = False
                for idx in actor.shots_lightmap:
                    lightmap_flag_items[idx].IsSet = True
                    
                    
            def setup_lighting_element(lighting_element, shot_index: int, persist=False):
                lighting_name = f"{self.scene_name}_sh{shot_index + 1}_{actor.name}"
                lighting_path = Path(self.tag_path.parent, "lights", lighting_name)
                with CinematicLightingTag(path=lighting_path) as cin_lighting:
                    lighting_element.SelectField("lighting").Path = cin_lighting.tag_path
                lighting_element.SelectField("flags").SetBit("persists across shots", persist)
                lighting_element.SelectField("marker").SetStringData(actor.lighting_marker)
                lighting_element.SelectField("subject").Value = element.ElementIndex

            # Add actor lighting
            match actor.lighting:
                case ActorLighting.PERSIST:
                    first_shot_element = block_data_shots.Elements[0] if self.corinth else block_shots.Elements[0]
                    setup_lighting_element(first_shot_element.SelectField("lighting").AddElement(), first_shot_element.ElementIndex, True)
                case ActorLighting.PER_SHOT:
                    for shot_i in actor.shots_active:
                        next_shot_element = block_data_shots.Elements[shot_i] if self.corinth else block_shots.Elements[shot_i]
                        setup_lighting_element(next_shot_element.SelectField("lighting").AddElement(), next_shot_element.ElementIndex)
 
        # Add cinematic events
        
        fps = blender_scene.render.fps / blender_scene.render.fps_base

        def game_frame(frame: int):
            return utils.round_int(frame * (30 / fps))

        frame_start = game_frame(int(blender_scene.frame_start))
        sound_sequences = {}
        if blender_scene.sequence_editor:
            sound_sequences = blender_scene.sequence_editor.strips_all
        for event in blender_scene.nwo.cinematic_events:
            frame = game_frame(event.frame)
            match event.type:
                case 'DIALOGUE':
                    c = CinematicDialogue()
                    c.from_event(event, actor_objects)
                    if c.dialogue is not None:
                        if event.sound_strip:
                            strip = sound_sequences.get(event.sound_strip)
                            if strip is not None:
                                frame = game_frame(int(strip.frame_start))
                        dialogue[c] = frame - frame_start + int(self.corinth)
                case 'EFFECT':
                    c = CinematicEffect()
                    c.from_event(event, actor_objects)
                    if c.effect is not None:
                        effects[c] = frame - frame_start + int(self.corinth)
                case 'SCRIPT':
                    c = CinematicCustomScript()
                    c.from_event(event, object_tag_weapon_names, actor_objects, self.corinth, actor_attachment_names, actor_attachment_weapon_names)
                    if c.script.strip():
                        custom_scripts[c] = frame - frame_start + int(self.corinth)         
                case 'MUSIC':
                    c = CinematicMusic()
                    c.from_event(event)
                    if c.music is not None:
                        music[c] = frame - frame_start + int(self.corinth)
                case 'FUNCTION':
                    c = CinematicObjectFunctionKeyframe()
                    c.from_event(event, actor_objects)
                    if c.function_name:
                        object_function_keyframes[c] = frame - frame_start + int(self.corinth)
        
        
        
        # Add back data blocks
        # Dialogue comes from blender
        block = block_shots
        
        # for data, shot_index in lighting.items():
        #     shot_element = block.Elements[shot_index]
        #     data.to_element(shot_element.SelectField("lighting").AddElement(), block_objects)
            
        # for data, frame_index in clips.items():
        #     shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
        #     if shot_index is None:
        #         continue
        #     shot_element = block.Elements[shot_index]
        #     end_offset = data.frame_end - data.frame_start
        #     data.frame_start = shot_frame
        #     data.frame_end = shot_frame + end_offset
        #     data.to_element(shot_element.SelectField("clip").AddElement(), block_objects)
            
        for data, frame_index in music.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("music").AddElement())
        
        
        function_keyframe_groups = defaultdict(list)
        for data, frame_index in object_function_keyframes.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            
            function_keyframe_groups[(shot_index, data.function_name, data.object)].append((data, shot_frame))
            
        for k, v in function_keyframe_groups.items():
            shot_index, function_name, object_name = k
            object_function = CinematicObjectFunction()
            object_function.object = object_name
            object_function.function_name = function_name
            for data, shot_frame in v:
                object_function.keyframes[shot_frame] = data
            
            shot_element = block.Elements[shot_index]
            object_function.to_element(shot_element.SelectField("object functions").AddElement(), block_objects)
            
        for data, frame_index in screen_effects.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.to_element(shot_element.SelectField("screen effects").AddElement(), self.corinth)
            
        for data, frame_index in user_input_constraints.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("user input constraints").AddElement())
        
        # if self.corinth:
        #     for data, frame_index in texture_movies.items():
        #         shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
        #         if shot_index is None:
        #             continue
        #         shot_element = block.Elements[shot_index]
        #         data.frame = shot_frame
        #         data.to_element(shot_element.SelectField("texture movies").AddElement())
        
        if self.corinth:
            block = block_data_shots
            
        for data, frame_index in dialogue.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("dialogue").AddElement())
            
        for data, frame_index in effects.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("effects").AddElement(), block_objects, self.corinth)
            
        for data, frame_index in custom_scripts.items():
            if data.script:
                shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
                if shot_index is None:
                    continue
                shot_element = block.Elements[shot_index]
                data.frame = shot_frame
                data.to_element(shot_element.SelectField("custom script").AddElement(), self.corinth)
