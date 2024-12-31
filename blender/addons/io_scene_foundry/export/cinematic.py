from io import TextIOWrapper
from pathlib import Path
import bpy

from .. import utils
from ..managed_blam.camera_track import camera_correction_matrix

class CinematicScene:
    def __init__(self, asset_path, asset_name, scene: bpy.types.Scene):
        self.name = f"{asset_name}_000"
        self.path_no_ext = Path(asset_path, self.name)
        self.path = self.path_no_ext.with_suffix(".cinematic_scene")
        self.path_qua = Path(self.path_no_ext).with_suffix(".qua")
        self.anchor = scene.nwo.cinematic_anchor
        self.anchor_name = f"{self.name}_anchor"
        self.anchor_location = 0.0, 0.0, 0.0
        self.anchor_yaw_pitch = 0.0, 0.0
        if self.anchor is not None:
            anchor_matrix = utils.halo_transforms_matrix(self.anchor.matrix_world.inverted())
            self.anchor_location = anchor_matrix.translation.to_tuple()
            matrix_3x3 = anchor_matrix.normalized().to_3x3()
            forward = matrix_3x3.col[0]
            left = matrix_3x3.col[1]
            up = matrix_3x3.col[2]
            yaw, pitch, roll = utils.ypr_from_flu(forward, left, up)
            self.anchor_yaw_pitch = yaw - 180, pitch
        
def calculate_focal_depths(focus_distance, aperture, coc=0.03, focal_length=50):
    """
    Calculate near and far focal depths based on depth of field parameters.

    Parameters:
    - focus_distance (float): The focus distance in Blender units.
    - aperture (float): The f-stop value.
    - coc (float): Circle of confusion size (default is a typical value for full-frame).
    - focal_length (float): Focal length of the camera lens in mm (default 50mm).

    Returns:
    - near_depth (float): Near focal depth.
    - far_depth (float): Far focal depth.
    """
    hyperfocal = (focal_length ** 2) / (aperture * coc)
    near_depth = (hyperfocal * focus_distance) / (hyperfocal + (focus_distance - focal_length))
    far_depth = (hyperfocal * focus_distance) / (hyperfocal - (focus_distance - focal_length))
    
    # Ensure far depth doesn't go negative for short focus distances
    far_depth = max(far_depth, focus_distance)
    
    return near_depth, far_depth

def calculate_blur_amount(focal_length, focus_distance, aperture, object_distance, sensor_width):
    """
    Calculate the blur amount (CoC size) for a given object distance.

    Parameters:
    - focal_length (float): Focal length of the camera lens (mm).
    - focus_distance (float): Focus distance (Blender units).
    - aperture (float): Aperture f-stop value.
    - object_distance (float): Distance to the object (Blender units).
    - sensor_width (float): Sensor width (mm).

    Returns:
    - blur_amount (float): Circle of confusion (CoC) size.
    """
    hyperfocal = (focal_length ** 2) / (aperture * (sensor_width / 43.27))
    coc = abs(
        (focal_length * (object_distance - focus_distance)) /
        (object_distance * (focus_distance - focal_length))
    ) * (focal_length / hyperfocal)

    return coc

class Actor:
    def __init__(self, ob: bpy.types.Object, scene_name: str, asset_path: str):
        self.ob = ob
        if "." in ob.name:
            ob.name = ob.name.replace(".", "_")
        self.name = ob.name
        self.tag = ob.nwo.cinematic_object
        self.graph = str(Path(asset_path, "objects", scene_name, f"{ob.name}.model_animation_graph"))
        self.sidecar = str(Path(asset_path, "export", "models", self.name))
        self.bones: list = []
        self.shot_bit_mask = None
        self.node_order = None
        
    def set_shot_bit_mask(self, shot_count: int):
        self.shot_bit_mask = " ".join(str(int(getattr(self.ob.nwo, f"shot_{i + 1}"))) for i in range(shot_count))

class ShotActor:
    def __init__(self, ob: bpy.types.Object, shot_index: int):
        self.ob = ob
        self.name = ob.name
        self.animation_name = f"{self.name}_{shot_index}"
    
class Shot: ...
    
class Frame:
    def __init__(self, ob: bpy.types.Object, corinth: bool):
        assert(ob.type == 'CAMERA')
        data = ob.data
        data: bpy.types.Camera
        blender_matrix = ob.matrix_world
        if corinth:
            matrix = utils.maya_transform_matrix(blender_matrix)
        else:
            matrix = utils.halo_transform_matrix(blender_matrix)
            
        focus_distance = data.dof.focus_distance
        aperture = data.dof.aperture_fstop
        focal_length = data.lens  # Focal length in mm
            
        self.position = utils.vector_str(matrix.translation * 100)
        matrix_3x3 = matrix.to_3x3() @ camera_correction_matrix.inverted()
        self.up = utils.vector_str(matrix_3x3.col[2])
        self.forward = utils.vector_str(matrix_3x3.col[0])
        self.horizontal_fov = 0.6911112070083618
        self.horizontal_aperture = 36
        self.focal_length = str(focal_length)
        self.depth_of_field = str(int(data.dof.use_dof))
        self.near_focal_plane_distance = str(data.clip_start) # not clip
        self.far_focal_plane_distance = str(data.clip_end) # not clip
        
        self.focal_depth = str(focus_distance)
        
        near, far = calculate_focal_depths(focus_distance, aperture, focal_length=focal_length)

        self.near_focal_depth = str(near)
        self.far_focal_depth = str(far)
        
        self.blur_amount = data.dof.aperture_ratio
        
        sensor_width = data.sensor_width
        
        near_blur = calculate_blur_amount(focal_length, focus_distance, aperture, data.clip_start, sensor_width)
        far_blur = calculate_blur_amount(focal_length, focus_distance, aperture, data.clip_end, sensor_width)
        
        self.near_blur_amount = str(near_blur)
        self.far_blur_amount = str(far_blur)

    
class Effect:
    def __init__(self):
        pass

class Script: ...
    
class QUA:
    main_scene_version = 4
    audio_data_version = 3
    custom_script_version = 1
    effect_data_version = 4
    def __init__(self, scene_name: str, shots, actors: list[Actor], corinth: bool, is_segment = False):
        self.has_camera_data = not is_segment
        self.version = 4 if corinth else 2
        self.scene_type = "segment" if is_segment else "main"
        self.scene_name = scene_name
        self.objects = actors
        self.shots = shots
        self.extra_cameras = []
        self.corinth = corinth
        
    def write_to_file(self, path: Path):
        if not path.parent.exists():
            path.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as file:
            self._write_version(file)
            if self.corinth:
                self._write_scene_type(file)
                self._write_main_scene_version(file)
            self._write_scene(file)
            self._write_shots_header(file)
            self._write_objects(file)
            self._write_shots(file)
            self._write_extra_cameras(file)   
        
    def _write_version(self, file: TextIOWrapper):
        file.write(
            ";### VERSION ###\n"
            f"{self.version}\n\n"
        )
        
    def _write_scene_type(self, file: TextIOWrapper):
        file.write(
            ";### SCENE TYPE ###\n"
            f"{self.scene_type}\n\n"
        )
        
    def _write_main_scene_version(self, file: TextIOWrapper):
        file.write(
            ";### MAIN SCENE VERSION ###\n"
            f"{self.main_scene_version}\n\n"
        )
        
    def _write_scene(self, file: TextIOWrapper):
        file.write(
            ";### SCENE ###\n"
            ";      <scene name (string)>\n"
            f"{self.scene_name}\n\n"
        )
        
    def _write_shots_header(self, file: TextIOWrapper):
        file.write(
            ";### SHOTS ###\n"
            f"{len(self.shots)}\n\n"
        )
        
    def _write_objects(self, file: TextIOWrapper):
        file.write(
            ";### OBJECTS ###\n"
            f"{len(self.objects)}\n"
            ";      <export name (string)>\n"
            ";      <animation id (string)>\n"
            ";      <animation graph tag path>\n"
            ";      <object type tag path>\n"
            ";      <shots visible (bit mask - sorta)>\n\n"
        )
        for actor in self.objects:
            file.write(
                f"; OBJECT {actor.name}\n"
                f"{actor.name}\n"
                f"{actor.name}\n"
                f"tags\{actor.graph}\n"
                f"tags\{actor.tag}\n"
                f"{actor.shot_bit_mask}\n\n"
            )
            
    def _write_shots(self, file: TextIOWrapper):
        for idx, shot in enumerate(self.shots):
            shot_num = idx + 1
            if self.has_camera_data:
                self._write_shot_camera(file, shot, shot_num)
            self._write_shot_data(file, shot, shot_num)
                
    def _write_shot_camera(self, file: TextIOWrapper, shot: Shot, shot_num: int):
        if self.corinth:
            file.write(
                f"; ### SHOT {shot_num} ###\n"
                ";          <Ubercam position (vector)>\n"
                ";          <Ubercam up (vector)>\n"
                ";          <Ubercam forward (vector)>\n"
                ";          <Focal Length (float)>\n"
                ";          <Depth of Field (bool)>\n"
                ";          <Near Focal Plane Distance (float)>\n"
                ";          <Far Focal Plane Distance (float)>\n"
                ";          <Near Focal Depth (float)>\n"
                ";          <Far Focal Depth (float)>\n"
                ";          <Near Blur Amount (float)>\n"
                ";          <Far Blur Amount (float)>\n"
                f"{len(shot.frames)}\n\n"
            )
            for idx, frame in enumerate(shot.frames):
                file.write(
                    f"; FRAME {idx + 1}\n"
                    f"{frame.position}\n"
                    f"{frame.up}\n"
                    f"{frame.forward}\n"
                    f"{frame.focal_length}\n"
                    f"{frame.depth_of_field}\n"
                    f"{frame.near_focal_plane_distance}\n"
                    f"{frame.far_focal_plane_distance}\n"
                    f"{frame.near_focal_depth}\n"
                    f"{frame.far_focal_depth}\n"
                    f"{frame.near_blur_amount}\n"
                    f"{frame.far_blur_amount}\n\n"
                )
        else:
            file.write(
                f"; ### SHOT {shot_num} ###\n"
                ";          <Ubercam position (vector)>\n"
                ";          <Ubercam up (vector)>\n"
                ";          <Ubercam forward (vector)>\n"
                ";          <Horizontal field of view (float)>\n"
                ";          <Horizontal film aperture (float, millimeters)>\n"
                ";          <Focal Length (float)>\n"
                ";          <Depth of Field (bool)>\n"
                ";          <Near Focal Plane Distance (float)>\n"
                ";          <Far Focal Plane Distance (float)>\n"
                ";          <Focal Depth (float)>\n"
                ";          <Blur Amount (float)>\n"
                f"{len(shot.frames)}\n\n"
            )
            for idx, frame in enumerate(shot.frames):
                file.write(
                    f"; FRAME {idx + 1}\n"
                    f"{frame.position}\n"
                    f"{frame.up}\n"
                    f"{frame.forward}\n"
                    f"{frame.horizontal_fov}\n"
                    f"{frame.horizontal_aperture}\n"
                    f"{frame.focal_length}\n"
                    f"{frame.depth_of_field}\n"
                    f"{frame.near_focal_plane_distance}\n"
                    f"{frame.far_focal_plane_distance}\n"
                    f"{frame.focal_depth}\n"
                    f"{frame.blur_amount}\n\n"
                )
    
    def _write_shot_data(self, file: TextIOWrapper, shot: Shot, shot_num: int):
        if self.corinth:
            file.write(
                ";*** AUDIO DATA VERSION ***\n"
                f"{self.audio_data_version}\n\n"
            )
        file.write(
            f";*** SHOT {shot_num} AUDIO DATA ***\n"
            f"{len(shot.sounds)}\n"
            ";          <Sound tag (string)>\n"
            ";          <Female sound tag (string)>\n"
            ";          <Audio filename (string)>\n"
            ";          <Female audio filename (string)>\n"
            ";          <Frame number (int)>\n"
            ";          <Character (string)>\n"
            ";          <Dialog Color (string)>\n"
        )
        for sound in shot.sounds:
            file.write(
                f"{sound.sound_tag}\n"
                f"{sound.female_sound_tag}\n"
                f"{sound.audio_filename}\n"
                f"{sound.female_audio_filename}\n"
                f"{sound.frame_number}\n"
                f"{sound.character}\n"
                f"{sound.dialog_color}\n\n"
            )
        
        if self.corinth:
            file.write(
                ";*** CUSTOM SCRIPT DATA VERSION ***\n"
                f"{self.custom_script_version}\n\n"
            )
        file.write(
            f";*** SHOT {shot_num} CUSTOM SCRIPT DATA ***\n"
            f"{len(shot.scripts)}\n"
            f";          <Node ID (long)>\n"
            f";          <Sequence ID (long)>\n"
            f";          <Script (string)>\n"
            f";          <Frame number (int)>\n\n"
        )
        for script in shot.scripts:
            f"{script.node_id}\n"
            f"{script.sequence_id}\n"
            f"{script.string}\n"
            f"{script.frame_number}\n\n"
            
        if self.corinth:
            file.write(
                ";*** EFFECT DATA VERSION ***\n"
                f"{self.effect_data_version}\n\n"
            )
        file.write(
            f";*** SHOT {shot_num} EFFECT DATA ***\n"
            f"{len(shot.effects)}\n"
            f";          <Node ID (long)>\n"
            f";          <Sequence ID (long)>\n"
            f";          <Effect (string)>\n"
            f";          <Marker Name (string)>\n"
            f";          <Marker Parent (string)>\n"
            f";          <Frame number (int)>\n"
            f";          <Effect State (int)>\n"
            f";          <Size Scale (float)>\n"
            f";          <Function A (string)>\n"
            f";          <Function B (string)>\n"
            f";          <Looping (long)>\n\n"
        )
        for effect in shot.effects:
            f"{effect.node_id}\n"
            f"{effect.sequence_id}\n"
            f"{effect.effect}\n"
            f"{effect.marker_name}\n\n"
            f"{effect.marker_parent}\n\n"
            
    def _write_extra_cameras(self, file: TextIOWrapper):
        file.write(
            ";### EXTRA CAMERAS ###\n"
            f"{len(self.extra_cameras)}\n"
            f";          <Camera name (string)>\n"
            f";          <Camera type (string)>\n\n"
        )
        for camera in self.extra_cameras:
            file.write(
                f"{camera.name}\n"
                f"{camera.type}\n\n"
            )