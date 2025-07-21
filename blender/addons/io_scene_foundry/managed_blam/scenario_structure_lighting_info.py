

from math import radians
from typing import cast

from mathutils import Color, Matrix, Vector

from ..constants import HALO_FACTOR, WU_SCALAR

from ..props.object import NWO_ObjectPropertiesGroup
from ..props.light import NWO_LightPropertiesGroup
from ..managed_blam.Tags import TagFieldBlockElement
from ..managed_blam import Tag
from .. import utils
import bpy

class ScenarioStructureLightingInfoTag(Tag):
    tag_ext = 'scenario_structure_lighting_info'
        
    def _read_fields(self):
        self.block_generic_light_definitions = self.tag.SelectField("Block:generic light definitions")
        self.block_generic_light_instances = self.tag.SelectField("Block:generic light instances")
        
    def _definition_index_from_id(self, id) -> int:
        for element in self.block_generic_light_definitions.Elements:
            if id == element.Fields[0].Data:
                return element.ElementIndex
            
        return 0
    
    def _definition_index_from_data_name(self, name, light_definitions) -> int:
        for definition in light_definitions:
            if name == definition.data_name:
                return definition.index
            
        return 0
    
    def clear_lights(self):
        self.block_generic_light_definitions.RemoveAllElements()
        self.block_generic_light_instances.RemoveAllElements()
        self.tag_has_changes = True
        
    def build_tag(self, light_instances, light_definitions):
        if self.corinth:
            self._write_corinth_light_definitions(light_definitions)
            self._write_corinth_light_instances(light_instances, light_definitions)
        else:
            self._write_reach_light_definitions(light_definitions)
            self._write_reach_light_instances(light_instances, light_definitions)
            
        self.tag_has_changes = True
            
    def _write_corinth_light_definitions(self, light_definitions):
        remaining_light_indices = list(range(len(light_definitions)))
        remove_indices = []
        
        for element in self.block_generic_light_definitions.Elements:
            element_id = element.SelectField("Definition Identifier").GetStringData()
            found_light = next((light for light in light_definitions if light.id == element_id), None)
            if found_light is None:
                remove_indices.append(element.ElementIndex)
            else:
                remaining_light_indices.remove(light_definitions.index(found_light))
                self._update_corinth_light_definitions(found_light, element)
                
        if remove_indices:
            for i in reversed(remove_indices):
                self.block_generic_light_definitions.RemoveElement(i)
                
        for i in remaining_light_indices:
            self._update_corinth_light_definitions(light_definitions[i], self.block_generic_light_definitions.AddElement())
                
    def _update_corinth_light_definitions(self, light, element: TagFieldBlockElement):
        element.SelectField("Definition Identifier").Data = light.id 
        parameters_struct  = element.SelectField("Midnight_Light_Parameters")
        parameters = parameters_struct.Elements[0]
        parameters.SelectField("haloLightNode").SetStringData(light.data_name)
        parameters.SelectField("Light Type").Value = light.type
        parameters.SelectField("Light Color").Data = light.color
        intensity_struct = parameters.SelectField("Intensity")
        intensity = intensity_struct.Elements[0]
        intensity_mapping = intensity.SelectField("Custom:Mapping")
        intensity_mapping.Value.ClampRangeMin = light.intensity
        parameters.SelectField("Lighting Mode").Value = light.lighting_mode
        parameters.SelectField("Distance Attenuation Start").Data = light.far_attenuation_start
        atten_struct = parameters.SelectField("Distance Attenuation End")
        atten = atten_struct.Elements[0]
        atten_mapping = atten.SelectField("Custom:Mapping")
        atten_mapping.Value.ClampRangeMin = light.far_attenuation_end
        
        if light.type == 1: # Spot
            parameters.SelectField("Inner Cone Angle").Data = light.hotspot_size
            hotpot_struct = parameters.SelectField("Outer Cone End")
            hotspot = hotpot_struct.Elements[0]
            hotspot_mapping = hotspot.SelectField("Custom:Mapping")
            hotspot_mapping.Value.ClampRangeMin = light.hotspot_cutoff
            parameters.SelectField("Cone Projection Shape").Value = light.cone_shape
            
        if light.type == 2: # Sun
            element.SelectField("sun").Value = 1
        else:
            element.SelectField("sun").Value = 0
            
        # Dynamic Only
        parameters.SelectField("Shadow Near Clip Plane").Data = light.shadow_near_clip
        parameters.SelectField("Shadow Far Clip Plane").Data = light.shadow_far_clip
        parameters.SelectField("Shadow Bias Offset").Data = light.shadow_bias
        parameters.SelectField("Dynamic Shadow Quality").Value = light.shadow_quality
        parameters.SelectField("Shadows").Value = light.shadows
        parameters.SelectField("Screenspace Light").Value = light.screen_space
        parameters.SelectField("Ignore Dynamic Objects").Value = light.ignore_dynamic_objects
        parameters.SelectField("Cinema Objects Only").Value = light.cinema_objects_only
        parameters.SelectField("Cinema Only").Value = light.cinema_only
        parameters.SelectField("Cinema Exclude").Value = light.cinema_exclude
        parameters.SelectField("Specular Contribution").Value = light.specular_contribution
        parameters.SelectField("Diffuse Contribution").Value = light.diffuse_contribution
        # Static Only
        element.SelectField("indirect amplification factor").Data = light.indirect_amp
        element.SelectField("jitter sphere radius").Data = light.jitter_sphere
        element.SelectField("jitter angle").Data = light.jitter_angle
        element.SelectField("jitter quality").Value = light.jitter_quality
        element.SelectField("indirect only").Value = light.indirect_only
        element.SelectField("static analytic").Value = light.static_analytic
        
        
    def _write_corinth_light_instances(self, light_instances, light_definitions):
        self.block_generic_light_instances.RemoveAllElements()
        for light in light_instances:
            element = self.block_generic_light_instances.AddElement()
            id = utils.id_from_string(light.data_name)
            element.SelectField("Light Definition ID").Data = id
            element.SelectField("Light Definition Index").Data = self._definition_index_from_id(id)
            element.SelectField("light mode").Value = light.light_mode
            element.SelectField("origin").Data = light.origin
            element.SelectField("forward").Data = light.forward
            element.SelectField("up").Data = light.up
            
    def _write_reach_light_definitions(self, light_definitions):
        self.block_generic_light_definitions.RemoveAllElements()
        for light in light_definitions:
            element = self.block_generic_light_definitions.AddElement()
            light.index = element.ElementIndex
            element.SelectField("type").Value = light.type
            element.SelectField("shape").Value = light.shape
            element.SelectField("color").Data = light.color
            intensity_divisor = 1
            # Reach seems to fudge our intensity numbers based on whether the light is a point or spot light, fight back!
            match light.type:
                case 0:
                    intensity_divisor = 0.37735857955
                case 1:
                    intensity_divisor = 3.14465382959
                case 2:
                    intensity_divisor = 0.6289308
                    
            element.SelectField("intensity").Data = light.intensity / intensity_divisor
            
            if light.type == 1:
                element.SelectField("hotspot size").Data = light.hotspot_size
                element.SelectField("hotspot cutoff size").Data = light.hotspot_cutoff
                element.SelectField("hotspot falloff speed").Data = light.hotspot_falloff
    
            element.SelectField("near attenuation bounds").Data = [light.near_attenuation_start, light.near_attenuation_end]
            
            flags = element.SelectField("flags")
            flags.SetBit("use far attenuation", True)
            if light.far_attenuation_end > 0:
                flags.SetBit("invere squared falloff", False)
                element.SelectField("far attenuation bounds").Data = [light.far_attenuation_start, light.far_attenuation_end]
            else:
                flags.SetBit("invere squared falloff", True)
                element.SelectField("far attenuation bounds").Data = [900, 4000]

            element.SelectField("aspect").Data = light.aspect
            
    def _write_reach_light_instances(self, light_instances, light_definitions):
        self.block_generic_light_instances.RemoveAllElements()
        for light in light_instances:
            element = self.block_generic_light_instances.AddElement()
            element.SelectField("definition index").Data = self._definition_index_from_data_name(light.data_name, light_definitions)
            element.SelectField("origin").Data = light.origin
            element.SelectField("forward").Data = light.forward
            element.SelectField("up").Data = light.up
            element.SelectField("bungie light type").Value = light.game_type
            
            flags = element.SelectField("screen space specular")
            flags.SetBit("screen space light has specular", light.screen_space_specular)
            
            element.SelectField("bounce light control").Data = light.bounce_ratio
            element.SelectField("light volume distance").Data = light.volume_distance
            element.SelectField("light volume intensity scalar").Data = light.volume_intensity
            
            if light.light_tag:
                element.SelectField("user control").Path = self._TagPath_from_string(light.light_tag)
            if light.shader:
                element.SelectField("shader reference").Path = self._TagPath_from_string(light.shader)
            if light.gel:
                element.SelectField("gel reference").Path = self._TagPath_from_string(light.gel)
            if light.lens_flare:
                element.SelectField("lens flare reference").Path = self._TagPath_from_string(light.lens_flare)
                
                
    def to_blender(self, parent_collection: bpy.types.Collection = None):
        definitions = self._from_reach_light_definitions()
        objects = self._from_reach_light_instances(definitions)
        
        if objects:
            collection = cast(bpy.types.Collection, bpy.data.collections.new(f"{self.tag_path.ShortName}_lights"))
            for ob in objects:
                collection.objects.link(ob)
                
            if parent_collection is None:
                bpy.context.scene.collection.children.link(collection)
            else:
                parent_collection.children.link(collection)
        
        print([ob.name for ob in objects])
        
        return objects
    
    def _from_reach_light_instances(self, definitions: dict[int: bpy.types.Light]):
        objects = []
        for element in self.block_generic_light_instances.Elements:
            blender_light = definitions.get(element.SelectField("definition index").Data)
            if blender_light is None:
                continue
            
            ob = cast(bpy.types.Object, bpy.data.objects.new(f"light_instance:{element.ElementIndex}", blender_light))
            nwo = cast(NWO_ObjectPropertiesGroup, ob.nwo)
            
            origin = Vector(*(element.SelectField("origin").Data,))
            forward = Vector((*element.SelectField("forward").Data,))
            up = Vector((*element.SelectField("up").Data,))
            
            # forward.normalize()
            # up.normalize()
            
            # right = forward.cross(up).normalized()
            
            # up = right.cross(forward)
            
            # matrix = Matrix((right, up, forward)).transposed()
            # matrix = matrix.to_4x4()
            # matrix.translation = origin * 100
            
            matrix_3x3 = Matrix.Identity(4).to_3x3()
            matrix_3x3.col[1] = forward
            matrix_3x3.col[2] = up
            matrix = matrix_3x3.to_4x4()
            matrix.translation = origin * 100
            
            ob.matrix_world = matrix
            ob.scale *= (1 / 0.03048)
            
            match element.SelectField("bungie light type").Value:
                case 0:
                    nwo.light_game_type = '_connected_geometry_bungie_light_type_default'
                case 1:
                    nwo.light_game_type = '_connected_geometry_bungie_light_type_uber'
                case 2:
                    nwo.light_game_type = '_connected_geometry_bungie_light_type_inlined'
                case 3:
                    nwo.light_game_type = '_connected_geometry_bungie_light_type_screen_space'
                case 4:
                    nwo.light_game_type = '_connected_geometry_bungie_light_type_rerender'
            
            nwo.light_screenspace_has_specular = element.SelectField("screen space specular").TestBit("screen space light has specular")
            nwo.light_bounce_ratio = element.SelectField("bounce light control").Data
            nwo.light_volume_distance = element.SelectField("light volume distance").Data
            nwo.light_volume_intensity = element.SelectField("light volume intensity scalar").Data
            nwo.light_fade_end_distance = element.SelectField("fade out distance").Data
            nwo.light_fade_start_distance = element.SelectField("fade start distance").Data
            nwo.light_tag_override = self.get_path_str(element.SelectField("user control").Path)
            nwo.light_shader_reference = self.get_path_str(element.SelectField("shader reference").Path)
            nwo.light_gel_reference = self.get_path_str(element.SelectField("gel reference").Path)
            nwo.light_lens_flare_reference = self.get_path_str(element.SelectField("lens flare reference").Path)
            
            objects.append(ob)
            
        return objects
    
    def _from_reach_light_definitions(self):
        definitions: dict[int: bpy.types.Light] = {}
        for element in self.block_generic_light_definitions.Elements:
            match element.SelectField("type").Value:
                case 0:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'POINT'))
                case 1:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'SPOT'))
                    hotspot_cutoff_size = element.SelectField("hotspot cutoff size").Data
                    blender_light.spot_size = radians(hotspot_cutoff_size)
                    if hotspot_cutoff_size > 0.0:
                        blender_light.spot_blend = element.SelectField("hotspot size").Data / hotspot_cutoff_size
                case 2:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'SUN'))
                    
            nwo = cast(NWO_LightPropertiesGroup, blender_light.nwo)
                    
            nwo.light_shape = '_connected_geometry_light_shape_circle' if element.SelectField("shape").Value == 1 else '_connected_geometry_light_shape_rectangle'
            color = Color((*element.SelectField("color").Data,))
            blender_light.color = color.from_srgb_to_scene_linear()
            nwo.light_intensity = element.SelectField("intensity").Data
            
            blender_light.shadow_soft_size = max((*element.SelectField("near attenuation bounds").Data,)) * WU_SCALAR
            nwo.light_far_attenuation_start, nwo.light_far_attenuation_end = [a * WU_SCALAR for a in element.SelectField("far attenuation bounds").Data]
            nwo.light_aspect = element.SelectField("aspect").Data
            
            blender_light.shadow_soft_size = nwo.light_near_attenuation_end
            
            definitions[element.ElementIndex] = blender_light
            
        return definitions
            
            
            