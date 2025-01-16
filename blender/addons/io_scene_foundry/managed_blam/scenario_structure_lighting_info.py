

from ..managed_blam.Tags import TagFieldBlockElement
from ..managed_blam import Tag
from .. import utils

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
            parameters.SelectField("Inner Cone Angle").Data = light.hotspot_cutoff
            hotpot_struct = parameters.SelectField("Outer Cone End")
            hotspot = hotpot_struct.Elements[0]
            hotspot_mapping = hotspot.SelectField("Custom:Mapping")
            hotspot_mapping.Value.ClampRangeMin = light.hotspot_size
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