import math

from mathutils import Matrix, Vector

from .light import LightTag
from .. import utils
from . import Tag
import bpy

class CinematicLight:
    def __init__(self):
        self.matrix: Matrix = None
        self.intensity = 0.0
        self.color = 0.0, 0.0, 0.0
        self.valid_color = False
        self.valid_intensity = False
        
    def compute_matrix(self, direction_angle: float, front_back_angle: float, distance: float=0.0):
        yaw = math.radians(direction_angle)
        pitch = math.radians(front_back_angle)
        
        direction = Vector((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)))
        position = direction * distance * 100
        
        forward = (-direction).normalized()
        up = Vector((0, 0, 1))
        
        right = up.cross(forward).normalized()
        up = forward.cross(right).normalized()
        
        rot = Matrix((right.to_4d(), up.to_4d(), forward.to_4d(), Vector((0, 0, 0, 1)))).transposed()
        
        self.matrix = Matrix.Translation(position) @ rot
        
    def set_color(self, color_data):
        self.color = [utils.srgb_to_linear(n) for n in color_data]
        self.valid_color = any(n > 0.0 for n in self.color)
        
    def set_intensity(self, intensity_data):
        self.intensity = intensity_data
        self.valid_intensity = self.intensity > 0.0
        
    def to_blender(self, armature: bpy.types.Object, light_name: str):
        data = bpy.data.lights.new(light_name, 'SUN')
        data.nwo.light_intensity = self.intensity
        data.color = self.color
        data.use_shadow = False
        ob = bpy.data.objects.new(data.name, data)
        ob.parent = armature
        ob.parent_type = 'BONE'
        bone = armature.pose.bones[0]
        ob.parent_bone = bone.name
        ob.matrix_world = bone.matrix @ self.matrix
        
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
        if marker is None or not self.use_marker:
            ob.parent = armature
            ob.parent_type = 'BONE'
            bone = armature.pose.bones[0]
            ob.parent_bone = bone.name
            ob.matrix_world = bone.matrix @ self.matrix
        else:
            ob.matrix_world = self.matrix
            ob.parent = marker
        
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
        pass
    
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
        for element in self.tag.SelectField("Block:dynamic lights").Elements:
            light_tag_path = element.SelectField("Reference:light").Path
            if not self.path_exists(light_tag_path):
                continue
            
            dynamic_light = DynamicLight()
            dynamic_light.light_tag = light_tag_path
            dynamic_light.compute_matrix(element.SelectField("Real:Direction").Data, element.SelectField("Real:Front-Back").Data, element.SelectField("Real:Distance").Data)
            cin_lighting.dynamic_lights.append(dynamic_light)
    
    def to_cinematic_lighting(self, marker, persist, shot_index) -> CinLighting:
        cin_lighting = CinLighting(marker, persist, shot_index)
        if self.corinth:
            self._from_corinth(cin_lighting)
        else:
            self._from_reach(cin_lighting)
            
        return cin_lighting
