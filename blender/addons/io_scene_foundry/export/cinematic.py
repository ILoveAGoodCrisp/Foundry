from pathlib import Path
import bpy

from ..managed_blam.object import ObjectTag
from ..managed_blam.model import ModelTag
from ..managed_blam.animation import AnimationTag
from ..managed_blam.cinematic_scene import CinematicClip, CinematicCustomScript, CinematicDialogue, CinematicEffect, CinematicLighting, CinematicMusic, CinematicObjectFunction, CinematicScreenEffect, CinematicTextureMovie, CinematicUserInputConstraints

from ..managed_blam.Tags import TagFieldBlock

from ..managed_blam import Tag

from .. import utils
from ..managed_blam.camera_track import camera_correction_matrix

class CinematicScene:
    def __init__(self, asset_path, scene_name, scene: bpy.types.Scene):
        self.name = scene_name
        self.path_no_ext = Path(asset_path, self.name)
        self.path = self.path_no_ext.with_suffix(".cinematic_scene")
        self.path_qua = Path(self.path_no_ext).with_suffix(".qua")
        self.anchor = scene.nwo.cinematic_anchor
        self.anchor_name = f"{self.name}_anchor"
        self.anchor_location = 0.0, 0.0, 0.0
        self.anchor_yaw_pitch = 0.0, 0.0, 0.0
        if self.anchor is not None:
            anchor_matrix = utils.halo_transforms_matrix(self.anchor.matrix_world.inverted_safe())
            self.anchor_location = anchor_matrix.translation.to_tuple()
            matrix_3x3 = anchor_matrix.normalized().to_3x3()
            forward = matrix_3x3.col[0]
            left = matrix_3x3.col[1]
            up = matrix_3x3.col[2]
            yaw, pitch, roll = utils.ypr_from_flu(forward, left, up)
            self.anchor_yaw_pitch_roll = yaw - 180, pitch, 0.0
        
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
    
    return utils.halo_scale(near_depth), utils.halo_scale(far_depth)

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

def calculate_focal_distances(camera):
    if not isinstance(camera.data, bpy.types.Camera):
        print("Selected object is not a camera.")
        return None

    cam_data = camera.data
    if not cam_data.dof.use_dof:
        return 0, 0, 0
    lens_mm = cam_data.lens  # Focal length in millimeters
    aperture = cam_data.dof.aperture_fstop  # F-Stop value
    sensor_width = cam_data.sensor_width    # Sensor width in mm
    coc = 0.029  # Circle of confusion for 35mm equivalent (adjust as needed)

    # Determine the focus distance
    if cam_data.dof.focus_object:
        # Focus object exists, calculate distance from camera to object
        focus_object = cam_data.dof.focus_object
        focus_distance = (camera.matrix_world.translation - focus_object.location).length
    else:
        # Fallback to manually set focus distance
        focus_distance = cam_data.dof.focus_distance

    # Hyperfocal Distance
    hyperfocal_distance = (lens_mm**2) / (aperture * coc)

    # Near and Far Focus Limits
    if focus_distance > 0:
        near_focus = (hyperfocal_distance * focus_distance) / (hyperfocal_distance + (focus_distance - lens_mm))
        far_focus = (hyperfocal_distance * focus_distance) / (hyperfocal_distance - (focus_distance - lens_mm))
    else:
        near_focus = 0
        far_focus = 0

    return near_focus, far_focus, focus_distance

class Actor:
    def __init__(self, ob: bpy.types.Object, scene_name: str, asset_path: str, child_asset_name=""):
        self.ob = ob
        if "." in ob.name:
            ob.name = ob.name.replace(".", "_")
        self.name = ob.name
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
        
        self.graph = str(Path(asset_path, "objects", scene_name, f"{ob.name}.model_animation_graph"))
        if child_asset_name:
            self.sidecar = str(Path(asset_path, child_asset_name, "export", "models", self.name))
        else:
            self.sidecar = str(Path(asset_path, "export", "models", self.name))
        self.render_model = None
        self.bones: list = []
        self.shots_active = []
        self.node_order = None
        self.variant = ob.nwo.cinematic_variant
        self.validation_complete = False
        
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
                    scenery_object.SelectField("functions").PasteReplaceEntireBlock()
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
    
class Shot: ...
    
class Frame:
    def __init__(self, ob: bpy.types.Object, corinth: bool):
        assert(ob.type == 'CAMERA')
        data = ob.data
        data: bpy.types.Camera
        blender_matrix = ob.matrix_world
        matrix = utils.halo_transforms_matrix(blender_matrix)
            
        if data.dof.use_dof:
            # Focal distance
            if data.dof.focus_object:
                # Focus object exists, calculate distance from camera to object
                focus_object = data.dof.focus_object
                focal_distance = (ob.matrix_world.translation - focus_object.location).length
            else:
                # Fallback to manually set focus distance
                focal_distance = data.dof.focus_distance

            # Aperture (f-stop value)
            aperture = data.dof.aperture_fstop

            # Lens focal length (in mm)
            lens = data.lens

            # Calculate the depth of field region
            # Hyperfocal distance: the distance beyond which all objects are in acceptable focus
            hyperfocal = (lens ** 2) / (aperture * 5)

            # Near and far focal planes
            near_focal_plane = (hyperfocal * focal_distance) / (hyperfocal + (focal_distance - lens))
            far_focal_plane = (hyperfocal * focal_distance) / (hyperfocal - (focal_distance - lens))

            # Blur amount (relative to aperture)
            blur_amount = 1 / aperture if aperture > 0 else 0
        else:
            focal_distance = 0
            near_focal_plane = 0
            far_focal_plane = 0
            blur_amount = 0
            
        self.position = matrix.translation.to_tuple()
        matrix_3x3 = matrix.to_3x3() @ camera_correction_matrix.inverted_safe()
        up = matrix_3x3.col[2]
        forward = matrix_3x3.col[0]
        self.up = up.normalized().to_tuple()
        self.forward = forward.normalized().to_tuple()
        self.focal_length = data.lens * (0.5 if corinth else 1.3)
        self.depth_of_field = int(data.dof.use_dof)

        self.near_focal_plane_distance = utils.halo_scale(near_focal_plane) * 100
        self.far_focal_plane_distance = utils.halo_scale(far_focal_plane) * 100
        
        self.focal_depth = focal_distance
        
        # near, far = calculate_focal_depths(focus_distance, aperture, focal_length=focal_length)

        # self.near_focal_depth = near 
        # self.far_focal_depth = far
        
        self.blur_amount = blur_amount
        
        sensor_width = data.sensor_width
        
        # near_blur = calculate_blur_amount(focal_length, focus_distance, aperture, data.clip_start, sensor_width)
        # far_blur = calculate_blur_amount(focal_length, focus_distance, aperture, data.clip_end, sensor_width)
        
        # self.near_blur_amount = near_blur
        # self.far_blur_amount = far_blur

    
class Effect:
    def __init__(self):
        pass

class Script: ...
    
class QUA:
    main_scene_version = 4
    audio_data_version = 3
    custom_script_version = 1
    effect_data_version = 4
    def __init__(self, asset_path, scene_name: str, shots: list, actors: list[Actor], corinth: bool, is_segment = False):
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
            
    def write_to_tag(self):
        with Tag(path=self.tag_path.with_suffix(".cinematic_scene")) as scene:
            scene.tag.SelectField("StringId:name").SetStringData(self.scene_name)
            scene.tag.SelectField("StringId:anchor").SetStringData(f"{self.scene_name}_anchor")
            scene.tag_has_changes = True
            if self.corinth:
                with Tag(path=self.tag_path.with_suffix(".cinematic_scene_data")) as data:
                    scene.tag.SelectField("Reference:data").Path = data.tag_path
                    data.tag_has_changes = True
                    self._write_scene_data(data, scene.tag.SelectField("Block:objects"), scene.tag.SelectField("Block:shots"), data.tag.SelectField("Block:extra camera frame data"), data.tag.SelectField("Block:objects"), data.tag.SelectField("Block:shots"))
            else:
                self._write_scene_data(scene, scene.tag.SelectField("Block:objects"), scene.tag.SelectField("Block:shots"), scene.tag.SelectField("Block:extra camera frame data"))
            
    def _write_scene_data(self, tag, block_objects: TagFieldBlock, block_shots: TagFieldBlock, block_extra_camera: TagFieldBlock, block_data_objects: TagFieldBlock = None, block_data_shots: TagFieldBlock = None):
        # EXTRA CAMERAS TODO
        
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
        else:
            elements_zip = zip(block_shots.Elements, block_shots.Elements)
        
        for element, data_element in elements_zip:
            block_dialogue = data_element.SelectField("dialogue")
            block_dialogue.RemoveAllElements()
            
            block_effects = data_element.SelectField("effects")
            for sub_element in block_effects.Elements:
                c = CinematicEffect()
                c.from_element(sub_element, block_objects, self.corinth)
                if not c.use_maya_value:
                    effects[c] = current_frame_index + c.frame + int(self.corinth)
            block_effects.RemoveAllElements()
            
            block_custom_script = data_element.SelectField("custom script")
            for sub_element in block_custom_script.Elements:
                c = CinematicCustomScript()
                c.from_element(sub_element)
                if not c.use_maya_value:
                    custom_scripts[c] = current_frame_index + c.frame + int(self.corinth)
            block_custom_script.RemoveAllElements()
        
            # dicts of element blocks and their overall scene frame
            block_lighting = element.SelectField("lighting")
            for sub_element in block_lighting.Elements:
                c = CinematicLighting()
                c.from_element(sub_element, block_objects)
                lighting[c] = element.ElementIndex # lighting only stores its shot index as it isn't bound to a frame
            block_lighting.RemoveAllElements()
            
            block_clip = element.SelectField("clip")
            for sub_element in block_clip.Elements:
                c = CinematicClip()
                c.from_element(sub_element, block_objects)
                clips[c] = current_frame_index + c.frame_start + int(self.corinth) # corinth uses index 1 for frames
            block_clip.RemoveAllElements()
            
            block_music = element.SelectField("music")
            for sub_element in block_music.Elements:
                c = CinematicMusic()
                c.from_element(sub_element)
                music[c] = current_frame_index + c.frame + int(self.corinth)
            block_music.RemoveAllElements()
            
            block_object_functions = element.SelectField("object functions")
            for sub_element in block_object_functions.Elements:
                c = CinematicObjectFunction()
                c.from_element(sub_element, block_objects)
                for keyframe in c.keyframes:
                    object_function_keyframes[keyframe] = current_frame_index + keyframe.frame + int(self.corinth)
            block_object_functions.RemoveAllElements()
            
            block_screen_effects = element.SelectField("screen effects")
            for sub_element in block_screen_effects.Elements:
                c = CinematicScreenEffect()
                c.from_element(sub_element, self.corinth)
                screen_effects[c] = current_frame_index + c.frame + int(self.corinth)
            block_screen_effects.RemoveAllElements()
            
            block_user_input_constraints = element.SelectField("user input constraints")
            for sub_element in block_user_input_constraints.Elements:
                c = CinematicUserInputConstraints()
                c.from_element(sub_element)
                user_input_constraints[c] = current_frame_index + c.frame + int(self.corinth)
            block_user_input_constraints.RemoveAllElements()
            
            if self.corinth:
                block_texture_movies = element.SelectField("texture movies")
                for sub_element in block_texture_movies.Elements:
                    c = CinematicTextureMovie()
                    c.from_element(sub_element)
                    texture_movies[c] = current_frame_index + c.frame + int(self.corinth)
                block_texture_movies.RemoveAllElements()
                element = block_data_shots.Elements[idx]
                
            current_frame_index += (data_element.SelectField("frame count").Data - 1)
        
        # SHOTS
        # make sure shots block is same size as shots count
        while block_shots.Elements.Count > len(self.shots):
            block_shots.RemoveElement(block_shots.Elements.Count - 1)
        while block_shots.Elements.Count < len(self.shots):
            block_shots.AddElement()
            
        if self.corinth:
            while block_data_shots.Elements.Count > len(self.shots):
                block_data_shots.RemoveElement(block_data_shots.Elements.Count - 1)
            while block_data_shots.Elements.Count < len(self.shots):
                block_data_shots.AddElement()
        
        for idx, shot in enumerate(self.shots):
            element = block_shots.Elements[idx]
            element.SelectField("frame count").Data = shot.frame_count
            frame_data = element.SelectField("frame data")
            frame_data.RemoveAllElements()
                
            if not shot.frames:
                continue
            
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
        actor_elements = {actor: None for actor in self.objects}
        to_remove_object_element_indexes = []
        # Loop through elements and assign actors where they already exist, else mark them for deletion
        for element in block_objects.Elements:
            for actor in self.objects:
                if actor.name == element.SelectField("name").GetStringData():
                    actor_elements[actor] = element
                    break
            else:
                to_remove_object_element_indexes.append(element.ElementIndex)
        
        # Remove any elements that don't have a valid actor
        for idx in reversed(to_remove_object_element_indexes):
            block_objects.RemoveElement(idx)
            
        object_tag_weapon_names = {} # used for custom scripts
        actor_objects = {a.ob for a in self.objects} # for checking an event is valid
        # Add elements for actors without them
        for actor, element in actor_elements.items():
            if element is None:
                element = block_objects.AddElement()
                element.SelectField("name").SetStringData(actor.name)
                element.SelectField("variant name").SetStringData(actor.variant)
            if actor.weapon_tag is not None:
                print(actor.name, element)
                block_attachments = element.SelectField("Block:attachments")
                for attachment_element in block_attachments.Elements:
                    attachment_path = attachment_element.SelectField("Reference:attachment type").Path
                    if attachment_path is None:
                        continue
                    elif attachment_path.RelativePathWithExtension == actor.weapon_tag:
                        object_tag_weapon_names[actor.original_tag] = attachment_element.SelectField("attachment object name").GetStringData()
                        break
                else:
                    attachment_element = block_attachments.AddElement()
                    attachment_element.SelectField("flags").SetBit("invisible", True)
                    attachment_element.SelectField("object marker name").SetStringData("primary_trigger")
                    attachment_element.SelectField("attachment object name").SetStringData(f"{actor.name}_weapon")
                    attachment_element.SelectField("attachment marker name").SetStringData("primary_trigger")
                    attachment_element.SelectField("attachment type").Path = tag._TagPath_from_string(actor.weapon_tag)
                    object_tag_weapon_names[actor.original_tag] = attachment_element.SelectField("attachment object name").GetStringData()
                        
                actor_elements[actor] = element

            if not self.corinth:  
                # Reach writes this data to the cinematic_scene tag so lets do it now
                element.SelectField("identifier").SetStringData(actor.name)
                element.SelectField("model animation graph").Path = tag._TagPath_from_string(actor.graph)
                element.SelectField("object type").Path = tag._TagPath_from_string(actor.tag)
                flag_items = element.SelectField("shots active flags").Items
                for item in flag_items:
                    item.IsSet = False
                for idx in actor.shots_active:
                    flag_items[idx].IsSet = True
                
        # Clear the cinematic_scene_data objects if corinth, and write the object data
        if self.corinth:
            block_data_objects.RemoveAllElements()
            # process actors by element index, not sure if order matters here but I'm choosing to play it safe
            actors = [k for k, v in sorted(actor_elements.items(), key=lambda item: item[1].ElementIndex)]
            for actor in actors:
                element = block_data_objects.AddElement()
                element.SelectField("name").SetStringData(actor.name)
                element.SelectField("identifier").SetStringData(actor.name)
                element.SelectField("model animation graph").Path = tag._TagPath_from_string(actor.graph)
                element.SelectField("object type").Path = tag._TagPath_from_string(actor.tag)
                flags = element.SelectField("shots active flags")
                flags.RefreshShots() # shots won't register unless we call this
                flags.ClearShots()
                for idx in actor.shots_active:
                    flags.SetShotChecked(idx, True) # SetShotChecked is part of TagFieldCustomCinematicShotFlags, which is not used by Reach
        
        # Add cinematic events
        frame_start = int(bpy.context.scene.frame_start)
        sound_sequences = bpy.context.scene.sequence_editor.sequences_all
        for event in bpy.context.scene.nwo.cinematic_events:
            match event.type:
                case 'DIALOGUE':
                    c = CinematicDialogue()
                    c.from_event(event, actor_objects)
                    if c.dialogue is not None:
                        frame = event.frame
                        if event.sound_strip:
                            strip = sound_sequences.get(event.sound_strip)
                            if strip is not None:
                                frame = int(strip.frame_start)
                        dialogue[c] = frame - frame_start + int(self.corinth)
                case 'EFFECT':
                    c = CinematicEffect()
                    c.from_event(event, actor_objects)
                    if c.effect is not None:
                        effects[c] = event.frame - frame_start + int(self.corinth)
                case 'SCRIPT':
                    c = CinematicCustomScript()
                    c.from_event(event, object_tag_weapon_names, actor_objects)
                    if c.script.strip():
                        custom_scripts[c] = event.frame - frame_start + int(self.corinth)
        
        
        # Add back data blocks
        # Dialogue comes from blender
        block = block_shots
        
        for data, shot_index in lighting.items():
            shot_element = block.Elements[shot_index]
            data.to_element(shot_element.SelectField("lighting").AddElement(), block_objects)
            
        for data, frame_index in clips.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            end_offset = data.frame_end - data.frame_start
            data.frame_start = shot_frame
            data.frame_end = shot_frame + end_offset
            data.to_element(shot_element.SelectField("clip").AddElement(), block_objects)
            
        for data, frame_index in music.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("music").AddElement())
            
        for data, frame_index in object_function_keyframes.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("object functions"), block_objects)
            
        for data, frame_index in screen_effects.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            end_offset = data.stop_frame - data.frame
            data.frame = shot_frame
            data.stop_frame = shot_frame + end_offset
            data.to_element(shot_element.SelectField("screen effects").AddElement(), self.corinth)
            
        for data, frame_index in user_input_constraints.items():
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("user input constraints").AddElement())
        
        if self.corinth:
            for data, frame_index in texture_movies.items():
                shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
                if shot_index is None:
                    continue
                shot_element = block.Elements[shot_index]
                data.frame = shot_frame
                data.to_element(shot_element.SelectField("texture movies").AddElement())
        
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
            shot_index, shot_frame = self.get_shot_index_and_frame(frame_index)
            if shot_index is None:
                continue
            shot_element = block.Elements[shot_index]
            data.frame = shot_frame
            data.to_element(shot_element.SelectField("custom script").AddElement())
            