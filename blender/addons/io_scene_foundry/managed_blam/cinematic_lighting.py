import math

from mathutils import Matrix, Vector

from .light import LightTag
from .. import utils
from ..tags.blender import BlenderTag
from ..tags.lighting import CinematicLightingDocument
from . import import_transform
import bpy

def _cinematic_light_source_vector(direction_angle: float, front_back_angle: float) -> Vector:
    yaw = math.radians(direction_angle)
    pitch = math.radians(front_back_angle)
    return Vector((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))).normalized()

def _tag_path_to_string(tag_path) -> str:
    return getattr(tag_path, "RelativePathWithExtension", str(tag_path))

def _root_bone_matrix(armature: bpy.types.Object) -> Matrix:
    if armature is None:
        return Matrix.Identity(4)
    if len(armature.pose.bones) == 0:
        return armature.matrix_world.copy()
    return armature.matrix_world @ armature.pose.bones[0].matrix

def _set_armature_root_parent(ob: bpy.types.Object, armature: bpy.types.Object, matrix: Matrix):
    matrix = import_transform.transform_matrix(matrix, rotate=False)
    ob.parent = armature
    if len(armature.pose.bones) > 0:
        bone = armature.pose.bones[0]
        ob.parent_type = 'BONE'
        ob.parent_bone = bone.name
        ob.matrix_world = armature.matrix_world @ bone.matrix @ matrix
    else:
        ob.matrix_world = armature.matrix_world @ matrix

def _set_object_parent(ob: bpy.types.Object, parent: bpy.types.Object, matrix: Matrix):
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_local = import_transform.transform_matrix(matrix, rotate=False)

class CinematicLight:
    def __init__(self):
        self.matrix: Matrix = None
        self.intensity = 0.0
        self.color = 0.0, 0.0, 0.0
        self.valid_color = False
        self.valid_intensity = False
        self.direction_angle = 0.0
        self.front_back_angle = 0.0
        self.distance = 0.0
        
    def compute_matrix(self, direction_angle: float, front_back_angle: float, distance: float=0.0):
        self.direction_angle = direction_angle
        self.front_back_angle = front_back_angle
        self.distance = distance
        source_direction = _cinematic_light_source_vector(direction_angle, front_back_angle)
        position = source_direction * distance * 100
        rot = source_direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        self.matrix = Matrix.Translation(position) @ rot
        
    def set_color(self, color_data):
        self.color = [utils.srgb_to_linear(n) for n in color_data]
        self.valid_color = any(n > 0.0 for n in self.color)
        
    def set_intensity(self, intensity_data):
        self.intensity = intensity_data
        self.valid_intensity = self.intensity > 0.0
        
    def _set_metadata(self, ob: bpy.types.Object, light_type: str):
        ob.nwo.is_cinematic_light = True
        ob["cinematic_light_type"] = light_type
        ob["cinematic_light_direction"] = self.direction_angle
        ob["cinematic_light_front_back"] = self.front_back_angle
        ob["cinematic_light_distance"] = self.distance

    def to_blender(self, armature: bpy.types.Object, marker: bpy.types.Object, light_name: str):
        data = bpy.data.lights.new(light_name, 'SUN')
        data.energy = self.intensity
        data.color = self.color
        data.use_shadow = False
        ob = bpy.data.objects.new(data.name, data)
        if marker is not None:
            _set_object_parent(ob, marker, self.matrix)
        else:
            _set_armature_root_parent(ob, armature, self.matrix)
        self._set_metadata(ob, "vmf")
        
        return ob
        
class DynamicLight(CinematicLight):
    def __init__(self):
        super().__init__()
        self.follow_object = False
        self.use_marker = False
        self.light_tag = ""
        
    def to_blender(self, armature: bpy.types.Object, marker: bpy.types.Object, light_name: str):
        with LightTag(path=self.light_tag) as light:
            data = light.to_blender()
            
        ob = bpy.data.objects.new(light_name, data)
        parent_marker = marker if self.use_marker else None
        if self.follow_object:
            if parent_marker is not None:
                _set_object_parent(ob, parent_marker, self.matrix)
            else:
                _set_armature_root_parent(ob, armature, self.matrix)
        else:
            parent_matrix = parent_marker.matrix_world if parent_marker is not None else _root_bone_matrix(armature)
            ob.matrix_world = parent_matrix @ import_transform.transform_matrix(self.matrix, rotate=False)
        self._set_metadata(ob, "dynamic")
        ob["cinematic_light_follow_object"] = self.follow_object
        ob["cinematic_light_use_marker"] = self.use_marker
        ob["cinematic_light_tag"] = _tag_path_to_string(self.light_tag)
        
        return ob
    
class CinLighting:
    def __init__(self, marker, persist, shot_index):
        self.marker = marker
        self.persist = persist
        self.shot_index = shot_index
        self.vmf_lights: list[CinematicLight] = []
        self.light_probes: list[CinematicLight] = []
        self.dynamic_lights: list[DynamicLight] = []
        self.cortana_lights: list[CinematicLight] = []
    
class CinematicLightingTag(BlenderTag, CinematicLightingDocument):
    def __init__(self, path='', *, tag_must_exist=False, **kwargs):
        super().__init__(path, tag_must_exist=tag_must_exist, **kwargs)

    def to_cinematic_lighting(self, marker, persist, shot_index) -> CinLighting:
        lighting = CinLighting(marker, persist, shot_index)
        for record in self.dynamic_lights():
            light = DynamicLight()
            light.light_tag = record.reference
            light.follow_object = record.follow_object
            light.use_marker = record.use_marker
            light.compute_matrix(record.direction, record.front_back, record.distance)
            lighting.dynamic_lights.append(light)
        return lighting
