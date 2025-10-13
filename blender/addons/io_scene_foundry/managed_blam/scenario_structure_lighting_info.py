

from math import radians
from typing import cast

from mathutils import Matrix, Vector

from ..tools.property_apply import apply_props_material

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
            self.block_generic_light_definitions.RemoveAllElements()
            for _ in range(len(light_definitions)):
                self.block_generic_light_definitions.AddElement()
            self.block_generic_light_instances.RemoveAllElements()
            for _ in range(len(light_instances)):
                self.block_generic_light_instances.AddElement()
            
            # Save and load the tag again to get around some post process BS the reach tag does
            self.tag.Save()
            self.tag.Dispose()
            self.tag, self.tag_path = self._get_tag_and_path(False)
            self.tag.Load(self.tag_path)
            self._read_fields()
            
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
        # self.block_generic_light_definitions.RemoveAllElements()
        for idx, light in enumerate(light_definitions):
            element = self.block_generic_light_definitions.Elements[idx]
            light.index = element.ElementIndex
            element.SelectField("type").Value = light.type
            element.SelectField("shape").Value = light.shape
            element.SelectField("color").Data = light.color
            intensity_divisor = 1
            # Reach seems to fudge our intensity numbers based on whether the light is a point or spot light, fight back!
            # NOTE 23/07/2025 no longer need to do this with the tag post-process workaround
            # match light.type:
            #     case 0:
            #         intensity_divisor = 0.37735857955
            #     case 1:
            #         intensity_divisor = 3.14465382959
            #     case 2:
            #         intensity_divisor = 0.6289308
                    
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
        # self.block_generic_light_instances.RemoveAllElements()
        for idx, light in enumerate(light_instances):
            element = self.block_generic_light_instances.Elements[idx]
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
            element.SelectField("fade out distance").Data = light.fade_out_distance
            element.SelectField("fade start distance").Data = light.fade_start_distance
            
            if light.light_tag:
                element.SelectField("user control").Path = self._TagPath_from_string(light.light_tag)
            if light.shader:
                element.SelectField("shader reference").Path = self._TagPath_from_string(light.shader)
            if light.gel:
                element.SelectField("gel reference").Path = self._TagPath_from_string(light.gel)
            if light.lens_flare:
                element.SelectField("lens flare reference").Path = self._TagPath_from_string(light.lens_flare)
    
    def lightmap_regions_to_blender(self, parent_collection: bpy.types.Collection = None):
        if self.corinth:
            return []
        
        objects = []
        for region in self.tag.SelectField("Block:regions").Elements:
            triangles = region.Fields[1]
            tri_count = triangles.Elements.Count
            if tri_count == 0:
                continue
            
            name = region.Fields[0].GetStringData()
            data = cast(bpy.types.Mesh, bpy.data.meshes.new(name))
            
            vertices = [Vector(tri.Fields[i].Data) * 100 for tri in triangles.Elements for i in range(3)]
            faces = [list(range(i, i + 3)) for i in range(0, tri_count * 3, 3)]
            
            data.from_pydata(vertices=vertices, edges=[], faces=faces)
            data.nwo.mesh_type = '_connected_geometry_mesh_type_lightmap_region'
            
            ob = bpy.data.objects.new(name, data)
            apply_props_material(ob, 'LightmapRegion')
            objects.append(ob)
        
        if objects:
            coll_name = f"{self.tag_path.ShortName}_lightmap_regions"
            collection = bpy.data.collections.get(coll_name)
            if collection is None:
                collection = cast(bpy.types.Collection, bpy.data.collections.new(coll_name))
            for ob in objects:
                collection.objects.link(ob)
                
            if parent_collection is None:
                bpy.context.scene.collection.children.link(collection)
            else:
                parent_collection.children.link(collection)
                
        return objects
            
    
    def lightmap_regions_from_blender(self, region_objects: list[bpy.types.Object]):
        if self.corinth:
            return
        
        regions = self.tag.SelectField("Block:regions")
        start_count = regions.Elements.Count
        if start_count > 0:
            regions.RemoveAllElements()
        
        for ob in region_objects:
            matrix = utils.halo_transforms(ob)
            mesh = ob.to_mesh()
            mesh.transform(matrix)
            mesh.calc_loop_triangles()
            
            if not mesh.polygons:
                continue
            
            region = regions.AddElement()
            region.Fields[0].SetStringData(ob.name.lower())
            triangles = region.Fields[1]
            
            loop_tris = mesh.loop_triangles
            
            if len(loop_tris) > triangles.MaximumElementCount:
                utils.print_warning(f"Lightmap region exceeds loop triangle maximum. Has {len(loop_tris)}, max is {triangles.MaximumElementCount}")
                continue
            
            # print("MAX TRI COUNT= ", triangles.MaximumElementCount)
            
            for tri in mesh.loop_triangles:
                element = triangles.AddElement()
                for idx, i in enumerate(tri.loops):
                    vert = mesh.vertices[mesh.loops[i].vertex_index]
                    element.Fields[idx].Data = vert.co
            
            ob.to_mesh_clear()
            
        self.tag_has_changes = start_count > 0 or region_objects

                
    def to_blender(self, parent_collection: bpy.types.Collection = None):
        if self.corinth:
            definitions = self._from_corinth_light_definitions()
            objects = self._from_corinth_light_instances(definitions)
        else:
            definitions = self._from_reach_light_definitions()
            objects = self._from_reach_light_instances(definitions)
        
        if objects:
            collection_name = f"{self.tag_path.ShortName}_lighting_info"
            collection = bpy.data.collections.get(collection_name)
            if collection is None:
                collection = cast(bpy.types.Collection, bpy.data.collections.new(collection_name))
                # collection.nwo.type = 'permutation'
                if parent_collection is None:
                    bpy.context.scene.collection.children.link(collection)
                else:
                    parent_collection.children.link(collection)
                    
            for ob in objects:
                collection.objects.link(ob)

        return objects
    
    def _from_corinth_light_instances(self, definitions: dict[int: bpy.types.Light]):
        objects = []
        for element in self.block_generic_light_instances.Elements:
            blender_light = definitions.get(element.SelectField("Light Definition Index").Data)
            if blender_light is None:
                continue
            
            ob = cast(bpy.types.Object, bpy.data.objects.new(f"light_instance:{element.ElementIndex}", blender_light))
            nwo = cast(NWO_ObjectPropertiesGroup, ob.nwo)
            
            origin = Vector(*(element.SelectField("origin").Data,)) * 100
            forward = Vector((*element.SelectField("forward").Data,)).normalized()
            up = Vector((*element.SelectField("up").Data,)).normalized()
            left = up.cross(forward).normalized()
            
            matrix = Matrix((
                (forward[0], left[0], up[0], origin[0]),
                (forward[1], left[1], up[1], origin[1]),
                (forward[2], left[2], up[2], origin[2]),
                (0, 0, 0, 1),
            ))
            
            ob.matrix_world = matrix
            ob.scale *= (1 / 0.03048)
            
            match element.SelectField("light mode").Value:
                case 0:
                    nwo.light_mode = '_connected_geometry_light_mode_dynamic'
                case 1:
                    nwo.light_mode = '_connected_geometry_light_mode_static'
                case 2:
                    nwo.light_mode = '_connected_geometry_light_mode_analytic'
            
            objects.append(ob)
            
        return objects
    
    def _from_corinth_light_definitions(self):
        definitions: dict[int: bpy.types.Light] = {}
        for element in self.block_generic_light_definitions.Elements:
            parameters = element.SelectField("Struct:Midnight_Light_Parameters").Elements[0]
            match parameters.SelectField("Light Type").Value:
                case 0:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'POINT'))
                case 1:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'SPOT'))
                    hotspot_cutoff_size = parameters.SelectField("Inner Cone Angle").Data
                    hotpot_struct = parameters.SelectField("Outer Cone End")
                    hotspot = hotpot_struct.Elements[0]
                    hotspot_mapping = hotspot.SelectField("Custom:Mapping")
                    blender_light.spot_size = radians(hotspot_cutoff_size)
                    if hotspot_cutoff_size > 0.0:
                        blender_light.spot_blend = 1 - hotspot_mapping.Value.ClampRangeMin / hotspot_cutoff_size
                case 2:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'SUN'))
                    
            nwo = cast(NWO_LightPropertiesGroup, blender_light.nwo)
                    
            blender_light.color = [utils.srgb_to_linear(c) for c in parameters.SelectField("Light Color").Data]
            
            intensity_struct = parameters.SelectField("Intensity")
            intensity = intensity_struct.Elements[0]
            intensity_mapping = intensity.SelectField("Custom:Mapping")

            blender_light.energy = utils.calc_light_energy(blender_light, intensity_mapping.Value.ClampRangeMin)
            
            nwo.light_physically_correct = parameters.SelectField("Lighting Mode").Value == 0
            
            nwo.light_far_attenuation_start = parameters.SelectField("Distance Attenuation Start").Data * 100
            atten_struct = parameters.SelectField("Distance Attenuation End")
            atten = atten_struct.Elements[0]
            atten_mapping = atten.SelectField("Custom:Mapping")

            nwo.light_far_attenuation_end = atten_mapping.Value.ClampRangeMin * 100
            
            nwo.light_cone_projection_shape = '_connected_geometry_cone_projection_shape_cone' if parameters.SelectField("Cone Projection Shape").Value == 0 else '_connected_geometry_cone_projection_shape_frustum'
            
            # Dynamic props
            
            nwo.light_shadow_near_clipplane = parameters.SelectField("Shadow Near Clip Plane").Data
            nwo.light_shadow_far_clipplane = parameters.SelectField("Shadow Far Clip Plane").Data
            nwo.light_shadow_bias_offset = parameters.SelectField("Shadow Bias Offset").Data
            nwo.light_dynamic_shadow_quality = '_connected_geometry_dynamic_shadow_quality_normal' if parameters.SelectField("Dynamic Shadow Quality").Value == 0 else '_connected_geometry_dynamic_shadow_quality_expensive'
            nwo.light_shadows = parameters.SelectField("Shadows").Value == 1
            nwo.light_screenspace = parameters.SelectField("Screenspace Light").Value == 1
            nwo.light_ignore_dynamic_objects = parameters.SelectField("Ignore Dynamic Objects").Value == 1
            nwo.light_cinema_objects_only = parameters.SelectField("Cinema Objects Only").Value == 1
            if parameters.SelectField("Cinema Only").Value == 1:
                nwo.light_cinema = '_connected_geometry_lighting_cinema_only'
            if parameters.SelectField("Cinema Exclude").Value == 1:
                nwo.light_cinema = '_connected_geometry_lighting_cinema_exclude'
                
            nwo.light_specular_contribution = parameters.SelectField("Specular Contribution").Value == 1
            nwo.light_diffuse_contribution = parameters.SelectField("Diffuse Contribution").Value == 1
            
            # Static Props
            
            nwo.light_amplification_factor = element.SelectField("indirect amplification factor").Data
            nwo.light_jitter_sphere_radius = element.SelectField("jitter sphere radius").Data
            nwo.light_jitter_angle = radians(element.SelectField("jitter angle").Data)
            
            match element.SelectField("jitter quality").Value:
                case 0:
                    nwo.light_jitter_quality = '_connected_geometry_light_jitter_quality_low'
                case 1:
                    nwo.light_jitter_quality = '_connected_geometry_light_jitter_quality_medium'
                case 2:
                    nwo.light_jitter_quality = '_connected_geometry_light_jitter_quality_high'
                    
            nwo.light_indirect_only = element.SelectField("indirect only").Value == 1
            nwo.light_static_analytic = element.SelectField("static analytic").Value == 1
            
            definitions[element.ElementIndex] = blender_light
            
        return definitions
            
    def _from_reach_light_instances(self, definitions: dict[int: bpy.types.Light]):
        objects = []
        for element in self.block_generic_light_instances.Elements:
            blender_light = definitions.get(element.SelectField("definition index").Data)
            if blender_light is None:
                continue
            
            ob = cast(bpy.types.Object, bpy.data.objects.new(f"light_instance:{element.ElementIndex}", blender_light))
            nwo = cast(NWO_ObjectPropertiesGroup, ob.nwo)
            
            origin = Vector(*(element.SelectField("origin").Data,)) * 100
            forward = Vector((*element.SelectField("forward").Data,)).normalized()
            up = Vector((*element.SelectField("up").Data,)).normalized()
            left = up.cross(forward).normalized()
            
            matrix = Matrix((
                (forward[0], left[0], up[0], origin[0]),
                (forward[1], left[1], up[1], origin[1]),
                (forward[2], left[2], up[2], origin[2]),
                (0, 0, 0, 1),
            ))
            
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
                        blender_light.spot_blend = 1 - element.SelectField("hotspot size").Data / hotspot_cutoff_size
                case 2:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element.ElementIndex}", 'SUN'))
                    
            nwo = cast(NWO_LightPropertiesGroup, blender_light.nwo)
                    
            nwo.light_shape = '_connected_geometry_light_shape_circle' if element.SelectField("shape").Value == 1 else '_connected_geometry_light_shape_rectangle'
            blender_light.color = [utils.srgb_to_linear(c) for c in element.SelectField("color").Data]
            blender_light.energy = utils.calc_light_energy(blender_light, element.SelectField("intensity").Data)
            
            blender_light.shadow_soft_size = max((*element.SelectField("near attenuation bounds").Data,))
            nwo.light_far_attenuation_start, nwo.light_far_attenuation_end = [a for a in element.SelectField("far attenuation bounds").Data]
            nwo.light_aspect = element.SelectField("aspect").Data
            
            definitions[element.ElementIndex] = blender_light
            
        return definitions
            
            
            