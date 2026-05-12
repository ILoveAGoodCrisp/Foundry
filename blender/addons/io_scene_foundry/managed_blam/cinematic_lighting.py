import math

from mathutils import Matrix, Vector

from .light import LightTag
from .. import utils
from . import Tag
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
    
class CinematicLightingTag(Tag):
    tag_ext = 'cinematic_lighting'
    
    def _from_corinth(self, cin_lighting: CinLighting):
        lights = self.tag.SelectField("Block:Authored Light Probe[0]/Block:Lights")
        
        if lights is not None and lights.Elements.Count > 0:
            element = lights.Elements[0]
            # Light 1
            light_1 = CinematicLight()
            light_1.set_color(element.SelectField("RealRgbColor:Direct color 1").Data)
            light_1.set_intensity(element.SelectField("Real:Direct intensity 1").Data * element.SelectField("Real:Authored Light Probe Intensity Scale").Data)
            if light_1.valid_color and light_1.valid_intensity:
                light_1.compute_matrix(element.SelectField("Real:Direction 1").Data, element.SelectField("Real:Front-Back 1").Data)
                cin_lighting.vmf_lights.append(light_1)
            
            # Light 2
            light_2 = CinematicLight()
            light_2.set_color(element.SelectField("RealRgbColor:Direct color 2").Data)
            light_2.set_intensity(element.SelectField("Real:Direct intensity 2").Data * element.SelectField("Real:Authored Light Probe Intensity Scale").Data)
            if light_2.valid_color and light_2.valid_intensity:
                light_2.compute_matrix(element.SelectField("Real:Direction 2").Data, element.SelectField("Real:Front-Back 2").Data)
                cin_lighting.vmf_lights.append(light_2)
    
    def _from_reach(self, cin_lighting: CinLighting):
        # Directional VMF Light
        directional_vmf_light = CinematicLight()
        directional_vmf_light.set_color(self.tag.SelectField("RealRgbColor:Directional Color").Data)
        directional_vmf_light.set_intensity(self.tag.SelectField("Real:Directional scale").Data * self.tag.SelectField("Real:vmf light scale").Data)
        if directional_vmf_light.valid_color and directional_vmf_light.valid_intensity:
            directional_vmf_light.compute_matrix(self.tag.SelectField("Real:Direction").Data, self.tag.SelectField("Real:Front-Back").Data)
            cin_lighting.vmf_lights.append(directional_vmf_light)
        
        # Analytical VMF Light
        analytical_vmf_light = CinematicLight()
        analytical_vmf_light.set_color(self.tag.SelectField("RealRgbColor:Analytical color").Data)
        analytical_vmf_light.set_intensity(self.tag.SelectField("Real:Analytical scale").Data * self.tag.SelectField("Real:analytical light scale").Data)
        if analytical_vmf_light.valid_color and analytical_vmf_light.valid_intensity:
            analytical_vmf_light.compute_matrix(self.tag.SelectField("Real:Direction(A)").Data, self.tag.SelectField("Real:Front-Back(A)").Data)
            cin_lighting.vmf_lights.append(analytical_vmf_light)
            
        # Dynamic Lights
        for element in self.tag.SelectField("dynamic lights").Elements:
            light_tag_path = element.SelectField("light").Path
            if not self.path_exists(light_tag_path):
                continue
            
            dynamic_light = DynamicLight()
            dynamic_light.light_tag = light_tag_path
            flags = element.SelectField("Flags")
            dynamic_light.follow_object = flags.TestBit("follow object")
            dynamic_light.use_marker = flags.TestBit("position at marker")
            dynamic_light.compute_matrix(element.SelectField("Real:Direction").Data, element.SelectField("Real:Front-Back").Data, element.SelectField("Real:Distance").Data)
            cin_lighting.dynamic_lights.append(dynamic_light)
    
    def to_cinematic_lighting(self, marker, persist, shot_index) -> CinLighting:
        cin_lighting = CinLighting(marker, persist, shot_index)
        if self.corinth:
            self._from_corinth(cin_lighting)
        else:
            self._from_reach(cin_lighting)
            
        return cin_lighting
